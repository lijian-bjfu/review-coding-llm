#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从合并后的编码表生成 MAXQDA 字典 Excel。

手动测试：
1. 先运行 `python scripts/03_merge_codings.py --app example_app_test` 生成 `codebook_merged.csv`。
2. 再运行 `python scripts/04_build_dictionary.py --app example_app_test`。
3. 应生成 `codebook_final.xlsx`，用 Excel 打开后只包含 `分类`、`检索词` 两列。
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from utils import ensure_can_write, ensure_file_exists, get_app_subdir, validate_columns, write_meta

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# 在 VS Code 中直接点击"运行"时，修改下方变量来替代命令行参数。
# 命令行执行时这些变量会被忽略。
# =============================================================================

VSCODE_APP = "myworld"
# 要导出字典的应用名，需与初始化时使用的名称一致
# 运行前请确保已执行 03_merge_codings.py 生成 codebook_merged.csv

VSCODE_OVERWRITE = False
# 若 codebook_final.xlsx 已存在是否允许覆盖（True = 允许，False = 已存在时报错退出）

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(app=VSCODE_APP, overwrite=VSCODE_OVERWRITE)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="从 codebook_merged.csv 生成 MAXQDA 字典 Excel。")
    parser.add_argument("--app", required=True, help="应用名。")
    parser.add_argument("--overwrite", action="store_true", help="若输出文件已存在，允许覆盖。")
    return parser


def main() -> None:
    """脚本入口。"""
    args = get_args()
    merged_path = get_app_subdir(args.app, "02_inductive_coding_dir") / "codebook_merged.csv"
    ensure_file_exists(
        merged_path,
        [
            f"请先运行 `python scripts/03_merge_codings.py --app {args.app}` 生成合并结果",
        ],
    )

    df = pd.read_csv(merged_path, encoding="utf-8-sig")
    validate_columns(df, ["分类", "检索词"])
    output_path = get_app_subdir(args.app, "02_inductive_coding_dir") / "codebook_final.xlsx"
    ensure_can_write(output_path, args.overwrite)
    df[["分类", "检索词"]].to_excel(output_path, index=False, engine="openpyxl")
    write_meta(
        output_path,
        {
            "app": args.app,
            "source_path": merged_path,
            "output_type": "maxqda_dictionary",
        },
    )

    print(f"[OK] 已生成 MAXQDA 字典：{output_path}")
    print("导入指引：在 MAXQDA 中选择字典导入，文件类型选择 Excel，仅保留 `分类` 和 `检索词` 两列。")


if __name__ == "__main__":
    main()
