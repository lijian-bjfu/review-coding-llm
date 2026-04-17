# LLM 辅助质性编码工具 (MVP v0.2)

一个结合大语言模型（LLM）对话窗口进行用户评论质性编码的轻量级工作流工具。

## 工具定位

这是一个**半自动的质性编码辅助工具**：

- **不调用LLM API**：使用者在 Claude.ai / ChatGPT / DeepSeek 等产品的对话窗口完成编码
- **Python脚本负责**：数据预处理、批次管理、prompt组装、结果整合
- **LLM对话窗口负责**：实际的归纳/演绎编码与对话纠偏
- **研究者全程在回路中**：每批结果经研究者审阅确认后才进入下一批
- **聚焦编码模式**：每批数据围绕研究者指定的聚焦主题进行编码

## 工作流概览

```
┌─────────────────────────────────────────────────────────────┐
│  数据准备      │  归纳编码（循环）  │  演绎编码  │  字典导出  │
├─────────────────────────────────────────────────────────────┤
│  清洗+抽样     │  组装prompt        │  应用编码本│  合并结果  │
│  切分批次      │  →LLM对话          │  到新数据  │  生成xlsx  │
│  定义聚焦主题  │  →研究者审阅       │            │            │
│                │  →更新编码本       │            │            │
└─────────────────────────────────────────────────────────────┘
```

三类角色协作：

| 标记 | 执行者 | 任务 |
|------|--------|------|
| -h   | 研究者（human） | 决策、审阅、确认、纠偏 |
| -a   | LLM（AI） | 批量阅览、编码生成、格式化输出 |
| -s   | Python脚本 | 数据处理、批次切分、prompt组装、结果合并 |

## 项目结构

```
llm_coding_mvp/
├── README.md                       ← 主文档（使用指南）
├── AGENTS.md                       ← Codex开发守则
├── docs/
│   └── prompt_engineering.md       ← prompt工程的详细约定
├── scripts/                        ← 开发阶段由Codex生成
│   ├── utils.py
│   ├── 00_setup_proj.py
│   ├── 01_sampling_data.py
│   ├── 02_create_prompts.py
│   ├── 03_merge_codings.py
│   ├── 04_build_dictionary.py
│   └── 05_saturation_check.py
├── prompts/
│   ├── inductive/
│   │   ├── 00_base_rules.txt              ← 第1层：方法论常量
│   │   ├── 01_rolling_rules_template.txt  ← 第3层：决策历史模板
│   │   ├── 02_codebook_current_template.md ← 第2层：当前编码本模板
│   │   └── 03_focus_template.txt          ← 第4层：聚焦指令模板
│   └── deductive/
│       └── 00_base_rules.txt
└── data_dir/
    └── <APP_NAME>_dir/
        ├── 00_rawdata_dir/
        │   ├── <APP_NAME>.csv
        │   └── <APP_NAME>_sampled_log.csv
        ├── 01_preprocessed_for_llm_dir/
        │   ├── <APP_NAME>_batch_00.txt
        │   ├── <APP_NAME>_unused.txt
        │   └── ...
        ├── 02_inductive_coding_dir/
        │   ├── knowledge/
        │   │   ├── 00_base_rules.txt
        │   │   ├── 01_rolling_rules.txt
        │   │   ├── 02_codebook_current.md
        │   │   ├── 03_focus.txt         ← 每批更新
        │   │   └── prompt_log.json
        │   ├── batches/
        │   │   ├── batch_00_preview.md
        │   │   ├── batch_00_coding.csv
        │   │   └── ...
        │   ├── prompt_logs/
        │   │   ├── batch_00_inductive_prompt.txt
        │   │   └── ...
        │   └── codebook_final.xlsx
        └── 03_deductive_coding_dir/
            ├── knowledge/
            │   └── 00_base_rules.txt
            ├── batches/
            └── prompt_logs/
```

### 四层记忆架构

保证多批次编码一致性的核心设计。每次给LLM的完整prompt由四层拼接：

