"""Async vs sync action-chunk queue scheduler for S4 timing diagnostics.

Wraps :class:`ActionChunkQueue` (chunk=10 / execute K=5). Does not load weights,
does not start Isaac, and never claims task success.

Modes
-----
* **sync**: when the execute queue is empty, block the control tick on
  ``infer_chunk_fn`` before popping.
* **async_double_buffer**: when pending drops to 0 (or optionally early), kick
  off a background infer; control ticks keep popping (or count underrun) until
  the future completes and ``push_chunk`` swaps the buffer.
"""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from training.smolvla_s3.runtime_s4 import (
    DEFAULT_CONTRACT,
    ActionChunkQueue,
    S4RuntimeContract,
)

ChunkFn = Callable[[], tuple[Sequence[Sequence[float]], float]]
# Returns (chunk[chunk_size][action_dim], inference_latency_ms)


@dataclass
class QueueRuntimeTick:
    tick: int
    t_s: float
    mode: str
    pending_before: int
    action: tuple[float, ...] | None
    underrun: bool
    infer_started: bool
    infer_completed: bool
    deadline_miss: bool  # tick wall > control period (sync block)


@dataclass
class QueueRuntimeReport:
    mode: str
    control_rate_hz: float
    replan_period_s: float
    chunk_size: int
    execute_k: int
    n_ticks: int
    underruns: int
    deadline_misses: int
    infer_calls: int
    inference_latency_ms: list[float] = field(default_factory=list)
    tick_wall_ms: list[float] = field(default_factory=list)
    dropped_stale_actions: int = 0
    claims_task_success: bool = False
    async_double_buffer: bool = False

    def summary(self) -> dict[str, Any]:
        def _pct(values: list[float], q: float) -> float | None:
            if not values:
                return None
            ordered = sorted(values)
            index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
            return float(ordered[index])

        period_ms = 1000.0 / self.control_rate_hz
        return {
            "mode": self.mode,
            "async_double_buffer": self.async_double_buffer,
            "control_rate_hz": self.control_rate_hz,
            "control_period_ms": period_ms,
            "replan_period_s": self.replan_period_s,
            "chunk_size": self.chunk_size,
            "execute_k": self.execute_k,
            "n_ticks": self.n_ticks,
            "underruns": self.underruns,
            "underrun_rate": (
                float(self.underruns / self.n_ticks) if self.n_ticks else None
            ),
            "deadline_misses": self.deadline_misses,
            "deadline_miss_rate": (
                float(self.deadline_misses / self.n_ticks) if self.n_ticks else None
            ),
            "infer_calls": self.infer_calls,
            "inference_latency_ms_p50": _pct(self.inference_latency_ms, 0.50),
            "inference_latency_ms_p95": _pct(self.inference_latency_ms, 0.95),
            "inference_latency_ms_max": (
                float(max(self.inference_latency_ms))
                if self.inference_latency_ms
                else None
            ),
            "tick_wall_ms_p50": _pct(self.tick_wall_ms, 0.50),
            "tick_wall_ms_p95": _pct(self.tick_wall_ms, 0.95),
            "tick_wall_ms_max": (
                float(max(self.tick_wall_ms)) if self.tick_wall_ms else None
            ),
            "fits_replan_budget": (
                None
                if not self.inference_latency_ms
                else float(max(self.inference_latency_ms))
                <= 1000.0 * self.replan_period_s
            ),
            "dropped_stale_actions": self.dropped_stale_actions,
            "claims_task_success": False,
            "ran_isaac": False,
        }


class SyncQueueScheduler:
    """Block the control tick on inference whenever the execute queue is empty."""

    def __init__(
        self,
        *,
        infer_chunk_fn: ChunkFn,
        contract: S4RuntimeContract = DEFAULT_CONTRACT,
    ) -> None:
        self.infer_chunk_fn = infer_chunk_fn
        self.contract = contract
        self.queue = ActionChunkQueue(
            chunk_size=contract.chunk_size, execute_k=contract.n_action_steps
        )
        self.infer_calls = 0

    def reset(self) -> None:
        self.queue.reset()
        self.infer_calls = 0

    def tick(self, *, tick: int, t_s: float) -> QueueRuntimeTick:
        t0 = time.perf_counter()
        pending_before = self.queue.pending
        infer_started = False
        infer_completed = False
        if pending_before == 0:
            infer_started = True
            chunk, lat_ms = self.infer_chunk_fn()
            self.infer_calls += 1
            self.queue.push_chunk(chunk, inference_latency_ms=lat_ms)
            infer_completed = True
        action = self.queue.pop_action(now_s=t_s)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        period_ms = 1000.0 / self.contract.control_rate_hz
        return QueueRuntimeTick(
            tick=tick,
            t_s=t_s,
            mode="sync",
            pending_before=pending_before,
            action=action,
            underrun=action is None,
            infer_started=infer_started,
            infer_completed=infer_completed,
            deadline_miss=wall_ms > period_ms,
        )


