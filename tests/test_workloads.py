import math

import numpy as np
import pytest

from schedlab.workloads import CLASSES, SPLITS, generate, n_accelerators

import tomllib
from itertools import combinations
from pathlib import Path

from schedlab.model import make_instance
from schedlab.workloads import assert_separated, experiment_matrix

CONFIGS = Path(__file__).resolve().parent.parent / "configs"


def config_matrix(name):
    cfg = tomllib.loads((CONFIGS / name).read_text())
    return experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])


@pytest.fixture(scope="module")
def matrix():
    """Every instance of the planned full experiment, by split, built from configs/full.toml."""
    return config_matrix("full.toml")


def test_matrix_sizes(matrix):
    assert {s: len(v) for s, v in matrix.items()} == dict(train=1080, val=180, test_id=360, test_ood=90)
    assert min(i.n for v in matrix.values() for i in v) == 50  # no empty or degenerate experimental instance


@pytest.mark.parametrize("name", ["full.toml", "pilot.toml", "cost_probe.toml"])
def test_experimental_matrix_has_no_duplicates_and_no_cross_split_overlap(name):
    by_split = config_matrix(name)
    hashes = {s: [i.meta["hash"] for i in v] for s, v in by_split.items()}
    for s, h in hashes.items():
        assert len(h) > 0 and len(set(h)) == len(h), f"duplicate instances inside {s}"
    for a, b in combinations(hashes, 2):                       # every pair of splits
        assert not set(hashes[a]) & set(hashes[b]), f"{a} and {b} share instances"
    everything = [h for v in hashes.values() for h in v]
    assert len(set(everything)) == len(everything)
    ids = [i.id for v in by_split.values() for i in v]
    seeds = [i.meta["seed"] for v in by_split.values() for i in v]
    assert len(set(ids)) == len(ids) and len(set(seeds)) == len(seeds)
    assert assert_separated(by_split) == {s: len(v) for s, v in by_split.items()}   # the runner's own check agrees


def test_pilot_and_full_matrices_do_not_share_instances_across_different_splits():
    """The pilot runs on val. None of its instances may be a train or test instance of the full campaign."""
    full, pilot = config_matrix("full.toml"), config_matrix("pilot.toml")
    pilot_val = {i.meta["hash"] for i in pilot["val"]}
    for split in ("train", "test_id", "test_ood"):
        assert not pilot_val & {i.meta["hash"] for i in full[split]}


def test_empty_workloads_are_fixtures_not_experimental_instances():
    """An empty workload has no content, so all of them share one hash regardless of split.
    They are therefore excluded from experimental matrices, and the separation check rejects them."""
    a, b = generate("regular", 0, 2, "train", 0), generate("regular", 0, 2, "test_id", 0)
    assert a.n == b.n == 0 and a.meta["hash"] == b.meta["hash"]
    with pytest.raises(ValueError, match="share instances"):
        assert_separated({"train": [a], "test_id": [b]})
    with pytest.raises(ValueError, match="edge-case fixtures"):
        experiment_matrix(dict(sizes=[0, 50], processors=[2], classes=["regular"], instances={"val": 1}))


def test_separation_check_detects_violations():
    x, y = generate("regular", 20, 2, "val", 0), generate("regular", 20, 2, "val", 1)
    assert assert_separated({"a": [x], "b": [y]}) == {"a": 1, "b": 1}
    with pytest.raises(ValueError, match="duplicate"):
        assert_separated({"a": [x, x]})
    with pytest.raises(ValueError, match="share"):
        assert_separated({"a": [x], "b": [y, x]})
    # identical content built independently is still caught: the check is on content, not object identity
    clone = make_instance("clone", x.m, [(u, v) for v in range(x.n) for u in x.preds[v]], x.cost,
                          dict(x.meta))
    with pytest.raises(ValueError, match="share"):
        assert_separated({"a": [x], "b": [clone]})


def test_single_task_instances_differ_across_splits():
    hashes = {generate("regular", 1, 2, s, 0).meta["hash"] for s in SPLITS}
    assert len(hashes) == len(SPLITS)


def test_ood_cells_are_labelled(matrix):
    labels = {i.meta["label"] for i in matrix["test_ood"]}
    assert len(labels) == 9 and all("/" in x for x in labels)
    assert {i.meta["label"] for i in matrix["test_id"]} == set(CLASSES)


def test_dag_invariants(matrix):
    for split, insts in matrix.items():
        for inst in insts:
            n = inst.n
            assert inst.cost.shape == (n, inst.m) and (inst.cost > 0).all() and np.isfinite(inst.cost).all()
            for v in range(n):
                assert all(0 <= u < v for u in inst.preds[v])            # topological ids => acyclic
                assert len(set(inst.preds[v])) == len(inst.preds[v])
                assert all(v in inst.preds[w] for w in inst.succs[v])
            if inst.meta["family"] == "layered":
                widths = inst.meta["widths"]
                assert sum(widths) == n and min(widths) >= 1
                assert all(inst.preds[v] for v in range(widths[0], n))   # only first-layer tasks are sources
                assert not any(inst.preds[v] for v in range(widths[0]))