```
┌─────────────────────────────────────────────┐
│ 第1层：方法论常量（永不变）                  │
│   00_base_rules.txt                         │
│   - 任务定义、输出格式、编码工艺             │
├─────────────────────────────────────────────┤
│ 第2层：当前编码本快照（每批后更新）          │
│   02_codebook_current.md                    │
│   - 已确认的编码名+定义+纳入/排除标准+样例   │
├─────────────────────────────────────────────┤
│ 第3层：决策历史摘要（每批后追加，不删）      │
│   01_rolling_rules.txt                      │
│   - 关键变更记录（合并/拆分/重命名+原因）    │
├─────────────────────────────────────────────┤
│ 第4层：本批聚焦指令（每批研究者更新）        │
│   03_focus.txt                              │
│   - 本批聚焦主题、范围边界、预期规模         │
└─────────────────────────────────────────────┘

完整prompt = 第1层 + 第2层 + 第3层 + 第4层 + 本批数据
```

**四层的更新节奏**：

| 层 | 文件 | 更新频率 | 更新者 |
|----|------|---------|--------|
| 第1层 | `00_base_rules.txt` | 极少改 | 研究者（仅调整方法论时） |
| 第2层 | `02_codebook_current.md` | 每批后 | 研究者（基于LLM产出审阅） |
| 第3层 | `01_rolling_rules.txt` | 仅重大决策 | 研究者（做了合并/拆分等决策时） |
| 第4层 | `03_focus.txt` | 每批前 | 研究者（即使内容不变也要确认） |

## 快速开始

### 环境要求

- Python 3.10+
- pandas, openpyxl（`pip install -r requirements.txt`）
- 一个可用的LLM对话窗口（Claude.ai / ChatGPT / DeepSeek 等）

### 走一遍完整流程

```bash
# 1. 初始化项目
python scripts/00_setup_proj.py --app myworld

# 2. 数据放到 data_dir/myworld_dir/00_rawdata_dir/myworld.csv
#    必需列：name, rating, review（原始中文文本，不分词）

# 3. 编辑聚焦主题文件
#    data_dir/myworld_dir/02_inductive_coding_dir/knowledge/03_focus.txt

# 4. 抽样切分批次
python scripts/01_sampling_data.py --app myworld --batch_size 100 --n_batches 5

# 5. 为第0批组装prompt
python scripts/02_create_prompts.py --app myworld --batch 0 --stage inductive

# 6. 粘贴到LLM对话窗口，执行归纳编码循环

# 7. 第0批完成后处理第1批
#    （回第3步更新focus，再从第5步开始）

# 8. 所有批次完成后
python scripts/05_saturation_check.py --app myworld  # 检查饱和度
python scripts/03_merge_codings.py --app myworld      # 合并批次
python scripts/04_build_dictionary.py --app myworld   # 导出MAXQDA字典
```

除了在命令行执行外，也可通过vscode运行。每个脚本提供相应的配置变量，各脚本配置变量如下：

- 00_setup_proj.py	VSCODE_APP, VSCODE_OVERWRITE。写入项目名，建立data文件夹
- 01_sampling_data.py	VSCODE_APP, VSCODE_BATCH_SIZE, VSCODE_N_BATCHES, VSCODE_SEED, VSCODE_MIN_LEN, VSCODE_STRATIFY, VSCODE_OVERWRITE。抽样数据，允许分层抽样、过滤数据，有抽样日志避免重复抽样。
- 02_create_prompts.py	VSCODE_APP, VSCODE_BATCH, VSCODE_STAGE, VSCODE_CLIPBOARD, VSCODE_OUTPUT, VSCODE_OVERWRITE。打印出提示词，并在 `prompt_logs/` 里保留一份副本，用于手工微调。
- 03_merge_codings.py	VSCODE_APP, VSCODE_OVERWRITE
- 04_build_dictionary.py	VSCODE_APP, VSCODE_OVERWRITE
- 05_saturation_check.py	VSCODE_APP

---

## 工作流详解

### 阶段一：数据准备

#### 步骤1.1 数据清洗 -h

**输入**：原始数据（任意格式）
**输出**：`00_rawdata_dir/<APP_NAME>.csv`
**要求**：至少包含三列

| 列名 | 类型 | 说明 |
|------|------|------|
| name | str | 评论用户ID或用户名（任意唯一标识） |
| rating | int/float | 产品评分 |
| review | str | 评论正文（**原始中文**，不做分词） |

**重要提醒**：
- 如果数据源做过分词处理（带空格的中文），**最好还原为原始文本**
  再进入本工具。分词文本会显著降低LLM编码质量，且无法与MAXQDA字典匹配。
- 可选列（如有会一同保留）：`timestamp`, `platform`, `version` 等。

#### 步骤1.2 初始化项目目录 -s

