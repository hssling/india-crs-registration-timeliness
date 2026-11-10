#!/usr/bin/env python3
"""Validation of the timeliness proxies, their sensitivity to the modelled
denominator, and tests of whether state convergence in completeness could be
produced mechanically.

1. Benchmark. Delhi's registered counts in the 2022-2024 reports are restricted
   to events that occurred and were registered in the same calendar year (the
   reports' own notes), so within-21-day registrations divided by that count is
   an occurrence-based, year-end-censored timeliness against which the
   registration-year and recent-event measures can be compared. Goa's counts
   exclude registrations made more than one year late, so they must equal the
   time-gap total minus the more-than-one-year band: an exact tie-out of the
   recent-event denominator.
2. Bracket. Registration-year timeliness (lower) and recent-event timeliness
   (upper) bracket occurrence-cohort timeliness among registered events when
   the late registrations a cohort will eventually receive do not exceed those
   made during the year. Claims are classified by whether they hold at both
   ends of the bracket.
3. Denominator sensitivity of timely coverage: state-specific multiplicative
   errors (log-normal, SD 10% and 20%) on estimated events, 2,000 draws; the
   probability that each state remains among the five lowest.
4. Mechanics of convergence. (a) Test-retest reliability of the completeness
   measure from adjacent years (2010, 2011); the slope that regression to the
   mean alone could produce is about -(1 - r). (b) Ceiling-only null: every
   state receives the same expected gain, plus noise, and values are capped at
   100% as in publication; the distribution of the convergence slope under this
   null is compared with the observed slope.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT
EXTRACTED = ROOT / "data_extracted"
PDF_2024 = ROOT / "source_reports" / "CRS" / "2024.pdf"
TABLES = ROOT / "outputs" / "tables"
DATA = ROOT / "data_extracted"
RNG = np.random.default_rng(20261110)
logging.getLogger("pdfminer").setLevel(logging.ERROR)

CANON = {"ddieulh i": "Delhi", "d & n haveli and daman &": "D & N Haveli and Daman & Diu",
         "d & n haveli and daman & diu": "D & N Haveli and Daman & Diu"}
BOUNDARY_CHANGED = {"Telangana", "Andhra Pradesh", "Jammu & Kashmir", "Ladakh",
                    "D & N Haveli and Daman & Diu", "Daman & Diu", "D & N Haveli"}
VALUES: dict = {}


def canon(name: str) -> str:
    key = " ".join(str(name).split()).lower()
    return CANON.get(key, " ".join(str(name).split()))


def statement_rows(header: str, states: tuple[str, ...]) -> dict:
    """Year-by-year registered counts (Statement 10 or 11 of the 2024 report)."""
    out = {}
    with pdfplumber.open(str(PDF_2024)) as pdf:
        for page in pdf.pages:
            if header not in (page.extract_text() or ""):
                continue
            for table in page.extract_tables():
                years = None
                for row in table:
                    cells = [c for c in row if c not in (None, "")]
                    if years is None and sum(bool(re.fullmatch(r"20\d\d", str(c))) for c in cells) >= 5:
                        years = [int(c) for c in cells if re.fullmatch(r"20\d\d", str(c))]
                        continue
                    names = [c for c in cells if re.search(r"[A-Za-z]{3}", str(c))]
                    if years and names and canon(names[0]) in states:
                        nums = [int(c) for c in cells if re.fullmatch(r"\d+", str(c))]
                        out[canon(names[0])] = dict(zip(years[-len(nums):], nums))
            break
    return out


COUNTS = DATA / "registered_counts_delhi_goa.csv"


def registered_counts() -> tuple[dict, dict]:
    """Published registered counts for Delhi and Goa, 2022-2024 (Statements 10
    and 11 of the 2024 report). Read from the extracted file when present, so
    the analysis reproduces without the report PDF; otherwise extracted once."""
    if not COUNTS.exists():
        rows = []
        for event, header in (("births", "Statement 10: Number of registered births"),
                              ("deaths", "Statement 11: Number of registered deaths")):
            for state, by_year in statement_rows(header, ("Delhi", "Goa")).items():
                for year, n in by_year.items():
                    if year >= 2022:
                        rows.append({"event": event, "state": state, "year": year, "registered": n})
        pd.DataFrame(rows).to_csv(COUNTS, index=False)
    c = pd.read_csv(COUNTS)
    out = {}
    for event in ("births", "deaths"):
        out[event] = {s: dict(zip(g.year, g.registered)) for s, g in c[c.event == event].groupby("state")}
    return out["births"], out["deaths"]


def benchmark(tg: pd.DataFrame) -> pd.DataFrame:
    births, deaths = registered_counts()
    rows, tie = [], []
    for event, counts in (("births", births), ("deaths", deaths)):
        for year in (2022, 2023, 2024):
            r = tg[(tg.state == "Delhi") & (tg.event == event) & (tg.report_year == year)].iloc[0]
            occurred = counts["Delhi"][year]
            rows.append({"year": year, "event": event,
                         "registration_year": round(100 * r.within_21d / r.total_registered, 1),
                         "recent_event": round(100 * r.within_21d / (r.total_registered - r.after_1y), 1),
                         "occurrence_based": round(100 * r.within_21d / occurred, 1),
                         "occurred_and_registered": occurred, "within_21d": int(r.within_21d)})
            g = tg[(tg.state == "Goa") & (tg.event == event) & (tg.report_year == year)].iloc[0]
            tie.append({"year": year, "event": event,
                        "timegap_total_minus_over1y": int(g.total_registered - g.after_1y),
                        "published_registered": counts["Goa"][year]})
    b = pd.DataFrame(rows)
    b["gap_registration_year"] = (b.occurrence_based - b.registration_year).round(1)
    b["gap_recent_event"] = (b.occurrence_based - b.recent_event).round(1)
    b.to_csv(TABLES / "proxy_benchmark_delhi.csv", index=False)
    t = pd.DataFrame(tie)
    t["difference"] = t.published_registered - t.timegap_total_minus_over1y
    t.to_csv(TABLES / "goa_tieout.csv", index=False)
    VALUES["goa_tieout_max_abs_difference"] = int(t.difference.abs().max())
    VALUES["delhi_gap_ryt_range"] = [float(b.gap_registration_year.min()), float(b.gap_registration_year.max())]
    VALUES["delhi_gap_ret_range"] = [float(b.gap_recent_event.min()), float(b.gap_recent_event.max())]
    VALUES["delhi_ret_closer_all"] = bool((b.gap_recent_event.abs() < b.gap_registration_year.abs()).all())
    return b, t


def bracket_claims() -> None:
    nat = pd.read_csv(TABLES / "national_timeliness_accounting.csv").set_index(["report_year", "event"])
    st = pd.read_csv(TABLES / "state_2024_timeliness_accounting.csv")
    d_b = nat.loc[(2024, "births"), "ryt"] - nat.loc[(2022, "births"), "ryt"]
    d_u = nat.loc[(2024, "births"), "ret"] - nat.loc[(2022, "births"), "ret"]
    VALUES["national_birth_change_2022_2024_lower"] = round(float(d_b), 1)
    VALUES["national_birth_change_2022_2024_upper"] = round(float(d_u), 1)
    lo5 = set(st.nsmallest(5, "ryt_deaths").state)
    up5 = set(st.nsmallest(5, "ret_deaths").state)
    VALUES["death_bottom5_both_bounds"] = sorted(lo5 & up5)
    # Highest upper bound among the five: they are low even on the generous measure
    VALUES["death_bottom5_max_upper"] = float(st[st.state.isin(lo5)].ret_deaths.max())
    VALUES["death_national_upper_2024"] = float(nat.loc[(2024, "deaths"), "ret"])
    VALUES["nagaland_birth_bracket"] = [float(st.set_index("state").loc["Nagaland", "ryt_births"]),
                                        float(st.set_index("state").loc["Nagaland", "ret_births"])]


def denominator_sensitivity() -> pd.DataFrame:
    st = pd.read_csv(TABLES / "state_2024_timeliness_accounting.csv")
    rows = []
    for event in ("deaths", "births"):
        base = st[f"tc_{event}"].to_numpy()
        base_bottom = set(st.nsmallest(5, f"tc_{event}").state)
        for sd in (0.10, 0.20):
            hits = np.zeros(len(st))
            rhos = []
            for _ in range(2000):
                err = np.exp(RNG.normal(0, sd, len(st)))
                sim = base / err                     # denominator scaled by err
                order = np.argsort(sim)[:5]
                hits[order] += 1
                rhos.append(stats.spearmanr(base, sim)[0])
            for i, s in enumerate(st.state):
                if s in base_bottom or hits[i] / 2000 >= 0.2:
                    rows.append({"event": event, "denominator_error_sd": sd, "state": s,
                                 "timely_coverage": float(base[i]),
                                 "prob_lowest_five": round(hits[i] / 2000, 2),
                                 "median_rank_rho": round(float(np.median(rhos)), 2)})
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "timely_coverage_denominator_sensitivity.csv", index=False)
    d = out[(out.event == "deaths") & (out.denominator_error_sd == 0.20)]
    VALUES["tc_deaths_sd20_prob"] = dict(zip(d.state, d.prob_lowest_five))
    VALUES["tc_deaths_sd20_rho"] = float(d.median_rank_rho.iloc[0])
    d10 = out[(out.event == "deaths") & (out.denominator_error_sd == 0.10)]
    VALUES["tc_deaths_sd10_prob"] = dict(zip(d10.state, d10.prob_lowest_five))
    return out


def mechanics() -> pd.DataFrame:
    p = pd.read_csv(EXTRACTED / "state_level_of_registration_raw.csv")
    p = p[~p.state_raw.str.strip().str.lower().str.startswith("ii)")].copy()
    p["state"] = p.state_raw.map(canon)
    w = p.pivot_table(index="state", columns="report_year", values=["level_births_pct", "level_deaths_pct"])
    common = [s for s in w.index if s not in BOUNDARY_CHANGED
              and not np.isnan(w.loc[s, ("level_births_pct", 2010)])
              and not np.isnan(w.loc[s, ("level_births_pct", 2024)])]
    rows = []
    for ind, label in (("level_births_pct", "births"), ("level_deaths_pct", "deaths")):
        x0 = w.loc[common, (ind, 2010)].to_numpy()
        x1 = w.loc[common, (ind, 2024)].to_numpy()
        x11 = w.loc[common, (ind, 2011)].to_numpy()
        ok = ~np.isnan(x11)
        # reliability from adjacent years among states not at the ceiling in either year
        nc = ok & (x0 < 100) & (x11 < 100)
        r_adj = stats.pearsonr(x0[nc], x11[nc])[0]
        obs = stats.linregress(x0, x1 - x0)
        resid_sd = float(np.std((x1 - x0) - (obs.intercept + obs.slope * x0), ddof=2))
        # ceiling-only null: common expected gain g, noise, cap at 100.
        # g is calibrated so that the simulated mean 2024 level matches the observed one.
        target = x1.mean()
        lo, hi = -50.0, 100.0
        for _ in range(60):
            g = (lo + hi) / 2
            sims = np.minimum(100, x0[None, :] + g + RNG.normal(0, resid_sd, (400, len(x0))))
            lo, hi = (g, hi) if sims.mean() < target else (lo, g)
        slopes = []
        for _ in range(2000):
            sim = np.minimum(100, x0 + g + RNG.normal(0, resid_sd, len(x0)))
            slopes.append(stats.linregress(x0, sim - x0).slope)
        slopes = np.array(slopes)
        rows.append({"event": label, "n": len(common), "observed_slope": round(obs.slope, 2),
                     "adjacent_year_r": round(r_adj, 3), "n_reliability": int(nc.sum()),
                     "rtm_slope_bound": round(-(1 - r_adj), 3),
                     "null_common_gain_pp": round(g, 1), "null_noise_sd_pp": round(resid_sd, 1),
                     "null_slope_mean": round(float(slopes.mean()), 2),
                     "null_slope_p2_5": round(float(np.percentile(slopes, 2.5)), 2),
                     "null_slope_p97_5": round(float(np.percentile(slopes, 97.5)), 2),
                     "share_null_at_least_as_negative": round(float((slopes <= obs.slope).mean()), 3)})
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "convergence_mechanics.csv", index=False)
    for r in rows:
        VALUES[f"mech_{r['event']}"] = r
    return out


def main() -> None:
    tg = pd.read_csv(EXTRACTED / "timeliness_by_state.csv")
    tg["state"] = tg.state_raw.map(canon)
    b, t = benchmark(tg)
    bracket_claims()
    sens = denominator_sensitivity()
    mech = mechanics()
    (TABLES / "values_bounds_and_mechanics.json").write_text(json.dumps(VALUES, indent=1, default=str), encoding="utf-8")
    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(b.to_string(), "\n", t.to_string(), "\n", sens.to_string(), "\n", mech.to_string())
    print(json.dumps({k: v for k, v in VALUES.items() if not k.startswith("mech_")}, indent=1, default=str))


if __name__ == "__main__":
    main()
