"""Shot maps, goal-mouth plots, and shot-quality grids.

Three figures that together answer "why did this team underperform its xG?":

    shot_map       every shot as a bubble sized by xG, with the goals called out
    goal_mouth     where shots actually crossed the goal line, on a real goal frame
    quality_grid   xG per shot by pitch zone - the "where are the good chances" view

    python fig_shooting/plot_shot_map.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
FIGDIR = ROOT / "figures"

# Frame the attacking two-thirds, portrait so the goal end reads naturally.
# A full 120x80 pitch wastes half the canvas on a half-circle that carries no
# information for a shot map. The value is (x_min, x_max, y_min, y_max).
VIEW = (76.0, 123.0, -1.0, 81.0)

# Bubble area encodes xG. The scale is linear and labelled, so a reader can
# compare two bubbles by eye instead of guessing.
BUBBLE_MIN, BUBBLE_MAX = 40.0, 2200.0


def bubble_sizes(xg: np.ndarray) -> np.ndarray:
    return BUBBLE_MIN + (BUBBLE_MAX - BUBBLE_MIN) * np.clip(xg, 0, 1) ** 0.85


def plot_shot_map() -> None:
    """Both teams' shots on one pitch, sized by xG, goals ringed."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    home, away = match.teams

    fig, ax = plt.subplots(figsize=(7.6, 11.5))
    fig.subplots_adjust(left=0.02, right=0.985, top=0.92, bottom=0.05)
    fs.draw_pitch(ax, style=style)
    ax.set_xlim(VIEW[0], VIEW[1])
    ax.set_ylim(VIEW[2], VIEW[3])

    totals = {}
    for team, color, marker in ((home, fs.TEAM_COLORS["home"], "o"),
                                (away, fs.TEAM_COLORS["away"], "^")):
        shots = ds.shots(match, team)
        totals[team] = (len(shots), sum(s.xg for s in shots), sum(s.is_goal for s in shots))
        if not shots:
            continue

        xg = np.array([s.xg for s in shots])
        xs = np.array([s.x for s in shots])
        ys = np.array([s.y for s in shots])
        goals = np.array([s.is_goal for s in shots])

        # Non-goals first so goals sit on top.
        order = np.argsort(goals)
        ax.scatter(xs[order], ys[order], s=bubble_sizes(xg)[order],
                   color=color, alpha=0.42, marker=marker,
                   edgecolor="white", linewidth=1.0, zorder=5,
                   label=f"{team}  {totals[team][0]} shots · {totals[team][1]:.2f} xG")

        if goals.any():
            ax.scatter(xs[goals], ys[goals], s=bubble_sizes(xg)[goals],
                       facecolor="none", edgecolor=color, linewidth=2.8,
                       marker=marker, zorder=7,
                       label=f"{team} goals ({int(goals.sum())})")

        # Label the biggest chances so the map tells a story, not just a scatter.
        # Two penalties in the same spot would overprint, so nudge successive
        # labels outward when they land too close together.
        placed: list[tuple[float, float]] = []
        for i in np.argsort(xg)[::-1][:3]:
            s = shots[i]
            ox, oy = 10, 14
            while any(abs(s.x + ox / 6 - px) < 9 and abs(s.y + oy / 6 - py) < 6
                      for px, py in placed):
                oy += 17
            placed.append((s.x + ox / 6, s.y + oy / 6))
            ax.annotate(
                f"{s.player.split()[-1]} {s.xg:.2f}",
                (s.x, s.y), xytext=(ox, oy), textcoords="offset points",
                fontsize=10, color=fs.PALETTE["ink"], zorder=12,
                arrowprops=dict(arrowstyle="-", color=fs.PALETTE["grey_mid"],
                                linewidth=0.9, shrinkA=0, shrinkB=4),
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.85),
            )

    ax.legend(loc="upper left", fontsize=12, markerscale=0.55, labelspacing=0.6,
              bbox_to_anchor=(0.0, 1.0))
    fs.add_title(ax, "Shot map: every attempt, sized by expected goals",
                 f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
                 f"{match.competition} {match.season}",
                 style=style)

    # A labelled xG size key in its own inset, so bubble area is readable rather
    # than decorative, and it cannot collide with the shot cloud.
    key = fig.add_axes([0.055, 0.075, 0.30, 0.19])
    key.set_xlim(0, 1)
    key.set_ylim(0, 1)
    key.axis("off")
    key.set_title("bubble area = xG", fontsize=10.5, weight="bold",
                  color=fs.PALETTE["grey_dark"], pad=4)
    for y, val in zip((0.80, 0.46, 0.14), (0.05, 0.25, 0.60)):
        key.scatter([0.22], [y], s=bubble_sizes(np.array([val]))[0],
                    facecolor="none", edgecolor=fs.PALETTE["grey_dark"],
                    linewidth=1.4, zorder=9)
        key.text(0.46, y, f"{val:.2f}", fontsize=10, va="center",
                 color=fs.PALETTE["grey_dark"], zorder=9)

    fs.assert_pitch_aspect(fig, ax, label="shot map")
    paths = fs.finalize_figure(fig, FIGDIR / "shooting_shot_map", formats=["png", "pdf"], dpi=300)
    for p in paths:
        print("wrote", p)


