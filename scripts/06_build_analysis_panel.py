"""Combine the reconciled national trend, the state/UT panel, and the SRS
national benchmark into analysis-ready tables, and compute the trend/
convergence statistics:
  - National trend 2009-2024.
  - Cross-state dispersion (coefficient of variation, max-min range) in each
    year that has a state table, to test whether the divide is narrowing or
    the national aggregate is just being pulled up by a few large states.
  - Per-state change between the earliest and latest available year, ranked,
    to identify which states closed the gap and which did not.
  - A flag for state-years where births registration is capped at 100.0%
    while deaths registration is far lower in the same state-year --
    the denominator-plausibility pattern noted during extraction (not proof
    of an error, but worth surfacing rather than treating all 100.0% values
    as equally meaningful).
"""
import csv
import statistics
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = STUDY_ROOT / "data_extracted"
OUT_DIR = STUDY_ROOT / "outputs"

NFHS5_WINDOW = (2019, 2021)
CAP_FLAG_THRESHOLD_BIRTHS = 100.0
CAP_FLAG_GAP_THRESHOLD = 30.0  # percentage points

NAME_CANONICAL = {
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "uttaranchal": "Uttarakhand",
    "nct of delhi": "Delhi",
    "andaman & nicobar islands": "A & N Islands",
    "a and n islands": "A & N Islands",
    "dadra & nagar haveli": "D & N Haveli",
    "dadra and nagar haveli": "D & N Haveli",
}


def canonical_state(name: str) -> str:
    key = name.strip().lower()
    return NAME_CANONICAL.get(key, name.strip())


def load_state_panel() -> list:
    path = DATA_DIR / "state_level_of_registration_raw.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["state"] = canonical_state(r["state_raw"])
        r["report_year"] = int(r["report_year"])
        r["level_births_pct"] = float(r["level_births_pct"])
        r["level_deaths_pct"] = float(r["level_deaths_pct"])
    return rows


def load_national_trend() -> list:
    path = DATA_DIR / "national_trend_reconciled.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["year"] = int(r["year"])
        r["value_pct"] = float(r["value_pct"])
    return rows


def national_summary(national_rows: list) -> None:
    out_path = OUT_DIR / "tables" / "table1_national_trend.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "birth_registration_pct", "death_registration_pct", "gap_pp", "nfhs5_window"])
        by_year = {}
        for r in national_rows:
            by_year.setdefault(r["year"], {})[r["indicator"]] = r["value_pct"]
        for year in sorted(by_year):
            vals = by_year[year]
            b = vals.get("birth_registration")
            d = vals.get("death_registration")
            gap = round(b - d, 1) if (b is not None and d is not None) else ""
            in_window = "yes" if NFHS5_WINDOW[0] <= year <= NFHS5_WINDOW[1] else "no"
            writer.writerow([year, b if b is not None else "", d if d is not None else "", gap, in_window])
    print(f"Wrote {out_path}")


def state_dispersion(state_rows: list) -> None:
    out_path = OUT_DIR / "tables" / "table2_state_dispersion_by_year.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_year: dict = {}
    for r in state_rows:
        by_year.setdefault(r["report_year"], []).append(r)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "year", "n_states", "births_mean", "births_cv_pct", "births_range_pp",
            "deaths_mean", "deaths_cv_pct", "deaths_range_pp",
        ])
        for year in sorted(by_year):
            recs = by_year[year]
            births = [r["level_births_pct"] for r in recs]
            deaths = [r["level_deaths_pct"] for r in recs]

            def cv(values):
                m = statistics.mean(values)
                if m == 0:
                    return 0.0
                sd = statistics.pstdev(values)
                return round(100 * sd / m, 1)

            writer.writerow([
                year, len(recs),
                round(statistics.mean(births), 1), cv(births), round(max(births) - min(births), 1),
                round(statistics.mean(deaths), 1), cv(deaths), round(max(deaths) - min(deaths), 1),
            ])
    print(f"Wrote {out_path}")


def capped_births_low_deaths_flags(state_rows: list) -> None:
    out_path = OUT_DIR / "tables" / "table3_denominator_flags.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    flagged = [
        r for r in state_rows
        if r["level_births_pct"] >= CAP_FLAG_THRESHOLD_BIRTHS
        and (r["level_births_pct"] - r["level_deaths_pct"]) >= CAP_FLAG_GAP_THRESHOLD
    ]
    flagged.sort(key=lambda r: (-r["report_year"], r["level_deaths_pct"]))
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["report_year", "state", "level_births_pct", "level_deaths_pct", "gap_pp"])
        for r in flagged:
            writer.writerow([
                r["report_year"], r["state"], r["level_births_pct"], r["level_deaths_pct"],
                round(r["level_births_pct"] - r["level_deaths_pct"], 1),
            ])
    print(f"Wrote {out_path} ({len(flagged)} state-year rows flagged: births=100.0% with deaths >={CAP_FLAG_GAP_THRESHOLD}pp lower)")


def earliest_vs_latest_state_change(state_rows: list) -> None:
    out_path = OUT_DIR / "tables" / "table4_state_change_earliest_vs_latest.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_state: dict = {}
    for r in state_rows:
        by_state.setdefault(r["state"], []).append(r)

    rows_out = []
    for state, recs in by_state.items():
        recs.sort(key=lambda r: r["report_year"])
        earliest, latest = recs[0], recs[-1]
        if earliest["report_year"] == latest["report_year"]:
            continue
        rows_out.append({
            "state": state,
            "earliest_year": earliest["report_year"],
            "earliest_births_pct": earliest["level_births_pct"],
            "earliest_deaths_pct": earliest["level_deaths_pct"],
            "latest_year": latest["report_year"],
            "latest_births_pct": latest["level_births_pct"],
            "latest_deaths_pct": latest["level_deaths_pct"],
            "births_change_pp": round(latest["level_births_pct"] - earliest["level_births_pct"], 1),
            "deaths_change_pp": round(latest["level_deaths_pct"] - earliest["level_deaths_pct"], 1),
            "latest_gap_pp": round(latest["level_births_pct"] - latest["level_deaths_pct"], 1),
        })

    rows_out.sort(key=lambda r: r["deaths_change_pp"])
    fieldnames = [
        "state", "earliest_year", "earliest_births_pct", "earliest_deaths_pct",
        "latest_year", "latest_births_pct", "latest_deaths_pct",
        "births_change_pp", "deaths_change_pp", "latest_gap_pp",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"Wrote {out_path} ({len(rows_out)} states/UTs)")


def main() -> None:
    national_rows = load_national_trend()
    state_rows = load_state_panel()

    national_summary(national_rows)
    state_dispersion(state_rows)
    capped_births_low_deaths_flags(state_rows)
    earliest_vs_latest_state_change(state_rows)


if __name__ == "__main__":
    main()
