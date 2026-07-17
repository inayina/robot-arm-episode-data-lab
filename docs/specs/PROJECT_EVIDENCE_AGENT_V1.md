---
title: Project Evidence Agent V1
type: spec
status: draft
authoritative: false
rag_enabled: false
created: 2026-07-14
---

# Project Evidence Agent V1

> 本SPEC描述待实现设计，不代表对应能力已经存在，不得作为当前项目事实来源。

## 1. Background

### 1.1 项目范围与本次审计依据

本项目当前应描述为“Panda 机械臂的多仓数据、训练、离线评估与 Sim2Sim / Sim2Real-readiness 验证闭环”，不能据此声称真实机械臂部署、已完成真实 Sim2Real、稳定在线自主抓取或已完成 ACT canonical run。该边界由中游 `AGENTS.md:236-250`、`README.md:18-21,166` 和 `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:5-9,89-98` 明确给出。

本 SPEC 基于 2026-07-14 的只读审计。仓库采用以下逻辑名，实际路径仍由配置解析，不写死为运行前提：

| 逻辑名 | 本次解析路径 | 角色证据 |
|---|---|---|
| `ros2-arm-teleoperation-suite` | `/home/ina/dev/ros2-arm-teleoperation-suite` | 上游；`docs/AGENTS.md:9-87` |
| `robot-arm-episode-data-lab` | `/home/ina/robot-sim-lab/robot-arm-episode-data-lab` | 中游；`AGENTS.md:11-62` |
| `ros2-moveit-pybullet-bridge` | `/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge` | 下游；`docs/AGENTS.md:9-73` |

默认 sibling 路径在本机不存在；当前代码按“环境变量 → 配置路径 → fallback paths”选择首个存在目录。证据是 `configs/rag_sources.yaml:1-13` 与 `scripts/rag_assistant.py:58-75`。这项可移植行为必须保留。

### 1.2 当前 RAG 已实现的能力

当前入口是 `scripts/rag_assistant.py`，并由 `bin/ask-project:1-4` 提供 shell 包装。已实现能力包括：

- 从 YAML 加载多个仓库和 include/exclude 规则，解析环境变量与 fallback path；见 `scripts/rag_assistant.py:47-75`。
- 对三仓匹配文件做大小、二进制和排除目录过滤；见 `configs/rag_sources.yaml:15-45`、`scripts/rag_assistant.py:78-102`。
- Markdown 按 ATX 标题层级分块；见 `scripts/rag_assistant.py:110-132`。
- Python 使用标准库 `ast` 按模块、顶层 class/function 及 class method 分块；见 `scripts/rag_assistant.py:135-175`。
- 其他文本配置按每 80 行分块；见 `scripts/rag_assistant.py:179-187`。
- 对英文、代码标识符和中文字符做轻量 tokenization；见 `scripts/rag_assistant.py:203-216`。
- 使用 BM25，附加 symbol 精确 token 3 倍 boost 和非测试 Python 文件 1.2 倍 boost；见 `scripts/rag_assistant.py:219-278`。
- 输出仓库、相对路径、行号、章节/符号、片段和分数；见 `scripts/rag_assistant.py:337-353`。
- 可选调用 OpenAI Chat Completions 或本地 Ollama；无可用 LLM 时本地检索仍可执行；见 `scripts/rag_assistant.py:304-334`。
- 支持一次性 `--query` 和交互模式；见 `scripts/rag_assistant.py:356-386`。

本次只读运行解析到 3 个仓库、485 个文件和 5,160 个 chunk。该数字是审计时运行观察，不是稳定接口或项目 headline。

### 1.3 为什么仍不足以可靠回答项目事实

当前实现解决的是“在哪里出现了这些词”，尚未解决“这份材料是什么性质、是否当前、能否证明该 claim”。例如：

- `configs/rag_sources.yaml:18` 使三仓所有 `docs/**/*.md` 同等进入候选，包含 current、portfolio、reference、spec、legacy 和 archive。
- 当前 index 不包含 `evidence/**/*.json`、`training/reports/**/*.json` 或 `data/exports/**/manifest.json`；见 `configs/rag_sources.yaml:15-32`。因此最新运行产物无法与提到同一数字的文档公平竞争。
- 检索排序给非测试 Python 代码 1.2 倍 premium，反而没有落实 `AGENTS.md:119-128` 的“自动化测试及实际运行产物优先于代码、配置、文档”顺序；见 `scripts/rag_assistant.py:270-276`。
- prompt 能要求 LLM 区分事实类别，但候选选择前没有类型、状态或 mode 过滤；见 `scripts/rag_assistant.py:281-301`。LLM 不能补救已经选错或漏掉的证据。

本次实测查询“ACT是否已经完成canonical训练？”时，前两名来自 `docs/sorting_dev_guide.md`，第 4 名来自 `docs/archive/planning/panda_training_lab_spec.md`；查询“94.399 ms能否作为已验证数字写入简历？”时，结果包含下游 `docs/archive/portfolio/UNIFIED_RESUME.md`，却无法召回未被索引的 `evidence/downstream/benchmark_summary.json`。这说明当前问题不是单纯调 BM25 参数即可解决。

### 1.4 文档混乱与检索算法问题必须分开处理

文档问题是知识源本身存在冲突、失效链接、错误索引或未声明状态。例如：

- `docs/portfolio/CANONICAL_EXPERIMENT.md:8-10,47-54` 把 `17.626/49.508 ms` 与 `94.399 ms` 写成 canonical 结果；最新归档产物 `evidence/downstream/benchmark_summary.json:5-11` 是 `fault_injection=false`、mean/max `9.79/34.218 ms`，且 alarm latency 为 null。
- `docs/README.md:3-4` 指向当前不存在的 `evidence/canonical_20260711/README.md`；`.gitignore:17-20` 只为该目录预留 exception，但本次审计未找到目录。
- `docs/README.md:67-75` 存在嵌套且内容错误的 Markdown code fence。

检索算法问题则是没有知识分类、状态过滤、证据优先级、claim resolution 和 query mode。Project Evidence Agent V1 同时提供 registry、query 和 audit：registry/query 降低误召回，audit 暴露源文档问题；它不应把“更聪明的排序”伪装成“文档已被修正”。

## 2. Current-State Audit

### 2.1 当前链路

```text
bin/ask-project
  -> scripts/rag_assistant.py --query
     -> configs/rag_sources.yaml
     -> configured_sources()
     -> iter_source_files()
     -> parse_markdown_file() / parse_python_file() / fixed 80-line chunks
     -> retrieve_chunks() [BM25 + boosts]
     -> evidence text
     -> optional OpenAI/Ollama summary
```

### 2.2 状态分类

