"""Pass networks, progressive passing, and passing sonars.

    pass_network     who passes to whom, weighted by volume, positioned by average location
    progressive      where a team actually advances the ball, and where it gets stuck
    sonar            one player's passing output split by direction and distance

    python fig_passing/plot_pass_network.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
TEAM_INDEX = 0  # which side to feature in the network
FIGDIR = ROOT / "figures"


def build_network(ds, match, team, min_passes: int = 4):
    """Node positions (average pass origin) and weighted edges between players."""
    passes = ds.passes(match, team)
    origins: dict[str, list] = defaultdict(list)
    edges: Counter = Counter()

    for p in passes:
        origins[p.player].append([p.x, p.y])
        if p.completed and p.recipient:
            edges[(p.player, p.recipient)] += 1

    positions = {k: np.mean(np.array(v), axis=0) for k, v in origins.items()}
    counts = {k: len(v) for k, v in origins.items()}

    # Keep only the players who actually participated in the passing structure.
    keep = {k for k, c in counts.items() if c >= min_passes}
    edges = {k: v for k, v in edges.items() if k[0] in keep and k[1] in keep and v >= 3}
    positions = {k: v for k, v in positions.items() if k in keep}
    counts = {k: v for k, v in counts.items() if k in keep}
    return positions, edges, counts


def plot_pass_network() -> None:
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    team = match.teams[TEAM_INDEX]
    other = match.teams[1 - TEAM_INDEX]

    positions, edges, counts = build_network(ds, match, team)
    if not positions:
        raise SystemExit(f"No passing network for {team}")

    fig, ax = plt.subplots(figsize=(13.5, 9.2))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.05)
    fs.draw_pitch(ax, style=style, show_third_lines=True)

    # --- edges ------------------------------------------------------------- #
    # Width by volume, alpha by volume: the primary passing structure reads from
    # line thickness alone, which survives greyscale printing.
    if edges:
        volumes = np.array(list(edges.values()), dtype=float)
        vmax = volumes.max()
        for (a, b), v in edges.items():
            pa, pb = positions[a], positions[b]
            frac = v / vmax
            ax.plot([pa[0], pb[0]], [pa[1], pb[1]],
                    color=fs.TEAM_COLORS["home"],
                    linewidth=0.7 + 7.0 * frac,
                    alpha=0.14 + 0.58 * frac,
                    solid_capstyle="round", zorder=3)

    # --- nodes ------------------------------------------------------------- #
    max_count = max(counts.values(), default=1)
    for name, xy in positions.items():
        c = counts[name]
        # Node radius is set by involvement, and the label is scaled to fit it.
        # Surname is preferred; if it is long, fall back to an initial so text
        # never overflows the node.
        size = 340 + 30 * c
        radius_pt = np.sqrt(size) / 2.0
        surname = name.split()[-1]
        label = surname if len(surname) <= 8 else surname[:7] + "."
        fontsize = float(np.clip(radius_pt * 0.62, 6.5, 11.0))

        ax.scatter([xy[0]], [xy[1]], s=size, color=fs.TEAM_COLORS["home"],
                   edgecolor="white", linewidth=2.2, zorder=6)
        ax.text(xy[0], xy[1] + 0.6, label, ha="center", va="center",
                fontsize=fontsize, color="white", weight="bold", zorder=7)
        ax.text(xy[0], xy[1] - fontsize * 0.34, f"{c}", ha="center", va="center",
                fontsize=fontsize * 1.05, color="white", zorder=7,
                alpha=0.95, weight="bold")

    fs.add_title(ax, f"{team} passing network",
                 f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
                 f"{match.competition} {match.season} · "
                 f"nodes = average pass origin, size = passes made, "
                 f"lines = completed passes (min 3)",
                 style=style)

    # Explicit scale key for edge width, so line thickness is readable.
    key = fig.add_axes([0.035, 0.055, 0.20, 0.13])
    key.set_xlim(0, 1)
    key.set_ylim(0, 1)
    key.axis("off")
    key.set_title("line width = passes", fontsize=10, weight="bold",
                  color=fs.PALETTE["grey_dark"], pad=4)
    for y, v in zip((0.72, 0.42, 0.12), (3, 10, 20)):
        frac = min(v / max(edges.values(), default=20), 1.0)
        key.plot([0.06, 0.44], [y, y], color=fs.TEAM_COLORS["home"],
                 linewidth=0.7 + 7.0 * frac, alpha=0.14 + 0.58 * frac,
                 solid_capstyle="round")
        key.text(0.52, y, f"{v}", fontsize=9.5, va="center",
                 color=fs.PALETTE["grey_dark"])

    fs.assert_pitch_aspect(fig, ax, label="pass network")
    for p in fs.finalize_figure(fig, FIGDIR / "passing_pass_network",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_progressive() -> None:
    """Progressive progression as a flow field, not an arrow hairball.

    One arrow per grid cell showing the mean direction and mean advance of the
    progressive passes originating there. Drawing every pass individually produces
    a few hundred overlapping arrows and reads as noise; aggregating by origin
    zone answers the actual question - "from here, where does the ball go?"
    """
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
        passes = [p for p in ds.passes(match, team) if p.is_progressive and p.completed]

        # Bucket passes by the cell their origin falls in.
        buckets: dict[tuple[int, int], list] = defaultdict(list)
        for p in passes:
            i = min(nx - 1, max(0, int(p.x / cell_w)))
            j = min(ny - 1, max(0, int(p.y / cell_h)))
            buckets[(i, j)].append(p)

        volumes = np.array([len(v) for v in buckets.values()], dtype=float)
        vmax = volumes.max() if len(volumes) else 1.0

        for (i, j), group in buckets.items():
            dx = float(np.mean([p.end_x - p.x for p in group]))
            dy = float(np.mean([p.end_y - p.y for p in group]))
            n = len(group)
            frac = n / vmax
            cx, cy = (i + 0.5) * cell_w, (j + 0.5) * cell_h
            # Anchor each arrow at the cell centre; scale its length by the mean
            # advance so longer arrows mean the ball travelled further.
            ex, ey = cx + dx, cy + dy
            ax.annotate("", xy=(ex, ey), xytext=(cx, cy),
                        arrowprops=dict(arrowstyle="-|>", color=color,
                                        linewidth=0.8 + 6.5 * frac,
                                        alpha=0.25 + 0.65 * frac,
                                        shrinkA=0, shrinkB=0,
                                        mutation_scale=12 + 16 * frac), zorder=4)
            if n >= 3:
                ax.text(cx, cy, str(n), ha="center", va="center", fontsize=10.5,
                        weight="bold", color="white", zorder=8,
                        path_effects=None,
                        bbox=dict(boxstyle="circle,pad=0.18", fc=color, ec="white",
                                  linewidth=1.4, alpha=0.95))

        n_prog = len(passes)
        n_entries = sum(1 for p in passes if p.end_x >= 102.0)
        ax.set_title(f"{team}: {n_prog} progressive passes · "
                     f"{n_entries} played into the box", fontsize=16, loc="left", pad=10)

    fig.suptitle("Progressive passing: from each zone, where does the ball go?",
                 fontsize=20, weight="bold", y=0.975)
    fig.text(0.5, 0.008,
             "A progressive pass advances the ball at least 10 yards up-pitch from the team's "
             "own 80 yards; completed only. Each arrow is one zone's mean direction and mean "
             "advance, sized by volume.\n"
             "Circled numbers mark zones with 3 or more progressive passes. Because arrows are "
             "averaged vectors, a zone that advances to both flanks can read as pointing "
             "sideways. Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for ax in axes:
        fs.assert_pitch_aspect(fig, ax, label="progressive pitch")
    for p in fs.finalize_figure(fig, FIGDIR / "passing_progressive",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_sonar() -> None:
    """One player's passes split into 12 directional wedges, stacked by outcome."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    # Feature the player who made the most passes for the home side.
    from metrics import player_metrics
    pm = player_metrics(ds, match, match.teams[TEAM_INDEX])
    star = max(pm.values(), key=lambda m: m.passes).player
    passes = [p for p in ds.passes(match, match.teams[TEAM_INDEX]) if p.player == star]

    n_wedges = 12
    fig = plt.figure(figsize=(16, 8))
    ax_pitch = fig.add_axes([0.03, 0.07, 0.44, 0.80])
    ax_sonar = fig.add_axes([0.53, 0.07, 0.44, 0.80], projection="polar")

    fs.draw_pitch(ax_pitch, style=style, show_third_lines=True)
    for p in passes:
        ax_pitch.annotate("", xy=(p.end_x, p.end_y), xytext=(p.x, p.y),
                          arrowprops=dict(arrowstyle="-|>",
                                          color=fs.ROLE["success"] if p.completed else fs.ROLE["failure"],
                                          linewidth=1.5, alpha=0.5, shrinkA=0, shrinkB=0,
                                          mutation_scale=11), zorder=4)
    ax_pitch.scatter([passes[0].x], [passes[0].y], s=260, marker="*",
                     color=fs.ROLE["highlight"], edgecolor=fs.PALETTE["ink"],
                     linewidth=1.2, zorder=8) if passes else None
    ax_pitch.set_title(f"{star}\n{len(passes)} passes · "
                       f"{sum(p.completed for p in passes)} completed",
                       fontsize=15, loc="left")
    fs.assert_pitch_aspect(fig, ax_pitch, label="sonar pitch")

    # Wedge index from pass bearing. 0 deg = straight up-pitch.
    completed = np.zeros(n_wedges)
    incomplete = np.zeros(n_wedges)
    for p in passes:
        ang = np.degrees(np.arctan2(p.end_y - p.y, p.end_x - p.x))  # -180..180
        # Fold to a 0..360 "forward is up" frame, then bucket.
        bearing = (ang + 90) % 360
        idx = int(bearing / (360 / n_wedges)) % n_wedges
        (completed if p.completed else incomplete)[idx] += 1

    theta = np.arange(n_wedges) * (2 * np.pi / n_wedges)
    width = 2 * np.pi / n_wedges * 0.94
    ax_sonar.set_theta_zero_location("N")
    ax_sonar.set_theta_direction(-1)

    ax_sonar.bar(theta, completed, width=width, bottom=incomplete,
                 color=fs.ROLE["success"], edgecolor="white", linewidth=1.0,
                 label="Completed", zorder=4)
    ax_sonar.bar(theta, incomplete, width=width,
                 color=fs.ROLE["failure"], edgecolor="white", linewidth=1.0,
                 label="Incomplete", zorder=4)

    # Direction labels, clockwise from forward, matching the bar order above.
    labels = ["FWD", "FWD-R", "RIGHT", "BACK-R", "BACK", "BACK-L",
              "LEFT", "FWD-L", "FWD", "FWD-R", "RIGHT", "BACK-R"]
    ax_sonar.set_xticks(theta)
    ax_sonar.set_xticklabels(labels, fontsize=10.5)
    ax_sonar.legend(loc="upper right", bbox_to_anchor=(1.22, 1.14), fontsize=11)
    ax_sonar.set_title("Passing direction, stacked by outcome", fontsize=15, pad=26)
    ax_sonar.grid(color=fs.PALETTE["neutral"], alpha=0.65)

    fig.suptitle(f"Passing sonar: {star}", fontsize=21, weight="bold", x=0.06, ha="left", y=0.95)
    fig.text(0.5, 0.005,
             "Bearings are relative to the team's attacking direction, so forward is always up. "
             f"{n_wedges} wedges of 30 degrees.\nData provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "passing_sonar", formats=["png", "pdf"], dpi=300):
        print("wrote", p)


if __name__ == "__main__":
    plot_pass_network()
    plot_progressive()
    plot_sonar()
