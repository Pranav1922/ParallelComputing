"""M-D analysis of a measured OpenMP execution campaign (docs/MD_ANALYSIS_PLAN.md, written before launch).

    python -m schedlab.omp_analysis results/raw/<omp campaign> [--out-root results]

writes results/derived/<campaign>/*.csv and results/figures/<campaign>/*.{pdf,svg} (+ plotted-data CSVs).
Inputs are read-only. Every number is computed from the campaign's runs.csv / task_trace.csv(.gz), the
calibration manifest, and (for M2's Python decision time) the accepted S03 campaign. Output is deterministic,
so a second run into another directory must give byte-identical files.
Units: wall/compute/wait in measured seconds; sim_makespan_tu in simulated time units; never added.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, wilcoxon

ROOT = Path(__file__).resolve().parent.parent
S03_RAW = ROOT / "results" / "raw" / "20261017T083329Z-s03_final-b8e5be9a"
PRIMARY_G = 10.0
BOOT, SEED = 10_000, 20261018
GA_SEEDS = {"GA": ["GA#s0", "GA#s1", "GA#s2"], "GA-KEYS-EFT": ["GA-KEYS-EFT#s0", "GA-KEYS-EFT#s1", "GA-KEYS-EFT#s2"]}
plt.rcParams["svg.hashsalt"] = "schedlab-md"


def _method(df: pd.DataFrame) -> pd.Series:
    return np.where(df["mode"] == "static", df["label"], df["mode"].str.upper())


def per_instance(runs: pd.DataFrame) -> pd.DataFrame:
    """Median and CV over the timed reps per (instance, granularity, method), plus speedup and gaps."""
    t = runs[runs.warmup == 0].copy()
    t["method"] = _method(t)
    t["dep_wait_share"] = t.dep_wait_s / (t.wall_s * t.threads)
    t["idle_share"] = t.idle_s / (t.wall_s * t.threads)
    t["ready_queue_per_task_s"] = t.ready_queue_s / t.n
    keys = ["instance_id", "us_per_tu", "method"]
    g = t.groupby(keys)
    p = g.agg(workload_class=("workload_class", "first"), n=("n", "first"), threads=("threads", "first"),
              sim_makespan_tu=("sim_makespan_tu", "first"), wall_median_s=("wall_s", "median"),
              wall_mean_s=("wall_s", "mean"), wall_sd_s=("wall_s", "std"), wall_min_s=("wall_s", "min"),
              wall_max_s=("wall_s", "max"), reps=("wall_s", "size"), compute_median_s=("compute_s", "median"),
              dep_wait_share=("dep_wait_share", "median"), idle_share=("idle_share", "median"),
              ready_queue_per_task_s=("ready_queue_per_task_s", "median"), imbalance=("imbalance", "median"))
    p = p.reset_index()
    p["wall_cv"] = p.wall_sd_s / p.wall_mean_s
    m = p.groupby("instance_id").threads.max().rename("m")
    p = p.join(m, on="instance_id")
    t1 = p[p.method == "SERIAL"].set_index(["instance_id", "us_per_tu"])
    p = p.join(t1.wall_median_s.rename("T1_s"), on=["instance_id", "us_per_tu"])
    p = p.join(t1.sim_makespan_tu.rename("serial_best_tu"), on=["instance_id", "us_per_tu"])
    p["speedup"] = p.T1_s / p.wall_median_s
    p["efficiency"] = p.speedup / p.m
    p["G_raw"] = p.wall_median_s / (p.sim_makespan_tu * p.us_per_tu * 1e-6)           # NaN for TASKS
    u_hat = p.T1_s / p.serial_best_tu                                                  # measured s per sim_tu
    p["G_adj"] = p.wall_median_s / (p.sim_makespan_tu * u_hat)
    return p.sort_values(keys).reset_index(drop=True)


def _gm_ci(r: np.ndarray, rng) -> tuple[float, float, float]:
    lr = np.log(r)
    idx = rng.integers(len(lr), size=(BOOT, len(lr)))
    boot = np.exp(lr[idx].mean(axis=1))
    return float(np.exp(lr.mean())), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def _paired(p: pd.DataFrame, a: str, b: str, g: float, e2e: pd.DataFrame | None = None) -> dict:
    """Ratio A/B per instance on medians; GA-style A = mean of its seeds' medians. Noise band per §4."""
    q = p[p.us_per_tu == g].set_index(["instance_id", "method"])
    ids = sorted(p.instance_id.unique())

    def val(meth, col):
        ms = GA_SEEDS.get(meth, [meth])
        return np.mean([q.loc[[(i, s) for i in ids], col].to_numpy() for s in ms], axis=0), len(ms)

    ta, ka = val(a, "wall_median_s")
    tb, kb = val(b, "wall_median_s")
    # CV of a mean of k independent medians: sqrt(sum cv_s^2) / k (seeds); k = 1 otherwise
    cva = np.sqrt(np.sum([q.loc[[(i, s) for i in ids], "wall_cv"].to_numpy() ** 2 for s in GA_SEEDS.get(a, [a])],
                         axis=0)) / ka
    cvb = np.sqrt(np.sum([q.loc[[(i, s) for i in ids], "wall_cv"].to_numpy() ** 2 for s in GA_SEEDS.get(b, [b])],
                         axis=0)) / kb
    if e2e is not None:  # end-to-end: Python decision/scheduling time + measured execution
        da = e2e.loc[ids, a].to_numpy()
        db = e2e.loc[ids, b].to_numpy()
        cva, cvb = cva * ta / (ta + da), cvb * tb / (tb + db)
        ta, tb = ta + da, tb + db
    r = ta / tb
    sa, _ = val(a, "sim_makespan_tu") if a != "TASKS" else (np.full(len(ids), np.nan), 1)
    sb, _ = val(b, "sim_makespan_tu")
    r_sim = sa / sb
    band = 2 * np.sqrt((cva ** 2 + cvb ** 2) / 10)
    lr = np.log(r)
    gm, lo, hi = _gm_ci(r, np.random.default_rng(SEED))
    w = wilcoxon(lr, zero_method="wilcox").pvalue if np.any(lr != 0) else 1.0
    out = dict(a=a, b=b, us_per_tu=g, end_to_end=e2e is not None, instances=len(ids), geo_mean_ratio=gm,
               ci95_lo=lo, ci95_hi=hi, wilcoxon_p=w, wins=int((lr < -band).sum()), ties=int((abs(lr) <= band).sum()),
               losses=int((lr > band).sum()), median_noise_band=float(np.median(band)),
               sim_geo_mean_ratio=float(np.exp(np.log(r_sim).mean())) if np.isfinite(r_sim).all() else np.nan,
               # instances whose two schedules are identical (simulated ratio exactly 1) carry no sign to agree with
               sim_identical=int(np.sum(r_sim == 1)) if np.isfinite(r_sim).all() else np.nan,
               sign_agreement=float(np.mean((np.sign(lr) == np.sign(np.log(r_sim)))[r_sim != 1]))
               if np.isfinite(r_sim).all() and np.any(r_sim != 1) else np.nan)
    return out


