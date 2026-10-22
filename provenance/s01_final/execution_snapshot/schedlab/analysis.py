"""Derived metrics, the manual's 19-column CSV, summary table, figure, and campaign checks.

Everything here is recomputed from the raw directory. Makespan is simulated (sim_tu); scheduling
time is measured (seconds). They are never added together.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .runner import RAW_COLUMNS

MANUAL_COLUMNS = [
    "Student_ID", "Batch_ID", "Workload", "Dataset", "Problem_Size", "Algorithm", "Parallel_Model", "Hardware",
    "Resource_Count", "Threads", "Execution_Time", "Speedup", "Efficiency", "Communication_Time",
    "Synchronization_Time", "Scheduling_Time", "Memory_Use", "Energy_if_available", "Run_ID",
]
SPEEDUP_BASELINE = "serial execution of all tasks on the best single simulated processor"
PLACEHOLDER = "UNCONFIRMED"
_INT = ["decision_count", "fitness_evals", "peak_rss_kb", "valid", "algo_seed"]
_KEY = ["instance_hash", "algorithm"]


def load_raw(raw_dir) -> tuple[pd.DataFrame, dict]:
    raw_dir = Path(raw_dir)
    # "NA" is read as missing. round_trip: pandas' default float parser can be off by one ulp.
    raw = pd.read_csv(raw_dir / "runs.csv", dtype={c: "Int64" for c in _INT}, float_precision="round_trip")
    return raw, json.loads((raw_dir / "manifest.json").read_text())


def derive(raw: pd.DataFrame, manifest: dict, identity: dict) -> pd.DataFrame:
    """One row per raw row: the manual's 19 columns, then extras. Failed rows keep NA measurements."""
    ok = raw[raw.status == "ok"]
    per_inst = ok.groupby(_KEY).makespan_sim.mean().unstack("algorithm")  # repeats -> instance
    ref = pd.DataFrame(index=per_inst.index)
    ref["fcfs"] = per_inst["FCFS-EAT"] if "FCFS-EAT" in per_inst else np.nan
    ref["heft"] = per_inst["HEFT"] if "HEFT" in per_inst else np.nan
    heuristics = raw.loc[raw.sub_problem == "BASE", "algorithm"].unique()
    ref["best"] = per_inst[[c for c in per_inst.columns if c in heuristics]].min(axis=1)
    ref = ref.reindex(raw.instance_hash).reset_index(drop=True)

    cmax = raw.makespan_sim
    speedup = raw.serial_best_sim / cmax
    m = pd.DataFrame({
        "Student_ID": raw.sub_problem.map(identity["student_id"]),
        "Batch_ID": identity["batch_id"],
        "Workload": raw.workload_class,
        "Dataset": raw.instance_id,
        "Problem_Size": raw.problem_size,
        "Algorithm": raw.algorithm,
        "Parallel_Model": "SIM-LIST-SCHED",
        "Hardware": "SIM:" + raw.platform,
        "Resource_Count": raw.resource_count,
        "Threads": raw.threads,
        "Execution_Time": cmax,                 # simulated time units, see Time_Unit
        "Speedup": speedup,
        "Efficiency": speedup / raw.resource_count,
        "Communication_Time": np.nan,           # not modelled -> NA
        "Synchronization_Time": np.nan,         # not modelled -> NA
        "Scheduling_Time": raw.scheduling_time_s,  # measured seconds
        "Memory_Use": raw.peak_rss_kb,
        "Energy_if_available": np.nan,
        "Run_ID": raw.run_uid,
        # extras
        "Time_Unit": raw.time_unit,
        "Scheduling_Time_Unit": "s",
        "Speedup_Baseline": SPEEDUP_BASELINE,
        "Sub_Problem": raw.sub_problem,
        "Split": raw.split,
        "Platform": raw.platform,
        "Algo_Seed": raw.algo_seed,
        "Repeat": raw.run_id,
        "Instance_Hash": raw.instance_hash,
        "Lower_Bound": raw.lower_bound_sim,
        "Norm_Makespan": cmax / raw.lower_bound_sim,
        "Utilization": raw.busy_time_sim / (raw.resource_count * cmax),
        "Improvement_vs_FCFS": (ref.fcfs - cmax) / ref.fcfs,
        "Improvement_vs_HEFT": (ref.heft - cmax) / ref.heft,
        "Improvement_vs_BestHeuristic": (ref.best - cmax) / ref.best,
        "Regret_vs_VBS": cmax / ref.best - 1,
        "Decision_Time": raw.decision_time_s,
        "Fitness_Evals": raw.fitness_evals,
        "Host_Hardware": raw.hardware_id,
        "Status": raw.status,
        "Error": raw.error_msg,
    })
    # Outliers are flagged, never removed: scheduling time beyond Q3 + 3*IQR within its group.
    g = m.groupby(["Algorithm", "Problem_Size", "Resource_Count"]).Scheduling_Time
    q1, q3 = g.transform(lambda x: x.quantile(0.25)), g.transform(lambda x: x.quantile(0.75))
    m["Timing_Outlier"] = (m.Scheduling_Time > q3 + 3 * (q3 - q1)).astype(int)
    assert list(m.columns[:19]) == MANUAL_COLUMNS and len(m) == len(raw)
    return m


