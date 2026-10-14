"""Player and team comparison: radars, percentile bars, and similarity.

This family is the closest port of the source repo's method-comparison figures:
the `figure_VIGIL` radar and `figure_ImmunoStruct` grouped bars, retargeted from
"my model vs baselines" to "this player vs their positional peers".

    radar         two players on shared axes, percentile-ranked within position
    percentiles   a player's percentile bar chart across every metric
    similarity    who plays most like a given player, by metric vector distance

    python fig_comparison/plot_radar.py
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
from metrics import PlayerMetrics, player_metrics  # noqa: E402
from sb_data import Dataset  # noqa: E402

#: The season used for peer-group comparison. WC2022 has 64 matches with full
#: event data, which is enough for percentiles to mean something.
COMPETITION_ID, SEASON_ID = 43, 106
FIGDIR = ROOT / "figures"

#: Radar axes: (label, attribute on PlayerMetrics, per-90 normalised?)
RADAR_AXES = [
    ("Goals", "goals", True),
    ("xG", "xg", True),
    ("Shots", "shots", True),
    ("Prog. passes", "progressive_passes", True),
    ("xT created", "xt", True),
    ("Key passes", "key_passes", True),
    ("Prog. carries", "progressive_carries", True),
    ("Pressures", "pressures", True),
]


def _season_players(ds: Dataset, limit: int | None = None) -> dict[str, PlayerMetrics]:
    """Aggregate every player over a whole season of cached matches.

    Percentiles are only meaningful against a peer group, so this pools all
    cached matches from the season rather than comparing within one game.
    """
    ids = ds.cached_match_ids(with_frames=False)
    fixtures = ds.fixtures(COMPETITION_ID, SEASON_ID)
    season_ids = [f["match_id"] for f in fixtures if f["match_id"] in set(ids)]
    if limit:
        season_ids = season_ids[:limit]

    pooled: dict[str, PlayerMetrics] = {}
    for mid in season_ids:
        try:
            match = ds.match(mid)
        except FileNotFoundError:
            continue
        for name, m in player_metrics(ds, match).items():
            agg = pooled.get(name)
            if agg is None:
                agg = PlayerMetrics(player=m.player, team=m.team)
                pooled[name] = agg
            agg.minutes += m.minutes
            for field_name in ("shots", "goals", "passes", "passes_completed",
                               "progressive_passes", "line_breaking_passes",
                               "key_passes", "assists", "progressive_carries",
                               "pressures", "interceptions", "blocks", "clearances",
                               "recoveries", "duels", "duels_won",
                               "touches_final_third", "touches_box"):
                setattr(agg, field_name, getattr(agg, field_name) + getattr(m, field_name))
            for attr in ("xg", "npxg", "xt", "carry_distance"):
                setattr(agg, attr, getattr(agg, attr) + getattr(m, attr))
            agg.pass_links.update(m.pass_links)
    # Drop players with too little time for a rate to be stable.
    return {k: v for k, v in pooled.items() if v.minutes >= 180}


def _percentile_ranks(pool: dict[str, PlayerMetrics], field: str,
                      per90: bool = True) -> dict[str, float]:
    """Percentile rank of every player on one metric (0-100)."""
    vals = {}
    for name, m in pool.items():
        v = getattr(m, field)
        vals[name] = (v * m.per90) if per90 else float(v)
    ordered = sorted(vals.items(), key=lambda kv: kv[1])
    n = len(ordered)
    return {name: (rank / max(n - 1, 1)) * 100.0 for rank, (name, _) in enumerate(ordered)}


def plot_radar() -> None:
    """Two attackers, percentile-ranked within the tournament's player pool."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    pool = _season_players(ds)
    if len(pool) < 30:
        raise SystemExit(
            f"Only {len(pool)} players with 180+ minutes cached. "
            "Run:  python football-data-visualisation/scripts/fetch_statsbomb.py --core"
        )
    print(f"peer group: {len(pool)} players with 180+ minutes in "
          f"{ds.fixtures(COMPETITION_ID, SEASON_ID)[0]['season']['season_name']}")

    # Feature the two highest-minutes forwards in the pool (by xG).
    tops = sorted(pool.values(), key=lambda m: m.xg, reverse=True)[:2]
    picks = [m.player for m in tops]
    if len(picks) < 2:
        raise SystemExit("Need at least two players to compare.")

    labels = [a[0] for a in RADAR_AXES]
    series = []
    for name in picks:
        ranks = []
        for _, field, per90 in RADAR_AXES:
            pr = _percentile_ranks(pool, field, per90)
            ranks.append(pr.get(name, 0.0))
        series.append(ranks)

    fig = plt.figure(figsize=(16, 9.6))
    # The radial axis labels sit outside the polar axes on every side, so the
    # axes is inset well within the canvas and the caption lives in the left
    # margin rather than underneath, where it would collide with "xT created".
    ax = fig.add_axes([0.33, 0.05, 0.60, 0.80], projection="polar")

    fs.make_radar(ax, labels, series, picks,
                  colors=[fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"]],
                  rmin=0, rmax=100, fill_alpha=0.16)
    # Percentile rings: these are the point of the chart, so label them clearly.
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20th", "40th", "60th", "80th", "100th"], fontsize=9,
                       color=fs.PALETTE["grey_dark"])
    ax.set_rlabel_position(196)
    ax.tick_params(axis="x", pad=12)
    ax.legend(loc="upper left", bbox_to_anchor=(-0.30, 1.10), fontsize=13,
              handlelength=1.6)

    fig.suptitle("Player radar: percentile rank among tournament peers",
                 fontsize=21, weight="bold", x=0.04, ha="left", y=0.965)

    # Left column: who is being compared, and the pool they are ranked against.
    y = 0.86
    for m, name, color in zip(tops, picks,
                              (fs.TEAM_COLORS["home"], fs.TEAM_COLORS["away"])):
        fig.text(0.04, y, name, fontsize=14, weight="bold", color=color, ha="left")
        fig.text(0.04, y - 0.042,
                 f"{m.team} · {m.minutes:.0f} min · {m.goals} goals from {m.xg:.2f} xG",
                 fontsize=11.5, color=fs.PALETTE["grey_mid"], ha="left")
        y -= 0.115

    fig.text(0.04, 0.56,
             f"Peer group\n{len(pool)} players with\n180+ minutes in the\nsame competition\nand season",
             fontsize=11.5, color=fs.PALETTE["grey_dark"], ha="left", va="top",
             linespacing=1.5)
    fig.text(0.04, 0.30,
             "Every axis is a percentile:\n100 = best in the pool.\n"
             "All rates are per 90 minutes.\nData provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"], ha="left", va="top",
             linespacing=1.6)

    for p in fs.finalize_figure(fig, FIGDIR / "comparison_radar",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_percentiles() -> None:
    """A single player's full percentile profile as a horizontal bar chart."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    pool = _season_players(ds)
    if len(pool) < 30:
        raise SystemExit("Not enough cached players for percentiles; fetch --core first.")

    target = max(pool.values(), key=lambda m: m.xg).player
    metrics = [
        ("Goals", "goals", True), ("xG", "xg", True), ("Shots", "shots", True),
        ("Shot quality (xG/shot)", None, False),
        ("Progressive passes", "progressive_passes", True),
        ("Line-breaking passes", "line_breaking_passes", True),
        ("Pass completion", None, False),
        ("xT created", "xt", True),
        ("Progressive carries", "progressive_carries", True),
        ("Pressures", "pressures", True),
        ("Interceptions", "interceptions", True),
        ("Duels won", "duels_won", True),
    ]

    # Derived ratios need their own percentile pass, so build the value function.
    def value_of(m: PlayerMetrics, field: str | None) -> float:
        if field is None:
            return 0.0
        v = getattr(m, field)
        return v * m.per90

    def derived_value(m: PlayerMetrics, label: str) -> float:
        if label == "Shot quality (xG/shot)":
            return m.xg_per_shot
        if label == "Pass completion":
            return m.pass_completion
        return 0.0

    def pct_for(label: str, field: str | None, per90: bool) -> float:
        if field is not None:
            return _percentile_ranks(pool, field, per90).get(target, 0.0)
        # Percentile-rank a derived ratio directly.
        vals = sorted((derived_value(m, label), n) for n, m in pool.items())
        names = [n for _, n in vals]
        if target not in names:
            return 0.0
        return names.index(target) / max(len(names) - 1, 1) * 100.0

    labels = [m[0] for m in metrics]
    pcts = [pct_for(*m) for m in metrics]
    raw = []
    for label, field, _ in metrics:
        if field is not None:
            raw.append(f"{value_of(pool[target], field):.2f}")
        elif label == "Shot quality (xG/shot)":
            raw.append(f"{pool[target].xg_per_shot:.3f}")
        else:
            raw.append(f"{pool[target].pass_completion:.0%}")

    fig, ax = plt.subplots(figsize=(12.5, 10.2))
    fig.subplots_adjust(left=0.30, right=0.90, top=0.85, bottom=0.16)

    y = np.arange(len(labels))[::-1]
    # Diverging colour around the median: above-average and below-average read
    # differently, which is the whole point of a percentile chart.
    colors = [fs.ROLE["success"] if p >= 50 else fs.ROLE["defend_alt"] for p in pcts]
    bars = ax.barh(y, pcts, height=0.62, color=colors, edgecolor="white",
                   linewidth=1.4, zorder=4)
    ax.axvline(50, color=fs.PALETTE["grey_dark"], linewidth=1.6,
               linestyle="dashed", zorder=5)
    ax.text(50, len(labels) - 0.3, " tournament median", fontsize=10.5,
            color=fs.PALETTE["grey_dark"], va="center")

    for bar, p, r in zip(bars, pcts, raw):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{p:.0f}th   ({r})", va="center", fontsize=11,
                color=fs.PALETTE["ink"], zorder=6)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=13)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0th", "25th", "50th", "75th", "100th"])
    ax.set_xlabel("percentile among tournament peers", labelpad=10)
    ax.grid(axis="x", alpha=0.22, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    m = pool[target]
    fig.suptitle(f"{target}: percentile profile",
                 fontsize=22, weight="bold", x=0.30, ha="left", y=0.96)
    fig.text(0.30, 0.905,
             f"{m.team} · {m.minutes:.0f} minutes · {m.goals} goals from {m.xg:.2f} xG",
             fontsize=13, color=fs.PALETTE["grey_mid"], ha="left")
    # Footnote sits below the axes x-label, so the two cannot overlap.
    fig.text(0.30, 0.025,
             f"Percentiles are against {len(pool)} players with 180+ minutes in the same "
             "competition and season. Bracketed values are raw per-90 figures\n"
             "(or the ratio itself for xG/shot and pass completion). "
             "Data provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"], ha="left", va="bottom")

    for p in fs.finalize_figure(fig, FIGDIR / "comparison_percentiles",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


def plot_similarity() -> None:
    """Players most similar to a target, on a z-scored metric vector."""
    style = fs.apply_pitch_style()
    ds = Dataset.load()
    pool = _season_players(ds)
    if len(pool) < 30:
        raise SystemExit("Not enough cached players for similarity; fetch --core first.")

    fields = ["shots", "xg", "progressive_passes", "line_breaking_passes",
              "key_passes", "xt", "progressive_carries", "pressures",
              "interceptions", "duels_won"]
    names = list(pool)
    # Per-90 matrix, then z-scored per column so no single metric dominates the
    # distance simply because its units are larger.
    mat = np.array([[getattr(pool[n], f) * pool[n].per90 for f in fields] for n in names])
    z = (mat - mat.mean(axis=0)) / np.where(mat.std(axis=0) > 0, mat.std(axis=0), 1.0)

    target = max(pool.values(), key=lambda m: m.xg).player
    ti = names.index(target)
    dist = np.linalg.norm(z - z[ti], axis=1)
    order = np.argsort(dist)[1:9]  # exclude self

    fig, ax = plt.subplots(figsize=(12.5, 8.2))
    fig.subplots_adjust(left=0.24, right=0.95, top=0.84, bottom=0.13)

    y = np.arange(len(order))[::-1]
    sims = [1.0 / (1.0 + dist[i]) for i in order]
    ax.barh(y, sims, height=0.64, color=fs.TEAM_COLORS["home"], alpha=0.85,
            edgecolor="white", linewidth=1.3, zorder=4)

    for yy, i, s in zip(y, order, sims):
        ax.text(s + 0.004, yy, f"{s:.3f}", va="center", fontsize=11,
                color=fs.PALETTE["ink"], zorder=6)
        ax.text(-0.006, yy, pool[names[i]].team, va="center", ha="right",
                fontsize=10.5, color=fs.PALETTE["grey_mid"], zorder=6)

    ax.set_yticks(y)
    ax.set_yticklabels([names[i] for i in order], fontsize=13)
    ax.set_xlabel("similarity  (1 / (1 + z-scored metric distance))")
    ax.set_xlim(0, max(sims) * 1.18)
    ax.grid(axis="x", alpha=0.22, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.suptitle(f"Who plays most like {target}?",
                 fontsize=22, weight="bold", x=0.06, ha="left", y=0.95)
    fig.text(0.06, 0.02,
             f"Metrics ({', '.join(f.replace('_', ' ') for f in fields)}), all per 90, "
             "z-scored across the peer group, compared by Euclidean distance.\n"
             "Similarity is a stylistic proxy: it describes statistical profile, not quality. "
             "Data provided by StatsBomb.",
             fontsize=10, color=fs.PALETTE["grey_mid"])

    for p in fs.finalize_figure(fig, FIGDIR / "comparison_similarity",
                                formats=["png", "pdf"], dpi=300):
        print("wrote", p)


if __name__ == "__main__":
    plot_radar()
    plot_percentiles()
    plot_similarity()
