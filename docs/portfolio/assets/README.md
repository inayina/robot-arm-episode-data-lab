# Portfolio visual assets (render phase)

SVG is the source of truth for architecture diagrams. PNG is the IDE/deck preview (and the only format for the multimodal collage).

Caption classes:

- `architecture diagram based on current repository implementation`
- `visualization regenerated from recorded evidence`

Do not treat Offline Pass, Interface Pass, replay, or this waveform snippet as task success.

## Files to use in the deck

| Page | Open this (preview) | Source |
|---|---|---|
| 1 Overview | `system_overview.png` | `system_overview.svg` |
| 2 Control chain | `teleop_control_chain.png` | `teleop_control_chain.svg` |
| 3 Geometry / camera | `geometry_camera_consistency.png` | `geometry_camera_consistency.svg` |
| 4 Multimodal | `multimodal_episode.png` | PNG only — no wrapper SVG |
| 5 Gate flow | `data_gate_flow.png` | `data_gate_flow.svg` |
| 6 Replay / Risk | existing HOC screenshot | optional `replay_risk_flow.svg` **not drawn** |

Regenerate architecture / geometry / gate:

```bash
python3 scripts/render_portfolio_visual_assets.py
```

The deck figure is `multimodal_episode.png`. Raw `.parquet` is gitignored (pre-commit only allows source/docs/media). Local copies may remain under `assets/evidence/` for re-render:

```bash
python3 scripts/render_portfolio_multimodal_episode.py \
  --episode-root docs/portfolio/assets/evidence/waveform_episode_20260817T132722Z/layout
```
