# SmolVLA Stage 5 Root-Cause Report

Status: partial Stage 5. Fixed-target and cross-backend isolation completed.
The single allowed B learned-policy trace was blocked before its first valid
observation by the local Isaac-to-ROS adapter path. This report deliberately
separates contract evidence from task-success evidence.

## Result

The present evidence does not support retraining or an execution-contract
change. It supports restoring the required remote and Isaac environments, then
running the ordered fixed-target and cross-backend experiments.

| hypothesis | evidence | status | implication |
| --- | --- | --- | --- |
| H1 initial joint posture / state15 OOD | Isaac nominal q0 lies within all 36 B training q0 ranges; full Isaac state15 unmeasured | NOT_SUPPORTED for q0; UNTESTED for full state15 | do not change home posture |
| H2 MoveIt Servo redundant IK/null-space branch | fixed full/position/orientation targets converged; PyBullet witness agrees on the expert target | NOT_SUPPORTED for this target; not global | do not change solver or geometry |
| H3 online quaternion norm/rotation contract | B postprocessed quaternions are near unit; upstream normalizes final target | NOT_SUPPORTED at observed postprocess layer | raw-head/ROS sample still needed for closure |
| H4 training EEF reference differs from Servo EEF | source target is `panda_link0` / `panda_ee`; Servo tip is `panda_ee` | NOT_SUPPORTED | no 0.207 m compensation |
| H5 open-loop versus remote preprocessing drift | remote B forward now runs, but remote tree has no remote inference server | INSUFFICIENT_DATA | require same-frame 10x8 parity fixture |
| H6 command multiple writer | authoritative adapter enforces one publisher; S4 disables teleop start; learned trace produced no command | SUPPORTED static single writer; learned live path not reached | first prove ROS observation path |
| H7 stale chunk/timing | policy log stopped after discarded warmup; no observation/action/remote completion trace | NOT_REACHED | do not attribute to chunk timing |
| H8 expert target intrinsically dangerous | PyBullet and local Isaac fixed-target witnesses solve the same target with margin | NOT_SUPPORTED for that target only | not a global task conclusion |
| H9 closed-loop observation distribution shift | learned trace telemetry is empty because ROS adapter never formed a snapshot | NOT_REACHED | analyse only after bridge evidence |
| H10 B open-loop residual around 4.2 cm | canonical B report records 0.042417 m EE RMSE | SUPPORTED | performance limitation, not execution root cause |
| H11 camera-view distribution difference | B dual-input audit passes; learned trace has zero observation telemetry and adapter did not reach live raw topics | INSUFFICIENT_DATA | do not call calibration failure |

## Explicitly excluded actions

No retraining, data recollection, camera/geometry alteration, URDF edit, joint
limit change, Servo solver replacement, gain tuning, seed expansion, or action
semantic change was performed. The downstream delta7 production replay
contract remains unchanged.

## Next gate

`ISAAC_ROS_BRIDGE_EVIDENCE_REQUIRED` remains. The B checkpoint is loadable on
the remote RTX 3090, the local Isaac/Franka runtime is confirmed, and the
fixed-target sequence is complete. Before any new learned trace, prove that
the ROS adapter receives `/isaac/joint_states`, scene RGB and wrist RGB in the
same ROS domain and republishes the canonical topics. Then, and only then, a
repeat of the same single B seed may be considered. No retraining, recollection,
seed expansion, geometry change or control tuning is justified.
