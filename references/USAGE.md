# Super Translator Team Pro Usage

本文件给出这套 Skill 的最小使用方式，方便在 OpenClaw 或其他宿主环境里快速验证流程。

## 适用范围

- 技术文档 Markdown 翻译
- 含代码块、行内代码、LaTeX 公式、少量 HTML 标签的文档
- 需要术语统一、格式保护、差异对照的场景

## 当前能力边界

- 本 Skill 是“流程型 Skill”，不是独立工作流引擎。
- 它依赖宿主环境提供模型调用能力与文件编排能力。
- `config.json` 里的 `model_routes` 目前是参考配置，不会由本地脚本自动发起远程模型调用。

## 最小执行流程

假设输入文件为 `input.md`。

1. 保护代码和特殊格式：

```powershell
python scripts/placeholder.py input.md > input.processed.md
```

2. 如有需要，切分长文档：

```powershell
python scripts/splitter.py input.processed.md
```

3. 让宿主环境或人工完成：

- 初稿翻译，得到 `Draft_v1.md`
- 审校润色，得到 `Draft_v2.md`

4. 计算修改幅度：

```powershell
python hooks/calc_diff.py Draft_v1.md Draft_v2.md
```

5. 生成差异报告：

```powershell
python scripts/diff_generator.py Draft_v1.md Draft_v2.md Review_Needed_Diff.html
```

6. 还原占位符并修复 Markdown：

```powershell
python scripts/format_fix.py Draft_v2.md input.mapping.json > Final_Temp.md
```

7. 做最终格式检查：

```powershell
python hooks/syntax_check.py Final_Temp.md
```

8. 检查通过后，将 `Final_Temp.md` 作为最终输出。

9. 导出 Trados 交付文件：

```powershell
python scripts/trados_export.py Draft_v1.md Final_Output.md --source-lang en-US --target-lang zh-CN --xliff-out trados/segments.xliff --tmx-out trados/memory.tmx
```

显式指定术语映射用于术语一致性 QA：
```powershell
python scripts/trados_export.py Draft_v1.md Final_Output.md --source-lang en-US --target-lang zh-CN --glossary-json references/glossary.active.json --qa-csv-out trados/qa_flags.csv
```

增量导出（只导出新增/变更段）：

```powershell
python scripts/trados_export.py Draft_v1.md Final_Output.md --source-lang en-US --target-lang zh-CN --baseline-csv trados/segment_map_prev.csv --only-changed --xliff-out trados/segments.delta.xliff --tmx-out trados/memory.delta.tmx --csv-out trados/segment_map.delta.csv
```

Trados 导出分段规则（增强版）：
- 标题（`#`）单独成段
- 列表项（有序/无序）单独成段
- Markdown 表格行单独成段
- 代码围栏块（``` ... ```）按整块成段
- 普通段落按空行分段
- 每个段会生成稳定 ID（XLIFF `trans-unit id` / TMX `tu.tuid`），便于增量更新与记忆对齐
- 同时会输出 `segment_map.csv`，包含 `stable_id / source / target` 映射，便于人工审校与追踪
- CSV 会包含 `change_type` 字段：`new` / `updated` / `unchanged`
- 增量模式下会额外输出 `removed_segments.csv`，记录基线中已删除段（`change_type=removed`）
- 会输出 `qa_flags.csv`，标记高风险段（如空译文、疑似未翻译、占位符残留、长度异常）
- 若 `--glossary-json` 可用，还会检测 `term_inconsistency`（术语不一致）
- 默认是“只报告不拦截”（`--fail-on-severity none`）

## 推荐输入约束

- 尽量使用 UTF-8 编码
- Markdown 标题尽量规范，长文档优先使用 `##` 二级标题
- 避免把整页复杂 HTML 直接塞进输入；这套 Skill 更适合 Markdown 主体 + 少量内联标签

## 推荐输出产物

- `Draft_v1.md`
- `Draft_v2.md`
- `Final_Temp.md`
- `Final_Output.md`
- `Review_Needed_Diff.html`
- `input.mapping.json`
- `trados/segments.xliff`
- `trados/memory.tmx`
- `trados/segment_map.csv`
- `trados/removed_segments.csv` (仅增量模式)
- `trados/qa_flags.csv`

