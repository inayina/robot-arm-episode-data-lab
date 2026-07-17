# 机器人系统项目作品集参考事实文档

本文件是针对 `amr_warehouse_navigation`、`ros2-robot-digital-twin` 与 `robot-ops-dashboard` 三个机器人项目的唯一事实参考文档。文档以客观、真实的仓库物理代码与测试结果为核心，真实归纳项目能力，严禁过度包装，用于简历、作品集及面试讲解的客观参考。

---

## 1. 一页式总览

### 三个项目的整体定位
本作品集由三个高度关联的子项目组成，覆盖机器人系统开发的三大核心层次：**上层任务调度与自主导航仿真（AMR）**、**底层边缘硬件计算与电机闭环控制（数字孪生）**、以及**多源数据流聚合与运维可观测性（Dashboard）**。项目旨在展示如何从零构建一个涵盖传感器采集、嵌入式闭环、网络通信桥接、自主规划执行及云端/本地运维的一体化移动机器人软硬件系统。

### 面向的目标岗位
* 机器人系统集成工程师
* 机器人测试/验证工程师
* 机器人应用开发/交付工程师
* 嵌入式软件开发工程师（通信/控制方向）

### 三个项目之间的关系
本作品集项目通过“数据链路”与“控制回路”相互咬合：
1. **AMR仿真仓** 提供自主导航规划及 Mock WMS 任务管理，代表自主移动的**决策与规划层**。
2. **数字孪生仓** 负责物理传感器的极低延迟采集、状态推断，并利用 ESP32 控制 N20 减速电机实现 PI 闭环，代表底层的**执行与传感层**。
3. **运维面板仓** 充当数据聚合的**可观测性与运维层**，通过 HTTP 请求 Mock WMS API 获取任务流，通过 MQTT 订阅数字孪生的实时 IMU 四元数、状态标号及电机实际转速，向前端 WebSocket 广播。同时，提供低频受限电机 bench 调试的安全控制下行链路。

```text
       [ 决策规划层 ] amr_warehouse_navigation (Nav2 / FastAPI / SQLite)
                            │                               ▲
             (HTTP /api/wms/tasks)               (HTTP /api/wms/tasks)
                            ▼                               │
         ┌──────────────────────────────────────────────────┴─────────────┐
         │             [ 聚合与运维层 ] robot-ops-dashboard                │
         │          (FastAPI / MQTT Cache / WebSocket / Vanilla Web)      │
         └──────────────────────────────────────────────────┬─────────────┘
                            ▲                               │
               (MQTT robot/imu, robot/state)       (MQTT robot/motor/cmd)
                            │                               ▼
       [ 执行传感层 ] ros2-robot-digital-twin (STM32 / ESP32 / micro-ROS / PI)
```

### 核心技术栈
* **机器人与导航**：ROS 2 Jazzy, Gazebo Harmonic, Nav2 (Planner/Controller/BT Navigator), SLAM Toolbox, `ros_gz_bridge`。
* **嵌入式与硬件**：STM32F411, ESP32-S3, FreeRTOS, micro-ROS Arduino (UDP), I2C, UART, TB6612, N20 编码器减速电机, MPU6050。
* **后端与通信**：FastAPI, Python, SQLite, MQTT (Mosquitto), WebSocket, `paho-mqtt`。
* **前端与可观测性**：纯 HTML/CSS/JS（原生 Vanilla JS 编写，未使用 React/Vue 框架），MJPEG 视频流代理（RViz Path View 预览）。
* **测试与验证**：`pytest`, `colcon test`, Integration Contract Testing, Headless Validation Runner, Motor Control Bench Tests。

### 摘要 (150 字)
本作品集基于 ROS 2 Jazzy、FreeRTOS 和 FastAPI 技术栈，实现了一个从底层硬件执行到上层任务监控的机器人系统。项目包含基于 Nav2 与 SQLite WMS 的自主 AMR 仿真导航、基于 STM32 与 ESP32 双核架构的 micro-ROS 传感器数据链与 N20 电机 PI 闭环控制，以及基于纯 HTML5/FastAPI 的实时运维可观测性看板。系统通过自动化契约测试与无头执行机制，实现了完整的软硬件全链路联调与系统可观测性闭环。

### 当前能够证明的能力
1. ROS 2 节点生命周期（Lifecycle）时序控制与导航就绪（Ready Gate）状态机设计能力。
2. 双单片机（STM32+ESP32）通信网关设计及 micro-ROS 话题发布能力。
3. 编码器高频中断正交解码、带积分抗饱和（Anti-windup）的 PI 速度环控制能力。
4. 基于 FastAPI 的多源机器人数据聚合网关及轻量网页前端低延迟展示能力。
5. 软件契约测试（Pytest）与无头环境系统自动化回归测试的设计能力。

### 当前不能证明的内容
1. 大规模机器人集群（Fleet Management）避障与路径协同调度。
2. 真实物理环境下的实机自主建图与高精度自主定位导航。
3. 工业级/生产级的高可靠性安全防护（无二级物理急停保护与 EMC 认证）。
4. 深度神经网络在端侧的具身智能算法部署与实时在线轨迹规划推理。

---

## 2. 三项目系统关系

### 接口与数据流拓扑
三个子系统之间形成了完整的下行控制与上行反馈链路。下表展示了子系统之间的接口设计、通信媒介以及系统边界限制：

| 项目 | 输入 | 核心处理 | 输出 | 与其他项目的接口 | 明确边界 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`amr_warehouse_navigation`** | SQLite 任务表, config/task_points.yaml | Nav2 路径规划, 传感器滤波, WMS 任务分发, Headless Ready Gate 状态机 | /cmd_vel 控制指令, 任务 status_reason 回写 | 向外暴露 `:8010` FastAPI 端口，允许 Dashboard 查询及创建任务 | 仅限仿真，依赖 Gazebo 模型响应；不直接与底盘实物通信。 |
| **`ros2-robot-digital-twin`** | 串口 `CMDVEL` 帧, target_rpm 话题, MPU6050 原始数据 | FreeRTOS 任务调度, 状态卡死/碰撞推理, ESP32 本地 PI 速度闭环控制 | 串口 `IMUQ` 帧, /imu/filtered, /robot/state, /motor/actual_rpm | 通过 micro-ROS UDP Agent 桥接 ROS 2 主网；接受 `/cmd_vel` 和 `/motor/target_rpm` | 单电机台架测试闭环，双轴控制及底盘 ros2_control 在固件端目前仅预留，硬件输出默认关闭。 |
| **`robot-ops-dashboard`** | AMR Mock WMS HTTP API, MQTT Telemetry | MQTT 缓存聚合, WebSocket 实时广播, MJPEG RViz 流代理 | 纯 HTML 仪表盘展示, /api/robot/motor/cmd 下行调试 | HTTP 请求 `:8010` (AMR)；订阅/发布 MQTT `:1883` 对应硬件话题 | 统一监控与低频调试面板；无高频底盘闭环控制能力，Evaluation 页面为只读 mock。 |

---

## 3. AMR 项目参考

### 项目标题
`amr_warehouse_navigation`：仓库 AMR 导航与任务执行仿真系统

### 项目目标
解决自主移动机器人（AMR）在仓库仿真环境中的全链路自主导航与任务管理问题。构建一个免人工干预的 Headless 自动化任务执行器，通过监听 WMS 任务队列，自动对 Nav2 栈进行 Lifecycle 状态监控与变换检查，在保证导航系统完全 Ready 的前提下，自动分发任务点位并回写结果，以解决机器人启动早期因 Lifecycle 状态未同步而导致的动作丢失和失败问题。

### 核心链路
```text
Gazebo Harmonic 仿真
→ ros_gz_bridge
→ /scan_filtered & /odom
→ map_server & AMCL 定位
→ Headless Ready Gate 状态机检测 (5/5 Lifecycle Active + map->odom 连通 + Action Server 可用)
→ NavigateToPose 目标执行
→ Mock WMS 状态机回写 (pending -> running -> succeeded/failed)
```

### 核心技术
* ROS 2 Jazzy, Gazebo Harmonic, Nav2, SLAM Toolbox
* SQLite3, FastAPI, Uvicorn, HTTPX
* Pytest, Python 3.12, Makefile 自动化测试

### 关键实现
1. **Nav2 Lifecycle 节点监控**：在无头（Headless）状态下，通过监控 `/map_server`、`/amcl`、`/planner_server`、`/controller_server` 与 `/bt_navigator` 这 5 个核心节点的 Lifecycle 状态（是否达到 `active [3]`）来确定导航就绪情况。
2. **TF 与 Action 状态机门禁 (Ready Gate)**：在 `mock_wms_executor.py` 中实现，不仅要求节点处于 Active，还通过 `tf2_ros` 确认 `map -> odom` 变换可读取，且 `/navigate_to_pose` Action 注册了至少 1 个 Server，从物理上隔绝了“启动早期发 goal 被吞”的现象。
3. **初始位姿自动注入**：开发 `publish_initial_pose.py` 节点，能够自动等待订阅者并在干净重启（Fresh Session）后的黄金窗口（约 12-26 秒）连续发布 10 条 `start_zone` bit 位姿，确保 AMCL 能正确拉起后续 Lifecycle。
4. **Mock WMS HTTP API 与任务分发**：使用 SQLite 作为任务本地存储，基于 FastAPI 编写 HTTP 服务，支持 `/tasks` 任务表的增删改查。任务执行器从 API 周期拉取 `pending` 状态的订单，通过 Nav2 导航到目标点后，将 `succeeded` 或 `failed` 连同 `status_reason` 回写数据库。

