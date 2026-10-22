"""Cross-language validation of the C++ workload simulator (cpp/schedsim) against the Python core.

V1 format round trip, V2 append replay and GA decoding, V3 insertion replay, V4 the six heuristics, bounds, mean
cost and upward rank, V5 validator agreement; plus integer-cost instances that stress ties and exact-fit gaps. Equality is exact (bit for bit) unless a test says otherwise.
The campaign-scale V4 check is `python -m schedlab.interop xval-heuristics` (see cpp/README.md).
"""
import shutil
import subprocess
import tempfile

import numpy as np
import pytest

from schedlab import interop
from schedlab.ga import decode
from schedlab.heuristics import HEURISTICS
from schedlab.model import Schedule, ScheduleBuilder, bounds, validate
from schedlab.workloads import instance_hash
from test_heuristics import campaign_instances
from test_model import random_instances


@pytest.fixture(scope="module", autouse=True)
def built():
    if not interop.BIN.exists():
        if shutil.which("g++-15") is None:
            pytest.skip("cpp/build/schedsim not built and g++-15 not available")
        subprocess.run(["make", "-C", str(interop.ROOT / "cpp")], check=True, capture_output=True)


def instances():
    """500 M1 validation instances (n 1..80, m 1..16, both families) plus 100 small random ones."""
    yield from campaign_instances()
    yield from random_instances(100, seed=11)


@pytest.fixture(scope="module")
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def random_order(inst, rng, insert):
    """A random feasible placement order and processors, and the Python schedule they build."""
    b, order, proc = ScheduleBuilder(inst), [], [0] * inst.n
    while not b.done():
        t, p = int(rng.choice(b.ready)), int(rng.integers(inst.m))
        b.place(t, p, insert)
        order.append(t)
        proc[t] = p
    return order, proc, b.schedule()


def test_v1_round_trip(workdir):
    for inst in instances():
        ses = interop.Session(inst, workdir)
        iid, n, m, edges, cost = interop.parse_instance_text(ses.dump())
        assert (iid, n, m) == (inst.id, inst.n, inst.m)
        assert edges == sorted((u, v) for v in range(inst.n) for u in inst.preds[v])
        c = np.array(cost, dtype=np.float64).reshape(inst.n, inst.m)
        assert c.tobytes() == np.ascontiguousarray(inst.cost).tobytes()  # bit-identical, sign included
        assert instance_hash(n, m, edges, c) == inst.meta["hash"]


def test_v1_rejects_malformed(workdir):
    inst = next(iter(random_instances(1)))
    ses = interop.Session(inst, workdir)
    good = ses.path.read_text()
    for bad in (good.replace("size", "sz"), good.replace("end", ""),
                good.replace(float(inst.cost[0, 0]).hex(), "-0x1p+0"),   # non-positive cost
                good.replace(float(inst.cost[0, 0]).hex(), "nan")):
        ses.path.write_text(bad)
        with pytest.raises(RuntimeError):
            ses.bounds()
    inst2 = next(i for i in random_instances(50) if any(i.preds))
    ses = interop.Session(inst2, workdir)
    v = next(t for t in range(inst2.n) if inst2.preds[t])
    u = inst2.preds[v][0]
    txt = ses.path.read_text().replace(f"\n{u} {v}\n", f"\n{v} {u}\n", 1)   # edge against topological order
    ses.path.write_text(txt)
    with pytest.raises(RuntimeError):
        ses.bounds()


@pytest.mark.parametrize("insert", [False, True], ids=["V2-append", "V3-insert"])
def test_v2_v3_replay(workdir, insert):
    rng = np.random.default_rng(5)
    mode = "insert" if insert else "append"
    for inst in instances():
        ses = interop.Session(inst, workdir)
        cases = [random_order(inst, rng, insert) for _ in range(3)]
        got = ses.eval([interop.job_text(f"r{k}", mode, o, p) for k, (o, p, _) in enumerate(cases)])
        for k, (_, _, py) in enumerate(cases):
            assert interop.identical(got[f"r{k}"], py), (inst.id, k)


