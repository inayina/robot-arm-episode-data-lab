# Solution Brief：机器人策略上线前验证与风险治理

**版本**：v0.1  
**状态**：Current portfolio solution brief  
**日期**：2026-07-30  
**方案主语**：具身策略数据治理与分层验证框架  
**边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[解决方案架构文档包](README.md)

---

## 客户问题

机器人算法团队经常拥有一个“离线指标不错”的策略，却无法回答：

- 训练实际使用了哪些数据，评测集是否泄漏？
- observation/action、normalization、chunk 和执行频率是否一致？
- 动作完成下发后，物体是否真的被 reach、grasp、lift？
- 失败来自数据、模型、接口、物理链、相机还是安全系统？
- 下一笔 GPU、仿真或硬件投入能消除哪个不确定性？

如果没有分层证据，团队容易把 interface Pass 写成任务成功，把系统联调问题归咎于模型，或在尚未理解失败原因时继续扩数据、扩 seed 和重训。

---

## 解决方案

本方案把一个策略从 intake 到 handoff 拆成六层验收：

| 层 | 核心问题 | 典型产物 |
|---|---|---|
| Data | 数据、split、schema 与来源是否可信？ | inspection、release manifest、SHA、split report |
| Offline | 专家状态分布上的预测是否过线？ | metrics、open-loop gate |
| Interface | checkpoint、action adapter 和运行合同能否工作？ | config audit、replay、latency、clip report |
| Behavior | EE、夹爪、时序和动作饱和是否合理？ | phase/action trace、behavior tag |
| Task | 仿真中是否真的 reach/grasp/lift/place？ | continuous Task GT、bounded gate |
| System | QoS、deadline、risk、Hold/E-stop 与 cleanup 是否健康？ | system trace、risk status、wiring evidence |

六层状态独立保存，后层不得覆盖前层原始事实。Risk/Safety 可以 Hold 或 E-stop，但只有上游 continuous Task GT 能判定物理任务结果。

---

## 参考架构

```text
Policy / Data Intake
  → Contract & Provenance Preflight
  → Offline Evaluation
  → Neutral Handoff
  → Replay / Interface Smoke
  → Bounded Task Validation（需批准）
  → Risk & Failure Attribution
  → Unified Acceptance Report
```

三仓事实所有权：

- 上游：控制、采集、在线执行、Safety、Task GT；
- 中游：合同、数据、release、训练、离线评测、handoff；
- 下游：replay harness、monitor、risk、HOC 证据。

详细设计见 [REFERENCE_ARCHITECTURE.md](REFERENCE_ARCHITECTURE.md)。

---

## 已有证据

| 证据 | 当前事实 | 能证明 | 不能证明 |
|---|---|---|---|
| prospective open-loop | 10 episodes / 2,593 帧；EE `0.0253 m`、grip BA `0.9943`，Pass | expert-state first-action fit | 闭环任务成功 |
| bounded Isaac S4 | interface 5/5、reach 1/5、grasp/lift 0/5，Hold | 接口与连续 Task GT 分栏 | 真机或 Sim2Real |
| scripted oracle | 修复物理链后 lift 5/5 | 名义仿真链具备任务上界 | learned-policy 成功 |
| M6 wiring | R0 EXECUTED、R2 HELD、R3 ESTOPPED | ROS/DDS 接线和安全裁决 | 物理力矩归零或任务成功 |
| downstream replay | 1 episode / 1,105 telemetry rows；`is_closed_loop=false` | handoff 与 replay 接口复用 | 自主闭环抓取 |

权威路径见 [EVIDENCE_INDEX.md](../../EVIDENCE_INDEX.md)。

---

## 客户价值

本方案不承诺“模型一定成功”，而是帮助团队更早、更准确地回答：

1. 哪一层已经通过，哪一层仍然 Hold；
2. 哪些问题可在昂贵仿真/硬件前拦截；
3. 哪个实验能以最小成本排除最大不确定性；
4. 哪些结果可以对外声明，哪些不能；
5. 如何把 PoC 证据、风险和遗留项移交给下一团队。

建议 KPI（待客户项目实测）：首次接入耗时、preflight 拦截数、trace/provenance 完整率、failure-lane 定位耗时、被止损的 rollout/GPU 预算、报告自动生成覆盖率。

---

## 适用与不适用

**适用：**

- 已有 policy/checkpoint，需要验证数据、接口和仿真表现；
- 正在搭建机器人学习数据/评测流水线；
- 需要 replay、failure attribution、readiness 与审计证据；
- 需要在真机前建立分阶段验收。

**不适用：**

- 客户期望直接购买成功抓取模型；
- 客户要求当前即提供真实 Panda 驱动或安全认证；
- 客户需要已完成的多租户 SaaS、云 HA、IAM 或合规认证；
- 没有明确 task GT，却要求输出任务成功率。

---

## 交付路径

| 阶段 | 主要交付 | 决策 |
|---|---|---|
| Discovery | scope、assumptions、RACI、success criteria | 是否进入 PoC |
| Preflight | policy identity、schema、artifact hash、adapter mapping | Pass / invalid |
| PoC | offline/interface/system evidence | Pass / Hold / No-Go |
| Bounded validation | continuous Task GT（需另批） | Task Hold / Pass（仅该协议） |
| Handoff | unified report、known limitations、runbook | 是否进入下一阶段 |

默认作品集 PoC 使用 CPU/mock/replay 和冻结证据，不自动启动 GPU、ROS live、Isaac 或真实模型 authoritative cutover。