def summarize(master: pd.DataFrame) -> pd.DataFrame:
    """Per algorithm. Repeats and algorithm seeds are averaged per instance first; the instance is the unit."""
    ok = master[master.Status == "ok"]
    inst = ok.groupby(["Algorithm", "Instance_Hash"]).agg(
        norm=("Norm_Makespan", "mean"), speedup=("Speedup", "mean"), eff=("Efficiency", "mean"),
        util=("Utilization", "mean"), imp=("Improvement_vs_FCFS", "mean"), regret=("Regret_vs_VBS", "mean"),
        imp_heft=("Improvement_vs_HEFT", "mean"), imp_best=("Improvement_vs_BestHeuristic", "mean"),
        evals=("Fitness_Evals", "mean"),
        t=("Scheduling_Time", "median"), t_cv=("Scheduling_Time", lambda x: x.std() / x.mean()))
    out = inst.groupby("Algorithm").agg(**{
        "instances": ("norm", "size"), "cmax_over_lb_mean_of_instances": ("norm", "mean"),
        "cmax_over_lb_median_of_instances": ("norm", "median"),
        "speedup_mean": ("speedup", "mean"), "efficiency_mean": ("eff", "mean"), "utilization_mean": ("util", "mean"),
        "paired_impr_vs_FCFS-EAT_mean": ("imp", "mean"), "paired_impr_vs_HEFT_mean": ("imp_heft", "mean"),
        "paired_impr_vs_best_heuristic_mean": ("imp_best", "mean")},
        beats_best_heuristic=("imp_best", lambda x: int((x > 1e-12).sum())),
        ties_best_heuristic=("imp_best", lambda x: int((x.abs() <= 1e-12).sum())),
        fitness_evals=("evals", "mean"), regret_vs_vbs_mean=("regret", "mean"),
        sched_time_s_median=("t", "median"), sched_time_s_max=("t", "max"), sched_time_cv_median=("t_cv", "median"))
    # Column names say how each value was aggregated (DATA_SCHEMA.md 4.1):
    #   cmax_over_lb_*_of_instances: mean/median over instances of the per-instance Cmax/LB.
    #   paired_impr_vs_X_mean: mean over instances of (Cmax_X - Cmax_alg) / Cmax_X, same instance both sides.
    # A ratio of the aggregate Cmax/LB means is a different statistic and is not reported.
    out["rows_not_ok"] = master[master.Status != "ok"].groupby("Algorithm").size().reindex(out.index, fill_value=0)
    out["timing_outliers"] = master.groupby("Algorithm").Timing_Outlier.sum().reindex(out.index, fill_value=0)
    return out.reset_index()


S01_METHODS = ["GA", "GA-KEYS-EFT", "HILL-CLIMB", "RANDOM-SEARCH", "GA-UNSEEDED"]
BASELINES = ["FCFS-EAT", "HEFT", "BEST-HEURISTIC"]
BEST_OF_3 = "GA-BEST-OF-SEEDS"
BOOT, BOOT_SEED, TIE = 10_000, 20261017, 1e-12


def per_instance(master: pd.DataFrame) -> pd.DataFrame:
    """Instance x algorithm table of simulated makespan, the mean over repeats or algorithm seeds (the primary
    value). Adds BEST-HEURISTIC (per-instance minimum of the six heuristics) and, when GA ran, GA-BEST-OF-SEEDS
    (per-instance minimum over GA's seeds, which costs the sum of their optimization times)."""
    ok = master[master.Status == "ok"]
    per = ok.groupby(["Instance_Hash", "Algorithm"]).Execution_Time.mean().unstack("Algorithm")
    per["BEST-HEURISTIC"] = per[sorted(set(ok.loc[ok.Sub_Problem == "BASE", "Algorithm"]))].min(axis=1)
    if "GA" in per:
        per[BEST_OF_3] = ok[ok.Algorithm == "GA"].groupby("Instance_Hash").Execution_Time.min()
    return per


