import hashlib
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from schedlab.heuristics import HEURISTICS, list_schedule, minmin
from schedlab.model import bounds, make_instance, upward_rank, validate
from schedlab.workloads import CLASSES, generate
from test_model import append_replay, homog, recompute_times, same

NAMES = ["FCFS-EAT", "FCFS-EFT", "SPT-EFT", "LPT-EFT", "HEFT", "MINMIN"]
SIZES, PROCS = (1, 2, 5, 10, 20, 40, 80), (1, 2, 3, 4, 8, 16)


def campaign_instances(count=500):
    """The M1 validation campaign: 500 seeded instances over all classes, both families, n 1..80, m 1..16."""
    classes = list(CLASSES)
    for i in range(count):
        yield generate(classes[i % 4], SIZES[i % 7], PROCS[(i // 7) % 6], "test_id", i,
                       family="forkjoin" if i % 5 == 4 else "layered", campaign_seed=1)


def digest(instances):
    h = hashlib.sha1()
    for inst in instances:
        h.update(inst.meta["hash"].encode())
        for name in NAMES:
            s, _ = HEURISTICS[name](inst, None)
            h.update(s.proc.tobytes() + s.start.tobytes() + s.finish.tobytes())
    return h.hexdigest()


def test_registry_is_exactly_the_six_heuristics():
    assert list(HEURISTICS) == NAMES


def test_campaign_500_instances_valid_deterministic_reachable():
    seen = set()
    schedules = gaps_used = 0
    for inst in campaign_instances():
        seen.add((inst.meta["workload_class"], inst.meta["family"], inst.n, inst.m))
        b = bounds(inst)
        for name in NAMES:
            s, info = HEURISTICS[name](inst, None)
            where = f"{name} on {inst.id}"
            assert validate(inst, s) == [], where
            assert same(s, HEURISTICS[name](inst, None)[0]), f"not deterministic: {where}"
            # makespan and times recomputed without the builder
            start, finish = recompute_times(inst, s)
            assert np.array_equal(start, s.start) and np.array_equal(finish, s.finish), where
            assert s.makespan == finish.max(), where
            assert b["lower_bound"] * (1 - 1e-12) <= s.makespan <= inst.cost.max(axis=1).sum() * (1 + 1e-12), where
            if inst.m == 1:
                assert s.makespan == pytest.approx(b["serial_best"]), where
            # reachable by GA/RL: append mode reproduces the insertion schedule exactly
            assert same(append_replay(inst, s), s), where
            gaps_used += not same(s, HEURISTICS[name](inst, None, insert=False)[0])
            schedules += 1
    assert schedules == 3000
    assert {c for c, *_ in seen} == set(CLASSES) and {f for _, f, *_ in seen} == {"layered", "forkjoin"}
    assert {n for *_, n, _ in seen} == set(SIZES) and {m for *_, m in seen} == set(PROCS)
    assert gaps_used > 0  # insertion changed at least some schedules, so the reachability check is not trivial
    print(f"\ncampaign: 500 instances, {schedules} schedules valid; insertion changed {gaps_used} of them")


def test_deterministic_across_processes_and_hash_seeds():
    """Same digest in this process and in fresh interpreters with different PYTHONHASHSEED."""
    here = digest(campaign_instances(40))
    code = "from test_heuristics import digest, campaign_instances; print(digest(campaign_instances(40)))"
    root = Path(__file__).resolve().parent.parent
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=os.pathsep.join([str(root), str(root / "tests")]))
        out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
        assert out.stdout.strip() == here


def test_empty_workload():
    inst = generate("regular", 0, 3, "val", 0)
    for name in NAMES:
        s, _ = HEURISTICS[name](inst, None)
        assert len(s.proc) == 0 and s.makespan == 0 and validate(inst, s) == []


def test_single_task_goes_to_its_fastest_processor_when_cost_aware():
    inst = make_instance("one", 3, [], [[9.0, 2.0, 5.0]])
    for name in NAMES:
        s, _ = HEURISTICS[name](inst, None)
        assert s.proc[0] == (0 if name == "FCFS-EAT" else 1)   # EAT is cost-blind: lowest processor id


def test_independent_equal_tasks():
    for n, m in [(7, 3), (8, 4), (5, 8)]:
        inst = make_instance("indep", m, [], homog([4.0] * n, m))
        for name in NAMES:
            assert HEURISTICS[name](inst, None)[0].makespan == math.ceil(n / m) * 4.0


def test_tie_breaking_is_by_task_id_then_processor_id():
    inst = make_instance("ties", 2, [], homog([1.0] * 4, 2))
    for name in NAMES:
        s, _ = HEURISTICS[name](inst, None)
        assert s.proc.tolist() == [0, 1, 0, 1] and s.start.tolist() == [0, 0, 1, 1], name


def test_chain_is_serial_for_every_heuristic():
    inst = make_instance("chain", 4, [(i, i + 1) for i in range(5)], homog([1, 2, 3, 4, 5, 6], 4))
    for name in NAMES:
        s, _ = HEURISTICS[name](inst, None)
        assert s.makespan == 21 and sorted(s.start.tolist()) == s.start.tolist()


def placement_order(s):
    return sorted(range(len(s.start)), key=lambda t: (s.start[t], t))


def test_task_rule_semantics_on_one_processor():
    # one processor, independent tasks: the schedule order is the priority order
    inst = make_instance("prio", 1, [], [[5.0], [1.0], [3.0], [1.0]])
    assert placement_order(list_schedule(inst, "FCFS", "EFT")) == [0, 1, 2, 3]
    assert placement_order(list_schedule(inst, "SPT", "EFT")) == [1, 3, 2, 0]
    assert placement_order(list_schedule(inst, "LPT", "EFT")) == [0, 2, 1, 3]
    assert placement_order(minmin(inst)) == [1, 3, 2, 0]


def test_heft_follows_upward_rank():
    # 0 -> 2 (long tail), 1 independent and short: rank(0) = 1 + 10, rank(1) = 2, rank(2) = 10
    inst = make_instance("rank", 1, [(0, 2)], [[1.0], [2.0], [10.0]])
    assert upward_rank(inst).tolist() == [11, 2, 10]
    assert placement_order(list_schedule(inst, "RANKU", "EFT")) == [0, 2, 1]
    assert placement_order(list_schedule(inst, "SPT", "EFT")) == [0, 1, 2]


def test_fcfs_orders_by_ready_time():
    # 0 (long) -> 2, 1 (short) -> 3: task 3 becomes ready first and must be placed before task 2
    inst = make_instance("fcfs", 2, [(0, 2), (1, 3)], homog([5, 1, 1, 1], 2))
    s = list_schedule(inst, "FCFS", "EAT")
    assert s.start.tolist() == [0, 0, 5, 1]


def test_eat_is_cost_blind_and_eft_is_cost_aware():
    inst = make_instance("het", 2, [], [[10.0, 1.0], [10.0, 1.0]])
    assert list_schedule(inst, "FCFS", "EAT").proc.tolist() == [0, 1]
    assert list_schedule(inst, "FCFS", "EFT").proc.tolist() == [1, 1]


def test_fcfs_eat_equals_fcfs_eft_on_homogeneous_platforms():
    for i in range(40):
        inst = generate(("regular", "irregular")[i % 2], 40, (2, 4, 8)[i % 3], "val", i, campaign_seed=2)
        assert same(HEURISTICS["FCFS-EAT"](inst, None)[0], HEURISTICS["FCFS-EFT"](inst, None)[0])


def test_insertion_strictly_helps_fixed_priority_heuristics_on_crafted_gap():
    # A(0) -> B(1); C(2) independent. B is fast on p1, so it sits at [10,12] there and leaves [0,10] idle.
    inst = make_instance("gap", 2, [(0, 1)], [[10.0, 100.0], [30.0, 2.0], [20.0, 3.0]])
    for name in ("HEFT", "LPT-EFT"):
        with_gap = HEURISTICS[name](inst, None, insert=True)[0]
        appended = HEURISTICS[name](inst, None, insert=False)[0]
        assert with_gap.makespan == 12 and appended.makespan == 15, name
        assert with_gap.start[2] == 0 and with_gap.proc[2] == 1
        assert validate(inst, with_gap) == [] and validate(inst, appended) == []


def test_append_mode_diagnostic():
    """Diagnostic, not a guarantee: mean makespan with insertion vs forced append (greedy rules can go either way)."""
    insts = list(campaign_instances(200))
    print()
    for name in NAMES:
        ins = np.array([HEURISTICS[name](i, None, insert=True)[0].makespan for i in insts])
        app = np.array([HEURISTICS[name](i, None, insert=False)[0].makespan for i in insts])
        print(f"  {name:9s} mean(insertion/append) = {np.mean(ins / app):.4f}   "
              f"better {np.sum(ins < app):3d}  equal {np.sum(ins == app):3d}  worse {np.sum(ins > app):3d}")
        assert all(validate(i, HEURISTICS[name](i, None, insert=False)[0]) == [] for i in insts[:20])


@pytest.mark.parametrize("task_rule, proc_rule", [("EDF", "EFT"), ("FCFS", "FASTEST")])
def test_unknown_rules_rejected(task_rule, proc_rule):
    with pytest.raises(ValueError):
        list_schedule(make_instance("x", 1, [], [[1.0]]), task_rule, proc_rule)