def test_v2_ga_decode(workdir):
    rng = np.random.default_rng(6)
    for inst in instances():
        ses = interop.Session(inst, workdir)
        keys = [rng.random(inst.n) for _ in range(2)]
        keys.append(np.round(rng.random(inst.n), 1))          # many ties: lowest id must win
        assign = [rng.integers(inst.m, size=inst.n) for _ in keys]
        blocks = [interop.keys_text(f"k{i}", k, a) for i, (k, a) in enumerate(zip(keys, assign))]
        blocks += [interop.keys_text(f"e{i}", k) for i, k in enumerate(keys)]  # GA-KEYS-EFT decoder
        got = ses.eval(blocks)
        for i, (k, a) in enumerate(zip(keys, assign)):
            assert interop.identical(got[f"k{i}"], decode(inst, k, a)), (inst.id, i)
            assert interop.identical(got[f"e{i}"], decode(inst, k)), (inst.id, i)


def test_v2_semi_active_replay_of_heuristics(workdir):
    """Claim 2 + corollary across languages: each Python heuristic schedule, replayed in C++ append mode
    in start-time order, comes back identical."""
    for inst in campaign_instances(200):
        ses = interop.Session(inst, workdir)
        py = {name: fn(inst, None)[0] for name, fn in HEURISTICS.items()}
        got = ses.eval([interop.job_text(n, "append", interop.placement_order(s), s.proc) for n, s in py.items()])
        for name, s in py.items():
            assert interop.identical(got[name], s), (inst.id, name)


def test_v2_infeasible_order_is_rejected_by_both(workdir):
    rng = np.random.default_rng(8)
    checked = 0
    for inst in instances():
        if not any(inst.preds):
            continue
        order, proc, _ = random_order(inst, rng, False)
        v = next(t for t in order if inst.preds[t])
        bad = [v] + [t for t in order if t != v]                    # successor before its predecessor
        bad_proc = list(proc)
        bad_proc[order[0]] = inst.m                                  # processor out of range
        got = interop.Session(inst, workdir).eval([interop.job_text("pred", "append", bad, proc),
                                                   interop.job_text("proc", "append", order, bad_proc)])
        assert isinstance(got["pred"], str) and "not ready" in got["pred"]
        assert isinstance(got["proc"], str) and "out of range" in got["proc"]
        b = ScheduleBuilder(inst)
        with pytest.raises(ValueError):
            for t in bad:
                b.place(t, proc[t])
        checked += 1
    assert checked > 400


def test_v4_heuristics_and_bounds(workdir):
    for inst in instances():
        ses = interop.Session(inst, workdir)
        cpp = ses.heuristics()
        for name, fn in HEURISTICS.items():
            for mode in ("insert", "append"):
                py = fn(inst, None, insert=mode == "insert")[0]
                assert interop.identical(cpp[f"{name}:{mode}"], py), (inst.id, name, mode)
                assert not validate(inst, py)
        assert ses.bounds() == bounds(inst), inst.id                # exact float equality, all four


def test_v4_mean_cost_and_upward_rank_bitwise(workdir):
    """numpy's pairwise mean differs from a left-to-right sum on some rows (m >= 8). SPT/LPT/HEFT keys
    depend on it, so the C++ mean and upward rank are compared bit for bit, not only through schedules."""
    from schedlab.model import make_instance, upward_rank
    rng = np.random.default_rng(12)
    differs = 0
    insts = list(instances())
    for m in range(1, 17):
        cost = rng.lognormal(4, 1.5, size=(60, m))
        differs += sum(sum(r.tolist()) != r.sum() for r in cost)  # left-to-right vs numpy pairwise
        edges = [(u, v) for v in range(60) for u in range(v) if rng.random() < 0.05]
        insts.append(make_instance(f"sum-m{m}", m, edges, cost))
    for inst in insts:
        mean, rank = interop.Session(inst, workdir).ranks()
        assert mean.tobytes() == inst.cost.mean(axis=1).tobytes(), inst.id
        assert rank.tobytes() == upward_rank(inst).tobytes(), inst.id
    assert differs > 0  # the check really exercises a summation-order difference


