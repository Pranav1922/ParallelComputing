"""Hand-computed checks of the S01 aggregation formulas (DATA_SCHEMA.md 4.1) on a synthetic master table."""
import numpy as np
import pandas as pd
import pytest

from schedlab.analysis import (convergence_data, improvement_data, paired_stats, per_instance, s01_overhead_quality,
                               s01_paired, summarize)

# Two instances. FCFS-EAT 10 / 20, HEFT 9 / 12, GA seeds (7, 9) / (10, 10) -> seed means 8 / 10.
CMAX = {("a", "FCFS-EAT"): [10], ("a", "HEFT"): [9], ("a", "GA"): [7, 9],
        ("b", "FCFS-EAT"): [20], ("b", "HEFT"): [12], ("b", "GA"): [10, 10]}
TIME = {"FCFS-EAT": 0.001, "HEFT": 0.001, "GA": 0.5}


def master():
    rows = []
    for (inst, algo), values in CMAX.items():
        for seed, c in enumerate(values):
            rows.append(dict(Instance_Hash=inst, Algorithm=algo, Execution_Time=float(c), Status="ok",
                             Sub_Problem="S01" if algo == "GA" else "BASE", Split="test_id", Workload="regular",
                             Problem_Size=50, Resource_Count=2, Scheduling_Time=TIME[algo], Lower_Bound=5.0,
                             Norm_Makespan=c / 5.0, Speedup=1.0, Efficiency=0.5, Utilization=0.5,
                             Fitness_Evals=1, Run_ID=f"{inst}{algo}{seed}"))
    rows.append(dict(rows[-1], Status="error", Execution_Time=np.nan, Run_ID="failed"))  # never counted
    m = pd.DataFrame(rows)
    per = m[m.Status == "ok"].groupby(["Instance_Hash", "Algorithm"]).Execution_Time.mean().unstack()
    best = per[["FCFS-EAT", "HEFT"]].min(axis=1)
    for col, ref in (("Improvement_vs_FCFS", per["FCFS-EAT"]), ("Improvement_vs_HEFT", per["HEFT"]),
                     ("Improvement_vs_BestHeuristic", best)):
        r = ref.reindex(m.Instance_Hash).to_numpy()
        m[col] = (r - m.Execution_Time) / r
    m["Regret_vs_VBS"] = 0.0
    m["Timing_Outlier"] = 0
    return m


def test_per_instance_uses_the_seed_mean_and_ignores_failed_rows():
    per = per_instance(master())
    assert per.loc["a", "GA"] == 8 and per.loc["b", "GA"] == 10
    assert per.loc["a", "BEST-HEURISTIC"] == 9 and per.loc["b", "BEST-HEURISTIC"] == 12
    assert per.loc["a", "GA-BEST-OF-SEEDS"] == 7 and per.loc["b", "GA-BEST-OF-SEEDS"] == 10


def test_paired_improvement_is_the_mean_of_per_instance_ratios_not_a_ratio_of_means():
    s = paired_stats(pd.Series({"a": 8.0, "b": 10.0}), pd.Series({"a": 10.0, "b": 20.0}))
    # per instance: 0.8 and 0.5
    assert s["ratio_mean"] == pytest.approx(0.65) and s["improvement_mean"] == pytest.approx(0.35)
    assert s["ratio_geomean"] == pytest.approx(np.sqrt(0.4)) and s["improvement_geomean"] == pytest.approx(1 - np.sqrt(0.4))
    assert s["ratio_median"] == pytest.approx(0.65) and (s["ratio_min"], s["ratio_max"]) == (0.5, 0.8)
    assert 1 - 18 / 30 != pytest.approx(s["improvement_mean"])          # ratio of total makespans differs
    assert (s["better"], s["tie"], s["worse"]) == (2, 0, 0) and s["instances"] == 2


def test_paired_stats_counts_ties_and_losses_and_drops_unpaired_instances():
    s = paired_stats(pd.Series({"a": 10.0, "b": 12.0, "c": 5.0}), pd.Series({"a": 10.0, "b": 10.0, "d": 1.0}))
    assert s["instances"] == 2 and (s["better"], s["tie"], s["worse"]) == (0, 1, 1)
    assert s["improvement_mean"] == pytest.approx(-0.1)


