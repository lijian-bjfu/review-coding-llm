# AGENTS.md — Codex 开发守则 (v0.2)

> 这份文档是给 **Codex（OpenAI的编码agent）** 读的项目级常驻指令。
> 每次开始开发会话时，Codex会自动读取本文件，将其作为所有脚本开发的基本规范。

## 项目使命

本项目是一个**LLM辅助的质性编码工作流工具**（MVP阶段）。核心价值是
**让研究者在不调用API的前提下**，用脚本辅助数据预处理和结果整合，
用LLM对话窗口完成实际编码。

完整的工作流、数据结构、文件约定参见 `README.md`。开始写任何脚本前，
**必须先通读 README.md**。

## 核心设计原则（v0.2）

### 1. 脚本只做工程，不做"和LLM交流"

所有与LLM交流相关的逻辑（prompt内容、编码纪律、模式切换）都在
`prompts/` 目录下的文件中。脚本**不得**在代码里嵌入prompt文本、
也不得根据参数改变prompt的生成逻辑。

**好的设计**：脚本按固定规则读取prompt文件→拼接→输出
**坏的设计**：脚本根据 `--mode focus` 参数动态组装不同的prompt内容

这意味着研究者日后调整编码规则时，**只改 `prompts/` 下的文件，不改代码**。

### 2. 固定流程，不做过度参数化

脚本的命令行参数应限于**数据和目录相关的参数**（app名、batch编号、
overwrite等），不接受"模式"、"策略"、"阶段切换"类的逻辑参数。

例外：`--stage inductive|deductive` 是允许的，因为这只是选择从
`prompts/inductive/` 还是 `prompts/deductive/` 读取文件，属于
"读哪个文件"的工程决策，不是"用什么策略"的业务决策。

### 3. MVP优先

- **能跑起来 > 完美**
- 不引入不必要的抽象
- 不引入不必要的依赖
- 优先 Python 标准库 + pandas + openpyxl

## 开发原则

### 确定性与幂等性

- 相同输入+相同参数 → 相同输出
- 抽样相关脚本必须接受 `--seed` 参数，默认 `--seed 42`
- 输出文件写入前检查是否存在，如存在需要 `--overwrite` 强制覆盖

### 可追溯性

每个产出文件在生成时，写入同名 `.meta.json` 文件，记录：
- 生成时间
- 使用的参数
- 源数据的hash（如适用）
- 脚本名称

### 错误处理

- 使用 `argparse` 处理命令行参数，提供 `-h/--help`
- 对用户输入做严格校验，失败时给出**建设性错误消息**

错误消息示例：

```
[Bad]  FileNotFoundError: myworld.csv
[Good] 未找到数据文件：data_dir/myworld_dir/00_rawdata_dir/myworld.csv
       请确认：
       1. 项目是否已初始化（运行 00_setup_proj.py --app myworld）
       2. CSV文件是否已放入 00_rawdata_dir/ 目录
```

- 对LLM输出的解析采用**宽容但可诊断**的策略：
  - 能解析就解析，记录警告
  - 解析失败时输出明确的"这一行不符合预期格式"+建议修复方法
  - 永远不要默默吞掉错误

### 中文友好

所有CSV读写使用 `encoding='utf-8-sig'`（带BOM，Windows用Excel打开不乱码）。
所有日志/错误消息用中文。

## 技术栈约定

| 项目 | 选择 | 说明 |
|------|------|------|
| Python版本 | 3.10+ | 使用 `match` 语句和新式类型注解 |
| 数据处理 | pandas | 统一接口，避免纯 csv 模块 |
| Excel | openpyxl | 不使用 xlrd/xlwt |
| JSON | 标准库 json | 写入时 `ensure_ascii=False, indent=2` |
| 命令行 | argparse | 不使用 click/typer |
| 剪贴板（可选） | pyperclip | 仅 `02_create_prompts.py` 的 `--clipboard` 使用；未安装时降级为stdout |
| 类型注解 | 使用 | 函数签名必须有类型注解 |

