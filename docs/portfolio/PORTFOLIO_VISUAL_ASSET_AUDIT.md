# Portfolio Visual Asset Audit

| Field | Value |
|---|---|
| Status | Audit complete. Render phase **P0 + optional recapture done**; Page 6 mini-flow skipped |
| Audit date | 2026-08-17 |
| Render date | 2026-08-17 |
| Render output | `docs/portfolio/assets/` |
| Scope | Three-repo Panda mainline visual assets for a ~6-page “仿真遥操作 / Robot Data Infrastructure” deck |
| Canonical location | **This file** (midstream). Do not triplicate into upstream/downstream unless a repo-local README needs a one-line pointer. |
| Upstream HEAD | `ros2-arm-teleoperation-suite` `f9f6eab` (2026-08-14) |
| Midstream HEAD | `robot-arm-episode-data-lab` `381cf71` (2026-08-05) |
| Downstream HEAD | `ros2-moveit-pybullet-bridge` `985c8da` (2026-08-05) |

## Purpose

Recruiters and interviewers need a small set of **true, checkable** visuals. This audit answers:

1. What visual assets already exist?
2. What is READY vs STALE / LEGACY?
3. What is missing for the 6-page narrative?
4. Which 3–5 figures should be drawn next, from which evidence, without inventing runs?

## Honesty rules (binding for later render phase)

Every portfolio figure must answer: **where did this come from?**

Allowed labels:

- `actual run screenshot / GIF / PNG`
- `architecture diagram based on current repository implementation`
- `visualization regenerated from recorded evidence`

Forbidden:

- inventing task success, real-robot photos, or certified functional safety
- mixing MuJoCo / Isaac / PyBullet into one run
- packaging historical / legacy / superseded evidence as current mainline
- presenting mock CAN / MockModbus as real hardware
- presenting Isaac bounded eval as the default stack
- Offline Pass / Interface Pass / replay Pass as task success
- dual-arm “completed system” visuals

---

## 0. Executive summary

### Direct conclusion

The three repos already contain **enough real screenshots, GIFs, SVGs, and machine-readable evidence** to support a 6-page portfolio — but the assets are **scattered, partially stale relative to HEAD, and not yet shaped for the Human→…→Risk narrative**.

**Largest gap for Page 3 (Geometry / TF / Camera):** Stage 1–4 reports + local `evidence/` JSON/CSV exist and are regenerable, but there is **no portfolio-ready SVG/PNG**. Geometry artifacts are **gitignored** under upstream `evidence/`, so they are not GitHub-visible unless summarized into `docs/portfolio/assets/` with provenance.

**Largest narrative gap for Page 1:** Existing overviews are **repo-centric** (upstream / midstream / downstream boxes). The planned deck needs a **pipeline-centric** overview (Keyboard → … → Replay/Risk) with ≤8 modules.

### Counts (approximate)

| Bucket | Approx. count | Notes |
|---|---:|---|
| Upstream `media/` tracked images | 35 | M1–M7 demos + 3-repo SVGs |
| Midstream `docs/portfolio/` + `assets/` images | ~50 | Mix of CURRENT SmolVLA/eval + LEGACY PyBullet |
| Downstream `docs/assets/` images | ~40 | Mix of CURRENT HOC/Panda + LEGACY iiwa |
| Mermaid in Markdown | many | Useful as source notes; **not** final portfolio art |
| Geometry / camera / timing local evidence dirs | yes (upstream, gitignored) | Sufficient to **auto-render** Page 3 |

---

## 1. Control-rate facts (HEAD-checked)

Use these labels only if redrawing control-chain figures:

| Claim | HEAD source | Status |
|---|---|---|
| MoveIt Servo ~125 Hz | `src/teleop_moveit_config/config/servo.yaml` `publish_period: 0.008` | CURRENT |
| Controller / CM sim 500 Hz | `src/teleop_bringup/config/control_rate_sim.yaml` `update_rate: 500` | CURRENT |
| Real path 1 kHz | `control_rate_real.yaml` | Design path; not physical proof |
| MuJoCo physics ~1 kHz | `mujoco_sim_node.py` `physics_rate` default `1000.0` | CURRENT |
| Encoder publish 500 Hz | `encoder_publish_rate` default `500.0` | CURRENT |
| Isaac S4 policy rate 10 Hz | `isaac_sim_adapter/.../s4_runtime_contract.yaml` | Bounded eval only — not default teleop stack |

