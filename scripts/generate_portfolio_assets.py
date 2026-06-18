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
