# Scripts

**本目录由 Codex 填充。**

开发守则参见项目根目录的 `AGENTS.md`。

## 待开发的脚本列表

按此顺序实现，每个脚本规范详见 `AGENTS.md` "脚本规范" 章节：

1. `utils.py` — 共享工具函数
2. `00_setup_proj.py` — 初始化项目目录
3. `01_sampling_data.py` — 抽样+切分批次
4. `02_create_prompts.py` — 组装三层prompt
5. `03_merge_codings.py` — 合并所有批次的编码CSV
6. `04_build_dictionary.py` — 生成MAXQDA字典Excel
7. `05_saturation_check.py` — 饱和度监控

## 开发路线建议（给Codex）

最小打通路径：1 → 2 → 3 → 4，可以跳过5先跑基础流程验证。
最终产出（4）验证通过后，补充饱和度监控（5）与其他辅助脚本。
