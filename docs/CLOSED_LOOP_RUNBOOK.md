# 三仓闭环跑手册 (Closed Loop Runbook)

状态：**G0–G3 收口执行入口**。Sim-to-Sim 闭环，不宣称 Sim2Real。

---

## Gate 一览

| Gate | 目标 | 负责仓 | 脚本 |
|------|------|--------|------|
| **G0** | 上游 raw 可信 | 上游 | `run_batch_preflight_smoke.sh` |
| **G1** | adapt → release → train → handoff | 中游 | `run_three_repo_closed_loop.sh` |
| **G2** | PolicyRunner replay | 下游 | `benchmark_system.py`（G1 脚本可选触发） |
| **G3** | 证据包 + registry | 中游 | 自动生成于 `evidence/` |

---

## G0：上游批采（Day 1–3）

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
source /opt/ros/jazzy/setup.bash && source install/setup.bash

bash scripts/run_batch_preflight_smoke.sh
# 输出目录见日志 BATCH_PREFLIGHT_OUTPUT_ROOT

python3 scripts/validate_dataset.py "$OUT_ROOT" --min-frames 5 --json
```

**出口**：3/3 smoke；`upstream_gate=batch_generator`；`grasp_assist=false`。

单类 20 条（G0 扩展）：

```bash
export UPSTREAM_RAW=/tmp/your_batch_out
ros2 run synth_data_gen batch_generator --ros-args \
  -p target_object_name:=object_red_box \
  -p episodes:=20 -p max_attempts_per_episode:=3 \
  -p validation_mode:=place
```

---

## G1：中游训练链（Day 3–5）

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

UPSTREAM_RAW=/path/to/upstream/batch/output \
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
```

Registry 追加：`data/registry/releases.yaml`

---

## G2：下游 replay（Day 5–7）

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab

UPSTREAM_RAW=/path/to/raw WITH_DOWNSTREAM=1 \
  ./scripts/run_three_repo_closed_loop.sh
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

检查清单：

- [ ] G0 `validate_dataset.json` valid=true
- [ ] G1 release + handoff manifest 存在
- [ ] G1 smoke train metrics 存在
- [ ] G2 benchmark_summary（若跑下游）
- [ ] 三仓 commit hash 在 `evidence/*_commit.txt`

---

## 刻意后置（闭环后再做）

- Multi-task ACT + HOC 语言下发
- 大规模 GPU 训练
- RM-M3 死区补偿、RM-M7 自动化 grasp eval
- 真机验收

Agent 规范：[../AGENTS.md](../AGENTS.md)
