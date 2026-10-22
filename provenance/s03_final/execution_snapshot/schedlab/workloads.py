"""Synthetic workloads: DAG families, cost matrices, class presets, seeded splits, content hashing."""
from __future__ import annotations

import hashlib
import math
import zlib

import numpy as np

from .model import Instance, make_instance

CAMPAIGN_SEED = 20261011
SPLITS = {"train": 0, "val": 1, "test_id": 2, "test_ood": 3}
FAMILIES = ("layered", "forkjoin")
MEAN_WORK = 100.0  # sim_tu

# class -> (work CV, irregular layer widths, platform)
CLASSES = {
    "regular": (0.1, False, "homog"),
    "irregular": (1.5, True, "homog"),
    "heterogeneous": (0.5, False, "hetero"),
    "irregular_hetero": (1.5, True, "hetero"),
}


def n_accelerators(m: int) -> int:
    """Accelerators on a hetero platform: about a quarter, at least 1, always leaving one CPU."""
    return min(max(1, round(m / 4)), m - 1)


def layered_dag(n: int, fatness: float, density: float, irregular: bool, rng) -> tuple[list, tuple]:
    """Layered random DAG. Returns (edges, layer widths). Tasks are numbered layer by layer."""
    if n == 0:
        return [], ()
    n_layers = min(n, max(2, round(math.sqrt(n) / fatness)))
    if irregular:
        w = rng.uniform(1.0, 2.0 * n / n_layers, n_layers)
        widths = 1 + rng.multinomial(n - n_layers, w / w.sum())
    else:
        widths = np.full(n_layers, n // n_layers)
        widths[: n % n_layers] += 1
    starts = np.concatenate(([0], np.cumsum(widths)))
    edges = set()
    for k in range(1, n_layers):
        lo, hi = int(starts[k - 1]), int(starts[k])  # previous layer is [lo, hi)
        for v in range(hi, int(starts[k + 1])):
            for _ in range(1 + rng.binomial(3, density)):
                u = rng.integers(lo, hi) if rng.random() < 0.8 else rng.integers(0, hi)
                edges.add((int(u), v))
    return sorted(edges), tuple(int(x) for x in widths)


def forkjoin_dag(n: int, rng) -> list:
    """Stages of: fork task -> parallel chains -> join task, until n tasks are used."""
    edges, nxt, prev_join = set(), 0, None
    while nxt < n:
        fork, nxt = nxt, nxt + 1
        if prev_join is not None:
            edges.add((prev_join, fork))
        tails = []
        width, length = int(rng.integers(2, 7)), int(rng.integers(1, 5))
        for _ in range(width):
            last = fork
            for _ in range(length):
                if nxt >= n:
                    break
                edges.add((last, nxt))
                last, nxt = nxt, nxt + 1
            tails.append(last)
        prev_join = None
        if nxt < n:
            prev_join, nxt = nxt, nxt + 1
            edges.update((t, prev_join) for t in tails)
    return sorted(edges)


def cost_matrix(n: int, m: int, work_cv: float, platform: str, rng) -> np.ndarray:
    """cost[t, p] in sim_tu. Base work is lognormal with mean MEAN_WORK and the given CV."""
    sigma2 = math.log(1.0 + work_cv**2)
    work = rng.lognormal(math.log(MEAN_WORK) - sigma2 / 2, math.sqrt(sigma2), n)
    cost = np.repeat(work[:, None], m, axis=1)
    if platform == "hetero":
        k = n_accelerators(m)  # the last k processors are accelerators
        accel = np.clip(rng.lognormal(math.log(4.0), 1.0, n), 0.25, 32.0)
        if k:
            cost[:, m - k:] = (work / accel)[:, None]
    return cost


def instance_hash(n: int, m: int, edges, cost: np.ndarray) -> str:
    h = hashlib.sha1(f"{n},{m};".encode())
    h.update(np.asarray(edges, dtype=np.int64).tobytes())
    h.update(np.ascontiguousarray(cost, dtype=np.float64).tobytes())
    return h.hexdigest()


def generate(workload_class: str, n: int, m: int, split: str, index: int, *, family: str = "layered",
             work_cv: float | None = None, campaign_seed: int = CAMPAIGN_SEED) -> Instance:
    """One reproducible instance. The seed depends on every argument, so splits never share a stream."""
    if workload_class not in CLASSES:
        raise ValueError(f"unknown workload class {workload_class!r}")
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    if family not in FAMILIES:
        raise ValueError(f"unknown family {family!r}")
    if min(n, index, campaign_seed) < 0 or m < 1:
        raise ValueError("need n >= 0, m >= 1, index >= 0, campaign_seed >= 0")
    cv, irregular, platform = CLASSES[workload_class]
    if work_cv is not None:
        cv = work_cv
    # crc32, not hash(): Python's hash() is salted per process
    entropy = [campaign_seed, SPLITS[split], zlib.crc32(f"{family}/{workload_class}/{cv}".encode()), n, m, index]
    rng = np.random.default_rng(np.random.SeedSequence(entropy))
    fatness = float(math.exp(rng.uniform(math.log(0.5), math.log(2.0))))
    density = float(rng.uniform(0.1, 0.5))
    if family == "layered":
        edges, widths = layered_dag(n, fatness, density, irregular, rng)
    else:
        edges, widths = forkjoin_dag(n, rng), ()
    cost = cost_matrix(n, m, cv, platform, rng)
    meta = dict(family=family, workload_class=workload_class, platform=platform, work_cv=cv, fatness=fatness,
                density=density, widths=widths, split=split, index=index, seed=tuple(entropy),
                hash=instance_hash(n, m, edges, cost))
    cv_tag = "" if work_cv is None else f"-cv{cv:g}"
    return make_instance(f"{family}-{workload_class}{cv_tag}-n{n}-m{m}-{split}-{index:04d}", m, edges, cost, meta)


# Out-of-distribution cells (EXPERIMENTAL_METHODOLOGY.md 2.4)
OOD_SETS = {
    "ood_size": [dict(workload_class=c, n=400, m=4) for c in CLASSES],
    "ood_procs": [dict(workload_class=c, n=200, m=16) for c in ("irregular", "irregular_hetero")],
    "ood_struct": [dict(workload_class=c, n=100, m=4, family="forkjoin") for c in ("irregular", "irregular_hetero")],
    "ood_cv": [dict(workload_class="irregular", n=100, m=4, work_cv=3.0)],
}


def experiment_matrix(workload: dict, campaign_seed: int = CAMPAIGN_SEED) -> dict[str, list[Instance]]:
    """Every instance of an experiment, by split, from the [workload] section of a config.

    This is the single definition of the experimental matrix: the runner and the separation
    test both use it. Empty workloads (n = 0) carry no content, so they all share one content
    hash; they are edge-case fixtures only and are rejected here.
    """
    if min(workload["sizes"]) < 1:
        raise ValueError("experimental problem sizes must be >= 1 (empty workloads are edge-case fixtures only)")
    out = {}
    for split, count in workload["instances"].items():
        if split == "test_ood":
            cells = [dict(c, label=f"{name}/{c['workload_class']}") for name in workload.get("ood", [])
                     for c in OOD_SETS[name]]
        else:
            cells = [dict(workload_class=c, n=n, m=m) for c in workload["classes"]
                     for n in workload["sizes"] for m in workload["processors"]]
        out[split] = []
        for cell in cells:
            label = cell.pop("label", cell["workload_class"])
            for i in range(count):
                inst = generate(split=split, index=i, campaign_seed=campaign_seed, **cell)
                inst.meta["label"] = label
                out[split].append(inst)
    return out


def assert_separated(by_split: dict[str, list[Instance]]) -> dict[str, int]:
    """Raise unless no content hash repeats inside a split or appears in two splits. Returns split sizes."""
    hashes = {s: [i.meta["hash"] for i in insts] for s, insts in by_split.items()}
    for s, h in hashes.items():
        if len(set(h)) != len(h):
            raise ValueError(f"duplicate instances inside split {s!r}")
    names = list(hashes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(hashes[a]) & set(hashes[b]):
                raise ValueError(f"splits {a!r} and {b!r} share instances")
    return {s: len(h) for s, h in hashes.items()}
