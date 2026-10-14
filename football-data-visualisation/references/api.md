# API Reference

The conventions, constants, and function signatures for football figures.
Implement these, or adapt from the [`fig_*` demos](demos.md).

All of this lives in `football-data-visualisation/scripts/`. Put that directory
on `sys.path` (every demo does) or set `PYTHONPATH`.

---

## Constants

### Palette

```python
PALETTE = {
    # anchors, carried over from figures4papers so the visual DNA survives
    "blue_main": "#0F4D92",   "blue_secondary": "#3775BA",
    "blue_light": "#8FB8DE",  "blue_pale": "#DCE9F5",
    "green_1": "#DDF3DE",     "green_2": "#AADCA9",   "green_3": "#8BCF8B",
    "green_strong": "#2E7D4F",
    "red_1": "#F6CFCB",       "red_2": "#E9A6A1",     "red_strong": "#B64342",
    "amber": "#E8A33D",       "amber_light": "#F7DFB5",
    "highlight": "#FFD700",
    "teal": "#42949E",        "violet": "#9A4D8E",
    "neutral": "#CFCECE",     "grey_mid": "#767676",   "grey_dark": "#4D4D4D",
    "ink": "#272727",         "paper": "#FFFFFF",
    "pitch_dark": "#2B2F3A",  "pitch_light": "#FBFBF9",
}
```

### ROLE — the one semantic change from the source repo

figures4papers colours by **method** (blue = proposed, red = baseline). Football
figures colour by **role**: who is attacking, who is defending, and whether the
action succeeded.

```python
ROLE = {
    "attack": "#0F4D92",         # team in possession / the subject of the figure
    "attack_alt": "#3775BA",
    "attack_faint": "#8FB8DE",
    "defend": "#B64342",         # the opposition, or a negative outcome
    "defend_alt": "#E9A6A1",
    "defend_faint": "#F6CFCB",
    "success": "#2E7D4F",        # completed / won / positive
    "success_faint": "#AADCA9",
    "failure": "#767676",        # incomplete / lost — deliberately desaturated
    "neutral": "#CFCECE",
    "highlight": "#FFD700",      # a single "look here" accent per figure
    "context": "#E8A33D",        # secondary annotation (draws, referees)
    "context_faint": "#F7DFB5",
    "ink": "#272727",
}
```

**Use `highlight` at most once per figure.** It is the one channel that survives
every colour-vision deficiency and every greyscale print.

### Two-team palettes

Home always reads blue, away always reads red — consistent across a whole
document, so a reader learns it once.

```python
TEAM_COLORS = {
    "home": "#0F4D92", "home_alt": "#3775BA",
    "away": "#B64342", "away_alt": "#E9A6A1",
    "neutral": "#767676",
}
```

### Colormaps

| Name | Use |
|------|-----|
| `MOMENTUM_CMAP` | Diverging, red → white → blue. Pitch control, net momentum. |
| `THREAT_CMAP` | Sequential, pale → amber → red. xG and threat surfaces. |
| `COUNT_CMAP` | Sequential, pale → blue. Counts: touches, pressures, passes. |

### Pitch geometry (StatsBomb 120 × 80 yards)

```python
PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0
PENALTY_AREA_DEPTH = 18.0     # 6-yard box is SIX_YARD_DEPTH = 6.0
PENALTY_AREA_HALF_WIDTH = 20.0
CENTRE_CIRCLE_R = 10.0
GOAL_HALF_WIDTH = 4.0         # 8-yard goal
GOAL_DEPTH = 1.8              # drawn outside the goal line
GOAL_WIDTH_M, GOAL_HEIGHT_M = 7.32, 2.44   # metres, for goal-mouth plots
```

---

## Style

### PitchStyle

```python
@dataclass(frozen=True)
class PitchStyle:
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
```

Two presets ship:

- `PRINT_STYLE` — light pitch, thin grey lines, larger type. **Default.**
- `BROADCAST_STYLE` — dark pitch, brighter lines, smaller type, no spines.

### apply_pitch_style(style=None) → PitchStyle

Configures rcParams: font stack and sizes, spines top/right off, frameless
legend, `svg.fonttype="none"`. Call **once**, before creating figures. Returns the
style so you can pass it around.

Note: `font.weight` "semibold" is not present in Arial or Helvetica and falls
back with a warning — the helpers use `"bold"`.

---

## Pitch drawing

### draw_pitch(ax, style=None, orientation="horizontal", show_third_lines=False, show_half_spaces=False, grass_stripes=0, label=None, crop=None)

Draws the pitch and **sets the aspect ratio and limits**. Call it before adding
data.

| Parameter | Effect |
|-----------|--------|
| `orientation` | `"horizontal"` (attacking left-to-right) or `"vertical"` |
| `show_third_lines` | dashed lines at x = 40 and x = 80 |
| `show_half_spaces` | shades y ∈ [10,20] and [60,70] in each final third |
| `grass_stripes` | mowing stripes for a broadcast look |
| `label` | corner annotation, e.g. the data attribution |
| `crop` | `"attacking-half"`, `"final-third"`, `"box"`, or `None` |

