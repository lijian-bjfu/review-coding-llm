#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并所有批次的编码 CSV。

手动测试：
1. 在 `02_inductive_coding_dir/batches/` 中准备若干 `batch_NN_coding.csv`。
2. 运行 `python scripts/03_merge_codings.py --app example_app_test`。
3. 应生成 `codebook_merged.csv`，并打印原始行数、去重后行数和每类引文数。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from utils import (
    CODING_REQUIRED_COLUMNS,
    ensure_can_write,
    get_app_subdir,
    get_batches_dir,
    parse_coding_csv,
    write_meta,
)

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# 在 VS Code 中直接点击"运行"时，修改下方变量来替代命令行参数。
# 命令行执行时这些变量会被忽略。
# =============================================================================

VSCODE_APP = "myworld"
# 要合并编码结果的应用名，需与初始化时使用的名称一致

VSCODE_OVERWRITE = False
# 若 codebook_merged.csv 已存在是否允许覆盖（True = 允许，False = 已存在时报错退出）

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(app=VSCODE_APP, overwrite=VSCODE_OVERWRITE)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="合并所有批次的编码 CSV，输出统一结果。")
    parser.add_argument("--app", required=True, help="应用名。")
    parser.add_argument("--overwrite", action="store_true", help="若输出文件已存在，允许覆盖。")
    return parser


def main() -> None:
    """脚本入口。"""
    args = get_args()

    batches_dir = get_batches_dir(args.app, "inductive")
    coding_paths = sorted(batches_dir.glob("batch_*_coding.csv"))
    if not coding_paths:
        raise FileNotFoundError(
            f"未在 {batches_dir} 找到任何 `batch_NN_coding.csv` 文件。\n"
            "请先将 LLM 输出保存为批次编码 CSV。"
        )

    frames = []
    total_rows = 0
    for path in coding_paths:
        frame = parse_coding_csv(path)
        total_rows += len(frame)
        frames.append(frame)

    merged_df = pd.concat(frames, ignore_index=True)
    merged_df = merged_df.drop_duplicates(subset=CODING_REQUIRED_COLUMNS, keep="first")
    merged_df = merged_df.sort_values(by=["分类", "检索词"], kind="stable").reset_index(drop=True)

    output_path = get_app_subdir(args.app, "02_inductive_coding_dir") / "codebook_merged.csv"
    ensure_can_write(output_path, args.overwrite)
    merged_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    write_meta(
        output_path,
        {
            "app": args.app,
            "source_paths": coding_paths,
            "output_type": "merged_codebook",
        },
    )

    print(f"[OK] 已输出：{output_path}")
    print(f"原始行数：{total_rows}")
    print(f"去重后行数：{len(merged_df)}")
    print(f"编码数：{merged_df['分类'].nunique()}")
    counts = merged_df.groupby("分类").size().sort_values(ascending=False)
    print("每个编码的引文数：")
    for category, count in counts.items():
        print(f"- {category}: {count}")


if __name__ == "__main__":
    main()
