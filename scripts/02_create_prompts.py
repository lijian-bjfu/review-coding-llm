#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装四层记忆与批次数据，生成完整 prompt。

手动测试：
1. 先运行 `python scripts/00_setup_proj.py --app example_app_test`。
2. 再运行 `python scripts/01_sampling_data.py --app example_app_test --batch_size 2 --n_batches 1`。
3. 运行 `python scripts/02_create_prompts.py --app example_app_test --batch 0 --stage inductive`，
   应输出包含四层记忆与批次数据的完整 prompt，并在 `prompt_logs/` 留存副本。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils import (
    ensure_can_write,
    ensure_file_exists,
    ensure_parent_dir,
    get_codebook_current_path,
    get_knowledge_dir,
    get_preprocessed_batch_path,
    get_prompt_logs_dir,
    get_rolling_rules_path,
    read_batch_file,
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

VSCODE_BATCH = 0
# 要组装 prompt 的批次编号，从 0 开始，对应 batch_00.txt、batch_01.txt……

VSCODE_STAGE = "inductive"
# 编码阶段，可选值："inductive"（归纳编码）或 "deductive"（演绎编码）

VSCODE_CLIPBOARD = False
# 是否将生成的 prompt 复制到系统剪贴板（需安装 pyperclip；True = 复制，False = 输出到控制台）

VSCODE_OUTPUT: str | None = None
# 将 prompt 写入指定文件路径，而非输出到控制台；None 表示不写文件（直接输出到控制台）
# 示例：VSCODE_OUTPUT = "data_dir/myworld_dir/prompt_batch00.txt"

VSCODE_OVERWRITE = False
# 配合 VSCODE_OUTPUT 使用：若目标文件已存在是否允许覆盖

# =============================================================================


def get_args() -> argparse.Namespace:
    """获取运行参数：命令行模式解析 argv，VS Code 模式使用顶部配置变量。"""
    if len(sys.argv) > 1:
        return build_parser().parse_args()
    return argparse.Namespace(
        app=VSCODE_APP,
        batch=VSCODE_BATCH,
        stage=VSCODE_STAGE,
        clipboard=VSCODE_CLIPBOARD,
        output=Path(VSCODE_OUTPUT) if VSCODE_OUTPUT else None,
        overwrite=VSCODE_OVERWRITE,
    )


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。"""
    parser = argparse.ArgumentParser(description="组装四层记忆与批次数据，输出完整 prompt。")
    parser.add_argument("--app", required=True, help="应用名。")
    parser.add_argument("--batch", required=True, type=int, help="批次编号。")
    parser.add_argument("--stage", required=True, choices=["inductive", "deductive"], help="编码阶段。")
    parser.add_argument("--clipboard", action="store_true", help="复制到系统剪贴板。未安装 pyperclip 时降级为标准输出。")
    parser.add_argument("--output", type=Path, help="将 prompt 写入指定文件，而不是标准输出。")
    parser.add_argument("--overwrite", action="store_true", help="配合 --output 使用，允许覆盖目标文件。")
    return parser


def read_required_text(path: Path, suggestions: list[str]) -> str:
    """读取必需文本文件。"""
    ensure_file_exists(path, suggestions)
    return path.read_text(encoding="utf-8")

def build_prompt(layer1: str, layer2: str, layer3: str, layer4: str, batch_text: str, batch_id: int) -> str:
    """拼接完整 prompt。"""
    return (
        "=======================================\n"
        "【第1层:编码规则与方法论】\n"
        "=======================================\n"
        f"{layer1.strip()}\n\n"
        "=======================================\n"
        "【第2层:当前编码本(研究者已确认)】\n"
        "=======================================\n"
        f"{layer2.strip()}\n\n"
        "=======================================\n"
        "【第3层:编码决策历史】\n"
        "=======================================\n"
        f"{layer3.strip()}\n\n"
        "=======================================\n"
        "【第4层:本批聚焦指令】\n"
        "=======================================\n"
        f"{layer4.strip()}\n\n"
        "=======================================\n"
        f"【本批待编码数据:批次 {batch_id}】\n"
        "=======================================\n"
        f"{batch_text.strip()}\n\n"
        "=======================================\n"
        "【任务启动】\n"
        "=======================================\n"
        "请按照第1层\"工作流约定\"的步骤1,先输出【批次阅览报告】，\n"
        "不要直接输出编码。等待研究者确认方向后再进行编码。\n"
    )


def maybe_copy_to_clipboard(content: str) -> bool:
    """尝试复制到剪贴板。"""
    try:
        import pyperclip  # type: ignore
    except ImportError:
        return False

    pyperclip.copy(content)
    return True


def save_prompt_log(
    prompt: str,
    app: str,
    stage: str,
    batch_id: int,
    source_paths: list[Path],
) -> Path:
    """将 prompt 保存到 prompt_logs/ 目录下，供人工检查和微调。

    文件名格式：batch_{NN}_{stage}_prompt.txt
    每次运行均覆盖同名文件（日志目的是"最新版本"，不需要版本历史）。
    """
    logs_dir = get_prompt_logs_dir(app, stage)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"batch_{batch_id:02d}_{stage}_prompt.txt"
    log_path.write_text(prompt, encoding="utf-8")
    write_meta(
        log_path,
        {
            "app": app,
            "batch": batch_id,
            "stage": stage,
            "source_paths": source_paths,
            "output_type": "prompt_log",
        },
    )
    return log_path


def main() -> None:
    """脚本入口。"""
    args = get_args()

    knowledge_dir = get_knowledge_dir(args.app, args.stage)
    rules_path = knowledge_dir / "00_base_rules.txt"
    codebook_path = get_codebook_current_path(args.app, args.stage)
    rolling_rules_path = get_rolling_rules_path(args.app, args.stage)
    focus_path = knowledge_dir / "03_focus.txt"
    batch_path = get_preprocessed_batch_path(args.app, args.batch)

    layer1 = read_required_text(
        rules_path,
        [f"请先运行 `python scripts/00_setup_proj.py --app {args.app}` 初始化项目目录"],
    )
    layer2 = read_required_text(
        codebook_path,
        ["请确认 knowledge/02_codebook_current.md 是否存在"],
    )
    layer3 = read_required_text(
        rolling_rules_path,
        ["请确认 knowledge/01_rolling_rules.txt 是否存在"],
    )
    layer4 = read_required_text(focus_path, ["请确认 knowledge/03_focus.txt 是否存在"])
    batch_text = read_batch_file(args.app, args.batch)

    prompt = build_prompt(layer1, layer2, layer3, layer4, batch_text, args.batch)

    # ── 总是保存副本到 prompt_logs/（供人工检查和微调后再粘贴给 LLM） ──────────
    source_paths = [rules_path, codebook_path, rolling_rules_path, focus_path, batch_path]
    log_path = save_prompt_log(prompt, args.app, args.stage, args.batch, source_paths)
    print(f"[OK] Prompt 副本已保存：{log_path}")
    print(f"     在粘贴给 LLM 前，可在此文件中检查或微调内容。")

    # ── 额外输出方式（--output / --clipboard / 默认 stdout） ─────────────────
    if args.output:
        ensure_can_write(args.output, args.overwrite)
        ensure_parent_dir(args.output)
        args.output.write_text(prompt, encoding="utf-8")
        write_meta(
            args.output,
            {
                "app": args.app,
                "batch": args.batch,
                "stage": args.stage,
                "source_paths": source_paths,
                "output_type": "prompt",
            },
        )
        print(f"[OK] Prompt 同时写入指定文件：{args.output}")
        return

    copied = maybe_copy_to_clipboard(prompt) if args.clipboard else False
    if args.clipboard:
        if copied:
            print("[OK] Prompt 已复制到剪贴板，可直接粘贴。")
        else:
            print("[提示] 未安装 pyperclip，已降级为输出到标准输出。")
            print(prompt, end="")
    else:
        print(prompt, end="")


if __name__ == "__main__":
    main()
