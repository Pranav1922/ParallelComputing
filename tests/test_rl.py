import json
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from schedlab import rl
from schedlab.analysis import analyze, check
from schedlab.heuristics import HEURISTICS
from schedlab.model import ScheduleBuilder, make_instance, validate
from schedlab.runner import build_schedulers, run_campaign
from schedlab.workloads import experiment_matrix, generate
from test_model import same

ROOT = Path(__file__).resolve().parent.parent
SMALL_CELLS = [("regular", 10, 2), ("heterogeneous", 12, 3)]
TINY = dict(batch=2, max_updates=3, val_every=1, time_cap_s=600.0, bc_updates=2)


def insts(k=8, split="val"):
    return [generate(["regular", "irregular", "heterogeneous", "irregular_hetero"][i % 4], 12 + i, 2 + i % 3,
                     split, i, campaign_seed=5) for i in range(k)]


@pytest.fixture(autouse=True)
def small_stream(monkeypatch):
    monkeypatch.setattr(rl, "CELLS", SMALL_CELLS)


# ---- environment and features -----------------------------------------------------------------------------

def test_candidates_are_exactly_the_valid_pairs_and_features_are_sane():
    for inst in insts(4):
        b, ctx = ScheduleBuilder(inst), rl.Context(inst)
        while not b.done():
            pairs, X = rl.candidates(b, ctx)
            assert pairs == [(t, p) for t in b.ready for p in range(inst.m)]
            assert X.shape == (len(pairs), 12) and np.isfinite(X).all()
            assert np.allclose(X[:, 0], np.log(inst.cost[[t for t, _ in pairs], [p for _, p in pairs]]
                                                / inst.cost.min(axis=1)[[t for t, _ in pairs]]))
            assert (X[:, 6] >= 0).all() and X[:, 6].min() == 0          # finish relative to the best candidate
            b.place(*pairs[len(pairs) // 2], rl.INSERT)


def test_features_are_deterministic_and_invariant_to_the_time_unit():
    inst = insts(1)[0]
    edges = [(u, v) for v in range(inst.n) for u in inst.preds[v]]
    scaled = make_instance("s", inst.m, edges, inst.cost * 3.7)
    for a in (inst, scaled):
        b = ScheduleBuilder(a)
        b.place(b.ready[0], 0, True)
    ba, bs = ScheduleBuilder(inst), ScheduleBuilder(scaled)
    for b in (ba, bs):
        b.place(b.ready[0], 1, True)
    Xa, Xs = rl.candidates(ba, rl.Context(inst))[1], rl.candidates(bs, rl.Context(scaled))[1]
    assert np.allclose(Xa, Xs, rtol=1e-9) and np.array_equal(Xa, rl.candidates(ba, rl.Context(inst))[1])


def test_rollouts_are_valid_greedy_is_deterministic_and_ties_go_to_the_first_candidate():
    torch.manual_seed(0)
    pol = rl.make_policy(12)
    for inst in insts(6):
        for mode in ("greedy", "sample"):
            s = rl.rollout(inst, pol, list(range(12)), mode, torch.Generator().manual_seed(1))[0]
            assert validate(inst, s) == []
        a, b = (rl.rollout(inst, pol, list(range(12)))[0] for _ in range(2))
        assert same(a, b)
    zero = rl.make_policy(12)
    for p in zero.parameters():
        torch.nn.init.zeros_(p)
    inst = make_instance("ties", 2, [], [[1.0, 1.0]] * 3)
    s = rl.rollout(inst, zero, list(range(12)))[0]
    assert s.proc.tolist() == [0, 0, 0]          # all-equal scores: lowest task id on the lowest processor


def test_heft_trajectory_in_the_rl_environment_equals_heft():
    """The RL environment, with HEFT's decisions, reproduces the HEFT baseline exactly: same simulator, same
    insertion rule. This is also the trajectory the behaviour-cloning fallback imitates."""
    pol = rl.make_policy(12)
    for inst in insts(8):
        s = rl.rollout(inst, pol, list(range(12)), "heft")[0]
        assert same(s, HEURISTICS["HEFT"](inst, None)[0])


# ---- reward and advantage ---------------------------------------------------------------------------------

def test_reward_and_advantage_signs_and_normalisation():
    c, heft, lb = np.array([90.0, 100, 120, 100]), np.array([100.0, 100, 100, 110]), np.array([50.0, 50, 50, 55])
    G, A, Z = rl.advantages(c, heft, lb)
    assert np.allclose(G, -c / lb) and np.allclose(A, (heft - c) / lb)
    assert ((A > 0) == (c < heft)).all() and ((A == 0) == (c == heft)).all()       # positive iff RL beat HEFT
    assert np.allclose(A, G - (-heft / lb))                                         # A = G - b
    assert abs(Z.mean()) < 1e-12 and abs(Z.std() - 1) < 1e-12 and (np.argsort(Z) == np.argsort(A)).all()
    assert np.array_equal(rl.advantages([5.0, 5.0], [5.0, 5.0], [1.0, 1.0])[2], [0.0, 0.0])


# ---- training: information flow, determinism, checkpointing, fallback -------------------------------------

def test_training_refuses_non_val_validation_and_held_out_collisions(tmp_path):
    with pytest.raises(ValueError, match="val"):
        rl.train(0, insts(2, "test_id"), set(), tmp_path / "a", settings=TINY)
    hit = {rl.stream_instance(1).meta["hash"]}
    with pytest.raises(RuntimeError, match="collides"):
        rl.train(0, insts(2), hit, tmp_path / "b", settings=TINY)


def test_training_stream_is_train_split_and_disjoint_from_the_real_matrix(monkeypatch):
    monkeypatch.setattr(rl, "CELLS", [(c, n, m) for c in ("regular", "irregular", "heterogeneous", "irregular_hetero")
                                      for n in (50, 100, 200) for m in (2, 4, 8)])
    cfg = tomllib.loads((ROOT / "configs" / "full.toml").read_text())
    mx = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
    held = {i.meta["hash"] for s in ("train", "val", "test_id", "test_ood") for i in mx[s]}
    stream = [rl.stream_instance(k) for k in range(60)]
    assert {i.meta["split"] for i in stream} == {"train"} and min(i.meta["index"] for i in stream) >= 1000
    assert not {i.meta["hash"] for i in stream} & held and len({i.meta["hash"] for i in stream}) == 60


def test_training_is_deterministic_and_keeps_the_best_validation_checkpoint(tmp_path):
    val = insts(3)
    a = rl.train(0, val, set(), tmp_path / "a", settings=TINY, log=lambda m: None)
    b = rl.train(0, val, set(), tmp_path / "b", settings=TINY, log=lambda m: None)
    c = rl.train(1, val, set(), tmp_path / "c", settings=TINY, log=lambda m: None)
    assert a["model_id"] == b["model_id"] != c["model_id"]
    assert (tmp_path / "a" / "train_hashes.txt").read_text() == (tmp_path / "c" / "train_hashes.txt").read_text()
    log = pd.read_csv(tmp_path / "a" / "training_log.csv", na_values="NA")
    v = log.dropna(subset=["val_rho"])
    best = v.loc[v.val_rho.idxmin()]                        # idxmin: first minimum = earliest update
    assert a["best_update"] == best["update"] and a["best_val_rho"] == best["val_rho"] and a["val_rho_update0"] == v.val_rho.iloc[0]
    assert a["learned_vs_update0"] == (a["best_val_rho"] < a["val_rho_update0"])
    model, mid = rl.load(tmp_path / "a")
    assert mid == a["model_id"] and rl.validate_policy(model["policy"], model["cols"], val,
        [HEURISTICS["HEFT"](i, None)[0].makespan for i in val]) == pytest.approx(a["best_val_rho"], rel=1e-12)
    with pytest.raises(FileExistsError):
        rl.train(0, val, set(), tmp_path / "a", settings=TINY)


def test_ablation_drops_the_heft_features_and_bc_flag_is_recorded(tmp_path):
    m = rl.train(0, insts(2), set(), tmp_path / "abl", ablation=True, bc=True, settings=TINY, log=lambda m: None)
    assert m["features"] == [f for f in rl.FEATURES if f not in rl.HEFT_FEATURES] and len(m["features"]) == 10
    assert m["behaviour_cloning"] is True and m["ablation"] is True


def test_behaviour_cloning_objective_reproduces_heft_on_a_toy_instance():
    torch.manual_seed(0)
    inst = generate("heterogeneous", 10, 2, "train", 5000, campaign_seed=5)
    pol, cols = rl.make_policy(12), list(range(12))
    opt = torch.optim.Adam(pol.parameters(), lr=1e-2)
    for _ in range(150):
        loss = -rl.rollout(inst, pol, cols, "heft")[1]
        opt.zero_grad()
        loss.backward()
        opt.step()
    assert same(rl.rollout(inst, pol, cols)[0], HEURISTICS["HEFT"](inst, None)[0])


def test_load_detects_tampering_and_schedule_refuses_training_instances(tmp_path):
    meta = rl.train(0, insts(2), set(), tmp_path / "m", settings=TINY, log=lambda m: None)
    model, _ = rl.load(tmp_path / "m")
    with pytest.raises(ValueError, match="training stream"):
        rl.schedule(rl.stream_instance(0), None, model)
    s, info = rl.schedule(insts(1)[0], None, model)
    assert info["decision_count"] == insts(1)[0].n and info["decision_time_s"] > 0
    bad = tmp_path / "bad"
    bad.mkdir()
    for f in ("policy.pt", "train_hashes.txt"):
        (bad / f).write_bytes((tmp_path / "m" / f).read_bytes())
    (bad / "model.json").write_text(json.dumps(dict(meta, model_id="0" * 16)))
    with pytest.raises(ValueError, match="do not match"):
        rl.load(bad)


# ---- configuration lock and runner/analysis integration ---------------------------------------------------

def test_pilot_config_changes_only_the_pilot_length():
    cfg = tomllib.loads((ROOT / "configs" / "s02_pilot.toml").read_text())
    full = tomllib.loads((ROOT / "configs" / "full.toml").read_text())
    assert cfg["workload"] == full["workload"] and cfg["campaign"]["seed"] == full["campaign"]["seed"] == rl.CAMPAIGN_SEED
    assert set(cfg["s02_train"]) == {"max_updates", "time_cap_s", "val_every"} and cfg["run"]["splits"] == ["val"]
    assert {k: v for k, v in rl.SETTINGS.items()} == dict(lr=3e-4, batch=16, beta=0.01, clip=1.0, max_updates=3000,
        time_cap_s=2700.0, val_every=100, hidden=64, stream_seed=20261017, stream_offset=1000, bc_updates=200)


CONFIG = """
[campaign]
name = "s02_it"
seed = 5
workers = 1
[workload]
sizes = [10, 14]
processors = [2, 3]
classes = ["regular", "heterogeneous"]
instances = { train = 2, val = 2 }
ood = []
[run]
splits = ["val"]
algorithms = ["FCFS-EAT", "FCFS-EFT", "SPT-EFT", "LPT-EFT", "HEFT", "MINMIN", "RL-S0", "RL-S1"]
timing_repeats = 2
timeout_s = 60
[s02]
models = { "RL-S0" = "%s", "RL-S1" = "%s" }
model_ids = { "RL-S0" = "%s", "RL-S1" = "%s" }
"""


def test_runner_and_analysis_with_two_seed_models(tmp_path):
    a = rl.train(0, insts(2), set(), tmp_path / "s0", settings=TINY, log=lambda m: None)
    b = rl.train(1, insts(2), set(), tmp_path / "s1", settings=TINY, log=lambda m: None)
    cfg = tmp_path / "c.toml"
    cfg.write_text(CONFIG % (tmp_path / "s0", tmp_path / "s1", a["model_id"], b["model_id"]))
    raw_dir = run_campaign(cfg, tmp_path / "raw")
    t = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    s02 = t[t.sub_problem == "S02"]
    assert len(t) == 16 * 8 * 2 and set(t.status) == {"ok"} and set(s02.algo_seed) == {"NA"}
    assert set(s02[s02.algorithm == "RL-S0"].model_id) == {a["model_id"]}
    m = json.loads((raw_dir / "manifest.json").read_text())
    assert "power_at_start" in next(iter(m["hardware"].values())) and "power_at_end" in m
    res = analyze(raw_dir, tmp_path / "res", ROOT / "configs" / "identity.toml")
    assert res["problems"] == []
    p = res["s02_paired"]
    assert "RL" in set(p.algorithm) and p.wilcoxon_p.notna().sum() <= 1
    assert p[(p.algorithm == "RL") & (p.baseline == "HEFT")].wilcoxon_p.notna().sum() <= 1
    fig = res["figures"]
    for stem in ("g4_training_curves", "g5_makespan_by_method", "g6_rho_by_group"):
        assert (fig / f"{stem}.pdf").exists() and (fig / f"{stem}.svg").read_text().count("<svg") == 1
    inst = pd.read_csv(fig / "g5_makespan_by_method_instances.csv", float_precision="round_trip")
    summ = pd.read_csv(fig / "g5_makespan_by_method.csv").set_index(["Split", "Method"])["median"]
    assert np.allclose(summ.sort_index(), inst.groupby(["Split", "Method"]).Cmax_over_LB.median().sort_index(), rtol=1e-12)
    g6 = pd.read_csv(fig / "g6_rho_by_group_instances.csv", float_precision="round_trip")
    assert np.allclose(pd.read_csv(fig / "g6_rho_by_group.csv").set_index(["Split", "Group", "Method"])["median"].sort_index(),
                       g6.groupby(["Split", "Group", "Method"]).rho_vs_HEFT.median().sort_index(), rtol=1e-12)
    bad = tmp_path / "bad.toml"
    bad.write_text(CONFIG % (tmp_path / "s0", tmp_path / "s1", "0" * 16, b["model_id"]))
    with pytest.raises(ValueError, match="pinned"):
        build_schedulers(tomllib.loads(bad.read_text()))


def test_full_training_config_uses_the_predeclared_settings_unchanged():
    cfg = tomllib.loads((ROOT / "configs" / "s02_train.toml").read_text())
    full = tomllib.loads((ROOT / "configs" / "full.toml").read_text())
    assert "s02_train" not in cfg and cfg["workload"] == full["workload"] and cfg["campaign"]["seed"] == full["campaign"]["seed"]


def test_final_s02_config_is_locked():
    cfg = tomllib.loads((ROOT / "configs" / "s02_final.toml").read_text())
    full = tomllib.loads((ROOT / "configs" / "full.toml").read_text())
    assert cfg["workload"] == full["workload"] and cfg["campaign"]["seed"] == full["campaign"]["seed"]
    assert cfg["run"]["splits"] == ["test_id", "test_ood"] and cfg["run"]["timing_repeats"] == 3
    assert cfg["run"]["algorithms"] == ["FCFS-EAT", "FCFS-EFT", "SPT-EFT", "LPT-EFT", "HEFT", "MINMIN",
                                        "RL-S0", "RL-S1", "RL-S2", "RL-NOHEFTFEAT"]
    assert cfg["s02"]["model_ids"] == {"RL-S0": "c827a9f51c512ac4", "RL-S1": "e83496e27b9d4ef1",
                                       "RL-S2": "1765acd48d43dfde", "RL-NOHEFTFEAT": "a7781d888bca8550"}
    assert cfg["s02"]["models"] == {"RL-S0": "results/models/s02_rl_seed0", "RL-S1": "results/models/s02_rl_seed1",
                                    "RL-S2": "results/models/s02_rl_seed2",
                                    "RL-NOHEFTFEAT": "results/models/s02_rl_noheftfeat_seed0"}
    assert "s02_train" not in cfg
