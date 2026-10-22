"""S03: adaptive workload-aware scheduler. Per-instance selection among the six heuristics (ALGORITHM_DESIGN.md 5).

Information flow (enforced here, checked again by the runner):
  tree, labels, sample weights, novelty-guard ranges   <- `train` split only
  tree depth, SBS, contingency decision                <- `val` split only
  nothing                                              <- `test_id`, `test_ood`
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text

from . import ga
from .heuristics import HEURISTICS
from .model import Instance, ScheduleBuilder, bounds

FEATURES = ["log_n", "par_ratio", "depth_ratio", "edge_density", "work_cv", "work_skew", "cp_ratio",
            "het_machine", "het_affinity"]
GROUPS = {"structure": ["log_n", "par_ratio", "depth_ratio", "edge_density", "cp_ratio"],
          "work": ["work_cv", "work_skew"], "heterogeneity": ["het_machine", "het_affinity"]}
# Label tie-break: cheaper first (measured pilot costs: static-key list heuristics < HEFT, which also computes ranks,
# < MINMIN, which is O(n^2 m)), then alphabetical within equal cost.
COST_ORDER = ["FCFS-EAT", "FCFS-EFT", "LPT-EFT", "SPT-EFT", "HEFT", "MINMIN"]
PORTFOLIO = COST_ORDER
DEPTHS = (1, 2, 3, 4)                    # max_depth <= 4 (ALGORITHM_DESIGN 5.3); "unlimited" is an ablation only
GUARD_MARGIN = 0.10                      # novelty guard: train range widened by 10% of its width on each side
CONTINGENCY_GAP = 0.02                   # 5.7: mean per-instance SBS/VBS - 1 on val below this triggers the GA member
METHODS = ("ADAPTIVE", "ADAPTIVE-NOGUARD", "ADAPTIVE-TOP2", "TRY-ALL", "RANDOM-SELECT")

# Contingency extension (ALGORITHM_DESIGN 5.7, EXPERIMENTAL_METHODOLOGY 7.4): a seventh member, S01's GA at 1,000 evals.
GA_MEMBER = "GA-1000"
GA_SETTINGS = {**ga.DEFAULTS, "max_evals": 1000}   # DEFAULTS equal the locked s01_final.toml [ga] values
GA_METHODS = ("ADAPTIVE-GA", "GA-1000")
THETAS = (0.0, 0.005, 0.01, 0.02, 0.05)
LABEL_SEED = 20261017
TIE = 1e-12


def features(inst: Instance) -> np.ndarray:
    """The nine workload features, O(e + n*m), computed before any scheduling. Order = FEATURES."""
    n, m = inst.n, inst.m
    if n == 0:
        return np.zeros(len(FEATURES))
    level = [0] * n
    for t in range(n):  # ids are topological
        level[t] = 1 + max((level[u] for u in inst.preds[t]), default=0)
    n_levels = max(level)
    mean = inst.cost.mean(axis=1)
    sd = mean.std()
    skew = float(((mean - mean.mean()) ** 3).mean() / sd ** 3) if sd > 0 else 0.0
    het_machine = float((inst.cost.std(axis=1) / mean).mean())
    fastest_overall = int(inst.cost.sum(axis=0).argmin())
    # ties count as "the overall fastest": on a homogeneous platform every processor is fastest
    affinity = float((inst.cost.min(axis=1) < inst.cost[:, fastest_overall] * (1 - TIE)).mean())
    ef = [0.0] * n
    w = mean.tolist()
    for t in range(n):
        ef[t] = w[t] + max((ef[u] for u in inst.preds[t]), default=0.0)
    return np.array([
        np.log(n),
        n / n_levels / m,                          # mean level width / m
        n_levels / n,
        sum(map(len, inst.preds)) / n,
        sd / mean.mean(),
        skew,
        max(ef) / (mean.sum() / m),
        het_machine,
        affinity,
    ])


def _require_split(insts, split: str) -> None:
    bad = {i.meta.get("split") for i in insts} - {split}
    if bad:
        raise ValueError(f"expected only {split!r} instances, got {sorted(map(str, bad))}")


def heuristic_table(insts) -> dict:
    """Features and the makespan of every portfolio heuristic, per instance (deterministic)."""
    X = np.array([features(i) for i in insts])
    C = np.array([[HEURISTICS[h](i, None)[0].makespan for h in PORTFOLIO] for i in insts])
    lb = np.array([bounds(i)["lower_bound"] for i in insts])
    return dict(X=X, C=C, lb=lb, hashes=[i.meta["hash"] for i in insts], labels_meta=[i.meta.get("label") for i in insts])


def labels(C: np.ndarray) -> np.ndarray:
    """Index of the lowest-makespan heuristic; ties go to the earlier (cheaper) entry of PORTFOLIO."""
    best = C.min(axis=1, keepdims=True)
    return (C <= best * (1 + TIE)).argmax(axis=1)


def _fit(X, C, depth, cols):
    y = labels(C)
    w = (C.max(axis=1) - C.min(axis=1)) / C.min(axis=1)  # instances where the choice matters count more
    if not (w > 0).any():
        w = np.ones(len(C))
    tree = DecisionTreeClassifier(max_depth=depth, random_state=0)
    tree.fit(X[:, cols], y, sample_weight=w)
    return tree


def _regret(tree, X, C, cols) -> np.ndarray:
    pick = tree.predict(X[:, cols])
    return C[np.arange(len(C)), pick] / C.min(axis=1) - 1


def train_selector(train_insts, val_insts) -> dict:
    """Fit the tree on `train`; choose depth, SBS and the contingency on `val`. Returns the model bundle."""
    _require_split(train_insts, "train")
    _require_split(val_insts, "val")
    tr, va = heuristic_table(train_insts), heuristic_table(val_insts)
    all_cols = list(range(len(FEATURES)))
    depth_table = {}
    for d in DEPTHS + (None,):
        r = _regret(_fit(tr["X"], tr["C"], d, all_cols), va["X"], va["C"], all_cols)
        depth_table["unlimited" if d is None else str(d)] = float(r.mean())
    depth = min(DEPTHS, key=lambda d: (round(depth_table[str(d)], 12), d))  # lowest val regret, then shallower
    tree = _fit(tr["X"], tr["C"], depth, all_cols)
    ablation = {}
    for g, names in GROUPS.items():
        cols = [k for k, f in enumerate(FEATURES) if f not in names]
        ablation[f"without_{g}"] = float(_regret(_fit(tr["X"], tr["C"], depth, cols), va["X"], va["C"], cols).mean())
    norm_val = va["C"] / va["lb"][:, None]
    val_rank = sorted(range(len(PORTFOLIO)), key=lambda k: (round(float(norm_val[:, k].mean()), 12), k))
    sbs_i = val_rank[0]
    gap = float((va["C"][:, sbs_i] / va["C"].min(axis=1) - 1).mean())
    lo, hi = tr["X"].min(axis=0), tr["X"].max(axis=0)
    return dict(
        tree=tree, depth=depth, portfolio=list(PORTFOLIO), features=list(FEATURES),
        guard_lo=lo - GUARD_MARGIN * (hi - lo), guard_hi=hi + GUARD_MARGIN * (hi - lo),
        sbs=PORTFOLIO[sbs_i], val_rank=[PORTFOLIO[k] for k in val_rank], train_hashes=tr["hashes"], val_hashes=va["hashes"],
        report=dict(
            train_instances=len(train_insts), val_instances=len(val_insts), depth=depth,
            val_mean_regret_by_depth=depth_table, val_mean_regret_feature_ablation=ablation,
            val_mean_regret_adaptive=depth_table[str(depth)],
            sbs=PORTFOLIO[sbs_i], val_mean_cmax_over_lb={h: float(norm_val[:, k].mean()) for k, h in enumerate(PORTFOLIO)},
            val_sbs_vbs_gap=gap, contingency_threshold=CONTINGENCY_GAP, contingency_triggered=gap < CONTINGENCY_GAP,
            train_label_counts={h: int((labels(tr["C"]) == k).sum()) for k, h in enumerate(PORTFOLIO)},
            val_label_counts={h: int((labels(va["C"]) == k).sum()) for k, h in enumerate(PORTFOLIO)},
            guard_margin=GUARD_MARGIN, rules=export_text(tree, feature_names=FEATURES),
        ))


def save(bundle: dict, out_dir) -> str:
    """Write the model directory once (never overwritten). Returns model_id = sha256 prefix of selector.pkl.
    Measured timings (bundle['timings']) go to model.json only, so the id depends on the training data alone."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True)
    timings = bundle.get("timings", {})
    blob = pickle.dumps({k: v for k, v in bundle.items() if k != "timings"})
    (out_dir / "selector.pkl").write_bytes(blob)
    model_id = hashlib.sha256(blob).hexdigest()[:16]
    (out_dir / "train_hashes.txt").write_text("\n".join(bundle["train_hashes"]) + "\n")
    (out_dir / "val_hashes.txt").write_text("\n".join(bundle["val_hashes"]) + "\n")
    (out_dir / "model.json").write_text(json.dumps(dict(model_id=model_id, **bundle["report"], measured=timings), indent=2))
    for f in out_dir.iterdir():
        f.chmod(0o444)
    return model_id


