import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from schedlab import adaptive
from schedlab.analysis import analyze, check, gap_closed
from schedlab.heuristics import HEURISTICS
from schedlab.model import make_instance, validate
from schedlab.runner import DECISION_COLUMNS, run_campaign
from schedlab.workloads import experiment_matrix, generate

ROOT = Path(__file__).resolve().parent.parent
WORKLOAD = dict(sizes=[10, 20], processors=[2, 3], classes=["regular", "heterogeneous"],
                instances=dict(train=6, val=3, test_id=2), ood=[])
SEED = 31


@pytest.fixture(scope="module")
def matrix():
    return experiment_matrix(WORKLOAD, SEED)


@pytest.fixture(scope="module")
def bundle(matrix):
    return adaptive.train_selector(matrix["train"], matrix["val"])


# ---- features ---------------------------------------------------------------------------------------------

def test_features_are_finite_deterministic_and_scale_free(matrix):
    for inst in matrix["train"][:12]:
        x = adaptive.features(inst)
        assert x.shape == (len(adaptive.FEATURES),) and np.isfinite(x).all()
        assert np.array_equal(x, adaptive.features(inst))
        edges = [(u, v) for v in range(inst.n) for u in inst.preds[v]]
        scaled = make_instance("s", inst.m, edges, inst.cost * 7.5)       # change of time unit
        assert np.allclose(adaptive.features(scaled), x, rtol=1e-12)


def test_feature_values_on_known_instances():
    homog = make_instance("h", 2, [(0, 1), (0, 2), (1, 3), (2, 3)], [[1, 1], [2, 2], [2, 2], [1, 1]])
    x = dict(zip(adaptive.FEATURES, adaptive.features(homog)))
    assert x["log_n"] == pytest.approx(np.log(4)) and x["depth_ratio"] == pytest.approx(3 / 4)
    assert x["par_ratio"] == pytest.approx(4 / 3 / 2) and x["edge_density"] == pytest.approx(1.0)
    assert x["het_machine"] == 0 and x["het_affinity"] == 0
    assert x["cp_ratio"] == pytest.approx(4 / (6 / 2))                   # path 1+2+1 over work/m
    het = make_instance("x", 2, [], [[1, 10], [10, 1], [1, 10]])
    assert dict(zip(adaptive.FEATURES, adaptive.features(het)))["het_affinity"] == pytest.approx(1 / 3)
    assert np.array_equal(adaptive.features(make_instance("e", 2, [], np.zeros((0, 2)))), np.zeros(9))


# ---- training and information flow ------------------------------------------------------------------------

def test_labels_break_ties_towards_the_cheaper_heuristic():
    C = np.array([[5.0, 5.0, 6, 6, 5.0, 7], [9, 9, 9, 9, 8, 8]])
    assert adaptive.labels(C).tolist() == [0, 4]


def test_training_rejects_any_other_split(matrix):
    with pytest.raises(ValueError, match="train"):
        adaptive.train_selector(matrix["train"] + matrix["test_id"][:1], matrix["val"])
    with pytest.raises(ValueError, match="val"):
        adaptive.train_selector(matrix["train"], matrix["test_id"])
    with pytest.raises(ValueError, match="train"):
        adaptive.train_selector(matrix["val"], matrix["val"])


def test_depth_sbs_and_contingency_come_from_val(bundle, matrix):
    r = bundle["report"]
    table = {int(k): v for k, v in r["val_mean_regret_by_depth"].items() if k != "unlimited"}
    assert r["depth"] == min(table, key=lambda d: (round(table[d], 12), d)) and bundle["tree"].get_depth() <= r["depth"]
    va = adaptive.heuristic_table(matrix["val"])
    norm = (va["C"] / va["lb"][:, None]).mean(axis=0)
    assert bundle["sbs"] == adaptive.PORTFOLIO[int(norm.argmin())] and bundle["val_rank"][0] == bundle["sbs"]
    gap = (va["C"][:, adaptive.PORTFOLIO.index(bundle["sbs"])] / va["C"].min(axis=1) - 1).mean()
    assert r["val_sbs_vbs_gap"] == pytest.approx(gap) and r["contingency_triggered"] == (gap < 0.02)
    assert set(bundle["train_hashes"]) == {i.meta["hash"] for i in matrix["train"]}
    assert not set(bundle["train_hashes"]) & {i.meta["hash"] for i in matrix["test_id"]}


