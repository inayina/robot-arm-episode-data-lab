# Customer Acceptance Matrix

**版本**：v0.1  
**用途**：把 Discovery、Preflight、Offline、Interface、Behavior、Task、System 和 Handoff 转化为可签字验收项。  
**边界**：本矩阵是解决方案验收模板，不改变任何既有 Gate；未运行的阶段必须标记 `NOT_RUN`。

返回：[解决方案架构文档包](README.md)

---

## 1. 状态语义

| 状态 | 含义 |
|---|---|
| `PASS` | 该验收项在冻结协议和证据范围内通过 |
| `HOLD` | 证据不足或存在可整改问题；停止进入下一高风险阶段 |
| `NO_GO` | 硬门禁失败；不得继续 |
| `INVALID` | 协议、身份、测试器或 provenance 无效，结果不得使用 |
| `NOT_RUN` | 未执行；不能按行业惯例补全 |
| `N/A` | 经双方确认不适用，并记录理由 |

`PASS` 只能回答本层问题，不能向上升级为 Task success、Sim2Real 或 production ready。

---

## 2. Discovery 与 Scope

| ID | 验收项 | Evidence | Owner | Pass 条件 | 当前模板状态 |
|---|---|---|---|---|---|
| DIS-01 | business decision 明确 | Solution Scope | Customer Business | 决策、时间、owner 明确 | NOT_RUN |
| DIS-02 | use case / Task GT 明确 | GT definition | Customer Platform/QA | 权威来源和缺失降级规则明确 | NOT_RUN |
| DIS-03 | in/out scope 冻结 | scope.yaml | Solution Architect | non-goals、assumptions、dependencies 完整 | NOT_RUN |
| DIS-04 | 资源与预算 | cost template | Customer Business | CPU/GPU/仿真/人工额度明确 | NOT_RUN |
| DIS-05 | 停止条件与 RACI | signed matrix | All owners | P0 决策 owner 唯一 | NOT_RUN |

---

## 3. Policy / Data Preflight

| ID | 验收项 | Evidence | Pass 条件 | 失败动作 |
|---|---|---|---|---|
| PRE-01 | policy identity | `policy_identity.yaml` | name/version/artifact/release 完整 | INVALID |
| PRE-02 | artifact integrity | manifest/hash report | required hash 全匹配 | INVALID |
| PRE-03 | observation schema | schema + cross-check | key/order/shape/norm/camera 一致 | INVALID |
| PRE-04 | action schema | schema + sample | version/dim/channel/frame 一致 | INVALID |
| PRE-05 | runtime contract | runtime YAML | chunk/K/rate/TTL/reset 合法 | HOLD/INVALID |
| PRE-06 | adapter mapping | mapping + tests | 具名、版本化、无隐式切片 | INVALID |
| PRE-07 | data split/provenance | inspection/release | 无已知 overlap，来源可追溯 | NO_GO |
| PRE-08 | claims | preflight report | `claims_*=false` | INVALID |

---

## 4. 六层验证

| ID | Layer | 客户问题 | Required Evidence | Pass 条件 | 不可证明 |
|---|---|---|---|---|---|
| VAL-01 | Data | 数据可训练、可复现吗？ | inspection、manifest、split、SHA | schema/split/health 通过 | 策略成功 |
| VAL-02 | Offline | 冻结专家态上预测过线吗？ | metrics、gate、checkpoint audit | 冻结 Gate Pass | 闭环 |
| VAL-03 | Interface | 能加载、映射和执行吗？ | replay/wiring/latency/clip | 合同要求通过 | 物体被抓起 |
| VAL-04 | Behavior | 动作和时序合理吗？ | EE/grip/phase trace | 预注册 behavior criteria | lift/place |
| VAL-05 | Task | 是否物理完成？ | continuous Task GT | 冻结 bounded protocol Pass | 真机/Sim2Real |
| VAL-06 | System | 运行与安全链健康吗？ | QoS/deadline/risk/cleanup | system criteria Pass | Task success |

---

## 5. 故障注入与恢复

| ID | 场景 | 期望 | Evidence | 当前项目证据 |
|---|---|---|---|---|
| FI-01 | nominal / R0 | EXECUTED | policy/execution trace | M6 mock Pass |
| FI-02 | risk R2 | HELD | risk→hold→execution trace | M6 mock Pass |
| FI-03 | risk R3 | ESTOPPED | risk→estop→safety trace | M6 mock Pass |
| FI-04 | unknown action schema | reject/invalid | preflight/runtime report | schema tests exist |
| FI-05 | action dim invalid | reject | validator error | CPU onboarding fixture Pass |
| FI-06 | TTL expired | Hold/reject | reason code + trace | contract/tests exist |
| FI-07 | sequence regression | Hold/reject | reason code + trace | CPU onboarding fixture Pass |
| FI-08 | recovery | operator ack + controlled reset | recovery evidence | Hardware Pending for real robot |

M6 结果不证明物理力矩归零；真实 E-stop 与 recovery 必须现场验收。

---

## 6. 非功能验收

| ID | NFR | 目标 | 测量 | 状态 |
|---|---|---|---|---|
| NFR-01 | Auditability | 核心产物含 version/path/SHA | provenance completeness | 待客户项目实测 |
| NFR-02 | Reproducibility | 两次规范化结果等价 | normalized report diff | CPU onboarding rehearsal Pass（仅合同 fixture） |
| NFR-03 | Observability | 四泳道可关联 | trace completeness | M5/M6 有历史证据 |
| NFR-04 | Fail closed | invalid/stale/unknown 不执行 | negative fixtures | dim/hash/sequence CPU fixtures Pass；其它场景按各自合同证据 |
| NFR-05 | Operability | 启停/cleanup/rollback 可执行 | runbook drill | 文档完成，drill 待跑 |
| NFR-06 | Performance | latency/deadline 分栏 | p50/p95/miss ratio | 有历史数字，非 SLO |
| NFR-07 | Security | secrets/license/access/retention 清单 | checklist | 设计要求，未认证 |
| NFR-08 | Cost | 资源与人工可估算 | cost sheet | 模板完成，数据待填 |

---

## 7. 当前项目示例裁决

| Backend / Layer | 当前结果 | 客户解释 |
|---|---|---|
| SmolVLA open-loop / Offline | PASS | expert-state first-action 通过 |
| PolicyRunner / Interface | smoke complete | handoff/replay 接口可复用，`is_closed_loop=false` |
| Isaac S4 / Task | HOLD | interface 5/5，但 lift 0/5 |
| M6 / System | wiring PASS | R0/R2/R3 裁决链有效，mock only |

总体不能写 `GO TO PRODUCTION`；当前只支持分层 readiness 与 Hold 结论。

---

## 8. Handoff Sign-off

最终报告必须记录：

- 每个验收项状态、evidence path、owner、timestamp；
- unresolved P0/P1/P2 issues；
- residual risks；
- next allowed stage；
- explicitly prohibited stage；
- Customer、Solution Architect、QA/Safety 签字；
- claims/non-claims。

模板见 [templates/acceptance_report.template.yaml](templates/acceptance_report.template.yaml)。