def test_bootstrap_interval_is_deterministic_and_brackets_the_mean():
    rng = np.random.default_rng(3)
    base = pd.Series(rng.uniform(10, 20, 60))
    alg = base * rng.uniform(0.9, 1.05, 60)
    a, b = paired_stats(alg, base), paired_stats(alg, base)
    assert a == b and a["ratio_ci95_lo"] < a["ratio_mean"] < a["ratio_ci95_hi"]
    const = paired_stats(base * 0.9, base)
    assert const["ratio_ci95_lo"] == pytest.approx(0.9) and const["ratio_ci95_hi"] == pytest.approx(0.9)


def test_paired_table_and_summary_agree():
    m = master()
    t = s01_paired(m).set_index(["algorithm", "baseline"])
    assert set(t.split) == {"test_id"}                              # one split: no redundant "all" rows
    assert t.loc[("GA", "FCFS-EAT"), "improvement_mean"] == pytest.approx(0.35)
    assert t.loc[("GA", "HEFT"), "improvement_mean"] == pytest.approx(1 - (8 / 9 + 10 / 12) / 2)
    assert t.loc[("GA-BEST-OF-SEEDS", "FCFS-EAT"), "improvement_mean"] == pytest.approx(1 - (0.7 + 0.5) / 2)
    assert np.isnan(t.loc[("GA", "HEFT"), "wilcoxon_p"]) and not np.isnan(t.loc[("GA", "BEST-HEURISTIC"), "wilcoxon_p"])
    s = summarize(m).set_index("Algorithm").loc["GA"]
    assert s["paired_impr_vs_FCFS-EAT_mean"] == pytest.approx(t.loc[("GA", "FCFS-EAT"), "improvement_mean"])
    assert s["paired_impr_vs_HEFT_mean"] == pytest.approx(t.loc[("GA", "HEFT"), "improvement_mean"])
    assert s["paired_impr_vs_best_heuristic_mean"] == pytest.approx(t.loc[("GA", "BEST-HEURISTIC"), "improvement_mean"])
    assert s["cmax_over_lb_mean_of_instances"] == pytest.approx((8 / 5 + 10 / 5) / 2)


def test_overhead_table_and_hypothetical_break_even():
    o = s01_overhead_quality(master()).set_index("algorithm")
    ga, best = o.loc["GA"], o.loc["GA-BEST-OF-SEEDS"]
    assert ga.opt_time_s_median == pytest.approx(0.5) and best.opt_time_s_median == pytest.approx(1.0)  # 2 seeds charged
    assert ga.time_ratio_vs_HEFT_median == pytest.approx(500)
    # tau* = (T_GA - T_HEFT) / (Cmax_HEFT - Cmax_GA): instance a: 0.499 / 1, instance b: 0.499 / 2
    assert ga.HYPOTHETICAL_tau_star_s_per_tu_median == pytest.approx((0.499 + 0.2495) / 2)
    assert ga.share_better_than_HEFT == 1


def test_improvement_data_matches_the_formula():
    d = improvement_data(master()).set_index(["Instance_Hash", "Algorithm", "Baseline"]).Improvement
    assert d[("a", "GA", "FCFS-EAT")] == pytest.approx(0.2) and d[("b", "GA", "FCFS-EAT")] == pytest.approx(0.5)
    assert d[("a", "GA", "BEST-HEURISTIC")] == pytest.approx(1 / 9)


def test_convergence_is_a_step_function_on_the_grid():
    m = master()
    uid = m[(m.Algorithm == "GA") & (m.Status == "ok")].Run_ID.iloc[0]          # instance a, HEFT = 9
    m.loc[m.Run_ID == uid, "Fitness_Evals"] = 300
    trace = pd.DataFrame(dict(run_uid=uid, generation=[0, 1, 2], fitness_evals=[150, 250, 300],
                              best_makespan_sim=[9.0, 8.0, 7.0]))
    c = convergence_data(trace, m).set_index("evals").best_over_heft
    assert np.isnan(c[100]) and c[200] == pytest.approx(1) and c[300] == pytest.approx(7 / 9)


def test_break_even_is_infinite_where_the_search_does_not_beat_heft():
    m = master()
    m.loc[(m.Instance_Hash == "b") & (m.Algorithm == "GA"), "Execution_Time"] = 12.0   # ties HEFT on b
    m.loc[(m.Instance_Hash == "b") & (m.Algorithm == "GA") & (m.Status != "ok"), "Execution_Time"] = np.nan
    o = s01_overhead_quality(m).set_index("algorithm").loc["GA"]
    assert o.share_better_than_HEFT == 0.5
    assert np.isinf(o.HYPOTHETICAL_tau_star_s_per_tu_median)       # median of (0.499, inf)