`draw_pitch` re-asserts `set_aspect("equal")` after setting limits, because
several helpers — most importantly `imshow`, whose default aspect is `"auto"` —
would otherwise reset it and silently stretch the pitch.

### figure_with_pitch(figsize=(13, 9), style=None, tight=True, **pitch_kw)

Convenience returning `(fig, ax)` with the pitch already drawn. Pass
`tight=False` if you will add inset axes, because `tight_layout` does not account
for insets.

### assert_pitch_aspect(fig, ax, label="axes", tol=0.01)

Raises if one data unit is not the same pixel length in x and y. Call it
immediately before saving any geometry-bearing figure. It reads the live data
transform, which is authoritative — measuring pixels in the exported image is
not, because axes spines and line widths pollute the result.

### add_title(ax, title, subtitle=None, style=None, x=0.0, y=1.06)

Left-aligned title with optional subtitle above an axes.

---

## Plot helpers

Ports of the figures4papers `make_*` API.

### make_grouped_bar(ax, categories, series, labels, ylabel="Value", colors=None, annotate=False, value_fmt="{:.1f}", ylim=None, horizontal=False)

`series` is a list of arrays, one per group; `len(categories)` must equal each
array's length. Bars carry black edges for sharp separation. Returns the last
`BarContainer`.

### make_trend(ax, x, y_series, labels, colors=None, ylabel=None, xlabel=None, show_shadow=True, linewidth=2.6, marker=None, step=False)

Each series is a 1D array (a line) or a 2D array (a band drawn as min/max).

### make_heatmap(ax, matrix, x_labels=None, y_labels=None, cmap=None, cbar_label=None, annotate=False, vmin=None, vmax=None, cbar=True) → AxesImage

Heatmap on `ax`. **Uses `aspect="auto"`, so do not call it on a pitch axes** —
use `imshow` directly with an explicit `extent` instead.

### make_scatter(ax, x, y, label=None, color=None, size=50, alpha=0.7, edgecolor="none", zorder=4, **kw)

### make_radar(ax, categories, series, labels, colors=None, fill_alpha=0.18, rmin=0.0, rmax=None, ring_labels=True)

Polar chart. For player percentiles pass `rmin=0, rmax=100` and label the rings
as percentiles.

### annotate_point(ax, x, y, text, dx=1.2, dy=1.2, ...)

Small labelled callout.

### legend_panel(fig, handles, labels, loc="lower center", ncol=4, **kw)

Repo convention: a dedicated legend, so data panels stay clean.

---

## Export

### finalize_figure(fig, out_path, formats=None, dpi=300, close=True, pad=0.06, bbox="tight", **savefig_kw) → list[Path]

Writes one file per format, creating parent directories. Returns the paths.

Supported: `pdf, svg, eps, png, jpg, jpeg, tif, tiff`.

**`bbox="tight"` crops to the drawn artists and is correct for most figures.** It
interacts badly with `set_aspect("equal")` in some layouts, so geometry-bearing
figures that must be dimensionally exact should pass `bbox=None` and control
margins with `fig.subplots_adjust`. `fig_shooting/plot_shot_map.py`'s goal-mouth
panel does this.

---

## Data layer — `sb_data`

### Dataset

```python
ds = Dataset.load()                      # raises if data/cache is missing
ds.cached_match_ids(with_frames=True)    # -> [int]
ds.cached_match_ids(with_frames=False)   # faster; events only
ds.fixtures(competition_id, season_id)   # -> [dict]
ds.find_match("Argentina vs France")     # -> dict | None
ds.match(match_id)                       # -> Match (cached)
ds.season_players(competition_id, season_id)
```

### Match

```python
match.match_id, match.home, match.away
match.home_score, match.away_score, match.scoreline
match.competition, match.season, match.date
match.teams                              # -> (home, away)
match.raw_events, match.raw_frames
match.attacking_direction(team)          # +1 or -1 (cached; do not recompute)
```

### Extractor methods

Every extractor **orients** its output so the acting team attacks left-to-right.

```python
ds.shots(match, team=None, include_shootout=False) -> list[Shot]
ds.passes(match, team=None)                        -> list[Pass]
ds.carries(match, team=None)                       -> list[Carry]
ds.defensive_actions(match, team=None)             -> list[DefAction]
ds.frames(match, team=None)                        -> list[Frame]
```

### Shot

`match_id, team, player, x, y, xg, outcome, body_part, technique, minute,
end_x, end_y, end_z, first_time, under_pressure, play_pattern`

Derived: `is_goal`, `distance`, `angle` (goal opening angle, degrees).

### Pass

`match_id, team, player, recipient, x, y, end_x, end_y, minute, completed,
pass_type, height, length, is_progressive, is_line_breaking, xthreat,
under_pressure`

`is_progressive` = advances ≥ 10 yd up-pitch from the team's own 80 yards.
`is_line_breaking` = advances ≥ 20 yd. Methods `start()`, `end()`.

### DefAction

