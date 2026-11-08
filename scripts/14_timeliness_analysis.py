"""Aggregate the state-level time-gap data into the national timeliness trend
and the 2024 state consolidated table used in the analysis.

Timeliness (share registered within the legal 21-day window) is computed as a
volume-weighted national aggregate: sum of within-21-day registrations across
states divided by the sum of all registrations, so large states carry weight in
proportion to their event counts, exactly as the national completeness figure
does.
"""
import csv
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = STUDY_ROOT / "data_extracted"
TABLES_DIR = STUDY_ROOT / "outputs" / "tables"

NAME_CANONICAL = {
    "orissa": "Odisha", "pondicherry": "Puducherry", "uttaranchal": "Uttarakhand",
    "nct of delhi": "Delhi", "a & n islands": "A & N Islands",
    "andaman & nicobar islands": "A & N Islands", "a and n islands": "A & N Islands",
    "dadra & nagar haveli": "D & N Haveli", "dadra and nagar haveli": "D & N Haveli",
}


def canon(name):
    return NAME_CANONICAL.get(name.strip().lower(), name.strip())


def load_timeliness():
    with (DATA_DIR / "timeliness_by_state.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["report_year"] = int(r["report_year"])
        r["state"] = canon(r["state_raw"])
        for k in ("within_21d", "d21_30d", "d30d_1y", "after_1y", "total_registered"):
            r[k] = int(r[k])
    return rows


def national_timeliness_trend(rows):
    out_path = TABLES_DIR / "table_national_timeliness.csv"
    by = {}
    for r in rows:
        key = (r["report_year"], r["event"])
        agg = by.setdefault(key, {"within": 0, "after1y": 0, "total": 0})
        agg["within"] += r["within_21d"]
        agg["after1y"] += r["after_1y"]
        agg["total"] += r["total_registered"]

    years = sorted({y for (y, _e) in by})
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "birth_timely_pct", "death_timely_pct",
                    "birth_delayed_over1y_pct", "death_delayed_over1y_pct"])
        for y in years:
            b = by.get((y, "births"))
            d = by.get((y, "deaths"))
            w.writerow([
                y,
                round(100 * b["within"] / b["total"], 1) if b else "",
                round(100 * d["within"] / d["total"], 1) if d else "",
                round(100 * b["after1y"] / b["total"], 1) if b else "",
                round(100 * d["after1y"] / d["total"], 1) if d else "",
            ])
    print(f"Wrote {out_path}")
    for y in years:
        b = by.get((y, "births"))
        d = by.get((y, "deaths"))
        bt = round(100 * b["within"] / b["total"], 1) if b else None
        dt = round(100 * d["within"] / d["total"], 1) if d else None
        print(f"  {y}: birth timely {bt}%  death timely {dt}%")


def state_2024_consolidated(rows):
    """Merge 2024 completeness and timeliness by state; rank by death timeliness."""
    with (DATA_DIR / "state_level_of_registration_raw.csv").open(encoding="utf-8") as f:
        comp = {}
        for r in csv.DictReader(f):
            if int(r["report_year"]) == 2024:
                comp[canon(r["state_raw"])] = (float(r["level_births_pct"]), float(r["level_deaths_pct"]))

    tl = {}
    for r in rows:
        if r["report_year"] == 2024:
            tl.setdefault(r["state"], {})[r["event"]] = (r["timely_pct"], r["delayed_over_1y_pct"])

    out_rows = []
    for state in sorted(set(comp) & set(tl)):
        bc, dc = comp[state]
        bt = tl[state].get("births", ("", ""))
        dt = tl[state].get("deaths", ("", ""))
        out_rows.append({
            "state": state,
            "birth_completeness_pct": bc,
            "death_completeness_pct": dc,
            "birth_timely_pct": bt[0],
            "death_timely_pct": dt[0],
            "birth_delayed_over1y_pct": bt[1],
            "death_delayed_over1y_pct": dt[1],
        })
    out_rows.sort(key=lambda r: (r["death_timely_pct"] if r["death_timely_pct"] != "" else 999))

    out_path = TABLES_DIR / "table_state_2024_consolidated.csv"
    header = ["State/UT", "Birth completeness (%)", "Death completeness (%)",
              "Birth timely (%)", "Death timely (%)",
              "Birth >1yr late (%)", "Death >1yr late (%)"]
    keys = ["state", "birth_completeness_pct", "death_completeness_pct",
            "birth_timely_pct", "death_timely_pct",
            "birth_delayed_over1y_pct", "death_delayed_over1y_pct"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in out_rows:
            w.writerow([r[k] for k in keys])
    print(f"Wrote {out_path} ({len(out_rows)} states/UTs)")
    print("Lowest death timeliness (worst frontier states), 2024:")
    for r in out_rows[:8]:
        print(f"  {r['state']}: death complete {r['death_completeness_pct']}%, "
              f"death timely {r['death_timely_pct']}%")


def main():
    rows = load_timeliness()
    national_timeliness_trend(rows)
    state_2024_consolidated(rows)


if __name__ == "__main__":
    main()
