# 示例项目目录

这是一个**空的项目目录结构**，作为 Codex 生成 `00_setup_proj.py` 时的参照。

研究者实际使用时不要往这里放数据——运行 `00_setup_proj.py --app <你的项目名>`
会创建一个全新的 `<你的项目名>_dir/`。

## 目录结构说明

```
example_app_dir/
├── 00_rawdata_dir/                 ← 放清洗后的原始CSV数据
├── 01_preprocessed_for_llm_dir/    ← 脚本生成的批次txt文件
├── 02_inductive_coding_dir/
│   ├── knowledge/                  ← 三层记忆文件
│   │   ├── prompt_coding_rules.txt      (第1层)
│   │   ├── prompt_rolling_rules.txt     (第3层)
│   │   ├── codebook_current.md          (第2层)
│   │   └── prompt_log.json              (变更日志)
│   └── batches/                    ← 每批的LLM产出（preview + coding）
└── 03_deductive_coding_dir/        ← 演绎编码阶段产出
```

每个空目录里的 `.gitkeep` 文件只是为了让 git 追踪目录结构，可以忽略。