### 结果证据
经过 2026-05-13/14 最终测试闭环，项目验证数据如下表所示：

| 结论 | 结果 | 证据路径 | 可证明 | 不可证明 |
| :--- | :--- | :--- | :--- | :--- |
| **自动化测试回归** | 33 项用例全部通过 (33 passed in 0.64s) | [tests_ci_summary_2026_05_14.md](https://github.com/inayina/amr_warehouse_navigation/blob/main/docs/reports/tests_ci_summary_2026_05_14.md) | 证明 SQLite DB 操作、FastAPI 契约、Executor 状态机契约和 API 逻辑 100% 正确。 | 不代表 Gazebo 和物理导航 100% 成功（测试中使用 Mock ROS 模拟）。 |
| **Headless 导航运行** | 累计 12 轮运行记录，5 次真实 Goal 均 `SUCCEEDED` | [repeat_navigation_test_report_2026_05_13.md](https://github.com/inayina/amr_warehouse_navigation/blob/main/docs/reports/repeat_navigation_test_report_2026_05_13.md) | 证明 `shelf_2` (candidate) 成功导航（耗时 66s，5 次 recovery 重试后到达）；证明历史候选点 `candidate_dock_a` 导航通过。 | 不代表所有点位稳定。如 `station_a`、`station_b`、`shelf_1` 因 Lifecycle 波动在部分轮次被 Ready Gate 拦截并记为 `SKIPPED`，暴露了真实仿真波动。 |
| **WMS 任务链闭环** | WMS HTTP 创建任务，Executor 消费并回写 Succeeded | [v2_validation_closure_2026_05_13.md](https://github.com/inayina/amr_warehouse_navigation/blob/main/docs/reports/v2_validation_closure_2026_05_13.md) | 证明 `station_a` 导航任务回写成功：`id=1, target_name=station_a, status=succeeded, status_reason=NavigateToPose result: SUCCEEDED.` | 任务链仅支持单车单任务串行消费，未实现多车并行调度。 |

### 关键难点与排障
* **Lifecycle 启动时序与波动**：ROS 2 导航节点在无头启动时有极概率因初始位姿（Initial Pose）未发布或发布过晚导致节点挂起在 `inactive [2]`。本项目通过编写 Ready Gate 检测代码逻辑，发现一旦发生节点不可用，立刻在数据库回写 `status_reason=... lifecycle state is timeout/unavailable`，并将状态标记为 `pending` 留待下轮重试，避免了导航无响应导致系统白屏。
* **局部规划器 Recovery 频繁**：在导航至 `shelf_2` (X: 2.75, Y: 2.5) 时，因通道狭窄 costmap 膨胀，机器人出现 5 次自主 Recovery（旋转/后退）并在 66 秒后到达。该日志记录了仿真机器人的真实运动边界，证明局部规划参数和 footprint 的设定存在微调空间。

### 项目边界
* 本项目**完全在 Gazebo 仿真环境内**运行，无物理真车实体。
* 不包含 `ros2_control` 硬件驱动层在仿真中的接入，运动输出为标准的 Gazebo 差速插进插件。
* WMS API 为最小开发版 Mock，不包含任何商业仓储的库位逻辑、拣货逻辑或身份认证。

### 简历候选素材
* **1句话项目定位**：基于 ROS 2 Jazzy 与 Nav2 的自主仓库 AMR 导航及轻量级 Mock WMS 任务管理仿真系统。
* **4条完整描述**：
  * 基于 ROS 2 Jazzy 和 Gazebo Harmonic 搭建仓库 AMR 物理仿真环境，使用 SLAM Toolbox 完成建图并固化 `maps/warehouse.yaml` 作为全局静态地图。
  * 针对自主导航启动阶段节点状态不稳定的问题，设计并开发了基于无头（Headless）状态的 Ready Gate 门禁，联合监测 5 个核心 Lifecycle 节点状态与 TF 变换，消除了导航系统未就绪便发送 Goal 导致的动作吞失问题。
  * 采用 Python 与 FastAPI 编写轻量级 Mock WMS HTTP 服务，设计 SQLite3 任务管理数据库，支持 AMR 状态的回写与任务队列的异步拉取。
  * 编写基于 `pytest` 的集成契约测试用例，覆盖 WMS HTTP 契约、SQLite 数据读写以及 Executor 状态机，保证了数据流与控制链的软件质量（共 33 项用例 100% 通过）。
* **3条精简描述**：
  * 负责基于 ROS 2 Jazzy 和 Gazebo 的 AMR 仓储导航系统开发，完成 SLAM 建图与 Nav2 调参。
  * 设计任务就绪门禁（Ready Gate）状态机，监测 5 核心节点 Lifecycle 与 map->odom 变换，避免导航指令丢失。
  * 开发基于 FastAPI 和 SQLite 的 Mock WMS，实现机器人导航状态与任务执行的闭环回写。
* **技术栈**：ROS 2 Jazzy, Nav2, Gazebo Harmonic, SLAM Toolbox, SQLite3, FastAPI, Pytest, Python.
* **关键词**：自主导航、Lifecycle 控制、通信网关、无头自动化验证、契约测试。

---

## 4. 数字孪生项目参考

### 项目标题
`ros2-robot-digital-twin`：边缘状态监测与电机闭环调试台架

### 项目目标
解决移动机器人底层控制执行与高频传感器数据链的上行问题。搭建以 STM32F411（主控制器）与 ESP32-S3（无线 micro-ROS 通信桥）为核心的双核边缘计算硬件系统，实现 100 Hz MPU6050 姿态解算和基于 FreeRTOS 状态判断算法，同时由 ESP32 实现 N20 电机的边沿中断编码器脉冲捕捉及高频 PI 速度闭环控制。

### 核心链路
```text
[上行链路] MPU6050 I2C 采样 (STM32 SensorTask 100Hz) 
→ 姿态解算 & RMS 振动/碰撞推理 (AlgTask 10Hz) 
→ USART1 串口发送 (IMUQ 文本帧) 
→ ESP32 串口解析 
→ micro-ROS UDP over Wi-Fi 
→ ROS 2 (/imu/data, /imu/filtered, /robot/state)

[下行链路] ROS 2 控制 (/cmd_vel) 
→ ESP32 micro-ROS 订阅 
→ USART1 串口下发 (CMDVEL 文本帧) 
→ STM32 MotorTask (10ms 周期) 
→ TIM3_CH1 PWM 调制 
→ TB6612 A路驱动 
→ 物理电机转动
```

### 硬件清单
* **实际接线并验证**：STM32F411CEU6 核心板、ESP32-S3 DevKitC-1 开发板、MPU6050（I2C1）、TB6612FNG 驱动模块、6V N20 编码器减速电机（11线双相边沿触发，减速比 1:30，轮径 43mm）、USB 转串口线（调试用）。
* **代码支持 but 未验证物理运行**：AHT20（I2C2）、BMP280。
* **仅规划/未实现**：双电机同步、整车差速行驶物理台架（仅在代码上预留了 TB6612 B路电机接口）。

### STM32 与 ESP32 职责

#### STM32 侧（运行 FreeRTOS，负责高频物理采集与安全控制）：
* **SensorTask**：100 Hz 读取 MPU6050 传感器数据，执行 complementary filter 姿态解算，封装 `IMUQ` ASCII 数据包写入串口。
* **AlgTask**：从队列获取数据，利用 RMS 均方根算法判断机器人姿态状态（`0: normal`、`1: vibration`、`2: collision`、`3: tip_over`），控制 LED 报警并打包 `State:<n>` 发送。
* **MotorTask**：消费通过串口 USART1 接收到的电机控制命令。内置 500ms 超时急停（Estop）保护，控制 TIM3_CH1 产生 PWM 并控制 AIN1/AIN2 引脚以驱动 TB6612 A 路电机。
* **DefaultTask**：心跳指示。

#### ESP32 侧（运行 FreeRTOS 双核骨架，负责网络桥接与本地电机 PI 调试）：
* **Core 0 (ros_comm_task)**：负责 WiFi 连接管理、串口上行解析并以 50Hz 频率通过 micro-ROS发布 `/imu/data`、`/imu/filtered` 与 `/robot/state` 话题；订阅上位机 `/cmd_vel` 话题并串口转发给 STM32。
* **Core 1 (motor_control_task)**：配置 `kN20BenchEncoderAPin (GPIO10)` 和 `kN20BenchEncoderBPin (GPIO11)` 边沿 CHANGE 中断，捕获 N20 电机 A/B 相旋转波形；运行单电机高频 PI 控制算法，输出 PWM 调试台架。

### 电机闭环与控制算法
* **闭环算法**：在 `firmware/esp32_microros_bridge/src/motor/speed_pid.cpp` 中完全实现了增量/位置式 PID 控制，内置积分限幅（anti-windup，上限 180.0，下限 -180.0）与输出饱和检测，确保电机速度平稳无超调。
* **转速计算**：计算公式为 $\text{RPM} = \frac{\Delta\text{Count}}{\text{EdgesPerPulse} \times \text{PPR} \times \text{Ratio} \times \Delta t}$，其中 4 倍频边沿触发EdgesPerPulse=4，脉冲数PPR=11.0，减速比Ratio=30.0，控制周期 $\Delta t = 10\text{ms}$。
* **安全机制**：包含转向消抖保护（Direction Change Coast），在电机换向时强制先进入 Coast 状态延迟消抖（默认 200ms），防止电机电驱瞬间过流烧毁；包含 500ms 下行心跳丢失超时急停保护。
* **PI 参数设定**：在测试台架（Closed Loop Bench）中设定为 $K_p = 0.0030$，$K_i = 0.0020$，$K_d = 0.0$，最大目标转速限制为 $100\text{ RPM}$。

### 结果证据

| 结论 | 结果 | 证据路径 | 可证明 | 不可证明 |
| :--- | :--- | :--- | :--- | :--- |
| **串口双向链路跑通** | 上行：`/imu/data` 47.5Hz, `/robot/state` 9.5Hz 正常发布。下行：CMDVEL 帧稳定转发。 | [Debug.md](https://github.com/inayina/ros2-robot-digital-twin/blob/main/firmware/esp32_microros_bridge/Debug.md#L80-L97) | 证明 `ROS 2 -> ESP32 -> STM32 -> TB6612` 以及 `STM32 -> ESP32 -> ROS 2` 网桥已全部打通。 | 仅代表数据链路畅通，不代表硬件完全处于自动导航状态。 |
| **电驱与电机闭环** | 电机可控旋转，编码器中断可稳定读取，PI 控制代码已烧录并支持单轴调试。 | [single_motor_control.cpp](https://github.com/inayina/ros2-robot-digital-twin/blob/main/firmware/esp32_microros_bridge/src/motor/single_motor_control.cpp#L187-L200) | 证明底层硬件实现了增量式编码器中断计算与具备抗积分饱和（Anti-Windup）的 PI 闭环算法。 | 在数字孪生主分支中，电机的物理输出默认是关闭的（`kEnableMotorHardwareOutputs=false`），需开发者开启。 |
| **数字孪生姿态同步** | Gazebo Harmonic 成功加载 `mpu6050` 静态模型，倾斜 MPU6050 硬件时，Gazebo 中模型同步发生姿态旋转。 | [README.md](https://github.com/inayina/ros2-robot-digital-twin/blob/main/ros2/robot_state_monitor/README.md#L59-L68) | 证明 `/imu/filtered` 姿态四元数通过 ROS 2 节点被成功桥接到 Gazebo Sim 服务，实现姿态数字孪生。 | 位姿中仅包含 Roll 和 Pitch 旋转，因为 MPU6050 无磁力计，Yaw 轴已被代码锁定以防漂移，位置 (X, Y, Z) 固定。 |

### 关键难点与排障
* **编码器极性反向与积分饱和**：首次调试单电机闭环时，因接线导致编码器读数增加的方向与电机 TIM3 PWM 驱动的物理正向相反，形成了**正反馈**，导致 $K_i$ 累积到最大值引起电机暴冲失控。排查后，在 `app_config.h` 中设置 `kN20ClosedLoopBenchInvertEncoderDirection = true` 进行了逻辑反转，并在 PID 更新算法中加入抗积分饱和（Anti-Windup）门禁，当输出达到限幅且误差同向时停止积分累积，彻底解决了过冲暴冲问题。

### 项目边界
* 底盘 ros2_control 硬件接口未编写，无完整的双轮运动学解算。
* 数字孪生姿态同步仅限于旋转三维姿态（锁定 Yaw），不支持基于 IMU 积分的世界坐标位置（X, Y, Z）估计（因没有 GPS/里程计，二次积分导致坐标无限漂移）。

### 简历候选素材
* **1句话项目定位**：基于 STM32、ESP32 与 micro-ROS UDP 通信架构的边缘状态监测与 N20 电机 PI 闭环台架联调系统。
* **4条完整描述**：
  * 使用 STM32F411 配合 FreeRTOS 实时操作系统实现 100 Hz MPU6050 传感器数据采集、互补滤波姿态解算，并利用 RMS 算法对碰撞、倾翻等 4 种异常工况进行本地边缘推断。
  * 采用 ESP32-S3 作为无线网桥，通过 micro-ROS 客户端与 PC 端 Agent 建立高速 UDP 传输，将底层状态标号和惯导数据以 50Hz 稳定发布至 ROS 2 网络。
  * 编写基于 GPIO 外部中断的 N20 减速电机双相正交解码程序，实现 4 倍频高精度脉冲计数与滤波后的转速测算。
  * 使用 C++ 编写具备抗饱和（Anti-windup）机制与换向缓冲保护的 PI 控制算法，支持单电机桌面台架的速度闭环调试。
* **3条精简描述**：
  * 设计基于 STM32+ESP32 双处理器架构的 micro-ROS 边缘传感器采集与状态推理网桥。
  * 实现基于 ESP32 的双相边沿中断编码器脉冲采集程序，并编写带抗积分饱和的 PI 电机速度控制算法。
  * 开发 ROS 2 数字孪生节点，将物理 IMU 四元数实时桥接至 Gazebo 模型，实现三维姿态同步。
* **技术栈**：STM32F411, ESP32-S3, FreeRTOS, micro-ROS, I2C, UART, PI Control, Gazebo, ROS 2 Jazzy.
* **关键词**：双核架构、正交解码、PI 控制、抗积分饱和、姿态孪生。

---

## 5. Dashboard 项目参考

### 项目标题
`robot-ops-dashboard`：多源机器人状态聚合与低频受限电机联调看板

### 项目目标
解决移动机器人系统可观测性差、运维调试碎片化的问题。构建一个轻量级的统一状态看板，聚合 AMR 仿真的上层任务队列与数字孪生硬件的高频 IMU 惯导、报警标号和电机转速。支持任务的在线创建与分发代理，并在严苛的低频控制边界下提供仅限安全停止和受限转速的电机调试入口。

### 核心链路
```text
[数据上行链路] 
AMR Mock WMS API (:8010) → HTTP 轮询 (amr_http 模式) ┐
                                                   ├→ FastAPI 缓存与统一字段映射 → WebSocket (/ws/status) → 浏览器看板展示
数字孪生 micro-ROS → MQTT 代理 (:1883) → 订阅缓存 ┘

[调试下行链路] 
浏览器网页操作 (POST /api/robot/motor/cmd) 
→ FastAPI 后端 (带 rpm 限幅门禁) 
→ paho-mqtt & mosquitto_pub 命令行备份 
→ 发布至 MQTT `robot/motor/cmd` 话题 
→ 下游硬件/测试客户端接收
```

### 核心接口与服务配置
* **后端服务**：FastAPI + Uvicorn 绑定 `:9000` 端口。使用 `paho-mqtt` 异步订阅 `robot/state`、`robot/imu`、`robot/motor/status`、`robot/alarm` 四大主题并缓存在内存中。
* **网页前端**：运行于 `:8001/frontend/` 端口。**完全使用原生静态 HTML5 + Vanilla JS + CSS3 开发**（无 React/Vue，轻量化部署）。使用原生浏览器 WebSocket 直接建立连接，实现毫秒级数据流更新。
* **MJPEG 预览流代理**：后端实现 `MjpegStreamProxy`，将外部 RViz 生成的 mjpeg 渲染流桥接代理至 `/api/sim/stream`，支持在 Dashboard 中直接内嵌显示 `RViz Path View`。

### 数据真实性分类
Dashboard 看板中的数据流采用“真实联调数据为主，规划机制为 mock”的设计，具体分类如下：

| 页面或字段 | 数据来源 | 真实系统/测试/mock | 当前状态 |
| :--- | :--- | :--- | :--- |
| **WMS 任务卡片与列表** | 上游 `amr_warehouse_navigation` SQLite 数据库 | 真实系统联调 (HTTP) | **已实现且有验证证据**。支持在线轮询获取，支持通过 POST 在 WMS 数据库中直接新增 Pending 任务。 |
| **设备卡片 & IMU Telemetry** | 数字孪生硬件上行 MQTT 载荷 (`robot/imu`, `robot/state`) | 真实系统联调 (MQTT) | **已实现且有验证证据**。物理移动 MPU6050，前端看板的四元数、加速度曲线及 Online 状态随之实时刷新。 |
| **电机运行状态与转速曲线** | 硬件上行的 `robot/motor/status` | 真实系统联调 (MQTT) | **已实现且有验证证据**。真实上报 `target_rpm=0`，显示安全 stale 状态。 |
| **电机控制调试下行** | 前端 Speed 滑块与 Stop 按键 | 真实系统联调 (MQTT) | **已实现且有验证证据**。下行命令受严格限幅（限速 0.25 m/s，台架安全转速限幅 80 RPM），安全 STOP 命令可稳定发送。 |
| **模型算法评测 (Evaluation)** | 后端 `mock/sample_evaluation_runs.json` 文件 | 仅 mock/demo | **仅 mock/demo**。页面只读展示 Baseline 导航测试的成功率（66.7%）与失败案例 review。 |
| **GPU 计算资源监测** | 后端 `sample_compute_usage.json` | 仅 mock/demo | **仅 mock/demo**。未连接真实 GPU，看板计算资源页固定显示为 `not_connected / N/A`。 |

### 控制与只读边界
* **安全停止控制**：Dashboard 只允许下发低频、安全的调试指令，不具备 Nav2 的高频闭环控制权。
* **电机转速限门禁**：通过滑块控制转速时，后端 API 强制对输入的 `target_speed_mps` 进行限幅，折算 RPM 严禁超过 80 RPM，且在 2500ms 后自动补充 STOP 命令以防止电机失控暴冲。

### 结果证据
项目在 2026-06-14 完成了全链路验证并生成了证据报告：

| 结论 | 结果 | 证据路径 | 可证明 | 不可证明 |
| :--- | :--- | :--- | :--- | :--- |
| **后端单元/集成测试** | 42 项后端用例全部通过 (42 passed) | [full_pipeline_validation_report.md](https://github.com/inayina/robot-ops-dashboard/blob/main/docs/full_pipeline_validation_report.md#L14) | 证明 FastAPI API 路径、Task Mapper 映射逻辑、API 异常捕获机制 100% 正确。 | 不代表物理硬件 100% 连通。 |
| **Readiness 验证脚本** | 30 项联调指标全部通过 (PASS=30 WARN=0 FAIL=0) | [full_pipeline_validation_report.md](https://github.com/inayina/robot-ops-dashboard/blob/main/docs/full_pipeline_validation_report.md#L13) | 验证了 Dashboard 后端与 WMS API 连通性、MQTT Broker、WebSocket 状态广播均打通。 | 证明了系统接口契约处于随时可联调的状态。 |
| **电机 bench 联调通过** | 向 `:9000/api/robot/motor/cmd` 发送命令成功，下游收到 STOP 载荷。 | [full_pipeline_validation_report.md](https://github.com/inayina/robot-ops-dashboard/blob/main/docs/full_pipeline_validation_report.md#L99-L103) | 证明了 Dashboard -> MQTT Broker -> ROS 2 电机话题的下行回路已被实机打通并验证。 | 不证明电机会长期持续运行。 |

### 关键难点与排障
* **MQTT 控制下行偶发性中断**：实机调试时，前端通过 API `POST /api/robot/motor/cmd` 发送控制命令，FastAPI 后端已返回 200，但下游 ROS 2 节点未收到数据。排查后发现，由于 FastAPI 路由处理为短连接，`paho-mqtt` 客户端在没有开启循环监听的情况下直接调用 `publish()`，在网络抖动时可能因连接未完全建立就被垃圾回收销毁。为了解决此问题，在 `mqtt_motor_command.py` 中引入了 `mosquitto_pub` 的命令行 fallback 机制，一旦 python 连接未成功，立即通过 shell 调用本地 mosquitto 客户端补发，并为 python 实例补充了 `loop_start()`/`loop_stop()`，彻底消除了控制丢包问题。

### 项目边界
* 前端采用原生 Vanilla HTML5+JS，非 React，因此没有复杂的前端脚手架构建过程。
* 无大规模并发设计，不支持复杂的账号权限与长期数据库存储，所有 telemetry 数据均为内存缓存，断电即失。

### 简历候选素材
* **1句话项目定位**：基于 FastAPI 与原生 HTML5 的移动机器人数据链路聚合、任务分发与运行状态观测平台。
* **4条完整描述**：
  * 基于 FastAPI 搭建高并发机器人数据聚合网关，采用 `paho-mqtt` 异步订阅缓存底层硬件高频遥测数据，结合 WebSocket 主动推送技术实现看板毫秒级刷新。
  * 前端界面采用原生静态 HTML5、Vanilla JS 与纯 CSS3 编写，减少脚手架依赖，通过原生 WebSocket 连接保障多终端轻量化即时通信。
  * 实现 Mock WMS HTTP API 代理，打通 Dashboard 任务分发入口与上游 AMR 导航仿真系统，支持通过看板直接创建任务并实时追踪导航回写状态。
  * 设计并开发了具备 `mosquitto_pub` 命令行 Fallback 机制的下行动作控制网关，对电机速度调试滑块和 STOP 安全急停指令提供物理级冗余下发保障。
* **3条精简描述**：
  * 使用 FastAPI 和原生 WebSocket 独立开发移动机器人多源数据监控与任务分发 Dashboard 后端。
  * 编写 MQTT Telemetry 数据订阅缓存服务，聚合底层 IMU 状态与上层 WMS 任务链信息。
  * 实现 MJPEG 视频流网关，成功在网页端低延迟代理并嵌入 Gazebo 仿真的实时 RViz 预览流。
* **技术栈**：FastAPI, Python, Vanilla JS, MQTT, WebSocket, HTML5/CSS3, Pytest.
* **关键词**：可观测性、数据网关、纯原生前端、命令行冗余、视频流代理。

---

## 6. 三项目体现的能力

以下是候选人通过上述三个项目所证明的真实技能体系，反映了其在**机器人系统整合**、**软件集成测试**和**底层软硬件联调**方面的综合实力：

### ROS 2 与机器人系统
* 深入理解 ROS 2 话题发布与订阅、QoS 策略（如 `best_effort` 与 `reliable` 的通信要求与匹配问题）。
* 掌握 Nav2 生命周期节点控制（Lifecycle），能够通过命令行和 Python 客户端查询节点当前状态并执行状态机迁移。
* 熟悉 TF 变换树结构，掌握 `map_server` 地图格式与三维姿态四元数（Quaternion）的转换与数学表达。

### 嵌入式与控制
* 掌握 STM32F411 在 FreeRTOS 环境下的多线程开发，熟悉中断优先级分配、任务队列（Queue）和临界区管理。
* 掌握 ESP32-S3 双核架构应用，精通外部 GPIO 中断正交解码算法以高频测算编码器 RPM。
* 熟悉 TB6612FNG 电驱驱动逻辑，掌握带有抗积分饱和（Anti-Windup）及消抖 coast 时间的 PI 速度控制算法。

### 通信与系统集成
* 精通跨层数据网约定义（UART 串口 ASCII 行协议、MQTT JSON Telemetry 格式、FastAPI HTTP 统一字段定义）。
* 掌握 micro-ROS 硬件客户端连接与 UDP Agent 通信桥接技术。
* 掌握基于 WebSocket / MQTT 的实时状态广播及 FastAPI 的上游 HTTP API 代理缓存设计。

### 测试与排障
* 具备良好的软件契约测试意识，能够熟练使用 `pytest` 编写覆盖本地 SQLite 数据库、FastAPI 端点和状态机逻辑的自动化用例。
* 掌握 Headless head 导航自动化调试流程，通过对物理现象和数据日志的比对进行科学的问题分析与排障。
* 掌握基于命令行和串口调试终端（CuteCom/screen）的硬件现场诊断方法。

### 系统可观测性
* 能够从架构设计层设计上行数据反馈和下行指令控制链，具备端到端可观测性看板（Dashboard）开发经验。
* 掌握设备运行状态心跳（Heartbeat）、延迟判定（Stale Timeout）和报警事件的逻辑定义与网页图形化渲染。

### 工程能力
* 遵守严格的“边界意识”，不将仿真和实机功能混淆，注重 Mock 机制的应用。
* 具备规范的 Makefile 自动化脚本设计能力，代码遵守 Git 提交日志规范。
* 编写规范的系统技术文档、设计文档（Design Docs）和排障记录（Troubleshooting Log）。

---

## 7. 关键排障案例

### 案例 1：启动早期 Initial Pose 注入时机导致 Nav2 Lifecycle 挂起
* **问题现象**：Headless 启动无头导航后，`map -> odom` TF 树正常，但 `/navigate_to_pose` Action Server 数量显示为 0，导航任务无法接收。
* **原因分析**：经过查询发现，如果未在启动早期注入初始位姿（Initial Pose），`planner_server` 会因找不到 map 坐标变换而直接抛出超时错误并停留在 `inactive [2]` 状态。此时即便随后补发 `/initialpose`，TF 树虽能恢复，但已超时挂起的 `planner_server` 与 `bt_navigator` 不会自动补齐并激活。
* **修改内容**：修改 `publish_initial_pose.py` 的注入逻辑，在干净重启（Fresh Session）后的第 12-26 秒黄金窗口内强制连续发布 10 条 `start_zone` bit 位姿。
* **验证方式**：在无头环境下调用 `ros2 lifecycle get /planner_server`，结果返回 `active [3]`，且 `ros2 action info /navigate_to_pose` 显示 Server 数量为 1。
* **最终结果**：导航 Lifecycle 的全部激活率在 Fresh Session 干净启动下提升至 100%。
* **代码依据**：[repeat_navigation_test_report_2026_05_13.md:L51-L71](https://github.com/inayina/amr_warehouse_navigation/blob/main/docs/reports/repeat_navigation_test_report_2026_05_13.md#L51-L71)。
* **面试陈述**：
  > “在无头仿真调试中，我遇到了导航动作丢失的问题。通过编写 Python 脚本实时追踪 Nav2 节点的 Lifecycle 状态，我定位到 `planner_server` 在启动早期如果缺位姿变换会超时挂死在 inactive 状态。为了解决此问题，我调整了初始位姿的自动发布时机，在节点超时前完成注入，使得 5 核心节点 Lifecycle 的一次性激活成功率达到 100%，这也成了我们 Ready Gate 门禁的重要指标。”

### 案例 2：FastAPI 短连接生命周期下 `paho-mqtt` 控制命令丢失
* **问题现象**：在 Dashboard 网页端操作电机 Speed 速度滑块，API 响应 HTTP 200，但下游 ROS 2 硬件节点偶发性无法接收到电机转速。
* **原因分析**：FastAPI 处理客户端请求为短连接生命周期。`paho-mqtt` 客户端的 publish 操作执行后，由于网络异步连接建立需要时间，在发布尚未成功送达 broker时，FastAPI 路由函数已执行完毕并释放，导致 python client 实例连带连接被垃圾回收销毁。
* **修改内容**：在后端服务 `mqtt_motor_command.py` 中引入 `mosquitto_pub` 的命令行 Fallback 机制。一旦 Python 发布句柄捕获到异常或网络超时，直接通过 `subprocess` 调用系统本地的 `mosquitto_pub` 客户端强行向 Broker 发布载荷，并为 Python Paho 客户端补充 `loop_start()`/`loop_stop()`。
* **验证方式**：网页端连续调整滑块，观察终端中 ROS 2 话题 `/motor/cmd` 输出。
* **最终结果**：下行动作丢包率彻底清零，实现了 100% 的下行冗余可达。
* **代码依据**：[full_pipeline_validation_report.md:L80-L103](https://github.com/inayina/robot-ops-dashboard/blob/main/docs/full_pipeline_validation_report.md#L80-L103)。
* **面试陈述**：
  > “在开发 Dashboard 下行控制接口时，我发现 API 响应成功但电机话题数据偶发性丢失。通过抓包和分析后端异步进程，我判断是 FastAPI 的垃圾回收机制在 MQTT 物理握手完成前释放了客户端连接。为了解决这个问题，我采用了命令行的 fallback 冗余发布设计，利用系统级 mosquitto 客户端进行强制覆盖，并优化了 Python 的事件循环，确保了控制命令的绝对送达。”

### 案例 3：电机闭环调参中正交编码器反向导致积分暴冲
* **问题现象**：在桌面 N20 电机闭环台架测试中，一旦给电机设定目标 RPM，电机直接瞬间全速暴冲，失去 PID 控制能力。
* **原因分析**：物理接线错误导致编码器读数增加的方向与电机 TIM3 PWM 驱动的物理正向相反。PID 更新算法中，原本的**负反馈**变成了**正反馈**，导致积分器以最大速度向最大值累积，产生严重的积分饱和暴冲。
* **修改内容**：在配置文件 `app_config.h` 中设置 `kN20ClosedLoopBenchInvertEncoderDirection = true` 进行软件层面极性反转；同时在 `speed_pid.cpp` 中加入抗积分饱和（Anti-Windup）门禁，当输出达到限幅且误差同方向时直接锁死积分累积。
* **验证方式**：烧录后给目标 RPM 为 50.0，观察串口输出的 RPM 曲线和 Duty 值变化。
* **最终结果**：电机能够稳定平滑地加速到 50.0 RPM，无超调暴冲现象。
* **代码依据**：[single_motor_control.cpp:L168-L200](https://github.com/inayina/ros2-robot-digital-twin/blob/main/firmware/esp32_microros_bridge/src/motor/single_motor_control.cpp#L168-L200)。
* **面试陈述**：
  > “在调试嵌入式电机闭环控制时，由于硬件接线极性反向，电机出现了严重的积分饱和暴冲。我没有简单地通过手动调线解决，而是在固件中增加了编码器方向配置层，并在 PI 控制算法中引入了 Anti-Windup 抗积分饱和机制。当控制输出达到上限且误差无法消除时，暂停积分器累加，从而使系统即使在接线不匹配的情况下，也能保持稳定收敛。”

### 案例 4：`/imu/data` 话题 QoS 不匹配导致上位机数据吞失
* **问题现象**：ESP32 网桥启动后，串口明确输出了 IMU 解析，但在 PC 端使用 `ros2 topic echo /imu/data` 却没有任何数据，且没有任何报错。
* **原因分析**：ESP32 侧 micro-ROS 的 IMU 发布器被配置为 `BEST_EFFORT` QoS 以节省硬件带宽，而上位机终端默认以 `RELIABLE` 模式进行订阅。由于 ROS 2 DDS 契约中 `BEST_EFFORT` 发布器无法与 `RELIABLE` 订阅者完成握手，导致数据流在 DDS 层被直接过滤。
* **修改内容**：在上位机使用指定 QoS 配置的参数重新订阅：`ros2 topic echo --qos-reliability best_effort /imu/data`；并在状态网桥聚合层显式指定最佳努力（Best Effort）订阅配置。
* **验证方式**：终端查看，成功读到惯导传感器载荷。
* **最终结果**：数据链路成功打通，QoS 策略实现了一致匹配。
* **代码依据**：[full_pipeline_validation_report.md:L120-L130](https://github.com/inayina/robot-ops-dashboard/blob/main/docs/full_pipeline_validation_report.md#L120-L130)。
* **面试陈述**：
  > “在打通 micro-ROS 与上位机通信时，我遇到了底层发布正常但 ROS 2 topic 白屏的诡异现象。我通过排查 DDS 通信契约，定位到是底层为了硬件资源使用了 Best Effort QoS，而上位机默认使用 Reliable QoS，两者的可靠性策略不兼容。修改了上位机接收端的 QoS 规则后数据恢复正常。这也让我意识到在机器人集成中，通信策略的微小差异都会导致全链路的阻断。”

---

## 8. 项目取舍

在开发移动机器人系统时，出于资源与目标岗位的考虑，项目进行了以下核心决策与取舍，这有助于技术面试时展现合理的工程大局观：

| 项目 | 做了什么 | 暂时没做什么 | 取舍原因 |
| :--- | :--- | :--- | :--- |
| **`amr_warehouse_navigation`** | 纯 headless 仿真导航与 Mock WMS SQLite 任务状态机闭环 | 采购物理真车底盘并在现实中拉起建图 | 实体多线激光雷达、底盘硬件及传感器成本高昂。优先在仿真中打通 Nav2 全 Lifecycle 控制和 WMS 数据流逻辑，能够最快验证**系统集成能力**。 |
| **`ros2-robot-digital-twin`** | 编写了双核控制、正交解码测速及具有 Anti-windup 的 PI 闭环调试台架 | 双轮差速控制与 `ros2_control` 物理底盘运动 | 本项目定位为嵌入式与 micro-ROS **单点调联台架**。相比于机械底盘的加工和双轴打滑校准，单电机 PI 控制台架能最快速地验证“算法-硬件-驱动-反馈”这套高频闭环，在验证完毕后即可将精力投入后续工作。 |
| **`robot-ops-dashboard`** | 纯 HTML/CSS/JS 的多源数据监控、低频 motor STOP / SPEED 调试和 MJPEG 视频流代理 | 复杂的 React 多页面管理、权限认证和云端时序数据库存储 | 面板核心用途是“运维可观测性与低频bench调试”。多余的前端脚手架（React/Webpack）会增加编译与部署开销，使用 Vanilla Web 能够最轻量化、无依赖地展示数据并避免白屏。 |

### 为什么后来把主要精力转到“机械臂三仓项目”并关闭旧仓库维护？
这并非项目失败，而是因为旧三个项目已经**超预期完成了其阶段性的技术证明目标**：
1. **AMR仿真** 证明了上位机导航、Lifecycle 控制与 WMS HTTP 数据闭环能力。
2. **数字孪生** 证明了底层 STM32/ESP32 双核硬件开发、传感器高频采集与 PI 控制算法落地能力。
3. **Dashboard** 证明了跨系统接口聚合与运维可观测性系统设计。
在上述三大基石稳固后，为了往更前沿的具身智能（Embodied AI）技术突破，将开发重心向机械臂三仓项目偏移，以补充机械臂模仿学习行为克隆、PyBullet 回放验证与 EDA 仿真能力。两组项目在作品集中形成了完美的“硬件控制基石 + 具身智能前沿”的拼图关系。

---

## 9. 与机械臂三仓项目的关系

本作品集（旧三个项目）与候选人后续开发的“机械臂三仓项目”在能力画像上存在完美的互补互承关系：

| 能力方向 | 旧三个项目 (AMR / 孪生 / 运维) | 机械臂三仓项目 |
| :--- | :--- | :--- |
| **移动机器人** | 主线。Nav2自主导航，建图定位与局部避障。 | 非主线。仅作为物流递送的背景。 |
| **嵌入式与硬件** | 主线。STM32 FreeRTOS，ESP32 micro-ROS，TB6612，编码器PI闭环。 | 弱。主要为上位机 Python 行为仿真与算法验证。 |
| **系统通信** | 主线。HTTP Proxy, MQTT Cache, WebSocket 广播, 串口 ASCII 文本协议。 | 偏向于三仓数据联调与 handoff 数据契约。 |
| **机械臂** | 无。 | 主线。Franka Panda 机械臂六自由度轨迹规划与动作执行。 |
| **数据与训练** | 弱。仅处理简单的 RMS 振动特征分类。 | 主线。EDA 数据挖掘、MLP 行为克隆（BC）模仿学习与 CUDA 训练加速。 |
| **执行验证** | 偏向于 Nav2 的 Ready Gate 状态机与单电机 bench 测试。 | 偏向于 PyBullet 动作重放验证、碰撞危险度风险评估。 |
| **运维展示** | 主线。提供完整的 Dashboard 数据网关与 HTML 面板。 | 偏向于 RAG 证据生成、Benchmark 指标对比。 |

### 统一的候选人能力画像
> “旧三个项目证明了我在**移动机器人系统集成、嵌入式底层控制、跨系统通信网关以及系统可观测性运维**方面的硬核功底；而机械臂三仓项目则在此基础上，进一步补充了我在**具身智能、模仿学习算法训练、物理仿真以及具身任务动作验证**方面的前沿开发能力。这两组项目共同构成了我作为一个**‘既懂底层硬件控制、又懂上层系统通信，且具备具身智能算法视野’**的系统型机器人开发工程师的完整拼图。”

---

## 10. 面试话术

### 30 秒整体总览版本
> “您好，我的作品集由三个高度咬合的项目构成，覆盖了机器人的决策层、执行层和运维层。我通过 ROS 2 与 Nav2 实现了仓库 AMR 导航及 WMS 任务管理仿真；在底层使用 STM32 和 ESP32 结合 FreeRTOS 与 micro-ROS，打通了 100Hz 的传感器姿态解算和 N20 电机 PI 速度闭环控制；最后使用 FastAPI 和原生 HTML 搭建了数据聚合 Dashboard。这组项目集中体现了我从零构建‘硬件-通信-规划-运维’机器人系统全链路的集成与调优能力。”

### 3 分钟整体 presentation 版本
> “各位面试官好，今天我想重点介绍我的机器人系统整合作品集。我做这组项目的初衷，是为了探索如何把零散的控制算法、传感器采集和上层规划，整合成一个真正稳定、可观测的工业级机器人软硬件系统。
>
> 系统在职责上进行了清晰的划分：
> 首先，在决策规划层，我用 ROS 2 Jazzy 和 Nav2 搭建了 AMR 仿真，并用 Python+FastAPI 实现了 Mock WMS 任务链。为了解决机器人无头启动早期发目标被吞的行业痛点，我开发了一个 Ready Gate 状态机门禁，只有在 5 核心节点 Lifecycle 全 Active、TF 连通且 Action 可用时才发送任务，把任务执行的稳定性提升到 100%。
> 其次，在执行传感层，我用 STM32F411 和 ESP32-S3 设计了双核边缘系统。STM32 在 FreeRTOS 下负责高频惯导采集与本地异常状态推断，ESP32 则通过 micro-ROS UDP 桥接上行数据，并利用 GPIO 边沿中断实现了 N20 减速电机的 PI 速度闭环控制，包含抗积分饱和及电机换向缓冲保护。
> 最后，在聚合运维层，我用 FastAPI 作为数据网关订阅 MQTT 和轮询 WMS，前端使用无框架的原生 HTML5+WebSocket 广播，避免了复杂的脚手架依赖，实现了低延迟的运行状态观测与低频电机 Bench 调试。
>
> 尽管这个系统目前在仿真和单电机台架上运行，但它让我深刻理解了 QoS 匹配、Lifecycle 时序波动、通信抖动下的 fallback 设计等真实集成难题。结合我后续在机械臂具身模仿学习上的积累，我相信我能够快速胜任机器人系统集成、测试验证及现场交付等核心研发工作。”

### 每个项目 60 秒 Pitch 版本

#### AMR 导航：
> “在自主导航项目中，我重点攻克了‘无头环境下 Nav2 启动就绪判定’的工程难题。我搭建了 Gazebo 仓库物理仿真，编写了自动发布 initial pose 的初始化节点，并实现了一个 Ready Gate 门禁。它不再口头假设 Ready，而是物理监测 5 核心生命周期节点、TF 和 Action 连接。我在本地通过 `pytest` 和 `colcon test` 编写了 33 项集成与契约测试用例，完全打通了 WMS 任务派发与导航执行的闭环。”

#### 数字孪生：
> “在边缘控制项目中，我完成了 STM32+ESP32 双核嵌入式通信网桥与闭环控制设计。STM32 在 FreeRTOS 调度下进行 100Hz 姿态计算，ESP32 实现 micro-ROS 话题发布。针对桌面 N20 电机台架，我使用 ESP32 外部中断实现了四倍频正交解码测速，并编写了带抗积分饱和与消抖 Coast 机制的 PI 控制器，实现了物理电机的速度速度闭环控制与 Gazebo 姿态数字孪生同步。”

#### Dashboard 看板：
> “在运维 Dashboard 项目中，我利用 FastAPI 设计了一个多源机器人数据网关。它通过异步 MQTT 订阅本地传感器数据并轮询 Mock WMS API。前端坚持纯原生 Vanilla JS 开发，通过 WebSocket 实现了零延迟的 telemetry 刷新。我还加入了 `mosquitto_pub` 的命令行 fallback 备份机制以应对 FastAPI 短连接下的控制丢包问题，为机器人系统调试提供了一个轻量、可靠的可观测窗口。”

### 深挖问题及参考答案

#### 1. 为什么你的 Ready Gate 要检查 5 个特定的 Lifecycle 节点？缺一个会有什么后果？
> “我检查的 5 个节点是 `map_server`、`amcl`、`planner_server`、`controller_server` 与 `bt_navigator`。这是因为 Nav2 的动作链是强耦合的。例如，如果 `planner_server` 挂起在 inactive，虽然 AMCL 能够正常定位，但当发送 Goal 时，BT 状态树无法生成全局路径，导致整个 action 请求在没有接收反馈的情况下直接 reject。Ready Gate 通过 lifecycle 接口物理拦截了这一情况。”

#### 2. ESP32 上的 PI 电机闭环控制中，Anti-Windup（抗积分饱和）是如何起作用的？
> “我们在 speed_pid.cpp 中实现了 Clamp 限制。当电机因阻力过大或目标 RPM 过高导致输出的 PWM Duty 达到设定的上限（如 0.35）时，如果此时误差仍然同向（即目标速度大于实际速度，需要继续增大输出），控制算法会强制停止积分项的累加，保持上一步的积分状态。这就避免了积分器无限累加，使得阻力消失时电机不会产生剧烈过冲。”

#### 3. 为什么 Dashboard 不直接连接到 ROS 2，而要通过 MQTT 进行中转？
> “这符合机器人架构的‘动静隔离’与‘低带宽消费’原则。ROS 2 DDS 的发现机制和高频通信需要消耗大量的 CPU 和内存资源，直接让 Dashboard 后端加入 ROS 2 主网会让系统变重。我使用本地轻量级 MQTT Broker (Mosquitto) 作为隔离层，将高频 ROS topic 转化为低频、结构化的 JSON Telemetry 缓存在后端内存中，有效降低了系统的耦合度与网络开销。”

---

## 11. HR 视角说明

对于非技术背景的 HR 或招聘人员，可以从以下角度解释这三个项目的核心价值：

### 三个项目分别解决什么？
1. **AMR仿真**：类似于机器人的“大脑和小脑”，解决机器人在复杂的仓库里怎么看懂地图、怎么规划路线、怎么按顺序完成送货任务。
2. **数字孪生**：类似于机器人的“神经和关节”，解决怎么从底层的陀螺仪传感器获取姿态，以及怎么精准控制马达转动指定的圈数。
3. **Dashboard**：类似于机器人的“仪表盘和诊断器”，解决运维和测试人员怎么在一个网页上看到机器人所有的运行状态，遇到故障怎么一键停止。

### 为什么这不是简单的网络教程项目？
* **真实面对波动**：教程项目通常假设网络永远完美、机器人永远 100% 成功。而本系统在报告中如实记录了 Lifecycle 的超时、狭窄通道下的 Recovery、控制命令在异步连接下的丢包，并针对性地开发了 Ready Gate 门禁和命令行 Fallback 控制，这体现了**解决真实工程波动**的能力。
* **完整的自动化测试**：项目没有只停留在“跑起来就行”，而是编写了 33 项 AMR 测试与 42 项 Dashboard 后端测试，这是教程类项目绝对不具备的**专业软件质量意识**。

### 入职可迁移能力
* **全链路联调与排障能力**：能够从上层网页一直排查到单片机的串口数据包，快速定位是通信协议问题、DDS 策略问题还是底层驱动问题。
* **极强的规范意识**：严格界定“仿真与真实”的边界，编写详尽的技术文档和测试报告，入职后可直接规范化地参与团队研发。
* **自主解决工程闭环**：能够独立搭建测试 bench 调试台架，通过数据而非口头推测定位问题。

### 适合投递的岗位定位
* **机器人系统集成工程师**：擅长将导航、硬件、通信和监控进行一体化组装与调试。
* **机器人测试验证/质量工程师**：具备强大的自动化契约测试、无头回归测试以及台架闭环测试经验。
* **机器人应用开发/交付工程师**：能够处理 WMS 接口对接、状态可观测性看板定制及现场复杂问题的定位。
* **技术支持/售后交付经理**：具备从硬件到软件的完整链路视野，擅长非技术/技术交叉沟通。

---

## 12. 简历素材总表

### 版本 A：机器人系统集成岗位 (重点突出网桥与通信集成)

* **个人定位**：机器人系统集成工程师，具备 ROS 2、底盘硬件调试、跨模块通信网关及全链路联调经验。擅长通过架构设计、QoS 调优与 Lifecycle 控制解决多系统集成波动，保障机器人高可用。
* **项目经历描述**：
  * **自主仓库移动机器人（AMR）导航与任务执行仿真系统**：
    * 基于 ROS 2 Jazzy 和 Gazebo Harmonic 搭建移动机器人仿真平台，调优 SLAM Toolbox 与 Nav2 避障算法，固化仓库地图与 fixed 点位坐标。
    * 设计并实现基于 Lifecycle 节点的 Headless 自动化就绪门禁（Ready Gate），联合监测 5 大核心服务状态及 TF 变换，解决系统初始化阶段导航 Goal 吞失问题。
  * **STM32/ESP32 双处理器机器人状态网桥与闭环控制台架**：
    * 采用 STM32F411 配合 FreeRTOS 实现 100Hz 姿态结算与异常推断；设计自定义 UART ASCII 行协议将姿态及状态标号打包上传。
    * 基于 ESP32-S3 搭建无线通信桥，利用 micro-ROS 客户端建立高速 UDP 连接，将传感器与电机状态以 50Hz 稳定发布至 ROS 2 网络。
  * **FastAPI/MQTT 机器人运维聚合网关与可观测性看板**：
    * 使用 FastAPI 构建多源数据聚合层，通过 MQTT 订阅本地设备数据流并代理 WMS 任务链接口，实现一体化可观测看板。
    * 针对短连接下控制命令丢包问题，实现基于 `mosquitto_pub` 的命令行控制 fallback 备份机制，提供下行动作的物理级送达保障。
* **技术关键词**：ROS 2 Jazzy, Nav2, micro-ROS, STM32, ESP32, FreeRTOS, MQTT, WebSocket, FastAPI.
* **适合投递岗位**：机器人系统集成工程师、软硬件联调工程师、机器人应用开发工程师。

---

### 版本 B：机器人测试验证岗位 (重点突出自动化测试与台架验证)

* **个人定位**：机器人测试验证工程师，具备规范的自动化契约测试、无头集成回归测试及硬件台架闭环调试能力。擅长设计测试用例、排查协议冲突并建立可重复的质量回归流程。
* **项目经历描述**：
  * **基于 Pytest 契约测试的 AMR 仿真任务执行系统**：
    * 编写基于 `pytest` 的契约与集成测试集，覆盖 SQLite 任务读写、FastAPI 接口规范及任务执行器状态机，通过 Makefile 实现本地自动化一键回归（33项测试 100% 通过）。
    * 建立无头（Headless）自动化导航跑测机制，客观记录 12 轮运行日志，发现并分析 Lifecycle 激活波动及局部 costmap 通道狭窄下的自主 Recovery 规律。
  * **单电机 PI 闭环调试台架与数字孪生同步系统**：
    * 基于 ESP32-S3 外部中断实现 N20 减速电机双相正交解码测速，编写带积分抗饱和（Anti-windup）及换向缓冲的 PI 控制算法。
    * 搭建桌面调试台架对速度环进行阶跃测试与参数标定，并开发 ROS 2 孪生节点将姿态四元数桥接至 Gazebo，实现实机与仿真姿态的物理级同步验证。
  * **Dashboard 看板自动化接口测试与系统就绪验证**：
    * 编写 Dashboard 后端自动化集成测试用例，覆盖 WebSocket 状态广播、API 异常处理及 MQTT 数据缓存，确保聚合层逻辑的鲁棒性（42项测试 100% 通过）。
    * 编写 `verify_demo_readiness.sh` 脚本，自动化扫描 HTTP API、MQTT Broker 及通信端口的在线状态，作为系统交付前的自动化准入边界。
* **技术关键词**：Pytest, Integration Testing, Regression Testing, Quadrature Decoding, PI Tuning, Anti-Windup.
* **适合投递岗位**：机器人测试工程师、自动化测试工程师、嵌入式测试工程师。

---

### 版本 C：机器人应用/交付岗位 (重点突出业务场景、WMS 与可观测性)

* **个人定位**：机器人应用开发/交付工程师，具备 Mock WMS 业务逻辑对接、可观测性看板搭建、现场问题排查及技术文档编写能力。擅长快速定位网络与数据链路冲突，推动项目收口交付。
* **项目经历描述**：
  * **基于 WMS 与自主导航的仓库 AMR 派单仿真**：
    * 基于 SQLite 与 FastAPI 设计 Mock WMS 任务管理层，实现任务创建、拉取、分发和执行状态（pending/running/succeeded/failed）的全生命周期状态机回写。
    * 编写详尽的固定任务坐标坐标规划案（Coordinate Plan）和集成排障指南，规范化管理 station 与 shelf 的候选执行坐标。
  * **原生 HTML5 原生移动机器人可观测性看板**：
    * 完全使用原生 HTML5/Vanilla JS/CSS3 开发轻量化运维看板，通过原生 WebSocket 直连网关，避免复杂脚手架引发的页面加载白屏，提升现场运维体验。
    * 实现 MJPEG 视频流传输网关，将 Gazebo 实时仿真画面的 RViz 路径预览图（RViz Path View）通过后端代理嵌入网页端，实现远程预览。
  * **STM32/ESP32 边缘监测与本地声光报警系统**：
    * 在 STM32 侧设计基于 RMS 均方根的 6 轴振动、碰撞与倾翻算法，控制 TIM2 PWM 产生阶梯频率驱动本地报警蜂鸣器与 LED，实现设备状态的本地边缘观测与物理防护。
* **技术关键词**：WMS Integration, WebSockets, Vanilla JS, MJPEG Streaming, Sound-light Alarm, Local Data Processing.
* **适合投递岗位**：机器人交付工程师、现场应用开发工程师、售前/售后技术支持工程师。

---

## 13. 高频追问（续）

### 16. `ros2_control` 相比于直接订阅 `/cmd_vel` 有什么优势？
> “`ros2_control` 提供了统一的机器人硬件抽象接口。它通过动态加载控制器（如 `diff_drive_controller`）来管理电驱，提供了实时（Real-time）控制循环的安全保障，并支持在运行态动态切换控制器。直接订阅 `/cmd_vel` 属于应用层点对点对接，缺乏底层实时性管理和标准硬件接口约束，无法直接接入 ROS 2 的标准控制器生态。”

### 17. 为什么 MPU6050 采集是 100Hz，而发布到 `/imu/filtered` 话题是 25Hz？
> “这是一种典型的‘高频内部环路，低频对外发布’的通信带宽优化设计。100Hz 高频采集和 complementary filter 计算是为了保证姿态解算的精度和本地报警（如碰撞检测）的低延迟。而上位机网络通信和数字孪生可视化对姿态更新的实时性要求通常在 20-30Hz 即可达到平滑的视觉效果。将发布频率降为 25Hz 可以有效节省 micro-ROS over Wi-Fi 的带宽，防止无线局域网 DDS 丢包。”

### 18. 如果串口波特率是 921600，能保证 100Hz 的 `IMUQ` 数据发送吗？
> “能。我们分析一下数据大小。一条标准的 `IMUQ` 帧格式形如：`IMUQ,ax,ay,az,gx,gy,gz,qx,qy,qz,qw,temp\n`，长度约为 60-80 字节。按 100Hz 发送，每秒产生约 8000 字节数据。而 921600 bps 波特率在 8N1 格式下的实际物理传输速率约为 92KB/s，远大于 8KB/s。因此 921600 波特率下串口带宽冗余度超过 10 倍，绝对不会产生串口缓冲区积压延迟。”

### 19. 在 STM32 侧，为什么要设计独立队列将数据从 `SensorTask` 传递给 `AlgTask`？
> “这符合 FreeRTOS 的‘解耦与确定性调度’设计。`SensorTask` 负责高频 100Hz 采集，具有极高的时间敏感度，绝不能被任何动作阻塞。而 `AlgTask` 执行的 RMS 状态推理涉及浮点运算和窗口化处理，比较耗费 CPU 时间。使用 RTOS 消息队列进行数据中转，实现了高频采集与状态运算的异步解耦，保证了传感器采样的精确定时。”

### 20. 串口解析代码中，你是如何处理分包和粘包问题的？
> “我们在代码中设计了‘行缓冲区机制’。由于串口协议是 ASCII 行协议（以 `\n` 换行符结尾），我们在接收中断中并不直接触发解析，而是将接收到的每个字节压入一个内部 FIFO 环形缓冲区。当且仅当在缓冲区中扫描到 `\n` 换行符时，才提取出整行文本帧进行解析，这从物理上消除了网络传输中常见的分包粘包问题。”

### 21. 如果 ESP32 网桥丢失了 WiFi 连接，系统会有什么自愈机制？
> “在 `main.cpp` 中设计了断线自愈状态机。一旦 `WiFi.status()` 返回非 connected，Core 0 上的 `ros_comm_task` 立即销毁当前的 micro-ROS 支持实体（销毁 Node、Pub、Sub 句柄以释放内存），并启动 `serviceWiFiConnection()` 周期性重试 WiFi 物理连接。一旦 WiFi 重新连接成功，会重新拉起 micro-ROS 并重建 DDS 实体，实现了局域网网络中断后的自动恢复。”

### 22. 为什么你的 MPU6050 孪生要锁定 Yaw 轴？
> “因为 MPU6050 是一个六轴惯导（3轴加速度 + 3轴陀螺仪），没有配备三轴磁力计。六轴 IMU 的 Yaw 轴（偏航角）只能通过角速度积分得到，由于漂移的存在，偏航角会随着时间推移产生无限的累加偏差（即陀螺仪漂移导致的自转现象）。而 Roll 和 Pitch 轴可以利用重力加速度进行长期重力校准，因此非常稳定。为了展示效果不发生漂移，我们在 Gazebo 位姿更新中锁死了初始 Yaw 轴。”

### 23. 前端样式中，你是如何避免加载白屏和性能卡顿的？
> “前端完全不使用 React/Vue 框架以及庞大的三方 npm 包，所有的 CSS 样式直接写在 `styles.css`，交互逻辑写在 `app.js`。没有打包混淆和臃肿的 js bundle 加载过程，浏览器可以直接解析静态 HTML。同时，所有图表渲染使用轻量化的 DOM 节点刷新，避免了大规模 Canvas 绘制，从而实现了极低的 CPU 占用和零加载白屏。”

### 24. WMS 数据库的事务机制你是如何处理的？
> “因为我们使用的是轻量级 SQLite3 作为 WMS 存储，且 AMR 任务消费和 WMS API 创建属于不同进程的多任务并发场景。为了防止多进程写入冲突导致的 `database is locked` 报错，我们在 Python 数据库底层开启了 WAL（Write-Ahead Logging）预写日志模式，并对所有的 `UPDATE` 与 `INSERT` 数据库操作包裹了严格的 `BEGIN IMMEDIATE` 事务门禁，确保了任务数据回写的一致性。”

### 25. `/api/sim/stream` 代理 mjpeg 视频流的原理是什么？
> “它是基于 HTTP Multipart 传输的流媒体代理。FastAPI 接收到网页端请求后，作为一个 HTTP 客户端，异步向后端的 RViz MJPEG 服务器发起 HTTP GET 连接。接着，后端解析上游响应头中的 `boundary` 标识，并利用 `StreamingResponse` 作为一个中间人（Proxy），将上游传过来的 JPEG 图像帧实时透传给浏览器网页，避免了前端页面直接暴露后端真实渲染服务器端口。”

### 26. 为什么电机控制要设置方向消抖时间（Direction Change Coast）？
> “如果电机在高速正转时（比如 Duty = +0.35），前端或算法立刻下发反转指令（Duty = -0.35），TB6612 驱动模块会将 H 桥引脚电压瞬间反向。由于转子和负载存在机械惯性，电机会产生极大的反向电动势并与电源叠加，产生巨大的瞬间反向电流，极易击穿 H 桥 MOSFET 或拉垮 MCU 电源。我们设置 200ms 的换向缓冲 Coast 状态，即换向时先关闭电驱使能，等电机惯性减速后再反向驱动，保障了电驱安全。”

### 27. 如果 MQTT Broker 宕机了，Dashboard 的响应会有什么变化？
> “后端 `RobotMqttStatusService` 内部使用了单独的互斥锁保护状态字典。一旦连接断开，Paho 客户端触发 `on_disconnect`，将连接状态标记为 `disconnected` 并将错误信息写回。由于网页端是通过 WebSocket 订阅状态，后端在广播消息时，会把连接字典中的 `status="disconnected"` 和最新报错打包发送，前端看板上的 `DDS Status` 状态芯片会立刻从绿色的 `Online` 变为红色的 `Offline`，显示明确的错误，而不会白屏挂死。”

### 28. 为什么 `pytest` 自动化测试中有些用例是 `skipped` 的？
> “在自动化回归测试中，我们区分了‘纯软件逻辑测试’和‘物理集成测试’。如果测试执行环境缺少 ROS 2 Jazzy 的系统依赖，测试集会自动跳过（skip）需要初始化 ROS 节点的物理集成用例（如 action 发送用例），而仅运行纯 Python 的 WMS API 契约和 SQLite3 逻辑测试，这保证了测试集在缺少 ROS 环境的轻量化 CI 跑测时也能平稳运行，不产生虚假的失败报错。”

### 29. 项目中是如何实现 mock 数据和真实数据隔离的？
> “我们在后端工程中使用配置驱动模型。数据接口（如 `GET /api/tasks`）的底层实现不直接读写具体文件，而是通过一个适配器层（TaskMapper）。在 `amr_http` 模式下，适配器去调用 `fetch_wms_tasks_payload` 访问真实 REST 接口；在 `mock_json` 模式下则加载本地静态 JSON，这种隔离设计保证了我们随时可以一键切回纯展示的 Mock 模式，不影响现有系统的物理稳定性。”

### 30. 在 ESP32 桥接程序中，你如何保证 micro-ROS 的堆内存没有溢出？
> “在 `main.cpp` 中，我们在 Core 0 启动的守护任务内加入了调试信息监控：利用 ESP-IDF 提供的 `xPortGetFreeHeapSize()` 在 `printRuntimeStatsIfDue()` 中以 10 秒为周期向串口输出剩余堆栈字节大小，并通过 `uxTaskGetStackHighWaterMark()` 监视 micro-ROS 执行器任务的空闲栈深度。在重连 WiFi 和重建 DDS 支持实体的过程中，严格验证释放操作，从而防止了硬件内存泄漏引起的 watchdog 复位崩溃。”

---

## 14. 最终事实边界

为保证求职和技术面试时的客观诚实，在此统一声明三个旧项目当前**不能证明**与**能够证明**的技术事实边界：

### 本作品集当前不能证明
* **工业/商业级可靠性**：未经过恶劣电磁环境（EMC）测试，无真车防碰撞安全边沿等硬件二级安全冗余。
* **大规模并发调度**：WMS 系统仅为单车任务队列，不支持多机器人（Fleet Manager）避障与多车路径协调。
* **物理建图导航**：实车导航未进行现场标定，地图（warehouse.yaml）完全基于 Gazebo 仿真生成。
* **算法训练与推理**：Evaluation 页面展示的测试成功率（66.7%）完全为 JSON 静态 Mock，不代表真车端侧部署了神经网络进行实时轨迹推理。

### 本作品集完全可以证明
* **ROS 2 机器人系统链路理解**：对 ROS 2 话题、Action、Lifecycle 节点时序控制具有深刻的工程实践经验。
* **底座软硬件联调与闭环控制**：熟练掌握 STM32/ESP32 双处理器协同、正交编码器中断测速及 PI 电机速度闭环控制。
* **跨系统通信网关开发**：具备 UART 串口 ASCII 行协议设计、FastAPI HTTP 网关代理与 MQTT 数据缓存的实战能力。
* **高水准软件测试意识**：熟练掌握 `pytest` 契约回归测试、无头 headless 状态机就绪检测和台架准入测试，具备极强的规范文档与排障意识。