```bash
python scripts/00_setup_proj.py --app <APP_NAME>
```

脚本会：
- 在 `data_dir/` 下创建 `<APP_NAME>_dir/` 及所有子目录
- 从 `prompts/inductive/` 复制四层文件模板到 `02_inductive_coding_dir/knowledge/`

#### 步骤1.3 编辑聚焦主题文件 -h

打开 `data_dir/<APP_NAME>_dir/02_inductive_coding_dir/knowledge/03_focus.txt`，
填写本次研究的聚焦主题、范围说明、预期规模。

**这一步至关重要**。模板里有详细注释，按提示填写即可。

示例（以"一起来捉妖"为例）：

```
## 本次研究聚焦主题

围绕"一起来捉妖"的户外玩法机制，识别玩家对户外玩法的各方面
体验，以及围绕户外玩法衍生出的相关话题（作弊、治理、地域、
投入成本）。

## 编码组织框架

1. 空间结构：户外玩法的空间设计
2. 机制漏洞：户外玩法中的作弊与破坏
3. 投入成本：户外玩法对现实资源的要求
4. 公平感受：户外玩法中的相对公平性体验
5. 治理效能：围绕户外玩法的举报/封号/申诉机制

## 范围说明

明确纳入：
- 即使表面是"时间"、"距离"问题，本质属于户外玩法投入的也要编码

明确排除：
- 纯登录bug、闪退等技术问题
- 与户外玩法无关的子玩法（配猫、合成）

## 预期产出规模
- 编码数：12-18 个
- 范围外比例：10-20%
```

#### 步骤1.4 抽样+切分批次 -s

```bash
python scripts/01_sampling_data.py --app <APP_NAME> --batch_size 100 --n_batches 5
```

**行为**：
- 从 `00_rawdata_dir/<APP_NAME>.csv` 读取全部数据
- 如设置 `--min_len`，先过滤过短评论
- 自动读取 `00_rawdata_dir/<APP_NAME>_sampled_log.csv`，续接历史抽样并排除已抽取记录
- 默认不重叠随机抽样；如设置 `--stratify`，则按 rating 自然比例分层抽样
- 当可用数据不足时，尽量抽取可用数据并明确提示
- 切分为N批
- 每批输出为 `01_preprocessed_for_llm_dir/<APP_NAME>_batch_NN.txt`
- 同时输出 `01_preprocessed_for_llm_dir/<APP_NAME>_unused.txt`
- 更新 `00_rawdata_dir/<APP_NAME>_sampled_log.csv`

**批次txt格式**：

```
[ID:U001] [rating:4] 这个游戏的操作真的好难啊，小朋友根本玩不转...

[ID:U002] [rating:2] 界面设计不够直观，找功能要翻半天...
```

#### 步骤1.5 Pilot 验证 -h+a（强烈推荐）

取 `batch_00.txt` 的前10-15条（或另抽一批小数据），走一遍完整编码流程。目的：

1. 验证 `03_focus.txt` 的聚焦主题描述是否清晰
2. 验证 LLM 能否按工艺执行
3. 沉淀为 **gold set**：未来批次编码完成后，可让LLM重编gold set，
   比对是否稳定

Pilot 过程发现的问题，回写到 `03_focus.txt` 或 `00_base_rules.txt`，
然后从batch_00正式开始。

---

### 阶段二：归纳编码（每批循环）

每批数据重复以下循环。**核心原则：没有研究者审阅通过，不进入下一批。**

#### 步骤2.0 更新聚焦指令 -h

每批开始前，打开 `03_focus.txt` 确认本批聚焦主题。即使与上批相同，
**也要打开确认一次**——这个确认本身是对自己研究方向的提醒。

#### 步骤2.1 组装prompt -s

```bash
python scripts/02_create_prompts.py --app <APP_NAME> --batch <N> --stage inductive
```

**行为**：读取四层文件 + 本批数据，拼成完整prompt，输出到控制台/剪贴板。

可选参数：
- `--clipboard`：直接复制到剪贴板（需安装pyperclip）
- `--output <file>`：写到文件

脚本还会在 `02_inductive_coding_dir/prompt_logs/` 或 `03_deductive_coding_dir/prompt_logs/`
中保留一份同名 prompt 副本，便于手工检查和微调。

#### 步骤2.2 LLM 初步阅览 -a

粘贴prompt到LLM窗口后，LLM会按约定输出**批次阅览报告**：

