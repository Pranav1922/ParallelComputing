import inspect

import numpy as np
import pytest

from schedlab.model import Schedule, ScheduleBuilder, bounds, make_instance, upward_rank, validate
from schedlab.workloads import CLASSES, generate


# ---- helpers shared with test_heuristics -------------------------------------------------

def recompute_times(inst, sched):
    """Independent of ScheduleBuilder: earliest start/finish times implied by the processor
    assignment and the per-processor order alone (longest path over precedence + machine arcs)."""
    order = sorted(range(inst.n), key=lambda t: (sched.start[t], t))
    start, finish, last_on = np.zeros(inst.n), np.zeros(inst.n), {}
    for t in order:
        p = int(sched.proc[t])
        s = max([finish[u] for u in inst.preds[t]] + [last_on.get(p, 0.0)])
        start[t], finish[t] = s, s + inst.cost[t, p]
        last_on[p] = finish[t]
    return start, finish


def append_replay(inst, sched):
    """Replay a schedule in append mode: tasks in start-time order on the same processors."""
    b = ScheduleBuilder(inst)
    for t in sorted(range(inst.n), key=lambda t: (sched.start[t], t)):
        b.place(t, int(sched.proc[t]))
    return b.schedule()


def random_schedule(inst, rng, insert):
    b = ScheduleBuilder(inst)
    while not b.done():
        b.place(int(rng.choice(b.ready)), int(rng.integers(inst.m)), insert)
    return b.schedule()


def same(a, b):
    return (np.array_equal(a.proc, b.proc) and np.array_equal(a.start, b.start)
            and np.array_equal(a.finish, b.finish))


def random_instances(count, seed=7):
    rng = np.random.default_rng(seed)
    classes = list(CLASSES)
    for i in range(count):
        yield generate(classes[i % 4], int(rng.integers(1, 31)), int(rng.integers(1, 6)), "val", i,
                       campaign_seed=seed)


def homog(costs, m):
    return np.repeat(np.array(costs, dtype=float)[:, None], m, axis=1)


# ---- hand-computed schedules ---------------------------------------------------------------

def test_chain_by_hand():
    inst = make_instance("chain", 2, [(0, 1), (1, 2)], homog([2, 3, 1], 2))
    b = ScheduleBuilder(inst)
    for t in range(3):
        b.place(t, 0)
    s = b.schedule()
    assert s.start.tolist() == [0, 2, 5] and s.finish.tolist() == [2, 5, 6] and s.makespan == 6
    assert validate(inst, s) == []


def test_diamond_by_hand():
    inst = make_instance("diamond", 2, [(0, 1), (0, 2), (1, 3), (2, 3)], homog([1, 2, 3, 1], 2))
    b = ScheduleBuilder(inst)
    b.place(0, 0), b.place(1, 0), b.place(2, 1), b.place(3, 0)
    s = b.schedule()
    assert s.start.tolist() == [0, 1, 1, 4] and s.finish.tolist() == [1, 3, 4, 5] and s.makespan == 5
    assert validate(inst, s) == []


def gap_instance(c_cost):
    # A(0) -> B(1); C(2) independent. A on p0 [0,4], B on p1 [4,6] leaves the gap [0,4] on p1.
    return make_instance("gap", 2, [(0, 1)], [[4, 4], [2, 2], [c_cost, c_cost]])


def test_insertion_uses_fitting_gap_by_hand():
    inst = gap_instance(3)
    b = ScheduleBuilder(inst)
    b.place(0, 0), b.place(1, 1)
    assert b.est(2, 1, insert=False) == 6 and b.est(2, 1, insert=True) == 0
    b.place(2, 1, insert=True)
    s = b.schedule()
    assert (s.start[2], s.finish[2], s.makespan) == (0, 3, 6)
    assert validate(inst, s) == []


def test_insertion_appends_when_gap_too_short():
    inst = gap_instance(5)
    b = ScheduleBuilder(inst)
    b.place(0, 0), b.place(1, 1)
    assert b.est(2, 1, insert=True) == 6
    b.place(2, 1, insert=True)
    assert b.schedule().start[2] == 6 and validate(inst, b.schedule()) == []


def test_gap_exactly_fits():
    inst = gap_instance(4)
    b = ScheduleBuilder(inst)
    b.place(0, 0), b.place(1, 1), b.place(2, 1, insert=True)
    assert b.schedule().start[2] == 0 and validate(inst, b.schedule()) == []


# ---- the validator is not vacuous ----------------------------------------------------------

def valid_diamond():
    inst = make_instance("diamond", 2, [(0, 1), (0, 2), (1, 3), (2, 3)], homog([1, 2, 3, 1], 2))
    b = ScheduleBuilder(inst)
    b.place(0, 0), b.place(1, 0), b.place(2, 1), b.place(3, 0)
    return inst, b.schedule()


