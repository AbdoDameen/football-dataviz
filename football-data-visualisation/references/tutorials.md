# Tutorials

Three end-to-end walkthroughs, from data to exported figure. Each one is the real
code path used by a demo script, so you can run the script and follow along.

Prerequisite: data is cached.

```bash
.venv/bin/python football-data-visualisation/scripts/fetch_statsbomb.py --core
```

Every example uses **FIFA World Cup 2022 Final, Argentina 3-3 France**
(`match_id = 3869685`) — cached by `--core`, and a good test case because it has
six goals, a penalty shootout, and full 360 coverage.

---

## Tutorial 1 — Shot map (the simplest complete figure)

**Question:** Argentina and France both scored three. Did they create chances the
same way?

### Step 1: load and inspect

```python
import sys; sys.path.insert(0, "football-data-visualisation/scripts")
from sb_data import Dataset

ds = Dataset.load()
match = ds.match(3869685)
print(match.scoreline)                       # Argentina 3-3 France
shots = ds.shots(match)
print(len(shots), sum(s.xg for s in shots))  # 30 5.029...
```

Note what already went right: `shots()` dropped the penalty-shootout attempts. Raw
events would have given 12 goals and 11.30 xG.

### Step 2: orient the coordinates

`Shot.x`/`Shot.y` are already normalised so the shooting team attacks
left-to-right. Verify rather than assume:

```python
print(min(s.x for s in shots))   # > 40 -> orientation flip worked
```

Never read `ev["location"]` directly for plotting.

### Step 3: draw the pitch and frame the view

```python
import matplotlib.pyplot as plt
import football_style as fs

style = fs.apply_pitch_style()
fig, ax = plt.subplots(figsize=(7.6, 11.5))
fig.subplots_adjust(left=0.02, right=0.985, top=0.92, bottom=0.05)
fs.draw_pitch(ax, style=style)

# Frame the attacking two-thirds. A full pitch wastes half the canvas on a
# half-circle that carries no information for a shot map.
VIEW = (76.0, 123.0, -1.0, 81.0)
ax.set_xlim(VIEW[0], VIEW[1])
ax.set_ylim(VIEW[2], VIEW[3])
```

Set `xlim`/`ylim` **after** `draw_pitch`. The view is portrait (47 × 82 yd) and
the figure is portrait, so the aspect stays exact.

### Step 4: encode xG as bubble area

```python
import numpy as np
BUBBLE_MIN, BUBBLE_MAX = 40.0, 2200.0
sizes = BUBBLE_MIN + (BUBBLE_MAX - BUBBLE_MIN) * np.clip(
    [s.xg for s in shots], 0, 1) ** 0.85
```

Area, not radius — radius exaggerates. The `** 0.85` compresses the top end so a
0.78 penalty does not swamp everything else.

### Step 5: one scale per panel, shared between teams

Because both teams are plotted on the same axes, they share the bubble scale
automatically. That is the point: Argentina's 0.49 bubble is visibly bigger than
France's 0.28.

Draw non-goals first, then goals, so goals are never occluded:

```python
order = np.argsort(goals)          # False(0) before True(1)
ax.scatter(xs[order], ys[order], s=sizes[order], alpha=0.42, ...)
ax.scatter(xs[goals], ys[goals], s=sizes[goals],
           facecolor="none", edgecolor=color, linewidth=2.8)   # ring, not fill
```

### Step 6: the geometry guard, then export

```python
fs.assert_pitch_aspect(fig, ax, label="shot map")
fs.finalize_figure(fig, "figures/shooting_shot_map", formats=["png", "pdf"], dpi=300)
```

**Always read the PNG back** before declaring the figure done. That is how the
label collision and the out-of-frame goal-mouth points in this project were
caught.

Full script: `fig_shooting/plot_shot_map.py`.

---

## Tutorial 2 — Pass network with a readable structure

**Question:** Where does a team's passing structure actually run?

### Step 1: nodes are average pass origins

```python
from collections import Counter, defaultdict
import numpy as np

passes = ds.passes(match, "Argentina")
origins, edges = defaultdict(list), Counter()
for p in passes:
    origins[p.player].append([p.x, p.y])
    if p.completed and p.recipient:
        edges[(p.player, p.recipient)] += 1

positions = {k: np.mean(np.array(v), axis=0) for k, v in origins.items()}
counts = {k: len(v) for k, v in origins.items()}
```

### Step 2: threshold, or the figure becomes a hairball

```python
keep = {k for k, c in counts.items() if c >= 4}
edges = {k: v for k, v in edges.items()
         if k[0] in keep and k[1] in keep and v >= 3}
```

Two thresholds: a player must have made 4+ passes to appear, and an edge must have
3+ completed passes to be drawn. Without them a full match renders as an
unreadable mass of overlapping lines.

