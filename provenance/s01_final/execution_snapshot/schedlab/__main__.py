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
    args = ap.parse_args()

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
