# Canonical v3 public evidence bundle

这是可直接提交到公开仓库的最小机器可读证据包。它从本地权威运行产物中做字段级摘录，删除本机绝对路径，并在 `provenance.json` 中固定每个原始文件的 SHA256。

公开包能证明：Recovery v3 的 prospective canonical first-action open-loop Gate 为 Pass；immutable release 与 checkpoint contract 有 SHA 锁定；修光后 bounded Isaac S4 的接口为 5/5、任务 lift 为 0/5，因此结论为 Hold；统一信封不把这些结果升级为任务成功。

公开包不能证明：在线自主抓取、Sim2Real、真机部署、统计显著成功率，或原始视频/逐帧预测的完整性。需要审计逐帧数据时，应按 `provenance.json` 的 SHA 获取原始运行归档。

文件：

- `open_loop_gate_summary.json`：open-loop Gate、关键指标、prospective 合同。
- `release_checkpoint_summary.json`：immutable release fingerprint、split 与 checkpoint audit。
- `s4_gate.json`：权威 bounded S4 漏斗。
- `s4_per_seed_summary.json`：去本机路径后的五个 seed 任务结果。
- `unified_eval_summary.json`：open-loop、PolicyRunner、Isaac 三后端分栏。
- `provenance.json`：原始文件 SHA256 和摘录规则。

所有 `claims_*` 字段必须保持 `false`。完整复现命令见 [FINAL_PROJECT_SUMMARY.md §7](../../FINAL_PROJECT_SUMMARY.md#7-复现与追溯)。