def test_save_load_round_trip_and_no_overwrite(bundle, tmp_path):
    mid = adaptive.save(bundle, tmp_path / "m")
    again, mid2 = adaptive.load(tmp_path / "m")
    assert mid == mid2 and again["sbs"] == bundle["sbs"] and json.loads((tmp_path / "m" / "model.json").read_text())["model_id"] == mid
    with pytest.raises(FileExistsError):
        adaptive.save(bundle, tmp_path / "m")


# ---- decisions --------------------------------------------------------------------------------------------

def test_decisions_are_portfolio_members_and_results_match_direct_runs(bundle, matrix):
    for inst in matrix["test_id"] + matrix["val"]:
        direct = {h: HEURISTICS[h](inst, None)[0].makespan for h in adaptive.PORTFOLIO}
        for method in adaptive.METHODS:
            s, info = adaptive.schedule(inst, np.random.default_rng(0), method, bundle)
            d = info["decision"]
            assert validate(inst, s) == [] and set(d["candidates"]) <= set(adaptive.PORTFOLIO)
            assert d["selected"] in d["candidates"] and s.makespan == direct[d["selected"]]
            assert info["decision_count"] == len(d["candidates"]) and info["decision_time_s"] >= 0
        top2 = adaptive.schedule(inst, None, "ADAPTIVE-TOP2", bundle)[1]["decision"]["candidates"]
        assert len(set(top2)) == 2 and top2[0] == adaptive.select(bundle, inst)["picks"][0]
        assert adaptive.schedule(inst, None, "TRY-ALL", bundle)[0].makespan == min(direct.values())


def test_novelty_guard_falls_back_to_sbs(bundle, matrix):
    inst = matrix["test_id"][0]
    far = dict(bundle, guard_lo=bundle["guard_lo"] + 1e6, guard_hi=bundle["guard_hi"] + 1e6)   # everything is novel
    d = adaptive.select(far, inst)
    assert d["fallback"] and d["picks"] == [bundle["sbs"]]
    assert adaptive.select(far, inst, k=2)["picks"] == bundle["val_rank"][:2]
    assert not adaptive.select(far, inst, guard=False)["fallback"]
    x = adaptive.features(inst)
    assert adaptive.select(bundle, inst)["novel"] == bool(((x < bundle["guard_lo"]) | (x > bundle["guard_hi"])).any())


def test_random_select_is_seeded():
    inst = generate("heterogeneous", 15, 2, "test_id", 0, campaign_seed=SEED)
    b = dict(portfolio=adaptive.PORTFOLIO, train_hashes=[], val_hashes=[])
    pick = lambda s: adaptive.schedule(inst, np.random.default_rng(s), "RANDOM-SELECT", b)[1]["decision"]["selected"]
    assert pick(3) == pick(3) and len({pick(s) for s in range(30)}) > 1


def test_leakage_guard(bundle, matrix):
    with pytest.raises(ValueError, match="training set"):
        adaptive.schedule(matrix["train"][0], None, "ADAPTIVE", bundle)
    val = matrix["val"][0]
    adaptive.schedule(val, None, "ADAPTIVE", bundle)                                 # the pilot may run on val
    as_test = type(val)(val.id, val.n, val.m, val.preds, val.succs, val.cost, dict(val.meta, split="test_id"))
    with pytest.raises(ValueError, match="model selection"):
        adaptive.schedule(as_test, None, "ADAPTIVE", bundle)


