# Policy Onboarding Preflight Fixture

这是解决方案架构 PoC 使用的纯 CPU 合同 fixture，不加载模型、不启动 ROS/仿真，也不授权训练、真实机器人或任务成功声明。

结构：

```text
policy_onboarding_fixture/
├── base/                       # 一份合法、可做 SHA 校验的策略接入包
│   ├── artifacts/policy.ckpt  # 29-byte 文本占位产物，不是真实 checkpoint
│   ├── policy_identity.yaml
│   ├── observation_schema.yaml
│   ├── action_schema.yaml
│   ├── runtime_contract.yaml
│   ├── artifact_manifest.json
│   ├── adapter_mapping.yaml
│   ├── sample_action.json
│   └── commands.jsonl
└── cases/                      # 对 base 做单一、显式、内存内故障注入
    ├── valid_bundle.json
    ├── invalid_action_dim.json
    ├── invalid_hash.json
    └── invalid_sequence.json
```

一键运行：

```bash
python3 scripts/run_policy_onboarding_poc.py \
  --output-dir /tmp/policy_onboarding_poc
```

预期：合法包 Pass；action dim/hash 为 Invalid；sequence regression 为 Hold。命令自身在四个实际结果均匹配冻结预期时退出 `0`，负向 case 被正确拒绝仍属于 PoC Pass。

单包 CLI 退出码：`0=pass`、`2=hold`、`3=invalid`、`4=validator could not run`。

**Not task success / Not Sim2Real / Not real robot**。
