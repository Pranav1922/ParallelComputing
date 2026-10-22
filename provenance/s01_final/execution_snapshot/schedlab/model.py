"""Shared scheduling core: instance, schedule, schedule builder (the simulator), independent validator, bounds.

All times are simulated time units (sim_tu), not seconds.
"""
from __future__ import annotations

from bisect import insort
from dataclasses import dataclass, field
from functools import cached_property

import numpy as np


@dataclass(frozen=True, eq=False)
class Instance:
    """A task DAG plus a cost matrix. Build with make_instance(), which validates the input."""
    id: str
    n: int
    m: int
    preds: tuple[tuple[int, ...], ...]
    succs: tuple[tuple[int, ...], ...]
    cost: np.ndarray  # (n, m) float64, > 0, read-only
    meta: dict = field(default_factory=dict)

    @cached_property
    def cost_rows(self) -> list:
        """cost as nested lists, built once; the builder reads it on every decode."""
        return self.cost.tolist()


def make_instance(id: str, m: int, edges, cost, meta: dict | None = None) -> Instance:
    """Validate and build an Instance.

    Tasks must be numbered topologically: every edge (u, v) has u < v. That rules out cycles and
    self-loops by construction. Costs must be finite and strictly positive.
    """
    if isinstance(m, bool) or not isinstance(m, (int, np.integer)) or m < 1:
        raise ValueError(f"processor count must be an integer >= 1, got {m!r}")
    cost = np.array(cost, dtype=np.float64)
    if cost.ndim != 2 or cost.shape[1] != m:
        raise ValueError(f"cost must have shape (n, {m}), got {cost.shape}")
    if not np.isfinite(cost).all() or (cost <= 0).any():
        raise ValueError("costs must be finite and strictly positive")
    n = cost.shape[0]
    preds: list[list[int]] = [[] for _ in range(n)]
    succs: list[list[int]] = [[] for _ in range(n)]
    seen = set()
    for u, v in edges:
        u, v = int(u), int(v)
        if not 0 <= u < v < n:
            raise ValueError(f"edge ({u}, {v}) must satisfy 0 <= u < v < {n} (topological numbering, no cycles)")
        if (u, v) in seen:
            raise ValueError(f"duplicate edge ({u}, {v})")
        seen.add((u, v))
        preds[v].append(u)
        succs[u].append(v)
    cost.setflags(write=False)
    return Instance(id, n, int(m), tuple(tuple(sorted(x)) for x in preds),
                    tuple(tuple(sorted(x)) for x in succs), cost, dict(meta or {}))


@dataclass(frozen=True, eq=False)
class Schedule:
    proc: np.ndarray    # (n,) int
    start: np.ndarray   # (n,) float
    finish: np.ndarray  # (n,) float

    @property
    def makespan(self) -> float:
        return float(self.finish.max()) if len(self.finish) else 0.0


class ScheduleBuilder:
    """The execution simulator. Every scheduler builds its schedule through place().

    A task is ready once all its predecessors have been placed. place() never produces an
    infeasible schedule; it raises on a task that is not ready.
    """

    def __init__(self, inst: Instance):
        self.inst = inst
        self._cost = inst.cost_rows
        self.avail = [0.0] * inst.m            # finish of the last task on each processor
        self.ready_time = [0.0] * inst.n       # max finish over placed predecessors
        self._npred = [len(p) for p in inst.preds]
        self.ready = [t for t in range(inst.n) if not inst.preds[t]]  # kept sorted by task id
        self._busy: list[list[tuple[float, float]]] = [[] for _ in range(inst.m)]  # sorted intervals
        self._proc = [-1] * inst.n
        self._start = [0.0] * inst.n
        self._finish = [0.0] * inst.n
        self._placed = 0

    def est(self, t: int, p: int, insert: bool = False) -> float:
        """Earliest start of ready task t on processor p. insert=True may use an idle gap."""
        s = self.ready_time[t]
        if not insert:
            return max(self.avail[p], s)
        c = self._cost[t][p]
        # ponytail: linear gap scan, O(tasks on p); bisect to the first relevant interval if profiling says so
        for a, b in self._busy[p]:
            if s + c <= a:
                return s
            if b > s:
                s = b
        return s

    def eft(self, t: int, p: int, insert: bool = False) -> float:
        return self.est(t, p, insert) + self._cost[t][p]

    def place(self, t: int, p: int, insert: bool = False) -> None:
        if not 0 <= p < self.inst.m:
            raise ValueError(f"processor {p} out of range")
        if not 0 <= t < self.inst.n or self._proc[t] != -1 or self._npred[t] != 0:
            raise ValueError(f"task {t} is not ready (already placed, unknown, or has unplaced predecessors)")
        s = self.est(t, p, insert)
        f = s + self._cost[t][p]
        self._proc[t], self._start[t], self._finish[t] = p, s, f
        insort(self._busy[p], (s, f))
        if f > self.avail[p]:
            self.avail[p] = f
        self.ready.remove(t)
        for v in self.inst.succs[t]:
            if f > self.ready_time[v]:
                self.ready_time[v] = f
            self._npred[v] -= 1
            if self._npred[v] == 0:
                insort(self.ready, v)
        self._placed += 1

    def done(self) -> bool:
        return self._placed == self.inst.n

    def schedule(self) -> Schedule:
        if not self.done():
            raise ValueError("schedule is incomplete")
        return Schedule(np.array(self._proc, dtype=np.int64), np.array(self._start, dtype=np.float64),
                        np.array(self._finish, dtype=np.float64))