def paired_stats(alg, base, rng=None) -> dict:
    """Paired statistics of r_i = Cmax_alg,i / Cmax_base,i over instances i present on both sides.

    ratio_mean        mean_i r_i                     (improvement_mean = 1 - ratio_mean
                                                       = mean_i (Cmax_base,i - Cmax_alg,i) / Cmax_base,i)
    ratio_geomean     exp(mean_i ln r_i)             (improvement_geomean = 1 - ratio_geomean)
    ratio_ci95_*      percentile bootstrap of ratio_mean, BOOT resamples of instances, fixed seed
    better/tie/worse  r_i < 1, |r_i - 1| <= 1e-12, r_i > 1 (better = alg has the shorter makespan)
    """
    r = (pd.Series(alg) / pd.Series(base)).dropna().to_numpy()
    if not len(r):
        return dict(instances=0)
    rng = rng or np.random.default_rng(BOOT_SEED)
    boot = r[rng.integers(len(r), size=(BOOT, len(r)))].mean(axis=1)
    return dict(instances=len(r), ratio_mean=r.mean(), ratio_median=np.median(r), ratio_q25=np.quantile(r, 0.25),
                ratio_q75=np.quantile(r, 0.75), ratio_min=r.min(), ratio_max=r.max(),
                ratio_ci95_lo=np.quantile(boot, 0.025), ratio_ci95_hi=np.quantile(boot, 0.975),
                ratio_geomean=float(np.exp(np.log(r).mean())), improvement_mean=1 - r.mean(),
                improvement_geomean=1 - float(np.exp(np.log(r).mean())),
                better=int((r < 1 - TIE).sum()), tie=int((np.abs(r - 1) <= TIE).sum()), worse=int((r > 1 + TIE).sum()))


def s01_paired(master: pd.DataFrame) -> pd.DataFrame:
    """Paired comparison table (methodology 5.1), per split and over all splits.
    Rows: every S01 method and GA-BEST-OF-SEEDS against FCFS-EAT, HEFT and BEST-HEURISTIC, and GA against each
    other S01 method. GA against its seed heuristics (HEFT, MINMIN, FCFS-EAT) cannot be worse, by construction:
    that is not evidence. Wilcoxon signed-rank (paired makespans, ties dropped) only for the predeclared primary
    comparison, GA vs BEST-HEURISTIC; it is one of three primary tests across S01-S03 that get a Holm correction,
    so at alpha = 0.05 it is significant after correction for certain only if p < 0.05 / 3."""
    from scipy.stats import wilcoxon
    per = per_instance(master)
    if "GA" not in per:
        return pd.DataFrame()
    split = master.groupby("Instance_Hash").Split.first()
    pairs = [(a, b) for a in S01_METHODS + [BEST_OF_3] if a in per for b in BASELINES]
    pairs += [("GA", b) for b in S01_METHODS[1:] if b in per]
    rows = []
    scopes = sorted(split.unique())
    for scope in scopes + (["all"] if len(scopes) > 1 else []):
        p = per if scope == "all" else per[split.reindex(per.index) == scope]
        for a, b in pairs:
            row = dict(algorithm=a, baseline=b, split=scope, **paired_stats(p[a], p[b]))
            row["wilcoxon_p"] = np.nan
            if (a, b) == ("GA", "BEST-HEURISTIC"):
                d = (p[a] - p[b]).dropna()
                if (d != 0).any():
                    row["wilcoxon_p"] = wilcoxon(p[a][d.index], p[b][d.index], zero_method="wilcox").pvalue
            rows.append(row)
    return pd.DataFrame(rows)


