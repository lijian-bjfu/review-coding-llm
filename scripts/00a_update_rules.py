#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 prompts/ 下的最新 base_rules 同步到项目 knowledge/ 目录。

用途：当研究者修改了 prompts/inductive/00_base_rules.txt（或 deductive）后，
运行本脚本将新版本同步到指定项目的 knowledge/ 目录，不影响其他文件
（codebook_current、rolling_rules、focus、prompt_log 等均不动）。

手动测试：
1. 修改 prompts/inductive/00_base_rules.txt 的任意内容
2. 运行 `python scripts/00a_update_rules.py --app example_app_test --stage inductive`
3. 检查 data_dir/example_app_test_dir/02_inductive_coding_dir/knowledge/00_base_rules.txt
   应与 prompts/inductive/00_base_rules.txt 内容一致
4. 检查同目录下其他文件（01_rolling_rules.txt、02_codebook_current.md 等）未被修改
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils import (
    review as PROMPTS_DIR,
    PROJECT_ROOT,
    get_knowledge_dir,
    validate_app_name,
    write_meta,
)

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# =============================================================================

VSCODE_APP = "一起来捉妖"
# 要更新的应用名

VSCODE_STAGE = "inductive"
# 要更新的阶段："inductive" 或 "deductive"

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(app=VSCODE_APP, stage=VSCODE_STAGE)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(
        description="将 prompts/ 下的最新 base_rules 同步到项目 knowledge/ 目录。"
    )
    parser.add_argument("--app", required=True, help="应用名。")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["inductive", "deductive"],
        help="要更新的阶段。",
    )
    return parser


def main() -> None:
    """脚本入口。"""
    args = get_args()
    validate_app_name(args.app)

    # 源文件：prompts/<stage>/00_base_rules.txt
    source_path = PROMPTS_DIR / args.stage / "00_base_rules.txt"
    if not source_path.is_file():
        raise FileNotFoundError(
            f"未找到源模板：{source_path.relative_to(PROJECT_ROOT)}\n"
            f"请确认 prompts/{args.stage}/00_base_rules.txt 存在。"
        )

    # 目标文件：data_dir/<app>_dir/<stage_dir>/knowledge/00_base_rules.txt
    knowledge_dir = get_knowledge_dir(args.app, args.stage)
    target_path = knowledge_dir / "00_base_rules.txt"

    if not knowledge_dir.exists():
        raise FileNotFoundError(
            f"项目 knowledge 目录不存在：{knowledge_dir.relative_to(PROJECT_ROOT)}\n"
            f"请先运行 `python scripts/00_setup_proj.py --app {args.app}` 初始化项目。"
        )

    # 读取并比较
    source_content = source_path.read_text(encoding="utf-8")

    if target_path.exists():
        current_content = target_path.read_text(encoding="utf-8")
        if current_content == source_content:
            print(f"[跳过] base_rules 已是最新版本，无需更新。")
            return

    # 写入
    target_path.write_text(source_content, encoding="utf-8")
    write_meta(
        target_path,
        {
            "app": args.app,
            "stage": args.stage,
            "action": "update_base_rules",
            "source_path": source_path,
        },
    )

    print(f"[OK] base_rules 已更新")
    print(f"     源文件：{source_path.relative_to(PROJECT_ROOT)}")
    print(f"     目标：  {target_path.relative_to(PROJECT_ROOT)}")
    print(f"")
    print(f"     以下文件未受影响：")

    # 列出 knowledge/ 下其他文件，确认未被动
    for f in sorted(knowledge_dir.iterdir()):
        if f.name == "00_base_rules.txt" or f.suffix == ".json" and "meta" in f.name:
            continue
        if f.name.endswith(".meta.json"):
            continue
        print(f"       ✓ {f.name}")


if __name__ == "__main__":
    main()
