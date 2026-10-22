"""CLI: python -m schedlab run --config configs/pilot.toml | python -m schedlab analyze results/raw/<campaign>"""
import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(prog="schedlab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a campaign and write raw results")
    r.add_argument("--config", required=True)
    r.add_argument("--out", default="results/raw")
    a = sub.add_parser("analyze", help="derive master.csv, tables and figures from a raw campaign directory")
    a.add_argument("raw_dir")
    a.add_argument("--out", default="results")
    a.add_argument("--identity", default="configs/identity.toml")
    a.add_argument("--final", action="store_true", help="refuse to export while identifiers are placeholders")
    t = sub.add_parser("train-selector", help="S03: fit the selector on train, choose depth/SBS on val, save it")
    t.add_argument("--config", required=True)
    t.add_argument("--ga", action="store_true", help="contingency extension: add GA-1000 (s03.model_ga), base = s03.model")
    args = ap.parse_args()

    if args.cmd == "train-selector":
        import json
        import tomllib
        from . import adaptive
        from .workloads import assert_separated, experiment_matrix
        cfg = tomllib.loads(open(args.config).read())
        matrix = experiment_matrix(cfg["workload"], cfg["campaign"]["seed"])
        assert_separated(matrix)
        if args.ga:
            base, base_id = adaptive.load(cfg["s03"]["model"])
            out = cfg["s03"]["model_ga"]
            adaptive.save(adaptive.train_selector_ga(matrix["train"], matrix["val"], base, base_id), out)
        else:
            out = cfg["s03"]["model"]
            adaptive.save(adaptive.train_selector(matrix["train"], matrix["val"]), out)
        report = json.loads(open(f"{out}/model.json").read())
        print(json.dumps({k: v for k, v in report.items() if k != "rules"}, indent=2))
        print(report["rules"])
        return 0

    if args.cmd == "run":
        from .analysis import load_raw
        from .runner import run_campaign
        out = run_campaign(args.config, args.out)
        raw, manifest = load_raw(out)
        print(f"{out}\nrows: {manifest['row_count']}  not ok: {manifest['failed_count']}  "
              f"wall: {manifest['wall_time_s']:.2f} s  splits: {manifest['split_counts']}")
        return int((raw.status == "invalid").any())

    import pandas as pd
    from .analysis import analyze
    res = analyze(args.raw_dir, args.out, args.identity, args.final)
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.float_format", "{:.6g}".format)
    print(res["summary"].to_string(index=False), "\n")
    print(res["timing"].to_string(index=False), "\n")
    if len(res["paired"]):
        cols = ["algorithm", "baseline", "split", "instances", "improvement_mean", "ratio_ci95_lo", "ratio_ci95_hi",
                "improvement_geomean", "better", "tie", "worse", "wilcoxon_p"]
        print(res["paired"][cols].to_string(index=False), "\n")
        print(res["overhead"].to_string(index=False), "\n")
    print(f"derived: {res['derived']}\nfigures: {res['figures']}")
    if res["placeholders"]:
        print("WARNING: Student_ID / Batch_ID are placeholders (configs/identity.toml). Not a final export.")
    for p in res["problems"]:
        print("CHECK FAILED:", p)
    print("campaign checks:", "all passed" if not res["problems"] else f"{len(res['problems'])} failed")
    return int(bool(res["problems"]))


sys.exit(main())
