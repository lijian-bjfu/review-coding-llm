#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查归纳编码的饱和度。

手动测试：
1. 在 `02_inductive_coding_dir/batches/` 中准备多个 `batch_NN.csv`。
2. 运行 `python scripts/05_saturation_check.py --app example_app_test`。
3. 应按批次输出饱和度表格，并给出状态建议。
"""

from __future__ import annotations

import argparse
import re
import sys
from statistics import mean

from utils import (
    count_batch_entries,
    get_batches_dir,
    get_preprocessed_batch_path,
    list_completed_batches,
    parse_coding_csv,
    print_warning,
)

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# 在 VS Code 中直接点击"运行"时，修改下方变量来替代命令行参数。
# 命令行执行时这些变量会被忽略。
# =============================================================================

VSCODE_APP = "一起来捉妖"
# 要检查饱和度的应用名，需与初始化时使用的名称一致
# 运行前请确保 02_inductive_coding_dir/batches/ 中已有 batch_NN_coding.csv

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(app=VSCODE_APP)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="检查归纳编码阶段的饱和度。")
    parser.add_argument("--app", required=True, help="应用名。")
    return parser


def get_batch_csv_paths(app: str, batch_id: int) -> list:
    """返回某个 batch_id 下所有主题的 CSV 文件路径列表。"""
    batches_dir = get_batches_dir(app, "inductive")
    pattern = f"batch_{batch_id:02d}_*.csv"
    paths = sorted(batches_dir.glob(pattern))
    # 排除 .meta.json 等非 CSV 文件（glob 已限定 *.csv，这里是防御性检查）
    return [p for p in paths if p.suffix == ".csv"]


def render_float(value: float | None) -> str:
    """格式化浮点数。"""
    return "-" if value is None else f"{value:.1f}"


def get_status(rolling_avg: float | None) -> tuple[str, str]:
    """根据滚动均值给出状态提示。"""
    if rolling_avg is None:
        return "状态：样本不足，暂无法判断饱和度", "建议：至少完成 3 批后再观察趋势"
    if rolling_avg >= 5:
        return "状态：远未饱和，继续编码", "建议：继续追加批次，观察新增编码是否开始明显下降"
    if rolling_avg >= 3:
        return "状态：趋于饱和，可考虑进入收尾", "建议：可再增加 1-2 批，确认是否还有稳定新增编码"
    return "状态：接近饱和，建议再跑1批验证后结束", "建议：若下一批新增仍很少，可结束归纳阶段"


def main() -> None:
    """脚本入口。"""
    args = get_args()
    completed_batches = list_completed_batches(args.app)
    if not completed_batches:
        raise FileNotFoundError(
            "未找到任何已完成的批次编码文件。\n"
            "请先在 `02_inductive_coding_dir/batches/` 中保存批次编码 CSV。"
        )

    seen_codes: set[str] = set()
    new_code_history: list[int] = []
    rows: list[dict[str, str]] = []

    for batch_id in completed_batches:
        # 读取该批次下所有主题的 CSV，合并后统计
        csv_paths = get_batch_csv_paths(args.app, batch_id)
        if not csv_paths:
            print_warning(f"批次 {batch_id:02d} 未找到任何 CSV 文件，已跳过。")
            continue

        batch_codes: set[str] = set()
        for csv_path in csv_paths:
            coding_df = parse_coding_csv(csv_path)
            codes = {str(code).strip() for code in coding_df["分类"].tolist() if str(code).strip()}
            batch_codes.update(codes)

        new_codes = len(batch_codes - seen_codes)
        seen_codes.update(batch_codes)
        unique_codes = len(seen_codes)
        new_code_history.append(new_codes)

        # 统计该批次的数据量
        try:
            batch_text = get_preprocessed_batch_path(args.app, batch_id).read_text(encoding="utf-8")
            data_count = count_batch_entries(batch_text)
        except FileNotFoundError:
            data_count = 0
            print_warning(f"批次 {batch_id:02d} 的原始 txt 文件未找到，数据量显示为 0。")

        if data_count == 0:
            print_warning(f"批次 {batch_id:02d} 未统计到任何记录，新增率将显示为 0。")
        new_rate = (new_codes / data_count * 100) if data_count else 0.0
        rolling_avg = mean(new_code_history[-3:]) if len(new_code_history) >= 3 else None

        rows.append(
            {
                "批次": str(batch_id),
                "总编码数": str(unique_codes),
                "新增": str(new_codes),
                "数据量": str(data_count),
                "新增率": f"{new_rate:.1f}%",
                "滚动均值(3批)": render_float(rolling_avg),
            }
        )

    if not rows:
        print("未能解析任何批次数据。")
        return

    headers = ["批次", "总编码数", "新增", "数据量", "新增率", "滚动均值(3批)"]
    widths = {header: max(len(header), *(len(row[header]) for row in rows)) for header in headers}
    print("  ".join(header.ljust(widths[header]) for header in headers))
    for row in rows:
        print("  ".join(row[header].ljust(widths[header]) for header in headers))

    final_avg = mean(new_code_history[-3:]) if len(new_code_history) >= 3 else None
    status, suggestion = get_status(final_avg)
    print()
    print(status)
    print(suggestion)


if __name__ == "__main__":
    main()
