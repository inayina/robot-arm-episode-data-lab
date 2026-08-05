# 技术面试文档包

**目标**：证明候选人不仅“跑过 demo”，而且能独立解释系统边界、代码链路、控制与通信原理、实验口径和故障定位。  
**适用岗位**：机器人软件、系统验证、算法测试、仿真评测、控制/集成、具身数据与评测工程。  
**不负责**：客户商业方案、科研 novelty 包装。  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[三轨总导航](../README.md)

---

## 1. 本轨道唯一主线

> **我把一个机器人学习 demo 做成了可排查、可验证的软硬件系统，并能沿感知 → ROS 2 → 数据/模型 → 动作 → 控制/物理 → Task GT 六层定位失败。**

技术面试不从“模型指标很高”开始，而从以下三点开始：

1. 三仓为何按事实所有权拆分；
2. 策略动作如何穿过合同、scheduler、execution adapter、控制器和安全链；
3. 为什么 interface Pass、system health 和 Task success 必须分开。

---

## 2. 推荐阅读顺序

| 顺序 | 材料 | 读到什么程度 |
|---|---|---|
| 1 | [../../PORTFOLIO_REFERENCE.md](../../PORTFOLIO_REFERENCE.md) | 能做 30 秒和 5 分钟系统介绍 |
| 2 | [../../BOUNDARY_FREEZE.md](../../BOUNDARY_FREEZE.md) | 能准确说出三仓所有权和禁止越界项 |
| 3 | [../../BADCASE_ATTRIBUTION_SUMMARY.md](../../BADCASE_ATTRIBUTION_SUMMARY.md) | 能完整讲一次同 seeds 反证和 failure attribution |
| 4 | [../../resume_description.md](../../resume_description.md) | 选择 A（验证）或 C（仿真）版本，不拼接 B 的数据岗位叙事 |
| 5 | [../../../POLICY_RUNTIME_INTEGRATION_SPEC.md](../../../POLICY_RUNTIME_INTEGRATION_SPEC.md) | 能画出 Brain / Scheduler / Execution / Safety / Task GT |
| 6 | [../../POLICY_RUNTIME_M6_WIRING_RESULTS.md](../../POLICY_RUNTIME_M6_WIRING_RESULTS.md) | 能解释 R0/R2/R3 wiring 证明了什么、没证明什么 |
| 7 | 下游 `docs/portfolio/INTERVIEW_PREP.md` | 按 §4 的 current 章节选读，不从头背诵 |

下游知识库位置：仓库 `ros2-moveit-pybullet-bridge` 的 `docs/portfolio/INTERVIEW_PREP.md`（本机路径 `/home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge/docs/portfolio/INTERVIEW_PREP.md`）。

---

## 3. 技术专题矩阵

每个专题都要准备“一句话原理 → 项目代码事实 → 验证方法 → 当前缺口”四段回答。

| 专题 | 必答问题 | 项目证据入口 |
|---|---|---|
| 三仓架构 | 为什么不是单仓？为什么 Task GT 只在上游？ | `BOUNDARY_FREEZE.md` §2 |
| 数据合同 | `state[15]`、`action[8]`、ACT delta[7] 如何区分？ | `THREE_REPO_CANONICAL_FACTS.md`、Panda action contract |
| Release | non-overwrite 与 immutable 有何差异？如何防 split 泄漏？ | `BOUNDARY_FREEZE.md` §3、Recovery audit |
| 模仿学习 | 为什么 offline first-action Pass 仍会 closed-loop Hold？ | `FINAL_PROJECT_SUMMARY.md` §4–5 |
| Action chunk | chunk10/K5、canonical H=1、queued diagnostic 分别回答什么？ | `SMOLVLA_V3_EVAL_SOP.md`、queue bench |
| 控制 | MoveIt Servo、阻抗控制、`ros2_control` 如何分工？ | 上游代码与 `PORTFOLIO_REFERENCE.md` |
| 实时性 | 为什么真机开 FIFO、仿真禁 FIFO？奈奎斯特为何不等于无 jitter？ | 下游面试知识库 §32 |
| ROS 2 / DDS | QoS、executor、callback group、latest-value 如何降低长尾？ | M6 results、下游 FAQ |
| 总线与安全 | EMCY、watchdog、DS402 Quick Stop、物理 E-stop 有何边界？ | 下游面试知识库 §32 |
| 故障归因 | 如何排除物理链、相机、接口和 state 编码？ | `BADCASE_ATTRIBUTION_SUMMARY.md` |
| 统计 | 0/5 与 5/5 为什么不能直接外推？ | `FINAL_PROJECT_SUMMARY.md` §4.0 |
| 系统边界 | mock、fixture、replay、Hardware Pending 如何表述？ | `BOUNDARY_FREEZE.md`、M6 results |

