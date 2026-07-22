# VLA Gate V0：兼容性审计（只读）

> **状态：CLOSED / ARCHIVED**  
> **决策日期：2026-07-21**  
> **当前结论：不进入本机 Gate V1，不作为第一 Panda 后训练策略。**  
> **主要原因：6GB 显存资源 No-Go、55-D 动作契约适配复杂、相对 SmolVLA 工程 ROI 较低。**  
> **保留原因：该审计形成了可复用的动作语义、Execution Adapter、Go/No-Go 和版本追踪契约。**  
> **当前活动路线：SmolVLA Gate S0–S2（Hold at S2；S3 须人工批准）。**  
> **入口：** [`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md) · [`THREE_REPO_CANONICAL_FACTS.md`](portfolio/THREE_REPO_CANONICAL_FACTS.md)

**日期**：2026-07-21  
**审计状态**：Gate V0 文档已完成；**未下载权重、未安装官方环境、未接入 Panda、未启动 Gate V1**。  
**历史候选**：Robbyant / Ant Group **LingBot-VLA 2.0**（公开 README / HF 卡片；本仓无本地权重）。  
**对照契约**：Panda `state[8]` + `ee_delta_gripper[7]` + scene RGB 240×320（训练部署 224 crop）+ `language_instruction` 字段。

来源（公开只读，2026-07-21 检索）：

- https://github.com/Robbyant/lingbot-vla-v2
- https://huggingface.co/robbyant/lingbot-vla-v2-6b
- MarkTechPost / Robbyant 发布说明（交叉核对）

凡本仓未实测项标为 **未验证**。

---

## 1. 兼容性矩阵

| 维度 | 本仓 Panda / ACT 现状 | LingBot-VLA 2.0（公开声明） | 判定 |
|---|---|---|---|
| 输入模态 | state + scene RGB；ACT **不用** language | 图像 + 语言指令 → 动作 | **部分兼容**：本仓有 `language_instruction` 字段；ACT 路径未用；VLA **需要**语言 |
| State 维度 | `observation.state[8]`（joint7+gripper） | 统一 **55-D** canonical state/action（含双臂/腰/头/移动等 pad） | **需 Adapter 映射**；Panda 单臂如何填 55-D **未验证** |
| Action 维度 | `ee_delta_gripper[7]`（delta xyz/rpy + gripper） | 同 55-D 布局：臂关节 14、EE pose 14、gripper 2、手 12、腰 4、头 2、移动 3、保留 4 | **维度不兼容**（直接输出不可喂现执行栈） |
| Action 语义 | 相对 EE delta + gripper cmd ∈[0,1] | EE 为 XYZ+quaternion（公开描述）；是否 absolute/delta **未验证** | **高风险**；必须 Gate V2 open-loop 对照 |
| Action chunk | ACT `chunk_size=50`，部署走队列 | 部署示例 `--use_length 25`（推理步长）；chunk 语义 **未验证**与 ACT 对齐 | **未知** |
| 控制频率 | 控制器 500 Hz；ACT infer ~2 Hz / cmd ~50 Hz | 4090D 上约 **130 ms**/次（10 denoising steps，公开数字） | 频率需 Adapter 节流；**本机显存是否可达未验证** |
| 图像数量/分辨率 | 主相机 scene 1×；训练 320×240→224 | 多相机/分辨率依赖 robot config；RoboTwin 示例存在；**Panda 配置未在官方仓库确认** | **未验证** |
| Language 格式 | 自由字符串（recorder 参数） | 自然语言任务指令（VLM 骨干 Qwen3-VL-4B） | **原则兼容**；token 模板 **未验证** |
| Normalization | ACT checkpoint 内 state/action mean/std | 后训练需 `assets/norm_stats`；官方有 robot config 流程 | **需自建 Panda norm**；未做 |
| Checkpoint | 本仓 ACT `.pt` + metadata | HF `robbyant/lingbot-vla-v2-6b`（6B native-depth）；另需 Qwen3-VL、MoGe、Depth/DINO teacher | **未下载** |
| 许可证 | 本仓代码自有 | 代码 **Apache-2.0**（README） | **许可 OK（公开声明）**；权重附加条款 **未逐文件核验** |
| 推理显存 | ACT ResNet18 级可在中等 GPU 跑 | 6B + VLM 骨干；公开部署示例用 4090D 级 | **本机 6GB 级 No-Go 风险高**（未实测） |
| 自定义 Panda 本体 | 已有 MuJoCo/Isaac Panda | 官方后训练要求 LeRobot 数据集 + `configs/robot_configs/<name>.yaml`；制造商列表含 **Franka**（公开） | **有希望但未验证**：无现成本仓 Panda Isaac 配置；不能假定零样本控臂 |

---

## 2. No-Go / Hold 项（Gate V0 结论）

| ID | 项 | 结论 |
|---|---|---|
| NG-1 | 直接把 55-D 输出接到本仓 `bound_ee_delta_gripper` / Isaac | **No-Go**（维度与语义不匹配） |
| NG-2 | 跳过 Adapter 契约直接控 Isaac | **No-Go**（违反三仓与 Gate V3 前门禁） |
| NG-3 | 本轮下载 6B 权重或启动后训练 | **No-Go**（计划明确禁止） |
| NG-4 | 假定零样本 Panda pick-place 成功 | **No-Go**（无证据） |
| HOLD-1 | 本机小显存是否跑得动官方推理 | **No-Go（已实测）**：宿主机 `nvidia-smi` = **RTX PRO 500 Laptop / 6113 MiB**；见 [`VLA_GATE_V1_PREFLIGHT.md`](VLA_GATE_V1_PREFLIGHT.md) §0。公开示例偏 4090D |
| HOLD-2 | ~~55-D → `ee_delta`「可逆映射」~~ | **已纠正**：该问题陈述错误。正确拆分为 channel selection / action semantics / execution conversion；见 [`VLA_GATE_V05_PANDA_ACTION_CONTRACT.md`](VLA_GATE_V05_PANDA_ACTION_CONTRACT.md)。**不得**把 55-D→`ee_delta_gripper` 当作简单或可逆映射 |
| HOLD-3 | 官方权重附加许可与第三方依赖 | **Hold** → 代码/HF 卡片声明 Apache-2.0（见 §6）；**未下载**权重包内逐文件复核仍待 Gate V1 |

**Gate V0 总判**：允许进入 **文档级** 规划与 Adapter 设计；**不允许**自动进入 Gate V1，除非人工确认显存/许可与映射假设。当前默认下一动作是 **Gate V0.5 动作/数据契约审计**（已完成文档），而非拉起 VLA 环境。

---

## 3. 与本仓执行栈的接入草图（不实现；V0.5 修订）

**错误草图（已废弃）**：把 55-D 直接「映射」成 `ee_delta_gripper[7]`。

**正确分层**：

```text
LingBot infer (55-D raw)
  → [1] canonical channel selection + pad/mask
  → [2] policy semantics (推荐 absolute EE xyz+xyzw + gripper_cmd)
  → semantic validation / denormalize target
  → [3] Execution Adapter: lookup measured state
        → convert absolute target to bounded incremental command
        → workspace/joint/gripper limits + watchdog + E-stop
  → Isaac execution
  → continuous GT  (only authority for task)
```

`ee_delta_gripper` 属于本仓 ACT/下游执行栈语义，**不是** LingBot canonical 输出的同义词。  
失败分栏必须区分：VLA 模型失败 / channel-semantics 失败 / Execution Adapter 失败 / 物理执行失败。

---

## 4. Gate V1–V3 提醒（本文件不授权执行）

| Gate | 本文件授权？ |
|---|---|
| V1 官方环境复现 | **否**（需单独批准 + 合适硬件） |
| V2 Panda open-loop | **否** |
| V3 有界 Isaac rollout | **否** |

---

## 5. 验收

- [x] 只读矩阵与 No-Go/Hold 成文
- [x] 未下载权重、未改训练、未跑 Isaac VLA
- [x] 登记于 `THREE_REPO_CANONICAL_FACTS.md`

---

## 6. V0 / V0.5 只读补强（2026-07-21，仍不下权重）

| 项 | 证据 | 结论 |
|---|---|---|
| 官方代码 LICENSE | GitHub `LICENSE` = **Apache-2.0**（全文） | **已确认（代码）** |
| HF 权重卡片许可声明 | `robbyant/lingbot-vla-v2-6b` README「License Agreement」写 **Apache-2.0**；API `tags` **无**显式 `license:*`；siblings **无**独立权重附加 LICENSE 文件名 | **声明层 OK**；**未下载** safetensors 包内嵌条款 → HOLD-3 **仍保持**（Gate V1 前逐文件复核） |
| 公开 `configs/robot_configs/` | 仅 **`robotwin.yaml`**、**`agilex_cobot_magic.yaml`**（GitHub contents API，2026-07-21） | **无 Franka/Panda yaml** |
| robotwin 动作语义 | `action.arm.position` 切片 0:6 + 7:13，`subtract_state: False`（**绝对关节**）；effector 切片 6/13 | **关节空间**，与本仓方案 B（absolute EEF）**张力大** → 若官方强制该路径，可能需回退评估方案 A |
| agilex 动作语义 | `action.arm.position` `subtract_state: true`（**关节增量**）；effector `subtract_state: false` | 进一步说明公开样例偏 **joint**，不是 EE pose |
| 55-D 左右臂 / quat | README 公开分段仍为草案依据；公开 robot_config **未**给出 EE quat 顺序或 Franka 切片 | **左右臂顺序、quat wxyz/xyzw、gripper 双通道：仍未验证**；本仓导出继续假定 **xyzw**（与 `recorder_node._pose_vec` 一致） |

**对 Gate 的影响**：

- Gate V0 结论不变：可做契约/fixture，**不可**自动进 V1。
- Gate V0.5 方案 B 仍是本仓推荐默认，但必须在 V1 人工确认「是否允许自研 Panda EE robot_config」；否则可能被迫对齐官方 joint 样例。
- **仍禁止**：下载 6B 权重、改 evidence、声称可零样本控 Panda。
