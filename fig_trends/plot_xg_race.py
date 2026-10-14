"""Match and season trend figures.

    xg_race      cumulative xG through a match, with goals marked
    momentum     territorial momentum in 5-minute bins
    rolling      rolling xG / xGA / form across a team's tournament run

    python fig_trends/plot_xg_race.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from metrics import momentum, rolling_form, xg_race  # noqa: E402
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
COMPETITION_ID, SEASON_ID = 43, 106
FIGDIR = ROOT / "figures"


def plot_xg_race() -> None:
    """Cumulative xG for both teams, with goals marked as they arrive."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    race = xg_race(ds, match)
    teams = list(match.teams)

    fig, ax = plt.subplots(figsize=(14.5, 8.2))
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.14)

    for team, color in zip(teams, (fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"])):
        mins, cum = race[team]
        # Step plot: xG only ever accumulates, so steps are the honest encoding.
        ax.step(mins, cum, where="post", color=color, linewidth=3.0,
                label=f"{team} ({cum[-1]:.2f} xG)", zorder=4)
        ax.fill_between(mins, 0, cum, step="post", color=color, alpha=0.14, zorder=3)

        # Mark each goal at the moment it changed the total. Goals can land in
        # the same minute (as in this final), so labels are pushed apart
        # vertically when they would otherwise overprint.
        shots = sorted(ds.shots(match, team), key=lambda s: s.minute)
        running = 0.0
        placed: list[tuple[float, float]] = []
        for s in shots:
            running += s.xg
            if not s.is_goal:
                continue
            ax.scatter([s.minute], [running], s=170, color=color,
                       edgecolor="white", linewidth=2.0, zorder=7)
            lx, ly = float(s.minute), float(running)
            while any(abs(lx - px) < 9 and abs(ly - py) < 0.11 for px, py in placed):
                ly += 0.10
            placed.append((lx, ly))
            ax.annotate(s.player.split()[-1], (s.minute, running),
                        xytext=(0, 13 + 17 * (ly - running) / 0.10),
                        textcoords="offset points",
                        fontsize=10, ha="center", color=color, weight="bold",
                        zorder=8)

    ax.set_xlabel("minute")
    ax.set_ylabel("cumulative xG")
    ax.set_xlim(0, 95)
    ax.set_ylim(0, max(race[t][1][-1] for t in teams) * 1.22)
    ax.grid(alpha=0.22, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", fontsize=13)

    # The headline insight is the gap between xG and the scoreline, so state it.
    tm_goals = {t: match.home_score if t == match.home else match.away_score for t in teams}
    for team, color in zip(teams, (fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"])):
        cum = race[team][1][-1]
        ax.annotate(f"{tm_goals[team]} goals from {cum:.2f} xG", (95, cum),
                    xytext=(-6, 10 if team == teams[0] else -20),
                    textcoords="offset points", fontsize=11.5, ha="right",
                    color=color, weight="bold")

    fs.add_title(ax, "xG race",
                 f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
                 f"{match.competition} {match.season} · marked circles are goals",
                 style=style)

    fig.text(0.07, 0.02,
             "Cumulative expected goals. A rising line means chances are being created; "
             "a flat line means a team is creating nothing.\nData provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "trends_xg_race", formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_momentum() -> None:
    """Territorial momentum in bins, as a diverging bar chart around zero."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    mom = momentum(ds, match, bin_minutes=5)

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(15, 9.8), sharex=True,
        gridspec_kw={"height_ratios": [1, 1.6], "hspace": 0.18})
    fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=0.13)

    bins = mom["bins"]
    home, away = mom["home"], mom["away"]
    net = mom["net"]
    home_team, away_team = mom["home_team"], mom["away_team"]

    # --- top: who generated what, per bin ---------------------------------- #
    width = 3.6
    ax_top.bar(bins - width / 2, home, width=width, color=fs.TEAM_COLORS["home"],
               label=home_team, edgecolor="white", linewidth=0.8, zorder=4)
    ax_top.bar(bins + width / 2, away, width=width, color=fs.TEAM_COLORS["away"],
               label=away_team, edgecolor="white", linewidth=0.8, zorder=4)
    ax_top.set_ylabel("territorial score")
    ax_top.legend(loc="upper left", fontsize=12)
    ax_top.grid(alpha=0.2, zorder=0)
    ax_top.set_axisbelow(True)
    ax_top.set_title("Territorial score per 5-minute bin", fontsize=15, loc="left", pad=8)

    # --- bottom: net momentum, diverging ----------------------------------- #
    # Red above the line = away team on top, blue below = home team on top, so
    # the band tells the story of the match in one sweep.
    colors = [fs.TEAM_COLORS["home"] if v >= 0 else fs.TEAM_COLORS["away"] for v in net]
    ax_bot.bar(bins, net, width=4.2, color=colors, edgecolor="white",
               linewidth=0.8, zorder=4)
    ax_bot.axhline(0, color=fs.PALETTE["ink"], linewidth=1.4, zorder=5)

    # Shade the strongest runs of pressure for each side.
    thresh = np.percentile(np.abs(net), 78)
    for b, v in zip(bins, net):
        if abs(v) >= thresh and v != 0:
            ax_bot.axvspan(b - 2.5, b + 2.5, color=(
                fs.TEAM_COLORS["home"] if v > 0 else fs.TEAM_COLORS["away"]),
                alpha=0.07, zorder=1)

    ax_bot.set_xlabel("minute")
    ax_bot.set_ylabel(f"net  ({home_team} − {away_team})")
    # Pad the x-range so the half-bars at minute 0 and 90 are not clipped.
    ax_bot.set_xlim(-6, 99)
    ax_bot.grid(alpha=0.2, zorder=0)
    ax_bot.set_axisbelow(True)
    ax_bot.set_title("Net momentum: which side was on top", fontsize=15, loc="left", pad=8)

    # Direction hints, since a diverging bar chart is easy to misread.
    ax_bot.text(0.002, 0.94, f"← {home_team} on top", transform=ax_bot.transAxes,
                fontsize=11, color=fs.TEAM_COLORS["home"], va="top")
    ax_bot.text(0.002, 0.06, f"← {away_team} on top", transform=ax_bot.transAxes,
                fontsize=11, color=fs.TEAM_COLORS["away"], va="bottom")

    fig.suptitle("Match momentum",
                 fontsize=22, weight="bold", x=0.07, ha="left", y=0.955)
    fig.text(0.07, 0.868,
             f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
             f"{match.competition} {match.season}",
             fontsize=13, color=fs.PALETTE["grey_mid"], ha="left")
    fig.text(0.07, 0.025,
             "Territorial score = final-third entries + 2 x box entries + 3 x shots + 2 x xG. "
             "Shaded bands mark the bins in the top 22% of intensity.\n"
             "Data provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "trends_momentum", formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_rolling() -> None:
    """Rolling xG for and against across a team's tournament run."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()

    home_team = ds.match(MATCH_ID).teams[0]
    fixtures = ds.fixtures(COMPETITION_ID, SEASON_ID)
    ids = ds.cached_match_ids(with_frames=False)
    available = {f["match_id"] for f in fixtures} & set(ids)
    # Keep the fixtures in date order so the rolling window means "last 3 games".
    run = [f["match_id"] for f in sorted(fixtures, key=lambda f: f["match_date"])
           if f["match_id"] in available and home_team in
           (f["home_team"]["home_team_name"], f["away_team"]["away_team_name"])]
    if len(run) < 4:
        raise SystemExit(f"Only {len(run)} cached matches for {home_team}; need at least 4.")

    form = rolling_form(ds, run, home_team, window=3)
    print(f"{home_team}: {len(run)} cached matches in the run")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(15, 9.6), sharex=True,
        gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.16})
    fig.subplots_adjust(left=0.07, right=0.97, top=0.85, bottom=0.14)

    x = np.arange(len(form["labels"]))
    w = form["window"]

    # --- per-match xG and rolling mean ------------------------------------- #
    ax1.bar(x - 0.19, form["xg"], width=0.38, color=fs.ROLE["attack"], alpha=0.45,
            label="xG (match)", zorder=3, edgecolor="white", linewidth=0.8)
    ax1.bar(x + 0.19, form["xga"], width=0.38, color=fs.ROLE["defend"], alpha=0.45,
            label="xG conceded (match)", zorder=3, edgecolor="white", linewidth=0.8)
    # The rolling line is offset by the window, so it is centred on the matches
    # it actually summarises rather than starting at match 1.
    xr = x[w - 1:]
    ax1.plot(xr, form["xg_roll"], color=fs.ROLE["attack"], linewidth=3.0,
             marker="o", markersize=7, label=f"xG, {w}-match rolling", zorder=6)
    ax1.plot(xr, form["xga_roll"], color=fs.ROLE["defend"], linewidth=3.0,
             marker="o", markersize=7, label=f"xG conceded, {w}-match rolling", zorder=6)
    ax1.set_ylabel("expected goals")
    ax1.grid(alpha=0.2, zorder=0)
    ax1.set_axisbelow(True)
    ax1.legend(loc="upper left", fontsize=11.5, ncol=2)
    ax1.set_title("Chances created and conceded", fontsize=15, loc="left", pad=8)

    # --- points per match --------------------------------------------------- #
    ax2.bar(x, form["points"], width=0.55,
            color=[fs.ROLE["success"] if p == 3 else
                   (fs.ROLE["context"] if p == 1 else fs.ROLE["failure"])
                   for p in form["points"]],
            edgecolor="white", linewidth=1.0, zorder=4)
    for xi, p in zip(x, form["points"]):
        ax2.text(xi, p + 0.06, str(int(p)), ha="center", fontsize=11,
                 color=fs.PALETTE["grey_dark"], zorder=6)
    ax2.set_yticks([0, 1, 3])
    ax2.set_ylabel("points")
    ax2.set_ylim(0, 3.5)
    ax2.grid(alpha=0.2, zorder=0)
    ax2.set_axisbelow(True)
    ax2.set_title("Result", fontsize=15, loc="left", pad=8)

    ax2.set_xticks(x)
    ax2.set_xticklabels(form["labels"], rotation=35, ha="right", fontsize=10.5)

    fig.suptitle(f"{home_team}: tournament form",
                 fontsize=22, weight="bold", x=0.07, ha="left", y=0.95)
    fig.text(0.07, 0.02,
             f"{len(run)} cached matches in date order. Rolling means are centred on the "
             f"{w} matches they summarise, so the line starts at game {w}.\n"
             "Data provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "trends_rolling", formats=["png", "pdf"], dpi=300):
        print("wrote", p)


if __name__ == "__main__":
    plot_xg_race()
    plot_momentum()
    plot_rolling()
