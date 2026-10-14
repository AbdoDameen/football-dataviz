"""Possession and territory figures.

    zone_grid      touches per zone in the attacking half, side by side
    field_tilt     who controls territory, as a share, plus packing
    carries        progressive carries as a flow field

    python fig_territory/plot_zone_grid.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from metrics import (  # noqa: E402
    TOUCH_EVENT_TYPES,
    attacking_half_touches,
    field_tilt,
    team_metrics,
    zone_occupancy,
)
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
FIGDIR = ROOT / "figures"


def plot_zone_grid() -> None:
    """Touches per zone in the attacking half, both teams on a shared scale."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    nx, ny = 6, 4
    x0 = 60.0
    grids = {t: zone_occupancy(ds, match, t, n_x=nx, n_y=ny) for t in match.teams}
    vmax = max(g.max() for g in grids.values())

    fig, axes = plt.subplots(1, 2, figsize=(19, 7.6), sharey=True)
    fig.subplots_adjust(left=0.02, right=0.93, top=0.83, bottom=0.13, wspace=0.06)

    for ax, team in zip(axes, match.teams):
        grid = grids[team]

        # The heatmap is opaque, so the pitch linework is drawn *above* it
        # (zorder) rather than underneath, and the attacking-half view is
        # restored afterwards because draw_pitch frames the full pitch.
        im = ax.imshow(grid, extent=[x0, fs.PITCH_LENGTH, 0, fs.PITCH_WIDTH],
                       origin="lower", cmap=fs.COUNT_CMAP, vmin=0, vmax=vmax,
                       interpolation="nearest", alpha=0.90, zorder=2)
        # White lattice so the zones read as a grid rather than a blur.
        for k in range(nx + 1):
            ax.plot([x0 + k * (fs.PITCH_LENGTH - x0) / nx] * 2, [0, fs.PITCH_WIDTH],
                    color="white", linewidth=1.5, zorder=3)
        for k in range(ny + 1):
            ax.plot([x0, fs.PITCH_LENGTH], [k * fs.PITCH_WIDTH / ny] * 2,
                    color="white", linewidth=1.5, zorder=3)

        # Markings on top, at heavier weight and a darker grey so they read
        # over the blue fill.
        fs.draw_pitch(ax, style=fs.PitchStyle(
            font_size=style.font_size, pitch_linewidth=2.4,
            line_color="#5F6B63", pitch_color="#FBFBF9"), zorder=6)
        ax.set_xlim(x0, fs.PITCH_LENGTH)
        ax.set_ylim(0, fs.PITCH_WIDTH)

        for (j, i), v in np.ndenumerate(grid):
            if v == 0:
                continue
            cx = x0 + (i + 0.5) * (fs.PITCH_LENGTH - x0) / nx
            cy = (j + 0.5) * fs.PITCH_WIDTH / ny
            ax.text(cx, cy, f"{int(v)}", ha="center", va="center", fontsize=13,
                    weight="bold", zorder=7,
                    color="white" if v > 0.55 * vmax else fs.PALETTE["ink"])

        total = int(grid.sum())
        ax.set_title(f"{team}\n{total} touches in the attacking half",
                     fontsize=16, loc="left", pad=10)

    cb = fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015)
    cb.set_label("touches in zone", fontsize=12)
    cb.outline.set_visible(False)

    fig.suptitle("Zone occupancy: where each team has the ball",
                 fontsize=21, weight="bold", y=0.965)
    fig.text(0.5, 0.02,
             f"Touches (passes, carries, shots, dribbles, receptions) in a {nx} x {ny} grid over "
             "the attacking half. Both panels share one colour scale.\n"
             "The final column is the penalty-box zone. Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for ax in axes:
        fs.assert_pitch_aspect(fig, ax, label="zone pitch")
    for p in fs.finalize_figure(fig, FIGDIR / "territory_zone_grid",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_field_tilt() -> None:
    """Territory share as a single stacked bar, plus the underlying team numbers."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    tilt = field_tilt(ds, match)
    tm = team_metrics(ds, match)
    teams = list(match.teams)

    fig = plt.figure(figsize=(15, 7.6))
    ax_bar = fig.add_axes([0.07, 0.70, 0.86, 0.13])
    ax_tab = fig.add_axes([0.07, 0.14, 0.86, 0.44])
    ax_tab.axis("off")

    # --- field tilt: one 100%-wide bar, home left -------------------------- #
    home_share = tilt[teams[0]]
    ax_bar.barh([0], [home_share], height=0.6, color=fs.TEAM_COLORS["home"],
                edgecolor="white", linewidth=2, zorder=3)
    ax_bar.barh([0], [1 - home_share], left=[home_share], height=0.6,
                color=fs.TEAM_COLORS["away"], edgecolor="white", linewidth=2, zorder=3)
    ax_bar.set_xlim(0, 1)
    ax_bar.set_ylim(-0.6, 0.6)
    ax_bar.axis("off")
    # Percentage labels sit inside their own segment, so no legend is needed.
    ax_bar.text(home_share / 2, 0, f"{teams[0]}\n{home_share:.0%}", ha="center",
                va="center", color="white", fontsize=15, weight="bold", zorder=4)
    ax_bar.text(home_share + (1 - home_share) / 2, 0, f"{teams[1]}\n{1 - home_share:.0%}",
                ha="center", va="center", color="white", fontsize=15, weight="bold", zorder=4)
    ax_bar.text(0, 0.52, "Field tilt: share of attacking-half touches",
                fontsize=15, weight="bold", color=fs.PALETTE["ink"])

    # --- underlying numbers ------------------------------------------------ #
    # One pass over each team's touches, using the exact definition that
    # field_tilt and zone_occupancy use, so every count on this figure agrees
    # with every other figure in the project.
    half_touches = attacking_half_touches(ds, match)
    box_touches = {}
    final_third_touches = {}
    for team in teams:
        box_n = ft_n = 0
        for ev in match.raw_events:
            if ev.get("type", {}).get("name") not in TOUCH_EVENT_TYPES:
                continue
            if ev.get("team", {}).get("name") != team:
                continue
            loc = ds._oriented(ev, match)
            if loc is None:
                continue
            if loc[0] >= 80.0:
                ft_n += 1
            if loc[0] >= 102.0 and 18.0 <= loc[1] <= 62.0:
                box_n += 1
        box_touches[team] = box_n
        final_third_touches[team] = ft_n

    rows = [
        ("Attacking-half touches", [half_touches[t] for t in teams], "{:,}"),
        ("Final-third touches", [final_third_touches[t] for t in teams], "{:,}"),
        ("Penalty-box touches", [box_touches[t] for t in teams], "{:,}"),
        ("Progressive passes", [tm[t].progressive_passes for t in teams], "{:,}"),
        ("Possession value (xT)", [tm[t].xt for t in teams], "{:.2f}"),
    ]

    y = 0.86
    ax_tab.text(0.0, 1.0, "Territory, in numbers", fontsize=15, weight="bold",
                transform=ax_tab.transAxes, va="top")
    for label, vals, fmt in rows:
        fmtf = fmt.format
        ax_tab.text(0.0, y, label, fontsize=13, transform=ax_tab.transAxes, va="center")
        for k, (t, v) in enumerate(zip(teams, vals)):
            xx = 0.52 + k * 0.22
            ax_tab.text(xx, y, fmtf(v), fontsize=14, weight="bold",
                        color=[fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"]][k],
                        transform=ax_tab.transAxes, va="center", ha="left")
        y -= 0.17
    for k, t in enumerate(teams):
        ax_tab.text(0.52 + k * 0.22, 1.0, t, fontsize=13, weight="bold",
                    color=[fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"]][k],
                    transform=ax_tab.transAxes, va="top")

    fig.suptitle("Territory profile", fontsize=22, weight="bold", x=0.07, ha="left", y=0.95)
    fig.text(0.07, 0.035,
             "A touch is a pass, carry, shot, dribble or reception — the same definition used by "
             "the zone grid, so counts agree across figures.\n"
             "xT sums the stylised threat value gained by each completed pass. "
             "Data provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "territory_field_tilt",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_carries() -> None:
    """Progressive carries as a zone-to-zone flow field, mirroring the pass version."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    nx, ny = 6, 4
    cell_w, cell_h = fs.PITCH_LENGTH / nx, fs.PITCH_WIDTH / ny

    fig, axes = plt.subplots(2, 1, figsize=(14, 13))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.05, hspace=0.14)

    for ax, team, color in zip(axes, match.teams,
                               (fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"])):
        fs.draw_pitch(ax, style=style, show_third_lines=True)
        carries = [c for c in ds.carries(match, team) if c.is_progressive]

        buckets: dict[tuple[int, int], list] = defaultdict(list)
        for c in carries:
            i = min(nx - 1, max(0, int(c.x / cell_w)))
            j = min(ny - 1, max(0, int(c.y / cell_h)))
            buckets[(i, j)].append(c)

        vmax = max((len(v) for v in buckets.values()), default=1)

        for (i, j), group in buckets.items():
            dx = float(np.mean([c.end_x - c.x for c in group]))
            dy = float(np.mean([c.end_y - c.y for c in group]))
            n = len(group)
            frac = n / vmax
            cx, cy = (i + 0.5) * cell_w, (j + 0.5) * cell_h
            ax.annotate("", xy=(cx + dx, cy + dy), xytext=(cx, cy),
                        arrowprops=dict(arrowstyle="-|>", color=color,
                                        linewidth=0.8 + 6.0 * frac,
                                        alpha=0.25 + 0.65 * frac,
                                        shrinkA=0, shrinkB=0,
                                        mutation_scale=12 + 15 * frac), zorder=4)
            if n >= 3:
                ax.text(cx, cy, str(n), ha="center", va="center", fontsize=10.5,
                        weight="bold", color="white", zorder=8,
                        bbox=dict(boxstyle="circle,pad=0.18", fc=color,
                                  ec="white", linewidth=1.4, alpha=0.95))

        total_dist = sum(c.distance for c in ds.carries(match, team))
        ax.set_title(f"{team}: {len(carries)} progressive carries · "
                     f"{total_dist:.0f} yd carried in total", fontsize=16, loc="left", pad=10)

    fig.suptitle("Progressive carries: from each zone, where does the player drive?",
                 fontsize=20, weight="bold", y=0.975)
    fig.text(0.5, 0.008,
             "A progressive carry advances the ball at least 5 yards up-pitch. Each arrow is one "
             "zone's mean direction and mean distance, sized by volume.\n"
             "Circled numbers mark zones with 3 or more progressive carries. "
             "Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for ax in axes:
        fs.assert_pitch_aspect(fig, ax, label="carry pitch")
    for p in fs.finalize_figure(fig, FIGDIR / "territory_carries",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


if __name__ == "__main__":
    plot_zone_grid()
    plot_field_tilt()
    plot_carries()
