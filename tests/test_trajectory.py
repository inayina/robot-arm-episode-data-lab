from __future__ import annotations

import numpy as np

from scripts.collect_episode import smooth_trajectory


def test_smooth_trajectory_starts_and_ends_at_expected_joint_targets() -> None:
    start = smooth_trajectory(step=0, num_steps=5, action_dim=7)
    end = smooth_trajectory(step=4, num_steps=5, action_dim=7)

    np.testing.assert_allclose(
        start,
        np.array([0.0, 0.45, 0.0, -1.35, 0.0, 1.1, 0.0], dtype=np.float32),
    )
    np.testing.assert_allclose(
        end,
        np.array([-0.35, 0.65, 0.2, -1.15, -0.1, 1.35, 0.25], dtype=np.float32),
    )


def test_smooth_trajectory_respects_action_dimension_and_single_step() -> None:
    action = smooth_trajectory(step=0, num_steps=1, action_dim=3)

    assert action.shape == (3,)
    np.testing.assert_allclose(
        action,
        np.array([-0.35, 0.65, 0.2], dtype=np.float32),
    )


def test_smooth_trajectory_midpoint_is_between_start_and_end() -> None:
    start = smooth_trajectory(step=0, num_steps=3, action_dim=7)
    middle = smooth_trajectory(step=1, num_steps=3, action_dim=7)
    end = smooth_trajectory(step=2, num_steps=3, action_dim=7)

    lower = np.minimum(start, end)
    upper = np.maximum(start, end)

    assert np.all(middle >= lower)
    assert np.all(middle <= upper)
    np.testing.assert_allclose(middle, (start + end) / 2.0, atol=1e-6)
