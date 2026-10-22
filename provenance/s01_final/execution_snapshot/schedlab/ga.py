"""S01: genetic algorithm for DAG scheduling, with random-search and hill-climbing controls.

Chromosome: keys in [0, 1]^n (task priorities) and assign in {0..m-1}^n (processor per task).
decode() always yields a feasible schedule, so no repair or penalty is needed.
Every method here runs exactly max_evals schedule evaluations (seed individuals included).
"""
from __future__ import annotations

import time

import numpy as np

from .heuristics import HEURISTICS
from .model import Instance, Schedule, ScheduleBuilder

METHODS = ("GA", "GA-UNSEEDED", "GA-KEYS-EFT", "RANDOM-SEARCH", "HILL-CLIMB")

DEFAULTS = dict(
    population=60,
    max_evals=6000,
    tournament=3,
    crossover_prob=0.9,
    key_sigma=0.15,
    mutations_per_chromosome=1.0,   # expected mutated genes per array; per-gene rate = this / n
    elite=2,
    seed_heuristics=("HEFT", "MINMIN", "FCFS-EAT"),
)


def decode(inst: Instance, keys, assign=None) -> Schedule:
    """Place the ready task with the highest key (ties: lowest id) on assign[t], append mode.
    assign=None is the restricted GA-KEYS-EFT decoder: processor with the earliest finish (ties: lowest id)."""
    b = ScheduleBuilder(inst)
    key = keys.tolist() if hasattr(keys, "tolist") else list(keys)
    proc = None if assign is None else (assign.tolist() if hasattr(assign, "tolist") else list(assign))
    ready, procs = b.ready, range(inst.m)
    while ready:  # ready is sorted by id, and max() returns the first maximum
        t = max(ready, key=key.__getitem__)
        b.place(t, proc[t] if proc is not None else min(procs, key=lambda p: (b.eft(t, p), p)))
    return b.schedule()


def encode(sched: Schedule) -> tuple[np.ndarray, np.ndarray]:
    """Chromosome that decodes back to the given semi-active schedule: keys decrease in start-time order."""
    n = len(sched.start)
    keys = np.empty(n)
    keys[sorted(range(n), key=lambda t: (sched.start[t], t))] = 1.0 - np.arange(n) / max(n, 1)
    return keys, sched.proc.astype(np.int64)


def _check_config(cfg: dict) -> None:
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"unknown GA settings: {sorted(unknown)}")
    if cfg["population"] < 2 or not 0 <= cfg["elite"] < cfg["population"]:
        raise ValueError("need population >= 2 and 0 <= elite < population")
    if cfg["max_evals"] < 1 or cfg["tournament"] < 1:
        raise ValueError("need max_evals >= 1 and tournament >= 1")
    if not 0 <= cfg["crossover_prob"] <= 1 or cfg["key_sigma"] <= 0 or cfg["mutations_per_chromosome"] <= 0:
        raise ValueError("need 0 <= crossover_prob <= 1, key_sigma > 0, mutations_per_chromosome > 0")
    bad = [h for h in cfg["seed_heuristics"] if h not in HEURISTICS]
    if bad or len(cfg["seed_heuristics"]) > cfg["population"]:
        raise ValueError(f"seed_heuristics must be known heuristics, at most `population` of them; bad: {bad}")


