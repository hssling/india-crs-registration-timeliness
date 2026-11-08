"""Beta-convergence regression: does a state/UT's registration completeness
change (earliest available year to latest) depend on where it started?

This is the standard convergence-regression form used in the regional/health
inequality literature (the same logic reference 6, Basu & Adair 2021, applies
to death-registration completeness): regress the change in an indicator on
its baseline level. A negative, significant slope means low-baseline
states/UTs gained more (convergence); a null slope means gains were roughly
uniform regardless of starting point (dispersion falling only because a few
outliers moved, not because of systematic catch-up).

Run on the same earliest-vs-latest state panel as
06_build_analysis_panel.py's Table 4 (state_change_earliest_vs_latest), for
both births and deaths.
"""
import csv
from pathlib import Path

from scipy import stats

STUDY_ROOT = Path(__file__).resolve().parents[1]
IN_PATH = STUDY_ROOT / "outputs" / "tables" / "table4_state_change_earliest_vs_latest.csv"
OUT_PATH = STUDY_ROOT / "outputs" / "tables" / "table5_convergence_regression.csv"


def run_regression(baseline: list, change: list) -> dict:
    result = stats.linregress(baseline, change)
    return {
        "n": len(baseline),
        "slope": round(result.slope, 4),
        "intercept": round(result.intercept, 2),
        "r_squared": round(result.rvalue ** 2, 3),
        "p_value": result.pvalue,
        "std_err": round(result.stderr, 4),
    }


def format_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def main() -> None:
    with IN_PATH.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    births_baseline = [float(r["earliest_births_pct"]) for r in rows]
    births_change = [float(r["births_change_pp"]) for r in rows]
    deaths_baseline = [float(r["earliest_deaths_pct"]) for r in rows]
    deaths_change = [float(r["deaths_change_pp"]) for r in rows]

    births_result = run_regression(births_baseline, births_change)
    deaths_result = run_regression(deaths_baseline, deaths_change)

    out_rows = [
        {"indicator": "birth_registration", **births_result, "p_value_display": format_p(births_result["p_value"])},
        {"indicator": "death_registration", **deaths_result, "p_value_display": format_p(deaths_result["p_value"])},
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["indicator", "n", "slope", "intercept", "r_squared", "p_value_display", "std_err"]
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in out_rows:
            writer.writerow({k: row[k] for k in fieldnames})

    print(f"Wrote {OUT_PATH}")
    for row in out_rows:
        print(
            f"{row['indicator']}: n={row['n']} slope={row['slope']} "
            f"(pp change per pp of baseline) R2={row['r_squared']} "
            f"p={row['p_value_display']} intercept={row['intercept']}"
        )


if __name__ == "__main__":
    main()
