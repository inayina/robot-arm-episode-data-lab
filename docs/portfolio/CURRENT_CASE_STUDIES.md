# Current Case Studies

**Authority:** This is a recruiter-facing extraction from
[THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md), not a second
current-facts source. Current as of 2026-08-21.

## 1. Targeted Recovery Data Intervention

**Problem.** A learned Panda policy did not reliably approach or grasp in
closed-loop states it had visited.

**Intervention.** The execution repository replayed continuous `EXECUTED`
policy prefixes, selected visited states, and used a scripted oracle to collect
recovery trajectories under Scene Contract v2. The data repository QA-locked
24 recovery episodes (16 train / 8 validation), mixed them with the original
release into an immutable 64-episode / 14,736-frame release, and completed a
7,545-step LoRA training run.

**Verification.** Four same-environment MuJoCo cases each completed 100
authoritative-runtime actions with continuous Task GT.

**Result.** Reach `1/4`, Grasp `0/4`, Lift `0/4`; gripper minima all exceeded
`0.93`. The intervention pipeline is reproducible, but the learned policy did
not solve stable grasping.

**Boundary.** Scripted-oracle GT validates the recovery label/task chain, not
the learned policy. The final evaluation bundles contain stale B checkpoint
metadata, so exact attribution to the new `007545` adapter remains an open
evidence residual; see
[provenance correction](../SMOLVLA_MIXED_RECOVERY_PROVENANCE_CORRECTION.md).

## 2. Cross-Backend Execution Chain Fault Isolation

**Symptom.** A bounded Isaac run of dual-camera B did not produce valid learned
policy behavior.

**Checks.** The team separated checkpoint/action contract, `panda_link0` to
`panda_ee` frame semantics, fixed-target MoveIt Servo convergence, a PyBullet
IK witness, single-writer enforcement, remote inference, and ROS observations.

**Finding.** Remote warmup forward reached the inference service and Isaac ran,
but the adapter remained blocked waiting for `/isaac/joint_states`; canonical
observation telemetry was empty and no observation-driven learned command
entered execution.

**Conclusion.** The original B run is `EXECUTION_CHAIN_PRECONDITION_BLOCKED`,
not a learned-policy task failure. A subsequent bounded non-policy bridge probe
did prove non-empty raw/canonical/control-state topics and a deterministic
command path. It does not retroactively validate B or authorize a learned-policy
task rollout; the system stops at interface closure.
