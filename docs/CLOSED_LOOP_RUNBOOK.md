# 三仓闭环跑手册 (Closed Loop Runbook)

状态：**G0–G3 收口执行入口**。Sim-to-Sim 闭环，不宣称 Sim2Real。

**上游持久库（推荐）**：`/home/ina/dev/ros2-arm-teleoperation-suite/data/episodes/`

---

## Gate 一览

| Gate | 目标 | 负责仓 | 脚本 |
|------|------|--------|------|
| **G0** | 上游 raw 可信 | 上游 | `collect_daily_episodes.sh` / `run_batch_preflight_smoke.sh` |
| **G1** | adapt → release → train → handoff | 中游 | `run_three_repo_closed_loop.sh` |
| **G2** | PolicyRunner replay | 下游 | `benchmark_system.py`（G1 脚本可选触发） |
| **G3** | 证据包 + registry | 中游 | 自动归档于 `evidence/` |

---

## 日常节奏（推荐）

每天采 1–3 条，累积到 `data/episodes/`，攒够 10–20 条再跑 release / 训练。

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash && source install/setup.bash

# 默认：采 1 条红盒子 episode → staging → 追加到 data/episodes/
./scripts/collect_daily_episodes.sh

# 查看库状态
python3 scripts/episode_archive.py status
python3 scripts/validate_dataset.py data/episodes --min-frames 5
```

三种物体各 1 条：

```bash
COLLECT_OBJECTS="object_red_box object_blue_cylinder object_green_sphere" \
  ./scripts/collect_daily_episodes.sh
```

只导入已有 `/tmp` 批次（不重跑仿真）：

```bash
./scripts/collect_daily_episodes.sh --import-only /tmp/ros2_arm_batch_preflight_<stamp>_<pid>
```

---

## G0：上游批采

### 持久归档布局

```text
data/episodes/
├── episode_000000/
│   ├── meta.json              # upstream_gate=batch_generator
│   └── train/                 # HuggingFace load_from_disk
├── episode_000001/
│   └── ...
└── collection_log.jsonl
```

说明见上游 `data/episodes/README.md`。目录已 gitignore，大文件不进仓库。

### 一次性 smoke（3 物体）

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash && source install/setup.bash

bash scripts/run_batch_preflight_smoke.sh
# 成功后导入持久库：
./scripts/collect_daily_episodes.sh --import-only "$OUT_ROOT"
```

**出口**：`validate_dataset` valid=true；`upstream_gate=batch_generator`；`grasp_assist=false`。

单类扩展（20 条）仍用 `batch_generator` 直接写 `output_dir:=data/episodes`（需配合 `episode_archive.py next-index` 设置 recorder 起始编号，或采完再 import）。

---

## G1：中游训练链

默认读取上游持久库（无需再设 `UPSTREAM_RAW`）：

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

./scripts/run_three_repo_closed_loop.sh
```

显式指定路径：

```bash
UPSTREAM_RAW=/home/ina/dev/ros2-arm-teleoperation-suite/data/episodes \
  ./scripts/run_three_repo_closed_loop.sh
```

Mock（无 ROS，CI / 冒烟）：

```bash
CLOSED_LOOP_USE_MOCK=1 ./scripts/run_three_repo_closed_loop.sh
```

产物：

```text
/tmp/three_repo_closed_loop_*/
├── adapted/
├── release/
├── train/
│   ├── checkpoint.npz
│   ├── predicted_actions.jsonl
│   └── bridge_handoff/
└── evidence/

仓库内归档：evidence/（G3 模板布局）
```

Registry 追加：`data/registry/releases.yaml`

---

## G2：下游 replay

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

WITH_DOWNSTREAM=1 ./scripts/run_three_repo_closed_loop.sh
```

或手动：

```bash
source ~/ros2_ws/install/setup.bash
python3 ~/ros2_ws/src/ros2-moveit-pybullet-bridge/scripts/benchmark_system.py \
  --strategy panda_jsonl_replay \
  --panda-handoff-path /path/to/bridge_handoff \
  --episodes 1 --duration-sec 5.0 \
  --output-dir /tmp/benchmark_out --launch-stack
```

填写反馈：`docs/templates/downstream_replay_summary.yaml`

---

## G3：证据包

模板：[templates/closed_loop_evidence/README.md](templates/closed_loop_evidence/README.md)

检查清单（最近一次跑通已归档于 `evidence/`）：

- [x] G0 `upstream/validate_dataset.json` valid=true
- [x] G1 release + handoff manifest 存在
- [x] G1 smoke train metrics 存在
- [x] G2 benchmark_summary（`WITH_DOWNSTREAM=1`）
- [x] 三仓 commit hash 在 `meta/three_repo_commits.txt`

快速查看：`evidence/meta/run_summary.json`

复现 G1+G2+G3：

```bash
WITH_DOWNSTREAM=1 CLOSED_LOOP_ARCHIVE_EVIDENCE=1 \
  ./scripts/run_three_repo_closed_loop.sh
```

---

## 刻意后置（闭环后再做）

- Multi-task ACT + HOC 语言下发
- 大规模 GPU 训练（建议 ≥10–20 episodes 后再 claim 训练 readiness）
- RM-M3 死区补偿、RM-M7 自动化 grasp eval
- 真机验收

Agent 规范：[../AGENTS.md](../AGENTS.md)
