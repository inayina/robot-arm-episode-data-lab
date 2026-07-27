<div align="right">

[中文](#中文) | [English](#english)

</div>

# robot-arm-episode-data-lab

[![CI](https://github.com/inayina/robot-arm-episode-data-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/inayina/robot-arm-episode-data-lab/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Robot](https://img.shields.io/badge/Robot-Franka%20Panda-0f766e)
![Role](https://img.shields.io/badge/Role-Midstream%20data%20%26%20evaluation-2563eb)

## 中文

训练机器人策略并不难展示，难的是回答三个更实际的问题：数据能不能信、接口有没有悄悄变化、离线指标变好后机器人是否真的完成了任务。

这个仓库专门处理这些问题。它位于 Panda 三仓系统的中间，把上游采集的专家 episode 变成有明确语义、可以追溯的数据 release，组织训练和离线评测，再把模型输出交给运行与验证系统。它更像整套系统的“实验中枢”，而不是单纯的训练脚本集合。

> 当前最重要的结论：数据和接口链路已经贯通；SmolVLA Recovery v3 通过了独立数据上的 open-loop Gate，但在有界 Isaac 闭环中 lift 仍为 0/5，因此结论是 **Hold**，不是任务成功。

### 为什么要拆成三个仓库

机器人实验里，采集、训练和执行如果混在一起，很容易出现职责重复或结论越级。这里将它们拆成一条清晰的数据链：

```text
上游：让 Panda 运动、采集 episode、给出物理任务真值
  ros2-arm-teleoperation-suite
                  │ raw episode + meta.json
                  ▼
中游：定义合同、整理数据、训练、离线评测、打包 handoff
  robot-arm-episode-data-lab（本仓）
                  │ checkpoint / actions / reports
                  ▼
下游：重放动作、观察分布与风险、关联运行时状态
  ros2-moveit-pybullet-bridge
```

上游回答“机器人和仿真发生了什么”，本仓回答“数据与策略结果是否可信”，下游回答“交付物能否被安全地重放和观测”。完整边界见 [三仓边界说明](docs/portfolio/BOUNDARY_FREEZE.md)。

### 一条 episode 在这里经历什么

1. **适配**：把上游字段转换成固定的 Panda state/action 语义。
2. **检查**：验证 schema、图像、轨迹健康度和训练 split；不重复推导上游已经判断过的物理成败。
3. **发布**：生成不可覆盖的 release；需要严格复现时，再使用带逐文件 SHA、split 和 fingerprint 的 immutable release。
4. **训练与审计**：训练 MLP BC、ACT 或 SmolVLA，并核对 checkpoint 实际使用的 state、camera、action、chunk 和 PEFT 配置。
5. **分层评测**：把 Data、Offline、Interface、Behavior、Task、System 六层分开，避免把 interface Pass 写成任务成功。
6. **交接**：导出与训练框架解耦的 handoff，供下游 replay harness 使用。

### 这个项目现在做到哪里

- 三仓数据、handoff 和纯 CPU 合同检查已经贯通。
- Release 分成普通 non-overwrite 与 SHA-locked immutable 两种，不再混用术语。
- SmolVLA Recovery v3 在 10 条独立 prospective episode、2,593 帧上的 canonical first-action Gate 为 **Pass**。
- 同一策略在修光后的 bounded Isaac S4 中 interface 5/5，但 reach 1/5、grasp 0/5、lift 0/5，因此保持 **Hold**。
- Scripted oracle 在同一物理链上 lift 5/5，说明物理链能够完成任务，但不能据此声称 learned policy 成功。
- Policy Runtime、Risk 和 HOC 是这条数据链的验证配套；SmolVLA authoritative cutover 仍未启用。

这些状态只表示当前证据边界：**Not task success / Not Sim2Real / Not real robot**。

### 从哪里开始

如果你只是想快速理解项目：

- [作品集母版](docs/portfolio/PORTFOLIO_REFERENCE.md)：5 分钟理解价值，30 分钟展开技术讨论。
- [架构图](docs/portfolio/portfolio_system_overview.svg)：三仓关系、我的职责和当前结论。
- [作品集入口](docs/portfolio/README.md)：面试与公开材料的精简导航。

如果你要阅读或开发代码：

```bash
# 查看数据检查入口
python3 training/scripts/inspect_dataset.py --help

# 在三个仓库都位于标准本机路径时，强制核对跨仓合同
python3 scripts/run_three_repo_contract_ci.py --require-cross-repo

# 运行中游主线测试
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  --ignore=tests/test_collect_integration.py \
  --ignore=tests/test_grasp.py \
  --ignore=tests/test_gripper.py \
  --ignore=tests/test_validate_dataset.py
```

如果你已有一批上游 Panda episode，可从这些入口继续：

```text
training/scripts/adapt_upstream_panda_dataset.py   字段与动作语义适配
training/scripts/inspect_dataset.py                数据和 split 检查
training/scripts/prepare_dataset_release.py        普通 non-overwrite release
training/scripts/prepare_smolvla_s3_release.py     SHA-locked immutable release
training/scripts/prepare_bridge_handoff.py         下游 handoff
```

### 目录怎么读

| 目录 | 主要内容 |
| --- | --- |
| `configs/` | Panda schema、训练、Gate 与 runtime 合同 |
| `training/adapters/` | 上游 episode 到训练语义的转换 |
| `training/scripts/` | 检查、release、训练、评测与 handoff 入口 |
| `training/smolvla_s3/` | SmolVLA Recovery 的控制面、open-loop 与 runtime 合同 |
| `evaluation/` | 跨后端报告 schema、统计解释和 fixture |
| `project_knowledge/` | 三仓事实检索、审计和影响分析 |
| `docs/portfolio/` | 对外总结、失败归因与最小公开证据包 |
| `scripts/` | 三仓闭环与合同检查入口 |

### 项目刻意不做什么

- 不在中游启动 ROS 2 实时控制或重新判断物理抓取成功。
- 不把 offline loss、open-loop Pass、interface Pass 或 `ran_isaac=true` 当作任务成功率。
- 不声称已经完成真实机械臂部署、Sim2Real 或稳定在线自主抓取。
- 不因一次 Hold 自动扩种子、重训或增加新的 Gate。

`agents/`、`core/` 和早期 KUKA/PyBullet 内容属于 Legacy，不与当前 Panda 主线混用，见 [archive/README.md](archive/README.md)。

### 进一步阅读

- [三仓边界与统一术语](docs/portfolio/BOUNDARY_FREEZE.md)
- [数据/策略/系统失败归因](docs/portfolio/BADCASE_ATTRIBUTION_SUMMARY.md)
- [最小公开证据包](docs/portfolio/public_evidence/canonical_v3/README.md)
- [完整文档索引](docs/README.md)
- [项目 Agent 与事实检索规范](AGENTS.md)

## English

This repository is the experimental hub in a three-repo Franka Panda system. It turns upstream expert episodes into explicit data contracts and reproducible releases, coordinates training and offline evaluation, and exports framework-neutral handoffs for downstream replay and risk inspection.

The project is built around one rule: a clean interface or a good offline metric is not task success. Recovery v3 currently passes its prospective open-loop gate but remains **Hold** in bounded Isaac evaluation with lift 0/5. This is not a real-robot or completed Sim2Real claim.

Start with the [portfolio master](docs/portfolio/PORTFOLIO_REFERENCE.md), the [human-readable architecture](docs/portfolio/portfolio_system_overview.svg), or the [portfolio index](docs/portfolio/README.md).
