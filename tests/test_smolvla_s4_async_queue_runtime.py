"""CPU tests for sync vs async double-buffer S4 queue schedulers."""

from __future__ import annotations

import time

from training.smolvla_s3.async_queue_runtime import (
    AsyncDoubleBufferScheduler,
    SyncQueueScheduler,
    run_scheduler,
)
from training.smolvla_s3.runtime_s4 import DEFAULT_CONTRACT


def _slow_chunk(latency_s: float = 0.05):
    def _fn():
        time.sleep(latency_s)
        action = [0.4, 0.0, 0.2, 0.0, 0.0, 0.0, 1.0, 1.0]
        chunk = [list(action) for _ in range(DEFAULT_CONTRACT.chunk_size)]
        return chunk, latency_s * 1000.0

    return _fn


def test_sync_deadline_misses_when_infer_exceeds_period() -> None:
    # control period = 100 ms; infer = 50 ms → only replan ticks miss? 
    # Actually sync blocks only when queue empty (every K=5 ticks).
    sched = SyncQueueScheduler(infer_chunk_fn=_slow_chunk(0.15))
    report, ticks = run_scheduler(sched, n_ticks=20, mode="sync")
    summary = report.summary()
    assert summary["infer_calls"] == 4  # 20/5
    assert summary["deadline_misses"] >= 4
    assert summary["underruns"] == 0
    assert summary["claims_task_success"] is False


def test_async_hides_infer_inside_replan_window() -> None:
    # Infer 150 ms < replan 500 ms; with realtime pacing, prefetch overlaps K.
    sched = AsyncDoubleBufferScheduler(infer_chunk_fn=_slow_chunk(0.15))
    try:
        report, ticks = run_scheduler(
            sched,
            n_ticks=20,
            mode="async_double_buffer",
            pace_realtime=True,
        )
    finally:
        sched.close()
    summary = report.summary()
    assert summary["underruns"] == 0
    assert summary["async_double_buffer"] is True
    # Only cold-start tick should miss the 100 ms deadline.
    assert summary["deadline_misses"] == 1
    assert ticks[0].deadline_miss is True
    assert all(not t.deadline_miss for t in ticks[1:])


def test_async_fits_replan_budget_flag() -> None:
    sched = SyncQueueScheduler(infer_chunk_fn=_slow_chunk(0.02))
    report, _ = run_scheduler(sched, n_ticks=10, mode="sync")
    assert report.summary()["fits_replan_budget"] is True