```markdown
## 批次概览
- 数据量：100条
- 聚焦主题：(重复研究者的指定)
- 估算范围内评论：约85条
- 估算范围外评论：约15条

## 我识别到的潜在编码方向（初步假设）
1. [方向1]：证据例子
2. ...

## 与当前编码本的初步匹配
- 可匹配已有编码的内容比例：约X%
- 可能需要新增的编码方向：...

## 需要您确认的方向性问题
- 问题1：...
- 问题2：...

## 可能的编码偏差风险
- 风险点1：...
```

#### 步骤2.3 研究者确认方向 -h

回答LLM提出的问题，明确本批编码的聚焦点。

**回写规范**：
- 将LLM的阅览报告复制保存为 `batches/batch_NN_preview.md`
- 将研究者的回复追加到文件末尾，用 `### 研究者回应` 分隔

#### 步骤2.4 LLM 进行归纳编码 -a

研究者在对话中输入指令（示例）：

> "请基于上面的讨论，对全部100条数据进行归纳编码。
> 严格按照编码工艺的 A→B→C→D 四步执行。
> 先给我编码摘要（带主题组织框架+编码明细），不要给完整CSV。"

LLM返回**编码摘要**（主题框架+编码明细+范围外统计+边界情况+未决项）。

#### 步骤2.5 研究者审阅编码 -h

按以下维度检查编码摘要：

- [ ] **主题vs编码层级是否清晰**：主题是容器，编码是内容？
- [ ] **覆盖度**：是否有重要评论未被编码？
- [ ] **粒度**：编码是否过于宽泛或过于细碎？
- [ ] **标签清晰度**：编码标签是否自解释？有无歧义？
- [ ] **命名规范**：是否为抽象概念而非原文词组堆积？
- [ ] **与现有编码本冲突**：是否有新编码实质上等同于已有编码？（首批无此项）
- [ ] **范围外合理**：范围外评论真的无关聚焦主题吗？
- [ ] **未决项处理**：LLM提出的未决项是否有明确裁定？

有问题就在对话中纠偏。**纠偏原则**：
- 一次一个修改点
- 修改理由写清楚（为写入 `prompt_log.json` 做准备）

#### 步骤2.6 LLM 生成完整结果 -a

研究者审阅通过后：

> "请生成本批的完整编码结果，按照约定的两列CSV格式输出。"

LLM输出两列CSV（`分类`, `检索词`）。

#### 步骤2.7 研究者回写 -h

LLM 会按主题分别输出CSV（以 `--- 主题：[主题名] ---` 分隔）。
研究者按分隔行切分，**每个主题保存为一个独立文件**，例如：

batches/batch_00_户外玩法影响.csv
batches/batch_00_游戏玩法体验.csv

研究者需要手动保存生生文件，将LLM输出的CSV按主题切分后，保存到：
```txt
data_dir/一起来捉妖_dir/02_inductive_coding_dir/batches/
├── batch_00_户外玩法影响.csv
├── batch_00_游戏玩法体验.csv
└── ...（有几个主题就几个文件）
```
命名格式：`batch_<NN>_<主题名>.csv`，主题名与 LLM 输出的分隔行一致。

同时，把LLM的阅览报告+你的回应+编码摘要也保存一份：
```txt
data_dir/一起来捉妖_dir/02_inductive_coding_dir/batches/
├── batch_00_preview.md          ← 阅览报告+你的回应+编码摘要
├── batch_00_户外玩法影响.csv
├── batch_00_游戏玩法体验.csv
```
batch_00_preview.md 不需要格式化，直接从LLM对话窗口把阅览报告、你的确认回复、编码摘要三段复制进去就行。这是你的过程记录，未来追溯用。

**然后更新四层记忆**：

1. **更新第2层 `02_codebook_current.md`**：
   - 新编码：添加条目（含定义、纳入/排除标准、样例引文）
   - 修改的编码：覆盖旧定义
   - 删除的编码：移除条目

操作：

打开：02_inductive_coding_dir/knowledge/02_codebook_current.md

把LLM这轮产出的所有编码写进去。格式按模板：


