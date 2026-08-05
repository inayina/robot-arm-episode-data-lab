# 8 分钟 PoC Demo Script

**版本**：v0.3  
**状态**：Script + executable fixtures + two-run timed CPU rehearsal complete；recorded demo pending  
**默认模式**：CPU contract tests + frozen evidence remap；不启动 ROS、GPU、Isaac 或真实策略 authoritative execution。  
**结论边界**：演示证明验证方案和证据治理，不证明任务成功、Sim2Real 或生产部署。

返回：[解决方案架构文档包](README.md)

---

## 0. 演示前准备

打开四个页面：

1. [SOLUTION_BRIEF.md](SOLUTION_BRIEF.md)；
2. [REFERENCE_ARCHITECTURE.md](REFERENCE_ARCHITECTURE.md)；
3. [CUSTOMER_ACCEPTANCE_MATRIX.md](CUSTOMER_ACCEPTANCE_MATRIX.md)；
4. [public evidence](../../public_evidence/canonical_v3/README.md)。

预先运行 CPU tests；若任何测试失败，本次演示标记 Hold，不临场改文件。

预先生成四个 onboarding 报告：

```bash
python3 scripts/run_policy_onboarding_poc.py \
  --output-dir /tmp/policy_onboarding_poc
```

双次演练权威证据见 [rehearsal README](../../../../evidence/solution_architect/policy_onboarding_rehearsal_20260730/README.md)：两次规范化结果一致；该计时不是完整 demo 或模型推理时延。

---

## 1. 时间线

### 0:00–1:00：客户问题

讲述：

> 客户有一个离线指标不错的机器人策略，但不知道上线失败来自数据、动作合同、执行接口、仿真物理还是策略闭环。我们的目标不是替客户宣布成功，而是让每一层只回答自己的问题，并在昂贵执行前尽可能早地拦截错误。

展示 Solution Brief 的六层表。

### 1:00–2:00：Reference Architecture

展示客户旅程和三仓图，强调：

- 中游拥有合同和证据口径；
- 上游拥有在线执行和 Task GT；
- 下游 PolicyRunner 只做 replay harness；
- Risk 可以 Hold/E-stop，但不能改 Task GT。

### 2:00–3:00：Onboarding / Fail Closed

展示 [POLICY_ONBOARDING_GUIDE.md](POLICY_ONBOARDING_GUIDE.md) 的 G0–G7：

- 正确策略包应声明 identity、obs/action、runtime、hash 和 adapter；
- unknown action、dim mismatch、hash mismatch、sequence regression 必须 invalid/Hold；
- 展示 `poc_summary.json`：valid=Pass、dim/hash=Invalid、sequence=Hold；
- 强调聚合命令 Pass 的含义是四个案例均符合预期，不是错误包被放行。

可运行的现有合同回归：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_policy_runtime_contract.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_policy_trace_bundle_contract.py
```

### 3:00–4:15：Interface 不等于 Task

展示 unified report 三后端：

- open-loop：Pass；
- PolicyRunner：smoke complete，`is_closed_loop=false`；
- Isaac S4：interface 5/5，但 lift 0/5，Hold。

讲述：

> 同一份报告允许三个结果同时为真，因为它们回答不同问题；这避免把“动作发出去了”包装成“物体被抓起来了”。

### 4:15–5:15：Safety Wiring

展示 M6 frozen evidence：R0 EXECUTED、R2 HELD、R3 ESTOPPED。

明确：这是 mock policy 经真实 ROS/DDS 的 wiring evidence，不证明物理控制器、执行器或真实急停已经验收。

### 5:15–6:30：Badcase / 信息增益

讲述同 seeds relight：

1. 首轮输入近黑，reach 3/5、grasp 1/5；
2. 修光后同 seeds 复测降为 reach 1/5、grasp/lift 0/5；
3. 首轮被标记 Superseded；
4. scripted oracle 5/5 证明名义物理链可用；
5. 结论倾向闭环 BC，但 1-seed MuJoCo 对照不足以证明唯一根因。

价值：用观测和对照先减少盲目重训，而不是美化指标。

### 6:30–7:30：Acceptance / Handoff

展示验收矩阵：

- 每层 Pass/Hold/No-Go；
- evidence、owner、residual risk；
- next allowed stage；
- explicitly prohibited stage。

当前示例的总体结论是 readiness evidence available / Task Hold，不是 Go to production。

### 7:30–8:00：边界与下一步

讲述：

> 当前已经具备合同、release、评测信封、replay、风险、M6 wiring 证据以及通过双次一致性演练的 CPU onboarding preflight。下一步产品化工作是录制完整 PoC 并组织第三方复现；真实模型切流、Isaac 新运行和真机都需要单独批准与验收。

---

## 2. 演示验收

| ID | 条件 |
|---|---|
| POC-01 | 8 分钟内完成，不临场修改 evidence |
| POC-02 | 至少一次明确说出 interface != task |
| POC-03 | mock/replay/fixture/HW Pending 标签可见 |
| POC-04 | 所有数字来自 canonical evidence |
| POC-05 | next step 与停止条件明确 |
| POC-06 | 如启动任何 ROS/sim，完成 timeout 和 Nuke On Done |

---

## 3. 录制版本待办

- 录制 1080p 屏幕和清晰语音；
- 准备中文 8 分钟、英文 5 分钟两个版本；
- 用实际四案例 `poc_summary.json` 替换 2:00–3:00 的纯文档展示；
- 不剪掉失败/警告来制造全绿印象；
- 片尾固定显示 **Not task success / Not Sim2Real / Not real robot**。
