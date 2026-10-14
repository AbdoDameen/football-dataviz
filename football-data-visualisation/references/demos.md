# Demos

The `fig_*` projects, each with a real runnable script and exported output. These
are the canonical references: when in doubt about how to build a figure, read the
script rather than the prose.

All demos use cached StatsBomb data and default to
**FIFA World Cup 2022 Final, Argentina 3-3 France** (`match_id = 3869685`).

---

## `fig_shooting/plot_shot_map.py`

Three figures on finishing quality. **The entry point if you are new** — the shot
map is the simplest complete figure in the repo.

| Output | Shows |
|--------|-------|
| `shooting_shot_map` | every shot as a bubble sized by xG, goals ringed, biggest chances labelled |
| `shooting_goal_mouth` | where shots crossed the goal line, on a true-scale 7.32 × 2.44 m frame |
| `shooting_quality_grid` | total xG and shot count per zone in the attacking third |

Demonstrates: orientation, shootout filtering, a labelled bubble-size key in an
inset, label de-collision, `assert_pitch_aspect`, and filtering goal-mouth
endpoints that fall outside the frame.

---

## `fig_passing/plot_pass_network.py`

Three passing figures.

| Output | Shows |
|--------|-------|
| `passing_pass_network` | node = average pass origin, node size = passes made, edge width = completed passes |
| `passing_progressive` | zone-to-zone flow field of progressive passes |
| `passing_sonar` | one player's 94 passes by direction and outcome, as a polar chart |

Demonstrates: the two-threshold rule for networks, volume-in-width encoding, a
line-width key, and the flow-field aggregation that replaces an arrow hairball.
Also states the mean-vector caveat.

---

## `fig_defending/plot_pressure_map.py`

| Output | Shows |
|--------|-------|
| `defending_pressure_map` | pressure density per team, with nested contour bands |
| `defending_profile` | defensive actions by third, plus the PPDA trade-off |
| `defending_high_turnover` | where possession is won back in the attacking half |

Demonstrates: a true Gaussian KDE on a fine grid (vs. the blocky artefacts of
smoothing a coarse histogram), nested contours scaled to each team's own peak,
and marker-shape-as-second-channel.

---

## `fig_territory/plot_zone_grid.py`

| Output | Shows |
|--------|-------|
| `territory_zone_grid` | touches per zone across the attacking half, both teams on one colour scale |
| `territory_field_tilt` | territory share as a single stacked bar plus the underlying numbers |
| `territory_carries` | progressive carries as a flow field |

Demonstrates: shared `vmin`/`vmax` across comparison panels, a white zone lattice
over a pitch, and a text table as a figure element.

---

## `fig_comparison/plot_radar.py`

| Output | Shows |
|--------|-------|
| `comparison_radar` | Messi vs Mbappé, percentile-ranked against 326 tournament peers |
| `comparison_percentiles` | one player's full percentile profile, diverging about the median |
| `comparison_similarity` | most statistically similar players, by z-scored metric distance |

Demonstrates: pooling a whole season into a peer group, percentile ranking with a
stated population, and the closest port of the source repo's method-comparison
radar (`figure_VIGIL`).

---

## `fig_trends/plot_xg_race.py`

| Output | Shows |
|--------|-------|
| `trends_xg_race` | cumulative xG with goals marked as they arrive |
| `trends_momentum` | territorial momentum per 5-minute bin, diverging about zero |
| `trends_rolling` | rolling xG for and against across a team's whole tournament run |

Demonstrates: step plots for accumulating quantities, a centred rolling window,
goal-label de-collision, and the divergence between scoreline and xG.

---

## `fig_tracking/plot_pitch_control.py`

| Output | Shows |
|--------|-------|
| `tracking_pitch_control` | Voronoi vs Spearman pitch control on one 360 freeze-frame |

The most advanced figure. Demonstrates: 360 freeze-frame handling, two competing
space-dominance models shown side by side, hatched low-confidence regions, and the
calibration check that stops a flat surface from shipping as a result.

**Read the caveats in the script before reusing the model.**

---

## Infrastructure

| Script | Purpose |
|--------|---------|
| `scripts/fetch_statsbomb.py` | download the open-data cache (`--list`, `--core`, `--season`, `--matches`) |
| `scripts/sb_data.py` | data layer: `Dataset`, `Match`, `Shot`, `Pass`, `Carry`, `DefAction`, `Frame`, `xthreat` |
| `scripts/football_style.py` | house style, pitch drawing, `make_*` helpers, export |
| `scripts/pitch_control.py` | Voronoi, Spearman pitch control, pressure, space geometry |
| `scripts/metrics.py` | per-player and per-team metrics, momentum, rolling form |
| `scripts/selftest.py` | end-to-end engine check; exits non-zero on failure |

Run everything:

```bash
for f in fig_*/plot_*.py; do .venv/bin/python "$f"; done
```

---

## Output

All figures land in `figures/` as both `*.png` (300 dpi, for reading and review)
and `*.pdf` (vector, for print and for editing text in Illustrator/Inkscape).

Attribution required in any publication: **Data provided by StatsBomb.**