def test_gap_closed_formula():
    lb = np.ones(2)
    assert gap_closed([10, 10], [8, 9], [6, 8], lb)["gap_closed"] == pytest.approx((10 - 8.5) / (10 - 7))
    assert np.isnan(gap_closed([5, 5], [5, 5], [5, 5], lb)["gap_closed"])


# ---- runner and analysis ----------------------------------------------------------------------------------

CONFIG = """
[campaign]
name = "s03_it"
seed = %d
workers = 1
[workload]
sizes = [10, 20]
processors = [2, 3]
classes = ["regular", "heterogeneous"]
instances = { train = 6, val = 3, test_id = 2 }
ood = []
[run]
splits = ["test_id"]
algorithms = ["FCFS-EAT", "FCFS-EFT", "SPT-EFT", "LPT-EFT", "HEFT", "MINMIN",
              "ADAPTIVE", "ADAPTIVE-TOP2", "ADAPTIVE-NOGUARD", "RANDOM-SELECT", "TRY-ALL"]
timing_repeats = 2
timeout_s = 60
[s03]
model = "%s"
seeds = [0, 1, 2]
"""


@pytest.fixture(scope="module")
def s03_campaign(tmp_path_factory, bundle):
    tmp = tmp_path_factory.mktemp("s03")
    model_id = adaptive.save(bundle, tmp / "model")
    cfg = tmp / "s03.toml"
    cfg.write_text(CONFIG % (SEED, tmp / "model"))
    raw_dir = run_campaign(cfg, tmp / "raw")
    return raw_dir, model_id, analyze(raw_dir, tmp / "results", ROOT / "configs" / "identity.toml")


def test_runner_records_s03_runs(s03_campaign):
    raw_dir, model_id, res = s03_campaign
    t = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    s03 = t[t.sub_problem == "S03"]
    assert len(t) == 16 * (6 * 2 + 4 * 2 + 3) and set(t.status) == {"ok"}
    assert set(s03.model_id) == {model_id} and set(t[t.sub_problem == "BASE"].model_id) == {"NA"}
    assert set(s03[s03.algorithm == "RANDOM-SELECT"].algo_seed) == {"0", "1", "2"}
    assert (s03.decision_time_s != "NA").all()
    d = pd.read_csv(raw_dir / "decisions.csv")
    assert list(d.columns) == DECISION_COLUMNS and set(d.run_uid) == set(s03.run_uid)
    m = json.loads((raw_dir / "manifest.json").read_text())
    assert m["models"][0]["model_id"] == model_id
    assert res["problems"] == []          # includes every S03 invariant in analysis._check_s03


def test_check_catches_a_wrong_s03_result(s03_campaign, tmp_path):
    raw_dir, _, _ = s03_campaign
    fake = tmp_path / "fake"
    fake.mkdir()
    raw = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    i = raw.index[raw.algorithm == "ADAPTIVE"][0]
    raw.loc[i, "makespan_sim"] = str(float(raw.loc[i, "makespan_sim"]) * 1.5)
    raw.to_csv(fake / "runs.csv", index=False)
    for f in ("manifest.json", "ga_trace.csv", "decisions.csv"):
        (fake / f).write_text((raw_dir / f).read_text())
    assert any("selected heuristic" in p for p in check(fake))