def load(model_dir) -> tuple[dict, str]:
    """Load a bundle we wrote ourselves (pickle is only ever read from our own model directories)."""
    blob = (Path(model_dir) / "selector.pkl").read_bytes()
    return pickle.loads(blob), hashlib.sha256(blob).hexdigest()[:16]


def assert_no_leakage(bundle: dict, inst: Instance) -> None:
    """Refuse instances the model learned from, and refuse test instances that were used for model selection."""
    h = inst.meta.get("hash")
    if h in set(bundle["train_hashes"]):
        raise ValueError(f"instance {inst.id} is in the selector's training set")
    if inst.meta.get("split", "").startswith("test") and h in set(bundle["val_hashes"]):
        raise ValueError(f"test instance {inst.id} was used for model selection")


def select(bundle: dict, inst: Instance, guard: bool = True, k: int = 1) -> dict:
    """Decision only: features -> guard -> tree. Returns the chosen heuristic(s) and whether the guard fired."""
    x = features(inst)
    novel = bool(((x < bundle["guard_lo"]) | (x > bundle["guard_hi"])).any())
    if guard and novel:
        picks = bundle["val_rank"][:k]  # SBS first, then the next best fixed policies on val
        return dict(picks=picks, fallback=True, novel=novel, x=x)
    proba = bundle["tree"].predict_proba(x[None, :])[0]
    classes = list(bundle["tree"].classes_)
    order = sorted(range(len(classes)), key=lambda j: (-proba[j], classes[j]))  # ties: cheaper heuristic
    picks = [bundle["portfolio"][classes[j]] for j in order[:k]]
    for h in bundle["portfolio"]:  # a tree may have seen fewer than k classes
        if len(picks) >= k:
            break
        if h not in picks:
            picks.append(h)
    return dict(picks=picks, fallback=False, novel=novel, x=x)