def s01_overhead_quality(master: pd.DataFrame) -> pd.DataFrame:
    """Per S01 method and problem size: measured optimization time (s) next to simulated quality (sim_tu).
    The two are never combined, except in the explicitly hypothetical column:
      tau_star_i = (T_alg,i - T_HEFT,i) / (Cmax_HEFT,i - Cmax_alg,i)   [seconds per simulated time unit]
    the conversion factor at which the extra optimization time would equal the simulated saving on instance i.
    It is defined only where alg is strictly better than HEFT; no real value of the conversion factor is known."""
    ok = master[master.Status == "ok"]
    per = per_instance(master)
    if "GA" not in per:
        return pd.DataFrame()
    t = ok.groupby(["Instance_Hash", "Algorithm"]).Scheduling_Time.agg(["mean", "sum"])
    t_alg = t["mean"].unstack("Algorithm")
    t_alg[BEST_OF_3] = t["sum"].unstack("Algorithm")["GA"]  # best of seeds is charged every seed's time
    size = ok.groupby("Instance_Hash").Problem_Size.first()
    rows = []
    for a in [x for x in S01_METHODS + [BEST_OF_3] if x in per]:
        for n in sorted(size.unique()):
            idx = size.index[size == n]
            gain = per.loc[idx, "HEFT"] - per.loc[idx, a]
            tau = ((t_alg.loc[idx, a] - t_alg.loc[idx, "HEFT"]) / gain)[gain > TIE * per.loc[idx, "HEFT"]]
            rows.append({"algorithm": a, "problem_size": n, "instances": len(idx),
                         "opt_time_s_median": t_alg.loc[idx, a].median(),
                         "heft_time_s_median": t_alg.loc[idx, "HEFT"].median(),
                         "time_ratio_vs_HEFT_median": (t_alg.loc[idx, a] / t_alg.loc[idx, "HEFT"]).median(),
                         "paired_impr_vs_HEFT_mean": 1 - (per.loc[idx, a] / per.loc[idx, "HEFT"]).mean(),
                         "paired_impr_vs_best_heuristic_mean": 1 - (per.loc[idx, a] / per.loc[idx, "BEST-HEURISTIC"]).mean(),
                         "share_better_than_HEFT": len(tau) / len(idx),
                         "HYPOTHETICAL_tau_star_s_per_tu_median": tau.median() if len(tau) else np.nan})
    return pd.DataFrame(rows)


def timing_by_size(master: pd.DataFrame) -> pd.DataFrame:
    ok = master[master.Status == "ok"]
    return (ok.groupby(["Algorithm", "Problem_Size"]).Scheduling_Time.agg(["median", "min", "max", "count"])
            .rename(columns=lambda c: f"sched_time_s_{c}" if c != "count" else "rows").reset_index())


