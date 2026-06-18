# 数据采集流程

本项目第一阶段刻意保持数据采集流程简单。目标是展示一条清晰、可验证的 `image-state-action episode` 数据闭环，而不是构建完整机械臂控制系统。

## 1. 环境初始化

`scripts/collect_episode.py` 默认以 PyBullet DIRECT 模式启动仿真。

默认会从 `configs/default.yaml` 读取采集参数（步数、分辨率、相机、任务名等）。
CLI 参数会覆盖配置文件中的同名字段，例如：

```bash
python scripts/collect_episode.py --config configs/default.yaml --output dataset_sample/episode_000001
python scripts/collect_episode.py --num-steps 30
```

环境中加载：

- 地面平面
- PyBullet 示例 KUKA iiwa 机械臂
- 一个 cube 操作对象
- 一个固定 RGB 相机

机械臂会被重置到确定性的初始关节配置，便于重复采集和调试。

## 2. 动作生成

V1 使用一段预设的平滑关节位置轨迹。

这样做可以让第一版保持确定性和可解释性：

- 不依赖 ROS2
- 不依赖 MoveIt 规划
- 不依赖逆运动学模块
- 不要求抓取成功
- 不包含强化学习训练

每个 step 保存的 action 是发送给 PyBullet 位置控制器的目标关节位置向量。

## 3. 仿真步进

每个 `episode` step 执行以下流程：

1. 计算目标关节位置
2. 应用 PyBullet 位置控制
3. 推进仿真
4. 读取关节位置
5. 读取末端位姿
6. 读取 cube 位姿
7. 渲染固定相机 RGB 图像
8. 将同步数据追加到数组中

## 4. Episode 保存

采集脚本写出：

- `images/{step:06d}.png`
- `states.npy`
- `actions.npy`
- `ee_poses.npy`
- `object_poses.npy`
- `metadata.json`

所有数组的第一维都与图像帧数一致。

## 5. 数据校验

`scripts/validate_dataset.py` 检查：

- 必要文件是否存在
- 图像帧是否从 `000000.png` 开始连续命名
- numpy 数组是否为二维
- 位姿数组第二维是否为 7
- 数组长度是否与图像帧数一致
- 元数据必要字段是否存在
- 元数据中的维度是否与实际数组一致

## 6. 轨迹回放

`scripts/visualize_episode.py` 会生成带标注的 GIF 回放。

标注信息包括：

- step index
- 动作向量前几项
- cube 的 xyz 位置

生成的 GIF 可用于 README、作品集截图或面试讲解。

## 7. 后续扩展方向

V2 之后可以基于同一套数据结构继续扩展：

- 转换为 LeRobot 风格数据集
- 使用 Isaac Sim 采集合成数据
- 使用 MoveIt 生成动作轨迹
- 接入 ROS2 执行日志
- 迁移到真实机械臂数据采集

这些方向都不属于第一阶段实现范围。
