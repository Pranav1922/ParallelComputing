"""Integration: config -> workloads -> schedulers -> independent validation -> raw CSV -> derived CSV -> figure."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from schedlab.analysis import MANUAL_COLUMNS, SPEEDUP_BASELINE, analyze, check
from schedlab.heuristics import HEURISTICS
from schedlab.model import Schedule, bounds
from schedlab.runner import RAW_COLUMNS, SCHEDULERS, TRACE_COLUMNS, run_campaign
from schedlab.workloads import experiment_matrix

ROOT = Path(__file__).resolve().parent.parent
NAMES = list(HEURISTICS)
CONFIG = """
[campaign]
name = "it"
seed = 5
workers = 1
notes = "integration test"
[workload]
sizes = [10]
processors = [2]
classes = ["regular", "irregular_hetero"]
instances = { train = 2, val = 2 }
ood = []
[run]
splits = ["val"]
algorithms = %s
timing_repeats = 2
timeout_s = %s
"""


def write_config(tmp_path, algorithms=NAMES, timeout=30):
    path = tmp_path / "it.toml"
    path.write_text(CONFIG % (json.dumps(algorithms), timeout))
    return path


def raw_text(raw_dir):
    return pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def campaign(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("campaign")
    raw_dir = run_campaign(write_config(tmp), tmp / "raw")
    return tmp, raw_dir, analyze(raw_dir, tmp / "results", ROOT / "configs" / "identity.toml")


def test_raw_output(campaign):
    _, raw_dir, _ = campaign
    assert {f.name for f in raw_dir.iterdir()} == {"runs.csv", "manifest.json", "run.log", "ga_trace.csv", "decisions.csv"}
    assert (raw_dir / "ga_trace.csv").read_text().strip() == ",".join(TRACE_COLUMNS)   # header only: no GA here
    t = raw_text(raw_dir)
    assert list(t.columns) == RAW_COLUMNS
    assert len(t) == 4 * 6 * 2                       # instances x algorithms x repeats
    assert not (t == "").any().any()                 # no blanks
    assert set(t.status) == {"ok"} and set(t.valid) == {"1"} and set(t.time_unit) == {"sim_tu"}
    assert set(t.split) == {"val"} and t.run_uid.is_unique
    for col in ("algo_seed", "model_id", "decision_time_s", "decision_count", "error_msg"):
        assert set(t[col]) == {"NA"}                 # unavailable -> NA, not 0
    assert "student_id" not in t.columns and "Student_ID" not in t.columns
    assert not any(c in t.columns for c in ("speedup", "efficiency", "utilization"))   # raw holds nothing derived


def test_every_algorithm_ran_on_identical_instances(campaign):
    _, raw_dir, _ = campaign
    t = raw_text(raw_dir)
    per_algo = {a: sorted(g.instance_hash) for a, g in t.groupby("algorithm")}
    assert set(per_algo) == set(NAMES) and len({tuple(v) for v in per_algo.values()}) == 1
    assert t.groupby("instance_hash")[["resource_count", "problem_size", "serial_best_sim", "lower_bound_sim"]].nunique().eq(1).all().all()


def test_raw_values_match_the_shared_core(campaign):
    """The runner adds no scheduling or makespan logic of its own."""
    _, raw_dir, _ = campaign
    cfg = json.loads((raw_dir / "manifest.json").read_text())["config"]
    insts = {i.meta["hash"]: i for i in experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])["val"]}
    raw = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
    for row in raw.itertuples():
        inst = insts[row.instance_hash]
        s, _ = HEURISTICS[row.algorithm](inst, None)
        assert row.makespan_sim == s.makespan
        assert row.busy_time_sim == pytest.approx(inst.cost[np.arange(inst.n), s.proc].sum())
        assert row.lower_bound_sim == bounds(inst)["lower_bound"] and row.serial_best_sim == bounds(inst)["serial_best"]
        assert row.scheduling_time_s > 0


def test_manifest(campaign):
    _, raw_dir, _ = campaign
    m = json.loads((raw_dir / "manifest.json").read_text())
    assert m["row_count"] == 48 and m["failed_count"] == 0 and m["separation_checked"] is True
    assert m["split_counts"] == {"train": 4, "val": 4}
    assert m["config"]["run"]["timing_repeats"] == 2 and m["finished_utc"] and m["wall_time_s"] > 0
    hw = next(iter(m["hardware"].values()))
    assert hw["cpu"] and hw["physical_cores"] >= 1 and hw["ram_bytes"] > 0
    assert m["software"]["numpy"] and m["software"]["python"]


def test_raw_directory_is_read_only_and_never_overwritten(campaign):
    _, raw_dir, _ = campaign
    assert all(not os.access(f, os.W_OK) for f in raw_dir.iterdir())
    with pytest.raises(PermissionError):
        open(raw_dir / "runs.csv", "a")


def test_master_csv(campaign):
    _, raw_dir, res = campaign
    path = res["derived"] / "master.csv"
    t = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(t.columns[:19]) == MANUAL_COLUMNS
    assert len(t) == len(raw_text(raw_dir))                      # nothing dropped
    assert not (t == "").any().any()
    for col in ("Communication_Time", "Synchronization_Time", "Energy_if_available"):
        assert set(t[col]) == {"NA"}
    assert set(t.Student_ID) == {"STUDENT_ID_UNCONFIRMED"} and set(t.Batch_ID) == {"BATCH_ID_UNCONFIRMED"}
    assert set(t.Time_Unit) == {"sim_tu"} and set(t.Scheduling_Time_Unit) == {"s"}
    assert set(t.Speedup_Baseline) == {SPEEDUP_BASELINE}
    assert set(t.Hardware) == {"SIM:homog", "SIM:hetero"} and set(t.Parallel_Model) == {"SIM-LIST-SCHED"}


def test_derived_metrics_are_recomputed_from_raw(campaign):
    _, raw_dir, res = campaign
    raw, m = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip"), res["master"]
    assert np.allclose(m.Speedup, raw.serial_best_sim / raw.makespan_sim)
    assert np.allclose(m.Efficiency, m.Speedup / raw.resource_count)
    assert np.allclose(m.Utilization, raw.busy_time_sim / (raw.resource_count * raw.makespan_sim))
    assert np.allclose(m.Norm_Makespan, raw.makespan_sim / raw.lower_bound_sim)
    assert (m.Norm_Makespan >= 1 - 1e-9).all() and ((m.Utilization > 0) & (m.Utilization <= 1 + 1e-9)).all()
    assert np.allclose(m.Execution_Time, raw.makespan_sim) and np.allclose(m.Scheduling_Time, raw.scheduling_time_s)
    fcfs = m[m.Algorithm == "FCFS-EAT"]
    assert np.allclose(fcfs.Improvement_vs_FCFS, 0)
    assert (m.Regret_vs_VBS >= -1e-12).all() and (m.groupby("Instance_Hash").Regret_vs_VBS.min().abs() < 1e-12).all()


def test_summary_and_figure_files(campaign):
    _, _, res = campaign
    assert set(res["summary"].Algorithm) == set(NAMES) and (res["summary"].instances == 4).all()
    stem = "g1_makespan_vs_size"
    assert {f.name for f in res["figures"].iterdir()} == {f"{stem}.pdf", f"{stem}.svg", f"{stem}.csv",
                                                          f"{stem}_instances.csv"}
    assert (res["figures"] / f"{stem}.svg").read_text().count("<svg") == 1
    assert res["problems"] == []


def test_normalisation_invariant(campaign):
    """Makespan / lower bound is >= 1 for every run, every plotted instance and every plotted summary value."""
    _, _, res = campaign
    m = res["master"]
    assert np.allclose(m.Norm_Makespan, m.Execution_Time / m.Lower_Bound) and (m.Norm_Makespan >= 1 - 1e-9).all()
    inst = pd.read_csv(res["figures"] / "g1_makespan_vs_size_instances.csv", float_precision="round_trip")
    data = pd.read_csv(res["figures"] / "g1_makespan_vs_size.csv", float_precision="round_trip")
    assert (inst.Norm_Makespan >= 1 - 1e-9).all()
    assert (data.q25 >= 1 - 1e-9).all() and (data.q25 <= data["median"]).all() and (data["median"] <= data.q75).all()


def test_figure_data_is_consistent_with_master(campaign):
    _, _, res = campaign
    m = res["master"]
    keys = ["Workload", "Resource_Count", "Problem_Size", "Algorithm"]
    inst = pd.read_csv(res["figures"] / "g1_makespan_vs_size_instances.csv", float_precision="round_trip")
    data = pd.read_csv(res["figures"] / "g1_makespan_vs_size.csv", float_precision="round_trip")
    # per-instance file: one row per (instance, algorithm), equal to the mean over that instance's repeats
    assert len(inst) == 4 * 6 and not inst.duplicated(["Instance_Hash", "Algorithm"]).any()
    expect = m.groupby(["Instance_Hash", "Algorithm"]).Norm_Makespan.mean()
    got = inst.set_index(["Instance_Hash", "Algorithm"]).Norm_Makespan
    assert np.allclose(got.sort_index(), expect.sort_index(), rtol=1e-12)
    # plotted summary: recomputable from the per-instance file alone; classes are not pooled
    again = inst.groupby(keys).Norm_Makespan.agg(
        median="median", q25=lambda x: x.quantile(0.25), q75=lambda x: x.quantile(0.75), count="size").reset_index()
    assert len(data) == 2 * 6 and (data["count"] == 2).all() and data["count"].sum() == len(inst)
    for col in ("median", "q25", "q75"):
        assert np.allclose(data.sort_values(keys)[col], again.sort_values(keys)[col], rtol=1e-12)
    assert set(data.Workload) == {"regular", "irregular_hetero"}


def test_final_export_refuses_placeholder_identifiers(campaign):
    tmp, raw_dir, res = campaign
    assert res["placeholders"] is True
    with pytest.raises(ValueError, match="placeholders"):
        analyze(raw_dir, tmp / "final", ROOT / "configs" / "identity.toml", final=True)
    ident = tmp / "identity.toml"
    ident.write_text('batch_id = "B-TEST"\n[student_id]\nBASE = "S-TEST"\nS01 = "S-TEST"\nS02 = "S-TEST"\nS03 = "S-TEST"\n')
    ok = analyze(raw_dir, tmp / "final", ident, final=True)
    assert set(ok["master"].Student_ID) == {"S-TEST"} and ok["placeholders"] is False


def test_rerun_gives_identical_simulated_columns(campaign, tmp_path):
    _, raw_dir, _ = campaign
    again = run_campaign(write_config(tmp_path), tmp_path / "raw")
    a, b = raw_text(raw_dir), raw_text(again)
    simulated = ["instance_hash", "algorithm", "run_id", "makespan_sim", "busy_time_sim", "serial_best_sim",
                 "lower_bound_sim", "valid", "status"]
    assert a[simulated].equals(b[simulated])
    assert not a.scheduling_time_s.equals(b.scheduling_time_s)   # wall-clock time is measured, so it differs


def crash(inst, rng):
    raise RuntimeError("boom\nsecond line")


def hang(inst, rng):
    while True:
        time.sleep(0.01)


def overlap(inst, rng):
    s, info = HEURISTICS["HEFT"](inst, rng)
    return Schedule(np.zeros_like(s.proc), s.start, s.finish), info   # everything on processor 0 at the old times


def test_failures_are_recorded_not_dropped(tmp_path):
    sched = dict(SCHEDULERS, CRASH=("BASE", crash, {}), HANG=("BASE", hang, {}), OVERLAP=("BASE", overlap, {}))
    raw_dir = run_campaign(write_config(tmp_path, ["HEFT", "CRASH", "HANG", "OVERLAP"], timeout=0.2),
                           tmp_path / "raw", sched)
    t = raw_text(raw_dir)
    assert len(t) == 4 * 4 * 2 and not (t == "").any().any()
    status = t.groupby("algorithm").status.agg(set).to_dict()
    assert status == {"HEFT": {"ok"}, "CRASH": {"error"}, "HANG": {"timeout"}, "OVERLAP": {"invalid"}}
    bad = t[t.status != "ok"]
    for col in ("makespan_sim", "busy_time_sim", "scheduling_time_s"):
        assert set(bad[col]) == {"NA"}                      # NA, never 0
    assert set(t[t.algorithm == "CRASH"].error_msg) == {"RuntimeError: boom"}
    assert set(t[t.algorithm == "OVERLAP"].valid) == {"0"} and set(t[t.algorithm == "CRASH"].valid) == {"NA"}
    assert json.loads((raw_dir / "manifest.json").read_text())["failed_count"] == 24
    res = analyze(raw_dir, tmp_path / "results", ROOT / "configs" / "identity.toml")
    m = res["master"]
    assert len(m) == 32 and m[m.Status != "ok"].Speedup.isna().all()      # failed rows kept, with NA metrics
    assert res["summary"].set_index("Algorithm").rows_not_ok.to_dict() == {"HEFT": 0}  # only HEFT has ok rows
    text = pd.read_csv(res["derived"] / "master.csv", dtype=str, keep_default_na=False)
    assert set(text[text.Status != "ok"].Execution_Time) == {"NA"} and set(text.Status) == {"ok", "error", "timeout", "invalid"}
    assert check(raw_dir, m) == []


def test_check_detects_tampering(campaign, tmp_path):
    _, raw_dir, _ = campaign
    fake = tmp_path / "fake"
    fake.mkdir()
    raw = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    raw.loc[0, "makespan_sim"] = "1.0"                      # below the lower bound, and unequal across repeats
    raw.iloc[:-1].to_csv(fake / "runs.csv", index=False)    # and one row missing
    (fake / "manifest.json").write_text((raw_dir / "manifest.json").read_text())
    (fake / "ga_trace.csv").write_text((raw_dir / "ga_trace.csv").read_text())
    problems = check(fake)
    assert any("lower bound" in p for p in problems) and any("repeats" in p for p in problems)
    assert any("every instance" in p for p in problems) and any("manifest counts" in p for p in problems)


def test_cli_end_to_end(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    cfg = write_config(tmp_path)
    run = subprocess.run([sys.executable, "-m", "schedlab", "run", "--config", str(cfg), "--out", str(tmp_path / "raw")],
                         capture_output=True, text=True, env=env, cwd=ROOT)
    assert run.returncode == 0, run.stderr
    raw_dir = run.stdout.splitlines()[0]
    an = subprocess.run([sys.executable, "-m", "schedlab", "analyze", raw_dir, "--out", str(tmp_path / "results")],
                        capture_output=True, text=True, env=env, cwd=ROOT)
    assert an.returncode == 0, an.stderr
    assert "campaign checks: all passed" in an.stdout and "placeholders" in an.stdout