| 项目 | 当前状态 | 证据与充分性 |
|---|---|---|
| RAG 入口 | **已实现** | `scripts/rag_assistant.py:356-386`；充分 |
| 旧 shell CLI | **已实现** | `bin/ask-project:1-4`；充分 |
| 配置来源 | **已实现** | 默认 `configs/rag_sources.yaml`，可由 `--config` 替换；`scripts/rag_assistant.py:19,356-360`；充分 |
| 三仓路径解析 | **已实现** | env、默认、fallback 顺序；`scripts/rag_assistant.py:58-75`；测试仅覆盖 env 优先，见 `tests/test_rag_assistant.py:37-55` |
| 文件扫描规则 | **已实现但存在缺陷** | include/exclude/size/binary 去重已实现；`scripts/rag_assistant.py:78-102`。缺陷是 `docs/**/*.md` 无分类且运行产物未纳入 |
| Markdown 分块 | **已实现** | 按标题；`scripts/rag_assistant.py:110-132`；无 code-fence/重复标题专项测试 |
| Python AST 分块 | **已实现** | module/class/function/method；`scripts/rag_assistant.py:135-175`，基础测试见 `tests/test_rag_assistant.py:99-109` |
| 配置/接口文本分块 | **已实现** | 固定 80 行；`scripts/rag_assistant.py:179-187` |
| 排序 | **已实现但存在缺陷** | BM25 + symbol boost + source Python boost；`scripts/rag_assistant.py:219-278`。没有 evidence/status/mode 权重，且 source boost 与项目证据优先级冲突 |
| 测试路径识别 | **已有但存在缺陷** | 排序用 `startswith("test") or "/test"`，prompt 标签只认 `tests/`；`scripts/rag_assistant.py:270-287` |
| LLM 调用 | **已实现、可选且不稳定** | OpenAI 或 Ollama；`scripts/rag_assistant.py:304-334`。本次受限环境返回调用失败，但证据列表仍输出 |
| 无 LLM 检索输出 | **已实现** | `scripts/rag_assistant.py:337-353`；但没有结构化 JSON 输出和证据分类 |
| 当前测试 | **已实现但覆盖不足** | 6 个测试，覆盖双仓 fixture、env 优先、输出字段、空结果、交互模式、Python symbol；`tests/test_rag_assistant.py:23-109`。本次 `6 passed` |
| knowledge registry | **尚未实现** | 三仓搜索未找到 `knowledge_registry` 或 `project_knowledge` 实现；当前项目证据充分 |
| query modes | **尚未实现** | parser 只有 `--query/--config/--top-k`；`scripts/rag_assistant.py:356-361` |
| audit 子命令 | **尚未实现** | 当前 parser/代码无对应入口 |
| impact 子命令 | **尚未实现** | 当前 parser/代码无 Git diff 解析或 component 映射 |
| 非 LLM 检索评测 | **尚未实现** | 当前测试没有固定查询集、期望类型或排序断言 |
| 94.399 ms 已被运行产物验证 | **文档声明但代码/产物未确认** | `docs/portfolio/CANONICAL_EXPERIMENT.md:10,53-54`；冲突审计见 `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:50-53` |
| ACT canonical training 已完成 | **文档和代码均不能确认** | ACT 构建代码存在于 `training/scripts/train_act_lerobot.py:168-190`；canonical 产物未定位，见 `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:72-73,98` |

### 2.3 旧 CLI 兼容面

V1 必须保留以下外部行为：

- `python3 scripts/rag_assistant.py --query "..."`
- `python3 scripts/rag_assistant.py --config <path> --query "..." --top-k N`
- 无 `--query` 时的交互模式，至少在一个兼容周期内保留。
- `bin/ask-project "..."` 将所有参数合并为一个 query 的行为。
- Python 层 `DocumentChunk.header_title` 和 `load_all_documents(Path)` 是源码中明确标注的兼容接口；见 `scripts/rag_assistant.py:38-44,190-196`。若后续弃用，必须先给 deprecation warning，不能在 V1 静默删除。

## 3. Confirmed Problems

### 3.1 `docs/**/*.md` 无差别进入索引

**证据：** `configs/rag_sources.yaml:15-32`；扫描器仅按 glob 和目录名过滤，见 `scripts/rag_assistant.py:85-102`。

中游实际同时存在 `docs/archive/`、`docs/legacy_pybullet/`、`docs/reference/`、`docs/portfolio/`、current docs 和若干 spec/roadmap；上游存在 `docs/archive/` 与多份 `SPEC_V2_*`；下游存在 `docs/archive/`、`docs/design/`、`docs/portfolio/` 和 current docs。当前扫描器不理解这些差异。

**影响：** archive 规划、作品集话术或通用学习资料可能因为标题/词频高而压过代码、测试和 current facts。本次 ACT 与 94.399 ms 查询已复现。

### 3.2 current/canonical/portfolio/reference/archive/legacy 无统一机器可读分类

**证据：** `docs/README.md:8-58` 以人工章节描述日常开发、历史规划、参考和作品集；`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:11-24` 又定义 capability status；二者都没有被 `scripts/rag_assistant.py` 读取为 metadata。相邻仓目录命名也不同：下游规划文档集中在 `docs/design/`，上游使用根级 `docs/SPEC_V2_*`。

**影响：** 目录名启发式不足以表达单文件例外、导出文档、已完成 spec、冲突中的 canonical 文档以及某个文件只对特定 component 权威的情况。

### 3.3 排序未真正落实 AGENTS.md 的证据优先级

**证据：** `AGENTS.md:119-128` 的顺序是测试/运行产物 > 代码 > 配置/schema > 当前技术文档 > README/portfolio > 通用经验。当前 index 不含主要运行产物，而 `scripts/rag_assistant.py:270-276` 对非测试 Python 代码加 1.2 倍权重；测试没有对应 premium。prompt 虽把 `tests/` 标为最高优先级，见 `scripts/rag_assistant.py:281-295`，但这是检索之后的文本标签，不会改变候选。

**影响：** “prompt 声称测试优先”与“retriever 实际给 source boost”不一致；更无法比较运行 JSON 与文档，因为 JSON 根本未入库。

### 3.4 测试路径识别没有覆盖三仓真实布局的一致语义

**证据：**

- 中游主要是 `tests/test_*.py`。
- 上游同时有 `tests/test_*.py` 与 `src/<package>/test/test_*.py`，例如 `src/grasp_monitor/test/test_grasp_monitor_state_machine.py`。
- 下游主要是 `<package>/test/test_*.py`，例如 `pybullet_bridge/test/test_panda_handoff.py`、`risk_engine/test/test_aggregator.py`。
- 排序器的 `_is_test` 启发式能识别上述多数路径，见 `scripts/rag_assistant.py:270-274`；但 `_prompt.evidence_kind` 只接受 `relative_path.startswith("tests/")`，见 `scripts/rag_assistant.py:281-287`，会把下游/上游 package tests 标成“项目代码”。
- `tests/test_rag_assistant.py:23-109` 没有覆盖三种真实布局。

**影响：** 同一个测试文件在打分和输出标签阶段可能得到不同类型，证据解释不可信。

### 3.5 未验证数字与最新运行产物冲突

**证据：**

- 旧 canonical 文档：`docs/portfolio/CANONICAL_EXPERIMENT.md:8-10,47-54`。
- 当前统一事实审计：`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:50-53`。
- 最新归档 JSON：`evidence/downstream/benchmark_summary.json:2-20`。
- 同一冲突也残留在下游前端常量：`ros2-moveit-pybullet-bridge:hoc_console/frontend/src/data/canonicalRun.ts:1-23`。

**结论：** `94.399 ms` 当前只能标为 `needs_reconciliation`/未验证 claim，不能作为 verified headline。`9.79/34.218 ms` 仅证明 1-episode、no-fault smoke，也不能扩展成 fault campaign 结论。

### 3.6 当前输出不能可靠区分事实、历史资料和规划

