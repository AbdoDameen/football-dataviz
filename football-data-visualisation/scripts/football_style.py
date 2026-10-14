"""Football house style: pitch geometry, palette, rcParams, and plot helpers.

This is the direct analogue of ``scientific-figure-making/references/api.md`` in
figures4papers, retargeted from lab-bench plots to football.

The single most important adaptation: figures4papers colours by **method**
(blue = proposed, red = baseline). Football figures colour by **role** - who is
attacking, who is defending, and whether an action succeeded. ``ROLE`` encodes
that, and ``TEAM_COLORS`` derives two-team palettes from it.

Usage
-----
    from football_style import apply_pitch_style, draw_pitch, finalize_figure
    apply_pitch_style()
    fig, ax = plt.subplots(figsize=(12, 8))
    draw_pitch(ax)
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import numpy as np

mpl.use("Agg", force=False)
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch

# --------------------------------------------------------------------------- #
# Pitch geometry (StatsBomb 120 x 80 yards)
# --------------------------------------------------------------------------- #
PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0

PENALTY_AREA_DEPTH = 18.0
PENALTY_AREA_HALF_WIDTH = 20.0  # 40 yards wide
SIX_YARD_DEPTH = 6.0
SIX_YARD_HALF_WIDTH = 10.0
PENALTY_SPOT = 12.0
CENTRE_CIRCLE_R = 10.0
CORNER_ARC_R = 1.0
GOAL_HALF_WIDTH = 4.0
GOAL_DEPTH = 1.8

# Goal-mouth plots use real-world metres rather than pitch yards.
GOAL_WIDTH_M = 7.32
GOAL_HEIGHT_M = 2.44


# --------------------------------------------------------------------------- #
# Palette - role semantics, ported from figures4papers' method semantics
# --------------------------------------------------------------------------- #
PALETTE = {
    # Anchors (kept from the source repo so the visual DNA survives)
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "blue_light": "#8FB8DE",
    "blue_pale": "#DCE9F5",
    "green_1": "#DDF3DE",
    "green_2": "#AADCA9",
    "green_3": "#8BCF8B",
    "green_strong": "#2E7D4F",
    "red_1": "#F6CFCB",
    "red_2": "#E9A6A1",
    "red_strong": "#B64342",
    "amber": "#E8A33D",
    "amber_light": "#F7DFB5",
    "highlight": "#FFD700",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "neutral": "#CFCECE",
    "grey_mid": "#767676",
    "grey_dark": "#4D4D4D",
    "ink": "#272727",
    "paper": "#FFFFFF",
    "pitch_dark": "#2B2F3A",
    "pitch_light": "#FBFBF9",
}

#: Role semantics. Football figures encode *who* and *outcome*, not *method*.
ROLE = {
    "attack": PALETTE["blue_main"],
    "attack_alt": PALETTE["blue_secondary"],
    "attack_faint": PALETTE["blue_light"],
    "defend": PALETTE["red_strong"],
    "defend_alt": PALETTE["red_2"],
    "defend_faint": PALETTE["red_1"],
    "success": PALETTE["green_strong"],
    "success_faint": PALETTE["green_2"],
    "failure": PALETTE["grey_mid"],
    "neutral": PALETTE["neutral"],
    "highlight": PALETTE["highlight"],
    "context": PALETTE["amber"],
    "context_faint": PALETTE["amber_light"],
    "ink": PALETTE["ink"],
}

DEFAULT_COLORS = [
    PALETTE["blue_main"], PALETTE["green_3"], PALETTE["red_strong"],
    PALETTE["teal"], PALETTE["violet"], PALETTE["neutral"],
]

#: Two-team match palettes. Home always reads blue, away always reads red.
TEAM_COLORS = {
    "home": PALETTE["blue_main"],
    "home_alt": PALETTE["blue_secondary"],
    "away": PALETTE["red_strong"],
    "away_alt": PALETTE["red_2"],
    "neutral": PALETTE["grey_mid"],
}

#: Diverging map for momentum / +/- style charts (away -> neutral -> home).
MOMENTUM_CMAP = mpl.colors.LinearSegmentedColormap.from_list(
    "momentum", [PALETTE["red_strong"], "#F4F4F2", PALETTE["blue_main"]]
)
#: Sequential map for density / threat surfaces.
THREAT_CMAP = mpl.colors.LinearSegmentedColormap.from_list(
    "threat", ["#F7F7F4", PALETTE["amber_light"], PALETTE["amber"], PALETTE["red_2"], PALETTE["red_strong"]]
)
#: Sequential map for counts (pressures, passes, touches) on a light pitch.
COUNT_CMAP = mpl.colors.LinearSegmentedColormap.from_list(
    "count", ["#F2F5F9", PALETTE["blue_pale"], PALETTE["blue_light"], PALETTE["blue_secondary"], PALETTE["blue_main"]]
)


@dataclass(frozen=True)
class PitchStyle:
    """Sizing and line conventions for football figures."""

    font_size: int = 16
    title_size: int = 22
    label_size: int = 13
    axes_linewidth: float = 2.0
    pitch_linewidth: float = 1.6
    pitch_color: str = "#FBFBF9"
    line_color: str = "#C9CEC9"
    transparent_pitch: bool = False
    use_tex: bool = False
    dark: bool = False
    font_family: tuple[str, ...] = ("Arial", "Helvetica", "DejaVu Sans", "sans-serif")


#: Print/publication preset: light pitch, thin grey lines, larger type.
PRINT_STYLE = PitchStyle()
#: Broadcast preset: dark pitch, brighter lines, smaller type (matches TV graphics).
BROADCAST_STYLE = PitchStyle(
    font_size=14, title_size=20, label_size=12,
    axes_linewidth=0.0, pitch_linewidth=1.4,
    pitch_color=PALETTE["pitch_dark"], line_color="#5A6270", dark=True,
)


def apply_pitch_style(style: PitchStyle | None = None) -> PitchStyle:
    """Set the global matplotlib rcParams for football figures. Returns the style."""
    style = style or PRINT_STYLE
    fg = "#F2F2F2" if style.dark else PALETTE["ink"]
    mpl.rcParams.update({
        "font.family": list(style.font_family),
        "font.size": style.font_size,
        "axes.titlesize": style.title_size,
        "axes.labelsize": style.label_size,
        "axes.titleweight": "bold",
        "axes.linewidth": style.axes_linewidth,
        "axes.edgecolor": fg,
        "axes.labelcolor": fg,
        "text.color": fg,
        "xtick.color": fg,
        "ytick.color": fg,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "legend.fontsize": style.label_size,
        "figure.facecolor": style.pitch_color if style.dark else PALETTE["paper"],
        "savefig.facecolor": style.pitch_color if style.dark else PALETTE["paper"],
        "svg.fonttype": "none",
        "figure.dpi": 110,
        "text.usetex": style.use_tex,
    })
    return style


# --------------------------------------------------------------------------- #
# Pitch drawing
# --------------------------------------------------------------------------- #
def _pitch_paths(style: PitchStyle, zorder: float = 1) -> list:
    """Build the linework of a full 120x80 pitch as matplotlib patches."""
    lw = style.pitch_linewidth
    c = style.line_color
    common = dict(facecolor="none", edgecolor=c, linewidth=lw, zorder=zorder)

    p = [
        Rectangle((0, 0), PITCH_LENGTH, PITCH_WIDTH, facecolor="none", edgecolor=c,
                  linewidth=lw, zorder=zorder),
        # Halfway line is a Line2D-style patch so it stays visible at any aspect.
        plt.Line2D([PITCH_LENGTH / 2, PITCH_LENGTH / 2], [0, PITCH_WIDTH],
                   color=c, linewidth=lw, zorder=zorder),
        Circle((PITCH_LENGTH / 2, PITCH_WIDTH / 2), CENTRE_CIRCLE_R, **common),
        Circle((PITCH_LENGTH / 2, PITCH_WIDTH / 2), 0.6, facecolor=c, edgecolor=c,
               zorder=zorder),
    ]
    # Both ends: penalty area, six-yard box, penalty spot, D-arc, goal, corner arcs.
    for side in (0, 1):
        sgn = 1 if side == 0 else -1
        x0 = 0.0 if side == 0 else PITCH_LENGTH
        p.append(Rectangle(
            (x0 if side == 0 else x0 - PENALTY_AREA_DEPTH, PITCH_WIDTH / 2 - PENALTY_AREA_HALF_WIDTH),
            PENALTY_AREA_DEPTH, 2 * PENALTY_AREA_HALF_WIDTH, **common))
        p.append(Rectangle(
            (x0 if side == 0 else x0 - SIX_YARD_DEPTH, PITCH_WIDTH / 2 - SIX_YARD_HALF_WIDTH),
            SIX_YARD_DEPTH, 2 * SIX_YARD_HALF_WIDTH, **common))
        spot_x = x0 + sgn * PENALTY_SPOT
        p.append(Circle((spot_x, PITCH_WIDTH / 2), 0.5, facecolor=c, edgecolor=c,
                        zorder=zorder))
        # Penalty arc: only the part outside the box is drawn.
        theta1, theta2 = (37, 143) if side == 0 else (217, 323)
        p.append(Arc((spot_x, PITCH_WIDTH / 2), 2 * CENTRE_CIRCLE_R, 2 * CENTRE_CIRCLE_R,
                     theta1=theta1, theta2=theta2, edgecolor=c, linewidth=lw,
                     zorder=zorder))
        # Goal itself, drawn just outside the goal line and within the canvas.
        gy = PITCH_WIDTH / 2 - GOAL_HALF_WIDTH
        gx = -GOAL_DEPTH if side == 0 else PITCH_LENGTH
        p.append(Rectangle((gx, gy), GOAL_DEPTH, 2 * GOAL_HALF_WIDTH,
                           facecolor="none", edgecolor=c, linewidth=lw * 1.5,
                           zorder=zorder))
        # Corner arcs: drawn from the goal-line end of the arc.
        for cy in (0.0, PITCH_WIDTH):
            t1, t2 = (0, 90) if cy == 0 else (270, 360)
            p.append(Arc((0 if cy == 0 else PITCH_LENGTH, cy), 2 * CORNER_ARC_R,
                         2 * CORNER_ARC_R, theta1=t1, theta2=t2,
                         edgecolor=c, linewidth=lw, zorder=zorder))
    return p


def draw_pitch(ax, style: PitchStyle | None = None, orientation: str = "horizontal",
               show_third_lines: bool = False, show_half_spaces: bool = False,
               grass_stripes: int = 0, label: str | None = None, crop: str | None = None,
               zorder: float = 1):
    """Draw a pitch onto ``ax`` and configure its limits.

    Parameters
    ----------
    orientation : ``"horizontal"`` (attacking left-to-right) or ``"vertical"``.
    show_third_lines : faint vertical lines splitting the pitch into thirds.
    show_half_spaces : shade the four half-space corridors (the zones football
        analysts care about most and generic pitch drawings never show).
    grass_stripes : number of mowing stripes for a broadcast look.
    crop : ``"attacking-half"``, ``"final-third"``, ``"box"`` or ``None``.
    zorder : linework depth. Raise it above an opaque data overlay (for example
        an `imshow` zone grid) so the pitch markings stay visible for orientation.
    """
    style = style or PRINT_STYLE
    ax.set_facecolor(style.pitch_color)

    if grass_stripes:
        stripe_w = PITCH_LENGTH / grass_stripes
        for i in range(grass_stripes):
            shade = 1.0 if i % 2 == 0 else 0.965
            ax.add_patch(Rectangle(
                (i * stripe_w, 0), stripe_w, PITCH_WIDTH,
                facecolor="none", edgecolor="none",
                zorder=0, alpha=0,
            ))
            ax.axvspan(i * stripe_w, (i + 1) * stripe_w,
                       color="white", alpha=0.035 if shade == 1.0 else 0.0, zorder=0)

    for patch in _pitch_paths(style, zorder=zorder):
        if isinstance(patch, plt.Line2D):
            ax.add_line(patch)
        else:
            ax.add_patch(patch)

    if show_third_lines:
        for x in (40.0, 80.0):
            ax.plot([x, x], [0, PITCH_WIDTH], color=style.line_color,
                    linewidth=style.pitch_linewidth * 0.8, linestyle=(0, (6, 6)),
                    alpha=0.75, zorder=zorder)

    if show_half_spaces:
        # Standard half-space definition: between the six-yard box edge and the
        # penalty-area edge, i.e. y in [10, 20] and [60, 70] from the goal line.
        for x0, x1 in ((102.0, 120.0), (0.0, 18.0)):
            for y0, y1 in ((10.0, 20.0), (60.0, 70.0)):
                ax.add_patch(Rectangle(
                    (x0, y0), x1 - x0, y1 - y0,
                    facecolor=PALETTE["blue_main"], alpha=0.055,
                    edgecolor="none", zorder=0))

    _set_pitch_limits(ax, orientation=orientation, crop=crop)

    if label:
        ax.text(0.985, 0.975, label, transform=ax.transAxes,
                fontsize=style.label_size, ha="right", va="top",
                color=PALETTE["grey_dark"] if not style.dark else "#B9C0CC", zorder=20)
    return ax


def _set_pitch_limits(ax, orientation: str, crop: str | None) -> None:
    if crop == "attacking-half":
        xlim, ylim = (60.0, 120.0), (0.0, PITCH_WIDTH)
    elif crop == "final-third":
        xlim, ylim = (80.0, 120.0), (0.0, PITCH_WIDTH)
    elif crop == "box":
        xlim, ylim = (96.0, 121.5), (12.0, 68.0)
    else:
        xlim, ylim = (-GOAL_DEPTH - 0.8, PITCH_LENGTH + GOAL_DEPTH + 0.8), (-1.5, PITCH_WIDTH + 1.5)

    ax.set_aspect("equal")
    if orientation == "vertical":
        ax.set_xlim(ylim)
        ax.set_ylim(xlim)
    else:
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    # Re-assert equal aspect *after* the limits: several helpers (notably
    # matplotlib's imshow, whose default aspect is "auto") will otherwise reset it
    # and silently stretch the pitch. This makes draw_pitch authoritative.
    ax.set_aspect("equal")
    for s in ax.spines.values():
        s.set_visible(False)


def orient(ax, orientation: str):
    """Return ``(transform, limits)`` helpers so vertical figures reuse code.

    For ``orientation="vertical"`` the swap is simply ``(y, x)``; this keeps a
    single coordinate system across every figure in the project.
    """
    if orientation == "horizontal":
        return (lambda xy: (np.asarray(xy)[..., 0], np.asarray(xy)[..., 1])), (PITCH_LENGTH, PITCH_WIDTH)
    return (lambda xy: (np.asarray(xy)[..., 1], np.asarray(xy)[..., 0])), (PITCH_WIDTH, PITCH_LENGTH)


# --------------------------------------------------------------------------- #
# Generic plot helpers (ports of figures4papers' make_* API)
# --------------------------------------------------------------------------- #
def make_grouped_bar(ax, categories, series, labels, ylabel="Value", colors=None,
                     annotate=False, value_fmt="{:.1f}", ylim=None, horizontal=False):
    """Grouped bars. ``series`` is a list of arrays, one per group."""
    n_groups = len(series)
    n_cats = len(categories)
    colors = colors or DEFAULT_COLORS
    x = np.arange(n_cats, dtype=float)
    width = 0.8 / n_groups
    containers = []
    for i, (vals, lab) in enumerate(zip(series, labels)):
        offset = (i - (n_groups - 1) / 2) * width
        vals = np.asarray(vals, dtype=float)
        if horizontal:
            bars = ax.barh(x + offset, vals, height=width * 0.92,
                           color=colors[i % len(colors)], label=lab,
                           edgecolor=PALETTE["ink"], linewidth=1.1, zorder=3)
        else:
            bars = ax.bar(x + offset, vals, width=width * 0.92,
                          color=colors[i % len(colors)], label=lab,
                          edgecolor=PALETTE["ink"], linewidth=1.1, zorder=3)
        containers.append(bars)
        if annotate:
            fmt = value_fmt.format
            for bar, v in zip(bars, vals):
                if horizontal:
                    ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                            " " + fmt(v), va="center", ha="left", fontsize=11)
                else:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height(), fmt(v), ha="center", va="bottom",
                            fontsize=11)
    if horizontal:
        ax.set_yticks(x)
        ax.set_yticklabels(categories)
        ax.set_xlabel(ylabel)
    else:
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.set_ylabel(ylabel)
    if ylim is not None:
        (ax.set_xlim if horizontal else ax.set_ylim)(ylim)
    ax.grid(axis="x" if horizontal else "y", alpha=0.25, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    return containers[-1]


def make_trend(ax, x, y_series, labels, colors=None, ylabel=None, xlabel=None,
               show_shadow=True, linewidth=2.6, marker=None, step=False):
    """Line series with an optional band for spread/uncertainty."""
    colors = colors or DEFAULT_COLORS
    x = np.asarray(x, dtype=float)
    for i, (ys, lab) in enumerate(zip(y_series, labels)):
        ys = np.asarray(ys, dtype=float)
        c = colors[i % len(colors)]
        if ys.ndim == 2:
            mean = ys.mean(axis=0)
            if show_shadow:
                ax.fill_between(x, ys.min(axis=0), ys.max(axis=0), color=c, alpha=0.18, linewidth=0)
            ys = mean
        drawstyle = "steps-post" if step else "default"
        ax.plot(x, ys, color=c, linewidth=linewidth, label=lab,
                marker=marker, drawstyle=drawstyle, zorder=3, solid_capstyle="round")
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.grid(alpha=0.22, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    return ax


def make_heatmap(ax, matrix, x_labels=None, y_labels=None, cmap=None, cbar_label=None,
                 annotate=False, vmin=None, vmax=None, cbar=True):
    """Heatmap on ``ax``; returns the ``AxesImage``."""
    matrix = np.asarray(matrix, dtype=float)
    im = ax.imshow(matrix, cmap=cmap or COUNT_CMAP, vmin=vmin, vmax=vmax,
                   aspect="auto", interpolation="nearest")
    if x_labels is not None:
        ax.set_xticks(np.arange(len(x_labels)))
        ax.set_xticklabels(x_labels)
    if y_labels is not None:
        ax.set_yticks(np.arange(len(y_labels)))
        ax.set_yticklabels(y_labels)
    if annotate:
        norm = im.norm
        for (j, i), v in np.ndenumerate(matrix):
            ax.text(i, j, f"{v:.2f}", ha="center", va="center", fontsize=11,
                    color="white" if norm(v) > 0.62 else PALETTE["ink"])
    if cbar:
        cb = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        if cbar_label:
            cb.set_label(cbar_label)
        cb.outline.set_visible(False)
    return im


def make_scatter(ax, x, y, label=None, color=None, size=50, alpha=0.7,
                 edgecolor="none", zorder=4, **kw):
    """Single-series scatter with sensible defaults."""
    return ax.scatter(x, y, s=size, alpha=alpha, label=label,
                      color=color or PALETTE["blue_main"],
                      edgecolor=edgecolor, zorder=zorder, **kw)


def make_radar(ax, categories, series, labels, colors=None, fill_alpha=0.18,
               rmin=0.0, rmax=None, ring_labels=True):
    """Radar/polar chart. ``series`` is a list of arrays of len(categories)."""
    colors = colors or DEFAULT_COLORS
    n = len(categories)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    all_vals = np.concatenate([np.asarray(s, dtype=float) for s in series])
    rmax = rmax if rmax is not None else float(np.nanmax(all_vals) * 1.08)
    for i, (vals, lab) in enumerate(zip(series, labels)):
        vals = np.asarray(vals, dtype=float).tolist()
        vals += vals[:1]
        c = colors[i % len(colors)]
        ax.plot(angles, vals, color=c, linewidth=2.6, label=lab, zorder=3)
        ax.fill(angles, vals, color=c, alpha=fill_alpha, zorder=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(rmin, rmax)
    if ring_labels:
        ax.set_yticks(np.linspace(rmin, rmax, 5)[1:])
        ax.set_yticklabels([f"{v:.0f}" for v in np.linspace(rmin, rmax, 5)[1:]], fontsize=9)
    else:
        ax.set_yticks([])
    ax.grid(color=PALETTE["neutral"], alpha=0.7, linewidth=0.9)
    ax.spines["polar"].set_color(PALETTE["neutral"])
    return ax


def annotate_point(ax, x, y, text, dx=1.2, dy=1.2, fontsize=10, color=None,
                   ha="left", va="bottom", weight="normal"):
    """Small labelled callout - the football equivalent of annotate_bars."""
    return ax.annotate(text, (x, y), xytext=(x + dx, y + dy),
                       fontsize=fontsize, ha=ha, va=va, weight=weight,
                       color=color or PALETTE["ink"], zorder=10)


def legend_panel(fig, handles, labels, loc="lower center", ncol=4, **kw):
    """Repo convention: a dedicated legend so data panels stay clean."""
    fig.legend(handles, labels, loc=loc, ncol=ncol, frameon=False, **kw)


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
SUPPORTED_FORMATS = {"pdf", "svg", "eps", "png", "jpg", "jpeg", "tif", "tiff"}


def assert_pitch_aspect(fig, ax, label="axes", tol=0.01):
    """Raise unless ``ax`` maps one data unit to the same pixel length in x and y.

    Geometry-bearing figures (pitches, goal frames) are only honest if a yard is
    the same length in both directions. This reads the live data transform, which
    is authoritative - measuring pixels in the exported image is not, because axes
    spines and line widths pollute the result.

    Call it immediately before saving, after any layout pass.
    """
    fig.canvas.draw()
    t = ax.transData
    origin = t.transform((0.0, 0.0))
    unit_x = t.transform((1.0, 0.0))
    unit_y = t.transform((0.0, 1.0))
    sx = abs(unit_x[0] - origin[0])
    sy = abs(unit_y[1] - origin[1])
    if sx <= 0 or sy <= 0:
        raise ValueError(f"{label}: degenerate data transform")
    if abs(sx - sy) / sy > tol:
        raise ValueError(
            f"{label}: aspect distorted - 1 unit is {sx:.3f}px in x but {sy:.3f}px in y "
            f"({(sx / sy - 1) * 100:+.1f}%). Ensure set_aspect('equal') is applied and "
            "that no layout pass overrides it."
        )
    return sx


def finalize_figure(fig, out_path, formats=None, dpi=300, close=True, pad=0.06,
                    bbox="tight", **savefig_kw):
    """Save ``fig`` to one or more formats. Returns the list of written paths.

    ``bbox="tight"`` crops to the drawn artists, which is what you want for most
    figures. **It is wrong for any figure whose axes use ``set_aspect('equal')``**
    - a pitch, a goal frame, a radar - because matplotlib resolves the aspect
    against the axes box, then tight-bbox changes that box and silently rescales
    the geometry (a 7.32 m goal comes out looking 5 m wide). Pass
    ``bbox=None`` for those and control margins with ``fig.subplots_adjust``.
    """
    out_path = Path(out_path)
    if formats is None:
        formats = [out_path.suffix.lstrip(".") or "pdf"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    saved = []
    for fmt in formats:
        fmt = fmt.lower().lstrip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format {fmt!r}; choose from {sorted(SUPPORTED_FORMATS)}")
        dest = out_path.with_suffix(f".{fmt}")
        if bbox == "tight":
            fig.savefig(dest, dpi=dpi, bbox_inches="tight", pad_inches=pad,
                        format=fmt, **savefig_kw)
        else:
            fig.savefig(dest, dpi=dpi, format=fmt, **savefig_kw)
        saved.append(dest)
    if close:
        plt.close(fig)
    return saved


def figure_with_pitch(figsize=(13, 9), style: PitchStyle | None = None,
                      tight: bool = True, **pitch_kw):
    """Convenience: a figure whose axes is already a drawn pitch.

    Pass ``tight=False`` when you plan to add inset axes: ``tight_layout`` does
    not account for insets and will shift the pitch underneath them.
    """
    style = style or PRINT_STYLE
    fig, ax = plt.subplots(figsize=figsize)
    draw_pitch(ax, style=style, **pitch_kw)
    if tight:
        fig.tight_layout(pad=1.2)
    return fig, ax


def add_title(ax, title, subtitle=None, style: PitchStyle | None = None, x=0.0, y=1.06):
    """Title + optional subtitle above an axes, left-aligned."""
    style = style or PRINT_STYLE
    col = "#F2F2F2" if style.dark else PALETTE["ink"]
    sub = "#B9C0CC" if style.dark else PALETTE["grey_mid"]
    ax.text(x, y, title, transform=ax.transAxes, fontsize=style.title_size,
            weight="bold", va="bottom", ha="left", color=col)
    if subtitle:
        ax.text(x, y - 0.035, subtitle, transform=ax.transAxes,
                fontsize=style.label_size + 1, va="bottom", ha="left", color=sub)