def optimize(inst: Instance, rng: np.random.Generator, method: str = "GA", **settings) -> tuple[Schedule, dict]:
    """Run one search method for exactly max_evals evaluations. Returns the best schedule found and info."""
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    cfg = {**DEFAULTS, **settings}
    _check_config(cfg)
    n, m, P, B = inst.n, inst.m, cfg["population"], cfg["max_evals"]
    if n == 0:  # nothing to search
        return ScheduleBuilder(inst).schedule(), dict(fitness_evals=0, trace=[], last_improvement_eval=0)
    t0 = time.perf_counter()
    rate = min(1.0, cfg["mutations_per_chromosome"] / n)
    keys_only = method == "GA-KEYS-EFT"
    best = dict(f=float("inf"), sched=None, at=0)
    evals, trace = 0, []

    def evaluate(keys, assign) -> float:
        nonlocal evals
        s = decode(inst, keys, None if keys_only else assign)
        evals += 1
        f = s.makespan
        if f < best["f"]:  # strict: the earliest best candidate is kept
            best.update(f=f, sched=s, at=evals)
        return f

    def log(generation: int, fits) -> None:
        trace.append((generation, evals, time.perf_counter() - t0, best["f"], float(np.mean(fits))))

    def mutate(keys, assign, force: bool = False):
        mk, ma = rng.random(keys.shape) < rate, rng.random(assign.shape) < rate
        if force and not (mk.any() or ma.any()):  # hill climbing needs a move
            (mk if rng.random() < 0.5 else ma)[rng.integers(n)] = True
        keys = np.clip(keys + mk * rng.normal(0.0, cfg["key_sigma"], keys.shape), 0.0, 1.0)
        return keys, np.where(ma, rng.integers(m, size=assign.shape), assign)

    seeds = [] if method == "GA-UNSEEDED" else [encode(HEURISTICS[h](inst, None)[0]) for h in cfg["seed_heuristics"]]

    if method in ("RANDOM-SEARCH", "HILL-CLIMB"):
        fits = [evaluate(k, a) for k, a in seeds[:B]]
        if method == "HILL-CLIMB":
            if fits:
                i = int(np.argmin(fits))  # first best seed
                cur_k, cur_a, cur_f = *seeds[i], fits[i]
            else:
                cur_k, cur_a = rng.random(n), rng.integers(m, size=n)
                cur_f = evaluate(cur_k, cur_a)
                fits.append(cur_f)
        generation = 0
        while True:
            if fits and (len(fits) >= P or evals == B):  # same logging cadence as one GA generation
                log(generation, fits)
                generation, fits = generation + 1, []
            if evals >= B:
                break
            if method == "RANDOM-SEARCH":
                fits.append(evaluate(rng.random(n), rng.integers(m, size=n)))
            else:
                k, a = mutate(cur_k, cur_a, force=True)
                f = evaluate(k, a)
                fits.append(f)
                if f <= cur_f:  # accept equal moves so the search can cross plateaus
                    cur_k, cur_a, cur_f = k, a, f
    else:
        pop_k, pop_a = rng.random((P, n)), rng.integers(m, size=(P, n))
        for i, (k, a) in enumerate(seeds):
            pop_k[i], pop_a[i] = k, a
        fit = np.full(P, np.inf)
        for i in range(min(P, B)):
            fit[i] = evaluate(pop_k[i], pop_a[i])
        log(0, fit[:min(P, B)])
        generation = 0
        while evals < B:
            generation += 1
            k = min(P - cfg["elite"], B - evals)  # the last generation is truncated to hit the budget exactly
            # tournament selection; sorting the candidates first makes argmin break ties by lowest index
            cand = np.sort(rng.integers(P, size=(2, k, cfg["tournament"])), axis=-1)
            pa, pb = np.take_along_axis(cand, fit[cand].argmin(axis=-1)[..., None], axis=-1)[..., 0]
            cross = (rng.random(k) < cfg["crossover_prob"])[:, None]
            child_k = np.where(cross & (rng.random((k, n)) < 0.5), pop_k[pb], pop_k[pa])  # uniform crossover,
            child_a = np.where(cross & (rng.random((k, n)) < 0.5), pop_a[pb], pop_a[pa])  # keys and assign separately
            child_k, child_a = mutate(child_k, child_a)
            child_f = np.array([evaluate(child_k[i], child_a[i]) for i in range(k)])
            elite = np.argsort(fit, kind="stable")[:cfg["elite"]]  # stable: ties by lowest index
            pop_k = np.concatenate([pop_k[elite], child_k])
            pop_a = np.concatenate([pop_a[elite], child_a])
            fit = np.concatenate([fit[elite], child_f])
            log(generation, fit)
            if len(fit) < P:  # truncated final generation; the budget is spent
                break
    return best["sched"], dict(fitness_evals=evals, trace=trace, last_improvement_eval=best["at"])
