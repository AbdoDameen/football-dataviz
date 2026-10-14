# Football Figure Design Theory

Why these football figures look the way they do. Inferred from the source repo's
style system and adapted, with the reasoning for each change.

## 1) What carried over from figures4papers

The publication house style is worth keeping for football, because both domains
share the same constraint: a figure must survive greyscale printing, a projector,
and a caption that does the explaining.

Kept unchanged:

- **Minimalist furniture.** Spines top/right off, frameless legends, no chart
  junk. A football figure is already visually busy; the frame must not compete.
- **Explicit y-limits.** Never let matplotlib auto-scale a comparison.
- **Direct labelling over legend-hunting** where a label can sit next to the data.
- **Vector export plus a raster preview** at 300 dpi (600 for dense panels).
- **`tight_layout` consistency** across panels of a figure — one row, one set of
  font sizes.
- **The anchor blue `#0F4D92`.** It carries the visual lineage, and it reads as
  "the subject of this figure".

## 2) What had to change, and why

### Colour encodes role, not method

The source repo's palette means *proposed method vs baseline*. Football has no
"proposed method"; it has **who is attacking, who is defending, and whether the
action worked**. So `ROLE` replaces method semantics:

| Role | Colour | Meaning |
|------|--------|---------|
| attack | `#0F4D92` | team in possession, or the figure's subject |
| defend | `#B64342` | the opposition, or a negative outcome |
| success | `#2E7D4F` | completed, won, positive |
| failure | `#767676` | incomplete, lost — deliberately desaturated |
| highlight | `#FFD700` | one "look here" accent per figure |

`failure` is grey rather than red on purpose. In football, a failed action is
usually context, not judgement; painting every incomplete pass red turns a pass
network into an alarm. Red is reserved for the *other team*.

### The pitch replaces the axes

A football figure is usually drawn on a pitch, so the pitch **is** the coordinate
system. That raises two obligations the source repo never had:

1. **Geometry must be honest.** A yard is the same length in x and y. See
   `assert_pitch_aspect` and the `imshow(aspect="auto")` trap in
   [api.md](api.md).
2. **Linework recedes.** Pitch lines are `#C9CEC9` at 1.6 pt — present for
   orientation, never competing with data.

### Data is sparse, and the figure must say so

Event data is a few thousand points. Tracking data is 22 players per frame, and
the free 360 feed is *camera-truncated*. Three rules follow:

- **Smooth point densities before contouring.** Contouring raw event counts
  isolates each point into its own blob, which reads as noise. Use a true
  Gaussian KDE on a fine grid (see `fig_defending/plot_pressure_map.py`), not a
  blur applied to a coarse histogram — the latter contours as blocky,
  axis-aligned squares.
- **Aggregate arrows.** One arrow per pass is a hairball. One arrow per zone,
  sized by volume, answers the question.
- **Hatch what is not measured.** 360 frames hold ~20 of 22 players, densest near
  the ball. `low_confidence_mask` marks cells more than 40 yards from any visible
  player; those values come from the model's decay term, not from observation.
  Hatch them rather than presenting extrapolation as data.

## 3) Layout and composition

- **Crop to the story.** A shot map wastes half its canvas on a half-circle. Use
  `crop="attacking-half"` or `crop="final-third"`, and tighten `ylim` when events
  cluster in the central corridor.
- **Portrait for goals, landscape for comparisons.** Shot maps and goal-mouth
  panels are portrait. Radars, trend lines, and grouped bars are landscape.
- **A dedicated legend or a direct label — never both.** The source repo uses a
  dedicated legend sub-axes; football figures more often label in place.
- **The caption carries the definition.** Every metric here — progressive,
  packing, PPDA, xT — means something specific. State it under the figure. The
  demo scripts all do.

## 4) Encoding strategy by family

### Shot maps
Bubble **area** encodes xG, linear and labelled, so two bubbles can be compared
by eye. Include a size key. Goals get a ring, not just a darker fill, so they
survive greyscale. Colour non-goals at low alpha and draw goals on top.

### Goal-mouth plots
Draw the frame to true scale (7.32 × 2.44 m) and plot only shots whose recorded
endpoint actually falls inside it. StatsBomb's `end_location` z coordinate is not
always within the goal, so filter rather than clipping silently.

### Pass networks
Node area scales with involvement; **edge width encodes pass volume** and nothing
else, because width is the channel readers judge most reliably. Scale the node
label to fit the node, and fall back to an initial for long surnames.

### Flow fields (progressive passes and carries)
Grid the pitch, one arrow per cell showing mean direction and mean advance, sized
by volume. **State the averaging caveat:** a zone that advances to both flanks can
read as pointing sideways, because mean vectors cancel.

### Heatmaps and density
Sequential counts use `COUNT_CMAP`; threat surfaces use `THREAT_CMAP`. Always
show a colourbar with units. For two-team comparisons on one metric, **share one
colour scale** — two independent autoscaled panels make equal numbers look
different.

### Radars
A radar is only meaningful against a baseline. Percentile-rank within a stated
peer group (same competition and season, minimum minutes) and label the rings as
percentiles. An absolute-value radar across eight differently-scaled metrics is
unreadable.

### Percentile bars
Diverging colour about the median, a labelled median line, and the raw value in
brackets beside each bar. Percentiles hide magnitude; the raw number restores it.

### Trend and momentum charts
Step plots for cumulative xG, because xG only accumulates. Diverging bars for net
momentum, with explicit direction labels — a diverging chart is easy to misread.

## 5) Export policy

| Target | Figure | Then |
|--------|--------|------|
| Paper / report | `bbox="tight"`, 300 dpi | PNG + PDF |
| Slide / projector | larger fonts, fewer panels | PNG at 200 dpi |
| Broadcast / dark UI | `BROADCAST_STYLE` | PNG |
| Dense multi-panel | 600 dpi | PNG + PDF |

Set `svg.fonttype = "none"` (already in the rcParams preset) so text stays
editable in vector output.

## 6) Recipe for a new football figure

1. Decide the **one question** the figure answers. Name it in the title.
2. Choose the family from [SKILL.md](../SKILL.md) and start from that demo.
3. Pick the role colours. One `highlight` at most.
4. Draw the pitch first, then data, then annotations.
5. Call `assert_pitch_aspect()` if the figure shows geometry.
6. Write the caption: metric definition, filter, sample size, attribution.
7. Export PNG + PDF at 300 dpi and read the PNG back before calling it done.

## Related files

- [api.md](api.md) — constants and signatures
- [common-patterns.md](common-patterns.md) — operational patterns
- [tutorials.md](tutorials.md) — worked walkthroughs
- [demos.md](demos.md) — the `fig_*` projects
