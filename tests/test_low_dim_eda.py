from __future__ import annotations

from training.scripts.eda_low_dim_dataset import quality_gate, trajectory_metrics


def test_trajectory_metrics_reports_episode_jitter() -> None:
    rows = []
    positions = [0.0, 0.01, 0.0, 0.01]
    for frame_index, position in enumerate(positions):
        rows.append({
            "episode_index": 3,
            "frame_index": frame_index,
            "timestamp": frame_index / 30.0,
            "observation.state": [position] * 7 + [1.0],
            "action": [position] * 7,
        })

    report = trajectory_metrics(rows)

    assert report["num_episodes"] == 1
    assert report["num_frames"] == 4
    episode = report["episodes"][0]
    assert episode["timestamp_strictly_increasing"] is True
    assert episode["joint_reversal_count"] == 14
    assert episode["joint_abs_step_rad"]["max"] == 0.01
    assert quality_gate(report)["passed"] is False
