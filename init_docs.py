"""Generate project-facing design and agent specification documents."""

from pathlib import Path


DESIGN_CONTENT = """# 轻量化机械臂闭环仿真平台 - 系统设计文档 (design.md)

## 1. 项目定位与核心原则

* **轻量高效**：基于 PyBullet 的纯 Python 单体架构，摆脱复杂的 ROS 通信配置，实现零 DDS 网络开销，环境 10 秒内快速启动。
* **算法解耦**：专注于核心运动学（IK）、路径规划（RRT）以及抓取逻辑的开发，提供极高的调试效率。
* **数据闭环**：原生设计端到端的数据流，每一步动作（Action）与状态（State）均按帧严格对齐并落盘，无缝对接实验看板与下游模仿学习框架（如 LeRobot）。

---

## 2. 系统架构（三层分层设计）

```text
┌──────────────────────────────────────────────────────┐
│                   应用层 (Apps)                       │
│   run_pick_place.py  │  batch_collect.py  │  demo     │
├──────────────────────────────────────────────────────┤
│                   核心层 (Core)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐   │
│  │ Planner  │ │   IK     │ │  RRT     │ │Gripper │   │
│  │(轨迹插补)│ │(运动学)  │ │(避障)    │ │(抓取)  │   │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘   │
├──────────────────────────────────────────────────────┤
│                   接口层 (HAL)                        │
│            RobotControl 抽象基类                      │
│   ┌──────────────┐    ┌──────────────┐               │
│   │ PyBulletRobot│    │  RealRobot   │ (物理真机预留)│
│   └──────────────┘    └──────────────┘               │
├──────────────────────────────────────────────────────┤
│                   数据层 (Data)                       │
│   Episode 格式: images/ + states.npy + actions.npy    │
│   + metadata.json (包含语言指令与 success 标签)        │
└──────────────────────────────────────────────────────┘
```

## 3. 关键模块详细设计

### 3.1 硬件抽象层 (HAL)

通过 `RobotControl` 抽象基类，将机械臂的底层控制（如角度读写、末端位姿获取）进行标准化封装：

* 仿真环境直接对接 PyBullet 的引擎接口。
* 真实硬件迁移时，上层算法无需变动，仅需继承该基类并实现对应的真机驱动接口，实现高度的软硬件解耦。

### 3.2 数据链路层与对齐规范

每个采集周期（Episode）均包含以下结构，确保多模态数据流的时间戳严格对齐：

* `images/`：按帧保存的 RGB/RGB-D 图像。
* `states.npy`：包含当前帧的关节角度（Joint Angles）与末端位姿（EE Pose）。
* `actions.npy`：记录控制器下发的下一步控制目标（Joint/Cartesian Target）。
* `metadata.json`：存储全局元数据，包含语言指令（Language Instruction）、任务成功/失败标签（Success Label）以及详细的失败原因分类（Error Type）。

---

## 4. 10 天实施路线图

* **Phase 1 (Day 1-2)**：HAL 接口定义、带阻尼 IK 求解器与笛卡尔空间直线插补实现。
* **Phase 2 (Day 3-4)**：纯 Python 双向 RRT 避障算法编写与 PyBullet 碰撞检测集成。
* **Phase 3 (Day 5-6)**：夹爪控制优化与基于物理状态变化的自动化抓取验证。
* **Phase 4 (Day 7-8)**：批量数据自动化采集脚本编写与实验管理看板（Dashboard）对接。
* **Phase 5 (Day 9-10)**：转换为标准的 LeRobot / Hugging Face Datasets 格式并完成全链路跑通。
"""


AGENTS_CONTENT = """# 闭环仿真智能体系统规范 (AGENTS.md)

本系统采用松耦合的智能体/状态机设计架构，将复杂的“感知-规划-执行-评测”拆分为多个高内聚的虚拟 Agent 协同工作。

## 1. 智能体拓扑与职责划分

### 任务规划智能体 (Task Planning Agent)

* **职责**：负责高层状态调度（比如解析传入的语言指令 `"pick up the block"`），管理有限状态机（FSM）。
* **行为**：将复杂任务拆解为阶段性的目标位姿（如：接近目标 -> 下落 -> 闭合夹爪 -> 抬升 -> 移动至释放点）。

### 运动规划智能体 (Motion Planning Agent)

* **职责**：负责底层的路径生成与插值。
* **行为**：接收来自 Task Agent 的目标位姿，通过 RRT 算法计算无碰撞路径，并在笛卡尔空间进行直线插补，调用阻尼 IK 求解器转换为关节电机指令。

### 自动化评测智能体 (Evaluation / Critic Agent)

* **职责**：负责实时的物理环境监控、数据质量检查与结果标注。
* **行为**：
  1. 监控仿真运行状态，若发生剧烈碰撞或逆运动学奇异点死锁，触发安全拦截并中止当前 Episode。
  2. 抓取完成后，通过读取物体的 Z 轴变化量自动评估抓取是否成功。
  3. 仿真结束后自动将结果（包含成功率、耗时、模型版本）落盘，并生成可供可视化看板读取的结构化 JSON 报告。

---

## 2. 智能体数据交互协议

各个 Agent 之间通过标准的数据字典（Dict）进行状态传递，拒绝硬编码。在每一帧的 `stepSimulation` 中，评测 Agent 拥有最高优先级的“拦截和标注权”，从而保证最终落盘数据的纯净度与高质量。
"""


def write_document(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"[SUCCESS] 成功创建并写入 {path.name}")


def generate_docs() -> None:
    root = Path(__file__).resolve().parent
    write_document(root / "design.md", DESIGN_CONTENT)
    write_document(root / "AGENTS.md", AGENTS_CONTENT)


if __name__ == "__main__":
    generate_docs()