def mutated(s, **changes):
    arrays = dict(proc=s.proc.copy(), start=s.start.copy(), finish=s.finish.copy())
    for name, (i, v) in changes.items():
        arrays[name][i] = v
    return Schedule(**arrays)


@pytest.mark.parametrize("changes, expect", [
    (dict(start=(3, 3.0), finish=(3, 4.0)), "predecessor"),        # task 3 before pred 2 finishes
    (dict(proc=(2, 0)), "overlap"),                                 # task 2 moved onto task 1
    (dict(finish=(1, 9.0)), "cost"),                                # wrong duration
    (dict(proc=(3, -1)), "out of range"),                           # missing / unscheduled task
    (dict(proc=(3, 2)), "out of range"),                            # processor does not exist
    (dict(start=(0, -1.0), finish=(0, 0.0)), "negative"),
    (dict(start=(3, np.nan)), "non-finite"),
])
def test_validate_catches(changes, expect):
    inst, s = valid_diamond()
    assert validate(inst, s) == []
    problems = validate(inst, mutated(s, **changes))
    assert problems and any(expect in x for x in problems), problems


def test_validate_catches_wrong_shape_and_dtype():
    inst, s = valid_diamond()
    assert validate(inst, Schedule(s.proc[:3], s.start[:3], s.finish[:3]))
    assert validate(inst, Schedule(s.proc.astype(float), s.start, s.finish))


def test_validate_is_independent_of_builder():
    src = inspect.getsource(validate)
    assert "ScheduleBuilder" not in src and "ready_time" not in src and "avail" not in src


# ---- builder rejects illegal actions -------------------------------------------------------

def test_place_rejects_illegal_actions():
    inst, _ = valid_diamond()
    b = ScheduleBuilder(inst)
    with pytest.raises(ValueError):
        b.place(3, 0)          # predecessors not placed
    with pytest.raises(ValueError):
        b.place(0, 2)          # no such processor
    with pytest.raises(ValueError):
        b.place(9, 0)          # no such task
    b.place(0, 0)
    with pytest.raises(ValueError):
        b.place(0, 1)          # already placed
    with pytest.raises(ValueError):
        b.schedule()           # incomplete


# ---- malformed and infeasible inputs -------------------------------------------------------

@pytest.mark.parametrize("m, edges, cost", [
    (0, [], np.empty((2, 0))),                 # no processors
    (-1, [], [[1.0]]),
    (2, [], [[1.0], [1.0]]),                   # cost shape does not match m
    (1, [], [1.0, 2.0]),                       # cost not 2-D
    (1, [], [[0.0]]),                          # zero cost
    (1, [], [[-1.0]]),
    (1, [], [[np.nan]]),
    (1, [], [[np.inf]]),
    (1, [(0, 2)], [[1.0], [1.0]]),             # edge to a task that does not exist
    (1, [(0, 0)], [[1.0], [1.0]]),             # self-loop
    (1, [(1, 0)], [[1.0], [1.0]]),             # back edge
    (1, [(0, 1), (1, 2), (2, 0)], [[1.0]] * 3),  # cycle
    (1, [(0, 1), (0, 1)], [[1.0], [1.0]]),     # duplicate edge
])
def test_malformed_instances_rejected(m, edges, cost):
    with pytest.raises(ValueError):
        make_instance("bad", m, edges, cost)


def test_instance_cost_is_read_only_and_copied():
    src = np.ones((2, 1))
    inst = make_instance("x", 1, [], src)
    src[0, 0] = 99
    assert inst.cost[0, 0] == 1
    with pytest.raises(ValueError):
        inst.cost[0, 0] = 5


# ---- edge cases --------------------------------------------------------------------------

def test_empty_workload():
    inst = make_instance("empty", 3, [], np.empty((0, 3)))
    b = ScheduleBuilder(inst)
    assert b.done()
    s = b.schedule()
    assert s.makespan == 0 and validate(inst, s) == []
    assert bounds(inst) == dict(serial_best=0.0, cp_min=0.0, work_lb=0.0, lower_bound=0.0)
    assert len(upward_rank(inst)) == 0


def test_single_task():
    inst = make_instance("one", 2, [], [[5.0, 3.0]])
    b = ScheduleBuilder(inst)
    b.place(0, 1)
    assert b.schedule().makespan == 3
    assert bounds(inst)["lower_bound"] == 3 and bounds(inst)["serial_best"] == 3


def test_critical_chain_gets_no_parallelism():
    n = 6
    inst = make_instance("chain", 4, [(i, i + 1) for i in range(n - 1)], homog(range(1, n + 1), 4))
    s = random_schedule(inst, np.random.default_rng(0), insert=True)
    assert s.makespan == sum(range(1, n + 1)) == bounds(inst)["lower_bound"]
    assert validate(inst, s) == []


