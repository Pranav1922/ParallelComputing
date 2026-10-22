"""Independent integrity check of the frozen S01 final campaign, and recomputation of its headline statistics
from runs.csv without schedlab.analysis. Read-only: writes only the JSON report named on the command line.

    python3 provenance/s01_final/verify_campaign.py results/raw/<campaign> results/derived/<campaign> out.json
"""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from schedlab.heuristics import HEURISTICS
from schedlab.runner import RAW_COLUMNS, _short_hash, build_schedulers
from schedlab.workloads import experiment_matrix

raw_dir, derived_dir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
cfg = tomllib.loads(Path("configs/s01_final.toml").read_text())
manifest = json.loads((raw_dir / "manifest.json").read_text())
text = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
raw = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
res, problems = {}, []


def need(cond, msg):
    if not cond:
        problems.append(msg)


# ---- identity of config and manifest ----
need(manifest["config"] == cfg, "manifest config differs from configs/s01_final.toml")
need(manifest["config_hash"] == _short_hash(cfg), "config hash mismatch")
need(list(text.columns) == RAW_COLUMNS, "header differs")
need(not (text == "").any().any(), "blank cells")

# ---- expected matrix ----
matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
insts = [i for s in cfg["run"]["splits"] for i in matrix[s]]
algos = cfg["run"]["algorithms"]
scheds = build_schedulers(cfg)
seeded = {a for a in algos if len(scheds[a]) > 3}
per_inst = sum(len(cfg["ga"]["seeds"]) if a in seeded else cfg["run"]["timing_repeats"] for a in algos)
res["expected_rows"] = len(insts) * per_inst
res["actual_rows"] = len(raw)
res["instances_expected"], res["instances_actual"] = len(insts), raw.instance_hash.nunique()
res["rows_per_instance"] = per_inst
need(len(raw) == res["expected_rows"], "row count differs from the expected matrix")
need(manifest["row_count"] == len(raw), "manifest row_count differs")
need(manifest["failed_count"] == int((raw.status != "ok").sum()), "manifest failed_count differs")
need(raw.run_uid.is_unique, "duplicate run_uid")
need(not raw.duplicated(["instance_hash", "algorithm", "run_id"]).any(), "duplicate (instance, algorithm, run_id)")
exp = pd.DataFrame([dict(instance_hash=i.meta["hash"], instance_id=i.id, problem_size=i.n, resource_count=i.m,
                         split=i.meta["split"], workload_class=i.meta["label"]) for i in insts]).set_index("instance_hash")
got = raw.groupby("instance_hash")[["instance_id", "problem_size", "resource_count", "split", "workload_class"]].first()
need(set(got.index) == set(exp.index), "instance set differs from the experiment matrix")
need(got.reindex(exp.index).astype(str).equals(exp.astype(str)), "instance metadata differs from the matrix")
need(set(raw.split) == {"test_id", "test_ood"}, "unexpected split in runs.csv")
for a in algos:
    sub = raw[raw.algorithm == a]
    reps = sub.groupby("instance_hash").run_id.apply(lambda x: tuple(sorted(x)))
    need(len(sub) == len(insts) * 3 and (reps == (0, 1, 2)).all(), f"{a}: not 3 rows per instance")
    if a in seeded:
        need((sub.groupby("instance_hash").algo_seed.apply(lambda x: tuple(sorted(x))) == (0, 1, 2)).all(), f"{a}: seeds")
    else:
        need(sub.algo_seed.isna().all(), f"{a}: deterministic algorithm has a seed")
    need(sub.algo_config_hash.astype(str).eq(_short_hash(scheds[a][2])).all(), f"{a}: config hash not the locked one")
res["status_counts"] = raw.status.value_counts().to_dict()
res["status_by_algorithm"] = raw.groupby(["algorithm", "status"]).size().unstack(fill_value=0).to_dict("index")
ok = raw[raw.status == "ok"]
need((ok.valid == 1).all(), "ok row not valid")
s01 = ok[ok.sub_problem == "S01"]
need((s01.fitness_evals == cfg["ga"]["max_evals"]).all(), "an S01 run did not use exactly max_evals")
res["s01_fitness_evals_values"] = sorted(s01.fitness_evals.unique().tolist())

# ---- heuristics re-run from scratch: makespans must match raw exactly (deterministic) ----
mism = 0
for inst in insts:
    for h in HEURISTICS:
        c = HEURISTICS[h](inst, None)[0].makespan
        r = ok[(ok.instance_hash == inst.meta["hash"]) & (ok.algorithm == h)].makespan_sim
        mism += int(not (r == c).all())
res["heuristic_rerun_mismatches"] = mism
need(mism == 0, "heuristic re-run differs from raw makespan")

# ---- headline statistics recomputed directly from raw ----
per = ok.groupby(["instance_hash", "algorithm"]).makespan_sim.mean().unstack()
per["BEST-HEURISTIC"] = per[list(HEURISTICS)].min(axis=1)
split = ok.groupby("instance_hash").split.first()
paired = pd.read_csv(derived_dir / "s01_paired.csv")
rows = []
for scope in ["test_id", "test_ood", "all"]:
    p = per if scope == "all" else per[split.reindex(per.index) == scope]
    for a in ["GA", "GA-KEYS-EFT", "HILL-CLIMB", "RANDOM-SEARCH", "GA-UNSEEDED"]:
        for b in ["FCFS-EAT", "HEFT", "BEST-HEURISTIC"]:
            imp, ratio = (p[b] - p[a]) / p[b], p[a] / p[b]
            r = paired[(paired.algorithm == a) & (paired.baseline == b) & (paired.split == scope)].iloc[0]
            same = np.isclose(r.improvement_mean, imp.mean(), rtol=0, atol=1e-12) and r.instances == len(imp)
            same &= (r.better, r.tie, r.worse) == (int((ratio < 1 - 1e-12).sum()), int((abs(ratio - 1) <= 1e-12).sum()),
                                                     int((ratio > 1 + 1e-12).sum()))
            need(same, f"s01_paired.csv differs from raw recomputation: {a} vs {b} on {scope}")
            rows.append(dict(scope=scope, algorithm=a, baseline=b, n=len(imp), mean_paired_improvement=imp.mean()))
    d = p["GA"] - p["BEST-HEURISTIC"]
    res[f"wilcoxon_GA_vs_BEST_HEURISTIC_{scope}"] = dict(
        n=int(len(d)), n_nonzero=int((d != 0).sum()),
        p=float(wilcoxon(p["GA"], p["BEST-HEURISTIC"], zero_method="wilcox").pvalue))
    need(np.isclose(paired[(paired.algorithm == "GA") & (paired.baseline == "BEST-HEURISTIC")
                           & (paired.split == scope)].wilcoxon_p.iloc[0], res[f"wilcoxon_GA_vs_BEST_HEURISTIC_{scope}"]["p"],
                    rtol=1e-9), f"wilcoxon p differs on {scope}")
res["recomputed"] = rows
res["ratio_of_aggregate_means_GA_vs_FCFS_all_NOT_A_PAIRED_STATISTIC"] = float(
    1 - (per.GA / per.index.map(ok.groupby("instance_hash").lower_bound_sim.first())).mean()
    / (per["FCFS-EAT"] / per.index.map(ok.groupby("instance_hash").lower_bound_sim.first())).mean())
res["problems"] = problems
out.write_text(json.dumps(res, indent=2, default=str))
print(json.dumps({k: v for k, v in res.items() if k not in ("recomputed", "status_by_algorithm")}, indent=2, default=str))
sys.exit(1 if problems else 0)
