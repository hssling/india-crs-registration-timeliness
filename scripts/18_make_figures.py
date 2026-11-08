#!/usr/bin/env python3
"""Figures (JPEG, 300 dpi, each well under 1024 KB).

Figure 1  National completeness, 2009-2024; years without a published national
          figure are bridged with dashed segments, not drawn as observed.
Figure 2  States/UTs, 2024. (A) completeness versus registration-year
          timeliness; (B) registration-year versus recent-event timeliness.
Figure S1 National timeliness accounting, 2020-2024.

Palette: blue #2a78d6 (births) and orange #eb6834 (deaths), validated for
colour-vision deficiency (protan dE 24.7); births are also circles and deaths
squares, so identity never rests on colour alone. No titles inside images: the
legends in the article carry them.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT
TABLES = ROOT / "outputs" / "tables"
FIG = ROOT / "outputs" / "figures"
FIG.mkdir(exist_ok=True)

BIRTH, DEATH = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "savefig.dpi": 300,
})


def save(fig, name: str) -> None:
    path = FIG / name
    fig.savefig(path, format="jpeg", dpi=300, bbox_inches="tight",
                pil_kwargs={"quality": 90, "optimize": True})
    plt.close(fig)
    kb = path.stat().st_size / 1024
    if kb > 1024:
        raise SystemExit(f"{name} is {kb:.0f} KB, above the 1024 KB limit")
    print(f"{name}: {kb:.0f} KB")


def figure1() -> None:
    nat = pd.read_csv(ROOT / "data_extracted" / "national_trend_reconciled.csv")
    nat = nat[(nat.year >= 2009)]
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for indicator, colour, marker, label in (
            ("birth_registration", BIRTH, "o", "Births"),
            ("death_registration", DEATH, "s", "Deaths")):
        s = nat[nat.indicator == indicator].sort_values("year")
        years, vals = list(s.year), list(s.value_pct)
        for (y0, v0), (y1, v1) in zip(zip(years, vals), zip(years[1:], vals[1:])):
            ax.plot([y0, y1], [v0, v1], color=colour, lw=2,
                    ls="-" if y1 - y0 == 1 else (0, (3, 2)))
        ax.plot(years, vals, ls="none", marker=marker, ms=6, color=colour,
                markeredgecolor="white", markeredgewidth=1, label=label)
        ax.annotate(f"{vals[-1]:.1f}%", (years[-1], vals[-1]),
                    xytext=(8, 6 if label == "Deaths" else -10), textcoords="offset points",
                    color=INK, fontsize=9)
    for y in (2017, 2020, 2021, 2022):
        ax.axvspan(y - 0.5, y + 0.5, color="#f1f0eb", zorder=0, lw=0)
    ax.text(2021, 52, "No national\nfigure\npublished", ha="center", va="center",
            fontsize=8, color=MUTED)
    ax.text(2017, 52, "No\nfigure", ha="center", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(2008.5, 2025.3)
    ax.set_ylim(45, 102)
    ax.set_xticks(range(2009, 2025, 1))
    ax.set_xticklabels([str(y) if y % 2 == 1 else "" for y in range(2009, 2025)])
    ax.set_xlabel("Year")
    ax.set_ylabel("Level of registration (%)")
    ax.legend(loc="lower right")
    save(fig, "figure1_national_completeness.jpg")


LABEL_OFFSETS = {
    # (dx, dy) in points, set by eye after rendering to avoid collisions
    "A": {"Arunachal Pradesh": (6, -10), "Nagaland": (6, 4), "Manipur": (-8, -12),
          "Bihar": (-6, -13), "Ladakh": (6, 4)},
    "B": {"Ladakh": (7, -3), "Manipur": (7, -4), "Jammu & Kashmir": (-7, -15),
          "Nagaland": (6, 2), "Arunachal Pradesh": (6, -4)},
}


def figure2() -> None:
    st = pd.read_csv(TABLES / "state_2024_timeliness_accounting.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 5.0))

    for event, colour, marker, label in (("births", BIRTH, "o", "Births"),
                                         ("deaths", DEATH, "s", "Deaths")):
        a.scatter(st[f"comp_{event}"], st[f"ryt_{event}"], s=34, marker=marker, color=colour,
                  edgecolor="white", linewidth=0.8, label=label, zorder=3, alpha=0.95)
        b.scatter(st[f"ryt_{event}"], st[f"ret_{event}"], s=34, marker=marker, color=colour,
                  edgecolor="white", linewidth=0.8, label=label, zorder=3, alpha=0.95)

    for state, (dx, dy) in LABEL_OFFSETS["A"].items():
        r = st[st.state == state].iloc[0]
        a.annotate(state, (r.comp_deaths, r.ryt_deaths), xytext=(dx, dy),
                   textcoords="offset points", fontsize=8, color=INK,
                   ha="right" if dx < 0 else "left")
    for state, (dx, dy) in LABEL_OFFSETS["B"].items():
        r = st[st.state == state].iloc[0]
        b.annotate(state, (r.ryt_births, r.ret_births), xytext=(dx, dy),
                   textcoords="offset points", fontsize=8, color=INK,
                   ha="right" if dx < 0 else "left")

    a.set_xlim(20, 103)
    a.set_ylim(-3, 103)
    a.set_xlabel("Completeness, published level of registration (%)")
    a.set_ylabel("Registration-year timeliness (%)")
    a.text(-0.12, 1.02, "A", transform=a.transAxes, fontsize=13, fontweight="bold", color=INK)
    a.legend(loc="upper left")

    b.plot([0, 100], [0, 100], color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    b.text(70, 64, "equal values", rotation=38, fontsize=8, color=MUTED)
    b.set_xlim(-3, 103)
    b.set_ylim(-3, 103)
    b.set_xlabel("Registration-year timeliness (%)")
    b.set_ylabel("Recent-event timeliness (%)")
    b.text(-0.12, 1.02, "B", transform=b.transAxes, fontsize=13, fontweight="bold", color=INK)
    b.legend(loc="lower right")
    fig.tight_layout(w_pad=3)
    save(fig, "figure2_completeness_vs_timeliness.jpg")


def figure_s1() -> None:
    nat = pd.read_csv(TABLES / "national_timeliness_accounting.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(10.5, 4.2))
    for event, colour, marker, label in (("births", BIRTH, "o", "Births"),
                                         ("deaths", DEATH, "s", "Deaths")):
        s = nat[nat.event == event].sort_values("report_year")
        a.plot(s.report_year, s.ryt, color=colour, lw=2, marker=marker, ms=6,
               markeredgecolor="white", label=f"{label}, registration-year")
        a.plot(s.report_year, s.ret, color=colour, lw=2, ls=(0, (3, 2)), marker=marker, ms=6,
               markerfacecolor="white", markeredgecolor=colour, label=f"{label}, recent events")
        b.plot(s.report_year, s.over1y, color=colour, lw=2, marker=marker, ms=6,
               markeredgecolor="white", label=label)
    for ax, letter in ((a, "A"), (b, "B")):
        ax.set_xticks(range(2020, 2025))
        ax.set_xlabel("Report year")
        ax.text(-0.16, 1.03, letter, transform=ax.transAxes, fontsize=13, fontweight="bold", color=INK)
    a.set_ylim(60, 100)
    a.set_ylabel("Registered within 21 days (%)")
    a.legend(loc="lower left", fontsize=8, handlelength=3.5)
    b.set_ylim(0, 30)
    b.set_ylabel("Registered >1 year after the event (%)")
    b.legend(loc="upper left", fontsize=8, handlelength=3.5)
    fig.tight_layout(w_pad=3)
    save(fig, "figureS1_national_timeliness_accounting.jpg")


if __name__ == "__main__":
    figure1()
    figure2()
    figure_s1()