**Stale claim to avoid:** `media/m1/m1_control_loop_proof.svg` still says `/joint_states` target **≥ 950 Hz** (M1-era). Sim mainline is **500 Hz**.

**Doc conflict (do not copy into figures):** upstream README module table says recorder uses `ApproximateTimeSynchronizer`. Code fact: `MultiModalSync` is **camera-driven latest-sample + slop** (`src/lerobot_recorder/lerobot_recorder/time_sync.py`). Stage 4 report confirms ApproximateTimeSynchronizer is **not** used.

---

## 2. Asset inventory (selected; full EVIDENCE_INDEX remains authoritative for keep/archive)

Legend:

- **Freshness:** `CURRENT` | `STALE` | `LEGACY` | `EXPERIMENTAL` | `UNKNOWN`
- **Usability:** `READY` | `NEEDS_CROP` | `NEEDS_RE_RENDER` | `NEEDS_REDRAW_FROM_EVIDENCE` | `NOT_SUITABLE`
- **Action:** `KEEP` | `RENDER` | `REDRAW` | `RECAPTURE` | `ARCHIVE` | `IGNORE`

### 2.1 Page 1 — System overview candidates

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-OV-01 | midstream | `docs/portfolio/readme_three_repo_overview.svg` | SVG | README / portfolio overview | Three-repo roles + Data→…→System gate strip; Offline≠Task | Manual SVG from BOUNDARY_FREEZE / READMEs | CURRENT | READY (repo narrative) | KEEP — use as **supporting** slide or appendix; not ideal as sole Page 1 hero |
| A-OV-02 | midstream | `docs/portfolio/portfolio_system_overview.svg` | SVG | Interview deck system map | Repo ownership + diagnosis capability | Manual SVG | CURRENT | NEEDS_REDRAW_FROM_EVIDENCE | REDRAW — too “three boxes”; Page 1 wants pipeline |
| A-OV-03 | midstream / up / down | `*/three_repo_canonical_dataflow.svg` | SVG | Canonical dataflow | Episode→release→handoff→replay | Manual from THREE_REPO_CANONICAL_FACTS | CURRENT | NEEDS_CROP | KEEP / optional crop for appendix |
| A-OV-04 | midstream / up / down | `*/three_repo_canonical_run_evidence.svg` | SVG | Run-evidence collage | Summarized metrics | Manifests / benchmarks | STALE risk | NEEDS_RE_RENDER | REGENERATE only if numbers still match public_evidence |
| A-OV-05 | midstream | `assets/diagrams/three_repo_dataflow_diagram.png` | PNG | Older dataflow | High-level flow | Docs | STALE | NOT_SUITABLE | ARCHIVE / IGNORE for 6-pager |
| A-OV-06 | downstream | `docs/assets/portfolio-overview.png` | PNG | Broad portfolio | Framing only | Docs | LEGACY | NOT_SUITABLE | ARCHIVE |
| A-OV-07 | downstream | `docs/archive/portfolio/unified-architecture*.mmd` | Mermaid | Five-repo unified architecture | Mentions other product repos | Historical | LEGACY | NOT_SUITABLE | IGNORE (out of scope this round) |
| **GAP-P1** | — | `docs/portfolio/assets/system_overview.svg` | — | — | Human→Teleop→Safety→Servo→CM→MuJoCo→Capture→QA→Replay | — | — | Missing | **REDRAW** (P0) |