**证据：** `DocumentChunk` 只有 repository/path/symbol/content/line fields，见 `scripts/rag_assistant.py:22-44`；输出只有这些字段和分数，见 `scripts/rag_assistant.py:337-353`。类型判断只在 LLM prompt 内用简单路径/后缀生成三类标签，见 `scripts/rag_assistant.py:281-301`。

**影响：** 没有 LLM 时完全没有状态标签；有 LLM 时也只能基于已选 chunk 猜测，无法知道 registry owner、last_verified、legacy boundary 或 claim authority。

### 3.7 当前测试不足以证明检索可靠性

**证据：** `tests/test_rag_assistant.py:23-109` 的六个测试只使用非常小的临时仓库 fixture。它们没有测试：

- current 与 archive 同词竞争；
- code/test/run artifact/canonical/portfolio 的排序；
- ACT、94.399 ms、三仓职责等真实回归查询；
- `needs_reconciliation` 过滤；
- 中英文混合查询和代码 symbol/path exact match 的稳定顺序；
- 三种真实测试目录；
- LLM 关闭时的结构化证据完整性；
- 本地文档链接、Git impact 或旧 wrapper 的 subprocess 兼容。

测试全部通过只能说明当前基础接口工作，不能证明回答正确。

## 4. Goals

V1 只实现以下目标：

1. 建立机器可读知识注册表，描述三仓知识源的 kind、status、mode、优先级、component 和验证时间。
2. 支持 `fact`、`debug`、`runbook`、`learning`、`portfolio`、`legacy` 及确定性 `auto` 查询模式。
3. 在检索前按 evidence kind/status/mode 过滤，在检索后按证据优先级解析冲突。
4. 提供只读文档与知识源一致性 audit，输出 JSON 和 Markdown。
5. 提供只读 Git diff impact 分析，映射 component、测试、文档、canonical facts 和风险。
6. 保留现有 RAG CLI 和 `bin/ask-project` 兼容入口。
7. 建立不依赖 LLM、以召回/过滤/排序为核心的固定查询评测。

## 5. Non-Goals

V1 不做：

- 多 Agent 协同或多 Agent 框架；
- 向量数据库、embedding service 或重型搜索依赖；
- 自动修改代码、注册表或文档；
- 自动删除、移动、重命名文档；
- 自动修复所有文档冲突；
- 实时 ROS graph、topic、controller 或仿真进程诊断；
- Web 前端或新聊天界面；
- 真实机器人控制、真实机械臂部署或 completed Sim2Real；
- 通用互联网知识问答；
- 以 LLM 生成文本的措辞作为正确性测试。

## 6. User Stories

### US-1：确认 ACT canonical training 状态

- **输入：** `project-knowledge query --mode fact "ACT是否已经完成canonical训练？"`
- **模式：** `fact`
- **预期行为：** 排除 archive/legacy/reference/portfolio-only；优先返回 `training/scripts/train_act_lerobot.py`、`training/scripts/train_act_smoke.py` 与当前 canonical facts；输出“代码路径存在，但当前项目证据不足，无法确认 canonical 完整训练产物”。
- **预期证据：** `training/scripts/train_act_smoke.py:1-18`、`training/scripts/train_act_lerobot.py:168-190`、`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:72-73,98`。
- **禁止：** 因文件名或开发指南标题含 ACT，就回答“已完成训练”；不得用 sorting spec 或 archive roadmap 证明当前状态。

### US-2：判断数字能否写入简历

- **输入：** `project-knowledge query --mode portfolio "94.399 ms能否作为已验证数字写入简历？"`
- **模式：** `portfolio`
- **预期行为：** 可召回 portfolio 候选，但先做 claim resolution；标记 94.399 为 `needs_reconciliation`，并指出最新 JSON 是不同 run、no fault。
- **预期证据：** `docs/portfolio/CANONICAL_EXPERIMENT.md:47-54`、`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:50-53`、`evidence/downstream/benchmark_summary.json:5-11`。
- **禁止：** 把未定位原始 JSON 的数字标为 verified headline；也不得把 9.79 ms 误写成 fault alarm。

### US-3：明确查询 KUKA legacy

- **输入：** `project-knowledge query --mode legacy "KUKA RRT抓取实现在哪里？"`
- **模式：** `legacy`
- **预期行为：** 允许召回中游 `agents/`、`core/`、`docs/legacy_pybullet/` 和明确注册的 legacy 资料，每条结果显示 `legacy` 标记。
- **预期证据：** `AGENTS.md:11-19`、`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md:100-106` 以及对应 legacy 代码。
- **禁止：** 把 KUKA/RRT 行为合并为 Panda training release 或上游 MoveIt Servo 当前主线。

### US-4：查询三仓当前职责

- **输入：** `project-knowledge query --mode fact "三仓当前职责是什么？"`
- **模式：** `fact`
- **预期行为：** 返回中游 canonical overview、上游/下游 AGENTS、关键代码入口；按仓库分组并显示充分性。
- **预期证据：** 中游 `AGENTS.md:11-62`、上游 `docs/AGENTS.md:9-87`、下游 `docs/AGENTS.md:9-73`，并由相关实现/测试佐证。
- **禁止：** 用 legacy KUKA 或下游历史 iiwa 资料补充 Panda 主线；不得声称真实机器人控制已完成。

### US-5：handoff 变更影响

- **输入：** 修改 `training/scripts/prepare_bridge_handoff.py` 后运行 `python -m project_knowledge.cli impact --base HEAD~1 --head HEAD`。
- **模式：** `impact`
- **预期行为：** 映射到 `handoff` component，列出 `tests/test_prepare_bridge_handoff.py`、下游 loader/replay 契约测试、可能过期的 `docs/INTER_REPO_CONTRACTS.md`、`docs/CLOSED_LOOP_RUNBOOK.md`、canonical facts 与 manifest 文档。
- **预期证据：** registry path rule、`depends_on` 反向边与 Git name-status diff。
- **禁止：** 自动修改这些文件；不得声称列出的文件一定已失效，只能标为“需要复核”。

### US-6：文档只读审计

- **输入：** `python -m project_knowledge.cli audit --json-out /tmp/audit.json --markdown-out /tmp/audit.md`
- **模式：** `audit`
- **预期行为：** 报告未注册 Markdown、缺失注册路径、本地失效链接、重复 H1、authority 冲突、current→legacy/archive 引用、缺少 last_verified、已知 claim 冲突和 code fence 问题。
- **预期证据：** 每条 finding 包含 repository、path、line、rule id、severity 和 remediation hint。
- **禁止：** 自动改链接、移动 archive 或覆写文档。

### US-7：Codex 回答前检索

- **输入：** `python -m project_knowledge.cli query --mode auto --no-llm --query "<用户原始问题>"`
- **模式：** `auto`，保守路由。
- **预期行为：** 即使无网络/LLM，也输出完整、带分类和路径行号的证据；证据不足时明确输出“当前项目证据不足，无法确认”。
- **预期证据：** 由注册表过滤后的测试、运行产物、代码、配置和 current docs。
- **禁止：** 用互联网常识补齐当前项目状态，或因 LLM 不可用而不输出证据。

## 7. Knowledge Classification Model

### 7.1 Evidence kind

下表优先级为建议默认值（0-100）；单文件 override 可降低或提高，但不能绕过 mode/status 硬过滤。