def _decision_times() -> pd.DataFrame:
    """Python scheduling time (s), median of the 3 repeats per test_id instance, from the accepted S03 campaign."""
    d = pd.read_csv(S03_RAW / "runs.csv", usecols=["instance_id", "split", "algorithm", "scheduling_time_s"])
    d = d[(d.split == "test_id") & d.algorithm.isin(["ADAPTIVE", "HEFT", "TRY-ALL"])]
    return d.groupby(["instance_id", "algorithm"]).scheduling_time_s.median().unstack()


def comparisons(p: pd.DataFrame) -> pd.DataFrame:
    e2e = _decision_times()
    rows = []
    for g in sorted(p.us_per_tu.unique(), reverse=True):
        rows += [dict(_paired(p, "GA", "HEFT", g), id="M1"),
                 dict(_paired(p, "ADAPTIVE", "HEFT", g, e2e), id="M2"),
                 dict(_paired(p, "TASKS", "HEFT", g), id="M3"),
                 dict(_paired(p, "TRY-ALL", "HEFT", g, e2e), id="M2-secondary"),
                 dict(_paired(p, "RL-S0", "HEFT", g), id="descriptive"),
                 dict(_paired(p, "GA-KEYS-EFT", "HEFT", g), id="descriptive"),
                 dict(_paired(p, "ADAPTIVE", "HEFT", g), id="descriptive-execution-only"),
                 dict(_paired(p, "FCFS-EAT", "HEFT", g), id="descriptive")]
    c = pd.DataFrame(rows)
    c["primary"] = c.id.isin(["M1", "M2", "M3"]) & (c.us_per_tu == PRIMARY_G)
    pr = c[c.primary].sort_values("wilcoxon_p")
    holm, run = {}, 0.0
    for k, (i, row) in enumerate(pr.iterrows()):          # Holm step-down, monotone
        run = max(run, min(1.0, (len(pr) - k) * row.wilcoxon_p))
        holm[i] = run
    c["holm_p"] = pd.Series(holm)
    c["resolvable_in_aggregate"] = np.where(
        c.primary, (c.holm_p < 0.05) & ((c.ci95_hi < 1) | (c.ci95_lo > 1)), (c.ci95_hi < 1) | (c.ci95_lo > 1))
    return c[["id", "a", "b", "us_per_tu", "primary", "end_to_end", "instances", "geo_mean_ratio", "ci95_lo", "ci95_hi",
              "wilcoxon_p", "holm_p", "resolvable_in_aggregate", "wins", "ties", "losses", "median_noise_band",
              "sim_geo_mean_ratio", "sim_identical", "sign_agreement"]]