``` markdown
# 当前编码本 (第2层记忆)

**版本**：v0.1
**最后更新**：2026-04-17
**已处理批次**：batch_00

## 主题1：户外玩法影响

### 位置失调

**定义**：因户外玩法的地理位置设计导致玩家感到不公或不便。

**纳入标准**：
- 提到资源/活动集中在特定城市或区域
- 提到自身位置导致无法参与

**排除标准**：
- 纯粹抱怨"活动少"但不涉及地域差异 → 可能归入【资源不均】

**样例引文**：
- "只有大城市才有好资源"
- "不在广州就别玩了"
- "三线城市啥都没有"

---

### 资源不均

**定义**：...

---

## 主题2：游戏玩法体验

### 擂台失衡

**定义**：...

---

（每个编码都这样写）
```
写这个文件的时间大概15-30分钟

2. **追加第3层 `01_rolling_rules.txt`**（仅重大变更时）：
   - 合并/拆分/重命名/删除编码时记录

操作：

如果在审阅过程中你做了合并/拆分/重命名等决策，追加到：02_inductive_coding_dir/knowledge/01_rolling_rules.txt

第一轮通常没有太多需要记的（因为没有"历史编码"要合并）。但如果你在审阅时告诉LLM"把X和Y合并成Z"了，就记一条：

```markdown
### [批次0] 合并

- **合并前**：XX、YY
- **合并后**：ZZ
- **原因**：...
- **后续规则**：遇到类似内容统一编为【ZZ】
```

3. **追加 `prompt_log.json`**（结构化变更日志）：

```json
{
  "batch_id": 1,
  "timestamp": "2026-04-16T14:30:00",
  "changes": [
    {
      "type": "initial",
      "themes": ["户外玩法影响", "游戏玩法体验"],
      "codes_count": 15,
      "reason": "首轮归纳编码完成"
    }
    {
      "type": "add",
      "code": "操作反馈延迟",
      "theme": "户外玩法影响",
      "reason": "出现5次以上，与现有'界面问题'不完全重合"
    },
    {
      "type": "merge",
      "source_codes": ["操作卡顿", "响应慢"],
      "target_code": "操作反馈延迟",
      "theme": "户外玩法影响"
    }
  ],
  "codebook_version": "v0.2",
  "themes": ["户外玩法影响", "游戏玩法体验"]
}
```

#### 步骤2.8 饱和度检查 -s

```bash
python scripts/05_saturation_check.py --app <APP_NAME>
```

当最近3批的新增编码数均 ≤ 2 时，提示可以进入收尾。

#### 循环：回到步骤2.0处理下一批

每批结束后，对着这个表打勾，全部打完才开始下一批：
```txt
批次 _____ 完成检查表

□ CSV已保存到 batches/batch_NN_<主题>.csv
□ 阅览报告+回应+摘要已保存到 batches/batch_NN_preview.md
□ 已审阅CSV质量（抽查引文、检查编码名、确认无范围外混入）
□ 已更新 02_codebook_current.md（所有编码都有定义+纳入/排除+样例）
□ 已更新 01_rolling_rules.txt（如有重大决策）
□ 已更新 prompt_log.json
□ 已运行 05_saturation_check.py
□ 已确认 03_focus.txt（下一批的聚焦主题）
□ 已运行 02_create_prompts.py 为下一批组装prompt
```
---

### 阶段三：演绎编码（归纳完成后）

演绎阶段将稳定的编码本作为"字典"，应用于新收集的数据。详细流程参见
`prompts/deductive/00_base_rules.txt`。核心区别：**不主动创造新编码**，
除非大量"字典无法覆盖"的内容出现且经研究者批准。

---

### 阶段四：生成最终编码本

#### 步骤4.1 合并所有批次 -s

```bash
python scripts/03_merge_codings.py --app <APP_NAME>
```

读取 `batches/` 下所有 `batch_NN_coding.csv`，合并去重后输出到
`codebook_merged.csv`。

#### 步骤4.2 导出MAXQDA字典 -s

```bash
python scripts/04_build_dictionary.py --app <APP_NAME>
```

生成 `codebook_final.xlsx`（两列：分类、检索词），可直接导入 MAXQDA 字典工具。

---

## 故障排查

### 常见失败模式

以下是实战中遇到过的典型失败，以及如何识别和处理。

#### 失败模式1：主题被当成编码

**症状**：研究者给了6个主题框架，LLM输出的CSV里分类列就是这6个主题名
（例如"空间结构"下塞了所有跟地域/场所/路线相关的引文）。

**识别**：检查编码数是否过少（通常应有10+）、每个编码下的引文是否
语义差异大。

**处理**：在对话中指出：

