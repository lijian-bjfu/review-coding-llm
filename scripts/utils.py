#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共享工具函数。

手动测试：
1. 运行 `python scripts/00_setup_proj.py --app example_app_test` 后，应创建完整目录结构与知识文件。
2. 在 `data_dir/example_app_test_dir/00_rawdata_dir/example_app_test.csv` 放入包含 `name/rating/review`
   的 UTF-8-SIG CSV 后，运行 `python scripts/01_sampling_data.py --app example_app_test --batch_size 2 --n_batches 1`
   应能成功读取数据并生成批次文件与 `.meta.json`。
"""

from __future__ import annotations

import csv
import hashlib
import inspect
import io
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

__version__ = "0.1.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data_dir"
review = PROJECT_ROOT / "prompts"

APP_NAME_PATTERN = re.compile(r"^[a-z0-9_\u4e00-\u9fff]+$")
REQUIRED_RAW_COLUMNS = ["name", "rating", "review"]
CODING_REQUIRED_COLUMNS = ["分类", "检索词"]
BATCH_FILE_PATTERN = re.compile(r"^batch_(\d{2})_coding\.csv$")
PUNCTUATION_TO_STRIP = " \t\r\n,，.。!！?？:：;；'\"“”‘’()（）[]【】{}<>《》、…-—"


def get_app_dir(app: str) -> Path:
    """返回 data_dir/<app>_dir 的绝对路径。"""
    validate_app_name(app)
    return DATA_DIR / f"{app}_dir"


def get_app_subdir(app: str, subdir: str) -> Path:
    """返回 app 项目下的某个子目录。"""
    return get_app_dir(app) / subdir


def load_rawdata(app: str) -> pd.DataFrame:
    """读取 00_rawdata_dir/<app>.csv，校验必需列 name/rating/review。"""
    rawdata_path = get_rawdata_path(app)
    ensure_file_exists(
        rawdata_path,
        [
            f"项目是否已初始化（运行 `python scripts/00_setup_proj.py --app {app}`）",
            f"CSV 文件是否已放入 `data_dir/{app}_dir/00_rawdata_dir/` 目录",
        ],
    )
    try:
        df = pd.read_csv(rawdata_path, encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"无法读取数据文件：{rawdata_path.relative_to(PROJECT_ROOT)}\n"
            "请确认该文件使用 UTF-8 编码保存。"
        ) from exc
    except Exception as exc:  # pragma: no cover - 宽泛兜底，提升命令行可诊断性
        raise ValueError(
            f"读取数据文件失败：{rawdata_path.relative_to(PROJECT_ROOT)}\n"
            f"原始错误：{exc}"
        ) from exc

    validate_columns(df, REQUIRED_RAW_COLUMNS)
    return df


def validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    """校验 DataFrame 包含必需列，缺失则抛出带建设性信息的 ValueError。"""
    missing = [column for column in required if column not in df.columns]
    if not missing:
        return

    existing = ", ".join(str(column) for column in df.columns) if len(df.columns) > 0 else "（空表）"
    required_text = ", ".join(required)
    missing_text = ", ".join(missing)
    raise ValueError(
        "数据列校验失败。\n"
        f"缺失列：{missing_text}\n"
        f"当前列：{existing}\n"
        f"请确认 CSV 至少包含以下列：{required_text}"
    )


def write_meta(output_path: Path, params: dict[str, Any]) -> None:
    """在 output_path 旁边写 .meta.json。"""
    output_path = output_path.resolve()
    meta_path = output_path.with_name(f"{output_path.name}.meta.json")
    meta = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "params": _make_json_safe(params),
        "source_hash": _compute_source_hash(params),
        "script_version": _resolve_script_version(),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_batch_file(app: str, batch_id: int) -> str:
    """读取批次 txt 文件的全部内容。"""
    batch_path = get_preprocessed_batch_path(app, batch_id)
    ensure_file_exists(
        batch_path,
        [
            f"请先运行 `python scripts/01_sampling_data.py --app {app} --batch_size <数量> --n_batches <批数>` 生成批次文件",
            f"确认批次编号是否正确（当前请求批次：{batch_id}）",
        ],
    )
    return batch_path.read_text(encoding="utf-8")


def list_completed_batches(app: str) -> list[int]:
    """扫描 batches/ 目录，返回已完成的批次编号列表。"""
    batches_dir = get_batches_dir(app, "inductive")
    if not batches_dir.exists():
        return []

    batch_ids: list[int] = []
    for path in batches_dir.iterdir():
        match = BATCH_FILE_PATTERN.match(path.name)
        if match:
            batch_ids.append(int(match.group(1)))
    return sorted(batch_ids)


def get_codebook_current_path(app: str, stage: str = "inductive") -> Path:
    """返回 02_codebook_current.md 的路径。"""
    return get_knowledge_dir(app, stage) / "02_codebook_current.md"


def get_rolling_rules_path(app: str, stage: str = "inductive") -> Path:
    """返回 01_rolling_rules.txt 的路径。"""
    return get_knowledge_dir(app, stage) / "01_rolling_rules.txt"


def get_prompt_log_path(app: str, stage: str = "inductive") -> Path:
    """返回 prompt_log.json 的路径。"""
    return get_knowledge_dir(app, stage) / "prompt_log.json"


def validate_app_name(app: str) -> None:
    """校验 app 名称是否符合约定。"""
    if APP_NAME_PATTERN.fullmatch(app):
        return
    raise ValueError(
        f"非法的应用名：{app}\n"
        "应用名只能包含英文小写字母、数字、下划线或汉字，例如：`myworld`、`一起来捉妖`。\n"
        "不支持空格、大写字母或其他特殊符号。"
    )


def ensure_file_exists(path: Path, suggestions: list[str] | None = None) -> None:
    """检查文件是否存在。"""
    if path.is_file():
        return

    message_lines = [f"未找到文件：{path.relative_to(PROJECT_ROOT)}"]
    if suggestions:
        message_lines.append("请确认：")
        message_lines.extend([f"{index}. {item}" for index, item in enumerate(suggestions, start=1)])
    raise FileNotFoundError("\n".join(message_lines))


def ensure_parent_dir(path: Path) -> None:
    """确保输出文件父目录存在。"""
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_can_write(path: Path, overwrite: bool) -> None:
    """检查输出文件是否允许写入。"""
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"输出文件已存在：{path.relative_to(PROJECT_ROOT)}\n"
            "如需覆盖，请追加 `--overwrite` 参数。"
        )


def get_rawdata_path(app: str) -> Path:
    """返回原始数据 CSV 路径。"""
    return get_app_subdir(app, "00_rawdata_dir") / f"{app}.csv"


def get_sampling_log_path(app: str) -> Path:
    """返回抽样日志 CSV 路径（保存于 rawdata 目录，记录历次已抽取的条目）。"""
    return get_app_subdir(app, "00_rawdata_dir") / f"{app}_sampled_log.csv"


def get_preprocessed_batch_path(app: str, batch_id: int) -> Path:
    """返回预处理批次 txt 路径。"""
    return get_app_subdir(app, "01_preprocessed_for_llm_dir") / f"{app}_batch_{batch_id:02d}.txt"


def get_unused_path(app: str) -> Path:
    """返回未使用数据输出路径。"""
    return get_app_subdir(app, "01_preprocessed_for_llm_dir") / f"{app}_unused.txt"


def get_knowledge_dir(app: str, stage: str = "inductive") -> Path:
    """返回指定阶段的 knowledge 目录。"""
    stage_dir = resolve_stage_dirname(stage)
    return get_app_subdir(app, stage_dir) / "knowledge"


def get_batches_dir(app: str, stage: str = "inductive") -> Path:
    """返回指定阶段的 batches 目录。"""
    stage_dir = resolve_stage_dirname(stage)
    return get_app_subdir(app, stage_dir) / "batches"


def get_prompt_logs_dir(app: str, stage: str = "inductive") -> Path:
    """返回指定阶段的 prompt_logs 目录（存放每次生成的 prompt 副本，供人工检查和微调）。"""
    stage_dir = resolve_stage_dirname(stage)
    return get_app_subdir(app, stage_dir) / "prompt_logs"


def resolve_stage_dirname(stage: str) -> str:
    """将阶段名映射为目录名。"""
    mapping = {
        "inductive": "02_inductive_coding_dir",
        "deductive": "03_deductive_coding_dir",
    }
    if stage not in mapping:
        raise ValueError(f"不支持的阶段：{stage}")
    return mapping[stage]


def strip_outer_punctuation(text: str) -> str:
    """去掉引文首尾标点，保留内部文本。"""
    return text.strip(PUNCTUATION_TO_STRIP)


def _find_coding_header_index(lines: list[str]) -> int:
    """找到编码 CSV 表头所在行。"""
    for index, line in enumerate(lines):
        normalized = line.lstrip("\ufeff").strip()
        if normalized == "分类,检索词":
            return index
    raise ValueError(
        "未找到标准表头 `分类,检索词`。\n"
        "请确认 CSV 首行或后续某一行包含标准表头，不要修改列名。"
    )


def parse_coding_csv(path: Path) -> pd.DataFrame:
    """宽容解析批次编码 CSV，返回包含 `分类`、`检索词` 两列的 DataFrame。"""
    ensure_file_exists(path, ["请确认该批次编码 CSV 已保存到 batches/ 目录"])
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    header_index = _find_coding_header_index(lines)

    valid_rows: list[list[str]] = []
    malformed_rows: list[str] = []
    reader = csv.reader(io.StringIO("\n".join(lines[header_index:])))
    header = next(reader, None)
    if header is None:
        raise ValueError(f"文件为空：{path}")

    for row_number, row in enumerate(reader, start=header_index + 2):
        if not row or all(not item.strip() for item in row):
            continue
        if len(row) != 2:
            malformed_rows.append(f"第 {row_number} 行列数不正确：{row}")
            continue
        valid_rows.append([row[0].strip(), strip_outer_punctuation(row[1].strip())])

    if malformed_rows:
        for warning in malformed_rows:
            print_warning(f"{path.name} - {warning}；已跳过该行。")

    df = pd.DataFrame(valid_rows, columns=CODING_REQUIRED_COLUMNS)
    validate_columns(df, CODING_REQUIRED_COLUMNS)
    df = df[(df["分类"] != "") & (df["检索词"] != "")]
    return df


def is_placeholder_content(text: str) -> bool:
    """判断知识文件是否仍处于模板占位状态。"""
    normalized = text.strip()
    if not normalized:
        return True

    placeholders = [
        "（初始为空，首批编码后填入）",
        "（初始为空，首批完成后根据需要追加）",
        "版本**：v0.0（初始状态，未开始编码）",
        "已处理批次**：无",
    ]
    return any(marker in normalized for marker in placeholders)


def count_batch_entries(batch_text: str) -> int:
    """统计批次 txt 中的评论条数。"""
    return len(re.findall(r"(?m)^\[ID:", batch_text))


def print_warning(message: str) -> None:
    """打印警告。"""
    print(f"[警告] {message}")


def _make_json_safe(value: Any) -> Any:
    """将 Path 等对象转换为可 JSON 序列化的数据。"""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_make_json_safe(item) for item in value]
    return value


def _compute_source_hash(params: dict[str, Any]) -> str:
    """根据 source_path/source_paths 计算源数据哈希。"""
    source_values: list[str] = []
    if "source_path" in params:
        source_values.append(str(params["source_path"]))
    if "source_paths" in params:
        source_values.extend(str(item) for item in params["source_paths"])

    if not source_values:
        return ""

    hasher = hashlib.sha256()
    for raw_path in sorted(source_values):
        path = Path(raw_path)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        if not path.exists():
            continue

        hasher.update(str(path.relative_to(PROJECT_ROOT)).encode("utf-8"))
        if path.is_file():
            hasher.update(path.read_bytes())
        else:
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                hasher.update(str(child.relative_to(PROJECT_ROOT)).encode("utf-8"))
                hasher.update(child.read_bytes())
    return hasher.hexdigest()


def _resolve_script_version() -> str:
    """优先记录 git commit，失败时回退到调用脚本版本。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        if commit:
            return commit
    except Exception:
        pass

    caller_globals = inspect.currentframe().f_back.f_globals if inspect.currentframe() else {}
    return str(caller_globals.get("__version__", __version__))