| kind | 本仓真实例子 | fact 模式 | 适用模式 | 默认优先级 | 可作为最终事实来源 |
|---|---|---:|---|---:|---|
| `test` | `tests/test_prepare_bridge_handoff.py`；上游 `src/*/test/`；下游 `*/test/` | 是 | fact, debug, runbook, legacy | 100 | 是；只证明测试覆盖与断言范围，不自动证明生产运行 |
| `run_artifact` | `evidence/**/*.json`、特定 release/metrics/manifest | 是 | fact, debug, portfolio | 98 | 是；必须有 provenance、run/release id，且未被冲突降级 |
| `code` | `training/**/*.py`、上游 `src/**/*.py`、下游 package Python | 是 | fact, debug, runbook, legacy | 90 | 是；只证明实现存在，不证明运行成功 |
| `config` | `configs/**/*.yaml`、ROS launch/config | 是 | fact, debug, runbook, legacy | 85 | 是；证明声明配置，运行时 override 需另证 |
| `canonical` | `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md` | 是 | fact, debug, portfolio | 80 | 有条件；status=current 且 claim 未冲突，只能低于测试/产物/代码 |
| `current_doc` | `README.md`、`docs/PROJECT_OVERVIEW.md`、三仓 `docs/AGENTS.md` | 是 | fact, debug, runbook, portfolio | 65 | 有条件；用于职责/约定，不能单独证明实现或 benchmark |
| `runbook` | `docs/CLOSED_LOOP_RUNBOOK.md` | 否，除非回答“规定的跑法” | runbook, debug | 60 | 只能作为当前操作说明，不能证明命令已成功运行 |
| `portfolio` | `docs/portfolio/resume_description.md` | 否 | portfolio | 35 | 否；只作为候选表述，必须由更高等级证据支持 |
| `reference` | `docs/reference/knowledge_base.md` | 否 | learning | 25 | 否；只表示背景/学习资料 |
| `spec` | 本文件、上游 `docs/SPEC_V2_*`、下游 `docs/design/*spec*` | 否 | learning, debug, impact | 20 | 否；除非问题明确询问设计内容，仍必须标为设计 |
| `legacy` | 中游 `agents/`、`core/`、`docs/legacy_pybullet/` | 否 | legacy | 30 | 仅可回答明确 legacy 范围，不能成为 Panda 主线事实 |
| `archive` | 三仓 `docs/archive/` | 否 | audit；显式诊断时可作为冲突上下文 | 5 | 否 |

`run_artifact` 不能仅凭文件位于 `evidence/` 就自动成为强证据。registry override 必须记录其 producer、run/release id 或 `depends_on`，并可将 sample/mock 标为 `derivative` 或 `historical`。当前 `evidence/downstream/benchmark_summary.json` 是 latest archived smoke，不是 fault campaign。

### 7.2 Status

| status | 含义 | fact 行为 | 最终事实来源 |
|---|---|---|---|
| `current` | 当前维护且最近验证 | 可进入 | 按 kind 规则允许 |
| `draft` | 尚未接受的设计/文档 | 排除 | 否 |
| `derivative` | 从其他材料派生的截图、话术、汇总 | 仅作辅助，不能独立定案 | 否 |
| `needs_reconciliation` | 与更强证据冲突或来源未定位 | 硬排除；debug/portfolio 可带警告展示 | 否 |
| `historical` | 曾经有效但非当前 | 排除；learning/debug 可显式展示 | 否 |
| `legacy` | 旧机器人/旧主线仍可查询 | 仅 legacy 模式 | 仅能回答 legacy 范围 |
| `archive` | 归档、被替代或保留记录 | 所有 query 默认排除 | 否 |

### 7.3 关键约束

1. kind 描述“材料是什么”，status 描述“材料当前处于什么状态”，二者不能合并成一个字段。
2. 路径规则提供默认分类；单文件 override 负责异常，不通过把整个 `docs/portfolio/` 误标为 canonical 来省维护成本。
3. `authoritative_for` 是 claim/component 范围，不是“这个文件所有内容永远正确”。
4. `canonical` 仍低于实际测试、运行产物、代码和 schema；canonical 自身过期时必须能降级为 `needs_reconciliation`。
5. legacy 与 Panda 主线必须在候选过滤阶段隔离，不能只在最终措辞中提醒。

## 8. Registry Schema

### 8.1 文件与版本

新增 `configs/knowledge_registry.yaml`。V1 使用现有 PyYAML，不新增 schema 库或数据库。顶层必须有 `schema_version: 1`，加载时做手写严格校验：未知必填字段、非法 kind/status/mode、重复 repo name、重复 override path 均报错。

### 8.2 建议 schema

```yaml
schema_version: 1

repositories:
  - name: ros2-arm-teleoperation-suite
    role: upstream
    path: ../ros2-arm-teleoperation-suite
    path_env: ROS2_ARM_TELEOP_REPO
    fallback_paths:
      - /home/ina/dev/ros2-arm-teleoperation-suite
    required: true

  - name: robot-arm-episode-data-lab
    role: midstream
    path: .
    required: true

  - name: ros2-moveit-pybullet-bridge
    role: downstream
    path: ../ros2-moveit-pybullet-bridge
    path_env: ROS2_MOVEIT_PYBULLET_BRIDGE_REPO
    fallback_paths:
      - /home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge
    required: true

rules:
  - repository: robot-arm-episode-data-lab
    globs: ["tests/**/*.py"]
    kind: test
    status: current
    enabled_modes: [fact, debug]
    evidence_priority: 100
    authoritative_for: [dataset_adapter, training, handoff]
    component: [dataset_adapter, training, handoff]
    tags: [pytest, midstream]
    last_verified: 2026-07-14

  - repository: ros2-moveit-pybullet-bridge
    globs: ["*/test/**/*.py", "*/*/test/**/*.py"]
    kind: test
    status: current
    enabled_modes: [fact, debug]
    evidence_priority: 100
    authoritative_for: [downstream_replay, risk_monitoring]
    component: [downstream_replay, risk_monitoring]
    tags: [pytest, downstream]
    last_verified: 2026-07-14

  - repository: robot-arm-episode-data-lab
    globs: ["docs/archive/**/*.md"]
    kind: archive
    status: archive
    enabled_modes: []
    evidence_priority: 5
    authoritative_for: []
    component: []
    tags: [archive]
    last_verified: 2026-07-14

overrides:
  - repository: robot-arm-episode-data-lab
    path: docs/portfolio/THREE_REPO_CANONICAL_FACTS.md
    kind: canonical
    status: current
    enabled_modes: [fact, debug, portfolio]
    evidence_priority: 80
    authoritative_for: [repository_roles, canonical_evidence]
    component: [canonical_evidence]
    tags: [panda, three_repo]
    depends_on:
      - evidence/downstream/benchmark_summary.json
      - training/reports/panda_mlp_bc/mlp_metrics.json
    last_verified: 2026-07-13

  - repository: robot-arm-episode-data-lab
    path: docs/portfolio/CANONICAL_EXPERIMENT.md
    kind: portfolio
    status: needs_reconciliation
    enabled_modes: [debug, portfolio]
    evidence_priority: 20
    authoritative_for: []
    component: [canonical_evidence]
    tags: [panda, conflicting_claims]
    depends_on: [evidence/downstream/benchmark_summary.json]
    last_verified: 2026-07-13
```

这只是 schema 示例，不是完整 registry，也不在本 SPEC 阶段创建。