### 2.2 Page 2 — Teleoperation & control

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-TC-01 | upstream | `media/m4/teleop_keyboard.gif` | GIF | Keyboard teleop demo | Human cartesian input moves sim arm | MuJoCo/ROS run (~2026-06-25) | STALE (old capture; stack still exists) | READY | KEEP for Page 2 hero motion; caption “sim teleop, not real robot” |
| A-TC-02 | upstream | `media/m7/grasp_demo.gif` | GIF | Grasp motion demo | Scripted/sim grasp visualization | MuJoCo (~2026-07-04) | CURRENT enough for demo | READY | KEEP |
| A-TC-03 | upstream | `media/m5/estop_and_reset.gif` | GIF | E-stop / reset | Software Hold/E-stop path | Sim run | CURRENT enough | READY | KEEP with **software safety** caption |
| A-TC-04 | midstream | `docs/portfolio/portfolio_control_safety_stack.svg` | SVG | Policy→driver→safety | Control/safety layers + Hardware Pending | Code + contracts | CURRENT | NEEDS_CROP | KEEP for deep interview; **too dense** for Page 2 alone |
| A-TC-05 | upstream | `media/m1/m1_control_loop_proof.svg` | SVG | M1 proof card | Early ros2_control↔MuJoCo loop | M1 docs | STALE (950 Hz claim) | NOT_SUITABLE | ARCHIVE / IGNORE |
| A-TC-06 | upstream | `media/m1/joint_states_hz.png` | PNG | Rate plot | Historical joint_states Hz | M1 logs | STALE vs 500 Hz sim | NOT_SUITABLE as CURRENT rate proof | IGNORE or relabel historical |
| A-TC-07 | upstream | `media/m1/rqt_graph_m1.png` | PNG | Node graph | Topology snapshot | ROS graph | STALE | NEEDS_CROP | Optional appendix only |
| A-TC-08 | midstream | `docs/portfolio/portfolio_realtime_priority_gantt.svg` | SVG | RT priority design | Sim vs real priority policy | Launch/config | CURRENT (design) | READY for specialist page | P2 — not needed for 6-pager core |
| A-TC-09 | upstream | `media/m2/*` CAN / DS402 | PNG/SVG | Virtual fieldbus | vcan / virtual DS402 | M2 evidence | CURRENT as **virtual** | READY only with “vcan / not physical bus” | KEEP as optional inset; not Page 2 center |
| **GAP-P2** | — | `docs/portfolio/assets/teleop_control_chain.svg` | — | — | Human→Safety→Servo 125→Impedance 500→MuJoCo 1k | Config files above | — | Missing simple chain | **REDRAW** (P0) |

### 2.3 Page 3 — Geometry / TF / camera (priority audit)

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-GC-01 | upstream | `docs/SIMULATION_GEOMETRY_STAGE1_REPORT.md` | MD report | Stage 1 FK/frame contract | Controller tip = `panda_link7`; EE gap 0.207 m is fixed chain | Offline CLI + tests | CURRENT | NEEDS_REDRAW_FROM_EVIDENCE | RENDER figure from JSON/CSV — do not screenshot MD tables |
| A-GC-02 | upstream | `docs/SIMULATION_GEOMETRY_STAGE2_REPORT.md` | MD | Live TF closeout + fault injection | URDF↔TF↔MuJoCo residuals ~1e-12 m | `evidence/geometry_stage1_live_tf/` | CURRENT (local) | NEEDS_REDRAW_FROM_EVIDENCE | Same |
| A-GC-03 | upstream | `docs/SIMULATION_GEOMETRY_STAGE3_REPORT.md` | MD | Camera extrinsic contract | Scene renderer↔TF max ‖Δp‖ = **0.0 m**; wrist eye-in-hand | `evidence/camera_stage3_{scene,wrist}/` | CURRENT (local) | NEEDS_REDRAW_FROM_EVIDENCE | Same |
| A-GC-04 | upstream | `docs/SIMULATION_GEOMETRY_STAGE4_REPORT.md` | MD | Publish-time skew | Signed Header skew observer; SOURCE_TIME unavailable | `evidence/timestamp_stage4/` | CURRENT (local) | Optional inset | RENDER only if Page 3 has space |
| A-GC-05 | upstream | `evidence/geometry_stage1_live_tf/geometry_samples.csv` | CSV | Machine residuals | Max ‖Δp‖ URDF↔live TF ≤ ~4e-16 m; live TF↔MuJoCo ≤ ~5.9e-12 m (8 poses) | Stage1 live CLI | CURRENT local / **not in git** | READY as **data source** | RENDER → portfolio asset + provenance JSON |
| A-GC-06 | upstream | `evidence/camera_stage3_scene/run_manifest.json` | JSON | Scene camera gate | `renderer_tf_max_translation_residual_m: 0.0`; optical frame match | Stage3A CLI | CURRENT local | READY as data source | RENDER |
| A-GC-07 | upstream | `evidence/camera_stage3_wrist/run_manifest.json` | JSON | Wrist contract | `T_hand_camera` stable ~1e-16 m; world pose moves; `H_knuckle_z05` | Stage3C | CURRENT local | READY as data source | RENDER |
| A-GC-08 | upstream | `media/m6/camera_rgb_view.png` | PNG | Scene RGB | MuJoCo scene render exists | M6 capture 2026-07-05 | STALE vs Aug wrist remount (scene still OK) | READY | KEEP for multimodal; prefer Aug live for “current wrist” |
| A-GC-09 | upstream | `media/m6/wrist_camera_view.png` | PNG | Wrist RGB | Pre-`H_knuckle_z05` wrist | 2026-07-05 | **STALE** | NOT_SUITABLE as current wrist | REPLACE with A-GC-11 |
| A-GC-10 | upstream | `media/m6/tactile_{left,right}_view.png` | PNG | GelSight-like | Tactile streams exist | 2026-07-05 | CURRENT enough | READY | KEEP |
| A-GC-11 | upstream | `evidence/live_rgb_bag_20260814T062618Z/png/{scene,wrist}.png` | PNG | Post-remount live RGB | Idle ready pose; wrist red_pixels=289 | Live bag round 2 | CURRENT local / gitignored | READY | Promote excerpt into portfolio assets |
| A-GC-12 | upstream | `docs/WRIST_RGB_ACCEPTANCE_REPORT.md` | MD | Wrist RGB acceptance | RGB 4/4 after remount | wrist_rgb_cli | CURRENT | Text only | Cite in caption |
| **GAP-P3** | — | `docs/portfolio/assets/geometry_camera_consistency.svg` (+ PNG) | — | — | URDF/FK ↔ live TF ↔ MuJoCo GT ↔ renderer/TF + residuals | A-GC-05..07 | — | Missing | **RENDER from evidence** (P0) — **no new sim required** if local evidence kept |

