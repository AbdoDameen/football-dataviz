# Common Patterns

Operational recipes for football figures. Each pattern names the demo that
implements it.

---

## 1) The standard pitch figure skeleton

Every geometry-bearing figure follows this order. Deviating causes the bugs listed
in [design-theory.md](design-theory.md) §2.

```python
import sys; sys.path.insert(0, "football-data-visualisation/scripts")
import matplotlib.pyplot as plt
import football_style as fs
from sb_data import Dataset

style = fs.apply_pitch_style()
ds = Dataset.load()
match = ds.match(3869685)

fig, ax = plt.subplots(figsize=(13.5, 9.2))
fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.05)

fs.draw_pitch(ax, style=style, show_third_lines=True)   # 1. pitch
# 2. data overlays here (imshow, scatter, arrows) — never with aspect="auto"
# 3. annotations and labels
fs.add_title(ax, "Title", "Subtitle", style=style)

fs.assert_pitch_aspect(fig, ax, label="my figure")      # 4. geometry guard
fs.finalize_figure(fig, "figures/my_figure", formats=["png", "pdf"], dpi=300)
```

**Why `subplots_adjust` rather than `tight_layout`:** `tight_layout` ignores inset
axes and will shift the pitch underneath a size key. When you need an inset
(bubble key, edge-width key), size the figure to the data's aspect ratio and set
margins by hand.

---

## 2) Surface over a pitch without breaking the aspect

`imshow` defaults to `aspect="auto"` and will stretch the pitch. Either omit the
argument (matplotlib then leaves an already-equal aspect alone, and `draw_pitch`
re-asserts it), or — safer and pixel-exact — compute the extent so cells are
square:

```python
nx, ny = 6, 4
extent = [0, fs.PITCH_LENGTH, 0, fs.PITCH_WIDTH]
im = ax.imshow(
    grid,
    extent=extent,
    origin="lower",
    cmap=fs.COUNT_CMAP,
    interpolation="nearest",
    alpha=0.9,
    zorder=2,
)
```

Used by `fig_territory/plot_zone_grid.py`.

---

## 3) Gaussian KDE for event density

Event locations are scattered points. To get a readable surface:

```python
def density(xs, ys, sigma=6.0, nx=240, ny=160):
    gx = np.linspace(0, fs.PITCH_LENGTH, nx)
    gy = np.linspace(0, fs.PITCH_WIDTH, ny)
    gxx, gyy = np.meshgrid(gx, gy)
    grid = np.zeros((ny, nx))
    for x, y in zip(xs, ys):
        d2 = (gxx - x) ** 2 + (gyy - y) ** 2
        grid += np.exp(-d2 / (2 * sigma ** 2)) * (d2 < (4 * sigma) ** 2)
    return grid
```

Evaluate on a **fine** grid. Blurring a coarse count histogram with a separable
kernel produces square artefacts that contour as blocky axis-aligned blobs.

Then contour in **nested bands** scaled to the team's own peak, so the lines
describe shape rather than absolute volume:

```python
levels = np.array([0.28, 0.48, 0.70, 0.88]) * grid.max()
ax.contour(gx, gy, grid, levels=levels, colors=[fs.PALETTE["grey_dark"]],
           linewidths=[0.9, 1.1, 1.4, 1.8], zorder=4, alpha=0.75)
```

A single quantile threshold on sparse points isolates each event into its own
blob. Used by `fig_defending/plot_pressure_map.py`.

---

## 4) Zone-to-zone flow field

For progressive passes or carries, one arrow per grid cell instead of one per
event.

```python
buckets = defaultdict(list)
for ev in events:
    i = min(nx - 1, max(0, int(ev.x / cell_w)))
    j = min(ny - 1, max(0, int(ev.y / cell_h)))
    buckets[(i, j)].append(ev)

vmax = max(len(v) for v in buckets.values())
for (i, j), group in buckets.items():
    dx = float(np.mean([e.end_x - e.x for e in group]))
    dy = float(np.mean([e.end_y - e.y for e in group]))
    frac = len(group) / vmax
    cx, cy = (i + 0.5) * cell_w, (j + 0.5) * cell_h
    ax.annotate("", xy=(cx + dx, cy + dy), xytext=(cx, cy),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                linewidth=0.8 + 6.0 * frac,
                                alpha=0.25 + 0.65 * frac,
                                shrinkA=0, shrinkB=0,
                                mutation_scale=12 + 15 * frac), zorder=4)
    if len(group) >= 3:
        ax.text(cx, cy, str(len(group)), ha="center", va="center", fontsize=10.5,
                weight="bold", color="white", zorder=8,
                bbox=dict(boxstyle="circle,pad=0.18", fc=color, ec="white",
                          linewidth=1.4, alpha=0.95))
```

Always state the caveat: arrows are **mean vectors**, so a cell feeding both
flanks can read as pointing sideways. Used by `fig_passing/plot_pass_network.py`
and `fig_territory/plot_zone_grid.py`.

---

## 5) Bubble size key

Size is the least reliable visual channel, so label it.

