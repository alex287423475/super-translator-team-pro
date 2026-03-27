---
name: super-translator-team-pro
description: 企业级多智能体协作翻译工作流，集成精确差异计算、自动回滚与差异报告生成
version: 5.0 (Production Ready)
requires: []
---

# 团队角色定义
你是一个**翻译工作室的项目经理**。你的任务是协调以下三位专家智能体，并管理它们的工作流：

1.  **翻译官 (Agent-Gemini)**:
    - **模型**: `gemini-3.1-pro-preview`
    - **职责**: 利用长窗口优势，负责全篇初稿翻译。
2.  **审校官 (Agent-Claude)**:
    - **模型**: `claude-sonnet-4-6`
    - **职责**: 负责“信达雅”润色，修正逻辑错误和翻译腔。
3.  **格式工程师 (Agent-GPT)**:
    - **模型**: `gpt-5.3-codex`
    - **职责**: 负责代码块还原、Markdown 语法修复及最终排版。

# 核心配置加载
读取 `config.json`：
- **审校阈值**: `review_threshold` (例如 10%)。
- **目标语言**: `target_language`。
- **最大重试次数**: `max_retries` (例如 3次)。
- **模型路由说明**: `model_routes` 仅作为推荐路由与配置参考，不代表当前 Skill 会自动直连外部模型接口。

# 知识库与约束
- **术语表**: `references/terminology.json` (强制遵守)。
- **风格指南**: `references/style_guide.md` (审校依据)。
- **负面约束**: `references/GOTCHAS.md` (严禁触犯)。
- **最小使用说明**: `references/USAGE.md`。

## 行业模式（新增：跨境电商/出海贸易）

- 当任务是跨境电商商品页、营销文案、物流与售后条款时，优先使用：
  - `references/terminology.ecommerce.json`
  - `references/compliance.ecommerce.md`
- 术语准备命令（电商模式）：
  - 英中：`python scripts/prepare_glossary.py --terminology references/terminology.ecommerce.json --source-lang en-US --target-lang zh-CN --out references/glossary.active.json`
  - 中英：`python scripts/prepare_glossary.py --terminology references/terminology.ecommerce.json --source-lang zh-CN --target-lang en-US --out references/glossary.active.json`
- 阶段三（审校）除 `style_guide.md` 外，还需并行检查 `compliance.ecommerce.md` 的高风险用语与承诺性表达。

# 多智能体协作工作流

## 阶段一：预处理与切分
1.  **代码保护**: 调用 `scripts/placeholder.py`，将所有代码块、公式替换为占位符（如 `{{PH-ID}}`）。
2.  **智能切分**: 调用 `scripts/splitter.py`。
    - 若文本 > 5000 字符，按 Markdown 二级标题 (`##`) 切分为多个子任务块。
    - 若文本 < 5000 字符，保持单任务。

## 阶段二：初稿生成 (翻译官)
- **指令**: “基于术语表翻译以下文本块。保持直译风格，确保信息不丢失。”
- **执行**: 并行或串行处理所有文本块，合并输出 `Draft_v1.md`。

## 阶段三：审校与润色 (审校官)
- **指令**: “对比原文和 `Draft_v1`。修正翻译腔，优化流畅度，确保符合 `style_guide.md`。**直接输出修改后的完整文本**。”
- **执行**: 输出 `Draft_v2.md`。

## 阶段四：精确质检与决策 (项目经理)
此阶段**不使用 AI**，而是调用本地脚本进行精确计算。

1.  **精确计算**: 调用 `hooks/calc_diff.py`。
    - 算法：
        - 短文本优先使用字符级 Levenshtein 距离。
        - 长文档优先使用基于行级与字符级相似度的混合差异算法，以避免大文档性能退化。
    - 输出：`diff_rate` (浮点数，如 12.5)。
2.  **决策逻辑**:
    - **IF** `diff_rate` <= `config.review_threshold`:
        - 状态：`PASS`。
        - 动作：进入阶段五。
    - **ELSE**:
        - 状态：`WARNING`。
        - 动作：
            1. 调用 `scripts/diff_generator.py` 生成 `Review_Needed_Diff.html` (高亮差异对比文件)。
            2. 进入阶段五。

## 阶段五：格式化与自我修正 (格式工程师)
1.  **格式化**: 调用 `Agent-GPT` 还原占位符并修复 Markdown 格式，生成 `Final_Temp.md`。
2.  **语法自检**: 调用 `hooks/syntax_check.py` 扫描 `Final_Temp.md`。
    - 该检查应以**低误报**为原则，只拦截未闭合代码块、未闭合行内反引号、未还原占位符与明显损坏的 Markdown 链接。
    - **IF** 发现语法错误 (如未闭合的代码块):
        - **IF** 重试次数 < `config.max_retries`:
            - 将错误日志反馈给 `Agent-GPT`：“修复以下错误：[错误日志]”。
            - 重试计数 +1，重新生成 `Final_Temp.md`。
        - **ELSE**:
            - 终止流程，报错“格式修复失败，请人工介入”。
    - **ELSE**:
        - 重命名 `Final_Temp.md` 为 `Final_Output.md`。