def test_s03_tables_and_figures(s03_campaign):
    _, _, res = s03_campaign
    rob, pairs, fig = res["s03_robustness"], res["s03_paired"], res["figures"]
    r = rob.set_index("method")
    assert r.loc["VBS", "regret_mean"] == 0 and (rob.regret_mean >= -1e-12).all()
    assert r.loc["TRY-ALL", "regret_mean"] == pytest.approx(0, abs=1e-12)
    sbs = res["manifest"]["models"][0]["report"]["sbs"]
    assert r.loc["SBS", "cmax_over_lb_mean"] == r.loc[sbs, "cmax_over_lb_mean"]          # SBS is that heuristic's rows
    p = pairs.set_index(["algorithm", "baseline"])
    assert p.wilcoxon_p.notna().sum() <= 1 and ("ADAPTIVE", "SBS") in p.index
    assert (pairs.better + pairs.tie + pairs.worse == pairs.instances).all()
    for stem in ("g7_feature_vs_policy", "g8_adaptive_vs_fixed", "g9_regret_heatmap"):
        assert (fig / f"{stem}.pdf").exists() and (fig / f"{stem}.svg").read_text().count("<svg") == 1
    inst = pd.read_csv(fig / "g8_adaptive_vs_fixed_instances.csv", float_precision="round_trip")
    summ = pd.read_csv(fig / "g8_adaptive_vs_fixed.csv").set_index(["Split", "Method"])["median"]
    assert np.allclose(summ.sort_index(), inst.groupby(["Split", "Method"]).Cmax_over_LB.median().sort_index(), rtol=1e-12)
    heat = pd.read_csv(fig / "g9_regret_heatmap_instances.csv", float_precision="round_trip")
    grid = pd.read_csv(fig / "g9_regret_heatmap.csv", index_col=0)
    assert np.allclose(grid.to_numpy(), heat.groupby(["Group", "Method"]).Regret.mean().unstack()[grid.columns].to_numpy(), rtol=1e-12)
    assert (res["derived"] / "s03_selection_by_class.csv").exists()


# ---- contingency extension: GA-1000 as a seventh member ---------------------------------------------------

@pytest.fixture(scope="module")
def ga_bundle(matrix, bundle):
    return adaptive.train_selector_ga(matrix["train"], matrix["val"], bundle, "base-id")


def test_ga_member_uses_the_locked_s01_settings_with_1000_evaluations():
    import tomllib
    locked = tomllib.loads((ROOT / "configs" / "s01_final.toml").read_text())["ga"]
    expect = {k: (tuple(v) if isinstance(v, list) else v) for k, v in locked.items() if k != "seeds"}
    assert adaptive.GA_SETTINGS == dict(expect, max_evals=1000)


def test_theta_labels_are_strict_and_ties_go_to_the_heuristic():
    C6 = np.array([[10.0, 11, 12, 13, 10, 14], [10.0, 11, 12, 13, 14, 15], [10.0, 11, 12, 13, 14, 15]])
    cga = np.array([10.0, 9.9, 9.0])
    assert adaptive.theta_labels(C6, cga, 0.0).tolist() == [0, 6, 6]
    assert adaptive.theta_labels(C6, cga, 0.02).tolist() == [0, 0, 6]


def test_extension_keeps_the_base_and_chooses_theta_by_the_predeclared_rule(ga_bundle, bundle, matrix):
    r = ga_bundle["report"]
    assert ga_bundle["portfolio"] == adaptive.PORTFOLIO + ["GA-1000"] and bundle["portfolio"] == adaptive.PORTFOLIO
    assert ga_bundle["sbs"] == bundle["sbs"] and ga_bundle["train_hashes"] == bundle["train_hashes"]
    assert np.array_equal(ga_bundle["guard_lo"], bundle["guard_lo"]) and r["extension_of"] == "base-id"
    t = r["theta_table"]
    ok = [th for th in adaptive.THETAS if t[str(th)]["ga_call_efficiency"] is not None]
    assert r["theta"] == (max(ok, key=lambda th: (round(t[str(th)]["ga_call_efficiency"], 12), th)) if ok else None)
    for th in ok:
        e = t[str(th)]
        assert e["ga_call_efficiency"] == pytest.approx((r["val_sbs_regret_vs_vbs6"] - e["val_mean_regret_vs_vbs6"]) / e["val_ga_calls"])
    assert r["trigger"]["val_sbs_vbs_gap"] == pytest.approx(bundle["report"]["val_sbs_vbs_gap"])
    with pytest.raises(ValueError):
        adaptive.train_selector_ga(matrix["train"][:-1], matrix["val"], bundle, "base-id")