def run_member(name: str, inst: Instance, rng=None):
    """Run one portfolio member. GA-1000 without an rng uses the fixed labelling stream of this instance."""
    if name != GA_MEMBER:
        return HEURISTICS[name](inst, None)
    if rng is None:
        rng = np.random.default_rng(np.random.SeedSequence([LABEL_SEED, int(inst.meta["hash"][:8], 16)]))
    s, info = ga.optimize(inst, rng, "GA", **GA_SETTINGS)
    return s, dict(fitness_evals=info["fitness_evals"])   # no trace: ga_trace.csv is for S01 runs only


def ga_table(insts) -> dict:
    """GA-1000 makespan (labelling stream) and measured seconds per instance."""
    C, T = [], []
    for i in insts:
        t0 = time.perf_counter()
        C.append(run_member(GA_MEMBER, i)[0].makespan)
        T.append(time.perf_counter() - t0)
    return dict(C=np.array(C), T=np.array(T))


def theta_labels(C6: np.ndarray, cga: np.ndarray, theta: float) -> np.ndarray:
    """Index into PORTFOLIO + [GA_MEMBER]: GA (6) where it beats the best heuristic by more than theta."""
    y = labels(C6)
    return np.where(cga < (1 - theta) * C6.min(axis=1), len(PORTFOLIO), y)