`match_id, team, player, kind, x, y, minute, success`

`kind` ∈ `pressure, duel, interception, block, clearance, recovery`.

### Carry

`match_id, team, player, x, y, end_x, end_y, minute, distance, is_progressive`
(`is_progressive` = advances ≥ 5 yd).

### Frame (360 freeze-frame)

`event_uuid, x, y, teammates, opponents, actor, keeper`

`teammates`/`opponents` are `(n, 2)` arrays **relative to the acting team**.
`all_players()` concatenates them. See the truncation caveat in
[design-theory.md](design-theory.md).

### is_shootout(ev) → bool

True for penalty-shootout events (`period >= 5`). They carry a flat 0.78 xG and
would inflate both goal counts and team xG. `shots()` excludes them by default.

### xthreat(x, y) → float, xthreat_grid() → np.ndarray, progressive_value(p) → float

A 12 × 8 stylised expected-threat surface over the pitch, rising toward the
opponent goal and peaking in the central corridor. Good enough to rank pass
value; **not** a fitted model. In the spirit of Karun Singh's xT.

---

## Analytics — `pitch_control`

### voronoi_control(teammates, opponents, resolution=120, bounds=(0,120,0,80)) → (control, known)

`control` is 1.0 where the nearest player is a teammate, 0.0 for an opponent, 0.5
where nobody is visible. `known` is False for those no-data cells — mask them
rather than painting a fake tie.

### voronoi_regions(teammates, opponents, resolution=240, bounds=...) → (labels, owner, gx, gy)

Hard Voronoi labels: `+1` teammate, `-1` opponent, `0` unknown.

### spearman_control(teammates, opponents, ball_xy, resolution=100, bounds=..., influence_radius=45.0, min_visible=12) → (control, coverage)

Pitch control after Spearman (2018): each player's time-to-intercept becomes a
logistic probability, normalised per cell. Returns the teammates' share in
[0, 1] and a per-frame coverage flag.

**Calibration matters.** The intercept logistic is
`1 / (1 + exp(k * (t - T)))` with `T = INTERCEPT_REFERENCE` (1.0 s) and
`k = INTERCEPT_SHARPNESS` (4.0). An exponent-inverse form saturates — it yields a
near-uniform surface with a standard deviation around 0.01, which looks like a
result and is noise. The shipped defaults produce a standard deviation near 0.27.
If you retune these, check the surface's spread, not just that it renders.

### low_confidence_mask(shape, bounds, teammates, opponents, horizon=40.0) → np.ndarray

Cells further than `horizon` yards from any visible player. These are
extrapolations produced by the decay term, not observations. **Hatch them.**

### pressure_at(points, targets, radius=8.0), free_space_ratio(...), convex_hull_area(...), team_shape(...)

Supporting geometry helpers.

---

## Analytics — `metrics`

### player_metrics(ds, match, team=None) → dict[str, PlayerMetrics]

Per player: `minutes, shots, goals, xg, npxg, passes, passes_completed,
progressive_passes, line_breaking_passes, key_passes, assists, xt, packing,
progressive_carries, carry_distance, pressures, interceptions, blocks,
clearances, recoveries, duels, duels_won, touches_final_third, touches_box,
pass_links`

Derived: `pass_completion, xg_per_shot, goals_minus_xg, per90`, and
`rate(value)` to convert a count to a per-90 rate.

### team_metrics(ds, match) → dict[str, TeamMetrics]

`goals, xg, shots, passes, passes_completed, progressive_passes,
final_third_entries, box_entries, xt, def_actions, pressures, high_turnovers,
opponent_passes`. Derived: `pass_completion`, `ppda`.

**PPDA** = opponent passes ÷ defensive actions. Lower means more aggressive
pressing. It is undefined when a team made no defensive actions — it returns
`nan` rather than 0.

### field_tilt(ds, match), zone_occupancy(ds, match, team, n_x=6, n_y=4), xg_race(ds, match), rolling_form(ds, match_ids, team, window=5), momentum(ds, match, bin_minutes=5)

### opponents_bypassed(p, opponent_positions)

Counts opponents inside the corridor between a pass's start and end. The
positions argument is indexed by minute, because StatsBomb has no per-event
opponent tracking outside 360 frames.

---

## Validation rules

- Sequences are converted to numpy arrays; 1D/2D and length checks are enforced.
- `make_grouped_bar`: `len(categories)` must equal each series' length.
- `make_trend`: each series must match `len(x)`.
- `make_radar`: each series must match `len(categories)`.
- `finalize_figure`: only the formats listed above are accepted.
- Unsupported matplotlib format strings raise `ValueError` rather than silently
  writing nothing.

## Conventions

- Save under a `figures/` directory with stable basenames; `finalize_figure`
  creates parents.
- In headless or batch runs, set the Agg backend before importing pyplot
  (every demo's `sys.path` preamble assumes this).
- **When the comparison, panel count, colour roles, crop, or data window are
  underspecified in a way that would change the figure, ask before finalising.**
- Attribute StatsBomb in every published figure.
