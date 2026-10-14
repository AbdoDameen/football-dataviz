"""Football analytics: pitch control, Voronoi, pressure, and space metrics.

The tracking layer runs on StatsBomb 360 freeze-frames. **Important caveat:**
360 frames only contain players inside the broadcast camera's visible area, so
they are a truncated snapshot rather than full-pitch tracking. A typical frame
holds ~20 of 22 players, densest near the ball. Every surface-returning function
therefore also returns a ``coverage`` mask, and the figures shade the region where
the sample is adequate. Do not read values in unshaded regions as measurements.

Models implemented
------------------
``voronoi_control``   Nearest-player dominance. Fast, exact, easy to read, and
                      the right default for "who owns this space" graphics.
``spearman_control``  Pitch control after Spearman (2018), "Beyond Expected
                      Goals", Journal of Sports Analytics: per-player
                      time-to-intercept converted to a logistic probability.
``pressure_at``       Local opponent density around a point.

The pitch-control constants are tuned to look right on football broadcast
frames; they are a stylised reimplementation, not a validated model.
"""

from __future__ import annotations

import numpy as np

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0

#: Player reaction time before they can move, in seconds.
REACTION_TIME = 0.28
#: Sprint speed. Elite players peak near 9 yd/s; 8 is a sustainable team-mean.
MAX_PLAYER_SPEED = 8.0
#: Speed of a rolling ball leaving the carrier, in yards per second.
BALL_SPEED_BASE = 13.0
#: Reference intercept time (s) where a player is 50/50 to reach the ball.
INTERCEPT_REFERENCE = 1.0
#: Steepness of the intercept logistic. Low values make every player look
#: equally likely and flatten the surface into noise.
INTERCEPT_SHARPNESS = 4.0


def _time_to_intercept(px: float, py: float, bx: float, by: float,
                       ball_speed: float = BALL_SPEED_BASE) -> float:
    """Seconds for a player at ``(px, py)`` to intercept a ball leaving ``(bx, by)``.

    Solves the standard quadratic for the earliest meeting point of a ball
    travelling at ``ball_speed`` and a player running at ``MAX_PLAYER_SPEED``,
    then adds reaction time.
    """
    dx, dy = px - bx, py - by
    dist = float(np.hypot(dx, dy))
    if dist < 1e-6:
        return REACTION_TIME

    a = MAX_PLAYER_SPEED ** 2 - ball_speed ** 2
    b = -2.0 * dist * MAX_PLAYER_SPEED
    c = dist ** 2

    if abs(a) < 1e-9:
        t = -c / b if abs(b) > 1e-9 else dist / MAX_PLAYER_SPEED
    else:
        disc = b ** 2 - 4 * a * c
        if disc < 0:
            # Ball outruns the player everywhere; they can only chase it down.
            t = dist / MAX_PLAYER_SPEED
        else:
            root = np.sqrt(disc)
            cands = [tt for tt in ((-b - root) / (2 * a), (-b + root) / (2 * a)) if tt > 0]
            t = min(cands) if cands else dist / MAX_PLAYER_SPEED
    return float(t) + REACTION_TIME


def intercept_probability(t: float | np.ndarray) -> float | np.ndarray:
    """Logistic map from intercept time to probability.

    1.0/(1 + exp(k * (t - T))) with T = ``INTERCEPT_REFERENCE``: a player who can
    reach the point in under a second is likely to win it, one who needs two
    seconds almost certainly will not. This is the term that makes pitch control
    spatially discriminating; an exponent-inverse form saturates and produces a
    near-uniform surface.
    """
    return 1.0 / (1.0 + np.exp(INTERCEPT_SHARPNESS * (np.asarray(t) - INTERCEPT_REFERENCE)))


def probability_of_interception(px: float, py: float, bx: float, by: float) -> float:
    """Probability the player at ``(px, py)`` intercepts a ball leaving ``(bx, by)``."""
    return float(intercept_probability(_time_to_intercept(px, py, bx, by)))