def plot_goal_mouth() -> None:
    """Where shots crossed the goal line, drawn on a real-scale goal frame."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    # Goal-mouth coordinates in metres, centred on x = 0, y from 0 to height.
    gw, gh = fs.GOAL_WIDTH_M, fs.GOAL_HEIGHT_M
    # Figure is sized so each panel's box matches the goal's 3:1 aspect; the
    # axes use set_aspect('equal') and we export with bbox=None so the goal stays
    # dimensionally honest instead of being stretched to the axes box.
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.4), sharey=True)
    fig.subplots_adjust(left=0.035, right=0.965, top=0.74, bottom=0.20, wspace=0.05)

    for ax, team, color in zip(axes, match.teams,
                               (fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"])):
        shots = ds.shots(match, team)

        def in_frame(s) -> bool:
            """A recorded goal-mouth endpoint that actually lies within the frame."""
            if s.end_z is None or s.end_y is None:
                return False
            xs_m = (s.end_y - fs.PITCH_WIDTH / 2) / fs.GOAL_HALF_WIDTH * (gw / 2)
            return abs(xs_m) <= gw / 2 and 0.0 <= s.end_z <= gh

        on_target = [s for s in shots if in_frame(s)]
        goals = [s for s in on_target if s.is_goal]
        saves = [s for s in on_target if not s.is_goal]

        # Goal frame: posts, crossbar, net hatching.
        ax.add_patch(Rectangle((-gw / 2, 0), gw, gh, facecolor="#F4F6F4",
                               edgecolor="none", zorder=1))
        for xline in np.linspace(-gw / 2, gw / 2, 13):
            ax.plot([xline, xline], [0, gh], color="#D8DEDA", linewidth=0.7, zorder=2)
        for yline in np.linspace(0, gh, 7):
            ax.plot([-gw / 2, gw / 2], [yline, yline], color="#D8DEDA", linewidth=0.7, zorder=2)
        ax.add_patch(Rectangle((-gw / 2, 0), gw, gh, facecolor="none",
                               edgecolor=fs.PALETTE["ink"], linewidth=3.0, zorder=4))
        # Goal line and posts extended.
        ax.plot([-gw / 2 - 0.5, gw / 2 + 0.5], [0, 0], color=fs.PALETTE["ink"],
                linewidth=3.0, zorder=4)
        # Penalty spot reference below.
        ax.text(0, -0.28, "goal line", ha="center", fontsize=10,
                color=fs.PALETTE["grey_mid"], zorder=5)

        for group, lab in ((saves, f"Saved or missed ({len(saves)})"),
                           (goals, f"Goals ({len(goals)})")):
            if not group:
                continue
            # StatsBomb end_location is [x, y, z] on the 120x80 grid, where the
            # goal spans y 36..44 and z is height. Convert both to metres.
            zs = np.array([s.end_z for s in group], dtype=float)
            ys = np.array([s.end_y for s in group], dtype=float)
            xs = (ys - fs.PITCH_WIDTH / 2) / fs.GOAL_HALF_WIDTH * (gw / 2)
            ax.scatter(xs, zs, s=bubble_sizes(np.array([s.xg for s in group])),
                       color=color, alpha=0.90 if lab.startswith("Goals") else 0.38,
                       edgecolor="white", linewidth=1.2, zorder=6,
                       label=lab)

        # Keep only shots that were actually on target inside the frame for the note.
        n_on = len(on_target)
        ax.set_xlim(-gw / 2 - 0.55, gw / 2 + 0.55)
        ax.set_ylim(-0.45, gh + 0.35)
        ax.set_aspect("equal")
        fs.assert_pitch_aspect(fig, ax, label=f"goal mouth ({team})")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=11)
        ax.set_title(f"{team}\n{n_on} shots with an in-frame endpoint", fontsize=15)

    fig.suptitle("Goal-mouth plot: where shots finished", fontsize=20, weight="bold", y=0.95)
    fig.text(0.5, 0.03,
             "Height (z) and lateral placement come from StatsBomb's recorded end_location; only "
             "shots whose endpoint falls inside the frame are plotted.\n"
             "The frame is drawn to true scale: 7.32 m x 2.44 m. Bubble area = xG. "
             "Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    paths = fs.finalize_figure(fig, FIGDIR / "shooting_goal_mouth", formats=["png", "pdf"],
                               dpi=300, bbox=None)
    for p in paths:
        print("wrote", p)


def plot_quality_grid() -> None:
    """xG and shot count per zone in the attacking third, for both teams."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    nx, ny = 6, 5
    x0, x1 = 78.0, 120.0
    # Shots cluster in the central corridor, so crop the wide flanks away rather
    # than pad the figure with four empty zones.
    y0, y1 = 14.0, 66.0

    fig, axes = plt.subplots(1, 2, figsize=(17, 7.4))
    fig.subplots_adjust(left=0.03, right=0.94, top=0.82, bottom=0.14, wspace=0.16)

    for ax, team in zip(axes, match.teams):
        shots = ds.shots(match, team)
        xg_sum = np.zeros((ny, nx))
        counts = np.zeros((ny, nx))
        for s in shots:
            i = min(nx - 1, max(0, int((s.x - x0) / (x1 - x0) * nx)))
            j = min(ny - 1, max(0, int((s.y - y0) / (y1 - y0) * ny)))
            xg_sum[j, i] += s.xg
            counts[j, i] += 1

        # Draw the pitch first, then a clean zone lattice on top so the grid is
        # legible over the linework.
        fs.draw_pitch(ax, style=style, crop="final-third")
        ax.set_ylim(y0, y1)
        for k in range(nx + 1):
            ax.plot([x0 + k * (x1 - x0) / nx] * 2, [y0, y1], color="white",
                    linewidth=1.6, zorder=3)
        for k in range(ny + 1):
            ax.plot([x0, x1], [y0 + k * (y1 - y0) / ny] * 2, color="white",
                    linewidth=1.6, zorder=3)

        im = ax.imshow(xg_sum, extent=[x0, x1, y0, y1], origin="lower",
                       cmap=fs.THREAT_CMAP, alpha=0.92, interpolation="nearest", zorder=2)
        vmax = max(xg_sum.max(), 1e-6)
        for (j, i), c in np.ndenumerate(counts):
            if c == 0:
                continue
            cx = x0 + (i + 0.5) * (x1 - x0) / nx
            cy = y0 + (j + 0.5) * (y1 - y0) / ny
            ax.text(cx, cy, f"{int(c)}\nshot{'s' if c > 1 else ''}",
                    ha="center", va="center", fontsize=11.5, zorder=6,
                    color="white" if xg_sum[j, i] > 0.55 * vmax else fs.PALETTE["ink"])
            ax.text(cx, cy - 4.6, f"{xg_sum[j, i]:.2f} xG", ha="center", va="center",
                    fontsize=11, zorder=6, weight="bold",
                    color="white" if xg_sum[j, i] > 0.55 * vmax else fs.PALETTE["grey_dark"])

        ax.set_title(f"{team}\n{len(shots)} shots · {sum(s.xg for s in shots):.2f} xG · "
                     f"{sum(s.is_goal for s in shots)} goals", fontsize=16)
        cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cb.set_label("total xG in zone", fontsize=11)
        cb.outline.set_visible(False)

    fig.suptitle("Shot-quality grid: where the chances come from",
                 fontsize=21, weight="bold", y=0.97)
    fig.text(0.5, 0.02,
             f"Attacking third divided into {nx} x {ny} zones (flanks cropped to the shooting "
             "corridor). Total xG accumulates in the zone the shot was taken from.\n"
             "High xG in a low-shot-count zone means a few very good chances rather than "
             "sustained pressure. Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    paths = fs.finalize_figure(fig, FIGDIR / "shooting_quality_grid", formats=["png", "pdf"], dpi=300)
    for p in paths:
        print("wrote", p)


if __name__ == "__main__":
    plot_shot_map()
    plot_goal_mouth()
    plot_quality_grid()