class AsyncDoubleBufferScheduler:
    """Prefetch next chunk while executing current K; swap only when empty.

    Ready chunks are held in ``_ready`` until the execute queue drains, so an
    early-finishing infer cannot truncate the current K window (unlike a naive
    ``push_chunk`` that clears pending actions).
    """

    def __init__(
        self,
        *,
        infer_chunk_fn: ChunkFn,
        contract: S4RuntimeContract = DEFAULT_CONTRACT,
    ) -> None:
        self.infer_chunk_fn = infer_chunk_fn
        self.contract = contract
        self.queue = ActionChunkQueue(
            chunk_size=contract.chunk_size, execute_k=contract.n_action_steps
        )
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="s4-async")
        self._future: Future | None = None
        self._ready: tuple[Sequence[Sequence[float]], float] | None = None
        self.infer_calls = 0

    def reset(self) -> None:
        if self._future is not None and not self._future.done():
            self._future.cancel()
        self._future = None
        self._ready = None
        self.queue.reset()
        self.infer_calls = 0

    def close(self) -> None:
        self.reset()
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _harvest_future(self) -> bool:
        if self._future is None or not self._future.done():
            return False
        self._ready = self._future.result()
        self._future = None
        return True

    def _launch_prefetch(self) -> bool:
        if self._future is not None or self._ready is not None:
            return False
        if self.queue.pending <= 0:
            return False
        self.infer_calls += 1
        self._future = self._pool.submit(self.infer_chunk_fn)
        return True

    def _install_ready(self) -> bool:
        if self._ready is None or self.queue.pending > 0:
            return False
        chunk, lat_ms = self._ready
        self._ready = None
        self.queue.push_chunk(chunk, inference_latency_ms=lat_ms)
        return True

    def tick(self, *, tick: int, t_s: float) -> QueueRuntimeTick:
        t0 = time.perf_counter()
        pending_before = self.queue.pending
        infer_started = False
        infer_completed = False

        infer_completed = self._harvest_future()

        if self.queue.pending == 0:
            if self._ready is not None:
                infer_completed = self._install_ready() or infer_completed
            elif self._future is not None:
                # Still in flight from previous window — must wait (overlap miss).
                self._ready = self._future.result()
                self._future = None
                infer_completed = True
                self._install_ready()
            else:
                # Cold start: block once, then prefetch the following chunk.
                chunk, lat_ms = self.infer_chunk_fn()
                self.infer_calls += 1
                self.queue.push_chunk(chunk, inference_latency_ms=lat_ms)
                infer_started = True
                infer_completed = True

        action = self.queue.pop_action(now_s=t_s)
        # After we have a live execute buffer, prefetch the *next* chunk.
        if not infer_started:
            infer_started = self._launch_prefetch()

        wall_ms = (time.perf_counter() - t0) * 1000.0
        period_ms = 1000.0 / self.contract.control_rate_hz
        return QueueRuntimeTick(
            tick=tick,
            t_s=t_s,
            mode="async_double_buffer",
            pending_before=pending_before,
            action=action,
            underrun=action is None,
            infer_started=infer_started,
            infer_completed=infer_completed,
            deadline_miss=wall_ms > period_ms,
        )


def run_scheduler(
    scheduler: SyncQueueScheduler | AsyncDoubleBufferScheduler,
    *,
    n_ticks: int,
    mode: str,
    pace_realtime: bool = False,
) -> tuple[QueueRuntimeReport, list[QueueRuntimeTick]]:
    """Run ``n_ticks`` control steps.

    When ``pace_realtime`` is True, sleep to honor ``control_rate_hz`` so that
    async prefetch can overlap the K-step execute window (required for a fair
    GPU bench). CPU unit tests keep the default (as-fast-as-possible).
    """
    contract = scheduler.contract
    dt = 1.0 / contract.control_rate_hz
    period_ms = 1000.0 * dt
    ticks: list[QueueRuntimeTick] = []
    walls: list[float] = []
    deadline_misses = 0
    underruns = 0
    t_origin = time.perf_counter()
    for i in range(n_ticks):
        t_s = i * dt
        t0 = time.perf_counter()
        event = scheduler.tick(tick=i, t_s=t_s)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        event = QueueRuntimeTick(
            tick=event.tick,
            t_s=event.t_s,
            mode=event.mode,
            pending_before=event.pending_before,
            action=event.action,
            underrun=event.underrun,
            infer_started=event.infer_started,
            infer_completed=event.infer_completed,
            deadline_miss=wall_ms > period_ms,
        )
        ticks.append(event)
        walls.append(wall_ms)
        deadline_misses += int(event.deadline_miss)
        underruns += int(event.underrun)
        if pace_realtime:
            target = t_origin + (i + 1) * dt
            delay = target - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
    report = QueueRuntimeReport(
        mode=mode,
        control_rate_hz=contract.control_rate_hz,
        replan_period_s=contract.replan_period_s,
        chunk_size=contract.chunk_size,
        execute_k=contract.n_action_steps,
        n_ticks=n_ticks,
        underruns=underruns,
        deadline_misses=deadline_misses,
        infer_calls=scheduler.infer_calls,
        inference_latency_ms=list(scheduler.queue.stats.inference_latency_ms),
        tick_wall_ms=walls,
        dropped_stale_actions=scheduler.queue.stats.dropped_stale_actions,
        async_double_buffer=(mode == "async_double_buffer"),
    )
    return report, ticks