def _q(x):
    return x.quantile([0.25, 0.5, 0.75]).to_numpy()


def summaries(p: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    s = p.groupby(["method", "m", "us_per_tu"]).agg(
        speedup_median=("speedup", "median"), speedup_q25=("speedup", lambda v: v.quantile(.25)),
        speedup_q75=("speedup", lambda v: v.quantile(.75)), efficiency_median=("efficiency", "median"),
        G_raw_median=("G_raw", "median"), G_adj_median=("G_adj", "median"), wall_cv_median=("wall_cv", "median"),
        wall_cv_q90=("wall_cv", lambda v: v.quantile(.9)), dep_wait_share=("dep_wait_share", "median"),
        idle_share=("idle_share", "median"), ready_queue_per_task_s=("ready_queue_per_task_s", "median"),
        imbalance=("imbalance", "median"), instances=("instance_id", "nunique")).reset_index()
    out["summary_by_method_m_granularity"] = s
    taus = []
    st = p[~p.method.isin(["SERIAL", "TASKS"])]
    for (iid, g), d in st.groupby(["instance_id", "us_per_tu"]):
        tau = kendalltau(d.sim_makespan_tu, d.wall_median_s).statistic
        taus.append(dict(instance_id=iid, us_per_tu=g, m=d.m.iloc[0], kendall_tau=tau))
    k = pd.DataFrame(taus)
    out["rank_agreement_per_instance"] = k
    out["rank_agreement_summary"] = k.groupby(["m", "us_per_tu"]).kendall_tau.agg(
        median="median", q25=lambda v: v.quantile(.25), q75=lambda v: v.quantile(.75)).reset_index()
    return out


def thread_slowdown(trace: pd.DataFrame, iters_per_us: float) -> pd.DataFrame:
    """Per run (rep 0, static and tasks), each thread's median task slowdown = measured / calibrated time.
    Thread indices are not tied to core types (no pinning), so the distribution over threads is reported."""
    t = trace[trace["mode"].isin(["static", "tasks"])].copy()
    t["slowdown"] = (t.end_s - t.start_s) / (t.iters / (iters_per_us * 1e6))
    per = t.groupby(["instance_id", "us_per_tu", "mode", "label", "thread"]).slowdown.median().reset_index()
    m = trace.groupby("instance_id").thread.max() + 1
    per = per.join(m.rename("m"), on="instance_id")
    per["slow_thread"] = per.slowdown > 1.3
    return per.groupby(["m", "us_per_tu"]).agg(
        thread_slowdown_q10=("slowdown", lambda v: v.quantile(.1)), thread_slowdown_median=("slowdown", "median"),
        thread_slowdown_q90=("slowdown", lambda v: v.quantile(.9)), share_threads_over_1_3=("slow_thread", "mean"),
        thread_runs=("slowdown", "size")).reset_index()


# ---- figures ------------------------------------------------------------------------------------

def _save(fig, fdir: Path, stem: str, data: pd.DataFrame) -> None:
    fig.tight_layout()
    fig.savefig(fdir / f"{stem}.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(fdir / f"{stem}.svg", metadata={"Date": None})
    plt.close(fig)
    data.to_csv(fdir / f"{stem}.csv", index=False)


SHOW = ["HEFT", "GA#s0", "RL-S0", "ADAPTIVE", "FCFS-EAT", "TASKS"]


def figures(p: pd.DataFrame, comp: pd.DataFrame, fdir: Path) -> None:
    gs = sorted(p.us_per_tu.unique(), reverse=True)
    # F1 speedup vs threads (measured; baseline T1 = SERIAL on the same instance and granularity)
    s = p[p.method.isin(SHOW)].groupby(["us_per_tu", "method", "m"]).speedup.agg(
        median="median", q25=lambda v: v.quantile(.25), q75=lambda v: v.quantile(.75)).reset_index()
    fig, axes = plt.subplots(1, len(gs), figsize=(9, 3), sharey=True)
    for ax, g in zip(axes, gs):
        for meth in SHOW:
            d = s[(s.us_per_tu == g) & (s.method == meth)]
            ax.errorbar(d.m, d["median"], yerr=[d["median"] - d.q25, d.q75 - d["median"]], marker="o", ms=3,
                        capsize=2, label=meth)
        ax.plot([2, 8], [2, 8], ":", color="grey", lw=0.8)
        ax.set_xticks([2, 4, 8])
        ax.set_title(f"mean task {100 * g:g} µs", fontsize=9)
        ax.set_xlabel("threads (m)")
    axes[0].set_ylabel("measured speedup T1 / Tp")
    axes[-1].legend(fontsize=6)
    fig.suptitle("Measured speedup on Apple M4 (median, IQR over instances; dotted: ideal)", fontsize=9)
    _save(fig, fdir, "md1_speedup_vs_threads", s)

    # F2 simulator gap, raw and calibration-adjusted (HEFT schedule), by m and granularity
    h = p[p.method == "HEFT"].melt(id_vars=["m", "us_per_tu"], value_vars=["G_raw", "G_adj"], var_name="gap")
    fig, axes = plt.subplots(1, 2, figsize=(8, 3), sharey=True)
    for ax, gap in zip(axes, ["G_raw", "G_adj"]):
        d = h[h.gap == gap]
        pos, data, labels = [], [], []
        for i, m in enumerate([2, 4, 8]):
            for j, g in enumerate(gs):
                pos.append(i * 4 + j)
                data.append(d[(d.m == m) & (d.us_per_tu == g)].value.to_numpy())
                labels.append(f"m{m}\n{100 * g:g}µs")
        ax.boxplot(data, positions=pos, widths=0.8, showfliers=False)
        ax.set_xticks(pos, labels, fontsize=6)
        ax.axhline(1, color="grey", ls=":", lw=0.8)
        ax.set_title({"G_raw": "raw: measured / (simulated × nominal µs per tu)",
                      "G_adj": "adjusted: measured / (simulated × measured serial s per tu)"}[gap], fontsize=8)
    axes[0].set_ylabel("measured / predicted (HEFT schedule)")
    _save(fig, fdir, "md2_simulator_gap", h)

    # F3 paired ratios vs HEFT: measured (per-instance medians) next to simulated
    rows = []
    for g in gs:
        q = p[p.us_per_tu == g].pivot_table(index="instance_id", columns="method", values=["wall_median_s", "sim_makespan_tu"])
        for a in ["GA", "RL-S0", "ADAPTIVE", "TASKS"]:
            cols = GA_SEEDS.get(a, [a])
            meas = q["wall_median_s"][cols].mean(axis=1) / q["wall_median_s"]["HEFT"]
            sim = (q["sim_makespan_tu"][cols].mean(axis=1) / q["sim_makespan_tu"]["HEFT"]) if a != "TASKS" else np.nan * meas
            rows += [dict(us_per_tu=g, method=a, kind=k, ratio=v) for k, ser in (("measured", meas), ("simulated", sim))
                     for v in ser.to_numpy()]
    r = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, len(gs), figsize=(9, 3), sharey=True)
    for ax, g in zip(axes, gs):
        pos, data, labels = [], [], []
        for i, a in enumerate(["GA", "RL-S0", "ADAPTIVE", "TASKS"]):
            for j, k in enumerate(["simulated", "measured"]):
                v = r[(r.us_per_tu == g) & (r.method == a) & (r.kind == k)].ratio.dropna().to_numpy()
                if len(v):
                    pos.append(i * 3 + j)
                    data.append(v)
                    labels.append(f"{a}\n{k[:4]}")
        ax.boxplot(data, positions=pos, widths=0.8, showfliers=False)
        ax.set_xticks(pos, labels, fontsize=6)
        ax.axhline(1, color="grey", ls=":", lw=0.8)
        ax.set_title(f"mean task {100 * g:g} µs", fontsize=9)
    axes[0].set_ylabel("ratio to HEFT (per instance)")
    fig.suptitle("Simulated vs measured ratio to HEFT (<1: faster than HEFT)", fontsize=9)
    _save(fig, fdir, "md3_ratio_to_heft", r)


def analyze(raw: Path, out_root: Path) -> tuple[Path, Path]:
    raw = Path(raw)
    m = json.loads((raw / "manifest.json").read_text())
    cal = json.loads((ROOT / m["calibration"] / "manifest.json").read_text())["derived"]
    runs = pd.read_csv(raw / "runs.csv", float_precision="round_trip")
    tr_path = raw / "task_trace.csv.gz" if (raw / "task_trace.csv.gz").exists() else raw / "task_trace.csv"
    trace = pd.read_csv(tr_path, float_precision="round_trip")
    ddir = Path(out_root) / "derived" / raw.name
    fdir = Path(out_root) / "figures" / raw.name
    ddir.mkdir(parents=True, exist_ok=True)
    fdir.mkdir(parents=True, exist_ok=True)
    p = per_instance(runs)
    p.to_csv(ddir / "per_instance.csv", index=False)
    comp = comparisons(p)
    comp.to_csv(ddir / "comparisons.csv", index=False)
    for name, df in summaries(p).items():
        df.to_csv(ddir / f"{name}.csv", index=False)
    thread_slowdown(trace, cal["iters_per_us"]).to_csv(ddir / "thread_slowdown.csv", index=False)
    pd.DataFrame([dict(threads=k, **{kk: vv for kk, vv in v.items() if kk != "kernel_median_s_by_thread"})
                  for k, v in cal["threads"].items()]).to_csv(ddir / "calibration_fork_join_and_threads.csv", index=False)
    figures(p, comp, fdir)
    return ddir, fdir


def check_traces(raw: Path) -> dict:
    """Acceptance criterion 3, independent of the executor's flags: for every traced run (rep 0), each task
    appears exactly once, starts no earlier than every predecessor ends, static tasks ran on their scheduled
    processor, and each task's iterations equal llround(cost[t][p] * K) for the processor whose cost applies."""
    import tomllib
    from .heuristics import HEURISTICS
    from .workloads import experiment_matrix
    raw = Path(raw)
    m = json.loads((raw / "manifest.json").read_text())
    ipt = {float(k): v for k, v in m["iters_per_tu"].items()}
    cfg = tomllib.loads((ROOT / m["config"]).read_text())
    insts = {i.id: i for i in experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])["test_id"]}
    rd = ROOT / m["rederive"] / "schedules"
    tr_path = raw / "task_trace.csv.gz" if (raw / "task_trace.csv.gz").exists() else raw / "task_trace.csv"
    tr = pd.read_csv(tr_path, float_precision="round_trip")
    problems, runs_checked = [], 0
    for iid, d_i in tr.groupby("instance_id", sort=True):
        inst = insts[iid]
        procs = {}
        text = (rd / f"{iid}.jobs").read_text()
        for blk in ("\n" + text).split("\nend\n"):
            if blk.strip():
                lines = blk.strip().splitlines()
                procs[lines[0].split()[1]] = [int(x) for x in lines[2].split()[1:]]
        for name in ("FCFS-EAT", "HEFT"):
            procs[name] = HEURISTICS[name](inst, None)[0].proc.tolist()
        p_serial = int(np.argmin([sum(inst.cost[t, p] for t in range(inst.n)) for p in range(inst.m)]))
        preds = inst.preds
        for (g, mode, label), d in d_i.groupby(["us_per_tu", "mode", "label"], sort=True):
            runs_checked += 1
            key = (iid, g, mode, label)
            if sorted(d.task) != list(range(inst.n)):
                problems.append((*key, "task set"))
                continue
            d = d.set_index("task").sort_index()
            start, end, th, it = d.start_s.to_numpy(), d.end_s.to_numpy(), d.thread.to_numpy(), d.iters.to_numpy()
            if any(start[t] < end[u] for t in range(inst.n) for u in preds[t]):
                problems.append((*key, "precedence"))
            if mode == "static":
                pr = np.array(procs[label])
                if not np.array_equal(th, pr):
                    problems.append((*key, "placement"))
            elif mode == "serial":
                pr = np.full(inst.n, p_serial)
                if np.any(th != 0):
                    problems.append((*key, "serial thread"))
            else:
                pr = th
                if np.any((th < 0) | (th >= inst.m)):
                    problems.append((*key, "thread range"))
            want = np.maximum(1, np.array([int(np.floor(inst.cost[t, pr[t]] * ipt[g] + 0.5)) for t in range(inst.n)]))
            if not np.array_equal(it, want):
                problems.append((*key, "iterations"))
    return dict(trace_rows=len(tr), runs_checked=runs_checked, instances=tr.instance_id.nunique(),
                problems=len(problems), first_problems=[list(map(str, p)) for p in problems[:20]])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schedlab.omp_analysis")
    ap.add_argument("raw", type=Path)
    ap.add_argument("--out-root", type=Path, default=ROOT / "results")
    ap.add_argument("--check-traces", action="store_true", help="acceptance criterion 3 only")
    a = ap.parse_args(argv)
    if a.check_traces:
        r = check_traces(a.raw)
        print(json.dumps(r))
        return 0 if r["problems"] == 0 else 1
    d, f = analyze(a.raw, a.out_root)
    print(d)
    print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
