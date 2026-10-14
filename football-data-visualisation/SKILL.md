---
name: football-data-visualisation
description: >-
  Covers publication- and broadcast-quality football analytics figures in
  matplotlib: shot maps, xG and goal-mouth plots, pass networks, progressive
  passing flow fields, pressure maps, zone occupancy, percentile radars, xG
  races, momentum charts, and 360 freeze-frame pitch control. Use when building
  football/soccer data visualisations on StatsBomb-style event data with this
  repository's house style, pitch geometry, and print/vector export conventions.
  Do not use for interactive dashboards or web viz (Plotly, D3, Flourish),
  non-football sports, or Illustrator/Figma-first infographic workflows.
---

# Football data visualisation

A visual guide to improving football. Every figure here is meant to be read by a
coach, not only a modeller: a shot map that explains *why* a side underperformed
its xG, a pass network that shows where the ball gets stuck, a pressure map that
shows which zone a press breaks down in.

This skill is a conversion of [figures4papers](https://github.com/ChenLiu-1996/figures4papers)
from scientific paper figures to football analytics figures. The house style,
helper API, and export policy carry over; the colour semantics and the subject
matter do not.

Open `references/` only as needed; do not preload every file. Start from the table
below, then follow links inside the document you opened.

## When to load this skill

- Matplotlib figures on **football event or tracking data** that must match **this
  repo's look** (light pitch, thin grey linework, blue/red team semantics).
- Requests involving **shot maps, pass networks, pressure maps, zone grids,
  radars, xG races, momentum, pitch control, or Voronoi**.
- **StatsBomb open-data** work: the data layer, 360 freeze-frames, and the
  metric definitions are all implemented here.
- **PDF/PNG vector export at print resolution** for football figures.

## When not to load

- **Interactive or web-first** football viz (Flourish, D3, Plotly, Observable).
- **Non-football** sports — the pitch geometry and metric vocabulary do not apply.
- Primary workflow is **3D, VR, or broadcast video overlay**.
- **Illustrator / Figma-first** infographic layout rather than data plots.

## Related files

| File | Open when |
|------|-----------|
| [references/tutorials.md](references/tutorials.md) | End-to-end walkthroughs (shot map, pass network, pitch control) |
| [references/api.md](references/api.md) | Helper signatures, `PALETTE`, `ROLE`, `PitchStyle`, validation rules |
| [references/common-patterns.md](references/common-patterns.md) | Layout patterns, flow fields, honest encoding of sparse data |
| [references/design-theory.md](references/design-theory.md) | Why the football style looks the way it does; export policy |
| [references/demos.md](references/demos.md) | Canonical `fig_*` projects, with what each one proves |

## The seven figure families

| Family | Figures | Answers |
|--------|---------|---------|
| **Shooting** | `shot_map`, `goal_mouth`, `quality_grid` | Why does the scoreline disagree with the xG? |
| **Passing** | `pass_network`, `progressive`, `sonar` | Where does the ball get stuck, and who moves it? |
| **Defending** | `pressure_map`, `profile`, `high_turnover` | Where does the press work, and what does it cost? |
| **Territory** | `zone_grid`, `field_tilt`, `carries` | Who controls which parts of the pitch? |
| **Comparison** | `radar`, `percentiles`, `similarity` | How does this player compare to peers? |
| **Trends** | `xg_race`, `momentum`, `rolling` | How did the match or season swing? |
| **Tracking** | `pitch_control` (Voronoi + Spearman) | Who actually owns the space right now? |

## Core loop

```python
import sys; sys.path.insert(0, "football-data-visualisation/scripts")
import matplotlib.pyplot as plt
import football_style as fs
from sb_data import Dataset

style = fs.apply_pitch_style()          # sets rcParams
ds = Dataset.load()                     # reads data/cache
match = ds.match(ds.cached_match_ids()[0])

fig, ax = plt.subplots(figsize=(13.5, 9.2))
fs.draw_pitch(ax, style=style, show_third_lines=True)
fs.add_title(ax, "Title", "Subtitle")
fs.assert_pitch_aspect(fig, ax, label="shot map")   # geometry guard
fs.finalize_figure(fig, "figures/my_figure", formats=["png", "pdf"], dpi=300)
```

## Five rules that are easy to get wrong

1. **Orient every event to one attacking direction.** StatsBomb stores raw
   coordinates, so a team attacking right-to-left has shots at x≈10. `Dataset`
   normalises this for you; never plot raw `location` directly.

2. **Exclude penalty-shootout events.** They carry a flat 0.78 xG and inflate
   goal counts. `Dataset.shots()` drops them by default — this is the difference
   between "6 goals, 5.03 xG" and a nonsense "12 goals, 11.30 xG".

3. **`draw_pitch` owns the aspect ratio.** Call it *before* any `imshow`, and
   never pass `aspect="auto"` to an overlay — it silently stretches the pitch.
   `assert_pitch_aspect()` catches this.

4. **Do not draw one arrow per event.** A few hundred pass or carry arrows is an
   unreadable hairball. Aggregate into a grid flow field (see
   `fig_passing/plot_pass_network.py`).

5. **360 freeze-frames are camera-truncated, not full tracking.** A frame holds
   ~20 of 22 players, densest near the ball. Return and draw a coverage or
   low-confidence mask; never present extrapolated pitch control as measurement.

## Data

StatsBomb open data, no API key:

```bash
.venv/bin/python football-data-visualisation/scripts/fetch_statsbomb.py --core
```

Caches under `data/cache/`. Attribution is required in any published figure:
**Data provided by StatsBomb.**
