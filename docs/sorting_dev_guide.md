# 中游仓库：多任务条件策略训练开发指南 (Midstream Sorting Dev Guide)

本指南针对中游 `robot-arm-episode-data-lab` 仓库，规范多目标分类任务的数据处理、**文本编码器集成以及多任务条件 ACT 模型训练**的具体开发细节与执行命令。

---

## 1. 依赖库准备

引入自然语言文本提取器，需要安装 Hugging Face Transformers 与相关词法分析工具：
```bash
python3 -m pip install transformers torch tokenizers
```

---

## 2. 文本编码器与特征融入设计

当前中游实现位于 `training/encoders/text_encoder.py`：

- `clip`：使用 Hugging Face `openai/clip-vit-base-patch32`，输出 512 维文本嵌入，用于 LeRobot / ACT 训练环境。
- `mean_hash`：纯 NumPy 确定性 512 维向量，用于 CI、离线测试和无 torch 环境。

在 `training/scripts/train_act_lerobot.py` 中，数据加载器会将：

```text
observation.state[8] + language_instruction_embedding[512] -> observation.state[520]
```

随后送入 LeRobot `ACTPolicy`，action 以 `chunk_size` 组织，chunk 不跨 episode 边界。

后续如果要升级为视觉 token 与文本 token 的显式 cross-attention，可在独立模型实现中扩展：

```python
attention_output = self.cross_attn(
    query=image_and_state_features,
    key=text_embeddings,
    value=text_embeddings
)
```

---

## 3. 数据校验与清洗命令

### 3.1 验证多任务数据集结构：
```bash
# 检查导出的数据集是否包含 language_instruction 字段并完成单调性诊断
python3 training/scripts/inspect_dataset.py \
  --dataset data/release/panda_sorting_dataset_v0 \
  --schema configs/robot_schemas/panda_multi_task.yaml
```

---

## 4. 多任务策略训练启动

轻量 smoke baseline（CI / 无 torch 环境优先使用）：
```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/release/panda_sorting_dataset_v0 \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --output checkpoints/panda_multi_task_policy
```

真实 LeRobot ACT 训练（需要 `environment-train.yml` 或等价 lerobot 环境）：
```bash
python3 training/scripts/train_act_lerobot.py \
  --dataset data/release/panda_sorting_dataset_v0 \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --output checkpoints/panda_multi_task_act \
  --epochs 50 \
  --batch-size 16 \
  --chunk-size 50 \
  --text-encoder clip
```

线性 baseline 训练完成后，先生成 replay，再打包为下游 bridge handoff：
```bash
python3 training/scripts/replay_policy.py \
  --dataset data/release/panda_sorting_dataset_v0 \
  --checkpoint checkpoints/panda_multi_task_policy/checkpoint.npz \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --output checkpoints/panda_multi_task_policy/predicted_actions.jsonl
```

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/release/panda_sorting_dataset_v0 \
  --replay checkpoints/panda_multi_task_policy/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda_multi_task.yaml \
  --output checkpoints/bridge_handoff/panda_multi_task_handoff_v0
```
