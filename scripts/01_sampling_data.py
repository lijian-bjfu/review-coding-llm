#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从原始数据随机抽样并切分为批次。

功能：
- 抽样日志：自动记录已抽取 ID，续接历史，自动排除重复数据
- 评分分层抽样(--stratify)：按各星级自然比例分配名额
- 评论长度过滤(--min_len)：过滤过短评论
- 宽容模式：可用数据不足时尽量抽取，并给出具体提示

写入策略：
- 批次文件 batch_NN.txt：遵循 --overwrite 参数。续抽时新 batch_id 自动递增，
  不会覆盖旧批次；只有用户想重跑已有批次时才需要 --overwrite。
- unused.txt、sampled_log.csv：**总是覆盖**。它们反映"项目当前状态"，
  每次抽样后本就应该刷新，不受 --overwrite 影响。

手动测试：
1. 先运行 `python scripts/00_setup_proj.py --app example_app_test`
2. 在 `data_dir/example_app_test_dir/00_rawdata_dir/example_app_test.csv`
   放入至少 10 条测试数据(含 name/rating/review 列)
3. 运行 `python scripts/01_sampling_data.py --app example_app_test --batch_size 2 --n_batches 2`
   应生成 batch_00.txt、batch_01.txt、unused.txt、sampled_log.csv 及各自的 `.meta.json`
4. 再次运行同一命令(无需 --overwrite)，应从剩余数据中续接抽取
   (batch_02.txt、batch_03.txt)，日志累计更新
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from utils import (
    ensure_can_write,
    ensure_parent_dir,
    get_preprocessed_batch_path,
    get_rawdata_path,
    get_sampling_log_path,
    get_unused_path,
    load_rawdata,
    print_warning,
    write_meta,
)

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# 在 VS Code 中直接点击"运行"时，修改下方变量来替代命令行参数。
# 命令行执行时这些变量会被忽略。
# =============================================================================

VSCODE_APP = "一起来捉妖"
# 要处理的应用名，需与 00_setup_proj.py 初始化时使用的名称一致

VSCODE_BATCH_SIZE = 50
# 每批包含的评论条数，建议 50–100

VSCODE_N_BATCHES = 5
# 本次希望生成的批次数；若可用数据不足则自动减少并给出提示

VSCODE_SEED = 42
# 随机抽样种子，固定后可复现相同的抽样结果

VSCODE_MIN_LEN = 20
# 评论最少字符数(0 = 不限制)；字符数低于此值的评论在进入抽样池前被过滤掉

VSCODE_STRATIFY = True
# 是否按 rating 列分层抽样
# True  = 按各星级在可用数据中的自然比例分配名额，保证样本分布均衡
# False = 纯随机抽样

VSCODE_OVERWRITE = False
# 若批次文件已存在是否允许覆盖(True = 允许，False = 已存在时报错退出)
# 注意：unused.txt 和 sampled_log.csv 不受此参数控制，每次运行都会刷新

# =============================================================================

# 日志列定义：name=条目ID，global_seq=全局序号，batch_id=所属批次编号
_LOG_COLUMNS = ["name", "global_seq", "batch_id"]


# ---------------------------------------------------------------------------
# 日志读写
# ---------------------------------------------------------------------------

def load_sampling_log(app: str) -> pd.DataFrame:
    """加载抽样日志；若不存在则返回空 DataFrame。"""
    log_path = get_sampling_log_path(app)
    if not log_path.exists():
        return pd.DataFrame(columns=_LOG_COLUMNS)
    return pd.read_csv(log_path, encoding="utf-8-sig", dtype={"name": str})


def append_to_log(app: str, new_rows: pd.DataFrame) -> None:
    """将本次抽样记录追加到日志(日志只增不减)。

    日志文件是"项目状态文件"，每次抽样后总是覆盖写入完整历史。
    """
    log_path = get_sampling_log_path(app)
    existing = load_sampling_log(app)
    combined = pd.concat([existing, new_rows], ignore_index=True)
    ensure_parent_dir(log_path)
    combined.to_csv(log_path, index=False, encoding="utf-8-sig")
    write_meta(
        log_path,
        {
            "app": app,
            "source_path": get_rawdata_path(app),
            "output_type": "sampling_log",
            "rows": len(combined),
        },
    )


# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------

def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(
        app=VSCODE_APP,
        batch_size=VSCODE_BATCH_SIZE,
        n_batches=VSCODE_N_BATCHES,
        seed=VSCODE_SEED,
        min_len=VSCODE_MIN_LEN,
        stratify=VSCODE_STRATIFY,
        overwrite=VSCODE_OVERWRITE,
    )


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="从原始数据随机抽样并切分为多个不重叠批次。")
    parser.add_argument("--app", required=True, help="应用名。")
    parser.add_argument("--batch_size", required=True, type=int, help="每批数据量。")
    parser.add_argument("--n_batches", required=True, type=int, help="期望生成的批次数。")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，默认 42。")
    parser.add_argument(
        "--min_len", type=int, default=0,
        help="评论最少字符数(0 = 不限制)；低于此值的评论在抽样前被过滤。",
    )
    parser.add_argument(
        "--stratify", action="store_true",
        help="按 rating 列的自然比例分层抽样(默认为纯随机)。",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="若批次文件(batch_NN.txt)已存在，允许覆盖。"
             "unused.txt 和 sampled_log.csv 不受此参数影响，总是刷新。",
    )
    return parser


# ---------------------------------------------------------------------------
# 抽样逻辑
# ---------------------------------------------------------------------------

def validate_positive_int(name: str, value: int) -> None:
    """校验正整数参数。"""
    if value > 0:
        return
    raise ValueError(f"`{name}` 必须是正整数，当前值为:{value}")


def normalize_comment(comment: Any) -> str:
    """将评论整理为单行文本(替换换行符、合并多余空格)。"""
    text = "" if comment is None else str(comment)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())


def format_entry(name: Any, rating: Any, review: Any) -> str:
    """将单条评论格式化为 LLM 友好的段落。"""
    return f"[ID:{name}] [rating:{rating}] {normalize_comment(review)}"


