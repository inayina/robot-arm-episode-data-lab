# Mixed Recovery MuJoCo Provenance Correction

**Status:** `OPEN P0 EVIDENCE RESIDUAL / NO RERUN AUTHORIZED`  
**Date:** 2026-08-21  
**Applies to:** `evidence/smolvla_mixed_mujoco_trainid_20260821T_final/`

## Verified facts

- The immutable mixed release is
  `smolvla_s3_mixed_recovery_v2_20260821T` with 64 episodes and 14,736 frames.
- The reported formal-training checkpoint is step `007545`; its adapter SHA256 is
  `49d01a4445a59b066558af8472b5d01f3e538767ada589f08b072aae80528981`.
- Its local static contract declares scene+wrist, `state[15]`, absolute EEF action[8],
  chunk 10 and `n_action_steps=5`.
- The four MuJoCo final bundles contain continuous Task GT observations: Reach 1/4,
  Grasp 0/4 and Lift 0/4. Those observations must not be promoted to task success.

## Metadata conflict

`P0/run_manifest.json` and the per-case `policy/checkpoint_metadata.json` retain
metadata for the older B experiment: a `005460`-era adapter SHA, training run id,
and `smolvla_wrist_ablation_v1_B` release. This conflicts with the report's claim
that the remote server loaded final mixed-recovery checkpoint `007545`.

## Current classification

`EVIDENCE_PROVENANCE_METADATA_CONFLICT`

This is not a release-schema failure, a recovery-data failure, or proof that the
Task GT observations are false. It prevents a clean statement that the four final
MuJoCo outcomes have been independently attributed to `007545`.

## P0 closure rule

Do not modify immutable evidence paths and do not rerun training or MuJoCo merely to
hide this conflict. A later evidence-only closure may reconstruct server-side
checkpoint identity from existing raw logs. If that is impossible, retain the
outcome as a reported runtime observation with incomplete checkpoint attribution.
