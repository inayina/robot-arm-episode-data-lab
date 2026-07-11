# 项目演进路线图：从线性 Baseline 到云端分布式具身智能

在实际的项目落地和技术面试中，面试官非常看重候选人对**系统级演进能力（System Scalability）**和**算法升级路线（Algorithm Roadmap）**的思考。当前项目的第一阶段采用了极简的线性模型以快速打通工程闭环，但其长线设计包含了向深度模仿学习与云端分布式计算的过渡。

---

## 1. 数据与模型的分级演进（Model Evolution）

当前项目的数据与模型开发分为四个清晰的梯队，逐步从低算力、重工程验证的 Baseline 演进到高算力、重感知决策的具身策略：

```text
L1: Linear Smoke Baseline (NumPy Only) ── 验证三仓数据与控制闭环 (当前主线)
  ↓
L2: MLP Behavior Cloning (PyTorch) ── 验证多层感知器的拟合能力 (已留出接口)
  ↓
L3: Action Chunking with Transformers (ACT) ── 引入时序注意力机制 (50+ 演示数据)
  ↓
L4: Diffusion Policy ── 引入多模态行为分布的去噪扩散策略 (100+ 演示数据)
```

### 1.1 为什么第一阶段坚持使用 `linear_smoke` 策略？
在面试中，面对面试官关于“为什么你的模型用的是线性回归，而不是大模型”的提问，你的标准高分回答如下：
* **工程第一原则**：在涉及上游 MuJoCo 仿真、中游 LeRobot 适配、下游 PyBullet 验证的多仓大型分布式系统中，第一步绝不能直接上大深度模型。大模型的训练缓慢、Bug 多且难以调试，会掩盖底层的**坐标系偏差、控制频率不匹配和总线丢包问题**。
* **极简闭环验证**：`linear_smoke`（[linear_policy.py](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/training/policies/linear_policy.py)）是一个 NumPy 实现的纯线性策略，执行时间不到 1 秒。它能在零算力成本下，快速验证 `raw episode -> adapter -> training -> handoff -> PyBullet replay` 的全链路控制数据流是否完全畅通，属于典型的**“工程除噪（Engineering De-noising）”**。

---

## 2. 规范化数据集划分设计（Train / Test Split Design）

为了防止模型产生过拟合（Overfitting）并客观评估策略在泛化（Generalization）任务上的表现，数据集的划分必须遵循严格的物理边界：

### 2.1 核心设计：基于 Episode 级别划分（Episode-level Split）
* **错误的做法**：在时序数据中，如果直接将所有帧（Frames）打散（Shuffle）并按 80/20 比例划分，会导致严重的**信息泄漏（Information Leakage）**。因为同一条轨迹中相邻两帧（间隔仅 10ms-30ms）的关节角度和图像是高度相关的，模型只需“记住”相邻帧就能在测试集上取得极高的虚假准确率。
* **正确的做法（本项目设计）**：必须以 **Episode（独立回放轨迹）** 为最小划分单元。
  * 假定采集了 100 条抓取轨迹，我们将 `episode_000` 到 `episode_079`（80%）划入训练集，`episode_080` 到 `episode_099`（20%）划入测试/验证集。
  * 这样能保证测试集中的轨迹对于神经网络而言是**完全陌生、从未见过**的，从而能真实评估策略在遭遇初始位姿偏差时的泛化校正能力。
* **实施位置**：这一划分逻辑将实现在中游的 [inspect_dataset.py](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/training/scripts/inspect_dataset.py) 与 `prepare_dataset_release.py` 中，通过在导出的 `manifest.json` 中标记每个 episode 的 `split = "train" | "val"` 来实现。

---

## 3. 云端分布式批量采集与训练架构（Cloud Scaling）

为了让模型从“线性学习”跃升到“深度学习”（如 ACT/Diffusion），数据量必须从数十条扩大到数千条（$10^4$ 级别）。这需要将仿真采集和训练管道搬上云端（如阿里云、AWS）：

```text
                  ┌──────────────────────────────────────────────┐
                  │          Kubernetes (K8s) Cluster            │
                  │  ┌──────────────┐          ┌──────────────┐  │
[Task Queue] ────>│  │ batch_gen #1 │   ...    │ batch_gen #N │  │ (headless MuJoCo)
                  │  └──────┬───────┘          └──────┬───────┘  │
                  └─────────┼─────────────────────────┼──────────┘
                            ▼                         ▼
                  ┌──────────────────────────────────────────────┐
                  │        Cloud Object Storage (S3 / OSS)       │
                  │  - episodes/train/    - manifest.json        │
                  └─────────────────────┬────────────────────────┘
                                        ▼
                  ┌──────────────────────────────────────────────┐
                  │          GPU Training Cluster (Ray)          │
                  │  ┌──────────────┐          ┌──────────────┐  │
                  │  │ GPU Node #1  │   ...    │ GPU Node #M  │  │ (ACT / Diffusion)
                  │  └──────────────┘          └──────────────┘  │
                  └──────────────────────────────────────────────┘
```

### 3.1 云端并行批量采集（Cloud heads-up Batch Collection）
* **无头渲染组件 (Headless Container)**：MuJoCo 仿真器通过容器化（Docker），使用 EGL 驱动进行 GPU 硬件加速的“无头（Headless）”画面渲染，去除 GUI 桌面依赖，封装为轻量级容器镜像。
* **分布式容器调度 (K8s Jobs & Celery)**：
  * 在工控机端或云端发起批量采集任务，下发 10,000 次不同物体初始位姿的采集命令到消息队列（如 Celery + Redis/RabbitMQ）。
  * 云端 Kubernetes (K8s) 集群根据算力资源，动态拉起 100 个 `batch_generator` 容器实例并行运行，每个容器独立运行 MuJoCo 并高频调用启发式专家控制算法。
  * **效率估算**：单个容器采集一条 20 秒的轨迹仅需 1 分钟；100 个容器并发运行，可在 **2 小时内轻松产出 10,000 条高质量专家轨迹数据集**。

### 3.2 云端存储同步（Object Storage Sync）
* 每个采集实例在完成一个 Episode 且通过“末端跟踪误差门禁”校验后，自动将数据落盘并调用 SDK，增量上传到云端对象存储（如 AWS S3 或阿里云 OSS），并自动更新全局 `manifest.json`。

### 3.3 分布式 GPU 深度学习训练（Distributed GPU Training）
* **数据分发**：训练节点（如配置了 8 张 NVIDIA H100 显卡的 GPU 实例）通过高速文件挂载或数据预缓存，直接从 S3 读取落盘的 LeRobot/HDF5 数据集。
* **分布式训练框架 (PyTorch DDP / Ray Train)**：
  * 废弃单机 NumPy 训练，改用 PyTorch 的 **DistributedDataParallel (DDP)** 或 **Ray Train** 框架。
  * 将大模型（ACT 的 Transformer Encoder-Decoder 结构，或 Diffusion Policy 的 Unet/1D CNN）的权重分发到 8 张显卡上进行数据并行训练（Data Parallelism），利用 WandB 进行在线实验指标追踪，产出高泛化率的深度模仿学习策略模型（Checkpoint）。