def tie_instances(count=300, seed=13):
    """Small integer costs: exact-fit idle gaps and equal priorities/finish times are common, so insertion
    boundaries (s + c <= a) and every tie rule are exercised, unlike with continuous costs."""
    from schedlab.model import make_instance
    rng = np.random.default_rng(seed)
    for i, base in enumerate(campaign_instances(count)):
        edges = [(u, v) for v in range(base.n) for u in base.preds[v]]
        hi = int(rng.integers(2, 5))
        if i % 2:
            cost = rng.integers(1, hi, size=(base.n, base.m)).astype(float)
        else:
            cost = np.repeat(rng.integers(1, hi, size=(base.n, 1)).astype(float), base.m, axis=1)
        yield make_instance(f"tie-{i}", base.m, edges, cost)


def test_v2_v3_v4_tie_stress(workdir):
    rng = np.random.default_rng(14)
    for inst in tie_instances():
        ses = interop.Session(inst, workdir)
        cpp = ses.heuristics()
        for name, fn in HEURISTICS.items():
            for mode in ("insert", "append"):
                assert interop.identical(cpp[f"{name}:{mode}"], fn(inst, None, insert=mode == "insert")[0]), \
                    (inst.id, name, mode)
        assert ses.bounds() == bounds(inst), inst.id
        cases = [random_order(inst, rng, ins) for ins in (True, False, True, False)]
        keys = np.round(rng.random(inst.n), 1)
        got = ses.eval([interop.job_text(f"r{k}", "insert" if k % 2 == 0 else "append", o, p)
                        for k, (o, p, _) in enumerate(cases)] + [interop.keys_text("k", keys)])
        for k, (_, _, py) in enumerate(cases):
            assert interop.identical(got[f"r{k}"], py), (inst.id, k)
        assert interop.identical(got["k"], decode(inst, keys)), inst.id


def mutations(inst, s, rng):
    """Valid and invalid variants of a valid schedule, as (label, Schedule)."""
    n, m = inst.n, inst.m
    out = [("ok", s)]
    for k in range(8):
        proc, start, finish = s.proc.copy(), s.start.copy(), s.finish.copy()
        t = int(rng.integers(n))
        kind = ["early", "dur", "proc", "neg", "minus1", "outm", "nan", "swap"][k]
        if kind == "early":
            d = start[t] * rng.uniform(0.05, 1.0)
            start[t] -= d
            finish[t] -= d
        elif kind == "dur":
            finish[t] += rng.uniform(1e-3, 5.0)
        elif kind == "proc":
            proc[t] = (proc[t] + 1) % m
        elif kind == "neg":
            start[t], finish[t] = -1.0, finish[t] - start[t] - 1.0
        elif kind == "minus1":
            proc[t] = -1
        elif kind == "outm":
            proc[t] = m
        elif kind == "nan":
            start[t] = float("nan")
        elif kind == "swap" and n > 1:
            u = int(rng.integers(n))
            start[[t, u]], finish[[t, u]], proc[[t, u]] = start[[u, t]], finish[[u, t]], proc[[u, t]]
        out.append((f"{kind}{k}", Schedule(proc, start, finish)))
    return out


def test_v5_validator_agreement(workdir):
    rng = np.random.default_rng(9)
    total = invalid = 0
    for inst in instances():
        ses = interop.Session(inst, workdir)
        base = HEURISTICS["HEFT"](inst, None)[0]
        cases = mutations(inst, base, rng)
        got = ses.validate([interop.check_text(lbl, s) for lbl, s in cases])
        for lbl, s in cases:
            py = validate(inst, s)
            assert len(got[lbl]) == len(py), (inst.id, lbl, got[lbl], py)
            total += 1
            invalid += bool(py)
    assert got and total >= 5000 and invalid >= 1000, (total, invalid)