def stratified_sample(df: pd.DataFrame, n_total: int, seed: int) -> pd.DataFrame:
    """按 rating 列的自然比例分层抽样，合计返回 n_total 条(或全部可用数据，取较小值)。

    分配策略：
    - 各星级的名额 = round(n_total × 该星级占比)
    - 最后一个星级补齐舍入误差，确保总数准确
    - 某星级数据不足时全部取出，剩余名额按比例补给其他星级
    """
    n_total = min(n_total, len(df))
    groups = sorted(df["rating"].unique())
    total_available = len(df)

    # 第一轮：按比例分配名额
    quotas: dict[Any, int] = {}
    allocated = 0
    for i, rating in enumerate(groups):
        group_df = df[df["rating"] == rating]
        if i == len(groups) - 1:
            quota = n_total - allocated  # 最后一组补齐误差
        else:
            quota = round(n_total * len(group_df) / total_available)
        quotas[rating] = min(quota, len(group_df))
        allocated += quotas[rating]

    # 第二轮：若某组不足导致 allocated < n_total，将余额补给有富余的组
    shortfall = n_total - allocated
    if shortfall > 0:
        for rating in groups:
            if shortfall <= 0:
                break
            group_size = len(df[df["rating"] == rating])
            extra = min(shortfall, group_size - quotas[rating])
            if extra > 0:
                quotas[rating] += extra
                shortfall -= extra

    parts = [
        df[df["rating"] == rating].sample(n=quotas[rating], random_state=seed)
        for rating in groups
        if quotas[rating] > 0
    ]
    return pd.concat(parts).sample(frac=1, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 输出写入
# ---------------------------------------------------------------------------

def write_output(
    path: Path,
    content: str,
    overwrite: bool,
    params: dict[str, Any],
    *,
    force: bool = False,
) -> None:
    """写入文本输出与 meta。

    Args:
        path: 输出文件路径
        content: 文本内容
        overwrite: --overwrite 参数值(是否允许覆盖已存在文件)
        params: 写入 .meta.json 的参数字典
        force: 若为 True，**无条件覆盖**，忽略 overwrite 参数。
               用于"项目状态文件"(unused.txt、sampled_log.csv)——
               它们本就应该每次运行都刷新。
    """
    if not force:
        ensure_can_write(path, overwrite)
    ensure_parent_dir(path)
    path.write_text(content, encoding="utf-8")
    write_meta(path, params)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    """脚本入口。"""
    args = get_args()
    validate_positive_int("batch_size", args.batch_size)
    validate_positive_int("n_batches", args.n_batches)

    # ── 1. 读入原始数据 ──────────────────────────────────────────────────────
    df = load_rawdata(args.app)
    print(f"读入原始数据:{len(df)} 条")

    # ── 2. 过滤过短评论 ──────────────────────────────────────────────────────
    if args.min_len > 0:
        before = len(df)
        df = df[df["review"].astype(str).str.len() >= args.min_len].reset_index(drop=True)
        filtered_out = before - len(df)
        if filtered_out:
            print(f"[过滤] 去除字符数 < {args.min_len} 的评论 {filtered_out} 条，剩余 {len(df)} 条")

    # ── 3. 加载日志，排除历史已抽取数据 ─────────────────────────────────────
    log_df = load_sampling_log(args.app)
    if not log_df.empty:
        already_sampled: set[str] = set(log_df["name"].astype(str))
        before = len(df)
        df = df[~df["name"].astype(str).isin(already_sampled)].reset_index(drop=True)
        excluded = before - len(df)
        print(f"[日志] 排除历史已抽取数据 {excluded} 条，剩余可用 {len(df)} 条")
    else:
        print("[日志] 未找到抽样日志，从全部数据开始抽取")

    # ── 4. 检查可用数据量 ────────────────────────────────────────────────────
    if len(df) == 0:
        raise ValueError(
            "排除历史抽样记录后，可用数据为空。\n"
            "可能的原因:\n"
            "1. 原始数据已全部被抽完\n"
            "2. --min_len 过滤条件过严，请调小或设为 0\n"
            f"抽样日志位置:{get_sampling_log_path(args.app)}"
        )

    # ── 5. 确定实际可抽数量(宽容：不足时尽量抽) ─────────────────────────────
    requested = args.batch_size * args.n_batches
    warnings_to_print: list[str] = []

    if len(df) < requested:
        warnings_to_print.append(
            f"可用数据 {len(df)} 条，少于请求量 "
            f"{args.batch_size} × {args.n_batches} = {requested} 条"
        )

    actual_count = min(len(df), requested)
    # 向上取整：最后一批可能不满
    actual_batches = (actual_count + args.batch_size - 1) // args.batch_size

    if actual_batches < args.n_batches:
        last_batch_size = actual_count - (actual_batches - 1) * args.batch_size
        warnings_to_print.append(
            f"实际生成 {actual_batches} 个批次(请求 {args.n_batches} 个)；"
            f"最后一批仅 {last_batch_size} 条"
        )

    # ── 6. 抽样 ──────────────────────────────────────────────────────────────
    if args.stratify:
        if "rating" not in df.columns:
            print_warning("未找到 rating 列，已退回为纯随机抽样")
            sampled_df = df.sample(n=actual_count, random_state=args.seed, replace=False)
        else:
            sampled_df = stratified_sample(df, actual_count, args.seed)
    else:
        sampled_df = df.sample(n=actual_count, random_state=args.seed, replace=False)

    sampled_df = sampled_df.reset_index(drop=True)

    # 未使用数据：按 name 排除本次实际抽中的记录，避免 reset_index 后误删。
    sampled_names = set(sampled_df["name"].astype(str))
    unused_df = df[~df["name"].astype(str).isin(sampled_names)].reset_index(drop=True)

    # ── 7. 确定本次全局序号和批次编号起点 ────────────────────────────────────
    next_seq: int = int(log_df["global_seq"].max()) + 1 if not log_df.empty else 1
    next_batch_id: int = int(log_df["batch_id"].max()) + 1 if not log_df.empty else 0

    # ── 8. 写批次文件并收集日志条目 ──────────────────────────────────────────
    # 批次文件遵循 --overwrite(force=False)——保护旧批次不被误覆盖
    rawdata_path = get_rawdata_path(args.app)
    common_meta: dict[str, Any] = {
        "app": args.app,
        "batch_size": args.batch_size,
        "n_batches": actual_batches,
        "seed": args.seed,
        "min_len": args.min_len,
        "stratify": args.stratify,
        "source_path": rawdata_path,
    }

    new_log_rows: list[dict[str, Any]] = []
    seq = next_seq

    for local_idx in range(actual_batches):
        start = local_idx * args.batch_size
        end = min(start + args.batch_size, actual_count)
        batch_df = sampled_df.iloc[start:end]
        batch_id = next_batch_id + local_idx

        lines: list[str] = []
        for _, row in batch_df.iterrows():
            lines.append(format_entry(row["name"], row["rating"], row["review"]))
            new_log_rows.append({
                "name": str(row["name"]),
                "global_seq": seq,
                "batch_id": batch_id,
            })
            seq += 1

        batch_path = get_preprocessed_batch_path(args.app, batch_id)
        write_output(
            batch_path,
            "\n\n".join(lines),
            args.overwrite,
            common_meta | {"batch_id": batch_id, "output_type": "batch_txt"},
            # force=False(默认)：批次文件受 --overwrite 保护
        )

    # ── 9. 写未使用数据文件(force=True：项目状态文件，总是刷新) ─────────────
    unused_path = get_unused_path(args.app)
    unused_header = (
        "# 未使用数据(仅供参考，非批次文件)\n"
        "# 这里是当前剩余、尚未进入任何批次的评论。\n"
        "# 每次运行 01_sampling_data.py 后本文件会被刷新。\n\n"
    )
    unused_body = "\n\n".join(
        format_entry(row["name"], row["rating"], row["review"])
        for _, row in unused_df.iterrows()
    )
    unused_content = unused_header + unused_body if unused_body else unused_header + "(无剩余数据)\n"
    write_output(
        unused_path,
        unused_content,
        args.overwrite,
        common_meta | {"unused_count": len(unused_df), "output_type": "unused_txt"},
        force=True,  # 项目状态文件，总是覆盖
    )

    # ── 10. 更新抽样日志(force=True：项目状态文件，总是刷新) ────────────────
    append_to_log(args.app, pd.DataFrame(new_log_rows))

    # ── 11. 输出结果摘要 ─────────────────────────────────────────────────────
    for w in warnings_to_print:
        print_warning(w)

    batch_range = (
        f"batch_{next_batch_id:02d}"
        if actual_batches == 1
        else f"batch_{next_batch_id:02d} – batch_{next_batch_id + actual_batches - 1:02d}"
    )
    print(f"[OK] 已生成 {actual_batches} 个批次文件({batch_range})，共 {actual_count} 条")
    print(f"批次目录:{get_preprocessed_batch_path(args.app, next_batch_id).parent}")
    print(f"全局序号:{next_seq} – {seq - 1}")
    print(f"剩余未使用数据:{len(unused_df)} 条 → {unused_path.name}")
    print(f"抽样日志:{get_sampling_log_path(args.app)}")

    if args.stratify and "rating" in sampled_df.columns:
        print("\n本次抽样评分分布:")
        dist = sampled_df["rating"].value_counts().sort_index()
        for rating, count in dist.items():
            print(f"  {rating} 星:{count} 条")


if __name__ == "__main__":
    main()