def train_selector_ga(train_insts, val_insts, base: dict, base_model_id: str) -> dict:
    """The contingency extension: same features, guard, SBS and splits as `base`; GA-1000 as a seventh member,
    theta-labels on `train`, depth per theta and theta itself chosen on `val` (EXPERIMENTAL_METHODOLOGY 7.4)."""
    _require_split(train_insts, "train")
    _require_split(val_insts, "val")
    tr, va = heuristic_table(train_insts), heuristic_table(val_insts)
    if tr["hashes"] != base["train_hashes"] or va["hashes"] != base["val_hashes"]:
        raise ValueError("extension must use exactly the base selector's train and val instances")
    gtr, gva = ga_table(train_insts), ga_table(val_insts)
    C7tr, C7va = np.column_stack([tr["C"], gtr["C"]]), np.column_stack([va["C"], gva["C"]])
    cols, rows_va = list(range(len(FEATURES))), np.arange(len(va["C"]))
    vbs_va = va["C"].min(axis=1)
    sbs_regret = float((va["C"][:, PORTFOLIO.index(base["sbs"])] / vbs_va - 1).mean())
    table, fits = {}, {}
    for theta in THETAS:
        y, yv = theta_labels(tr["C"], gtr["C"], theta), theta_labels(va["C"], gva["C"], theta)
        w = (C7tr.max(axis=1) - C7tr.min(axis=1)) / C7tr.min(axis=1)
        by_depth = {}
        for d in DEPTHS:
            tree = DecisionTreeClassifier(max_depth=d, random_state=0).fit(tr["X"], y, sample_weight=w)
            pick = tree.predict(va["X"])
            by_depth[d] = (float((C7va[rows_va, pick] / C7va[rows_va, yv] - 1).mean()), tree, pick)
        depth = min(DEPTHS, key=lambda d: (round(by_depth[d][0], 12), d))
        _, tree, pick = by_depth[depth]
        regret = float((C7va[rows_va, pick] / vbs_va - 1).mean())
        calls = int((pick == len(PORTFOLIO)).sum())
        eff = (sbs_regret - regret) / calls if calls and sbs_regret > regret else None
        fits[theta] = tree
        table[str(theta)] = dict(depth=depth, train_ga_labels=int((y == len(PORTFOLIO)).sum()),
                                 val_ga_labels=int((yv == len(PORTFOLIO)).sum()), val_ga_calls=calls,
                                 val_mean_regret_vs_vbs6=regret, ga_call_efficiency=eff,
                                 val_regret_by_depth={str(k): v[0] for k, v in by_depth.items()})
    ok = [t for t in THETAS if table[str(t)]["ga_call_efficiency"] is not None]
    theta = max(ok, key=lambda t: (round(table[str(t)]["ga_call_efficiency"], 12), t)) if ok else None
    tree = fits[theta] if theta is not None else None
    report = dict(
        extension_of=base_model_id, trigger=dict(rule="val SBS-VBS gap < 2% (ALGORITHM_DESIGN 5.7)",
                                                        val_sbs_vbs_gap=sbs_regret, triggered=sbs_regret < CONTINGENCY_GAP),
        ga_member=GA_MEMBER, ga_settings={k: list(v) if isinstance(v, tuple) else v for k, v in GA_SETTINGS.items()},
        thetas=list(THETAS), theta=theta, theta_table=table, sbs=base["sbs"],
        val_sbs_regret_vs_vbs6=sbs_regret,
        val_ga_gain_over_best_heuristic=dict(mean=float((1 - gva["C"] / vbs_va).mean()),
                                             share_strictly_better=float((gva["C"] < vbs_va * (1 - TIE)).mean())),
        rules=export_text(tree, feature_names=FEATURES) if tree is not None else "GA never selected",
        class_names=[(PORTFOLIO + [GA_MEMBER])[c] for c in tree.classes_] if tree is not None else [],
    )
    return dict(base, tree=tree if tree is not None else base["tree"], theta=theta, depth=table[str(theta)]["depth"]
                if theta is not None else base["depth"], portfolio=PORTFOLIO + [GA_MEMBER], report=report,
                never_ga=theta is None,
                timings=dict(ga_time_s_median_train=float(np.median(gtr["T"])),   # measured: kept out of model_id
                             ga_time_s_median_val=float(np.median(gva["T"]))))


def schedule(inst: Instance, rng, method: str, bundle: dict):
    """Scheduler entry point for the runner: (Schedule, info). info['decision'] goes to decisions.csv."""
    if method not in METHODS + GA_METHODS:
        raise ValueError(f"unknown S03 method {method!r}")
    assert_no_leakage(bundle, inst)
    t0 = time.perf_counter()
    if method == "TRY-ALL":  # no decision: runs everything, so no features are computed
        picks, d = list(PORTFOLIO), dict(fallback=False, novel=False, x=None)
    elif method == "GA-1000":  # fixed policy: always call the optimiser
        picks, d = [GA_MEMBER], dict(fallback=False, novel=False, x=None)
    elif method == "RANDOM-SELECT":
        picks, d = [PORTFOLIO[int(rng.integers(len(PORTFOLIO)))]], dict(fallback=False, novel=False, x=None)
    else:
        d = select(bundle, inst, guard=method != "ADAPTIVE-NOGUARD", k=2 if method == "ADAPTIVE-TOP2" else 1)
        picks = d["picks"]
    decision_time = time.perf_counter() - t0
    if inst.n == 0:
        return ScheduleBuilder(inst).schedule(), dict(decision_time_s=decision_time, decision_count=0,
                                                      decision=dict(selected=picks[0], candidates=picks, **d))
    runs = [(run_member(h, inst, rng), h) for h in picks]
    (best, info), chosen = min(runs, key=lambda r: (r[0][0].makespan, picks.index(r[1])))  # ties: earlier pick
    return best, dict(decision_time_s=decision_time, decision_count=len(picks), **info,
                      decision=dict(selected=chosen, candidates=picks, fallback=d["fallback"], novel=d["novel"],
                                    x=d["x"]))