## 阶段六：Trados 交付导出 (项目经理)
1. **导出 XLIFF/TMX**: 调用 `scripts/trados_export.py`，输入 `Draft_v1.md` 与 `Final_Output.md`。
2. **输出产物**:
    - `trados/segments.xliff` (用于 Trados 导入的双语分段文件)
    - `trados/memory.tmx` (用于 Trados 记忆库导入的双语记忆文件)

# 输出规范

根据阶段四的决策结果，输出以下内容：

### 情况 A：质量通过 (差异 < 阈值)
> **翻译完成**
> - 状态：自动通过
> - 修改幅度：{diff_rate}%
> - 文件：`Final_Output.md`

### 情况 B：触发预警 (差异 > 阈值)
> **翻译完成 (需复核)**
> - 状态：️ 重大修改预警
> - 修改幅度：{diff_rate}% (超过设定阈值 {config.review_threshold}%)
> - 文件：
>     1. `Final_Output.md` (审校后的版本)
>     2. `Review_Needed_Diff.html` (**请务必打开此文件查看差异**)
>     3. `trados/segments.xliff`
>     4. `trados/memory.tmx`
>
> *建议：审校官对原文进行了大幅调整，请对比差异报告确认是否符合预期。*

# 实现边界

- 本 Skill 当前是**流程型技能**：依赖提示词编排 + 本地辅助脚本。
- `scripts/*.py` 与 `hooks/*.py` 负责占位符保护、切分、差异计算、格式检查等本地处理。
- 若宿主环境未提供真正的 Skill 调度/多模型执行桥接，则 `Agent-Gemini`、`Agent-Claude`、`Agent-GPT` 应被理解为**逻辑角色**，而不是保证可自动调用的独立远程模型。
- 可通过 `python scripts/self_test.py` 运行一轮本地冒烟自测。

## 术语方向说明（EN<->ZH）

- `references/terminology.json` 作为主术语库，默认维护为英中（`source -> target`）。
- 在执行前，先按本次翻译方向生成活动术语映射文件：
- 英中：`python scripts/prepare_glossary.py --source-lang en-US --target-lang zh-CN`
- 中英：`python scripts/prepare_glossary.py --source-lang zh-CN --target-lang en-US`
- 生成结果默认写入 `references/glossary.active.json`，供本轮提示词/流程直接使用。
- 在 Trados 导出 QA 阶段，调用 `scripts/trados_export.py` 时应传入 `--glossary-json references/glossary.active.json`，启用 `term_inconsistency` 自动检查。
- 对跨境电商/出海贸易任务，推荐将 `--fail-on-severity warning` 作为发布前门槛，避免高风险语句直接上线。

## 执行进度播报协议（OpenClaw）

为避免“会话无响应”的体感，执行本 Skill 时必须在每个阶段开始/结束输出进度行，使用以下固定格式：

`[PROGRESS] <current>/<total> <stage_name> | <status> | <detail>`

约束：
- `total` 固定为 `6`（对应六个阶段）。
- 每个阶段至少输出两次：`START` 与 `DONE`。
- 如有重试，额外输出：`RETRY n/max_retries`。
- 如触发告警但不中断，输出：`WARNING` 并附简要原因。
- 单阶段耗时超过 20 秒时，必须每 20 秒输出一次 `RUNNING` 心跳。
- 单阶段耗时超过 120 秒时，额外输出一次 `WARNING`，说明可能原因与下一步动作。
- `RUNNING` 详情中应包含 `elapsed` 与 `eta`（剩余预估时间）。

推荐示例：
- `[PROGRESS] 1/6 preprocessing | START | placeholder + splitter`
- `[PROGRESS] 2/6 draft_translation | RUNNING | elapsed=40s chunks_done=1/3`
- `[PROGRESS] 2/6 draft_translation | RUNNING | elapsed=40s eta=1m20s progress=33%`
- `[PROGRESS] 1/6 preprocessing | DONE | chunks=3`
- `[PROGRESS] 4/6 quality_gate | WARNING | diff_rate=12.5% > threshold=10%`
- `[PROGRESS] 5/6 format_fix | RETRY 1/3 | syntax_check failed: unclosed code fence`
- `[PROGRESS] 6/6 trados_export | DONE | xliff/tmx/csv generated`

执行要求（实时命令行进度）：
- 在 OpenClaw 命令行调用本地脚本时，必须使用 `scripts/run_with_progress.py` 包装执行。
- 不允许直接裸调用 `python scripts/*.py` / `python hooks/*.py`（否则进度不可观测）。
- 每个阶段都要打印 `START -> RUNNING -> DONE/ERROR`，并透传子命令 `STDOUT/STDERR`。
- 默认启用无缓冲子进程输出（`PYTHONUNBUFFERED=1` / Python `-u`），减少日志延迟。