**Page 3 must state:** simulation consistency ≠ Sim2Real; `PHYSICAL=NOT_RUN/UNAVAILABLE`; renderer↔TF residual 0 under Stage 3 offline contract (scene; wrist ≈ 0 within float noise).

### 2.4 Page 4 — Multimodal episode & data pipeline

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-MM-01 | upstream | `media/m6/multimodal_sync.png` / `multimodal_sensor_sync_grid.png` | PNG | Sync visualization | Timing/sync plots from a capture | M6 2026-07-05 | STALE | NEEDS_RE_RENDER | Optional; verify numbers before reuse |
| A-MM-02 | upstream | `media/m6/lerobot_dataset_features.png` | PNG | Feature schema screenshot | Recorder feature names | M6 dataset | STALE | NEEDS_CROP | Optional appendix |
| A-MM-03 | upstream | `evidence/live_rgb_episode_20260814T063527Z/` | Episode | Live recorder verify | 76 frames; scene+wrist; `action_fill=hold_from_ee`; `command_missing=true` | Live portfolio capture | CURRENT local | READY for **schema/timeline**, not grasp | Use with honest caption |
| A-MM-04 | midstream | `assets/diagrams/episode_structure.png` | PNG | Episode structure | Historical schema | Legacy | LEGACY | NOT_SUITABLE | ARCHIVE |
| A-MM-05 | midstream | `assets/screenshots/lerobot_*.png` | PNG | Export screenshots | Legacy LeRobot export | Legacy | LEGACY | NOT_SUITABLE | ARCHIVE |
| A-MM-06 | midstream | `assets/diagrams/data_cleaning_lerobot_flow.png` | PNG | Cleaning flow | Design intent | Docs | STALE | NEEDS_REDRAW | Optional |
| **GAP-P4** | — | `docs/portfolio/assets/multimodal_episode.svg` (+ composite PNG) | — | — | What was recorded along time | Prefer A-GC-11 + A-GC-10 + real parquet snippets | — | Missing | **RENDER composite**; **RECAPTURE teleop episode only if** wanting moving joint/action curves |

**Data note:** Do **not** invent joint/EE/action curves. If live episode is near-static (`hold_from_ee`), either (a) schema+image composite without fake waveforms, or (b) re-run a short teleop/batch episode with `timeout` / `auto_record_seconds` and Nuke-On-Done.

