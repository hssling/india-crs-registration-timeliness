"""Three further analyses that turn the descriptive trend into an analytical
account of what moved, what didn't, and where to act next:

1. Institutional-contact trend vs completeness trend. If institutional
   birth/death share is flat or falling while completeness rises, the
   national improvement is not primarily a facility-contact story -- a
   national-time-series counterpart to the district-level cross-sectional
   finding that institutional births predict birth but not death
   registration in household survey evidence).
2. A simple before/after comparison of the average annual pace of national
   improvement, split at the 2023 RBD Act amendment. With only two
   post-amendment data points (2023, 2024) this is a descriptive comparison
   of average annual pace, not a powered structural-break test, and is
   reported as such.
3. A priority-audit ranking of states/UTs combining latest-year death-
   registration gap, direction of travel (still improving vs regressing),
   and denominator-flag frequency, giving a concrete, ranked target list
   for administrative attention.
"""
import csv
import statistics
from pathlib import Path

STUDY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = STUDY_ROOT / "data_extracted"
TABLES_DIR = STUDY_ROOT / "outputs" / "tables"


def institutional_share_vs_completeness() -> None:
    with (DATA_DIR / "institutional_share_national.csv").open(encoding="utf-8") as f:
        share_rows = list(csv.DictReader(f))
    with (DATA_DIR / "national_trend_reconciled.csv").open(encoding="utf-8") as f:
        trend_rows = list(csv.DictReader(f))

    births_share = {int(r["year"]): float(r["value_pct"]) for r in share_rows if r["indicator"] == "institutional_birth_share_pct"}
    deaths_share = {int(r["year"]): float(r["value_pct"]) for r in share_rows if r["indicator"] == "institutional_death_share_pct"}
    births_level = {int(r["year"]): float(r["value_pct"]) for r in trend_rows if r["indicator"] == "birth_registration"}
    deaths_level = {int(r["year"]): float(r["value_pct"]) for r in trend_rows if r["indicator"] == "death_registration"}

    out_path = TABLES_DIR / "table6_institutional_share_vs_completeness.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "institutional_birth_share_pct", "birth_registration_pct", "institutional_death_share_pct", "death_registration_pct"])
        for year in sorted(set(births_share) | set(deaths_share) | set(births_level) | set(deaths_level)):
            writer.writerow([
                year,
                births_share.get(year, ""),
                births_level.get(year, ""),
                deaths_share.get(year, ""),
                deaths_level.get(year, ""),
            ])
    print(f"Wrote {out_path}")

    years_d = sorted(set(deaths_share) & set(deaths_level))
    first_y, last_y = years_d[0], years_d[-1]
    print(
        f"Institutional death share: {deaths_share[first_y]}% ({first_y}) -> {deaths_share[last_y]}% ({last_y}), "
        f"while death registration rose {deaths_level[first_y]}% -> {deaths_level[last_y]}%"
    )
    years_b = sorted(y for y in (set(births_share) & set(births_level)) if y != 2011)  # 2011 flagged as an outlier
    first_yb, last_yb = years_b[0], years_b[-1]
    print(
        f"Institutional birth share (excl. 2011 outlier): {births_share[first_yb]}% ({first_yb}) -> "
        f"{births_share[last_yb]}% ({last_yb}), while birth registration rose {births_level[first_yb]}% -> {births_level[last_yb]}%"
    )


def pre_post_2023_pace() -> None:
    with (DATA_DIR / "national_trend_reconciled.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    deaths = {int(r["year"]): float(r["value_pct"]) for r in rows if r["indicator"] == "death_registration"}
    births = {int(r["year"]): float(r["value_pct"]) for r in rows if r["indicator"] == "birth_registration"}

    # Restrict to the 2009-2024 study window; earlier years (2000, 2002, 2003)
    # are historical context only, extracted from retrospective mentions, and
    # would otherwise silently stretch the "pre-amendment" span across a
    # 2003-2009 gap with no data in between.
    deaths = {y: v for y, v in deaths.items() if y >= 2009}
    births = {y: v for y, v in births.items() if y >= 2009}

    out_path = TABLES_DIR / "table7_pre_post_2023_pace.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["indicator", "period", "years_spanned", "total_change_pp", "avg_annual_pp"])
        for name, series in (("birth_registration", births), ("death_registration", deaths)):
            pre_years = sorted(y for y in series if y <= 2022)
            post_years = sorted(y for y in series if y >= 2022)
            pre_span = pre_years[-1] - pre_years[0]
            pre_change = series[pre_years[-1]] - series[pre_years[0]]
            post_span = post_years[-1] - post_years[0]
            post_change = series[post_years[-1]] - series[post_years[0]]
            writer.writerow([name, f"{pre_years[0]}-{pre_years[-1]} (pre-amendment)", pre_span, round(pre_change, 1), round(pre_change / pre_span, 2)])
            writer.writerow([name, f"{post_years[0]}-{post_years[-1]} (post-amendment)", post_span, round(post_change, 1), round(post_change / post_span, 2)])
    print(f"Wrote {out_path}")


def priority_ranking() -> None:
    with (TABLES_DIR / "table4_state_change_earliest_vs_latest.csv").open(encoding="utf-8") as f:
        change_rows = {r["state"]: r for r in csv.DictReader(f)}
    with (TABLES_DIR / "table3_denominator_flags.csv").open(encoding="utf-8") as f:
        flag_rows = list(csv.DictReader(f))

    flag_counts: dict = {}
    for r in flag_rows:
        flag_counts[r["state"]] = flag_counts.get(r["state"], 0) + 1

    out_rows = []
    for state, r in change_rows.items():
        latest_gap = float(r["latest_gap_pp"])
        deaths_change = float(r["deaths_change_pp"])
        direction = "regressing" if deaths_change < 0 else "improving"
        flags = flag_counts.get(state, 0)
        # Priority score: larger current gap, a regressing trend, and more
        # years flagged for the denominator-plausibility pattern all raise
        # priority for administrative audit. Regressing states get a fixed
        # penalty rather than being scaled by the (typically small) negative
        # change, since direction matters more here than magnitude.
        score = latest_gap + (15 if direction == "regressing" else 0) + 2 * flags
        out_rows.append({
            "state": state,
            "latest_year": r["latest_year"],
            "latest_births_pct": r["latest_births_pct"],
            "latest_deaths_pct": r["latest_deaths_pct"],
            "latest_gap_pp": r["latest_gap_pp"],
            "deaths_change_pp": r["deaths_change_pp"],
            "direction": direction,
            "years_flagged_denominator": flags,
            "priority_score": round(score, 1),
        })

    out_rows.sort(key=lambda r: -r["priority_score"])
    out_path = TABLES_DIR / "table8_priority_audit_ranking.csv"
    fieldnames = ["state", "latest_year", "latest_births_pct", "latest_deaths_pct", "latest_gap_pp", "deaths_change_pp", "direction", "years_flagged_denominator", "priority_score"]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {out_path}")
    print("Top 10 priority states/UTs for civil registration audit:")
    for r in out_rows[:10]:
        print(f"  {r['state']}: score={r['priority_score']} gap={r['latest_gap_pp']}pp direction={r['direction']} flags={r['years_flagged_denominator']}")


def main() -> None:
    institutional_share_vs_completeness()
    pre_post_2023_pace()
    priority_ranking()


if __name__ == "__main__":
    main()
