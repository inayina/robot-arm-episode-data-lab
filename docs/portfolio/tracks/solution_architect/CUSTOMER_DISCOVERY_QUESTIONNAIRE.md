# Customer Discovery Questionnaire

**版本**：v0.1  
**用途**：在设计 PoC 前冻结客户目标、策略合同、环境、安全边界、预算和验收责任。  
**输出**：完成后的答案应汇总到 `templates/solution_scope.template.yaml`。  
**边界**：问卷完成不等于技术可行性已验证，也不授权真机、训练或仿真执行。

返回：[解决方案架构文档包](README.md)

---

## 1. 业务与决策

1. 客户要解决的业务/科研问题是什么？
2. 当前流程在哪一步最慢、最贵或最不可解释？
3. 这次 engagement 的决策是什么：是否继续训练、是否进入仿真、是否接入硬件，还是仅完成风险审计？
4. 成功后的可测结果是什么？哪些只是长期愿景？
5. 哪类失败不可接受：碰撞、误闭爪、超时、数据泄漏、错误报告、成本超支？
6. 谁是业务 owner、技术 owner、验收 owner 和最终签字人？

### 输出字段

```yaml
business_problem: ""
decision_to_make: ""
measurable_outcomes: []
unacceptable_failures: []
executive_owner: ""
technical_owner: ""
acceptance_owner: ""
```

---

## 2. Use Case 与任务真值

1. 任务是 reach、pick、lift、place，还是纯轨迹 replay？
2. 任务开始和结束条件是什么？
3. reach/grasp/lift/place 分别由哪些测量定义？
4. Task GT 来自 simulator privileged state、传感器、人工标注还是业务系统？
5. Task GT 缺失时，客户是否接受只出 interface/readiness 报告？
6. 允许的任务范围、物体、位置、背景、相机和动力学变化是什么？
7. 需要报告点估计、置信区间还是仅 Go/Hold/No-Go？

**硬约束**：没有连续 Task GT 时，不得把动作完成、risk 健康或 replay 完成改写为任务成功。

---

## 3. Robot、控制与执行

| 问题 | 客户答案 |
|---|---|
| Robot model / URDF / SRDF | |
| Joint names/order/limits | |
| EE/tool frame | |
| Gripper command/state semantics | |
| Control mode（position/velocity/effort/Cartesian） | |
| Control / Servo / policy rate | |
| Workspace / velocity / acceleration limits | |
| IK / execution adapter owner | |
| Hold / E-stop / recovery semantics | |
| Simulation / hardware backend | |

需要明确区分：policy inference rate、chunk scheduler rate、command rate、controller rate 和 physics rate。

---

## 4. Policy 与模型产物

1. policy 名称、版本、框架、checkpoint 格式和 SHA256 是什么？
2. observation schema、字段顺序、shape、dtype、单位和 normalization 是什么？
3. camera key、分辨率、颜色空间、帧率和缺帧语义是什么？
4. action schema 是 absolute EEF8、delta EEF7、joint target 还是其它？
5. quaternion 顺序、坐标系、gripper 范围是什么？
6. chunk size、execute K、replan period、reset 语义是什么？
7. inference latency 的 p50/p95、timeout 和 warm-up 是什么？
8. 依赖、GPU、显存、license 和外部下载要求是什么？
9. policy 是否允许 shadow only？何时允许 authoritative cutover？

未知 channel slice 或 action 语义必须标记 `invalid`，不得“按惯例猜测”。

---

## 5. 数据与评测治理

1. 数据来自何处，是否有 `upstream_gate`、success 和安全标签？
2. train/validation/benchmark 如何切分？是否按 episode 分割？
3. 是否存在阈值设计污染或同一 episode 跨 split？
4. release 是否只有 non-overwrite，还是包含逐文件 SHA 和 content fingerprint？
5. privileged 信息是否进入 policy state？
6. 缺失图像、丢帧、时间戳回退和反向动作如何处理？
7. 历史结果如何标注 Current / Historical / Invalidated / Superseded？
8. 数据和模型的 retention、删除和访问权限是什么？

---

## 6. 集成与环境

| 类别 | 需要确认 |
|---|---|
| OS / ROS | 发行版、内核、Python/C++、ROS domain |
| ML stack | framework、CUDA、driver、依赖 lock |
| Simulation | backend、版本、headless/EGL、GPU |
| Middleware | DDS vendor、QoS、网络、时间同步 |
| Artifact | registry、下载方式、校验和、缓存 |
| Observability | logs、trace、metrics、video、retention |
| CI/CD | tests、artifact promotion、rollback |
| Security | secrets、network、IAM、license、PII |

当前项目不默认承诺 cloud、multi-tenant、HA、IAM 或 production hardening；客户如需要，必须独立纳入 scope。

---

## 7. 安全与现场约束

1. 是否只做 CPU/offline、mock/replay、bounded simulation，还是涉及硬件？
2. 谁拥有 physical E-stop、安全 PLC、控制柜和现场操作权？
3. software Hold、DS402 Quick Stop 和 physical E-stop 如何分工？
4. command stale、joint state stale、NaN/Inf、limit、timeout 的默认动作是什么？
5. 故障恢复是否需要 operator acknowledgement？
6. 哪些测试只能由具备资质的现场人员执行？
7. 现场是否有独立安全评审和保险/合规要求？

涉及真机时，仿真证据只能作为 precheck，不能替代现场安全验收。

---

## 8. PoC 范围、预算与停止条件

| 项 | 客户答案 |
|---|---|
| PoC 开始/结束日期 | |
| CPU/GPU/仿真预算 | |
| 最大数据/seed/rollout 数 | |
| 允许的代码/配置修改 | |
| 禁止动作 | |
| Pass/Hold/No-Go 判据 | |
| 失败后的默认停止动作 | |
| 需要升级决策的事项 | |

必须在执行前写明：何时停止、何时需要追加授权、哪些结果永远不能升级为任务成功。

---

## 9. RACI

| 工作项 | Customer Business | Customer Algorithm | Customer Platform | Solution Architect | Safety/QA |
|---|---|---|---|---|---|
| Scope / outcome | A | C | C | R | C |
| Policy identity | I | A/R | C | C | I |
| Data release | I | A/R | C | C | C |
| Runtime adapter | I | C | A/R | C | C |
| Task GT | C | C | A/R | C | A/C |
| Safety decision | I | I | R | C | A |
| Acceptance report | A | C | C | R | A/C |
| Production cutover | A | C | R | C | A |

`A`=Accountable，`R`=Responsible，`C`=Consulted，`I`=Informed。实际项目必须替换角色名称，不得保留空泛的“团队负责”。

---

## 10. Discovery Exit Criteria

只有同时满足以下条件才进入 PoC：

- decision、success criteria、non-goals 已签字；
- policy/data identity 可提供或明确列为 blocker；
- Task GT 权威和缺失时的降级口径已确认；
- 资源、预算、停止条件和禁止项已冻结；
- RACI、artifact ownership 和 retention 已确认；
- 真机/付费/GPU/仿真等新权限已单独获得。

