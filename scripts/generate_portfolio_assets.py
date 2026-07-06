#!/usr/bin/env python3
"""Generate portfolio diagram PNGs and LeRobot export screenshots."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "assets" / "diagrams"
SCREENSHOTS = ROOT / "assets" / "screenshots"
LEROBOT_EXPORT = ROOT / "dataset" / "v1" / "lerobot_export"


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def render_text_image(
    title: str,
    lines: list[str],
    *,
    width: int = 1200,
    pad: int = 28,
    title_size: int = 28,
    body_size: int = 18,
    bg: str = "#f8fafc",
    fg: str = "#0f172a",
    accent: str = "#2563eb",
) -> Image.Image:
    title_font = load_font(title_size)
    body_font = load_font(body_size)
    probe = Image.new("RGB", (width, 100), bg)
    draw = ImageDraw.Draw(probe)
    _, title_h = text_size(draw, title, title_font)
    line_heights = [text_size(draw, line, body_font)[1] + 6 for line in lines]
    height = pad * 2 + title_h + 16 + sum(line_heights) + 12
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    draw.text((pad, pad), title, fill=accent, font=title_font)
    y = pad + title_h + 16
    for line in lines:
        draw.text((pad, y), line, fill=fg, font=body_font)
        y += text_size(draw, line, body_font)[1] + 6
    return image


def draw_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    label: str,
    *,
    fill: str,
    outline: str = "#334155",
    font: ImageFont.ImageFont,
) -> None:
    draw.rounded_rectangle(xy, radius=10, fill=fill, outline=outline, width=2)
    x0, y0, x1, y1 = xy
    tw, th = text_size(draw, label, font)
    draw.text(((x0 + x1 - tw) / 2, (y0 + y1 - th) / 2), label, fill="#0f172a", font=font)


def draw_label(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    body: list[str],
    *,
    fill: str,
    outline: str = "#334155",
    title_color: str = "#0f172a",
    body_color: str = "#334155",
) -> None:
    title_font = load_font(18)
    body_font = load_font(13)
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=12, fill=fill, outline=outline, width=2)
    draw.text((x0 + 18, y0 + 16), title, fill=title_color, font=title_font)
    y = y0 + 48
    for line in body:
        draw.text((x0 + 18, y), line, fill=body_color, font=body_font)
        y += 22


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = "#475569",
) -> None:
    draw.line([start, end], fill=color, width=2)
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) >= abs(ey - sy):
        tip = 10 if ex >= sx else -10
        draw.polygon([(ex, ey), (ex - tip, ey - 5), (ex - tip, ey + 5)], fill=color)
    else:
        tip = 10 if ey >= sy else -10
        draw.polygon([(ex, ey), (ex - 5, ey - tip), (ex + 5, ey - tip)], fill=color)


def save_panda_p0_data_loop(path: Path) -> None:
    width, height = 1600, 720
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    subtitle_font = load_font(17)
    draw.text((48, 34), "Panda P0 Data Loop", fill="#0f766e", font=title_font)
    draw.text(
        (48, 78),
        "Middle-layer dataset contract: raw episode -> validation -> release -> baseline training -> replay handoff",
        fill="#475569",
        font=subtitle_font,
    )

    boxes = [
        (
            (48, 150, 290, 330),
            "Upstream Raw Episode",
            ["MuJoCo / ROS 2", "teleop input", "action / state", "observation"],
            "#ccfbf1",
        ),
        (
            (350, 150, 590, 330),
            "Adapter",
            ["action_type declared", "state[7]+gripper[1]", "no silent truncation"],
            "#dbeafe",
        ),
        (
            (650, 150, 890, 330),
            "Panda Dataset",
            ["observation.state[8]", "ee_pose[7]", "action[7]", "metadata"],
            "#fef3c7",
        ),
        (
            (950, 150, 1190, 330),
            "Validation + Release",
            ["inspect PASS/FAIL", "manifest.json", "inspection_report.json"],
            "#ede9fe",
        ),
        (
            (1250, 150, 1492, 330),
            "Training + Handoff",
            ["checkpoint.npz", "eval.json", "predicted_actions.jsonl"],
            "#dcfce7",
        ),
    ]
    for xy, title, body, fill in boxes:
        draw_label(draw, xy, title, body, fill=fill)

    for x in (290, 590, 890, 1190):
        draw_arrow(draw, (x + 16, 240), (x + 60, 240), color="#0f766e")

    bottom_boxes = [
        ((350, 430, 590, 570), "Schema Guard", ["configs/robot_schemas", "panda.yaml", "schema_id fixed"], "#e0f2fe"),
        ((650, 430, 890, 570), "Baseline Policy", ["linear_smoke", "state -> action", "CPU-only smoke"], "#fef9c3"),
        ((950, 430, 1190, 570), "Downstream Use", ["MoveIt / PyBullet", "execution risk", "Sim2Real-readiness"], "#fee2e2"),
    ]
    for xy, title, body, fill in bottom_boxes:
        draw_label(draw, xy, title, body, fill=fill)
    draw_arrow(draw, (770, 330), (770, 430), color="#64748b")
    draw_arrow(draw, (1070, 330), (1070, 430), color="#64748b")

    draw.text(
        (48, 650),
        "Boundary: software simulation/data pipeline only. This is not a completed real-robot Sim2Real validation.",
        fill="#64748b",
        font=subtitle_font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_panda_training_pipeline(path: Path) -> None:
    width, height = 1600, 820
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    body_font = load_font(15)
    draw.text((48, 34), "Panda Training Pipeline", fill="#1d4ed8", font=title_font)
    draw.text(
        (48, 80),
        "Minimal baseline training: prove dataset -> training -> evaluation -> replay contract, not model performance claims.",
        fill="#475569",
        font=body_font,
    )

    stages = [
        ((70, 155, 340, 315), "Dataset Release", ["frames.jsonl", "manifest.json", "inspection_report.json"], "#dbeafe"),
        ((410, 155, 680, 315), "train_act_smoke", ["linear_smoke policy", "observation.state", "ee_delta_gripper action"], "#dcfce7"),
        ((750, 155, 1020, 315), "Training Artifacts", ["checkpoint.npz", "metrics.json", "normalization.json"], "#fef3c7"),
        ((1090, 155, 1360, 315), "evaluate_policy", ["eval.json", "MAE / RMSE", "per-dim error"], "#ede9fe"),
    ]
    for xy, title, body, fill in stages:
        draw_label(draw, xy, title, body, fill=fill)
    for x in (340, 680, 1020):
        draw_arrow(draw, (x + 18, 235), (x + 70, 235), color="#2563eb")

    replay = [
        ((410, 455, 680, 615), "replay_policy", ["predicted_actions.jsonl", "episode_index", "frame_index", "action_type"], "#ccfbf1"),
        ((750, 455, 1020, 615), "prepare_bridge_handoff", ["dataset_manifest.json", "replay_check.json", "handoff_manifest.json"], "#fee2e2"),
        ((1090, 455, 1360, 615), "Bridge Consumer", ["MoveIt/PyBullet owner", "runtime validation", "risk analysis"], "#e0f2fe"),
    ]
    for xy, title, body, fill in replay:
        draw_label(draw, xy, title, body, fill=fill)
    draw_arrow(draw, (1230, 315), (1230, 455), color="#64748b")
    for x in (680, 1020):
        draw_arrow(draw, (x + 18, 535), (x + 70, 535), color="#2563eb")

    metrics = [
        "Portfolio-safe metrics: train_loss, val_loss, MAE, RMSE, state_dim, action_dim, frame_count",
        "Do not claim: robust grasp policy, ACT/Diffusion Policy, direct real-robot deployment",
    ]
    y = 700
    for line in metrics:
        draw.text((70, y), line, fill="#475569", font=body_font)
        y += 28
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_panda_p0_demo_terminal(path: Path) -> None:
    lines = [
        "$ PANDA_DEMO_ROOT=\"$(mktemp -d /tmp/panda_p0_demo.XXXXXX)\"",
        "$ python3 training/scripts/make_mock_panda_dataset.py --output \"$PANDA_DEMO_ROOT/raw\"",
        "Wrote mock Panda dataset: .../raw",
        "Frames: 10",
        "",
        "$ python3 training/scripts/inspect_dataset.py --dataset \"$PANDA_DEMO_ROOT/raw\" --schema configs/robot_schemas/panda.yaml",
        "Required fields: observation.state OK [8], observation.ee_pose OK [7], action OK [7]",
        "Optional images: WARN missing in mock data",
        "Status: PASS",
        "",
        "$ python3 training/scripts/train_act_smoke.py --dataset \"$PANDA_DEMO_ROOT/release\" --schema configs/robot_schemas/panda.yaml --output \"$PANDA_DEMO_ROOT/train\"",
        "Training output: .../train",
        "Train loss: 0.000000",
        "Val loss: 3.687882",
        "Status: PASS",
        "",
        "$ replay_policy && prepare_bridge_handoff",
        "Replay output: predicted_actions.jsonl",
        "Handoff output: bridge_handoff",
        "Action type: ee_delta_gripper   Action dim: 7",
        "Status: PASS",
    ]
    image = render_text_image(
        "Panda P0 Demo Terminal Evidence",
        lines,
        width=1500,
        body_size=18,
        bg="#0f172a",
        fg="#e2e8f0",
        accent="#22c55e",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_bridge_handoff_bundle(path: Path) -> None:
    lines = [
        "bridge_handoff/",
        "├── predicted_actions.jsonl",
        "├── dataset_manifest.json",
        "├── dataset_inspection_report.json",
        "├── replay_check.json",
        "└── handoff_manifest.json",
        "",
        "handoff_manifest.json:",
        "{",
        '  "handoff_id": "panda_p0_demo_bridge_v0",',
        '  "consumer_repo": "ros2-moveit-pybullet-bridge",',
        '  "schema_id": "panda_ee_delta_gripper_v0",',
        '  "action_type": "ee_delta_gripper",',
        '  "runtime_owner": "downstream bridge"',
        "}",
        "",
        "Contract: this repository owns validated data and replay files;",
        "the downstream bridge owns MoveIt/PyBullet execution validation.",
    ]
    image = render_text_image(
        "Bridge Handoff Bundle",
        lines,
        width=1300,
        body_size=19,
        bg="#f8fafc",
        fg="#0f172a",
        accent="#be123c",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_data_cleaning_lerobot_flow(path: Path) -> None:
    width, height = 1600, 760
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(34)
    body_font = load_font(15)
    draw.text((48, 34), "Data Cleaning + LeRobot Export Flow", fill="#0f766e", font=title_font)
    draw.text(
        (48, 80),
        "Middle-layer data curation: validate the contract first, then train, replay, or export.",
        fill="#475569",
        font=body_font,
    )

    stages = [
        (
            (55, 150, 295, 330),
            "Raw Episode",
            ["MuJoCo/ROS 2 recorder", "legacy PyBullet sample", "action/state/observation"],
            "#ccfbf1",
        ),
        (
            (355, 150, 595, 330),
            "Adapter + Mapping",
            ["robot schema selected", "action_type declared", "metadata normalized"],
            "#dbeafe",
        ),
        (
            (655, 150, 895, 330),
            "Schema Inspection",
            ["required fields", "shape checks", "warnings for optional data"],
            "#fef3c7",
        ),
        (
            (955, 150, 1195, 330),
            "Dataset Release",
            ["frames.jsonl", "manifest.json", "inspection_report.json"],
            "#ede9fe",
        ),
        (
            (1255, 150, 1495, 330),
            "Consumers",
            ["baseline training", "replay handoff", "LeRobot/HF export"],
            "#dcfce7",
        ),
    ]
    for xy, title, body, fill in stages:
        draw_label(draw, xy, title, body, fill=fill)
    for x in (295, 595, 895, 1195):
        draw_arrow(draw, (x + 18, 240), (x + 60, 240), color="#0f766e")

    consumers = [
        ((230, 455, 500, 615), "Panda Training Release", ["P0 mainline", "linear smoke / MLP BC", "metrics + checkpoint"], "#dcfce7"),
        ((560, 455, 830, 615), "Bridge Handoff", ["predicted_actions.jsonl", "runtime owner downstream", "Sim-to-Sim validation"], "#fee2e2"),
        ((890, 455, 1160, 615), "LeRobot v2.1 Layout", ["parquet + mp4", "meta/info.json", "format evidence"], "#e0f2fe"),
        ((1220, 455, 1490, 615), "HF Dataset Export", ["datasets.save_to_disk", "future ACT/Diffusion input", "not trained policy"], "#fef9c3"),
    ]
    for xy, title, body, fill in consumers:
        draw_label(draw, xy, title, body, fill=fill)
    for x in (365, 695, 1025, 1355):
        draw_arrow(draw, (1075, 330), (x, 455), color="#64748b")

    draw.text(
        (55, 690),
        "Boundary: export-compatible datasets are not equivalent to trained LeRobot/ACT/Diffusion policies or real-robot deployment.",
        fill="#64748b",
        font=body_font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_training_methods_matrix(path: Path) -> None:
    lines = [
        "Level | Method                         | Status              | Purpose",
        "------+--------------------------------+---------------------+----------------------------------------------",
        "L0    | Dataset inspection only        | implemented         | validate schema/release without training",
        "L1    | Linear smoke policy            | P0 mainline         | prove dataset -> train -> eval -> replay",
        "L2    | PyTorch MLP BC                 | optional script     | neural BC entry point when PyTorch exists",
        "L3    | LeRobot / ACT / Diffusion      | future integration  | external trainer input, not in-repo claim",
        "L4    | Runtime / real robot rollout    | downstream/future   | execution validation, not owned here",
        "",
        "Current portfolio claim:",
        "  L0 + L1 are the main proof of the minimal engineering loop.",
        "  L2 shows extension path, but it is not required for the P0 demo.",
        "  L3/L4 are boundaries and future interfaces, not completed results.",
        "",
        "Safe metrics to show:",
        "  train_loss, val_loss, MAE, RMSE, state_dim, action_dim, frame_count, action_type.",
        "",
        "Do not claim:",
        "  robust grasp policy, robot foundation model, completed ACT/Diffusion training, or real-robot success.",
    ]
    image = render_text_image(
        "Training Methods Matrix",
        lines,
        width=1500,
        body_size=18,
        bg="#f8fafc",
        fg="#0f172a",
        accent="#1d4ed8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_architecture_diagram(path: Path) -> None:
    width, height = 1280, 760
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(30)
    box_font = load_font(16)
    draw.text((40, 24), "System Architecture", fill="#2563eb", font=title_font)

    layers = [
        ("Application", "#dbeafe", ["collect_episode", "batch_collect", "validate", "export"]),
        ("Agents", "#dcfce7", ["task_fsm", "motion_planner", "evaluator"]),
        ("Core", "#fef3c7", ["trajectory", "ik", "hal", "grasp", "rrt"]),
        ("Data", "#ede9fe", ["episode dir", "lerobot_export"]),
    ]
    y = 90
    for name, color, items in layers:
        draw.rounded_rectangle((40, y, width - 40, y + 120), radius=12, outline="#94a3b8", width=2, fill=color)
        draw.text((56, y + 12), name, fill="#0f172a", font=load_font(20))
        x = 56
        for item in items:
            tw, _ = text_size(draw, item, box_font)
            draw.rounded_rectangle((x, y + 52, x + tw + 24, y + 92), radius=8, fill="#ffffff", outline="#64748b")
            draw.text((x + 12, y + 64), item, fill="#0f172a", font=box_font)
            x += tw + 36
        if y + 120 < height - 80:
            draw_arrow(draw, (width // 2, y + 120), (width // 2, y + 150))
        y += 150

    draw.text(
        (40, height - 44),
        "HAL isolates PyBullet; FSM + Evaluator drive pick-lift; episode writer keeps step-aligned multimodal data.",
        fill="#475569",
        font=box_font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_data_flow_diagram(path: Path) -> None:
    width, height = 1280, 520
    image = Image.new("RGB", (width, height), "#f8fafc")
    draw = ImageDraw.Draw(image)
    title_font = load_font(30)
    box_font = load_font(15)
    draw.text((40, 24), "Data Flow (pick_and_lift)", fill="#2563eb", font=title_font)

    boxes = [
        (60, 120, 170, 190, "task_fsm", "#dcfce7"),
        (230, 120, 390, 190, "motion_planner", "#dcfce7"),
        (450, 90, 610, 160, "cartesian\nik+trajectory", "#fef3c7"),
        (450, 190, 610, 260, "rrt+collision", "#fef3c7"),
        (670, 120, 830, 190, "apply_action", "#dbeafe"),
        (890, 90, 1050, 160, "grasp\nconstraint", "#fde68a"),
        (890, 190, 1050, 260, "gripper_urdf", "#fde68a"),
        (1110, 120, 1230, 190, "evaluator", "#dcfce7"),
        (670, 300, 830, 370, "episode writer", "#ede9fe"),
    ]
    for x0, y0, x1, y1, label, fill in boxes:
        draw_box(draw, (x0, y0, x1, y1), label, fill=fill, font=box_font)

    arrows = [
        ((170, 155), (230, 155)),
        ((390, 140), (450, 125)),
        ((390, 170), (450, 225)),
        ((610, 125), (670, 145)),
        ((610, 225), (670, 165)),
        ((830, 145), (890, 125)),
        ((830, 165), (890, 225)),
        ((1050, 125), (1110, 145)),
        ((1050, 225), (1110, 165)),
        ((750, 190), (750, 300)),
        ((1170, 190), (820, 300)),
    ]
    for start, end in arrows:
        draw_arrow(draw, start, end)

    draw.text(
        (60, 410),
        "Each sim step: plan -> apply joint targets -> grasp update -> safety check -> save PNG + npy arrays.",
        fill="#475569",
        font=box_font,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_episode_structure_diagram(path: Path) -> None:
    lines = [
        "episode_000001/",
        "├── images/",
        "│   ├── 000000.png  ──┐",
        "│   ├── 000001.png    │  step index t",
        "│   └── ...           │",
        "├── states.npy        ├─ states[t], actions[t], ee_poses[t], object_poses[t]",
        "├── actions.npy       │",
        "├── ee_poses.npy      │",
        "├── object_poses.npy  ┘",
        "└── metadata.json     episode-level: success, grasp_mode, language_instruction, ...",
        "",
        "Alignment rule: images/{step:06d}.png  <->  row t in every *.npy",
        "Typical shapes: states/actions [T, state_dim/action_dim], poses [T, 7]",
    ]
    image = render_text_image("Episode Directory Structure", lines, width=1180, body_size=20)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def lerobot_tree_lines() -> list[str]:
    if not LEROBOT_EXPORT.exists():
        return [
            "dataset/v1/lerobot_export/  (run export_lerobot_style.py locally)",
            "├── meta/",
            "│   ├── info.json",
            "│   ├── stats.json",
            "│   ├── episodes.jsonl",
            "│   └── tasks.jsonl",
            "├── data/chunk-000/",
            "│   └── episode_*.parquet",
            "└── videos/chunk-000/",
            "    └── observation.images.main/",
            "        └── episode_*.mp4",
        ]
    parquet_count = len(list((LEROBOT_EXPORT / "data" / "chunk-000").glob("*.parquet")))
    info = json.loads((LEROBOT_EXPORT / "meta" / "info.json").read_text(encoding="utf-8"))
    return [
        "dataset/v1/lerobot_export/",
        "├── meta/",
        "│   ├── info.json",
        "│   ├── stats.json",
        "│   ├── episodes.jsonl",
        "│   └── tasks.jsonl",
        "├── data/chunk-000/",
        f"│   └── episode_*.parquet  ({parquet_count} files)",
        "└── videos/chunk-000/",
        "    └── observation.images.main/",
        f"        └── episode_*.mp4  ({parquet_count} files)",
        "",
        f"codebase_version: {info.get('codebase_version')}",
        f"total_episodes: {info.get('total_episodes')}   total_frames: {info.get('total_frames')}",
        f"total_videos: {info.get('total_videos')}   fps: {info.get('fps')}",
        f"video_path: {info.get('video_path')}",
    ]


def save_lerobot_tree_screenshot(path: Path) -> None:
    image = render_text_image("LeRobot Export Layout", lerobot_tree_lines(), width=1180, body_size=20)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_lerobot_info_screenshot(path: Path) -> None:
    info_path = LEROBOT_EXPORT / "meta" / "info.json"
    if info_path.exists():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        features = info.get("features", {})
        feature_lines = []
        for name, spec in features.items():
            shape = spec.get("shape")
            feature_lines.append(f"  {name}: shape={shape}, dtype={spec.get('dtype')}")
        lines = [
            json.dumps(
                {
                    "codebase_version": info.get("codebase_version"),
                    "robot_type": info.get("robot_type"),
                    "total_episodes": info.get("total_episodes"),
                    "total_frames": info.get("total_frames"),
                    "fps": info.get("fps"),
                    "data_path": info.get("data_path"),
                },
                indent=2,
            ).splitlines(),
            "",
            "features:",
            *feature_lines,
        ]
        flat_lines: list[str] = []
        for item in lines:
            if isinstance(item, list):
                flat_lines.extend(item)
            else:
                flat_lines.append(item)
    else:
        flat_lines = [
            "meta/info.json not found locally.",
            "Run: python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export",
        ]
    image = render_text_image("LeRobot meta/info.json", flat_lines, width=1180, body_size=18)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def save_lerobot_parquet_screenshot(path: Path) -> None:
    parquet_path = LEROBOT_EXPORT / "data" / "chunk-000" / "episode_000000.parquet"
    lines: list[str]
    if parquet_path.exists():
        import pyarrow.parquet as pq

        table = pq.read_table(parquet_path)
        lines = [
            f"File: {parquet_path.relative_to(ROOT)}",
            f"Rows: {table.num_rows}   Columns: {table.num_columns}",
            "",
            "Schema:",
        ]
        for name in table.column_names:
            field = table.schema.field(name)
            lines.append(f"  {name}: {field.type}")
        lines.extend(["", "Sample row (frame_index=0):"])
        row = table.slice(0, 1).to_pydict()
        for name in table.column_names[:8]:
            value = row[name][0]
            rendered = repr(value)
            if len(rendered) > 72:
                rendered = rendered[:69] + "..."
            lines.append(f"  {name} = {rendered}")
    else:
        lines = [
            "episode_000000.parquet not found locally.",
            "Export first, then re-run this script.",
        ]
    image = render_text_image("LeRobot Parquet Episode", lines, width=1180, body_size=18)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> int:
    outputs = {
        "panda_p0_data_loop": save_panda_p0_data_loop(DIAGRAMS / "panda_p0_data_loop.png"),
        "panda_training_pipeline": save_panda_training_pipeline(DIAGRAMS / "panda_training_pipeline.png"),
        "panda_p0_demo_terminal": save_panda_p0_demo_terminal(SCREENSHOTS / "panda_p0_demo_terminal.png"),
        "bridge_handoff_bundle": save_bridge_handoff_bundle(SCREENSHOTS / "bridge_handoff_bundle.png"),
        "data_cleaning_lerobot_flow": save_data_cleaning_lerobot_flow(
            DIAGRAMS / "data_cleaning_lerobot_flow.png"
        ),
        "training_methods_matrix": save_training_methods_matrix(DIAGRAMS / "training_methods_matrix.png"),
        "architecture": save_architecture_diagram(DIAGRAMS / "architecture.png"),
        "data_flow": save_data_flow_diagram(DIAGRAMS / "data_flow_pick_lift.png"),
        "episode_structure": save_episode_structure_diagram(DIAGRAMS / "episode_structure.png"),
        "lerobot_tree": save_lerobot_tree_screenshot(SCREENSHOTS / "lerobot_export_tree.png"),
        "lerobot_info": save_lerobot_info_screenshot(SCREENSHOTS / "lerobot_meta_info.png"),
        "lerobot_parquet": save_lerobot_parquet_screenshot(SCREENSHOTS / "lerobot_parquet_schema.png"),
    }
    print("Generated portfolio assets:")
    for name in outputs:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
