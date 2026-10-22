"""Baseline list-scheduling heuristics: task rule x processor rule, plus MINMIN.

Every heuristic picks among list-ready tasks and places with gap insertion by default.
Ties: lowest task id, then lowest processor id.
"""
from __future__ import annotations

from functools import partial

from .model import Instance, Schedule, ScheduleBuilder, upward_rank


def _static_keys(inst: Instance, task_rule: str):
    """Smaller key = higher priority. None means the key is dynamic (FCFS: ready time)."""
    if task_rule == "FCFS":
        return None
    mean = inst.cost.mean(axis=1)
    if task_rule == "SPT":
        return mean.tolist()
    if task_rule == "LPT":
        return (-mean).tolist()
    if task_rule == "RANKU":
        return (-upward_rank(inst)).tolist()
    raise ValueError(f"unknown task rule {task_rule!r}")


def list_schedule(inst: Instance, task_rule: str, proc_rule: str, insert: bool = True) -> Schedule:
    if proc_rule not in ("EAT", "EFT"):
        raise ValueError(f"unknown processor rule {proc_rule!r}")
    b = ScheduleBuilder(inst)
    keys = _static_keys(inst, task_rule) or b.ready_time  # FCFS reads the live ready times
    score = b.est if proc_rule == "EAT" else b.eft        # EAT is cost-blind, EFT is cost-aware
    while not b.done():
        t = min(b.ready, key=lambda t: (keys[t], t))
        p = min(range(inst.m), key=lambda p: (score(t, p, insert), p))
        b.place(t, p, insert)
    return b.schedule()


def minmin(inst: Instance, insert: bool = True) -> Schedule:
    b = ScheduleBuilder(inst)
    while not b.done():
        _, t, p = min((b.eft(t, p, insert), t, p) for t in b.ready for p in range(inst.m))
        b.place(t, p, insert)
    return b.schedule()


def _as_scheduler(fn, inst: Instance, rng=None, insert: bool = True) -> tuple[Schedule, dict]:
    """Common scheduler signature: (inst, rng) -> (Schedule, info). Heuristics ignore rng."""
    return fn(inst, insert=insert), {}


HEURISTICS = {
    "FCFS-EAT": partial(_as_scheduler, partial(list_schedule, task_rule="FCFS", proc_rule="EAT")),
    "FCFS-EFT": partial(_as_scheduler, partial(list_schedule, task_rule="FCFS", proc_rule="EFT")),
    "SPT-EFT": partial(_as_scheduler, partial(list_schedule, task_rule="SPT", proc_rule="EFT")),
    "LPT-EFT": partial(_as_scheduler, partial(list_schedule, task_rule="LPT", proc_rule="EFT")),
    "HEFT": partial(_as_scheduler, partial(list_schedule, task_rule="RANKU", proc_rule="EFT")),
    "MINMIN": partial(_as_scheduler, minmin),
}