### 8.3 字段语义

| 字段 | 要求 |
|---|---|
| `repositories` | 复用当前 name/path/path_env/fallback_paths 语义，增加 role/required |
| `globs` | repo-relative、POSIX 风格；规则按声明顺序匹配，冲突必须报 audit warning，不能静默 last-one-wins |
| `path` override | 单一 repo-relative 文件；优先于 glob rule |
| `kind/status` | 必须来自第 7 节枚举 |
| `enabled_modes` | 文件允许进入的 query modes；audit 始终能读取 registry metadata |
| `evidence_priority` | 0-100；只在硬过滤后参与排序 |
| `authoritative_for` | claim namespace 或 component；空数组表示不能独立定案 |
| `component` | 可为一个或多个第 12 节 component |
| `tags` | robot、framework、artifact scope 等轻量检索标签 |
| `depends_on` | repo-relative 或 `repo:path`；供 audit 与 impact 建立反向边 |
| `last_verified` | ISO date；不是文件 mtime。current/canonical/runbook 必填 |

### 8.4 路径不存在处理

- required repository 的 env/default/fallback 均不存在：query/audit/impact 返回非零，列出所有尝试路径；不能悄悄退化成双仓答案。
- optional repository 不存在：输出结构化 warning，并在结果中显示 coverage incomplete。
- glob 无匹配：audit warning；如果规则标 `required_match: true` 则 error。
- 单文件 override 不存在：error；若 status 是 archive 且明确 `required: false`，可降为 warning。
- `depends_on` 不存在：audit finding；其依赖源不得继续声称“已验证”。
- 路径逃逸 repo root、绝对 override 或 `..`：配置错误并拒绝加载。

## 9. Retrieval Design

### 9.1 流程

```text
query
  -> deterministic mode routing
  -> registry catalog
  -> hard filters (mode, kind, status, repo availability)
  -> existing parsers/chunks
  -> BM25 + exact/path + metadata score
  -> evidence-tier aware rerank and diversity
  -> claim resolution / conflict labels
  -> structured evidence
  -> optional LLM summary of selected evidence only
```

### 9.2 候选过滤先于打分

- `archive`、status=`archive` 默认在所有 query mode 排除。
- `legacy`/status=`legacy` 默认排除，只在 `legacy` mode 进入。
- `reference` 只进入 `learning`。
- `portfolio` 只进入 `portfolio`，或在 debug 中作为冲突对象；不得进入 fact 候选。
- `needs_reconciliation` 不得进入 fact；在 debug/portfolio 中必须带冲突警告且不能成为 resolved claim。
- `spec` 不进入 fact；如果问题明确问“设计/计划是什么”，进入 learning/debug 并标注“待实现设计”。
- 未注册文件不参与 query，只进入 audit 的 `UNREGISTERED_SOURCE` finding。

### 9.3 得分

所有子分量先归一化，建议 V1 初始公式：

```text
score = 50 * normalized_bm25
      + exact_match_bonus          # 0..20，symbol > exact path segment > tag
      + 20 * evidence_priority/100
      + status_weight              # current +10, derivative -10, historical -20
      + mode_match_bonus           # exact mode +10，辅助模式 +0
```

规则：

1. BM25 复用当前实现和中文单字/CamelCase tokenization，避免引入新依赖。
2. exact match 必须区分 symbol、完整路径片段、component/tag；不得通过重复 query token 无限累加。
3. evidence priority 由 registry 提供，不再使用“所有非测试 `.py` 统一 1.2 倍”的隐式规则。
4. status 的硬排除优先于权重；`needs_reconciliation` 不能靠高 BM25 回到 fact。
5. top-k rerank 至少保证出现最高可用 evidence tier，并按 repository/component 做轻量去重，避免一个长 portfolio 文档占满结果。
6. 对同一 claim 冲突时，`test/run_artifact > code > config > canonical > current_doc > portfolio/reference/spec` 是 resolution 约束，不允许 portfolio 仅靠文本分数覆盖代码或运行产物。

### 9.4 LLM 边界

LLM 只接收过滤、排序和 claim resolution 后的证据；prompt 不负责决定证据是否 current。LLM 输出必须引用 evidence id，不能创建 registry 中不存在的来源。

`--no-llm` 时仍输出：mode、coverage、每条 evidence 的 repository/path/line/symbol/kind/status/score/last_verified/component、冲突和“证据不足”结论。JSON 应是核心机器接口，Markdown/text 是渲染层。

## 10. Query Modes

| mode | 默认纳入 | 默认排除 | 典型问题 |
|---|---|---|---|
| `fact` | test, run_artifact, code, config, canonical, current_doc | portfolio, reference, spec, legacy, archive, needs_reconciliation | 当前是否实现、真实字段、职责、数字是否已验证 |
| `debug` | test, run_artifact, code, config, current_doc, runbook；可显示冲突源 | reference 默认排除；archive 仅显式 flag | 报错、接口不一致、失败原因 |
| `runbook` | runbook, config, code, test | portfolio/reference/spec/legacy/archive | 如何运行、验证或复现 |
| `learning` | reference, current_doc, spec（带标签）, code | portfolio/legacy/archive | 概念、设计原理、学习材料 |
| `portfolio` | verified evidence + portfolio candidate + reconciliation warnings | legacy/archive/reference | 数字能否写简历、如何有边界地表述 |
| `legacy` | legacy code/docs/tests | Panda current 默认排除，除非作为边界说明 | KUKA、旧 PyBullet、历史 RRT |
| `auto` | 由下述规则唯一确定 | 继承目标 mode | Codex/旧 CLI 默认 |

### 10.1 `auto` 确定性路由

按以下优先顺序匹配，首个命中生效：

1. 明确包含 `legacy`、`KUKA`、`历史实现`、`旧版` → `legacy`。
2. 包含 `简历`、`作品集`、`headline`、`面试表述`、`能否写` → `portfolio`。
3. 包含 traceback、具体 error、`报错`、`失败`、`不一致`、`排查`、`debug` → `debug`。
4. 包含 `如何运行`、`怎么跑`、`命令`、`runbook`、`复现` → `runbook`。
5. 包含 `原理`、`为什么`、`学习`、`概念`，且不含“当前是否实现/字段/职责” → `learning`。
6. 其他全部 → `fact`。

`RRT` 单独出现不能自动路由 legacy，因为下游或历史材料都可能出现该词；歧义时保守进入 `fact`，若无 current 证据则提示用户显式选择 `legacy`，不能自动混合。

## 11. Audit Design

### 11.1 命令与输出

```bash
python -m project_knowledge.cli audit \
  --json-out /tmp/project-evidence-audit.json \
  --markdown-out /tmp/project-evidence-audit.md
```

audit 只读三仓与 registry。finding 统一包含：`rule_id`、`severity`、`repository`、`path`、`line`、`message`、`related_paths`、`suggestion`。默认有 error 时 exit 2、有 warning 时 exit 1、无 finding 时 exit 0；`--no-fail` 可始终返回 0 供探索使用。

### 11.2 V1 检查