def test_disconnected_tasks():
    inst = make_instance("indep", 2, [], homog([3, 3, 3, 3], 2))
    b = ScheduleBuilder(inst)
    assert b.ready == [0, 1, 2, 3]
    for t in range(4):
        b.place(t, t % 2)
    assert b.schedule().makespan == 6 == bounds(inst)["lower_bound"]


def test_one_processor_is_serial():
    for inst in random_instances(20):
        one = make_instance("m1", 1, [(u, v) for v in range(inst.n) for u in inst.preds[v]], inst.cost[:, :1])
        s = random_schedule(one, np.random.default_rng(1), insert=True)
        assert s.makespan == pytest.approx(one.cost.sum()) and validate(one, s) == []
        assert bounds(one)["serial_best"] == pytest.approx(one.cost.sum())


def test_more_processors_than_tasks():
    inst = make_instance("wide", 8, [], homog([2, 5, 3], 8))
    b = ScheduleBuilder(inst)
    for t in range(3):
        b.place(t, t)
    assert b.schedule().makespan == 5 == bounds(inst)["lower_bound"]


def test_upward_rank_by_hand():
    inst = make_instance("diamond", 2, [(0, 1), (0, 2), (1, 3), (2, 3)], homog([1, 2, 3, 1], 2))
    assert upward_rank(inst).tolist() == [5, 3, 4, 1]
    assert bounds(inst) == dict(serial_best=7.0, cp_min=5.0, work_lb=3.5, lower_bound=5.0)


# ---- properties on seeded random instances -----------------------------------------------

def test_random_schedules_valid_and_within_bounds():
    rng = np.random.default_rng(11)
    for inst in random_instances(300):
        for insert in (False, True):
            s = random_schedule(inst, rng, insert)
            assert validate(inst, s) == []
            lb = bounds(inst)["lower_bound"]
            assert lb * (1 - 1e-12) <= s.makespan <= inst.cost.max(axis=1).sum() * (1 + 1e-12)


def test_insertion_never_starts_later_than_append():
    rng = np.random.default_rng(12)
    for inst in random_instances(100):
        b = ScheduleBuilder(inst)
        while not b.done():
            t = int(rng.choice(b.ready))
            for p in range(inst.m):
                assert b.est(t, p, insert=True) <= b.est(t, p, insert=False)
            b.place(t, int(rng.integers(inst.m)), insert=bool(rng.integers(2)))


def test_independent_recomputation_matches_builder():
    """Start, finish and makespan recomputed without the builder equal the builder's (both modes)."""
    rng = np.random.default_rng(13)
    for inst in random_instances(300):
        for insert in (False, True):
            s = random_schedule(inst, rng, insert)
            start, finish = recompute_times(inst, s)
            assert np.array_equal(start, s.start) and np.array_equal(finish, s.finish)
            assert s.makespan == finish.max()


# ---- expressiveness: append mode vs insertion (ARCHITECTURE.md 3.1) ---------------------

def test_append_reproduces_insertion_schedules_exactly():
    rng = np.random.default_rng(14)
    used_gap = 0
    for inst in random_instances(300):
        s = random_schedule(inst, rng, insert=True)
        assert same(append_replay(inst, s), s)
        # count schedules where insertion really did something append-in-placement-order would not
        used_gap += any(s.start[t] < max((s.finish[u] for u in range(inst.n)
                                          if s.proc[u] == s.proc[t] and u != t and s.start[u] > s.start[t]),
                                         default=-1) for t in range(inst.n))
    assert used_gap > 50  # the test exercised schedules with several tasks per processor


def test_append_cannot_reproduce_delayed_schedule_only_dominate_it():
    """The restriction: a schedule with unforced idle time is not representable in append mode."""
    for inst in random_instances(50):
        s = random_schedule(inst, np.random.default_rng(15), insert=True)
        delayed = Schedule(s.proc, s.start + 10.0, s.finish + 10.0)
        assert validate(inst, delayed) == []
        r = append_replay(inst, delayed)
        assert not same(r, delayed)
        assert (r.start <= delayed.start).all() and r.makespan < delayed.makespan
        assert same(r, s)


def test_append_can_fill_gap_only_if_filler_is_ordered_first():
    inst = gap_instance(3)  # A->B, C independent; B on p1 leaves [0,4] idle on p1
    late = ScheduleBuilder(inst)
    late.place(0, 0), late.place(1, 1), late.place(2, 1)          # C after B: cannot go back into the gap
    early = ScheduleBuilder(inst)
    early.place(0, 0), early.place(2, 1), early.place(1, 1)       # C before B: same result as insertion
    assert late.schedule().start[2] == 6 and late.schedule().makespan == 9
    assert early.schedule().start[2] == 0 and early.schedule().makespan == 6
