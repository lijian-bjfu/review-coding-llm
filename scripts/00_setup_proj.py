#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""初始化 app 项目目录。

手动测试：
运行 `python scripts/00_setup_proj.py --app example_app_test` 后，应看到
`data_dir/example_app_test_dir/` 及其子目录被创建，`knowledge/` 下应包含四层记忆文件与 `prompt_log.json`，
并创建 `prompt_logs/` 目录。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from utils import (
    review,
    PROJECT_ROOT,
    ensure_can_write,
    get_app_dir,
    get_prompt_log_path,
    validate_app_name,
    write_meta,
)

__version__ = "0.1.0"

# =============================================================================
# VS Code 运行配置
# 在 VS Code 中直接点击"运行"时，修改下方变量来替代命令行参数。
# 命令行执行时这些变量会被忽略。
# =============================================================================

VSCODE_APP = "一起来捉妖"
# 要初始化的应用名，支持英文小写字母、数字、下划线或汉字，例如 "myworld"、"一起来捉妖"

VSCODE_OVERWRITE = False
# 若项目目录已存在是否允许覆盖（True = 允许，False = 已存在时报错退出）

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    # VS Code 直接运行时 sys.argv 只含脚本路径，使用顶部配置变量
    return argparse.Namespace(app=VSCODE_APP, overwrite=VSCODE_OVERWRITE)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="初始化一个 app 的项目目录结构。")
    parser.add_argument("--app", required=True, help="应用名，支持英文小写字母、数字、下划线或汉字。")
    parser.add_argument("--overwrite", action="store_true", help="若目标目录已存在，允许覆盖已存在文件。")
    return parser


def ensure_project_can_initialize(app_dir: Path, overwrite: bool) -> None:
    """校验项目目录是否允许初始化。"""
    if app_dir.exists() and not overwrite:
        raise FileExistsError(
            f"项目目录已存在：{app_dir.relative_to(PROJECT_ROOT)}\n"
            "如需覆盖初始化，请追加 `--overwrite` 参数。"
        )


def write_text_file(target_path: Path, content: str, overwrite: bool, params: dict[str, object]) -> None:
    """写入文本文件并生成 meta。"""
    ensure_can_write(target_path, overwrite)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    write_meta(target_path, params)


def copy_template(source_path: Path, target_path: Path, overwrite: bool, params: dict[str, object]) -> None:
    """复制模板文件并生成 meta。"""
    ensure_can_write(target_path, overwrite)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    write_meta(target_path, params | {"source_path": source_path})


def main() -> None:
    """脚本入口。"""
    args = get_args()
    validate_app_name(args.app)

    app_dir = get_app_dir(args.app)
    ensure_project_can_initialize(app_dir, args.overwrite)

    directories = [
        app_dir / "00_rawdata_dir",
        app_dir / "01_preprocessed_for_llm_dir",
        app_dir / "02_inductive_coding_dir" / "knowledge",
        app_dir / "02_inductive_coding_dir" / "batches",
        app_dir / "02_inductive_coding_dir" / "prompt_logs",
        app_dir / "03_deductive_coding_dir" / "knowledge",
        app_dir / "03_deductive_coding_dir" / "batches",
        app_dir / "03_deductive_coding_dir" / "prompt_logs",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    copy_template(
        review / "inductive" / "00_base_rules.txt",
        app_dir / "02_inductive_coding_dir" / "knowledge" / "00_base_rules.txt",
        args.overwrite,
        {"app": args.app, "stage": "inductive", "action": "init_base_rules"},
    )
    copy_template(
        review / "inductive" / "01_rolling_rules_template.txt",
        app_dir / "02_inductive_coding_dir" / "knowledge" / "01_rolling_rules.txt",
        args.overwrite,
        {"app": args.app, "stage": "inductive", "action": "init_rolling_rules"},
    )
    copy_template(
        review / "inductive" / "02_codebook_current_template.md",
        app_dir / "02_inductive_coding_dir" / "knowledge" / "02_codebook_current.md",
        args.overwrite,
        {"app": args.app, "stage": "inductive", "action": "init_codebook"},
    )
    copy_template(
        review / "inductive" / "03_focus_template.txt",
        app_dir / "02_inductive_coding_dir" / "knowledge" / "03_focus.txt",
        args.overwrite,
        {"app": args.app, "stage": "inductive", "action": "init_focus"},
    )

    copy_template(
        review / "deductive" / "00_base_rules.txt",
        app_dir / "03_deductive_coding_dir" / "knowledge" / "00_base_rules.txt",
        args.overwrite,
        {"app": args.app, "stage": "deductive", "action": "init_base_rules"},
    )

    prompt_log_path = get_prompt_log_path(args.app)
    write_text_file(
        prompt_log_path,
        json.dumps({"batches": []}, ensure_ascii=False, indent=2),
        args.overwrite,
        {"app": args.app, "stage": "inductive", "action": "init_prompt_log"},
    )
    print(f"[OK] 项目已初始化：{app_dir.relative_to(PROJECT_ROOT)}/")
    print("下一步：")
    print(f"  1. 将清洗后的数据放到 data_dir/{args.app}_dir/00_rawdata_dir/{args.app}.csv")
    print("  2. 编辑聚焦主题文件：")
    print(f"     data_dir/{args.app}_dir/02_inductive_coding_dir/knowledge/03_focus.txt")
    print(f"  3. 运行：python scripts/01_sampling_data.py --app {args.app} --batch_size 100 --n_batches 5")


if __name__ == "__main__":
    main()