| rule id | 检查 | V1 方法 |
|---|---|---|
| `UNREGISTERED_MARKDOWN` | 未注册 Markdown | `git ls-files '*.md'` 与 catalog 比较；ignored 文件另标 |
| `MISSING_REGISTERED_PATH` | override/required dependency 不存在 | registry resolution |
| `BROKEN_LOCAL_LINK` | Markdown 本地失效链接 | 解析相对文件/目录/anchor；忽略 `http(s)`, `mailto`, code fence |
| `DUPLICATE_H1` | 单文件多个一级标题 | fence-aware line scan；本次中游已有多个候选 |
| `MULTIPLE_AUTHORITIES` | 同一 `authoritative_for` 有多个 current authority 且无优先规则 | registry group check |
| `CURRENT_REFERENCES_LEGACY` | current/canonical/runbook 链接到 legacy/archive | link target catalog status；允许显式 `allow_legacy_reference` override |
| `MISSING_LAST_VERIFIED` | current/canonical/runbook/run_artifact 缺日期 | registry validation |
| `KNOWN_CLAIM_CONFLICT` | 已知数字/ID 冲突 | curated claim key + extractor/expected source；首批覆盖 downstream latency/fault、ACT run status、canonical run/release id |
| `UNCLOSED_CODE_FENCE` | Markdown fence 数量/类型未闭合 | fence-aware parser；应发现 `docs/README.md:67-75` 的异常结构 |
| `DOC_INDEX_ERROR` | 索引路径错误或重复 | 对 registry 标为 index 的表格/链接去重、存在性检查 |

已确认的首批 regression fixture 应包含：

- `docs/README.md:3-4` 的缺失 canonical evidence link；
- `docs/README.md:67-75` 的 code fence 问题；
- `docs/portfolio/CANONICAL_EXPERIMENT.md:53-54` 与 `evidence/downstream/benchmark_summary.json:5-11` 的 claim conflict；
- 下游 `hoc_console/frontend/src/data/canonicalRun.ts:16-19` 的旧数字作为非 Markdown 依赖冲突对象。

### 11.3 推迟到 V2+

- 任意自然语言 claim 的语义矛盾检测；V1 只做 curated claims。
- 外部 HTTP 链接联网校验。
- 自动修复链接、front matter、registry 或文档内容。
- 对 Mermaid、图片内容和截图数字做 OCR/语义审计。
- 判断一个技术结论“科学上是否正确”；V1 只核对项目证据与来源。

## 12. Impact Analysis Design

### 12.1 命令

```bash
python -m project_knowledge.cli impact --base HEAD~1 --head HEAD
```

默认只分析当前 Git repository，避免把每个仓库各自的 `HEAD~1..HEAD` 误当成同一次跨仓变更。可选 `--repository <logical-name>`；未来若支持 `--repository all`，必须逐仓报告解析到的 commit，并对缺失 ref 明确失败。

V1 使用 `git diff --name-status --find-renames <base> <head> --`，不修改工作树。`--include-working-tree` 可另行显式加入 staged/unstaged diff，但默认命令只分析给定 commits。

### 12.2 映射来源

1. registry `component`：changed path → component。
2. registry `depends_on` 的反向索引：changed source → 可能过期的依赖文档/事实源。
3. component 的 test globs：component → 相关测试。
4. symbol/path 共现：只作低置信补充，不可替代显式映射。
5. `authoritative_for`：变更是否触达 canonical claim。

### 12.3 最小 component 映射

| component | 真实路径起点 | 相关测试/文档示例 |
|---|---|---|
| `data_schema` | 中游 `configs/robot_schemas/*.yaml`、`training/io/` | `tests/test_panda_schema.py`、`tests/test_panda_dataset_inspection.py`、`docs/DATA_FLOW.md`、三仓 contract docs |
| `dataset_adapter` | `training/adapters/upstream_m6.py`、`training/scripts/adapt_upstream_panda_dataset.py` | `tests/test_upstream_m6_adapter.py`、`docs/INTER_REPO_CONTRACTS.md` |
| `training` | `training/policies/`、`training/encoders/`、`training/scripts/train_*.py`、evaluate/replay scripts | `tests/test_train_mlp_policy.py`、`tests/test_train_act_smoke.py`、`docs/TRAINING_METHODS.md`、canonical facts |
| `handoff` | `training/scripts/prepare_bridge_handoff.py`、handoff manifest schema/fixtures | `tests/test_prepare_bridge_handoff.py`、下游 `pybullet_bridge/test/test_panda_handoff.py`、`docs/CLOSED_LOOP_RUNBOOK.md` |
| `downstream_replay` | 下游 `pybullet_bridge/pybullet_bridge/learning/panda_handoff.py`、`panda_action_adapter.py`、`jsonl_action_replay_policy.py`、`policy_runner.py`、`scripts/benchmark_system.py` | 下游对应 `pybullet_bridge/test/test_*.py`、中游 handoff/contract docs |
| `risk_monitoring` | 下游 `dist_monitor/`、`risk_engine/`、sensor fusion、benchmark fault paths | `dist_monitor/test/`、`risk_engine/test/`、`docs/FMEA.md`、`docs/SAFETY_ACCEPTANCE_PLAN.md` |
| `canonical_evidence` | 中游 `evidence/`、tracked canonical docs、README、evidence index、known claim rules | `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md`、`CANONICAL_EXPERIMENT.md`、三仓 README |

路径必须使用当前真实下游位置 `pybullet_bridge/pybullet_bridge/learning/...`；不能沿用 `docs/portfolio/THREE_REPO_README_AUDIT.md:727-744` 已指出的旧 `control/`、`policy/` 文档路径。

### 12.4 输出

JSON/Markdown 至少包含：

- diff base/head/repository/commit hashes；
- changed files 与 component；
- direct tests 和 cross-repo contract tests；
- 可能过期文档及依赖原因；
- 受影响 canonical claim/authority；
- 风险提示：schema/action dimension、gate boundary、handoff compatibility、benchmark comparability、legacy leakage、无测试覆盖。

impact 只报告“建议复核/建议运行”，不声称测试已失败，也不运行测试或修改文件。

## 13. Proposed File Changes

以下是批准实施所依据的最小变更结构。实施核对时，用户进一步明确三仓是一套项目并要求相邻仓库也实施；因此 13.4 的“相邻仓只读”约束由该后续指令覆盖，但核心所有权、职责边界和非重复实现原则不变。

### 13.1 新增

| 文件 | 职责 |
|---|---|
| `configs/knowledge_registry.yaml` | 三仓 repository、glob、override、classification、component、authority、dependency 与 verified date 的唯一 registry |
| `project_knowledge/__init__.py` | 包版本与稳定公共类型出口；不放业务逻辑 |
| `project_knowledge/core.py` | registry 校验、source resolution、catalog、chunk metadata、mode filter、BM25/exact/priority rerank；复用当前轻量 parser/tokenizer 思路 |
| `project_knowledge/audit.py` | fence-aware Markdown/link/index 与 registry/claim 只读检查 |
| `project_knowledge/impact.py` | Git diff、component/test/doc/canonical 反向映射 |
| `project_knowledge/cli.py` | `query`、`audit`、`impact` 三个子命令及 JSON/Markdown/text rendering |
| `tests/test_project_knowledge.py` | registry、mode、排序、audit、impact 和兼容单元/集成测试；V1 先集中一文件，稳定后再按增长拆分 |
| `tests/fixtures/project_knowledge/` | 最小三仓目录、registry、冲突 Markdown/JSON 和 Git fixture |
| `tests/fixtures/project_knowledge/query_cases.yaml` | 不依赖 LLM 的固定 query/mode/required/forbidden/ordering 评测集 |