def test_ga_methods(ga_bundle, matrix):
    for inst in matrix["test_id"][:6]:
        seeds = min(HEURISTICS[h](inst, None)[0].makespan for h in adaptive.GA_SETTINGS["seed_heuristics"])
        s, info = adaptive.schedule(inst, np.random.default_rng(1), "GA-1000", ga_bundle)
        assert validate(inst, s) == [] and s.makespan <= seeds * (1 + 1e-12) and info["fitness_evals"] == 1000
        assert "trace" not in info and info["decision"]["selected"] == "GA-1000"
        a = adaptive.schedule(inst, np.random.default_rng(1), "ADAPTIVE-GA", ga_bundle)
        b = adaptive.schedule(inst, np.random.default_rng(1), "ADAPTIVE-GA", ga_bundle)
        assert a[0].makespan == b[0].makespan and a[1]["decision"]["selected"] in ga_bundle["portfolio"]


def test_runner_with_the_extension(tmp_path, bundle, ga_bundle):
    adaptive.save(bundle, tmp_path / "m")
    gid = adaptive.save(ga_bundle, tmp_path / "mg")
    cfg = tmp_path / "s03ga.toml"
    text = CONFIG % (SEED, tmp_path / "m")
    text = text.replace('"TRY-ALL"]', '"TRY-ALL", "ADAPTIVE-GA", "GA-1000"]') + f'model_ga = "{tmp_path / "mg"}"\n'
    cfg.write_text(text)
    raw_dir = run_campaign(cfg, tmp_path / "raw")
    t = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    g = t[t.algorithm.isin(["ADAPTIVE-GA", "GA-1000"])]
    assert len(g) == 16 * 2 * 3 and set(g.model_id) == {gid} and set(g.algo_seed) == {"0", "1", "2"}
    assert set(t[t.algorithm == "GA-1000"].fitness_evals) == {"1000"}
    assert (raw_dir / "ga_trace.csv").read_text().strip().count("\n") == 0       # S03 GA calls write no S01 trace
    res = analyze(raw_dir, tmp_path / "results", ROOT / "configs" / "identity.toml")
    assert res["problems"] == [] and (res["derived"] / "s03_ga_extension_overhead.csv").exists()
    assert {"ADAPTIVE-GA", "GA-1000"} <= set(res["s03_robustness"].method)


def test_model_id_ignores_measured_timings(ga_bundle, tmp_path):
    a = adaptive.save(dict(ga_bundle, timings=dict(t=1.0)), tmp_path / "a")
    b = adaptive.save(dict(ga_bundle, timings=dict(t=2.0)), tmp_path / "b")
    assert a == b and json.loads((tmp_path / "a" / "model.json").read_text())["measured"] == {"t": 1.0}


def test_final_s03_config_is_locked_to_the_reviewed_pilot():
    import tomllib
    load = lambda n: tomllib.loads((ROOT / "configs" / n).read_text())
    final, pilot, full = load("s03_final.toml"), load("s03_pilot_ga.toml"), load("full.toml")
    assert final["workload"] == pilot["workload"] == full["workload"] and final["campaign"]["seed"] == full["campaign"]["seed"]
    assert final["run"]["splits"] == ["test_id", "test_ood"]
    assert {k: v for k, v in final["run"].items() if k != "splits"} == {k: v for k, v in pilot["run"].items() if k != "splits"}
    assert {k: final["s03"][k] for k in ("model", "model_ga", "seeds")} == {k: pilot["s03"][k] for k in ("model", "model_ga", "seeds")}
    assert (final["s03"]["model_id"], final["s03"]["model_ga_id"]) == ("820ba281844c513e", "6d83fac40cb5c6ed")


def test_runner_refuses_a_model_that_differs_from_the_pinned_id(tmp_path, bundle):
    from schedlab.runner import build_schedulers
    adaptive.save(bundle, tmp_path / "m")
    with pytest.raises(ValueError, match="pinned"):
        build_schedulers({"s03": {"model": str(tmp_path / "m"), "model_id": "0000000000000000", "seeds": [0]}})