# --------------------------------------------------------------------------- #
# Nearest-player (Voronoi) control
# --------------------------------------------------------------------------- #
def voronoi_control(teammates: np.ndarray, opponents: np.ndarray,
                    resolution: int = 120,
                    bounds: tuple[float, float, float, float] = (0, 120, 0, 80)
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Nearest-player dominance: ``(control, known)``.

    ``control`` is 1.0 where the nearest player is a teammate, 0.0 where it is an
    opponent, and 0.5 where no player is visible. ``known`` is False for the
    no-data cells so a figure can mask them instead of painting a fake tie.
    """
    x0, x1, y0, y1 = bounds
    gx = np.linspace(x0, x1, resolution)
    gy = np.linspace(y0, y1, resolution)
    gxx, gyy = np.meshgrid(gx, gy)

    def nearest_dist(pts: np.ndarray) -> np.ndarray:
        pts = np.asarray(pts, dtype=float).reshape(-1, 2)
        if len(pts) == 0:
            return np.full(gxx.shape, np.inf)
        d = (gxx[..., None] - pts[:, 0]) ** 2 + (gyy[..., None] - pts[:, 1]) ** 2
        return np.sqrt(d.min(axis=-1))

    dt = nearest_dist(teammates)
    do = nearest_dist(opponents)

    known = ~(np.isinf(dt) & np.isinf(do))
    control = np.where(dt < do, 1.0, 0.0)
    control = np.where(dt == do, 0.5, control)
    control = np.where(known, control, 0.5)
    return control, known


def voronoi_regions(teammates: np.ndarray, opponents: np.ndarray,
                    resolution: int = 240,
                    bounds: tuple[float, float, float, float] = (0, 120, 0, 80)):
    """Hard Voronoi labels: +1 teammate, -1 opponent, 0 unknown.

    Returns ``(labels, owner, gx, gy)`` where ``owner`` indexes into the
    concatenated [teammates, opponents] array (opponents are offset by -n-1).
    """
    x0, x1, y0, y1 = bounds
    gx = np.linspace(x0, x1, resolution)
    gy = np.linspace(y0, y1, resolution)
    gxx, gyy = np.meshgrid(gx, gy)

    def idx_dist(pts: np.ndarray):
        pts = np.asarray(pts, dtype=float).reshape(-1, 2)
        if len(pts) == 0:
            return np.full(gxx.shape, np.inf), np.full(gxx.shape, -1, dtype=int)
        d = (gxx[..., None] - pts[:, 0]) ** 2 + (gyy[..., None] - pts[:, 1]) ** 2
        return np.sqrt(d.min(axis=-1)), d.argmin(axis=-1)

    dt, it = idx_dist(teammates)
    do, io = idx_dist(opponents)

    labels = np.zeros(gxx.shape, dtype=int)
    labels[dt < do] = 1
    labels[do < dt] = -1
    labels[np.isinf(dt) & np.isinf(do)] = 0

    owner = np.where(dt <= do, it, -io - 1)
    owner[np.isinf(dt) & np.isinf(do)] = 0
    return labels, owner, gx, gy


# --------------------------------------------------------------------------- #
# Spearman pitch control
# --------------------------------------------------------------------------- #
def spearman_control(teammates: np.ndarray, opponents: np.ndarray,
                     ball_xy: tuple[float, float],
                     resolution: int = 100,
                     bounds: tuple[float, float, float, float] = (0, 120, 0, 80),
                     influence_radius: float = 45.0, min_visible: int = 12
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Pitch control for one freeze-frame: ``(control, coverage)``.

    ``control`` is the teammates' share of control in [0, 1], normalised per cell
    over every visible player. ``coverage`` is False where the frame holds too few
    players for the surface to mean anything.

    Coverage is a property of the *frame*, not the cell: a 360 frame either
    contains a player or it does not, so a distant cell is not "unsampled" merely
    because nobody stands near it. ``coverage`` is therefore all-False for a thin
    frame, and the low-confidence *region* is reported separately by
    :func:`low_confidence_mask` so a figure can hatch distance from the sample.

    Vectorised over the grid: at ``resolution=100`` a 22-player frame is ~10k
    cells x 22 players, which runs in well under a second.
    """
    x0, x1, y0, y1 = bounds
    gx = np.linspace(x0, x1, resolution)
    gy = np.linspace(y0, y1, resolution)
    gxx, gyy = np.meshgrid(gx, gy)
    cells = np.column_stack([gxx.ravel(), gyy.ravel()])
    bx, by = ball_xy

    mates = np.asarray(teammates, dtype=float).reshape(-1, 2)
    opps = np.asarray(opponents, dtype=float).reshape(-1, 2)

    if len(mates) + len(opps) == 0:
        return np.full(gxx.shape, 0.5), np.zeros(gxx.shape, dtype=bool)

    def weights_for(pts: np.ndarray) -> np.ndarray:
        """(n_cells, n_players) influence weights."""
        if len(pts) == 0:
            return np.zeros((len(cells), 0))
        d = np.hypot(cells[:, None, 0] - pts[None, :, 0],
                     cells[:, None, 1] - pts[None, :, 1])
        # Time for each player to reach the ball, from their own position.
        t = np.array([_time_to_intercept(px, py, bx, by) for px, py in pts])[None, :]
        # Cell distance adds travel time, then maps to intercept probability.
        t_total = t + d / MAX_PLAYER_SPEED
        w = intercept_probability(t_total)
        # A soft influence horizon so distant players cannot claim a cell.
        w = w * np.exp(-(d / influence_radius) ** 2)
        return w

    wm = weights_for(mates)
    wo = weights_for(opps)
    mate_sum = wm.sum(axis=1)
    total = mate_sum + wo.sum(axis=1)
    control = np.where(total > 1e-9, mate_sum / np.maximum(total, 1e-9), 0.5)

    # Coverage is binary for the whole frame, driven by player count and spread.
    all_pts = np.vstack([p for p in (mates, opps) if len(p)])
    enough_players = len(all_pts) >= min_visible
    coverage = np.full(gxx.shape, enough_players, dtype=bool)

    return control.reshape(gxx.shape), coverage


def low_confidence_mask(shape: tuple[int, int],
                        bounds: tuple[float, float, float, float],
                        teammates: np.ndarray, opponents: np.ndarray,
                        horizon: float = 40.0) -> np.ndarray:
    """Cells further than ``horizon`` yards from any visible player.

    These are extrapolations: the surface there is produced by the decay term,
    not by an observed player. Figures should hatch them rather than present them
    as measurement.
    """
    x0, x1, y0, y1 = bounds
    gx = np.linspace(x0, x1, shape[1])
    gy = np.linspace(y0, y1, shape[0])
    gxx, gyy = np.meshgrid(gx, gy)
    pts = np.vstack([np.asarray(p, dtype=float).reshape(-1, 2)
                     for p in (teammates, opponents) if len(p)])
    if len(pts) == 0:
        return np.ones(shape, dtype=bool)
    d = np.hypot(gxx[..., None] - pts[:, 0], gyy[..., None] - pts[:, 1])
    return d.min(axis=-1) > horizon


# --------------------------------------------------------------------------- #
# Pressure and space occupancy
# --------------------------------------------------------------------------- #
def pressure_at(points: np.ndarray, targets: np.ndarray, radius: float = 8.0) -> np.ndarray:
    """Count of ``points`` within ``radius`` yards of each row in ``targets``."""
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    targets = np.asarray(targets, dtype=float).reshape(-1, 2)
    if len(points) == 0:
        return np.zeros(len(targets))
    d = np.hypot(targets[:, None, 0] - points[None, :, 0],
                 targets[:, None, 1] - points[None, :, 1])
    return (d <= radius).sum(axis=1).astype(float)


def free_space_ratio(teammates: np.ndarray, opponents: np.ndarray) -> float:
    """Share of the known pitch where the nearest visible player is a teammate."""
    control, known = voronoi_control(teammates, opponents, resolution=90)
    if not known.any():
        return 0.5
    return float(np.mean(control[known]))


def convex_hull_area(points: np.ndarray) -> float:
    """Area of the convex hull of ``points`` (compactness / spread of a shape)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(pts) < 3:
        return 0.0
    try:
        from scipy.spatial import ConvexHull
    except ImportError:  # pragma: no cover - scipy is optional
        return 0.0
    try:
        return float(ConvexHull(pts).volume)
    except Exception:
        return 0.0


def team_shape(points: np.ndarray) -> dict:
    """Centroid, length, width and spread of a team's visible positions."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    if len(pts) == 0:
        return {"centroid": np.array([np.nan, np.nan]), "length": 0.0,
                "width": 0.0, "spread": 0.0}
    return {
        "centroid": pts.mean(axis=0),
        "length": float(pts[:, 0].max() - pts[:, 0].min()),
        "width": float(pts[:, 1].max() - pts[:, 1].min()),
        "spread": float(pts.std(axis=0).sum()),
    }
