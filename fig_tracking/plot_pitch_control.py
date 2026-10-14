"""Pitch control and Voronoi space dominance from 360 freeze-frames.

Two panels on the same frame so the two models can be compared directly:

    Left  - Voronoi (nearest player). Exact, blocky, reads as "who is closest".
    Right - Spearman pitch control. Smooth probability surface; accounts for how
            long each player needs to reach a point, not just who is nearer.

The hatched region marks cells where fewer than six players are visible, i.e.
where the 360 sample is too sparse for the model to be trusted.

    python fig_tracking/plot_pitch_control.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "football-data-visualisation" / "scripts"))

import football_style as fs  # noqa: E402
from pitch_control import low_confidence_mask, spearman_control, voronoi_control  # noqa: E402
from sb_data import Dataset  # noqa: E402

MATCH_ID = 3869685  # FIFA World Cup 2022 Final: Argentina 3-3 France
CROP = (60.0, 120.0, 0.0, 80.0)  # attacking half - where 360 coverage is densest


def pick_frame(frames, prefer_team: str | None = None):
    """Choose a frame with strong coverage and a meaningful ball position."""
    candidates = [
        f for f in frames
        if len(f.teammates) + len(f.opponents) >= 14 and f.x > 75.0
    ]
    if not candidates:
        candidates = [f for f in frames if len(f.teammates) + len(f.opponents) >= 12]
    if not candidates:
        raise SystemExit("No usable 360 frames in this match.")
    # Prefer the frame with the most opponents nearby (a genuine contest).
    return max(candidates, key=lambda f: len(f.opponents) + len(f.teammates))


def main() -> int:
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    match = ds.match(MATCH_ID)
    frames = ds.frames(match)
    if not frames:
        raise SystemExit(f"No 360 data for match {MATCH_ID}. Fetch it first.")

    frame = pick_frame(frames)
    print(f"{match.scoreline}: using frame at "
          f"({frame.x:.0f}, {frame.y:.0f}) with "
          f"{len(frame.teammates)} teammates / {len(frame.opponents)} opponents")

    # --- models ------------------------------------------------------------ #
    voro, known = voronoi_control(frame.teammates, frame.opponents,
                                  resolution=180, bounds=CROP)
    control, coverage = spearman_control(frame.teammates, frame.opponents,
                                         ball_xy=(frame.x, frame.y),
                                         resolution=150, bounds=CROP)
    # Region where the surface is extrapolated beyond the nearest visible player.
    far = low_confidence_mask(control.shape, CROP, frame.teammates, frame.opponents,
                              horizon=42.0)

    print(f"Voronoi: possession team owns {np.mean(voro[known]):.1%} of known area")
    print(f"Control: mean {control[coverage].mean():.1%}, sd {control[coverage].std():.3f}, "
          f"extrapolated area {far.mean():.1%}")

    # --- figure ------------------------------------------------------------ #
    fig, axes = plt.subplots(1, 2, figsize=(21, 8.5))

    # Shared colormap: red (opponent) -> white (contested) -> blue (possession).
    cmap = fs.MOMENTUM_CMAP
    gx = np.linspace(CROP[0], CROP[1], control.shape[1])
    gy = np.linspace(CROP[2], CROP[3], control.shape[0])

    for ax, (surface, name, note, interp) in zip(axes, [
        (voro, "Voronoi: nearest player",
         "Hard cells. Fast and exact, but a player 1 yard closer 'owns' a whole cell.",
         "nearest"),
        (control, "Spearman pitch control",
         "Probability surface from time-to-intercept. Smooths the blocky edges.",
         "bilinear"),
    ]):
        fs.draw_pitch(ax, style=style, show_half_spaces=False)
        im = ax.imshow(
            surface, extent=[CROP[0], CROP[1], CROP[2], CROP[3]],
            origin="lower", cmap=cmap, vmin=0.0, vmax=1.0,
            interpolation=interp, alpha=0.85, zorder=2,
        )
        # Hatch the extrapolated zone rather than presenting it as measurement.
        # Linewidths must be a scalar here; contour rejects a dash tuple.
        ax.contourf(gx, gy, far.astype(float), levels=[0.5, 1.5],
                    colors="none", hatches=["////"], zorder=3)
        ax.contour(gx, gy, far.astype(float), levels=[0.5],
                   colors=[fs.PALETTE["grey_mid"]], linewidths=1.0,
                   linestyles="dashed", zorder=4)

        # Players on top. Ring colour = team; matches the surface colour scheme.
        if len(frame.opponents):
            ax.scatter(frame.opponents[:, 0], frame.opponents[:, 1], s=170,
                       color="white", edgecolor=fs.ROLE["defend"], linewidth=3.0,
                       zorder=8, label="Opponents")
        if len(frame.teammates):
            ax.scatter(frame.teammates[:, 0], frame.teammates[:, 1], s=170,
                       color=fs.ROLE["attack"], edgecolor="white", linewidth=2.0,
                       zorder=8, label="In possession")

        # Ball and its carrier.
        ax.scatter([frame.x], [frame.y], s=440, marker="o", facecolor="white",
                   edgecolor=fs.PALETTE["ink"], linewidth=2.2, zorder=10)
        ax.scatter([frame.x], [frame.y], s=95, marker="o",
                   color=fs.PALETTE["highlight"], edgecolor="none", zorder=11)

        fs.add_title(ax, name, note, style=style)

    # One shared, honest colorbar.
    cbar = fig.colorbar(im, ax=axes, fraction=0.022, pad=0.02)
    cbar.set_label("Share of control held by the team in possession", fontsize=12)
    cbar.outline.set_visible(False)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(["0%\nopponent", "25%", "50%\ncontested", "75%", "100%\npossession"])

    axes[0].legend(loc="lower left", fontsize=12, markerscale=1.1)
    fig.text(0.5, -0.02,
             "Hatched = more than 42 yd from the nearest visible player, where the surface is "
             "extrapolated rather than measured.\n"
             f"{match.home} {match.home_score}-{match.away_score} {match.away} · "
             f"{match.competition} {match.season} · attacking half only, "
             f"{len(frame.teammates) + len(frame.opponents)} of 22 players visible. "
             "Data provided by StatsBomb.",
             ha="center", fontsize=10, color=fs.PALETTE["grey_mid"])

    paths = fs.finalize_figure(fig, ROOT / "figures" / "tracking_pitch_control",
                               formats=["png", "pdf"], dpi=300)
    for p in paths:
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
