# 三仓边界冻结（历史快照 · 2026-07-27）

> **Historical / Superseded as Current State.** 本文记录 2026-07-27 的边界
> 收口决定，不能用作三仓当前事实。2026-08-21 之后的 Mixed Recovery / MuJoCo
> 与 Dual-camera B / Isaac Stage 5 事实由
> [THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md) 唯一维护。
> 历史内容和证据路径保持不动，避免破坏 provenance。

**状态**：在本文整理完成前，**冻结**新 Gate、新 runtime lane、新 risk 维度、新 dashboard 页面提交。  
**基线 commit**：`d7ba9d53e9df94c0c4565ba31114cf9b1511a878`（中游 `main`）  
**诚实边界（全文有效）**：**Not task success / Not Sim2Real / Not real robot**。

---

## 1. 唯一对外定位（冻结）

**主语**（全文对外叙述以此为主）：

> **具身策略数据治理与分层验证框架**

**结构**（不得再并列成三条产品线）：

| 层次 | 角色 | 对外怎么说 |
| --- | --- | --- |
| **基础** | 三仓数据链（采集 → 契约 → release → 训练 → handoff） | 「数据治理与契约化流水线」 |
| **配套** | Policy Runtime、Risk、HOC | 「分层验证与 readiness 配套」；服务于数据链的可审计判定，不是独立产品 |

禁止对外写成「数据平台 + Runtime 平台 + Risk 平台」三条并列产品线。

---

## 2. 模块所有权表（冻结）

| 仓库 | 模块域 | 实现锚点（摘要） | 明确不做 |
| --- | --- | --- | --- |
| **中游** `robot-arm-episode-data-lab` | **合同** | `configs/robot_schemas/panda.yaml`、`POLICY_ADAPTER_CONTRACT.md`、runtime S4 合同 | ROS 实时控制 |
| | **数据** | `upstream_m6.py` adapter、`inspect_dataset.py`、release 脚本 | 物理 lift/place 重判 |
| | **训练** | `train_act_*`、SmolVLA Recovery 入口 | 仿真执行 |
| | **离线评测** | open-loop gate、`unified_eval_report_v0`、评测 SOP | 在线 task GT 改判 |
| | **handoff** | `prepare_bridge_handoff.py` | PyBullet 执行 |
| **上游** `ros2-arm-teleoperation-suite` | **在线 inference** | SmolVLA/ACT 推理节点、PolicyBackend | schema/release/训练 |
| | **scheduler** | chunk queue、同步 replan、`runtime_s4` 启动合同；async double-buffer 仅有中游离线 bench，在线未接线 | 中游 split 物化 |
| | **execution adapter** | TTL、sequence、限幅、Hold/E-stop 裁决 | 下游 replay harness |
| | **task GT** | continuous GT、`batch_generator` 物理门禁 | 中游从 `object_pose` 重推成败 |
| **下游** `ros2-moveit-pybullet-bridge` | **replay** | **`PolicyRunner` = replay harness**（JSONL / trace bundle → PyBullet） | 采集、训练 |
| | **monitor** | `dist_monitor`、tracking 时序 | 任务 go/no-go |
| | **risk** | `risk_engine`、offline readiness | 覆盖上游 GT / 改写 `failure_lane` |
| | **HOC** | 四泳道控制台、trace export | 真机驱动 |

**硬命名**：下游 `PolicyRunner` 对外统一称为 **replay harness**（开环动作复现与接口 smoke），**不是**在线策略大脑；`is_closed_loop=false`、`claims_task_success=false` 为默认诚实标签。

---

## 3. Release 术语（冻结）

| 术语 | 定义 | 典型实现 | manifest 特征 |
| --- | --- | --- | --- |
| **non-overwrite release** | 拒绝覆盖非空输出目录的发布；固定当次拷贝与 inspection，**不**保证跨机指纹 | `training/scripts/prepare_dataset_release.py::prepare_release` | `manifest.json` + `inspection_report.json`；**无** `release_content_sha256`、**无** `splits.json` 指纹 |
| **immutable release** | 含 split、逐文件 hash、content fingerprint 的不可变发布；训练/评测绑定的权威数据根 | `training/scripts/prepare_smolvla_s3_release.py` 等 | `immutable: true`、`release_content_sha256`、逐文件 SHA256、`splits.json` |

**对外表述规则**：

- 泛称「release」且未列指纹时 → 默认 **non-overwrite release**。
- 声称「不可变 / SHA 锁定 / 防静默漂移」→ 必须指向 **immutable release** 产物并给出 hash。
- 不得把 `prepare_dataset_release` 的输出直接写成「immutable release」（除非后续统一底层实现并补指纹）。

**简历/作品集统一说法**：**权威合同 + SHA 锁定镜像**（指 immutable release + checkpoint audit + gate lock，而非口头「单源」）。