### 2.5 Page 5 — Data QA / evaluation / gates

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-QA-01 | midstream | `docs/portfolio/portfolio_data_evidence_flow.svg` | SVG | Train vs eval isolation | Train line ≠ eval line; Offline Pass ≠ Task | Recovery v3 + S4 facts | CURRENT | READY but **SmolVLA-specific** | KEEP for research track; simplify for infra deck |
| A-QA-02 | midstream | `docs/portfolio/readme_three_repo_overview.svg` (gate strip) | SVG | Gate ladder | Data/Offline/Interface/Behavior/Task/System | Canonical facts | CURRENT | READY | KEEP as reference |
| A-QA-03 | midstream | `docs/portfolio/smolvla_v3_eval_framework_summary.png` | PNG | Three-backend envelope | Offline Pass / smoke / Isaac Hold | `public_evidence/canonical_v3` | CURRENT | READY | KEEP for eval page |
| A-QA-04 | midstream | `docs/portfolio/smolvla_s4_bounded5_funnel.png` | PNG | Task funnel | interface 5/5 → reach 1/5 → grasp/lift 0/5 | relight `s4_gate.json` | CURRENT | READY | KEEP with Hold caption |
| A-QA-05 | midstream | `docs/portfolio/smolvla_recovery_v3_openloop_ee_vs_s2.png` | PNG | Offline EE improve | Offline metric only | gate_v3 report | CURRENT | READY | KEEP; never as task success |
| A-QA-06 | midstream | `docs/portfolio/public_evidence/canonical_v3/*.json` | JSON | Public gate digests | Machine-checkable Pass/Hold | Provenance locked | CURRENT | READY data | Source of truth for redraw |
| A-QA-07 | midstream | Isaac scene JPGs under `docs/portfolio/smolvla_s4_*.jpg` | JPG | Camera / lighting badcase | Blind vs relight | S4 telemetry | CURRENT | READY | Supporting, not main gate diagram |
| **GAP-P5** | — | `docs/portfolio/assets/data_gate_flow.svg` | — | — | Raw→Schema→Release→Offline→Handoff→Replay/Isaac→Task/System + inequality callouts | A-QA-02..06 | — | Missing simplified infra version | **REDRAW** (P0) — can reuse facts from A-QA-01/02 without new runs |

### 2.6 Page 5/6 — Replay / Risk / HOC

| Asset ID | Repository | Path | Type | Current purpose | What it proves | Evidence source | Freshness | Usability | Recommended action |
|---|---|---|---|---|---|---|---|---|---|
| A-RR-01 | downstream | `docs/assets/hoc-runtime-four-lane-dashboard.png` | PNG | HOC UI | Brain/Execution/Safety/Task GT lanes; UNAVAILABLE allowed | Deterministic frontend e2e + mock WS (2026-07-26) | CURRENT | READY | **KEEP as Page 6 hero** |
| A-RR-02 | midstream | `docs/portfolio/policy_runtime_m6_fault_response_timeline.png` | PNG | Safety feedback wiring | R0 EXECUTED / R2 HELD / R3 ESTOPPED on mock policy | `public_evidence/m6_wiring_20260727` | CURRENT | READY | KEEP; caption mock backend |
| A-RR-03 | midstream | `docs/portfolio/brain_cerebellum_runtime_system.svg` | SVG | Brain–cerebellum map | Runtime ownership | Roadmap + M6 | CURRENT | NEEDS_CROP | Optional |
| A-RR-04 | downstream | `docs/assets/panda_replay_*.png` | PNG | Latency / dist / resources | Monitor outputs | ~2026-07-12 plots | STALE / weak run-ID link | NEEDS_RE_RENDER | Relabel or regenerate from known benchmark JSON |
| A-RR-05 | downstream | `docs/assets/m5-hoc-*.{png,svg}` | PNG/SVG | Pre-four-lane HOC | Historical UI | Old dashboard | LEGACY | NOT_SUITABLE | ARCHIVE |
| A-RR-06 | downstream | iiwa / dual-repo / same-task assets | mixed | Legacy portfolio | Non-Panda mainline | Old runs | LEGACY | NOT_SUITABLE | ARCHIVE / IGNORE |
| A-RR-07 | midstream | `assets/gifs/demo_*.gif` | GIF | KUKA/PyBullet demos | Legacy | Legacy sim | LEGACY | NOT_SUITABLE | ARCHIVE |
| **GAP-P6** | — | `docs/portfolio/assets/replay_risk_flow.svg` | — | — | Handoff→PolicyRunner→PyBullet→Trace→Risk→Hold | Downstream README + code | — | Missing small flow | **REDRAW** (P1) — optional if HOC + caption suffice |

---

## 3. READY assets (safe to place in the 6-pager with correct captions)

