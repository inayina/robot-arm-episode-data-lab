# SmolVLA B Execution Handoff Audit

Status: Stage 5 partial, evidence-bounded audit. This is a midstream data and
inference-contract report; it does not own an Isaac controller.

## Contract from current HEAD

`training/smolvla_s3/runtime_s4.py` defines B as
`absolute_eef_gripper_v0`: action `[x, y, z, qx, qy, qz, qw, gripper]`,
`xyzw`, action dimension 8, chunk length 10, execute-K 5, and policy rate
10 Hz. `training/smolvla_s3/state15.py` defines state15 as joint position 7,
EE pose 7 (xyzw), and measured gripper 1.

`training/adapters/upstream_m6.py` directly preserves an upstream action8 when
`derive_ee_delta_action=False`; only the explicit true branch derives the
separate `ee_delta_gripper[7]` representation. B absolute action8 must not be
passed to the downstream delta7 replay contract.

## Training action provenance

The successful source metadata calls the action `ee_pose_gripper_cmd_v1` and
identifies `/teleop/cmd_pose` as its source. Upstream
`batch_generator.py` creates that `PoseStamped` in `panda_link0` after using
the `panda_link0 -> panda_ee` TF relation for target validation. Upstream
`recorder_node.py` copies the command pose and gripper directly into XYZW
action8; it does not apply a TF transform. Therefore:

- `TRAINING_ACTION_BASE_FRAME = panda_link0`
- `TRAINING_ACTION_REFERENCE_POINT = panda_ee`
- `TRAINING_ACTION_IS_PANDA_EE = CONFIRMED`

The known `panda_link7 -> panda_hand -> panda_ee` fixed chain is consequently
not evidence of a B action-reference mismatch and was not compensated.

## B release, open-loop and quaternion evidence

The local canonical artifact
`runs/smolvla_wrist_ablation_v1_B/openloop_canonical_full_20260818/s3_open_loop_report.json`
audits checkpoint config as state15/action8, chunk 10/K 5 and two visual
inputs. Its canonical first-action outcome is not a closed-loop result:

- EE RMSE: 0.0424170 m;
- quaternion angular error: 0.00267686 rad;
- gripper balanced accuracy: 0.995038;
- raw gripper out-of-bounds rate: 0.185706;
- canonical evaluator does not execute an action chunk queue.

The report's `frame_logs.raw_pred` is postprocessed output, not an unprocessed
neural head. Across 3,274 recorded postprocessed quaternions, norms are:

| statistic | value |
| --- | ---: |
| min / p01 / p05 | 0.999950815 / 0.999962405 / 0.999970552 |
| median / p95 / p99 / max | 0.999999136 / 1.000003798 / 1.000006659 / 1.000024211 |
| mean abs norm error | 0.000006513 |
| near-zero / non-finite / within-episode sign flips | 0 / 0 / 0 |

The 8,731 source training action quaternions are unit to floating-point
precision (min 0.9999999999999992, max 1.0, mean absolute norm error
3.53e-16), with no non-finite or near-zero sample.

Code audit found a documentation/code difference: `clamp_absolute_action8()`
in the midstream S4 runtime only clamps XYZ and gripper, but upstream
`bound_absolute_eef_gripper()` normalizes the quaternion before its ROS target
is created. Thus bounded-midstream norm equals postprocessed norm for a common
input, while the final upstream target is unit by code. A raw-head and emitted
B ROS-sample statistic is unavailable; it is not fabricated here.

## Initial distribution

From all 36 B release training episode first frames, the joint-q0 mean is
`[-0.000043, -0.785021, 0.000028, -2.356069, 0.000020, 1.571049, 0.785009]`.
The Isaac nominal posture read from current upstream HEAD,
`[0, -0.785, 0, -2.356, 0, 1.571, 0.785]`, lies within the observed q0
min/max for every joint, including J4 and J6. The same q0 was confirmed in the
local Isaac/ros2_control startup logs. Initial-joint OOD is therefore
`NOT_SUPPORTED` by q0 evidence. A full policy-input state15 sample was not
captured because the ROS adapter never formed a valid observation snapshot, so
full-state comparison remains `UNTESTED`.

## Remote GPU diagnostic and open-loop/remote parity

The remote GPU is now reachable and the real B 005460 checkpoint loaded on an
RTX 3090 using the remote `smolvla_s3` environment. A one-frame,
`queued_diagnostic` run loaded both scene and wrist inputs and executed the
LoRA forward. It recorded p50 latency 278.7 ms, p95 latency 280.8 ms, EE RMSE
0.01417 m and quaternion error 0.0009106 rad. The run was deliberately
non-canonical: the v3 prospective manifest was absent, so its gate decision
was `no_go`, and it is not task-success evidence.

The remote repository tree did not contain `remote_inference_server.py`; for
this bounded session, the existing local server file was copied as a single
runtime artifact, started on remote loopback, and reached `healthz=ready` over
an SSH tunnel. A same-observation open-loop-versus-remote-server 10x8
comparison was not yet run, so parity remains `UNTESTED`.

## Stage 5 local Isaac and learned-policy trace

The local Isaac runtime is now available on the RTX PRO 500 and the local
Franka USD is present. The fixed expert-target sequence completed in the
upstream repository: full-pose, position-only and orientation-only Servo
isolations converged to the same bounded target. The downstream PyBullet IK
witness independently solved the target with position residual `8.67e-7 m`,
rotation residual `1.86e-7 rad`, and positive J4/J6 margins. These results
support the target/frame/branch contract for this witness only; they do not
prove global Servo stability or task success.

One and only one bounded B learned-policy seed was then attempted through the
remote RTX 3090 server and SSH tunnel. The runtime used the dual-camera
state15/action8 contract, chunk10/K5, asynchronous inference, warmup and
authoritative execution. Isaac itself reached its bounded
`ISAAC_E1_DONE status=PASS`, but the ROS adapter remained at
`waiting for /isaac/joint_states`; Servo reported no robot-state update. The
policy log contains no action or prediction completion, and
`trials/seed_1/telemetry/observations.jsonl` is empty. GT ended with all four
subgoals false. This run is `PRECONDITION_BLOCKED`, not a B task-success or
task-failure sample, and no second seed is authorized.

## Stage 5 handoff

No retraining, collection, camera or geometry change is justified by this
audit. The B model itself is proven loadable and executable on the remote GPU;
the remaining gate is live ROS bridge evidence, followed by at most a repeat
of the same single seed. The existing downstream delta7 replay contract is
unchanged.