def figure_data(master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """G1 data: per-instance normalised makespan, and its median and quartiles per plotted point."""
    keys = ["Workload", "Resource_Count", "Problem_Size", "Algorithm"]
    ok = master[master.Status == "ok"]
    inst = ok.groupby(keys + ["Instance_Hash"]).Norm_Makespan.mean().reset_index()  # repeats/seeds -> instance
    summary = inst.groupby(keys).Norm_Makespan.agg(
        median="median", q25=lambda x: x.quantile(0.25), q75=lambda x: x.quantile(0.75), count="size").reset_index()
    return inst, summary


def figure_makespan_vs_size(master: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """G1: problem size vs normalised makespan. One panel per workload class x processor count, one line
    per algorithm, median with interquartile range over instances. Classes are never pooled.
    Saved as PDF and SVG, plus CSVs of the per-instance values and of the plotted summary."""
    inst, data = figure_data(master)
    inst.to_csv(out_dir / "g1_makespan_vs_size_instances.csv", index=False, na_rep="NA")
    data.to_csv(out_dir / "g1_makespan_vs_size.csv", index=False, na_rep="NA")
    classes, procs = sorted(data.Workload.unique()), sorted(data.Resource_Count.unique())
    algos, sizes = sorted(data.Algorithm.unique()), sorted(data.Problem_Size.unique())
    fig, axes = plt.subplots(len(classes), len(procs), figsize=(4.2 * len(procs), 2.9 * len(classes)),
                             sharex=True, sharey="row", squeeze=False)
    for r, cls in enumerate(classes):
        for c, m in enumerate(procs):
            ax = axes[r][c]
            cell = data[(data.Workload == cls) & (data.Resource_Count == m)]
            for i, algo in enumerate(algos):
                d = cell[cell.Algorithm == algo]
                x = d.Problem_Size * (1 + 0.012 * (i - (len(algos) - 1) / 2))  # dodge so intervals do not overlap
                ax.errorbar(x, d["median"], yerr=[d["median"] - d.q25, d.q75 - d["median"]], marker="o",
                            markersize=3, linewidth=1, capsize=2, label=algo, color=plt.cm.tab20(i % 20))
            ax.axhline(1.0, color="grey", linestyle=":", linewidth=0.8)   # the lower bound
            ax.set_xscale("log")
            ax.set_xticks(sizes, [str(s) for s in sizes])
            ax.set_xlim(min(sizes) * 0.8, max(sizes) * 1.25)
            ax.minorticks_off()
            ax.set_title(f"{cls}, {m} simulated processors", fontsize=9)
            if r == len(classes) - 1:
                ax.set_xlabel("Problem size (tasks)")
            if c == 0:
                ax.set_ylabel("Simulated makespan / lower bound")
    axes[0][-1].legend(fontsize=6, ncol=2)
    fig.suptitle("Simulated schedule quality (not measured execution time); median and interquartile range "
                 "over instances", fontsize=9)
    fig.tight_layout()
    for ext in ("pdf", "svg"):
        fig.savefig(out_dir / f"g1_makespan_vs_size.{ext}")
    plt.close(fig)
    return data


def _save(fig, out_dir: Path, stem: str) -> None:
    fig.tight_layout()
    for ext in ("pdf", "svg"):
        fig.savefig(out_dir / f"{stem}.{ext}")
    plt.close(fig)


def _iqr(x: pd.Series, keys: list) -> pd.DataFrame:
    return x.groupby(keys).agg(median="median", q25=lambda v: v.quantile(0.25), q75=lambda v: v.quantile(0.75),
                               mean="mean", count="size").reset_index()


def figure_opt_time_vs_size(master: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """G2a: measured optimization time (seconds, log) vs problem size, one panel per processor count, median and
    IQR over runs (each algorithm seed is a run). Pooled over classes and splits at equal (n, m)."""
    ok = master[(master.Status == "ok") & master.Algorithm.isin(S01_METHODS + ["HEFT", "MINMIN"])]
    runs = ok[["Run_ID", "Split", "Workload", "Instance_Hash", "Resource_Count", "Problem_Size", "Algorithm",
               "Algo_Seed", "Repeat", "Scheduling_Time", "Fitness_Evals"]]
    runs.to_csv(out_dir / "g2_opt_time_vs_size_runs.csv", index=False, na_rep="NA")
    data = _iqr(runs.set_index(["Resource_Count", "Problem_Size", "Algorithm"]).Scheduling_Time,
                ["Resource_Count", "Problem_Size", "Algorithm"])
    data.to_csv(out_dir / "g2_opt_time_vs_size.csv", index=False, na_rep="NA")
    procs, algos = sorted(data.Resource_Count.unique()), [a for a in S01_METHODS + ["HEFT", "MINMIN"]
                                                            if a in set(data.Algorithm)]
    fig, axes = plt.subplots(1, len(procs), figsize=(3.6 * len(procs), 3.2), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], procs):
        for i, a in enumerate(algos):
            d = data[(data.Resource_Count == m) & (data.Algorithm == a)]
            ax.errorbar(d.Problem_Size, d["median"], yerr=[d["median"] - d.q25, d.q75 - d["median"]], marker="o",
                        markersize=3, linewidth=1, capsize=2, label=a, color=plt.cm.tab10(i))
        ax.set_xscale("log")
        ax.set_yscale("log")
        sizes = sorted(data[data.Resource_Count == m].Problem_Size.unique())
        ax.set_xticks(sizes, [str(s) for s in sizes])
        ax.minorticks_off()
        ax.set_title(f"{m} simulated processors", fontsize=9)
        ax.set_xlabel("Problem size (tasks)")
    axes[0][0].set_ylabel("Measured optimization / scheduling time (s)")
    axes[0][-1].legend(fontsize=6)
    fig.suptitle("Measured wall-clock time per run (seconds, Apple host); median and IQR over runs", fontsize=9)
    _save(fig, out_dir, "g2_opt_time_vs_size")
    return data


def convergence_data(trace: pd.DataFrame, master: pd.DataFrame, step: int = 100) -> pd.DataFrame:
    """Best-so-far makespan of each S01 run on a common evaluation grid, divided by HEFT's makespan on the same
    instance. The trace is a step function: at grid point e the value is the best of the last log with
    fitness_evals <= e; before a run's first log the value is NA."""
    ok = master[master.Status == "ok"]
    runs = ok[ok.Sub_Problem == "S01"].set_index("Run_ID")
    heft = per_instance(master)["HEFT"]
    budget = int(runs.Fitness_Evals.max())
    grid = np.union1d(np.arange(step, budget, step), [budget])  # always ends at the full budget
    rows = []
    for uid, t in trace.groupby("run_uid", sort=False):
        r = runs.loc[uid]
        i = np.searchsorted(t.fitness_evals.to_numpy(), grid, side="right") - 1
        best = np.where(i >= 0, t.best_makespan_sim.to_numpy()[np.maximum(i, 0)], np.nan)
        rows.append(pd.DataFrame(dict(Run_ID=uid, Algorithm=r.Algorithm, Problem_Size=r.Problem_Size,
                                      Split=r.Split, Instance_Hash=r.Instance_Hash, evals=grid,
                                      best_over_heft=best / heft[r.Instance_Hash])))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def figure_convergence(trace: pd.DataFrame, master: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """G2b: best-so-far simulated makespan / HEFT makespan vs evaluations, one panel per problem size, median and
    IQR over runs."""
    curves = convergence_data(trace, master)
    curves.to_csv(out_dir / "g2_convergence_runs.csv", index=False, na_rep="NA")
    data = _iqr(curves.set_index(["Problem_Size", "Algorithm", "evals"]).best_over_heft.dropna(),
                ["Problem_Size", "Algorithm", "evals"])
    data.to_csv(out_dir / "g2_convergence.csv", index=False, na_rep="NA")
    sizes = sorted(data.Problem_Size.unique())
    fig, axes = plt.subplots(2, len(sizes), figsize=(3.3 * len(sizes), 5.6), sharey="row", squeeze=False)
    for c, n in enumerate(sizes):
        for row, ax in enumerate(axes[:, c]):  # row 1 zooms in on the seeded methods near HEFT
            for i, a in enumerate(a for a in S01_METHODS if a in set(data.Algorithm)):
                d = data[(data.Problem_Size == n) & (data.Algorithm == a)]
                ax.plot(d.evals, d["median"], linewidth=1, label=a, color=plt.cm.tab10(i))
                ax.fill_between(d.evals, d.q25, d.q75, alpha=0.15, color=plt.cm.tab10(i), linewidth=0)
            ax.axhline(1.0, color="grey", linestyle=":", linewidth=0.8)  # HEFT
            if row:
                ax.set_ylim(0.9, 1.02)
                ax.set_xlabel("Fitness evaluations")
            else:
                ax.set_title(f"n = {n}", fontsize=9)
    axes[0][0].set_ylabel("Best simulated makespan / HEFT")
    axes[1][0].set_ylabel("same, zoomed to 0.90-1.02")
    axes[0][-1].legend(fontsize=6)
    fig.suptitle("Convergence (simulated makespan); median and IQR over runs; dotted line = HEFT", fontsize=9)
    _save(fig, out_dir, "g2_convergence")
    return data


def improvement_data(master: pd.DataFrame) -> pd.DataFrame:
    """Per instance and S01 method: paired improvement (Cmax_base - Cmax_alg) / Cmax_base against FCFS-EAT and
    against BEST-HEURISTIC. Group = workload class on test_id, OOD set name on test_ood."""
    per = per_instance(master)
    first = master.groupby("Instance_Hash")[["Split", "Workload", "Problem_Size", "Resource_Count"]].first()
    group = np.where(first.Split == "test_ood", first.Workload.str.split("/").str[0], first.Workload)
    rows = []
    for a in [x for x in S01_METHODS if x in per]:
        for b in ("FCFS-EAT", "BEST-HEURISTIC"):
            rows.append(pd.DataFrame(dict(Instance_Hash=per.index, Group=pd.Series(group, first.index)[per.index].to_numpy(),
                                          Split=first.Split[per.index].to_numpy(), Algorithm=a, Baseline=b,
                                          Improvement=((per[b] - per[a]) / per[b]).to_numpy())))
    return pd.concat(rows, ignore_index=True)


def figure_improvement_by_class(master: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    """G3: box plots of paired per-instance improvement by workload class / OOD set; boxes = quartiles,
    whiskers = 5th and 95th percentiles, triangles = mean."""
    inst = improvement_data(master)
    inst.to_csv(out_dir / "g3_improvement_by_class_instances.csv", index=False, na_rep="NA")
    data = _iqr(inst.set_index(["Baseline", "Group", "Algorithm"]).Improvement, ["Baseline", "Group", "Algorithm"])
    data.to_csv(out_dir / "g3_improvement_by_class.csv", index=False, na_rep="NA")
    groups = list(dict.fromkeys(inst.sort_values(["Split", "Group"]).Group))
    algos = [a for a in S01_METHODS if a in set(inst.Algorithm)]
    fig, axes = plt.subplots(2, 1, figsize=(max(7, 1.3 * len(groups)), 6.4), squeeze=False)
    w = 0.8 / len(algos)
    for ax, base in zip(axes[:, 0], ("FCFS-EAT", "BEST-HEURISTIC")):
        for i, a in enumerate(algos):
            vals = [inst[(inst.Baseline == base) & (inst.Algorithm == a) & (inst.Group == g)].Improvement * 100
                    for g in groups]
            pos = np.arange(len(groups)) + (i - (len(algos) - 1) / 2) * w
            bp = ax.boxplot(vals, positions=pos, widths=w * 0.9, whis=(5, 95), showfliers=False, showmeans=True,
                            patch_artist=True, medianprops=dict(color="k", linewidth=1),
                            meanprops=dict(marker="^", markersize=3, markerfacecolor="k", markeredgecolor="k"))
            for box in bp["boxes"]:
                box.set(facecolor=plt.cm.tab10(i), alpha=0.6)
            ax.plot([], [], color=plt.cm.tab10(i), linewidth=6, alpha=0.6, label=a)
        ax.axhline(0, color="grey", linestyle=":", linewidth=0.8)
        ax.set_xticks(range(len(groups)), groups, fontsize=7)
        ax.set_ylabel(f"Paired improvement vs {base} (%)")
    axes[0][0].legend(fontsize=6, ncol=len(algos))
    fig.suptitle("Paired per-instance improvement in simulated makespan, (Cmax_base - Cmax_alg) / Cmax_base\n"
                 "seed mean per instance; box = quartiles, whiskers = 5th-95th percentile, triangle = mean", fontsize=9)
    _save(fig, out_dir, "g3_improvement_by_class")
    return data


def _check_s01(raw_dir: Path, ok: pd.DataFrame, cfg: dict) -> list[str]:
    """S01 invariants: equal budgets, seeded search never worse than its seeds, traces consistent with rows."""
    s01, bad = ok[ok.sub_problem == "S01"], []
    if s01.empty:
        return bad
    if (s01.fitness_evals != cfg["ga"]["max_evals"]).any():
        bad.append("an S01 run did not use exactly max_evals evaluations")
    heur = ok[ok.sub_problem == "BASE"].groupby(_KEY).makespan_sim.first().unstack("algorithm")
    seeds = [h for h in cfg["ga"]["seed_heuristics"] if h in heur.columns]
    seeded = s01[s01.algorithm.isin(["GA", "RANDOM-SEARCH", "HILL-CLIMB"])]
    if seeds and (seeded.makespan_sim > heur[seeds].min(axis=1).reindex(seeded.instance_hash).to_numpy() * (1 + 1e-12)).any():
        bad.append("a seeded search method is worse than one of its seed heuristics")
    trace = pd.read_csv(raw_dir / "ga_trace.csv", float_precision="round_trip")
    if set(trace.run_uid) != set(s01.run_uid):
        bad.append("ga_trace.csv does not cover exactly the ok S01 runs")
    g = trace.groupby("run_uid")
    if (g.best_makespan_sim.diff().dropna() > 0).any() or (g.fitness_evals.diff().dropna() <= 0).any():
        bad.append("a trace's best-so-far increased or its evaluation count did not grow")
    last = g.last()
    rows = s01.set_index("run_uid").reindex(last.index)
    if not (last.best_makespan_sim == rows.makespan_sim).all() or not (last.fitness_evals == rows.fitness_evals).all():
        bad.append("a trace's final row disagrees with its run")
    return bad


def check(raw_dir, master: pd.DataFrame | None = None) -> list[str]:
    """Campaign validation (VALIDATION_PLAN.md 3, the parts that apply so far). [] means all passed."""
    raw_dir, bad = Path(raw_dir), []
    text = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    raw, manifest = load_raw(raw_dir)
    cfg = manifest["config"]
    if list(text.columns) != RAW_COLUMNS:
        bad.append("runs.csv header differs from RAW_COLUMNS")
    if (text == "").any().any():
        bad.append("blank cells in runs.csv (should be NA)")
    ok, not_ok = raw[raw.status == "ok"], raw[raw.status != "ok"]
    if not (ok.valid == 1).all():
        bad.append("an ok row is not valid")
    if not_ok[["makespan_sim", "busy_time_sim", "scheduling_time_s"]].notna().any().any():
        bad.append("a failed row carries a measurement instead of NA")
    if (ok.makespan_sim < ok.lower_bound_sim * (1 - 1e-9)).any():
        bad.append("makespan below the lower bound")
    homog = ok[ok.platform == "homog"]
    if (homog.serial_best_sim / homog.makespan_sim > homog.resource_count * (1 + 1e-9)).any():
        bad.append("speedup exceeds processor count on a homogeneous platform")
    util = ok.busy_time_sim / (ok.resource_count * ok.makespan_sim)
    if not ((util > 0) & (util <= 1 + 1e-9)).all():
        bad.append("utilization outside (0, 1]")
    if (ok.scheduling_time_s <= 0).any():
        bad.append("non-positive scheduling time")
    det = ok[ok.algo_seed.isna()]
    if (det.groupby(_KEY).makespan_sim.nunique() > 1).any():
        bad.append("a deterministic algorithm gave different makespans across repeats")
    counts = raw.groupby(_KEY).size().unstack("algorithm")
    seeded = set(raw.loc[raw.algo_seed.notna(), "algorithm"]) | set(raw.loc[raw.sub_problem == "S01", "algorithm"])
    expected = pd.Series({a: len(cfg["ga"]["seeds"]) if a in seeded else cfg["run"]["timing_repeats"]
                          for a in cfg["run"]["algorithms"]})
    if (set(counts.columns) != set(expected.index) or counts.isna().any().any()
            or (counts[expected.index].to_numpy() != expected.to_numpy()).any()):
        bad.append("not every instance has every algorithm with every repeat or seed")
    bad += _check_s01(raw_dir, ok, cfg)
    if len(counts) != sum(manifest["split_counts"][s] for s in cfg["run"]["splits"]):
        bad.append("instance count differs from the experiment matrix")
    if raw.groupby("instance_hash").split.nunique().max() > 1 or "train" in set(raw.split):
        bad.append("split leakage in runs.csv")
    if set(raw.time_unit) != {"sim_tu"}:
        bad.append("time_unit is not sim_tu everywhere")
    if manifest["row_count"] != len(raw) or manifest["failed_count"] != len(not_ok):
        bad.append("manifest counts differ from runs.csv")
    if not manifest.get("separation_checked"):
        bad.append("split separation was not verified by the runner")
    if master is not None:
        if list(master.columns[:19]) != MANUAL_COLUMNS:
            bad.append("master.csv does not start with the manual's 19 columns")
        if len(master) != len(raw):
            bad.append("master.csv dropped or added rows")
        if not np.allclose(master.Speedup.dropna(), (raw.serial_best_sim / raw.makespan_sim).dropna()):
            bad.append("Speedup is not reproducible from raw columns")
        for col in ("Communication_Time", "Synchronization_Time", "Energy_if_available"):
            if master[col].notna().any():
                bad.append(f"{col} should be NA")
    return bad


def analyze(raw_dir, out_root="results", identity_path="configs/identity.toml", final: bool = False) -> dict:
    raw_dir = Path(raw_dir)
    identity = tomllib.loads(Path(identity_path).read_text())
    placeholders = PLACEHOLDER in identity["batch_id"] or any(PLACEHOLDER in v for v in identity["student_id"].values())
    if placeholders and final:
        raise ValueError("Student_ID / Batch_ID are still placeholders; confirm them in the identity file first")
    raw, manifest = load_raw(raw_dir)
    master = derive(raw, manifest, identity)
    derived = Path(out_root) / "derived" / raw_dir.name
    figures = Path(out_root) / "figures" / raw_dir.name
    derived.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    master.to_csv(derived / "master.csv", index=False, na_rep="NA")
    summary, timing = summarize(master), timing_by_size(master)
    summary.to_csv(derived / "summary_by_algorithm.csv", index=False, na_rep="NA")
    timing.to_csv(derived / "timing_by_size.csv", index=False, na_rep="NA")
    paired, overhead = s01_paired(master), s01_overhead_quality(master)
    figure_makespan_vs_size(master, figures)
    if len(paired):
        paired.to_csv(derived / "s01_paired.csv", index=False, na_rep="NA")
        overhead.to_csv(derived / "s01_overhead_quality.csv", index=False, na_rep="NA")
        figure_opt_time_vs_size(master, figures)
        figure_convergence(pd.read_csv(raw_dir / "ga_trace.csv", float_precision="round_trip"), master, figures)
        figure_improvement_by_class(master, figures)
    return dict(master=master, summary=summary, timing=timing, paired=paired, overhead=overhead,
                problems=check(raw_dir, master),
                placeholders=placeholders, derived=derived, figures=figures, manifest=manifest)