## 项目路径约定

所有脚本都假设**从项目根目录执行**（即 `review-coding-llm/`）。

路径处理统一使用 `pathlib.Path`：

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data_dir"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

def get_app_dir(app: str) -> Path:
    return DATA_DIR / f"{app}_dir"
```

不要使用 `os.path.join` 或字符串拼接路径。

## VSCode / IDE 运行模式

除命令行外，每个脚本也应支持在 VSCode 等 IDE 中直接运行（无参数
运行 `python scripts/XX_xx.py`）。实现方式：

- 在脚本顶部定义 `VSCODE_*` 配置变量（默认值可为 None 或空）
- 在 `__main__` 入口先尝试用 argparse 解析命令行参数
- 若 argparse 未获得任何参数（即直接从 IDE 运行），则从 VSCODE_* 
  变量读取参数
- 如果二者都没有，给出友好的错误提示

参数映射：

| 脚本 | VSCode变量 |
|------|-----------|
| 00_setup_proj.py | VSCODE_APP, VSCODE_OVERWRITE |
| 01_sampling_data.py | VSCODE_APP, VSCODE_BATCH_SIZE, VSCODE_N_BATCHES, VSCODE_SEED, VSCODE_MIN_LEN, VSCODE_STRATIFY, VSCODE_OVERWRITE |
| 02_create_prompts.py | VSCODE_APP, VSCODE_BATCH, VSCODE_STAGE, VSCODE_CLIPBOARD, VSCODE_OUTPUT, VSCODE_OVERWRITE |
| 03_merge_codings.py | VSCODE_APP, VSCODE_OVERWRITE |
| 04_build_dictionary.py | VSCODE_APP, VSCODE_OVERWRITE |
| 05_saturation_check.py | VSCODE_APP |

原则：命令行参数优先于 VSCode 变量。两种运行方式产出完全一致的结果。

## 脚本规范

### `scripts/utils.py`

共享工具函数。其他脚本通过 `from utils import ...` 导入。

**必须导出的函数**：

```python
from pathlib import Path
from typing import Any
import pandas as pd

def get_app_dir(app: str) -> Path:
    """返回 data_dir/<app>_dir 的绝对路径"""

def get_app_subdir(app: str, subdir: str) -> Path:
    """返回app项目下的某个子目录，subdir如'00_rawdata_dir'"""

def load_rawdata(app: str) -> pd.DataFrame:
    """读取 00_rawdata_dir/<app>.csv，校验必需列 user_id/rating/comment"""

def validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    """校验DataFrame包含必需列，缺失则抛出带建设性信息的ValueError"""

def write_meta(output_path: Path, params: dict[str, Any]) -> None:
    """在 output_path 旁边写 .meta.json"""

def read_batch_file(app: str, batch_id: int) -> str:
    """读取批次txt文件的全部内容"""

def list_completed_batches(app: str) -> list[int]:
    """扫描 batches/ 目录，返回已完成的批次编号列表（有 batch_NN_coding.csv 的）"""

def get_knowledge_dir(app: str, stage: str) -> Path:
    """返回 knowledge/ 目录路径，stage为 'inductive' 或 'deductive'"""
```

### `scripts/00_setup_proj.py`

**功能**：初始化一个app的项目目录结构。

**命令行**：

```bash
python scripts/00_setup_proj.py --app <APP_NAME> [--overwrite]
```

**行为**：
1. 校验 `app` 参数符合命名规范（英文小写+下划线）
2. 创建 `data_dir/<app>_dir/` 及其全部子目录
3. 从 `prompts/inductive/` 复制以下文件到
   `02_inductive_coding_dir/knowledge/`：
   - `00_base_rules.txt` → `00_base_rules.txt`
   - `01_rolling_rules_template.txt` → `01_rolling_rules.txt`
   - `02_codebook_current_template.md` → `02_codebook_current.md`
   - `03_focus_template.txt` → `03_focus.txt`
4. 创建空的 `prompt_log.json`（内容为 `{"batches": []}`）
5. 打印成功消息+下一步指引

**输出示例**：

```
[OK] 项目已初始化：data_dir/myworld_dir/
下一步：
  1. 将清洗后的数据放到 data_dir/myworld_dir/00_rawdata_dir/myworld.csv
  2. 编辑聚焦主题文件：
     data_dir/myworld_dir/02_inductive_coding_dir/knowledge/03_focus.txt
  3. 运行：python scripts/01_sampling_data.py --app myworld --batch_size 100