| ID | Asset | Best page | Caption must say |
|---|---|---|---|
| A-TC-01 | `teleop_keyboard.gif` | 2 | Sim teleop; not real Franka |
| A-TC-02 | `grasp_demo.gif` | 2 | Sim motion demo; not learned-policy success |
| A-TC-03 | `estop_and_reset.gif` | 2 / 6 | Software Hold/E-stop; not certified FS |
| A-GC-08/10 | scene + tactile PNGs | 3 / 4 | MuJoCo/EGL renders |
| A-GC-11 | Aug-14 live scene/wrist | 3 / 4 | Idle ready pose after wrist remount; not grasp |
| A-OV-01 | `readme_three_repo_overview.svg` | 1 appendix / appendix | Repo roles + gate inequality |
| A-QA-03/04/05 | SmolVLA eval figures | 5 | Offline Pass / Isaac Hold; not task success |
| A-RR-01 | HOC four-lane PNG | 6 | Observability; not task success |
| A-RR-02 | M6 timeline PNG | 6 | Mock policy wiring |

---

## 4. STALE / LEGACY / NOT_SUITABLE (do not present as current mainline)

| Class | Examples | Why |
|---|---|---|
| STALE rates | `m1_control_loop_proof.svg`, `joint_states_hz.png` | 1 kHz M1 acceptance vs sim 500 Hz |
| STALE wrist RGB | `media/m6/wrist_camera_view.png` | Pre-`H_knuckle_z05` (2026-07-05) |
| STALE sync wording | README “ApproximateTimeSynchronizer” | Code is `MultiModalSync` latest-sample |
| LEGACY midstream | `assets/gifs/demo_*.gif`, old episode_structure, lerobot screenshots | KUKA/PyBullet era |
| LEGACY downstream | iiwa GIFs, dual-repo overlays, old HOC | Non-Panda mainline |
| SUPERSEDED eval | first-round near-black S4 JPGs as “success” | Relight gate is authoritative; lift still 0/5 |
| OUT OF SCOPE | five-repo unified architecture, other product repos | Not this portfolio’s protagonist |

---

## 5. Missing assets (gaps vs 6-page plan)

| Gap | Needed figure | Exists today? | Blocker |
|---|---|---|---|
| P1 pipeline overview | Horizontal ≤8-module system overview | Partial (repo boxes only) | Narrative redraw |
| P2 teleop control chain | Human→…→MuJoCo with verified Hz | Dense safety stack only | Simplify + rate labels from config |
| P3 geometry/camera | Residual diagram + units | Reports+CSV only; no figure | Auto-read local evidence (or publish excerpts) |
| P4 multimodal composite | Time strip with real images ± real signals | Separate images; no composite | Optional short recapture for curves |
| P5 infra gate flow | Data→Offline→Interface→Behavior→Task→System | SmolVLA-specific / strip only | Simplify redraw |
| P6 mini replay/risk flow | Handoff→…→Hold | HOC screenshot exists | Optional |

Suggested future directory (do **not** relocate historical assets now):

```text
robot-arm-episode-data-lab/docs/portfolio/assets/
  system_overview.svg
  teleop_control_chain.svg
  geometry_camera_consistency.svg
  geometry_camera_consistency.png
  multimodal_episode.svg / .png
  data_gate_flow.svg
  replay_risk_flow.svg   # optional
  provenance/*.json      # SHA + source paths for regenerated figures
```

---

## 6. Recommended 3–5 figures to create next (pending your confirmation)

| Priority | Figure | Format | Data source (no fiction) | Need new sim run? |
|---|---|---|---|---|
| **P0-1** | Portfolio System Overview (pipeline) | SVG | Current READMEs + launch/control packages; label `architecture diagram based on current repository implementation` | **No** |
| **P0-2** | Teleop Control Chain | SVG | `servo.yaml`, `control_rate_sim.yaml`, `mujoco_sim` defaults; optional inset GIF stills | **No** |
| **P0-3** | Geometry / Camera Consistency | SVG + PNG | Auto-load `geometry_samples.csv` + camera `run_manifest.json` / CSV residuals; caption `visualization regenerated from recorded evidence` | **No** (if local evidence retained); else regenerate offline CLIs only |
| **P0-4** | Data QA / Gate Flow (infra) | SVG | `readme_three_repo_overview` gate strip + `public_evidence/canonical_v3` inequalities | **No** |
| **P1-5** | Multimodal Episode composite | SVG/PNG collage | Aug-14 live RGB + M6 tactile; schema from `meta.json` / parquet columns; **no fake curves** | **Only if** dynamic joint/action waveforms required |
| **P1-6** | Replay / Risk mini-flow | SVG | Downstream README + HOC screenshot as companion | **No** |