> "你把主题当编码用了。'空间结构'是容器，应包含多个具体编码，
> 比如'地域集中'、'场所稀缺'、'路线单一'。请重新按主题→编码的
> 层级关系产出摘要。"

#### 失败模式2：为覆盖率强造编码

**症状**：聚焦模式下，LLM为了让每条评论都有编码，造出与聚焦主题
无关的辅助编码（如"接入故障"、"功能诉求"）。

**识别**：检查编码摘要中是否有与 `03_focus.txt` 所定主题明显无关的编码。

**处理**：

> "你违反了聚焦模式纪律。'接入故障'、'功能诉求'与户外玩法无关，
> 应归为'范围外'。请重新产出摘要，严格遵守 3.2 '不强行赋码' 的纪律。"

#### 失败模式3：同义不同码

**症状**：同一概念在不同措辞下被创建成多个编码（"上班冲突"、
"出差不能玩"、"疫情禁足"分别成码）。

**识别**：阅读编码摘要时，发现几个编码"讲的是一回事"。

**处理**：

> "'上班冲突'、'出差不能玩'、'疫情禁足' 本质是同一概念——因现实条件
> 无法参与户外玩法。请合并为【现实冲突】，定义：..."

#### 失败模式4：引文被改写或截断

**症状**：CSV中的检索词不是原评论完整片段，有省略号或明显改写痕迹。

**识别**：抽查几条CSV引文，去原批次txt搜索是否完全匹配。

**处理**：

> "第N行的引文'...' 不是原评论完整片段。我的格式要求是引文必须是
> 原文连续片段，不允许截断或改写。请重新输出并保留原文。"

#### 失败模式5：LLM跳过编码工艺

**症状**：LLM直接给出编码结果，没有经过"阅览→确认→摘要"的步骤；
或者编码结果看起来像"顺序处理"而非全局标准化（有多个同义编码并存）。

**识别**：LLM在收到批次数据后立即输出CSV，或不经过审阅环节。

**处理**：重新粘贴prompt并强调：

> "请严格按第1层第5节'工作流约定'执行。收到数据后先输出【批次阅览报告】，
> 等待我确认后再编码。"

### 其他问题

#### LLM输出格式异常

**处理**：指出具体问题+重发规则：

> "你的CSV不符合格式要求：[具体问题]。请严格按第1层第5节步骤4的
> 格式要求重新输出：只有两列（分类、检索词），引文必须是原文完整片段。"

#### 编码漂移

**症状**：同类内容在不同批次被贴不同编码；某编码定义逐渐偏离最初描述。

**处理**：
1. 打开 `02_codebook_current.md`，检查漂移编码的定义是否模糊
2. 补充"纳入标准"和"排除标准"
3. 在 `01_rolling_rules.txt` 记录漂移矫正决策
4. 下一批对话开头提醒LLM："请严格遵循第2层中【X】的定义..."

#### 上下文溢出

**处理**：
- 每批开新对话窗口，不要一个会话跑到底
- 如果单批100条超出上下文，调小 `--batch_size`（建议50-80）

#### 编码本膨胀

**症状**：批次数>5 且编码数量>40。

**处理**：
1. 暂停新批次，进入"重构期"
2. 检查 `02_codebook_current.md`，找出语义重叠的编码
3. 手动合并，在 `01_rolling_rules.txt` 记录决策

---

## 附录：关键文档索引

| 文档 | 面向 | 用途 |
|------|------|------|
| `README.md`（本文件） | 研究者 | 完整工作流指南 |
| `AGENTS.md` | Codex开发AI | 脚本开发守则 |
| `docs/prompt_engineering.md` | 研究者+Codex | Prompt层面的详细约定 |
| `prompts/inductive/00_base_rules.txt` | LLM | 归纳编码方法论+编码工艺 |
| `prompts/inductive/03_focus_template.txt` | 研究者 | 每批聚焦指令模板 |
| `prompts/deductive/00_base_rules.txt` | LLM | 演绎编码方法论 |

---

## 版本说明

**v0.2** (当前版本)
- 统一为聚焦编码模式（移除全景模式）
- 新增第4层"聚焦指令"（`03_focus.txt`）
- 编码工艺明确化：Step A→B→C→D 四步法
- 加入覆盖率检查、范围外复核、命名规范、内部日志要求
- 补充"常见失败模式"章节（基于实战反馈）

**v0.1** (已废弃)
- 初版三层记忆架构