## 故障排查

- `syntax_check.py` 报未闭合代码块：
  优先检查模型输出是否破坏了三反引号围栏。

- `format_fix.py` 报占位符恢复失败：
  优先检查对应的 `.mapping.json` 是否存在、是否和输入源文件匹配。

- `calc_diff.py` 很慢：
  现在长文档已使用较快的混合算法；若仍偏慢，优先减少单次比对文档大小。

- Trados 导入提示分段不一致：
  检查 `Draft_v1.md` 与 `Final_Output.md` 的段落数量是否差异过大。导出脚本会尽量保底输出，但建议译后不要大幅打散原段落。

## Terminology Direction (EN<->ZH)

`references/terminology.json` is maintained in default `English -> Chinese` pairs.
When your project direction changes, generate a directional glossary file before translation:

```powershell
python scripts/prepare_glossary.py --source-lang zh-CN --target-lang en-US --out references/glossary.active.json
```

Recommended workflow:
- Run `prepare_glossary.py` once per language direction.
- Feed `references/glossary.active.json` to your translation prompt/runtime as the active terminology map.
- Keep `terminology.json` as the canonical master file; do not manually duplicate two files for two directions.
- If reverse direction has duplicate target terms, script keeps the first mapping and reports `collision_count` + `collision_examples` (report-only, no hard block).

## Progress Visibility in OpenClaw

When running this skill in OpenClaw, require stage-by-stage progress output so users can see liveness:

`[PROGRESS] <current>/<total> <stage_name> | <status> | <detail>`

Suggested stage names:
- `preprocessing`
- `draft_translation`
- `review_polish`
- `quality_gate`
- `format_fix`
- `trados_export`

Minimum reporting:
- one `START` line when a stage begins
- one `DONE` line when a stage ends
- optional `RETRY` / `WARNING` lines when needed
- if a stage runs longer than 20s, print `RUNNING` heartbeat every 20s
- if a stage runs longer than 120s, print a `WARNING` with likely cause and next action

Helper command:
```powershell
python scripts/progress_line.py --current 2 --total 6 --stage draft_translation --status RUNNING --detail "elapsed=40s chunks_done=1/3"
```

ETA helper command:
```powershell
python scripts/progress_eta.py --current 2 --total 6 --stage draft_translation --elapsed-sec 40 --expected-sec 120
```

Realtime wrapper (recommended for OpenClaw command execution):
```powershell
python scripts/run_with_progress.py --current 4 --total 6 --stage quality_gate --expected-sec 30 --heartbeat-sec 5 -- python hooks/calc_diff.py Draft_v1.md Draft_v2.md
```

`run_with_progress.py` defaults to unbuffered child output (`PYTHONUNBUFFERED=1` and Python `-u` when applicable).  
If you need to disable this behavior, add: `--no-force-unbuffered`.

Session-mode realtime command template (for OpenClaw):
```powershell
python scripts/run_with_progress.py --current 1 --total 6 --stage preprocessing --expected-sec 20 --heartbeat-sec 5 -- python scripts/placeholder.py input.md
python scripts/run_with_progress.py --current 1 --total 6 --stage preprocessing --expected-sec 20 --heartbeat-sec 5 -- python scripts/splitter.py input.processed.md
python scripts/run_with_progress.py --current 4 --total 6 --stage quality_gate --expected-sec 30 --heartbeat-sec 5 -- python hooks/calc_diff.py Draft_v1.md Draft_v2.md
python scripts/run_with_progress.py --current 5 --total 6 --stage format_fix --expected-sec 20 --heartbeat-sec 5 -- python scripts/format_fix.py Draft_v2.md input.mapping.json
python scripts/run_with_progress.py --current 5 --total 6 --stage format_fix --expected-sec 10 --heartbeat-sec 5 -- python hooks/syntax_check.py Final_Temp.md
python scripts/run_with_progress.py --current 6 --total 6 --stage trados_export --expected-sec 20 --heartbeat-sec 5 -- python scripts/trados_export.py Draft_v1.md Final_Output.md --source-lang en-US --target-lang zh-CN --xliff-out trados/segments.xliff --tmx-out trados/memory.tmx
```