---

## 4. 下游面试知识库使用规则

`INTERVIEW_PREP.md` 是大型 FAQ 库，不是从第一页顺序背诵的统一项目陈述。

### 4.1 优先使用的 current 章节

- §24–§30：Policy Runtime、Risk、HOC、trace replay 与 M6 wiring；
- §31：VLA、数据治理与分层验证；
- §32：非确定性时延、FIFO、总线、安全链、CPU/GPU 与传感器；
- 控制、ROS 2、CANopen 等原理章节：只在核对“对应项目代码事实”后使用。

### 4.2 不直接复用的旧口径

- 文件开头旧版三仓自我介绍；
- 把仿真主线统一说成 1 kHz；当前应区分 sim 500 Hz 与 real-path 1 kHz 配置；
- 把 grasp assist 当作训练数据常规方案；训练数据必须 `grasp_assist_enabled:=false`；
- 把下游 replay、risk 或 HOC 写成任务成功判定；
- 把 Legacy PyBullet/KUKA 的 RRT、FSM 或 action 语义混入 Panda 主线；
- 把 Hardware Pending 的 PREEMPT_RT、实体 EMCY、Bus-Off 或真机标定写成已验收。

若 FAQ 与当前代码/测试冲突，先更新 FAQ 的项目事实，再用于面试。

---

## 5. 三档回答模板

### 30 秒

只回答：项目定位、我的职责、一个最强证据、当前边界。

### 2 分钟

固定结构：问题 → 三仓架构 → 六层验证 → Badcase → 当前 Hold/边界。

### 10 分钟

固定结构：

1. 画三仓与控制/安全链；
2. 解释一个数据/action 合同；
3. 展开 offline Pass / closed-loop Hold；
4. 用 oracle 和同 seeds 复测讲故障归因；
5. 说明下一最小实验和停止条件。

---

## 6. STAR 案例只保留三组

| 案例 | 技术信号 | 权威材料 |
|---|---|---|
| evaluator command/state 混淆 | 先验证测试器，再评价被测对象 | `resume_description.md` §A.4 |
| scripted oracle v1 失败 → v2b 5/5 | 用系统上界隔离物理链 | `E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md` |
| 近黑 reach 3/5 → 修光 1/5 | 主动证伪自己的正向结果 | `BADCASE_ATTRIBUTION_SUMMARY.md` |

不要同时讲五六个浅案例；追问时再进入 split 泄漏、state[15] 或 queue latency。

---

## 7. 技术面试 readiness

| ID | 自检项 | Pass 标准 |
|---|---|---|
| TI-AC-01 | 系统图 | 5 分钟内手画三仓、控制和安全反馈 |
| TI-AC-02 | 代码锚点 | 每个核心模块至少能指出一个类/函数/配置 |
| TI-AC-03 | 原理 | 不看文档解释 BC shift、阻抗、QoS、FIFO 与 E-stop 边界 |
| TI-AC-04 | 证据 | 所有实验数字能追到 canonical JSON/文档 |
| TI-AC-05 | 边界 | 不混淆 sim/real、replay/closed-loop、system/task |
| TI-AC-06 | 排障 | 能从现象提出分层假设、验证顺序和停止条件 |
| TI-AC-07 | 修改能力 | 至少一个核心模块达到“能改并通过测试”而非只会讲 |

---

## 8. 本轨道交付清单

- 技术简历：使用 `resume_description.md` A 或 C 版本；
- 30 秒 / 2 分钟 / 10 分钟讲稿；
- 20 个岗位定制必答题；
- 3 个 STAR；
- 一张可手画系统图；
- 一份 code-anchor cheat sheet；
- 两轮录屏 mock interview 与复盘。
