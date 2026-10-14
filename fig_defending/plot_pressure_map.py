"""Pressing and defensive figures.

    pressure_map   where each team applies pressure, as a density surface over the pitch
    def_profile    defensive actions by pitch third, plus PPDA - the pressing tradeoff
    high_turnover  where possession is won back in the attacking half

    python fig_defending/plot_pressure_map.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from metrics import team_metrics  # noqa: E402
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
FIGDIR = ROOT / "figures"


def _density_grid(xs, ys, sigma: float = 6.0, nx: int = 240, ny: int = 160):
    """Gaussian kernel-density estimate of event locations over the full pitch.

    Evaluated directly on a fine grid rather than by blurring a coarse histogram:
    convolving a low-resolution count grid produces square artefacts that contour
    as blocky, axis-aligned blobs. A direct KDE is smooth and, for a few hundred
    events, still fast.
    """
    gx = np.linspace(0, fs.PITCH_LENGTH, nx)
    gy = np.linspace(0, fs.PITCH_WIDTH, ny)
    gxx, gyy = np.meshgrid(gx, gy)
    grid = np.zeros((ny, nx))
    if len(xs) == 0:
        return grid
    inv2s2 = 1.0 / (2.0 * sigma ** 2)
    for x, y in zip(xs, ys):
        d2 = (gxx - x) ** 2 + (gyy - y) ** 2
        # Only sum where the kernel is non-negligible; this keeps it O(n_events x
        # small_window) instead of O(n_events x grid).
        grid += np.exp(-d2 * inv2s2) * (d2 < (4.0 * sigma) ** 2)
    return grid


def plot_pressure_map() -> None:
    """Pressure events for each team, as a smoothed density surface.

    Pressure events are scattered single points, so the surface is smoothed with a
    wide kernel and drawn as nested contour bands. A single quantile threshold on
    sparse points isolates each dot into its own blob, which reads as noise rather
    than as a pressing shape.
    """
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    fig, axes = plt.subplots(2, 1, figsize=(14, 13))
    fig.subplots_adjust(left=0.02, right=0.90, top=0.93, bottom=0.05, hspace=0.14)

    for ax, team in zip(axes, match.teams):
        acts = [a for a in ds.defensive_actions(match, team) if a.kind == "pressure"]
        grid = _density_grid([a.x for a in acts], [a.y for a in acts], sigma=6.0)

        fs.draw_pitch(ax, style=style, show_third_lines=True)
        gx = np.linspace(0, fs.PITCH_LENGTH, grid.shape[1])
        gy = np.linspace(0, fs.PITCH_WIDTH, grid.shape[0])

        if grid.max() > 0:
            im = ax.imshow(grid, extent=[0, fs.PITCH_LENGTH, 0, fs.PITCH_WIDTH],
                           origin="lower", cmap=fs.COUNT_CMAP, alpha=0.88,
                           interpolation="bilinear", zorder=2)
            # Nested bands scaled to this team's own peak, so the contours
            # describe pressing shape rather than absolute volume.
            levels = np.array([0.28, 0.48, 0.70, 0.88]) * grid.max()
            ax.contour(gx, gy, grid, levels=levels, colors=[fs.PALETTE["grey_dark"]],
                       linewidths=[0.9, 1.1, 1.4, 1.8], zorder=4, alpha=0.75)

        high = sum(1 for a in acts if a.x >= 80.0)
        ax.set_title(f"{team}: {len(acts)} pressures · {high} in the final third "
                     f"({high / max(len(acts), 1):.0%})",
                     fontsize=16, loc="left", pad=10)
        if grid.max() > 0:
            cb = fig.colorbar(im, ax=ax, fraction=0.028, pad=0.015)
            cb.set_label("pressure density", fontsize=11)
            cb.outline.set_visible(False)

    fig.suptitle("Pressure map: where each team presses",
                 fontsize=21, weight="bold", y=0.975)
    fig.text(0.5, 0.008,
             "Gaussian-smoothed count of pressure events (sigma = 6 yd). Contour bands mark 28%, "
             "48%, 70% and 88% of each team's own peak density,\n"
             "so the lines describe pressing shape rather than volume. "
             "Each team is orientated to attack left-to-right. Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for ax in axes:
        fs.assert_pitch_aspect(fig, ax, label="pressure pitch")
    for p in fs.finalize_figure(fig, FIGDIR / "defending_pressure_map",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_def_profile() -> None:
    """Defensive actions by third, plus the PPDA tradeoff, as a two-panel figure."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    tm = team_metrics(ds, match)
    teams = list(match.teams)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 7.2),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    fig.subplots_adjust(left=0.06, right=0.97, top=0.82, bottom=0.14, wspace=0.24)

    # --- left: actions by third, grouped by action type -------------------- #
    kinds = ["pressure", "interception", "block", "clearance", "recovery", "duel"]
    thirds = ["Defensive third", "Middle third", "Final third"]

    def third_index(x: float) -> int:
        return 0 if x < 40 else (1 if x < 80 else 2)

    series, labels = [], []
    for team in teams:
        acts = ds.defensive_actions(match, team)
        counts = [sum(1 for a in acts if third_index(a.x) == t) for t in range(3)]
        series.append(counts)
        labels.append(team)

    fs.make_grouped_bar(ax1, thirds, series, labels,
                        ylabel="defensive actions",
                        colors=[fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"]],
                        annotate=True, value_fmt="{:.0f}")
    ax1.set_title("Where defensive actions happen", fontsize=16, loc="left", pad=10)
    ax1.legend(loc="upper right", fontsize=12)

    # --- right: PPDA vs high turnovers ------------------------------------- #
    # Lower PPDA = more aggressive pressing. This is the tradeoff a coach reads:
    # pressing high wins the ball upfield but costs defensive shape.
    xs = [tm[t].ppda for t in teams]
    ys = [tm[t].high_turnovers for t in teams]
    cols = [fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"]]

    for x, y, t, c in zip(xs, ys, teams, cols):
        ax2.scatter([x], [y], s=430, color=c, edgecolor="white", linewidth=2.4,
                    zorder=5)
        ax2.annotate(t, (x, y), xytext=(0, -30), textcoords="offset points",
                     ha="center", fontsize=13, weight="bold", color=c)
        ax2.annotate(f"PPDA {x:.1f}", (x, y), xytext=(0, 26), textcoords="offset points",
                     ha="center", fontsize=11, color=fs.PALETTE["grey_dark"])

    ax2.set_xlabel("PPDA  (lower = presses more aggressively)")
    ax2.set_ylabel("high turnovers  (won in opponent's half)")
    ax2.set_title("The pressing tradeoff", fontsize=16, loc="left", pad=10)
    ax2.grid(alpha=0.25, zorder=0)
    ax2.set_axisbelow(True)
    # Pad the limits so the team labels above and below the markers are never
    # clipped, and so a single-match sample of two points is not plotted at the
    # very edge of the axes.
    span_x = (max(xs) - min(xs)) if len(xs) > 1 else 0.0
    span_y = (max(ys) - min(ys)) if len(ys) > 1 else 0.0
    pad_x = max(span_x * 1.6, 1.5)
    pad_y = max(span_y * 1.6, 3.0)
    ax2.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
    ax2.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

    fig.suptitle("Defensive profile: how each team defends",
                 fontsize=21, weight="bold", y=0.96)
    fig.text(0.5, 0.02,
             "PPDA = opponent passes allowed per defensive action in the opponent's half. "
             "High turnovers are interceptions and recoveries\nmade in the attacking half. "
             "Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "defending_profile",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_high_turnover() -> None:
    """Ball recoveries in the attacking half - the payoff of a high press."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)

    fig, ax = plt.subplots(figsize=(14, 9.2))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.08)
    fs.draw_pitch(ax, style=style, show_third_lines=True, crop="attacking-half")
    ax.set_xlim(60, 122)

    for team, marker, color in ((match.teams[0], "o", fs.TEAM_COLORS["home"]),
                                (match.teams[1], "^", fs.TEAM_COLORS["away"])):
        acts = [a for a in ds.defensive_actions(match, team)
                if a.kind in {"interception", "recovery"} and a.x >= 60.0]
        if not acts:
            continue
        ax.scatter([a.x for a in acts], [a.y for a in acts], s=185, marker=marker,
                   color=color, alpha=0.62, edgecolor="white", linewidth=1.1,
                   zorder=5, label=f"{team} ({len(acts)})")
        # Ring the turnovers won highest up the pitch - those are the ones that
        # put the opponent under immediate threat.
        high_acts = [a for a in acts if a.x >= 85.0]
        if high_acts:
            ax.scatter([a.x for a in high_acts], [a.y for a in high_acts],
                       s=430, facecolor="none", edgecolor=fs.ROLE["highlight"],
                       linewidth=2.4, zorder=6)

    ax.legend(loc="upper right", fontsize=12, markerscale=1.1)
    fs.add_title(ax, "High turnovers: winning the ball in the attacking half",
                 f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
                 f"gold rings mark turnovers at least 35 yards from goal",
                 style=style)

    fs.assert_pitch_aspect(fig, ax, label="turnover pitch")
    for p in fs.finalize_figure(fig, FIGDIR / "defending_high_turnover",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


if __name__ == "__main__":
    plot_pressure_map()
    plot_def_profile()
    plot_high_turnover()
