import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from schedlab.analysis import analyze, check
from schedlab.ga import DEFAULTS, METHODS, decode, encode, optimize
from schedlab.heuristics import HEURISTICS
from schedlab.model import ScheduleBuilder, bounds, make_instance, validate
from schedlab.runner import TRACE_COLUMNS, run_campaign
from schedlab.workloads import CLASSES, generate
from test_heuristics import campaign_instances
from test_model import homog, recompute_times, same

ROOT = Path(__file__).resolve().parent.parent
SEEDED = ("GA", "RANDOM-SEARCH", "HILL-CLIMB")
SMALL = dict(population=20, max_evals=300)


def small_instances(count, n=(8, 15, 30), m=(1, 2, 4), seed=21):
    classes = list(CLASSES)
    for i in range(count):
        yield generate(classes[i % 4], n[i % len(n)], m[(i // 3) % len(m)], "val", i, campaign_seed=seed)


# ---- decoder -----------------------------------------------------------------------------

def test_random_chromosomes_always_decode_to_valid_schedules():
    rng = np.random.default_rng(1)
    for inst in small_instances(120):
        for assign in (rng.integers(inst.m, size=inst.n), None):      # full and keys-only decoders
            s = decode(inst, rng.random(inst.n), assign)
            assert validate(inst, s) == []
            start, finish = recompute_times(inst, s)                   # independent of the builder
            assert np.array_equal(start, s.start) and s.makespan == finish.max()
            assert s.makespan >= bounds(inst)["lower_bound"] * (1 - 1e-12)
            if assign is not None:
                assert np.array_equal(s.proc, assign)


def test_degenerate_chromosomes_are_still_valid():
    inst = generate("irregular_hetero", 30, 4, "val", 0, campaign_seed=21)
    for keys in (np.zeros(30), np.ones(30), np.full(30, 0.5)):
        for assign in (np.zeros(30, int), np.full(30, 3)):
            assert validate(inst, decode(inst, keys, assign)) == []


def test_decode_breaks_key_ties_by_lowest_task_id():
    inst = make_instance("ties", 1, [], homog([1, 1, 1, 1], 1))
    assert decode(inst, [0.5, 0.5, 0.5, 0.5], [0, 0, 0, 0]).start.tolist() == [0, 1, 2, 3]
    assert decode(inst, [0.1, 0.9, 0.9, 0.1], [0, 0, 0, 0]).start.tolist() == [2, 0, 1, 3]


def test_decode_respects_precedence_even_when_keys_disagree():
    inst = make_instance("chain", 2, [(0, 1), (1, 2)], homog([1, 1, 1], 2))
    s = decode(inst, [0.0, 0.5, 1.0], [0, 1, 0])          # keys ask for the reverse order
    assert s.start.tolist() == [0, 1, 2] and validate(inst, s) == []


def test_keys_only_decoder_picks_earliest_finish_processor():
    inst = make_instance("het", 2, [], [[10.0, 1.0], [10.0, 1.0]])
    assert decode(inst, [0.9, 0.1], None).proc.tolist() == [1, 1]


# ---- baseline reconstruction ---------------------------------------------------------------

def test_every_heuristic_schedule_round_trips_exactly():
    """decode(encode(H)) is the identical schedule, not merely the same makespan, for all six
    insertion-based heuristics on the 500-instance campaign."""
    count = 0
    for inst in campaign_instances():
        for name, h in HEURISTICS.items():
            s = h(inst, None)[0]
            keys, assign = encode(s)
            assert keys.shape == assign.shape == (inst.n,) and np.array_equal(assign, s.proc)
            if inst.n:
                assert 0 < keys.min() and keys.max() == 1 and len(np.unique(keys)) == inst.n
            assert same(decode(inst, keys, assign), s), f"{name} on {inst.id}"
            count += 1
    assert count == 3000


# ---- exact optima on tiny instances -----------------------------------------------------

def brute_force_optimum(inst):
    """Minimum makespan over every (topological order, assignment). This is the true optimum:
    some semi-active schedule is optimal, and append mode generates exactly the semi-active schedules."""
    best = float("inf")
    for order in itertools.permutations(range(inst.n)):
        pos = {t: i for i, t in enumerate(order)}
        if any(pos[u] > pos[v] for v in range(inst.n) for u in inst.preds[v]):
            continue
        for assign in itertools.product(range(inst.m), repeat=inst.n):
            b = ScheduleBuilder(inst)
            for t in order:
                b.place(t, assign[t])
            best = min(best, max(b.avail))
    return best


def test_tiny_instances_against_exact_optimum():
    hits = dict.fromkeys(list(HEURISTICS) + list(METHODS), 0)
    insts = [generate(list(CLASSES)[i % 4], (4, 5, 6)[i % 3], 2, "val", i, campaign_seed=9) for i in range(12)]
    for inst in insts:
        opt = brute_force_optimum(inst)
        assert opt >= bounds(inst)["lower_bound"] * (1 - 1e-12)
        results = {name: h(inst, None)[0].makespan for name, h in HEURISTICS.items()}
        for method in METHODS:
            results[method] = optimize(inst, np.random.default_rng(0), method, population=20, max_evals=1000)[0].makespan
        for name, f in results.items():
            assert f >= opt * (1 - 1e-12), f"{name} beat the exact optimum on {inst.id}"   # hard assertion
            hits[name] += f <= opt * (1 + 1e-12)
    # Diagnostic only: how often each method reaches the optimum. Not a pass criterion.
    print("\noptimum reached on", len(insts), "tiny instances:", hits)


# ---- budget, seeding, elitism --------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("budget", [1, 2, 3, 19, 20, 21, 137, 300])
def test_exactly_max_evals_evaluations(method, budget):
    inst = generate("irregular_hetero", 15, 3, "val", 0, campaign_seed=21)
    s, info = optimize(inst, np.random.default_rng(0), method, population=20, max_evals=budget)
    assert info["fitness_evals"] == budget
    assert info["trace"][-1][1] == budget and info["trace"][-1][3] == s.makespan
    assert 1 <= info["last_improvement_eval"] <= budget
    assert validate(inst, s) == []


def test_trace_is_consistent_and_best_never_gets_worse():
    for inst in small_instances(12):
        for method in METHODS:
            s, info = optimize(inst, np.random.default_rng(3), method, **SMALL)
            gens, evals, elapsed, best, mean = map(np.array, zip(*info["trace"]))
            assert (np.diff(best) <= 0).all() and (np.diff(evals) > 0).all() and (np.diff(elapsed) >= 0).all()
            assert gens.tolist() == list(range(len(gens)))
            assert (mean >= best - 1e-9).all() and best[-1] == s.makespan
            assert validate(inst, s) == []


def test_seeded_methods_are_never_worse_than_their_seed_heuristics():
    for inst in small_instances(24):
        seed_best = min(HEURISTICS[h](inst, None)[0].makespan for h in DEFAULTS["seed_heuristics"])
        for method in SEEDED:
            for budget in (1, 3, 300):                                # even a tiny budget evaluates seeds first
                s, _ = optimize(inst, np.random.default_rng(5), method, population=20, max_evals=budget)
                if budget >= 3:
                    assert s.makespan <= seed_best, (method, inst.id)
                else:
                    assert s.makespan == HEURISTICS["HEFT"](inst, None)[0].makespan   # first seed only


def test_unseeded_ga_does_not_use_heuristics():
    inst = generate("irregular_hetero", 30, 4, "val", 0, campaign_seed=21)
    s, _ = optimize(inst, np.random.default_rng(0), "GA-UNSEEDED", population=20, max_evals=20)
    first = np.random.default_rng(0)
    pop_k, pop_a = first.random((20, 30)), first.integers(4, size=(20, 30))
    assert s.makespan == min(decode(inst, pop_k[i], pop_a[i]).makespan for i in range(20))


def test_methods_share_seeds_and_budget_but_differ_in_search():
    inst = generate("irregular_hetero", 30, 4, "val", 1, campaign_seed=21)
    out = {m: optimize(inst, np.random.default_rng(0), m, **SMALL) for m in SEEDED}
    assert {info["fitness_evals"] for _, info in out.values()} == {300}
    firsts = {m: info["trace"][0][3] for m, (_, info) in out.items()}
    assert firsts["GA"] <= min(HEURISTICS[h](inst, None)[0].makespan for h in DEFAULTS["seed_heuristics"])


# ---- determinism ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_same_seed_same_result_different_seed_different_search(method):
    inst = generate("irregular_hetero", 30, 4, "val", 2, campaign_seed=21)
    a, ia = optimize(inst, np.random.default_rng(7), method, **SMALL)
    b, ib = optimize(inst, np.random.default_rng(7), method, **SMALL)
    assert same(a, b) and [t[:2] + t[3:] for t in ia["trace"]] == [t[:2] + t[3:] for t in ib["trace"]]
    _, ic = optimize(inst, np.random.default_rng(8), method, **SMALL)
    assert [t[4] for t in ia["trace"]] != [t[4] for t in ic["trace"]]


# ---- edge cases and bad input ------------------------------------------------------------

@pytest.mark.parametrize("method", METHODS)
def test_edge_case_instances(method):
    empty = generate("regular", 0, 2, "val", 0)
    s, info = optimize(empty, np.random.default_rng(0), method, **SMALL)
    assert len(s.proc) == 0 and info["fitness_evals"] == 0 and validate(empty, s) == []
    one = make_instance("one", 3, [], [[9.0, 2.0, 5.0]])
    s, info = optimize(one, np.random.default_rng(0), method, **SMALL)
    assert s.makespan == 2 and info["fitness_evals"] == 300
    chain = make_instance("chain", 3, [(i, i + 1) for i in range(5)], homog([1, 2, 3, 4, 5, 6], 3))
    assert optimize(chain, np.random.default_rng(0), method, **SMALL)[0].makespan == 21
    serial = generate("irregular", 12, 1, "val", 0, campaign_seed=21)
    assert optimize(serial, np.random.default_rng(0), method, **SMALL)[0].makespan == pytest.approx(serial.cost.sum())


@pytest.mark.parametrize("settings", [
    dict(population=1), dict(elite=20, population=20), dict(elite=-1), dict(max_evals=0), dict(tournament=0),
    dict(crossover_prob=1.5), dict(key_sigma=0), dict(mutations_per_chromosome=0),
    dict(seed_heuristics=("NOPE",)), dict(popsize=10),
])
def test_bad_settings_rejected(settings):
    inst = generate("regular", 10, 2, "val", 0)
    with pytest.raises(ValueError):
        optimize(inst, np.random.default_rng(0), "GA", **settings)


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        optimize(generate("regular", 10, 2, "val", 0), np.random.default_rng(0), "PSO")


# ---- runner integration ---------------------------------------------------------------------

CONFIG = """
[campaign]
name = "ga_it"
seed = 5
workers = 1
notes = ""
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
[ga]
population = 20
max_evals = %d
seed_heuristics = ["HEFT", "MINMIN", "FCFS-EAT"]
seeds = [0, 1, 2]
"""
ALL = list(HEURISTICS) + list(METHODS)


def run(tmp_path, algorithms=ALL, timeout=60, max_evals=150):
    cfg = tmp_path / "ga_it.toml"
    cfg.write_text(CONFIG % (json.dumps(algorithms), timeout, max_evals))
    return run_campaign(cfg, tmp_path / "raw")


@pytest.fixture(scope="module")
def ga_campaign(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ga")
    raw_dir = run(tmp)
    return tmp, raw_dir, analyze(raw_dir, tmp / "results", ROOT / "configs" / "identity.toml")


def test_runner_records_ga_runs(ga_campaign):
    _, raw_dir, res = ga_campaign
    t = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    assert len(t) == 4 * (6 * 2 + 5 * 3) and set(t.status) == {"ok"} and not (t == "").any().any()
    s01 = t[t.sub_problem == "S01"]
    assert set(s01.algorithm) == set(METHODS) and set(s01.fitness_evals) == {"150"}
    assert set(s01.algo_seed) == {"0", "1", "2"} and set(t[t.sub_problem == "BASE"].algo_seed) == {"NA"}
    assert s01.groupby("algorithm").algo_config_hash.nunique().eq(1).all() and s01.algo_config_hash.nunique() == 5
    assert res["problems"] == []          # includes budget equality, seeded <= seeds, trace consistency


def test_optimization_time_is_measured_separately_from_makespan(ga_campaign):
    _, _, res = ga_campaign
    m = res["master"]
    s01 = m[m.Sub_Problem == "S01"]
    assert set(m.Time_Unit) == {"sim_tu"} and set(m.Scheduling_Time_Unit) == {"s"}
    assert (s01.Scheduling_Time > 0).all() and (s01.Scheduling_Time > m[m.Sub_Problem == "BASE"].Scheduling_Time.max()).all()
    assert (s01.Utilization > 0).all() and (s01.Utilization <= 1 + 1e-9).all()
    seeded = s01[s01.Algorithm.isin(SEEDED)]
    assert (seeded.Improvement_vs_HEFT >= -1e-12).all()       # true by construction (seeded), not evidence


def test_convergence_trace_file(ga_campaign):
    _, raw_dir, _ = ga_campaign
    trace = pd.read_csv(raw_dir / "ga_trace.csv", float_precision="round_trip")
    raw = pd.read_csv(raw_dir / "runs.csv", float_precision="round_trip")
    assert list(trace.columns) == TRACE_COLUMNS
    s01 = raw[raw.sub_problem == "S01"].set_index("run_uid")
    assert set(trace.run_uid) == set(s01.index) and len(s01) == 60
    last = trace.groupby("run_uid").last()
    assert (last.best_makespan_sim == s01.makespan_sim.reindex(last.index)).all() and (last.fitness_evals == 150).all()
    assert (trace.groupby("run_uid").elapsed_s.last() <= s01.scheduling_time_s.reindex(last.index)).all()


def test_campaign_is_reproducible(ga_campaign, tmp_path):
    _, raw_dir, _ = ga_campaign
    cols = ["instance_hash", "algorithm", "algo_seed", "makespan_sim", "busy_time_sim", "fitness_evals"]
    a = pd.read_csv(raw_dir / "runs.csv", dtype=str)[cols]
    b = pd.read_csv(run(tmp_path) / "runs.csv", dtype=str)[cols]
    assert a.equals(b)
    ga = a[a.algorithm == "GA-UNSEEDED"]
    assert ga.groupby("instance_hash").makespan_sim.nunique().max() >= 1   # seeds are separate rows, all kept


def test_ga_timeout_is_recorded_as_a_failed_row(tmp_path):
    raw_dir = run(tmp_path, ["HEFT", "GA"], timeout=0.3, max_evals=10**8)
    t = pd.read_csv(raw_dir / "runs.csv", dtype=str, keep_default_na=False)
    ga = t[t.algorithm == "GA"]
    assert len(ga) == 12 and set(ga.status) == {"timeout"} and set(t[t.algorithm == "HEFT"].status) == {"ok"}
    assert set(ga.makespan_sim) == set(ga.scheduling_time_s) == set(ga.fitness_evals) == {"NA"}
    assert (raw_dir / "ga_trace.csv").read_text().strip() == ",".join(TRACE_COLUMNS)
    assert check(raw_dir) == []
    res = analyze(raw_dir, tmp_path / "results", ROOT / "configs" / "identity.toml")
    assert len(res["master"]) == len(t) and res["master"][res["master"].Algorithm == "GA"].Speedup.isna().all()


def test_paired_table(ga_campaign):
    _, _, res = ga_campaign
    t = res["paired"]
    assert set(t.split) == {"val"} and (t.instances == 4).all()
    assert (t.better + t.tie + t.worse == t.instances).all()
    assert np.allclose(t.improvement_mean, 1 - t.ratio_mean) and (t.ratio_ci95_lo <= t.ratio_ci95_hi).all()
    ga = t[t.algorithm == "GA"].set_index("baseline")
    assert set(ga.index) == {"FCFS-EAT", "HEFT", "BEST-HEURISTIC", "GA-KEYS-EFT", "HILL-CLIMB", "RANDOM-SEARCH",
                             "GA-UNSEEDED"}
    for seed in ("HEFT", "FCFS-EAT"):                  # by construction, not evidence
        assert ga.loc[seed, "worse"] == 0 and ga.loc[seed, "ratio_max"] <= 1 + 1e-12
    assert t.wilcoxon_p.notna().sum() <= 1            # only the predeclared primary comparison is tested
    assert (res["derived"] / "s01_paired.csv").exists() and (res["derived"] / "s01_overhead_quality.csv").exists()


def test_s01_figure_files_and_data(ga_campaign):
    _, raw_dir, res = ga_campaign
    fig, m = res["figures"], res["master"]
    for stem in ("g2_opt_time_vs_size", "g2_convergence", "g3_improvement_by_class"):
        assert (fig / f"{stem}.pdf").exists() and (fig / f"{stem}.svg").read_text().count("<svg") == 1
        data = pd.read_csv(fig / f"{stem}.csv")
        assert ((data.q25 <= data["median"] + 1e-12) & (data["median"] <= data.q75 + 1e-12)).all()
    runs = pd.read_csv(fig / "g2_opt_time_vs_size_runs.csv", float_precision="round_trip")
    s01 = m[m.Sub_Problem == "S01"]
    assert set(runs.Run_ID) >= set(s01.Run_ID)       # every search run is plotted, per seed
    assert np.allclose(runs.set_index("Run_ID").Scheduling_Time[s01.Run_ID], s01.Scheduling_Time)
    conv = pd.read_csv(fig / "g2_convergence_runs.csv", float_precision="round_trip")
    last = conv[conv.evals == conv.evals.max()].set_index("Run_ID").best_over_heft
    heft = m[m.Algorithm == "HEFT"].groupby("Instance_Hash").Execution_Time.first()
    expect = (s01.set_index("Run_ID").Execution_Time / heft.reindex(s01.Instance_Hash).to_numpy())
    assert len(last) == len(s01) and np.allclose(last[s01.Run_ID], expect[s01.Run_ID], rtol=1e-12)  # ends at the result
    imp = pd.read_csv(fig / "g3_improvement_by_class_instances.csv", float_precision="round_trip")
    again = imp.groupby(["Baseline", "Group", "Algorithm"]).Improvement.median()
    data = pd.read_csv(fig / "g3_improvement_by_class.csv").set_index(["Baseline", "Group", "Algorithm"])["median"]
    assert np.allclose(data.sort_index(), again.sort_index(), rtol=1e-12)


# ---- GA-KEYS-EFT audit ----------------------------------------------------------------------

def test_keys_eft_seeds_are_decoded_not_injected():
    """GA-KEYS-EFT's seeds are heuristic *orders* decoded with its own EFT append-mode rule. With a budget of
    exactly the seed count its result is the best decoded seed, which can be worse than the heuristic itself:
    no non-representable heuristic schedule is ever kept as the incumbent."""
    seeds = DEFAULTS["seed_heuristics"]
    worse_than_heuristic = 0
    for inst in small_instances(40, n=(15, 30), m=(2, 4)):
        decoded = [decode(inst, encode(HEURISTICS[h](inst, None)[0])[0], None).makespan for h in seeds]
        s, info = optimize(inst, np.random.default_rng(0), "GA-KEYS-EFT", population=20, max_evals=len(seeds))
        assert s.makespan == min(decoded) and info["fitness_evals"] == len(seeds)
        assert validate(inst, s) == []
        worse_than_heuristic += s.makespan > min(HEURISTICS[h](inst, None)[0].makespan for h in seeds) * (1 + 1e-12)
    assert worse_than_heuristic > 0      # the limitation is real on these instances, so it must be documented


def test_final_s01_config_is_locked_to_the_predeclared_settings():
    import tomllib
    load = lambda name: tomllib.loads((ROOT / "configs" / name).read_text())
    final, full, pilot = load("s01_final.toml"), load("full.toml"), load("ga_pilot.toml")
    assert final["workload"] == full["workload"] and final["campaign"]["seed"] == full["campaign"]["seed"]
    assert final["ga"] == pilot["ga"]                 # nothing tuned after the pilot
    assert final["run"]["splits"] == ["test_id", "test_ood"] and final["run"]["algorithms"] == pilot["run"]["algorithms"]