```python
key = fig.add_axes([0.055, 0.075, 0.30, 0.19])   # own axes, not annotation
key.set_xlim(0, 1); key.set_ylim(0, 1); key.axis("off")
key.set_title("bubble area = xG", fontsize=10.5, weight="bold", pad=4)
for y, val in zip((0.80, 0.46, 0.14), (0.05, 0.25, 0.60)):
    key.scatter([0.22], [y], s=bubble_sizes(np.array([val]))[0],
                facecolor="none", edgecolor=fs.PALETTE["grey_dark"], linewidth=1.4)
    key.text(0.46, y, f"{val:.2f}", fontsize=10, va="center",
             color=fs.PALETTE["grey_dark"])
```

A dedicated inset keeps the key off the data. Used by
`fig_shooting/plot_shot_map.py`.

---

## 6) Flow-field / edge-width key

Same idea for line thickness, which readers otherwise guess at.

```python
key = fig.add_axes([0.035, 0.055, 0.20, 0.13])
key.axis("off")
key.set_title("line width = passes", fontsize=10, weight="bold", pad=4)
for y, v in zip((0.72, 0.42, 0.12), (3, 10, 20)):
    frac = min(v / vmax, 1.0)
    key.plot([0.06, 0.44], [y, y], color=fs.TEAM_COLORS["home"],
             linewidth=0.7 + 7.0 * frac, alpha=0.14 + 0.58 * frac,
             solid_capstyle="round")
    key.text(0.52, y, f"{v}", fontsize=9.5, va="center")
```

Used by `fig_passing/plot_pass_network.py`.

---

## 7) Shared colour scale across comparison panels

Two panels of the same metric **must** share `vmin`/`vmax`, or equal values look
different.

```python
vmax = max(g.max() for g in grids.values())
for ax, team in zip(axes, teams):
    ax.imshow(grids[team], extent=extent, vmin=0, vmax=vmax, ...)
fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015)
```

Used by `fig_territory/plot_zone_grid.py`.

---

## 8) Percentile radar with a stated peer group

```python
pool = _season_players(ds)                # 180+ minutes, same comp + season
series = [[_percentile_ranks(pool, field, per90)[name] for _, field, per90 in AXES]
          for name in picks]
fs.make_radar(ax, labels, series, picks, rmin=0, rmax=100, fill_alpha=0.16)
ax.set_yticks([20, 40, 60, 80, 100])
ax.set_yticklabels(["20th", "40th", "60th", "80th", "100th"])
```

Put the peer group size in the figure. A percentile without a stated population
is meaningless. Used by `fig_comparison/plot_radar.py`.

---

## 9) Label de-collision

Event figures routinely put two labels on the same spot — two penalties in one
match, two goals in the same minute.

```python
placed = []
for ev in to_label:
    ox, oy = 10, 14
    while any(abs(ev.x + ox / 6 - px) < 9 and abs(ev.y + oy / 6 - py) < 6
              for px, py in placed):
        oy += 17
    placed.append((ev.x + ox / 6, ev.y + oy / 6))
    ax.annotate(text, (ev.x, ev.y), xytext=(ox, oy), textcoords="offset points",
                arrowprops=dict(arrowstyle="-", color=fs.PALETTE["grey_mid"],
                                linewidth=0.9, shrinkA=0, shrinkB=4),
                bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.85))
```

Used by `fig_shooting/plot_shot_map.py` and `fig_trends/plot_xg_race.py`.

---

## 10) Hatching unmeasured regions

Never present extrapolation as data. Two patterns:

```python
# binary mask (pitch control): contour the mask itself
ax.contourf(gx, gy, far.astype(float), levels=[0.5, 1.5],
            colors="none", hatches=["////"], zorder=3)
ax.contour(gx, gy, far.astype(float), levels=[0.5],
           colors=[fs.PALETTE["grey_mid"]], linewidths=1.0,
           linestyles="dashed", zorder=4)     # linewidths must be a scalar
```

Notes learned the hard way:

- `contour(linewidths=...)` takes a **scalar or list of scalars**, not a dash
  tuple.
- `linestyles` accepts a string like `"dashed"`; passing `(0, (5, 4))` raises
  `ValueError: Do not know how to convert [0] to dashes`.
- Hatch **region boundaries**, not every cell — a per-cell mask of sparse events
  hatches almost the whole pitch.

Used by `fig_tracking/plot_pitch_control.py`.

---

## 11) Penalty shootouts

```python
from sb_data import is_shootout
# Dataset.shots() already filters these out.
# If you read raw events yourself, filter explicitly:
events = [e for e in match.raw_events if not is_shootout(e)]
```

Shootout attempts carry `period >= 5` and a flat 0.78 xG. Including them turns a
3-3 final into "12 goals, 11.30 xG".

---

## 12) Categorical vs continuous colour

- **Continuous** (pressure density, xG, threat): sequential colormap + colourbar
  with units.
- **Categorical** (team, action type, outcome): `ROLE` / `TEAM_COLORS`, and add a
  second channel — marker shape or edge style — so the figure survives greyscale.

`fig_defending/plot_pressure_map.py` uses circles for the home team and triangles
for the away team for exactly this reason.
