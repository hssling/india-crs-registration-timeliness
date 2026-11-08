"""Reconcile the candidate national observations into one value per
year x indicator.

Preference order when a year has more than one candidate:
  1. statement2_india_row / stood_at from the report published FOR that year
     (report_year == year) -- the report's own self-reported figure.
  2. Any other observation, preferring the one from the report closest in
     time to the year it describes (most recently revised).

All candidates are kept in the audit trail column so a reader can see when
figures were revised between reports (e.g. 2011 and 2014 death registration
are each reported slightly differently by a later report than by the report
for that year itself -- this is noted, not hidden).
"""
import csv
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
IN_PATH = STUDY_ROOT / "data_extracted" / "national_level_of_registration_candidates.csv"
OUT_PATH = STUDY_ROOT / "data_extracted" / "national_trend_reconciled.csv"


def main() -> None:
    with IN_PATH.open(encoding="utf-8") as f:
        candidates = list(csv.DictReader(f))

    by_key: dict = {}
    for row in candidates:
        key = (row["indicator"], int(row["year"]))
        by_key.setdefault(key, []).append(row)

    out_rows = []
    for (indicator, year), obs in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        obs_sorted = sorted(
            obs,
            key=lambda r: (int(r["source_report"]) != year, abs(int(r["source_report"]) - year)),
        )
        chosen = obs_sorted[0]
        values = sorted({r["value_pct"] for r in obs})
        out_rows.append({
            "indicator": indicator,
            "year": year,
            "value_pct": chosen["value_pct"],
            "chosen_source_report": chosen["source_report"],
            "chosen_pattern": chosen["pattern"],
            "n_candidate_observations": len(obs),
            "distinct_values_seen": ";".join(values),
            "revised_across_reports": "yes" if len(values) > 1 else "no",
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "indicator", "year", "value_pct", "chosen_source_report", "chosen_pattern",
        "n_candidate_observations", "distinct_values_seen", "revised_across_reports",
    ]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} reconciled national observations to {OUT_PATH}")
    revised = [r for r in out_rows if r["revised_across_reports"] == "yes"]
    print(f"{len(revised)} year x indicator cells were reported with more than one distinct value across reports:")
    for r in revised:
        print(f"  {r['indicator']} {r['year']}: {r['distinct_values_seen']} -> chose {r['value_pct']} (from {r['chosen_source_report']} report)")

    for indicator in {"birth_registration", "death_registration"}:
        years = sorted(r["year"] for r in out_rows if r["indicator"] == indicator)
        missing = sorted(set(range(2009, 2025)) - set(years))
        print(f"{indicator}: covered years={years}")
        print(f"{indicator}: missing years (2009-2024)={missing}")


if __name__ == "__main__":
    main()