### Step 3: encode volume in line width

```python
vmax = max(edges.values())
for (a, b), v in edges.items():
    frac = v / vmax
    ax.plot([positions[a][0], positions[b][0]],
            [positions[a][1], positions[b][1]],
            color=fs.TEAM_COLORS["home"],
            linewidth=0.7 + 7.0 * frac,
            alpha=0.14 + 0.58 * frac,
            solid_capstyle="round", zorder=3)
```

Width is the channel readers judge most reliably, so it carries the primary
signal. Alpha reinforces it.

### Step 4: scale the node label to the node

An 11 pt surname overflows a small node. Fit it:

```python
size = 340 + 30 * count
radius_pt = np.sqrt(size) / 2.0
surname = name.split()[-1]
label = surname if len(surname) <= 8 else surname[:7] + "."
fontsize = float(np.clip(radius_pt * 0.62, 6.5, 11.0))
```

### Step 5: label the width channel

```python
key = fig.add_axes([0.035, 0.055, 0.20, 0.13])
key.axis("off")
key.set_title("line width = passes", fontsize=10, weight="bold", pad=4)
# ... draw three reference widths
```

See [common-patterns.md](common-patterns.md) §6.

Full script: `fig_passing/plot_pass_network.py`.

---

## Tutorial 3 — Pitch control from 360 freeze-frames

**Question:** At this moment, who owns the space around the ball?

This is the most advanced figure and the easiest to get wrong. Two traps.

### Step 1: get a usable frame — and know its limits

```python
frames = ds.frames(match)
usable = [f for f in frames if len(f.teammates) + len(f.opponents) >= 14]
frame = max(usable, key=lambda f: len(f.opponents) + len(f.teammates))
```

StatsBomb 360 frames contain only players inside the broadcast camera's visible
area: about 20 of 22, densest near the ball. **This is not full-pitch tracking.**
Crop to the attacking half where coverage is good, and never claim more.

### Step 2: pick the model

```python
from pitch_control import spearman_control, voronoi_control

# Nearest-player dominance: exact, blocky, easy to read.
voro, known = voronoi_control(frame.teammates, frame.opponents,
                              resolution=180, bounds=(60, 120, 0, 80))

# Time-to-intercept probability surface: smooth, accounts for who can *get* there.
control, coverage = spearman_control(frame.teammates, frame.opponents,
                                     ball_xy=(frame.x, frame.y),
                                     resolution=150, bounds=(60, 120, 0, 80))
```

Drawing both side by side is the honest presentation: they disagree, and the
disagreement is informative.

### Step 3: sanity-check the surface before trusting it

This is the step that matters. A pitch-control model with the wrong logistic form
renders beautifully and is noise:

```python
print(control[coverage].std())     # expect ~0.27, NOT ~0.01
```

If the standard deviation is near zero the surface is flat — the intercept
probability saturates and every player looks equally likely to reach every point.
See the calibration note in [api.md](api.md).

### Step 4: mark what is not measured

```python
from pitch_control import low_confidence_mask
far = low_confidence_mask(control.shape, (60, 120, 0, 80),
                          frame.teammates, frame.opponents, horizon=42.0)

ax.contourf(gx, gy, far.astype(float), levels=[0.5, 1.5],
            colors="none", hatches=["////"], zorder=3)
ax.contour(gx, gy, far.astype(float), levels=[0.5],
           colors=[fs.PALETTE["grey_mid"]], linewidths=1.0,
           linestyles="dashed", zorder=4)
```

Remember `linewidths` is a scalar or a list of scalars, and `linestyles` wants a
string. Passing a dash tuple raises.

### Step 5: state the sample size in the caption

```python
fig.text(0.5, -0.02,
         f"Hatched = more than 42 yd from the nearest visible player, where the "
         f"surface is extrapolated rather than measured.\n"
         f"{len(frame.teammates) + len(frame.opponents)} of 22 players visible. "
         "Data provided by StatsBomb.", ...)
```

Full script: `fig_tracking/plot_pitch_control.py`.

---

## Going further

- **Different match:** change `MATCH_ID` at the top of any demo. Use
  `ds.find_match("Spain vs Germany")` to look one up, then
  `fetch_statsbomb.py --matches <id>` to cache it.
- **Different season:** the comparison family uses
  `COMPETITION_ID, SEASON_ID = 43, 106`. Point it at another cached season —
  the peer group follows automatically.
- **Dark / broadcast figures:** `fs.apply_pitch_style(fs.BROADCAST_STYLE)`.
- **Self-test the whole engine:**

```bash
.venv/bin/python football-data-visualisation/scripts/selftest.py
```

It checks event extraction, orientation, metric sanity, pitch-control
calibration, and a full render-and-export round trip.