---

## 4. 可公开复核的最小证据包

不必公开大视频与完整 `runs/`，但对外链接或 README 应至少包含下列可机器读产物 + 生成命令：

| # | 产物 | 权威路径（SmolVLA Recovery v3 示例） |
| --- | --- | --- |
| 1 | **canonical gate JSON** | [public_evidence/canonical_v3/open_loop_gate_summary.json](public_evidence/canonical_v3/open_loop_gate_summary.json) + `configs/smolvla_s3/eval_gate_v3.lock.json` |
| 2 | **release / checkpoint SHA** | [public_evidence/canonical_v3/release_checkpoint_summary.json](public_evidence/canonical_v3/release_checkpoint_summary.json)（release fingerprint、split、adapter SHA 与 checkpoint contract） |
| 3 | **per-seed summary** | [public_evidence/canonical_v3/s4_gate.json](public_evidence/canonical_v3/s4_gate.json) + [s4_per_seed_summary.json](public_evidence/canonical_v3/s4_per_seed_summary.json) |
| 4 | **unified report** | [public_evidence/canonical_v3/unified_eval_summary.json](public_evidence/canonical_v3/unified_eval_summary.json)（open-loop / PolicyRunner / Isaac；`claims_*=false`） |
| 5 | **生成命令 + 外部 artifact 地址** | 见 [FINAL_PROJECT_SUMMARY.md §7](FINAL_PROJECT_SUMMARY.md#7-复现与追溯)；索引见 [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) |

完整资产登记（含 internal-only）见 [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)。公开包的原始路径、SHA256 与字段摘录规则见 [public_evidence/canonical_v3/provenance.json](public_evidence/canonical_v3/provenance.json)。

---

## 5. 作品集对外入口（压缩）

**主导航仅保留五份 + 本冻结页**：

| # | 文档 | 用途 |
| --- | --- | --- |
| 1 | [PORTFOLIO_REFERENCE.md](PORTFOLIO_REFERENCE.md) | 作品集母版（5 分钟价值 + 30 分钟技术展开，唯一叙事入口） |
| 2 | [portfolio_system_overview.svg](portfolio_system_overview.svg) | 人类可读架构图（数据链 + 我的职责 + 当前结论） |
| 3 | [BADCASE_ATTRIBUTION_SUMMARY.md](BADCASE_ATTRIBUTION_SUMMARY.md) | 失败归因案例（证伪 reach 3/5 → 1/5） |
| 4 | [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | 证据索引（生成脚本 + 能/不能证明） |
| 5 | [resume_description.md](resume_description.md) | 简历话术（三套版本 + 禁止清单） |

**内部审计**（保留在仓内，**不**进主导航）：`FINAL_PROJECT_SUMMARY.md`、`ROBOT_SYSTEM_PROJECTS_PORTFOLIO_REFERENCE.md`、`DEEP_DESIGN_ANALYSIS.md`、`EMBODIED_EVALUATION_ENGINEER_ALIGNMENT.md`、`SMOLVLA_RECOVERY_V3_PORTFOLIO.md`、`interview_walkthrough.md`、`project_status.md`、历史 MLP 母版等。检索入口：`docs/README.md`「内部审计」表。

---

## 6. 简历表述修正（冻结）

| 旧表述（禁用） | 冻结表述 |
| --- | --- |
| 「下游无 ROS 依赖」 | **handoff artifact 与模型框架解耦**（下游消费 JSONL/manifest；不捆绑 PyTorch/LeRobot 训练栈；Bridge 侧仍有 ROS 2 集成面用于 dist_monitor/risk launch） |
| 「单源合同」 | **权威合同 + SHA 锁定镜像**（schema YAML + immutable release 指纹 + `eval_gate_v3.lock.json` + checkpoint config audit） |

---

## 7. 功能提交冻结

在 **§1–§6** 落地且三仓 README / 作品集主导航已对齐前：

- **禁止**新增 Gate 版本、runtime lane、risk 维度、dashboard 页面。
- **禁止**把 Policy Runtime / Risk / HOC 包装为与数据链并列的对外产品线。
- **允许**：文档对齐、证据索引补链、pytest 契约回归、既有产物的 relabel（Superseded / Historical）。

解冻条件：三仓 README 指向本页；`docs/portfolio/README.md` 仅列五份对外文档；`resume_description.md` 已采用 §6 表述。

---

## 8. 三仓 README 指针

| 仓库 | 指针 |
| --- | --- |
| 中游（本仓） | [docs/portfolio/README.md](README.md) |
| 上游 | `ros2-arm-teleoperation-suite` → 本文件链接 |
| 下游 | `ros2-moveit-pybullet-bridge` → 本文件链接 |