def _tol(x: float) -> float:
    return 1e-9 * max(1.0, abs(x))


def validate(inst: Instance, s: Schedule) -> list[str]:
    """Independent feasibility check. Uses only the instance and the three schedule arrays.

    Returns a list of violations; an empty list means the schedule is valid.
    """
    n, m = inst.n, inst.m
    proc, start, finish = np.asarray(s.proc), np.asarray(s.start), np.asarray(s.finish)
    if not (proc.shape == start.shape == finish.shape == (n,)):
        return [f"array shapes {proc.shape}, {start.shape}, {finish.shape} do not match ({n},)"]
    if n == 0:
        return []
    if not np.issubdtype(proc.dtype, np.integer):
        return ["processor array is not integer"]
    out = [f"task {t}: processor {proc[t]} out of range (unscheduled?)"
           for t in np.flatnonzero((proc < 0) | (proc >= m))]
    if not (np.isfinite(start).all() and np.isfinite(finish).all()):
        out.append("non-finite start or finish time")
    if out:
        return out
    for t in range(n):
        if start[t] < -_tol(0.0):
            out.append(f"task {t}: negative start {start[t]}")
        if abs(finish[t] - start[t] - inst.cost[t, proc[t]]) > _tol(finish[t]):
            out.append(f"task {t}: finish - start != cost on processor {proc[t]}")
        for u in inst.preds[t]:
            if start[t] < finish[u] - _tol(finish[u]):
                out.append(f"task {t}: starts at {start[t]} before predecessor {u} finishes at {finish[u]}")
    for p in range(m):
        ts = sorted(np.flatnonzero(proc == p).tolist(), key=lambda t: (start[t], t))
        for a, b in zip(ts, ts[1:]):
            if start[b] < finish[a] - _tol(finish[a]):
                out.append(f"processor {p}: tasks {a} and {b} overlap")
    return out


def _longest_path(inst: Instance, w) -> float:
    ef = [0.0] * inst.n
    for t in range(inst.n):  # ids are topological
        ef[t] = w[t] + max((ef[u] for u in inst.preds[t]), default=0.0)
    return max(ef, default=0.0)


def bounds(inst: Instance) -> dict:
    """Instance invariants: speedup baseline and makespan lower bound."""
    if inst.n == 0:
        return dict(serial_best=0.0, cp_min=0.0, work_lb=0.0, lower_bound=0.0)
    cmin = inst.cost.min(axis=1)
    cp_min = _longest_path(inst, cmin.tolist())
    work_lb = float(cmin.sum()) / inst.m
    return dict(serial_best=float(inst.cost.sum(axis=0).min()), cp_min=cp_min, work_lb=work_lb,
                lower_bound=max(cp_min, work_lb))


def upward_rank(inst: Instance) -> np.ndarray:
    """rank(t) = mean cost of t + max rank over successors."""
    mean = inst.cost.mean(axis=1).tolist()
    rank = [0.0] * inst.n
    for t in reversed(range(inst.n)):
        rank[t] = mean[t] + max((rank[v] for v in inst.succs[t]), default=0.0)
    return np.array(rank, dtype=np.float64)