该结构刻意不拆出独立 `models.py/scoring.py/renderers.py/claims.py` 等小模块；V1 以可读、可测试、依赖少为优先。

### 13.2 修改

| 文件 | 修改目的 |
|---|---|
| `scripts/rag_assistant.py` | 缩为兼容包装器，保留旧 flags、交互模式、兼容 Python API；内部调用 `project_knowledge`。一个兼容周期内可保留旧 dataclass adapter |
| `tests/test_rag_assistant.py` | 保留现有 6 个测试并新增 subprocess wrapper/参数兼容断言，不把它替换成 LLM 文案测试 |
| `configs/rag_sources.yaml` | 暂时保留；只增加 deprecation 注释或由兼容 wrapper 读取。V1 不应要求用户立即迁移自定义配置 |
| `bin/ask-project` | 优先保持文件内容不变；只有在无法由 wrapper 完成 mode/default 迁移时才做最小调整 |
| `AGENTS.md` | 实现验收后再把强制调用示例指向新 CLI，同时保留旧命令；SPEC 阶段不改 |
| `docs/README.md` | 实现验收后加入本 SPEC/工具入口并单独修正文档问题；不得在功能实现提交中顺便大规模重排 |

### 13.3 保留兼容包装器

`scripts/rag_assistant.py` 与 `bin/ask-project` 都保留。新模块不能要求用户修改现有 Codex 调用规则后才能工作。

### 13.4 明确不修改

- 上游和下游不复制 registry、catalog、retrieval、audit 或 impact 核心；仅新增转发到中游核心的薄入口、入口测试和使用文档。相邻仓业务实现仍保持只读。
- 中游 `agents/`、`core/` 以及所有 legacy 实现。
- 现有 episode、release、checkpoint、training report 和 evidence 产物。
- 本次审计发现的旧文档、失效链接和数字冲突；它们由 audit 报告，不在 SPEC 轮次修复。

## 14. Compatibility

### 14.1 `scripts/rag_assistant.py`

```bash
python3 scripts/rag_assistant.py --query "..."
```

等价于：

```bash
python -m project_knowledge.cli query --mode auto --query "..."
```

旧 `--top-k` 原样映射；旧 `--config` 若指向 `rag_sources.yaml`，兼容层生成内存 registry defaults，并输出一次 stderr deprecation warning，不写文件。退出码保持：成功 0，配置/扫描失败 2。

无 `--query` 时继续提供旧交互 prompt，每次用 `auto`；新增能力不要求实现新聊天 UI。

### 14.2 `bin/ask-project`

当前 `bin/ask-project:1-4` 已调用旧脚本并把 `$*` 作为 query。只要兼容 wrapper 保留，该文件无需修改：

```bash
bin/ask-project "三仓当前职责是什么？"
```

仍应成功。需要 mode 的高级用户直接调用新 CLI；V1 不改变 wrapper 的参数拼接语义。

### 14.3 Python API

保留 `DocumentChunk.header_title` 与 `load_all_documents(Path)`；旧 `retrieve_chunks(query, chunks, top_k)` 可包装为无 registry metadata 的 `legacy_compat` catalog，仅供测试/外部调用，不用于新 CLI 的 project fact 默认路径。

## 15. Test Strategy

### 15.1 单元测试

- registry 必填字段、枚举、路径逃逸、重复规则、override 优先、缺失 required repo。
- 三种真实测试路径：`tests/`、`src/<pkg>/test/`、`<pkg>/test/` 均分类为 `test`。
- Markdown/Python/配置分块回归，保留现有 AST method behavior。
- mode 硬过滤与 status 硬过滤。
- evidence priority、symbol/path exact match、repository diversity 和 claim resolution。
- 无 LLM JSON schema 稳定性。
- audit 每个 rule id 的正/负 fixture。
- impact name-status（含 rename/delete）、component、depends_on、test/doc/canonical 映射。

### 15.2 Fixture

`tests/fixtures/project_knowledge/` 构造三个小仓库，目录形状模拟真实项目，不复制大型生产文件：

- current code/test/config；
- current canonical 与更强 run artifact；
- portfolio、reference、spec、legacy、archive 同词文档；
- `needs_reconciliation` 的 94.399 vs 9.79 fixture；
- broken link、duplicate H1、unclosed fence、duplicate authority；
- 可初始化的最小 Git repo，用两个 commits 验证 impact。

### 15.3 固定查询评测集

`query_cases.yaml` 每条至少包含：

```yaml
- id: act_canonical_status
  query: ACT是否已经完成canonical训练？
  mode: fact
  required_paths:
    - training/scripts/train_act_lerobot.py
    - docs/portfolio/THREE_REPO_CANONICAL_FACTS.md
  forbidden_kinds: [archive, legacy, reference, portfolio]
  required_conclusion: insufficient_verified_run
```

核心指标：required evidence recall、forbidden evidence leakage、top-tier rank、claim resolution label、deterministic output。LLM 关闭，不能断言自然语言措辞。

至少包含：ACT canonical、94.399 resume claim、三仓职责、KUKA legacy、handoff mismatch、runbook、reference learning、真实机器人/Sim2Real 边界。

### 15.4 兼容测试

- 保留 `tests/test_rag_assistant.py:23-109` 全部测试。
- subprocess 执行 `python3 scripts/rag_assistant.py --query ...`。
- subprocess 执行 `bin/ask-project ...`。
- 验证 LLM 未配置/不可达时仍有 evidence，且不会因网络失败改变检索排序。

## 16. Acceptance Criteria

- [ ] `python -m project_knowledge.cli query --mode fact --no-llm --query "三仓当前职责"` 在无 OpenAI/Ollama 时返回完整结构化证据并退出 0。
- [ ] `test_fact_excludes_legacy_and_archive` 证明 fact 结果中没有 kind/status 为 legacy/archive 的 chunk。
- [ ] `test_learning_allows_reference_with_label` 证明 learning 可召回 reference，且输出明确 `kind=reference`、`authoritative=false`。
- [ ] ACT 固定查询的 top evidence 包含真实 ACT code/canonical status，结论为“未确认 canonical run”，不会被 sorting 文档标题判定为已完成训练。
- [ ] 94.399 ms 固定查询得到 `needs_reconciliation`，不得产生 `verified_headline=true`。
- [ ] `python -m project_knowledge.cli audit --json-out /tmp/audit.json --markdown-out /tmp/audit.md` 同时生成可解析 JSON 和 Markdown，且不修改三仓文件。
- [ ] audit 能检测当前 fixture 中的失效本地链接、未注册 Markdown、重复 H1、缺失 last_verified、unclosed fence 和 known claim conflict。
- [ ] `python -m project_knowledge.cli impact --base HEAD~1 --head HEAD` 对 handoff fixture 输出相关测试与可能过期文档。
- [ ] impact 覆盖 `data_schema`、`dataset_adapter`、`training`、`handoff`、`downstream_replay`、`risk_monitoring`、`canonical_evidence` 七个 component。
- [ ] 三仓测试路径 fixture 全部分类为 kind=`test`，prompt/JSON 标签与排序使用同一分类结果。
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_rag_assistant.py` 旧 CLI 测试继续通过。
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider tests/test_project_knowledge.py` 全部新增测试通过。
- [ ] 固定 query eval 不调用 LLM，重复运行输出 evidence id 和顺序稳定。
- [ ] `git diff --exit-code` 能证明 query/audit/impact 执行本身没有修改被审计仓库。

