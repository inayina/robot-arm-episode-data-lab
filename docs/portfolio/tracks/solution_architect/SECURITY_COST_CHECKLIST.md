# Security, Compliance and Cost Checklist

**版本**：v0.1  
**状态**：Template / design requirements  
**边界**：当前项目未取得安全、隐私、云、生产或硬件合规认证，也不证明任务成功（Not task success）；本清单用于发现缺口，不能作为认证报告。

返回：[解决方案架构文档包](README.md)

---

## 1. Data Security

| 检查 | Owner | Evidence | Status |
|---|---|---|---|
| 数据分类（public/internal/confidential/PII） | | | NOT_RUN |
| raw episode 与视频访问控制 | | | NOT_RUN |
| train/eval/handoff 最小权限 | | | NOT_RUN |
| 加密 at rest / in transit | | | NOT_RUN |
| retention 与删除责任 | | | NOT_RUN |
| 对外 evidence 脱敏 | | | NOT_RUN |
| 日志是否包含路径、token、用户信息 | | | NOT_RUN |
| artifact 下载来源与完整性 | | | NOT_RUN |

默认公开包只包含最小 JSON、hash、摘要和生成命令，不公开完整 dataset/checkpoint/video，除非 license 和授权允许。

---

## 2. Secrets 与 Identity

- token、SSH key、registry credential 不得进入 Git、manifest、log 或截图；
- 外部模型/数据下载必须使用受控 secret store；
- artifact producer/consumer/owner 必须可追踪；
- 共享工作站需要最小权限和运行目录隔离；
- 真机命令权限与普通评测权限必须分离；
- operator acknowledgement 不得由 policy 自动伪造。

当前仓库没有完整 IAM/RBAC 实现；对外只能说“定义要求”，不能说“已企业级接入”。

---

## 3. License 与供应链

| 项 | 要求 |
|---|---|
| 源码 | repo/package license 清单 |
| 模型 | model card、weight license、附加条款 |
| 数据 | 来源、采集授权、再发布限制 |
| 容器/依赖 | version lock、漏洞扫描、SBOM（待实现） |
| GPU/driver | 支持矩阵与可复现版本 |
| 外部服务 | 数据出境、日志、计费和 SLA |

未下载或未逐文件检查的权重不能写“license fully verified”。

---

## 4. Robot Safety / Compliance

- software Hold ≠ safety-rated stop；
- DS402 Quick Stop ≠ physical dual-channel E-stop；
- simulation wiring ≠ real actuator torque-off；
- PREEMPT_RT/config tests ≠现场 WCET/jitter 验收；
- virtual EMCY ≠ master-side real EMCY/Bus-Off recovery；
- 真机需要独立风险评估、机械/电气检查、限速、围栏/区域、操作员培训和签字。

所有真实硬件条目当前均为 Hardware Pending。

---

## 5. Threat Scenarios

| Threat | Impact | Control | 当前状态 |
|---|---|---|---|
| checkpoint 被替换 | 错误策略执行 | SHA + manifest + audit | 部分实现 |
| schema 被静默修改 | action 语义漂移 | version + lock + fail closed | 已有合同 |
| replay 被当在线成功 | 错误业务结论 | `is_closed_loop=false` + claims | 已有约束 |
| GT 被 risk 覆盖 | 隐藏任务失败 | ownership + failure lane | 已有约束 |
| stale command 重放 | 运动风险 | TTL + sequence | 合同/测试；真机待验 |
| secret 泄漏 | 供应链/账户风险 | secret hygiene | 流程要求 |
| evidence 被覆盖 | 审计失真 | non-overwrite/immutable/history | 部分实现 |

---

## 6. Cost Model

成本必须分开估算：

```text
Total = engineering_hours
      + CPU_hours × CPU_rate
      + GPU_hours × GPU_rate
      + simulation_hours × sim_rate
      + storage_GB_month × storage_rate
      + artifact_egress
      + hardware/lab/operator
      + contingency
```

模板见 [templates/cost_estimate.template.yaml](templates/cost_estimate.template.yaml)。

### 成本驱动因素

| 阶段 | 主要成本 | 止损杠杆 |
|---|---|---|
| Discovery | 架构/算法/QA 人时 | 提前冻结 scope |
| Preflight | CPU 与工程人时 | 自动拦截 dim/hash/split |
| Offline | GPU inference/training | 先 audit，再跑；冻结 stop rule |
| Simulation | GPU/EGL/rollout | bounded seeds，不在 floor effect 扩样本 |
| Hardware | 设备、现场、Safety | 分阶段低速 bring-up |
| Reporting | 数据整理/审计 | schema + auto normalization |

---

## 7. ROI 表述规则

允许：

- “建议测量接入时间、拦截数、定位时间和避免的 rollout”；
- “本案例通过 Hold 决策没有自动启动 100+ rollout”；
- “该流程旨在减少盲目重训风险”。

禁止：

- 没有客户基线就声称节省 X%；
- 把未执行实验预算算成已节省现金；
- 把 task Hold 包装为产品成功率；
- 忽略 GPU、人工、维护和现场安全成本。

---

## 8. Exit Criteria

进入 pilot/production discussion 前至少满足：

- security/data/license owner 明确；
- artifact/hash/dependency audit 完整；
- cost assumptions 与上下界透明；
- P0 threats 有 control 和 evidence；
- residual risks 被签字接受；
- Hardware Pending 没有被仿真证据替代。