```

### `scripts/01_sampling_data.py`

**功能**：从原始数据随机抽样，切分为多个不重叠批次。

**命令行**：

```bash
python scripts/01_sampling_data.py --app <APP_NAME> \
    --batch_size 100 --n_batches 5 [--seed 42] [--overwrite]
```

**行为**：
1. 读取原始数据，校验总量 >= `batch_size * n_batches`
2. 用 `seed` 做随机抽样（不放回），取出 `batch_size * n_batches` 条
3. 切分为N批，每批输出到 `01_preprocessed_for_llm_dir/<app>_batch_NN.txt`
4. 每批次txt格式：每条评论独占一段，段之间空一行

**批次txt格式**：

```
[ID:U001] [rating:4] 这个游戏的操作真的好难啊，小朋友根本玩不转...

[ID:U002] [rating:2] 界面设计不够直观，找功能要翻半天...

[ID:U003] [rating:5] 孩子玩得很开心，美术风格很治愈...
```

**边界处理**：
- 评论中的换行符：替换为空格（保留语义但合并为单行）
- 评论中的 `[` 或 `]`：保留原样
- 未使用的数据：输出到 `<app>_unused.txt`
- **评论保留原始中文文本，不做分词**

### `scripts/02_create_prompts.py`

**功能**：将四层文件（base rules + codebook current + rolling rules
+ focus + 批次数据）拼接成完整prompt。

**命令行**：

```bash
python scripts/02_create_prompts.py --app <APP_NAME> --batch <N> \
    --stage <inductive|deductive> [--clipboard] [--output <file>]
```

**行为**（固定逻辑，无模式分支）：

1. 根据 `stage` 定位 knowledge 目录
2. 依次读取5个文件：
   - `knowledge/00_base_rules.txt`（第1层）
   - `knowledge/02_codebook_current.md`（第2层）
   - `knowledge/01_rolling_rules.txt`（第3层）
   - `knowledge/03_focus.txt`（第4层，聚焦指令）
   - `01_preprocessed_for_llm_dir/<app>_batch_NN.txt`（批次数据）
3. 按固定模板拼接
4. 输出到stdout/剪贴板/文件，并在 `prompt_logs/` 目录保存一份副本，
   文件名为 `batch_<NN>_<stage>_prompt.txt`（如 `batch_00_inductive_prompt.txt`）

**拼接模板**（写死在脚本里，不要参数化）：

```
=======================================
【第1层:编码规则与方法论】
=======================================
{第1层内容}

=======================================
【第2层:当前编码本(研究者已确认)】
=======================================
{第2层内容}

=======================================
【第3层:编码决策历史】
=======================================
{第3层内容}

=======================================
【第4层:本批聚焦指令】
=======================================
{第4层内容}

=======================================
【本批待编码数据:批次 {N}】
=======================================
{批次数据内容}

