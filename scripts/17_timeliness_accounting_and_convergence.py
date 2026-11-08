#!/usr/bin/env python3
"""Analyses of registration timeliness and state convergence in completeness.

1. Timeliness accounting. The CRS time-gap table classifies the registrations
   MADE in a calendar year by delay band (within 21 days; 22-30 days; 31 days to
   one year; more than one year). The published percentage registered within
   21 days is therefore registration-year timeliness (RYT): its denominator mixes
   the year's own events with late registrations of events from earlier years.
   Occurrence-cohort timeliness (OCT), the share of the events occurring in a
   year that are registered within 21 days, needs linked event-level dates and is
   not published. Two published-data measures bracket it:

   * recent-event timeliness (RET) = within-21-day / (all registrations minus
     those more than one year late). Removing registrations that certainly belong
     to earlier cohorts gives an upper approximation of OCT among registered
     events, because each cohort's own eventual >1-year registrations are
     excluded.
   * timely coverage (TC) = within-21-day registrations / estimated events of the
     year. A registration within 21 days of the event belongs to the current
     occurrence year (apart from a symmetric 21-day boundary at the turn of the
     year), so the numerator is cohort-specific by construction; TC is the
     closest published-data analogue of OCT among all events, but it inherits the
     modelled denominator. TC = completeness x RYT when completeness is uncapped.
   * recent-registration coverage (RC) = (registrations minus those more than one
     year late) / estimated events; an approximation of the share of a year's
     events registered within one year, assuming stable flows.

2. Convergence. Primary beta-convergence regression reproduced with 95% CIs,
   then sensitivity specifications for unequal windows and boundary changes,
   ceiling censoring, regression to the mean, and proportional gap closure; and
   sigma-convergence on a balanced panel with the count of units at the 100%
   ceiling.

Inputs are read-only: data_extracted/*.csv and
data_extracted/state_events_2024.csv (from 16_extract_events_2024.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT
EXTRACTED = ROOT / "data_extracted"
TABLES = ROOT / "outputs" / "tables"
DATA = ROOT / "data_extracted"
TABLES.mkdir(exist_ok=True)

CANON = {
    "orissa": "Odisha", "pondicherry": "Puducherry", "uttaranchal": "Uttarakhand",
    "nct of delhi": "Delhi", "ddieulh i": "Delhi",
    "andaman & nicobar islands": "A & N Islands", "a and n islands": "A & N Islands",
    "dadra & nagar haveli": "D & N Haveli", "dadra and nagar haveli": "D & N Haveli",
    "d & n haveli and daman &": "D & N Haveli and Daman & Diu",
    "d & n haveli & daman & diu": "D & N Haveli and Daman & Diu",
    "d & n haveli and daman & diu": "D & N Haveli and Daman & Diu",
}
NON_STATE = {"ii) percentage of infant death to total deaths"}
# Units whose territory changed inside the study window, or that exist for only
# part of it.
BOUNDARY_CHANGED = {"Telangana", "Andhra Pradesh", "Jammu & Kashmir", "Ladakh",
                    "D & N Haveli and Daman & Diu", "Daman & Diu", "D & N Haveli"}

VALUES: dict = {}


def canon(name: str) -> str:
    key = " ".join(str(name).split()).lower()
    return CANON.get(key, " ".join(str(name).split()))


def r1(x: float) -> float:
    return float(np.round(x + 1e-9, 1))


# --------------------------------------------------------------------------
# 1. Timeliness accounting
# --------------------------------------------------------------------------
def load_timegap() -> pd.DataFrame:
    tg = pd.read_csv(EXTRACTED / "timeliness_by_state.csv")
    tg["state"] = tg["state_raw"].map(canon)
    if tg.duplicated(["report_year", "event", "state"]).any():
        raise SystemExit("duplicate state rows after name repair")
    return tg


def national_timeliness(tg: pd.DataFrame) -> pd.DataFrame:
    g = tg.groupby(["report_year", "event"]).agg(
        units=("state", "nunique"), within=("within_21d", "sum"), d21_30=("d21_30d", "sum"),
        d30_1y=("d30d_1y", "sum"), after=("after_1y", "sum"), total=("total_registered", "sum"),
    ).reset_index()
    g["ryt"] = 100 * g.within / g.total
    g["band_21_30"] = 100 * g.d21_30 / g.total
    g["band_30_1y"] = 100 * g.d30_1y / g.total
    g["over1y"] = 100 * g.after / g.total
    g["ret"] = 100 * g.within / (g.total - g.after)
    est = pd.read_csv(DATA / "national_estimated_events.csv")
    rows = []
    for _, r in g.iterrows():
        e = est[est.year == r.report_year]
        estimated = (e[f"estimated_{r.event}"].iloc[0] if len(e) else np.nan)
        rows.append({**r.to_dict(),
                     "tc": 100 * r.within / estimated if len(e) else np.nan,
                     "rc": 100 * (r.total - r.after) / estimated if len(e) else np.nan})
    out = pd.DataFrame(rows)
    for c in ("ryt", "band_21_30", "band_30_1y", "over1y", "ret", "tc", "rc"):
        out[c] = out[c].map(lambda v: r1(v) if pd.notna(v) else v)
    out.to_csv(TABLES / "national_timeliness_accounting.csv", index=False)
    return out


def state_2024(tg: pd.DataFrame) -> pd.DataFrame:
    ev = pd.read_csv(DATA / "state_events_2024.csv")
    ev["state"] = ev["state"].map(canon)
    t24 = tg[tg.report_year == 2024]
    rows = []
    for _, e in ev[ev.state != "India"].iterrows():
        rec = {"state": e.state,
               "comp_births": e.level_births_pct, "comp_deaths": e.level_deaths_pct,
               "ratio_births": e.ratio_births_pct, "ratio_deaths": e.ratio_deaths_pct}
        ok = True
        for event in ("births", "deaths"):
            row = t24[(t24.state == e.state) & (t24.event == event)]
            if row.empty:
                ok = False
                break
            row = row.iloc[0]
            est = e[f"estimated_{event}"]
            rec[f"ryt_{event}"] = r1(100 * row.within_21d / row.total_registered)
            rec[f"over1y_{event}"] = r1(100 * row.after_1y / row.total_registered)
            rec[f"ret_{event}"] = r1(100 * row.within_21d / (row.total_registered - row.after_1y))
            rec[f"tc_{event}"] = r1(100 * row.within_21d / est)
            rec[f"rc_{event}"] = r1(100 * (row.total_registered - row.after_1y) / est)
        if ok:
            rows.append(rec)
        else:
            VALUES.setdefault("excluded_from_timegap_2024", []).append(e.state)
    df = pd.DataFrame(rows).sort_values(["ryt_deaths", "state"]).reset_index(drop=True)
    df.to_csv(TABLES / "state_2024_timeliness_accounting.csv", index=False)

    # How far do state rankings depend on the timeliness definition?
    for event in ("births", "deaths"):
        for alt in ("ret", "tc"):
            rho, p = stats.spearmanr(df[f"ryt_{event}"], df[f"{alt}_{event}"])
            VALUES[f"spearman_ryt_{alt}_{event}"] = round(float(rho), 2)
            VALUES[f"spearman_ryt_{alt}_{event}_p"] = float(p)
        bottom_ryt = set(df.nsmallest(5, f"ryt_{event}").state)
        bottom_tc = set(df.nsmallest(5, f"tc_{event}").state)
        bottom_ret = set(df.nsmallest(5, f"ret_{event}").state)
        VALUES[f"bottom5_overlap_tc_{event}"] = len(bottom_ryt & bottom_tc)
        VALUES[f"bottom5_overlap_ret_{event}"] = len(bottom_ryt & bottom_ret)
        VALUES[f"bottom5_ryt_{event}"] = sorted(bottom_ryt)
        VALUES[f"bottom5_tc_{event}"] = sorted(bottom_tc)
        VALUES[f"bottom5_ret_{event}"] = sorted(bottom_ret)
    VALUES["n_states_timegap_2024"] = len(df)
    VALUES["n_ratio_over100_births"] = int((ev[ev.state != "India"].ratio_births_pct > 100).sum())
    VALUES["n_ratio_over100_deaths"] = int((ev[ev.state != "India"].ratio_deaths_pct > 100).sum())
    VALUES["n_ratio_over100_either"] = int(((ev[ev.state != "India"].ratio_births_pct > 100)
                                            | (ev[ev.state != "India"].ratio_deaths_pct > 100)).sum())
    VALUES["n_states_statement2_2024"] = int((ev.state != "India").sum())
    return df


# --------------------------------------------------------------------------
# 2. Convergence
# --------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    p = pd.read_csv(EXTRACTED / "state_level_of_registration_raw.csv")
    junk = p.state_raw.str.strip().str.lower().isin(NON_STATE)
    VALUES["panel_rows_removed_non_state"] = int(junk.sum())
    p = p[~junk].copy()
    p["state"] = p.state_raw.map(canon)
    if p.duplicated(["report_year", "state"]).any():
        raise SystemExit("duplicate state-year in completeness panel")
    return p


def fit(x, y) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    res = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, len(x) - 2)
    return {"n": len(x), "slope": res.slope, "lo": res.slope - tcrit * res.stderr,
            "hi": res.slope + tcrit * res.stderr, "r2": res.rvalue ** 2, "p": res.pvalue}


def earliest_latest(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state, g in p.groupby("state"):
        g = g.sort_values("report_year")
        a, b = g.iloc[0], g.iloc[-1]
        rows.append({"state": state, "y0": a.report_year, "y1": b.report_year,
                     "b0": a.level_births_pct, "b1": b.level_births_pct,
                     "d0": a.level_deaths_pct, "d1": b.level_deaths_pct})
    return pd.DataFrame(rows)


def convergence(p: pd.DataFrame) -> pd.DataFrame:
    el = earliest_latest(p)
    el = el[el.y1 > el.y0]  # a unit observed in a single year has no change
    out = []

    def add(label, sample, key, xb, yb, xd, yd):
        fb, fd = fit(xb, yb), fit(xd, yd)
        out.append({"specification": label, "key": key,
                    **{f"births_{k}": v for k, v in fb.items()},
                    **{f"deaths_{k}": v for k, v in fd.items()}})

    # (a) primary, as originally specified
    add("Primary: earliest to latest available year", el, "primary",
        el.b0, el.b1 - el.b0, el.d0, el.d1 - el.d0)

    # (b) annualised change, same units (windows differ between units)
    span = el.y1 - el.y0
    add("Annualised change (pp per year)", el, "annualised",
        el.b0, (el.b1 - el.b0) / span, el.d0, (el.d1 - el.d0) / span)

    # (c) common window 2010-2024, constant boundaries
    w = p.pivot_table(index="state", columns="report_year",
                      values=["level_births_pct", "level_deaths_pct"])
    common = [s for s in w.index if s not in BOUNDARY_CHANGED
              and not np.isnan(w.loc[s, ("level_births_pct", 2010)])
              and not np.isnan(w.loc[s, ("level_births_pct", 2024)])]
    cw = w.loc[common]
    b10, b24 = cw[("level_births_pct", 2010)], cw[("level_births_pct", 2024)]
    d10, d24 = cw[("level_deaths_pct", 2010)], cw[("level_deaths_pct", 2024)]
    add("Common window 2010-2024, constant boundaries", None, "common",
        b10, b24 - b10, d10, d24 - d10)

    # (d) excluding units already at the 100% ceiling at baseline (they cannot gain)
    mb, md = b10 < 100, d10 < 100
    fb, fd = fit(b10[mb], (b24 - b10)[mb]), fit(d10[md], (d24 - d10)[md])
    out.append({"specification": "Common window, excluding units at 100% at baseline",
                "key": "no_baseline_ceiling",
                **{f"births_{k}": v for k, v in fb.items()},
                **{f"deaths_{k}": v for k, v in fd.items()}})

    # (e) excluding units at the ceiling at either end (no censoring)
    mb2, md2 = (b10 < 100) & (b24 < 100), (d10 < 100) & (d24 < 100)
    fb, fd = fit(b10[mb2], (b24 - b10)[mb2]), fit(d10[md2], (d24 - d10)[md2])
    out.append({"specification": "Common window, excluding units at 100% in either year",
                "key": "no_ceiling",
                **{f"births_{k}": v for k, v in fb.items()},
                **{f"deaths_{k}": v for k, v in fd.items()}})

    # (f) regression to the mean: baseline measured in 2010, change from 2011
    b11, d11 = cw[("level_births_pct", 2011)], cw[("level_deaths_pct", 2011)]
    ok = b11.notna() & d11.notna()
    add("Baseline 2010, change 2011-2024 (separate measurements)", None, "rtm",
        b10[ok], (b24 - b11)[ok], d10[ok], (d24 - d11)[ok])

    # (g) proportional gap closure: share of the baseline shortfall closed
    gb = ((b24 - b10) / (100 - b10))[mb]
    gd = ((d24 - d10) / (100 - d10))[md]
    fb, fd = fit(b10[mb], gb), fit(d10[md], gd)
    out.append({"specification": "Share of baseline shortfall closed (common window, baseline <100%)",
                "key": "gap_closure",
                **{f"births_{k}": v for k, v in fb.items()},
                **{f"deaths_{k}": v for k, v in fd.items()}})
    VALUES["gap_closure_median_births"] = round(float(gb.median()), 2)
    VALUES["gap_closure_median_deaths"] = round(float(gd.median()), 2)

    # (h) Theil-Sen robust slope, primary sample
    tsb = stats.theilslopes(el.b1 - el.b0, el.b0)
    tsd = stats.theilslopes(el.d1 - el.d0, el.d0)
    out.append({"specification": "Theil-Sen robust slope, primary sample", "key": "theilsen",
                "births_n": len(el), "births_slope": tsb[0], "births_lo": tsb[2], "births_hi": tsb[3],
                "births_r2": np.nan, "births_p": np.nan,
                "deaths_n": len(el), "deaths_slope": tsd[0], "deaths_lo": tsd[2], "deaths_hi": tsd[3],
                "deaths_r2": np.nan, "deaths_p": np.nan})

    res = pd.DataFrame(out)
    res.to_csv(TABLES / "convergence_sensitivity.csv", index=False)

    VALUES["n_primary"] = int(len(el))
    VALUES["n_common"] = int(len(cw))
    VALUES["n_common_baseline_below100_births"] = int(mb.sum())
    VALUES["n_common_baseline_below100_deaths"] = int(md.sum())
    VALUES["n_no_ceiling_births"] = int(mb2.sum())
    VALUES["n_no_ceiling_deaths"] = int(md2.sum())
    VALUES["declines_deaths_primary"] = sorted(el[el.d1 < el.d0].state)
    VALUES["declines_births_primary"] = sorted(el[el.b1 < el.b0].state)
    VALUES["common_states"] = sorted(common)

    # primary-sample table for the supplement (annualised column added)
    el = el.assign(births_change=el.b1 - el.b0, deaths_change=el.d1 - el.d0,
                   deaths_annual=(el.d1 - el.d0) / span, births_annual=(el.b1 - el.b0) / span,
                   latest_gap=el.b1 - el.d1)
    el.sort_values("deaths_change").to_csv(TABLES / "state_change_earliest_latest.csv", index=False)
    return res, cw


def sigma(p: pd.DataFrame) -> pd.DataFrame:
    years = sorted(p.report_year.unique())
    w = p.pivot_table(index="state", columns="report_year",
                      values=["level_births_pct", "level_deaths_pct"])
    balanced = [s for s in w.index if s not in BOUNDARY_CHANGED
                and all(not np.isnan(w.loc[s, ("level_deaths_pct", y)]) for y in years)]
    rows = []
    for y in years:
        b = w.loc[balanced, ("level_births_pct", y)]
        d = w.loc[balanced, ("level_deaths_pct", y)]
        rows.append({"year": y, "n": len(balanced),
                     "births_mean": b.mean(), "births_sd": b.std(ddof=1),
                     "births_iqr": b.quantile(.75) - b.quantile(.25), "births_at100": int((b >= 100).sum()),
                     "deaths_mean": d.mean(), "deaths_sd": d.std(ddof=1),
                     "deaths_iqr": d.quantile(.75) - d.quantile(.25), "deaths_at100": int((d >= 100).sum())})
    out = pd.DataFrame(rows).round(1)
    out.to_csv(TABLES / "sigma_convergence_balanced.csv", index=False)
    VALUES["n_balanced"] = len(balanced)
    VALUES["balanced_years"] = [int(y) for y in years]
    return out


def main() -> None:
    tg = load_timegap()
    nat = national_timeliness(tg)
    st = state_2024(tg)
    p = load_panel()
    conv, _ = convergence(p)
    sig = sigma(p)

    with (TABLES / "values.json").open("w", encoding="utf-8") as f:
        json.dump(VALUES, f, indent=1, default=str)

    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(nat[["report_year", "event", "units", "ryt", "band_21_30", "band_30_1y", "over1y", "ret", "tc", "rc"]])
    print(st.to_string())
    print(conv[["key", "births_n", "births_slope", "births_lo", "births_hi", "births_r2", "births_p",
                "deaths_n", "deaths_slope", "deaths_lo", "deaths_hi", "deaths_r2", "deaths_p"]].round(3).to_string())
    print(sig.to_string())
    print(json.dumps(VALUES, indent=1, default=str))


if __name__ == "__main__":
    main()
