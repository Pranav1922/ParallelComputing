"""V7-V9 for the OpenMP executor (cpp/build/ompexec), checked from its per-task trace in Python,
independently of the executor's own flags: precedence, placement, order, exactly-once, prescribed work,
thread count, and kernel linearity."""
import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from schedlab import interop, ompexec
from schedlab.heuristics import HEURISTICS
from schedlab.model import bounds
from schedlab.workloads import generate

K = 50.0  # iterations per sim_tu: tasks of a few us, enough to interleave threads


@pytest.fixture(scope="module", autouse=True)
def built():
    if not ompexec.BIN.exists():
        if shutil.which("g++-15") is None:
            pytest.skip("cpp/build/ompexec not built and g++-15 not available")
        subprocess.run(["make", "-C", str(interop.ROOT / "cpp")], check=True, capture_output=True)


def run(inst, plan_lines, jobs=""):
    with tempfile.TemporaryDirectory() as d:
        ses = interop.Session(inst, d)
        (Path(d) / "jobs.txt").write_text(jobs)
        (Path(d) / "plan.txt").write_text("\n".join(plan_lines) + "\n")
        out = ompexec._run("run", str(ses.path), str(Path(d) / "jobs.txt"), str(Path(d) / "plan.txt"), repr(K),
                           str(Path(d) / "trace.csv"))
        trace = list(csv.DictReader(open(Path(d) / "trace.csv")))
    return list(csv.DictReader(io.StringIO(out))), trace


def check_trace(inst, trace, nthreads, expect_thread=None, work_proc=None):
    """work_proc[t]: processor whose cost defines task t's work (None: the thread it ran on)."""
    tasks = {int(r["task"]): r for r in trace}
    assert sorted(tasks) == list(range(inst.n)) and len(trace) == inst.n          # every task exactly once
    for t, r in tasks.items():
        for u in inst.preds[t]:
            assert float(r["start_s"]) >= float(tasks[u]["end_s"]), (t, u)           # precedence, measured
        th = int(r["thread"])
        assert 0 <= th < nthreads
        if expect_thread is not None:
            assert th == expect_thread[t]
        p = th if work_proc is None else work_proc[t]
        assert int(r["iters"]) == max(1, round(inst.cost[t, p] * K)), (t, p)        # prescribed work
    return tasks


INSTANCES = [generate(c, n, m, "test_id", i, campaign_seed=20261011)
             for i, (c, n, m) in enumerate([("irregular", 60, 4), ("irregular_hetero", 80, 8),
                                            ("heterogeneous", 40, 2), ("regular", 30, 1)])]


@pytest.mark.parametrize("inst", INSTANCES, ids=lambda i: i.id)
def test_v7_static_follows_schedule(inst):
    s = HEURISTICS["HEFT"](inst, None)[0]
    jobs = interop.job_text("HEFT", "append", interop.placement_order(s), s.proc)
    rows, trace = run(inst, ["static HEFT 0 0 1 1"], jobs)
    r = rows[0]
    assert (r["order_ok"], r["thread_ok"], r["once_ok"], r["verify_ok"]) == ("1", "1", "1", "1")
    assert int(r["threads_seen"]) == inst.m                                           # V8
    assert float(r["sim_makespan_tu"]) == s.makespan
    tasks = check_trace(inst, trace, inst.m, expect_thread=s.proc.tolist(), work_proc=s.proc.tolist())
    for p in range(inst.m):                                                           # schedule order per thread
        mine = sorted((t for t in range(inst.n) if s.proc[t] == p), key=lambda t: (s.start[t], t))
        assert [int(tasks[t]["seq"]) for t in mine] == list(range(len(mine)))
        ends = [float(tasks[t]["end_s"]) for t in mine]
        starts = [float(tasks[t]["start_s"]) for t in mine]
        assert all(a <= b for a, b in zip(ends, starts[1:]))                         # no overlap on a thread


@pytest.mark.parametrize("inst", INSTANCES, ids=lambda i: i.id)
def test_v7_tasks_and_serial(inst):
    rows, trace = run(inst, ["tasks - 0 0 1 1"])
    assert rows[0]["verify_ok"] == "1" and int(rows[0]["threads_seen"]) == inst.m
    check_trace(inst, trace, inst.m)
    rows, trace = run(inst, ["serial - 0 0 1 1"])
    p = int(np.argmin(inst.cost.sum(axis=0)))
    assert rows[0]["verify_ok"] == "1" and float(rows[0]["sim_makespan_tu"]) == bounds(inst)["serial_best"]
    tasks = check_trace(inst, trace, 1, expect_thread=[0] * inst.n, work_proc=[p] * inst.n)
    starts = [float(tasks[t]["start_s"]) for t in range(inst.n)]
    assert starts == sorted(starts)                                                   # id order on one thread


def test_v8_thread_counts():
    for m in (1, 2, 4, 8):
        inst = generate("irregular", 40, m, "test_id", 0, campaign_seed=20261011)
        rows, _ = run(inst, ["tasks - 0 0 0 0"])
        assert int(rows[0]["threads_seen"]) == m


def test_v9_kernel_time_grows_linearly():
    out = ompexec._run("calibrate", "50000000", "1", "1")  # warm-up
    xs, ys = [], []
    for iters in (200_000, 400_000, 800_000, 1_600_000):
        rows = [r for r in csv.DictReader(io.StringIO(ompexec._run("calibrate", str(iters), "1", "5")))
                if r["kind"] == "kernel"]
        xs.append(iters)
        ys.append(float(np.median([float(r["seconds"]) for r in rows])))
    r = np.corrcoef(xs, ys)[0, 1]
    assert r ** 2 > 0.98 and all(a < b for a, b in zip(ys, ys[1:])), (xs, ys)       # loose: shared machine


def test_execute_rejects_manifest_key_clash_before_running(tmp_path):
    """Regression for the M-D crash: a clashing extra_manifest key must fail before any measurement."""
    with pytest.raises(ValueError, match="config_sha256"):
        ompexec.execute(tmp_path, tmp_path, pilot=True, extra_manifest=dict(config_sha256="x"))
    assert not any(tmp_path.iterdir())


def test_final_extra_keys_do_not_clash():
    import inspect
    src = inspect.getsource(ompexec.run_final)
    extra = src[src.index("extra_manifest=dict("):]
    assert "locked_config_sha256=" in extra and not any(f" {k}=" in extra.split(")")[0] for k in ompexec.MANIFEST_KEYS)