---

## 7. What can be generated from existing evidence vs must re-run

### 7.1 Generate without new simulation (preferred)

- P0-1, P0-2, P0-4, P1-6 architecture SVGs
- P0-3 geometry/camera figure from upstream local:

  - `evidence/geometry_stage1_live_tf/geometry_samples.csv`
  - `evidence/camera_stage3_scene/run_manifest.json` (+ samples CSV)
  - `evidence/camera_stage3_wrist/run_manifest.json` (+ samples CSV)

- Promote `evidence/live_rgb_bag_.../png/{scene,wrist}.png` into portfolio assets with provenance (gitignored today)
- Gate funnel already regenerated from `s4_gate.json` via midstream scripts — reuse PNGs

### 7.2 Must re-run simulation / capture (only if product requires it)

| Need | Why | Minimal command posture |
|---|---|---|
| Dynamic multimodal waveforms | Live episode is idle `hold_from_ee` | Bounded `timeout` / `auto_record_seconds` teleop or batch; then Nuke-On-Done |
| Current wrist GIF in motion | README GIFs predate remount | Optional; stills may suffice |
| Fresh joint_states Hz plot at 500 Hz | Old M1 plot misleading | Optional short rate probe |
| Git-visible geometry evidence | `evidence/` is gitignored | Offline Stage CLIs → copy **summaries** to `docs/portfolio/assets/provenance/` |

**Do not** re-run Isaac S4 / retrain / expand seeds for visuals.

---

## 8. Minimum-effort plan (after you confirm)

1. Create midstream `docs/portfolio/assets/` (new renders only).
2. Draw **P0-1..P0-4** only (4 SVGs; PNG export for geometry).
3. Promote Aug-14 scene/wrist stills + keep M6 tactile + keyboard/grasp GIFs.
4. Page 6 = HOC screenshot + short caption; skip P1-6 unless empty space.
5. Defer multimodal waveform recapture unless Page 4 feels empty without curves.
6. Do **not** move legacy assets; mark them ARCHIVE in captions/indexes only.

Estimated effort: **architecture redraws + evidence-driven geometry script** — no business-code changes; optional short timed capture only for Page 4 curves.

---

## 9. Priority board

### Priority P0 — must fix for portfolio comprehension

1. Pipeline **System Overview** SVG (not three-repo boxes alone)
2. **Teleop control chain** SVG with HEAD-verified rates
3. **Geometry / camera consistency** figure auto-filled from Stage 1–3 evidence
4. Simplified **Data / Offline / Interface / Behavior / Task / System** gate flow with Offline≠Task and Interface≠Lift callouts

### Priority P1 — nice to have

1. Multimodal episode collage (real images; schema timeline; no fake plots)
2. Small Replay→Risk→Hold flow next to HOC
3. Publish provenance JSON for geometry residuals into git
4. Replace README wrist still with Aug-14 remount still (docs-only)

### Priority P2 — not now

1. Realtime priority gantt / deep CAN DS402 proof cards as main slides
2. Regenerating all M1–M7 media
3. Five-repo / other-product architecture
4. Dual-arm or real-robot photography
5. New Isaac rollouts for prettier frames
6. Screenshotting Mermaid as final art

---

## 10. Page coverage matrix (after P0)

| Page | Can ship today? | After P0 renders? |
|---|---|---|
| 1 System Overview | Partial (repo SVG) | Yes |
| 2 Teleop & Control | Yes (GIFs) + weak chain diagram | Yes |
| 3 Geometry / Camera | Evidence yes / figure **no** | Yes |
| 4 Multimodal Episode | Partial stills | Yes without curves; better with optional recapture |
| 5 QA / Gates | Yes (SmolVLA figures) | Stronger with infra gate SVG |
| 6 Replay / Risk / HOC | Yes (HOC) | Optional mini-flow |

---

## 11. Stop point

Audit pass was read-only. Render pass (2026-08-17) wrote P0-1..P0-4 plus the Page 4 collage from a bounded waveform capture. Page 6 still uses the existing HOC screenshot; `replay_risk_flow.svg` was not drawn.

Use PNG files under `docs/portfolio/assets/` for IDE preview. Do not open a missing `multimodal_episode.svg` — that wrapper was deleted because it had no pixels.