## 17. Risks and Trade-offs

### 17.1 Registry 维护成本

三仓会继续新增文件，registry 可能落后。用目录规则覆盖常规情况、override 处理例外，并由 `UNREGISTERED_MARKDOWN`/missing path audit 约束；不能追求零维护。

### 17.2 过度依赖人工分类

人工 classification 可能有偏差，但它比从目录名或 prompt 隐式猜测更可审计。V1 应在结果中展示 rule id/override source，让错误可定位。

### 17.3 BM25 对中英文和代码 symbol 的限制

当前中文逐字 token 会放大常见字，CamelCase/underscore 的 exact semantics 仍有限。V1 通过 mode filter、exact path/symbol/tag 和评测缓解，不引入分词器或向量 DB；召回不足应通过 eval case 暴露。

### 17.4 三仓路径不统一

本机实际不在共同父目录，CI/其他开发机也可能不同。必须复用 `path_env` + relative + fallback 语义，输出 resolved coverage，不能把本次绝对路径写进代码。

### 17.5 Canonical 文档自身可能过期

`docs/portfolio/CANONICAL_EXPERIMENT.md` 已证明“canonical”命名不等于强证据。kind=`canonical` 仍低于运行产物/代码，并受 last_verified、depends_on 和 reconciliation 约束。

### 17.6 Audit 误报

current 文档可能合理引用 legacy 作为边界，多个 H1 可能有特殊渲染目的。本地 allowlist/override 必须带理由；audit 只报告，不自动修复。

### 17.7 本 SPEC 再次过期

本文件 front matter 明确 `status: draft`、`authoritative: false`、`rag_enabled: false`。实现后应由 acceptance test、registry 和 current docs 接管事实入口；audit 应检查 stale spec 的 last_verified/status，但不得把本 SPEC 作为“功能已存在”的证据。

### 17.8 运行产物可追溯性

当前 `evidence/*`、`training/reports/*`、`data/*` 多数被 `.gitignore:15-20` 忽略。将它们纳入本地 catalog 能改善事实查询，但 Git impact 无法追踪未提交产物的历史。V1 必须区分“本地存在”与“版本库可追溯”，并输出 provenance warning。

## 18. Implementation Stages

最多四阶段，均只修改中游仓库。

### Stage 1：registry 和 catalog

- **修改范围：** 新增 `configs/knowledge_registry.yaml`、`project_knowledge/__init__.py`、`project_knowledge/core.py` 的 registry/source/catalog 部分与基础 fixtures。
- **测试：** schema validation、三仓 fallback、glob/override、真实测试路径分类、missing path/coverage。
- **独立验收：** `python -m project_knowledge.cli query --mode fact --no-llm --query "三仓当前职责"` 能列出分类后的证据，即使排序仍沿用基础 BM25。
- **回滚：** 删除新增 package/registry/fixtures；旧 `scripts/rag_assistant.py` 尚未切换，不受影响。

### Stage 2：mode-aware retrieval 与兼容层

- **修改范围：** 完成 mode router、filter、score、claim resolution、JSON/text 输出；将 `scripts/rag_assistant.py` 接到新 core，保留旧 API/CLI。
- **测试：** mode isolation、priority、archive/legacy/reference/needs_reconciliation、ACT/94.399/职责 eval、旧 CLI。
- **独立验收：** `python -m project_knowledge.cli query ...`、`python3 scripts/rag_assistant.py --query ...`、`bin/ask-project ...` 三者通过；query eval 全绿。
- **回滚：** 恢复旧 wrapper import path；新 package 保留为未使用代码或整体删除，旧配置仍可运行。

### Stage 3：audit

- **修改范围：** 新增 `project_knowledge/audit.py`、CLI audit wiring、Markdown/link/claim fixtures。
- **测试：** 第 11 节每个 V1 rule 的 true/false case，JSON/Markdown schema 与只读性。
- **独立验收：** `python -m project_knowledge.cli audit --json-out /tmp/audit.json --markdown-out /tmp/audit.md --no-fail`。
- **回滚：** 删除 audit module/子命令与 fixtures；query/兼容层不变。

### Stage 4：impact 与文档收口

- **修改范围：** 新增 `project_knowledge/impact.py`、Git fixture、component mappings；验收后才最小更新 `AGENTS.md`/`docs/README.md`，但不自动清理历史文档。
- **测试：** add/modify/delete/rename diff、七个 component、depends_on、cross-repo test/doc suggestions、dirty tree 不被修改。
- **独立验收：** `python -m project_knowledge.cli impact --base HEAD~1 --head HEAD` 与完整 pytest。
- **回滚：** 删除 impact module/子命令并回退入口文档；query/audit 保持可用。

## 19. Open Questions

以下问题需要项目维护者决定，不能从当前代码自动得出：

1. **Registry 所有权：** V1 是否由中游单一 `configs/knowledge_registry.yaml` 维护三仓全部 override，还是允许上游/下游未来提供只读 fragment 再由中游合并？单一文件实现最小，但跨仓维护责任集中。
2. **可追溯运行产物策略：** 当前 canonical evidence exception 目录不存在，而主要 evidence/reports/data 被 gitignore。哪些 run artifact 必须提交 hash/index，哪些只允许作为本地、低可追溯证据？
3. **Claim authority owner：** `repository_roles`、`data_schema`、`canonical_run`、`downstream_latency` 等 `authoritative_for` namespace 的最终 owner 分别由哪个仓库/维护者批准？
4. **Portfolio verified headline 门槛：** 一个数字除机器可读产物、commit/run id 和无冲突外，是否还要求人工 approval 字段；若要求，approval 记录放 registry 还是独立 evidence index？

在这些问题决定前，V1 的保守默认应是：集中式 registry、本地 ignored artifact 明确标注低可追溯、冲突 claim 不进入 fact、portfolio 数字无明确 verified 标志就不能成为 headline。

---

## Appendix A. Audited Files and Commands

本 SPEC 至少审计了：

- 中游：`AGENTS.md`、`README.md`、`docs/README.md`、`docs/portfolio/THREE_REPO_CANONICAL_FACTS.md`、`docs/portfolio/CANONICAL_EXPERIMENT.md`、`scripts/rag_assistant.py`、`configs/rag_sources.yaml`、`tests/test_rag_assistant.py`、`bin/ask-project`、相关 evidence/ACT 文件。
- 上游：`docs/AGENTS.md`、真实 `tests/` 与 `src/*/test/` 布局、batch/recorder/launch 入口。
- 下游：`docs/AGENTS.md`、真实 `*/test/` 布局、Panda learning/replay/risk 入口和残留 canonical frontend 常量。

执行过的只读验证包括：

```bash
python3 scripts/rag_assistant.py --query "<本SPEC审计问题>"
python3 scripts/rag_assistant.py --query "ACT是否已经完成canonical训练？"
python3 scripts/rag_assistant.py --query "94.399 ms能否作为已验证数字写入简历？"
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  pytest -q -p no:cacheprovider tests/test_rag_assistant.py
```

测试结果为 `6 passed`。该结果只确认旧 RAG 基础测试通过，不代表本 SPEC 中的 query/audit/impact 已实现。