=======================================
【任务启动】
=======================================
请按照第1层"工作流约定"的步骤1,先输出【批次阅览报告】,
不要直接输出编码。等待研究者确认方向后再进行编码。
```

### `scripts/03_merge_codings.py`

**功能**：合并所有批次的编码CSV，输出去重后的统一结果。

**命令行**：

```bash
python scripts/03_merge_codings.py --app <APP_NAME> [--overwrite]
```

**行为**：
1. 扫描 `batches/` 下所有 `batch_NN_<主题名>.csv`（如 `batch_00_户外玩法影响.csv`）
2. 按文件名中的主题名分组
3. 每组内：读取并校验包含 `分类`, `检索词` 两列
4. 每组内：合并为单一DataFrame
5. 按 (`分类`, `检索词`) 完全一致的行去重
6. 按 `分类` 分组排序
7. 每个主题输出一个 `codebook_merged_<主题名>.csv`
8. 打印统计（按主题分别显示编码数和引文数）

**批次文件命名规范**：
- 格式：`batch_<NN>_<主题名>.csv`
- 批次编号 2 位零填充
- 主题名与 LLM 输出的 `--- 主题：[主题名] ---` 分隔行中的主题名一致
- 研究者从 LLM 输出中手动按分隔行切分保存为多个文件

**宽容解析**：
- 若第一行不是标准表头（LLM多加了前缀），尝试跳过非数据行
- 若某行列数不对，跳过并警告
- 若引文以标点开头/结尾，自动strip

### `scripts/04_build_dictionary.py`

**功能**：从 `codebook_merged.csv` 生成MAXQDA字典Excel。

**命令行**：

```bash
python scripts/04_build_dictionary.py --app <APP_NAME> [--overwrite]
```

**行为**：
1. 扫描 `codebook_merged_<主题名>.csv` 文件（可能有多个）
2. 每个主题生成一个 `codebook_final_<主题名>.xlsx`：
   - 表头：`分类`, `检索词`
   - 两列，无索引列
3. 打印 MAXQDA 导入指引：
   - 各主题字典文件的路径
   - 导入方式：MAXQDA 菜单 → 词典 → 导入 → 选择 .xlsx
   - 提示：每个主题作为一本独立字典导入

### `scripts/05_saturation_check.py`

**功能**：检查归纳编码的饱和度。

**命令行**：

```bash
python scripts/05_saturation_check.py --app <APP_NAME>
```

**行为**：
1. 扫描 `batches/` 下所有 `batch_NN_<主题名>.csv`，按批次编号排序
2. 合并同一批次下所有主题的编码（饱和度看的是全局编码池，不分主题）
3. 逐批计算：
   - 本批唯一编码数（跨所有主题）
   - 本批新增编码数（与之前批次的差集）
   - 最近3批的新增编码数滚动均值
4. 输出表格+状态提示

## 测试

MVP阶段不要求写单元测试，但每个脚本必须提供**手动测试方法**：

- 在脚本顶部的 docstring 里写明："手动测试：运行 `python scripts/XX_xx.py --app example_app` 后应该..."

## 交付标准

每个脚本完成后，Codex 需自检：

- [ ] 能通过 `python scripts/XX_xx.py --help` 显示帮助
- [ ] 有清晰的 docstring
- [ ] 所有公开函数有类型注解
- [ ] 错误消息用中文、具建设性
- [ ] 输出文件旁边有 `.meta.json`
- [ ] 从项目根目录运行，路径不会出错

## 不要做的事

- ❌ 不要调用任何LLM API
- ❌ 不要引入新依赖
- ❌ 不要写"尽责任但用户可能不需要"的功能
- ❌ 不要写Web界面/GUI
- ❌ 不要预设prompt内容——prompt模板由研究者维护在 `prompts/` 目录
- ❌ 不要修改 `prompts/` 目录下的任何文件
- ❌ 不要在代码里根据参数改变prompt的生成逻辑（分支应该写到prompt文件里）

## 遇到不确定的情况

1. 参考 `README.md` 中的流程描述
2. 选择"让研究者最容易恢复"的方案
3. 把决策写入 `.meta.json` 供审计

---

**版本**：v0.2 (MVP)

## v0.2 相对 v0.1 的变化

- 确定了**聚焦模式为唯一模式**（无全景模式）
- 新增 **第4层"聚焦指令"** (`03_focus.txt`)，由研究者每批更新
- 编码工艺写入 base rules（Step A→B→C→D）
- 去除了"模式切换"、"编码策略"等条件参数
- `02_create_prompts.py` 简化为固定的5文件拼接