def test_same_arguments_same_instance():
    for c in CLASSES:
        a, b = generate(c, 60, 4, "val", 3), generate(c, 60, 4, "val", 3)
        assert a.meta["hash"] == b.meta["hash"] and a.preds == b.preds and np.array_equal(a.cost, b.cost)


def test_every_argument_changes_the_instance():
    base = generate("irregular", 60, 4, "val", 3).meta["hash"]
    variants = [
        generate("irregular", 60, 4, "val", 4),
        generate("irregular", 60, 4, "test_id", 3),
        generate("irregular", 60, 8, "val", 3),
        generate("irregular", 61, 4, "val", 3),
        generate("regular", 60, 4, "val", 3),
        generate("irregular", 60, 4, "val", 3, family="forkjoin"),
        generate("irregular", 60, 4, "val", 3, work_cv=3.0),
        generate("irregular", 60, 4, "val", 3, campaign_seed=1),
    ]
    hashes = [v.meta["hash"] for v in variants]
    assert base not in hashes and len(set(hashes)) == len(hashes)


@pytest.mark.parametrize("cls", list(CLASSES))
def test_work_variability_matches_class(cls):
    cv = CLASSES[cls][0]
    work = np.concatenate([generate(cls, 200, 4, "train", i).cost[:, 0] for i in range(20)])  # column 0 is a CPU
    assert np.log(work).std() == pytest.approx(math.sqrt(math.log(1 + cv**2)), rel=0.10)


def test_ood_cv_override():
    work = np.concatenate([generate("irregular", 200, 4, "test_ood", i, work_cv=3.0).cost[:, 0] for i in range(20)])
    assert np.log(work).std() == pytest.approx(math.sqrt(math.log(10)), rel=0.10)


def test_layer_width_regularity():
    for i in range(20):
        w = generate("regular", 100, 4, "train", i).meta["widths"]
        assert max(w) - min(w) <= 1
    assert any(max(w) - min(w) > 1 for w in (generate("irregular", 100, 4, "train", i).meta["widths"]
                                             for i in range(20)))


@pytest.mark.parametrize("m", [1, 2, 3, 4, 8, 16])
def test_platforms(m):
    h = generate("regular", 80, m, "train", 0)
    assert (h.cost == h.cost[:, :1]).all()                                # homog: identical columns
    x = generate("heterogeneous", 80, m, "train", 0)
    k = n_accelerators(m)
    assert k == {1: 0, 2: 1, 3: 1, 4: 1, 8: 2, 16: 4}[m]
    assert (x.cost[:, : m - k] == x.cost[:, :1]).all()                    # CPUs identical
    if k:
        ratio = x.cost[:, 0] / x.cost[:, -1]
        assert (x.cost[:, m - k:] == x.cost[:, -1:]).all()
        assert ratio.min() >= 0.25 * (1 - 1e-12) and ratio.max() <= 32 * (1 + 1e-12)
        assert len(np.unique(ratio)) > 10                                 # per-task affinity, not a scalar speed


def test_some_tasks_are_slower_on_the_accelerator():
    x = generate("heterogeneous", 400, 4, "train", 0)
    assert (x.cost[:, -1] > x.cost[:, 0]).any() and (x.cost[:, -1] < x.cost[:, 0]).any()


def test_forkjoin_structure():
    for n in (1, 2, 3, 7, 50, 100):
        inst = generate("irregular", n, 4, "test_ood", 0, family="forkjoin")
        assert inst.n == n and not inst.preds[0]
        assert all(inst.preds[v] for v in range(1, n))                    # one connected component from task 0
    big = generate("irregular", 100, 4, "test_ood", 0, family="forkjoin")
    assert max(len(p) for p in big.preds) >= 2                            # there is at least one join


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_tiny_sizes(n):
    for c in CLASSES:
        for fam in ("layered", "forkjoin"):
            inst = generate(c, n, 2, "val", 0, family=fam)
            assert inst.n == n and inst.cost.shape == (n, 2)


@pytest.mark.parametrize("kwargs", [
    dict(workload_class="nope"), dict(split="holdout"), dict(family="tree"),
    dict(n=-1), dict(m=0), dict(index=-1), dict(campaign_seed=-5),
])
def test_bad_arguments_rejected(kwargs):
    args = dict(workload_class="regular", n=10, m=2, split="val", index=0)
    args.update(kwargs)
    with pytest.raises(ValueError):
        generate(**args)
