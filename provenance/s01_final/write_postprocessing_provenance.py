"""Write POSTPROCESSING_PROVENANCE.json: what produced the derived S01 outputs from the frozen raw campaign.

    python3 provenance/s01_final/write_postprocessing_provenance.py <campaign_id> <provenance json from a run> ...
Arguments after the campaign id are KEY=VALUE pairs recorded verbatim (commands, test results, times).
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from schedlab.runner import code_hash


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


camp = sys.argv[1]
extra = dict(a.split("=", 1) for a in sys.argv[2:])
raw, derived, figures = (Path("results", d, camp) for d in ("raw", "derived", "figures"))
here = Path(__file__).parent
record = dict(
    written_utc=datetime.now(timezone.utc).isoformat(),
    campaign_id=camp,
    raw_dir=str(raw),
    raw_files={f.name: sha(f) for f in sorted(raw.iterdir())},
    raw_read_only=all(not (f.stat().st_mode & 0o222) for f in raw.iterdir()),
    config_file="configs/s01_final.toml", config_sha256=sha(Path("configs/s01_final.toml")),
    execution_code_hash=json.loads((raw / "manifest.json").read_text())["code_hash"],
    analysis_code_hash=code_hash(),
    analysis_source_sha256={f.name: sha(f) for f in sorted(Path("schedlab").glob("*.py"))},
    analysis_vs_execution_diff="only schedlab/analysis.py differs; see EXECUTION_PROVENANCE.md",
    power="battery during the campaign (see EXECUTION_PROVENANCE.md)",
    derived_files={f.name: sha(f) for f in sorted(derived.iterdir())},
    figure_files={f.name: sha(f) for f in sorted(figures.iterdir())},
    provenance_files={f.name: sha(f) for f in sorted(here.glob("*")) if f.is_file()
                      and f.name != "POSTPROCESSING_PROVENANCE.json"},
    **extra,
)
(here / "POSTPROCESSING_PROVENANCE.json").write_text(json.dumps(record, indent=2))
print(json.dumps({k: v for k, v in record.items() if not k.endswith(("files", "sha256"))}, indent=2))
