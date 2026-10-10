"""
=============================================================================
ANGLE DIMENSION - an extension for IngeTrazo
=============================================================================
Version      : 1.0.0
Release date : 2026-10-06
Author       : Ryszard Jurdeczka
Licence      : MIT  (full text at the end of this header)
Requires     : IngeTrazo with extension API version 2 or newer
File name    : Angle_Dimension.py   (please do NOT rename - see the note below)
Developed as : Draw_Angle-rA_01 ... _13 (development revisions)

WHAT IT DOES
    Measures the angle between two lines that share a corner point (the
    "vertex") and leaves a permanent angle dimension in the drawing: two
    arms, an arc and the angle in degrees.

HOW TO INSTALL
    Copy this file into IngeTrazo's plugins folder (Extensions > Open
    plugins folder) and restart IngeTrazo.

HOW TO USE
    Extensions > Draw angle dim ........ Ctrl+Alt+A
        1. Click the VERTEX (the corner of the angle).
        2. Click a point on the FIRST ARM.
        3. Move the mouse - a live preview of the angle is shown.
        4. Click a point on the SECOND ARM - the dimension is saved.
    Extensions > Angle dim tools:
        Undo last angle dim ... Ctrl+Alt+U
            Cancels a half-finished dimension, otherwise removes the newest.
        Delete angle dim ...... Ctrl+Alt+D
            Then click on (or near) a dimension to delete it.
        Clear all angle dims .. Ctrl+Alt+E   (E = Erase all; asks first)
        About angle dim ....... Ctrl+Alt+I   (version and storage details)
    IngeTrazo's own Ctrl+Z also undoes adding or deleting a dimension.

WHERE THE DIMENSIONS ARE STORED
    Inside the open drawing (.igz), using IngeTrazo's extension storage.
    They are saved when you save the drawing, belong to that drawing only,
    and appear again when you open it. Adding or deleting a dimension counts
    as an edit (the drawing becomes "unsaved").

NOTE ON THE FILE NAME
    IngeTrazo files an extension's data inside the drawing under the
    extension's FILE NAME. If this file is renamed, drawings saved earlier
    will not show their dimensions (the data is still in the drawing: naming
    the file back to Angle_Dimension.py brings them back).

VERSION HISTORY
    1.0.0  2026-10-06  First public release. Built up over development
                       revisions 01-13: plain-language comments, label placed
                       outside the arc, dimensions stored in the drawing,
                       undo / delete / clear commands, sub-menu, and no
                       unwanted "Unnamed" menu entries.

KNOWN LIMITATIONS
    * Tested on Linux (MX Linux, IngeTrazo as a Flatpak) only.
    * 3D points are assumed to be in the units that IngeTrazo's
      world_to_pixels expects (metres, as it did in testing).
    * To keep IngeTrazo from listing the tool as an extra, unnamed menu
      entry, the tool class is created the first time it is used (see
      _tool_class()). This relies on how IngeTrazo currently builds its
      Extensions menu and may need updating if that changes.
    * Shortcuts are attached to the sub-menu items directly; if one clashes
      with another IngeTrazo shortcut it may not fire (the menu item still
      works).

LICENCE (MIT)
    Copyright (c) 2026 Ryszard Jurdeczka

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
=============================================================================
"""


# -----------------------------------------------------------------------------
# IMPORTS - bring in the tools (libraries) this file needs
# -----------------------------------------------------------------------------
from __future__ import annotations   # allows "float | None" style type hints

import math                          # sin, cos, atan2, degrees, radians, hypot

# PySide6 is the Qt toolkit that IngeTrazo uses for its window and drawing.
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPainter, QPen, QVector3D
from PySide6.QtWidgets import QMessageBox

# Helper that belongs to IngeTrazo itself.
from tools.base import Tool              # base class every IngeTrazo tool uses


# Information about this extension (shown in the About box)
__version__ = "1.0.0"
__author__ = "Ryszard Jurdeczka"
__license__ = "MIT"


# -----------------------------------------------------------------------------
# SETTINGS - change these values to alter how the tool looks or behaves
# -----------------------------------------------------------------------------
COLOR = QColor(242, 115, 41)         # Orange used for the dimension
SHORTCUT = "Ctrl+Alt+A"              # Start the draw tool
SHORTCUT_UNDO = "Ctrl+Alt+U"         # Undo last dimension
SHORTCUT_DELETE = "Ctrl+Alt+D"       # Pick a dimension to delete
SHORTCUT_CLEAR = "Ctrl+Alt+E"        # Erase (delete) all dimensions
SHORTCUT_ABOUT = "Ctrl+Alt+I"        # Show the About box

ARC_SEGMENTS = 48                    # The arc is drawn as 48 short straight lines
EPS = 1e-9                           # "Practically zero" - avoids divide-by-zero
MIN_CLICK_DISTANCE = 1e-6            # Clicks closer than this are the same point
ARC_RADIUS_FACTOR = 0.3              # Arc radius = 30% of the shorter arm
LINE_WIDTH = 2                       # Line thickness (pixels)

LABEL_FONT_SIZE = 10                 # Size of the angle text (points)
LABEL_PADDING_X = 10                 # Extra width around the text (pixels)
LABEL_PADDING_Y = 4                  # Extra height around the text (pixels)
LABEL_GAP = 6                        # Clear space between arc and label (pixels)
LABEL_BG = QColor(255, 255, 255, 230)    # Almost-opaque white behind the text

SUBMENU_TITLE = "Angle dim tools"    # Name of the sub-menu for the secondary commands
MIN_API_VERSION = 2                  # Oldest IngeTrazo extension API this file supports
PICK_TOLERANCE_PX = 20               # How close (pixels) a click must be to pick a dimension

DATA_FORMAT = 1                      # Version number of the stored data layout
LEGACY_KEY_PREFIX = "Draw_Angle"     # Early development copies (Draw_Angle-rA_NN) stored data under
                                     # these names; their data is still found and shown


# -----------------------------------------------------------------------------
# SHARED STATE - values the whole file uses
# -----------------------------------------------------------------------------
_APP = None          # IngeTrazo's extension object; filled in by setup() at the bottom
_DIMS = []           # The dimensions currently in the open drawing (a working copy).
                     # Each entry: (vertex, first arm end, second arm end, degrees)
_SOURCE = "none"     # Where _DIMS came from (shown in the info window)
_WARNED = False      # So the "cannot project" warning is only shown once
_TOOL_CLASS = None   # The tool class; created on first use by _tool_class()


def _flash(viewport, text: str, ms: int = 3000) -> None:
    """Show a message on IngeTrazo's status line."""
    try:
        viewport.flash_status(text, ms)
    except Exception:
        print(f"[Angle Dimension] {text}")   # fall back to the console


# -----------------------------------------------------------------------------
# MATHS HELPERS - pure geometry, no drawing
# -----------------------------------------------------------------------------
def angle_between(u: QVector3D, w: QVector3D) -> float | None:
    """Angle in DEGREES (0-180) between two direction vectors.

    Returns None if either vector has no length (angle undefined).
    atan2(|cross|, dot) stays accurate for very small/large angles.
    """
    if u.length() < EPS or w.length() < EPS:
        return None
    cross = QVector3D.crossProduct(u, w).length()
    dot = QVector3D.dotProduct(u, w)
    return math.degrees(math.atan2(cross, dot))


def angle_at(vertex: QVector3D, a: QVector3D, b: QVector3D) -> float | None:
    """Angle in degrees at `vertex` between the lines vertex->a and vertex->b."""
    return angle_between(a - vertex, b - vertex)


def arc_points(vertex, a, b, radius, n=ARC_SEGMENTS):
    """Return n+1 3D points forming an arc from arm A round to arm B.

    The arc is centred on `vertex` and lies in the plane of the two arms.
    Returns an empty list if the angle is undefined.
    """
    u, w = a - vertex, b - vertex
    theta = angle_between(u, w)
    if theta is None:
        return []

    e1 = u.normalized()                                  # along the first arm
    perp = w - e1 * QVector3D.dotProduct(w, e1)          # part of w at 90 degrees to e1
    if perp.length() < EPS:
        # Arms are in a straight line, so the plane is undefined:
        # pick any direction at right angles to e1.
        trial = QVector3D(0, 0, 1) if abs(e1.z()) < 0.9 else QVector3D(1, 0, 0)
        perp = QVector3D.crossProduct(e1, trial)
    e2 = perp.normalized()

    t_end = math.radians(theta)
    return [
        vertex + (e1 * math.cos(t) + e2 * math.sin(t)) * radius
        for t in (t_end * i / n for i in range(n + 1))
    ]


# -----------------------------------------------------------------------------
# CONVERSION HELPERS - turn "whatever IngeTrazo gives us" into usable values
# -----------------------------------------------------------------------------
def _to_vec3d(obj) -> QVector3D | None:
    """Convert a point of unknown type to a QVector3D, or None if impossible."""
    if obj is None:
        return None
    if isinstance(obj, QVector3D):
        return obj
    try:                                   # object with .x .y .z values
        return QVector3D(float(obj.x), float(obj.y), float(obj.z))
    except (AttributeError, TypeError, ValueError):
        pass
    try:                                   # list / tuple / array
        return QVector3D(float(obj[0]), float(obj[1]), float(obj[2]))
    except (TypeError, IndexError, ValueError):
        return None


def _to_qpointf(obj) -> QPointF | None:
    """Convert a 2D screen position of unknown type to a QPointF, or None."""
    if obj is None:
        return None
    try:                                   # Qt-style point: obj.x() and obj.y()
        return QPointF(float(obj.x()), float(obj.y()))
    except (AttributeError, TypeError, ValueError):
        pass
    try:                                   # list / tuple / array
        return QPointF(float(obj[0]), float(obj[1]))
    except (TypeError, IndexError, ValueError):
        return None


def _px_many(points) -> list:
    """Convert several 3D points (QVector3D) to screen positions in ONE call.

    Uses IngeTrazo's own world_to_pixels (the same projection its overlays
    use). Returns a list the same length as `points`; an entry is None if
    that point is behind the camera or could not be converted.
    """
    global _WARNED
    if not points:
        return []
    if _APP is None:
        return [None] * len(points)
    try:
        coords = [[p.x(), p.y(), p.z()] for p in points]
        px, py, in_front = _APP.world_to_pixels(coords)
        return [
            QPointF(float(x), float(y)) if bool(f) else None
            for x, y, f in zip(px, py, in_front)
        ]
    except Exception as exc:
        if not _WARNED:                      # tell the user once, not every frame
            _WARNED = True
            print(f"[Angle Dimension] world_to_pixels failed: {exc!r}")
            _flash(_APP.viewport, "Cannot convert 3D to screen", 6000)
        return [None] * len(points)


def _px(p):
    """Convert ONE 3D point to a screen position (QPointF), or None."""
    vec = _to_vec3d(p)
    return _px_many([vec])[0] if vec is not None else None


# -----------------------------------------------------------------------------
# STORAGE - keep the dimensions inside the drawing (.igz) file
# -----------------------------------------------------------------------------
def _encode(dims) -> dict:
    """Turn the working list into plain data that IngeTrazo can store (JSON-safe).

    Only the three points are stored; the angle is recalculated on loading.
    """
    return {
        "format": DATA_FORMAT,
        "dimensions": [
            {
                "v": [float(d[0].x()), float(d[0].y()), float(d[0].z())],
                "a": [float(d[1].x()), float(d[1].y()), float(d[1].z())],
                "b": [float(d[2].x()), float(d[2].y()), float(d[2].z())],
            }
            for d in dims
        ],
    }


def _decode(data) -> list:
    """Turn stored data back into the working list. Damaged entries are skipped."""
    result = []
    if not isinstance(data, dict):
        return result
    for item in data.get("dimensions", []) or []:
        try:
            v = QVector3D(*[float(c) for c in item["v"]])
            a = QVector3D(*[float(c) for c in item["a"]])
            b = QVector3D(*[float(c) for c in item["b"]])
        except (KeyError, TypeError, ValueError):
            continue                       # skip a damaged entry
        ang = angle_at(v, a, b)
        if ang is not None:
            result.append((v, a, b, ang))
    return result


def _find_other_revision_data():
    """Look (read-only) for dimensions stored by ANOTHER revision of this extension.

    IngeTrazo files extension data under the extension's key (its file name),
    so a newly renamed revision starts with an empty slot. This searches the
    drawing's stored extension data for keys starting with LEGACY_KEY_PREFIX
    (other than ours) and returns (key, dimensions) for the newest one that
    holds dimensions, or (None, []) if none.
    """
    try:
        stored = _APP.scene.plugin_data
        own_key = _APP.key
        for key in sorted(stored, reverse=True):        # newest name first
            if key == own_key or not str(key).startswith(LEGACY_KEY_PREFIX):
                continue
            dims = _decode(stored[key])
            if dims:
                return key, dims
    except Exception as exc:
        print(f"[Angle Dimension] other-revision lookup skipped: {exc!r}")
    return None, []


def _refresh_from_document() -> None:
    """Re-read the dimensions from the open drawing into the working list.

    IngeTrazo calls this whenever the drawing changes (New, Open, Undo,
    edit), and we also call it once at start-up.
    """
    global _SOURCE
    try:
        data = _APP.document_data(None)       # None = nothing stored for us yet
    except Exception as exc:
        print(f"[Angle Dimension] document_data failed: {exc!r}")
        data = None

    if data is not None:
        _DIMS[:] = _decode(data)              # our own data (may be an empty list)
        _SOURCE = "this drawing (own data)"
    else:
        key, dims = _find_other_revision_data()
        _DIMS[:] = dims
        _SOURCE = (f"read-only from other revision '{key}' (saved under this key "
                   "on the next edit)" if key else "none stored yet")

    try:
        _APP.viewport.update()                # redraw so the change shows
    except Exception:
        pass


def _commit() -> bool:
    """Save the working list into the drawing. Returns True on success.

    This is one undo step in IngeTrazo and marks the drawing as unsaved.
    (Note: an empty list is stored as empty data, NOT as None, so cleared
    dimensions are not "resurrected" from another revision.)
    """
    global _SOURCE
    try:
        _APP.set_document_data(_encode(_DIMS))
        _SOURCE = "this drawing (own data)"
        _APP.viewport.update()
        return True
    except Exception as exc:
        print(f"[Angle Dimension] save failed: {exc!r}")
        _flash(_APP.viewport, "Could not save angle dimensions", 5000)
        return False


# -----------------------------------------------------------------------------
# DRAWING - paints one complete angle dimension on screen
# -----------------------------------------------------------------------------
def _draw_dimension_elements(painter, v, a, b, ang) -> None:
    """Draw one angle dimension: two arm lines, an arc and a text label.

    v = vertex, a/b = ends of the first/second arm (world coordinates),
    ang = the angle in degrees (shown as text).
    """
    painter.save()                         # remember painter settings
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(COLOR, LINE_WIDTH))

        # Work out the arc, then convert ALL points to the screen in one call.
        radius = ARC_RADIUS_FACTOR * min((a - v).length(), (b - v).length())
        arc = arc_points(v, a, b, radius)
        screen = _px_many([v, a, b] + arc)
        px_v, px_a, px_b = screen[0], screen[1], screen[2]
        arc_px = screen[3:]

        # --- 1. The two arms ---
        if px_v and px_a:
            painter.drawLine(px_v, px_a)
        if px_v and px_b:
            painter.drawLine(px_v, px_b)

        # --- 2. The arc between the arms ---
        for p0, p1 in zip(arc_px, arc_px[1:]):
            if p0 and p1:                  # skip segments that cannot be shown
                painter.drawLine(p0, p1)

        # --- 3. The angle text, placed OUTSIDE the arc ---
        # Work in screen pixels: start at the middle of the arc, point away
        # from the vertex, and slide the label out until its whole box is
        # clear of the arc, plus a small gap.
        if len(arc_px) == ARC_SEGMENTS + 1 and px_v is not None:
            arc_mid = arc_px[ARC_SEGMENTS // 2]
            if arc_mid is not None:
                text = f"{ang:.1f}°"

                font = QFont()
                font.setBold(True)
                font.setPointSize(LABEL_FONT_SIZE)
                painter.setFont(font)
                fm = painter.fontMetrics()
                w = fm.horizontalAdvance(text) + LABEL_PADDING_X
                h = fm.height() + LABEL_PADDING_Y

                # Direction on screen from the vertex out through the arc.
                dx = arc_mid.x() - px_v.x()
                dy = arc_mid.y() - px_v.y()
                length = math.hypot(dx, dy)
                if length < 1e-6:
                    dx, dy = 0.0, -1.0           # arc has collapsed: just go up
                else:
                    dx, dy = dx / length, dy / length

                # How far the box reaches from its centre in that direction.
                reach = abs(dx) * w / 2 + abs(dy) * h / 2

                # Centre of the label: arc middle + reach + gap.
                cx = arc_mid.x() + dx * (reach + LABEL_GAP)
                cy = arc_mid.y() + dy * (reach + LABEL_GAP)
                box_x = int(cx - w / 2)
                box_y = int(cy - h / 2)

                # White rounded box (no outline), then the text on top.
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(LABEL_BG)
                painter.drawRoundedRect(box_x, box_y, w, h, 4, 4)
                painter.setPen(QPen(COLOR.darker(130)))
                painter.drawText(
                    box_x + LABEL_PADDING_X // 2,
                    box_y + LABEL_PADDING_Y // 2 + fm.ascent(),
                    text,
                )
    finally:
        painter.restore()                  # always put the painter back


def _saved_overlay(viewport, painter) -> None:
    """Called by IngeTrazo on every frame: draw all saved dimensions."""
    for v, a, b, ang in _DIMS:
        _draw_dimension_elements(painter, v, a, b, ang)


# -----------------------------------------------------------------------------
# PICKING HELPERS - used by the Delete tool to find the clicked dimension
# -----------------------------------------------------------------------------
def _dist_point_to_segment(p: QPointF, s0: QPointF, s1: QPointF) -> float:
    """Shortest distance (pixels) from point p to the line segment s0-s1."""
    vx, vy = s1.x() - s0.x(), s1.y() - s0.y()
    seg_len2 = vx * vx + vy * vy
    if seg_len2 < 1e-12:                   # segment is just a dot
        return math.hypot(p.x() - s0.x(), p.y() - s0.y())
    # How far along the segment the closest point is (0 = start, 1 = end).
    t = ((p.x() - s0.x()) * vx + (p.y() - s0.y()) * vy) / seg_len2
    t = max(0.0, min(1.0, t))
    return math.hypot(p.x() - (s0.x() + t * vx), p.y() - (s0.y() + t * vy))


def _dimension_screen_distance(dim, p: QPointF) -> float:
    """Distance (pixels) from screen point p to the nearest part of a dimension."""
    v, a, b, _ang = dim
    radius = ARC_RADIUS_FACTOR * min((a - v).length(), (b - v).length())
    # Outline: arm 1, arm 2, then the arc as a chain of points.
    chains = [[v, a], [v, b], arc_points(v, a, b, radius)]
    best = float("inf")
    for chain in chains:
        pix = _px_many(chain)
        for s0, s1 in zip(pix, pix[1:]):
            if s0 is not None and s1 is not None:
                best = min(best, _dist_point_to_segment(p, s0, s1))
    return best


# -----------------------------------------------------------------------------
# TOOL 1 - DRAW: three clicks (vertex, arm 1, arm 2) create a dimension
# -----------------------------------------------------------------------------
def _tool_class():
    """Return the tool class, creating it the first time it is needed.

    WHY LAZY? IngeTrazo automatically lists every Tool class that exists when
    its Extensions menu is built. That listing does not start our tool (it
    did nothing when clicked) and, for a nameless class, showed as "Unnamed".
    Creating the class only when the user first starts the tool keeps it out
    of that automatic list. This file's own menu item starts the tool instead.
    """
    global _TOOL_CLASS
    if _TOOL_CLASS is not None:
        return _TOOL_CLASS

    class DrawAngleDimTool(Tool):
        """Interactive tool for creating angle dimensions (and, in delete mode,
        for picking a dimension to delete).

        Only ONE tool class exists (a second would be a second automatic menu
        entry), and it is created on first use - see _tool_class().
        """

        name = "Draw angle dim"                                  # shown in status / help
        description = "Measure and save permanent angle dimensions."  # tooltip / F3 help

        uses_snap = True   # snap clicks to nearby points/edges

        def __init__(self, delete_mode: bool = False) -> None:
            # delete_mode=True: clicking picks a saved dimension to delete,
            # instead of drawing a new one.
            self.delete_mode = delete_mode
            self.uses_snap = not delete_mode   # deleting needs the raw click, not a snap
            self._reset()

        def _reset(self) -> None:
            """Forget any half-finished dimension and go back to step 1."""
            self.start_point = None   # the vertex (click 1)
            self.arm_a = None         # end of the first arm (click 2)
            self.hover = None         # current mouse position (for the preview)

        def is_in_progress(self) -> bool:
            """True if the user has clicked at least once on the current dimension."""
            return self.start_point is not None

        def on_activate(self, viewport) -> None:
            self._reset()
            if self.delete_mode:
                viewport.flash_status("Click a dimension to delete it", 4000)
            else:
                viewport.flash_status("Click the vertex", 3000)

        def on_deactivate(self, viewport) -> None:
            self._reset()

        def on_hover(self, ctx) -> None:
            """Mouse moved: remember where, so the preview follows the cursor."""
            p = _to_vec3d(getattr(ctx, "world", None))
            if p is not None:
                self.hover = p
                ctx.viewport.update()

        def on_click(self, ctx) -> None:
            """Mouse clicked: advance through the three steps (or delete, in delete mode)."""
            if self.delete_mode:
                _delete_dimension_at(ctx)
                return
            p = _to_vec3d(getattr(ctx, "world", None))
            vp = ctx.viewport
            if p is None:
                return

            if self.start_point is None:
                # STEP 1 - the vertex.
                self.start_point = p
                vp.flash_status("Click first arm", 3000)

            elif self.arm_a is None:
                # STEP 2 - first arm. Ignore a click on top of the vertex.
                if (p - self.start_point).length() < MIN_CLICK_DISTANCE:
                    return
                self.arm_a = p
                vp.flash_status("Click second arm", 3000)

            else:
                # STEP 3 - second arm; finish the dimension.
                ang = angle_at(self.start_point, self.arm_a, p)
                if ang is None:
                    vp.flash_status("Invalid angle - pick a different point", 2000)
                    return
                _DIMS.append((self.start_point, self.arm_a, p, ang))
                if _commit():                               # save into the drawing
                    vp.flash_status("Dimension Anchored!", 2000)
                self._reset()

            vp.update()

        def rubber_band_lines(self):
            """Temporary guide lines IngeTrazo draws while the tool is in use."""
            v = self.start_point
            if v is None:
                return []
            lines = []
            if self.arm_a is not None:
                lines.append((v, self.arm_a))
            if self.hover is not None:
                lines.append((v, self.hover))
            return lines

        def draw_overlay(self, viewport, painter) -> None:
            """Live preview of the angle while choosing the second arm."""
            if self.start_point is not None and self.arm_a is not None and self.hover is not None:
                ang = angle_at(self.start_point, self.arm_a, self.hover)
                if ang is not None:
                    _draw_dimension_elements(painter, self.start_point, self.arm_a, self.hover, ang)

    _TOOL_CLASS = DrawAngleDimTool
    return _TOOL_CLASS


# -----------------------------------------------------------------------------
# DELETE - click on a dimension to remove it (runs inside the draw tool)
# -----------------------------------------------------------------------------
def _delete_dimension_at(ctx) -> None:
    """Delete the saved dimension nearest to the click, if one is close enough."""
    vp = ctx.viewport
    if not _DIMS:
        _flash(vp, "No dimension near that click", 2000)
        return

    # Where on the SCREEN did the user click? Try a screen position supplied
    # by IngeTrazo first; otherwise project the 3D click point.
    click = None
    for name in ("pixel", "screen", "pos", "position"):
        click = _to_qpointf(getattr(ctx, name, None))
        if click is not None:
            break
    if click is None:
        click = _px(getattr(ctx, "world", None))
    if click is None:
        return

    # Find the dimension whose lines/arc pass closest to the click.
    best_i, best_d = None, float("inf")
    for i, dim in enumerate(_DIMS):
        d = _dimension_screen_distance(dim, click)
        if d < best_d:
            best_i, best_d = i, d

    if best_i is not None and best_d <= PICK_TOLERANCE_PX:
        del _DIMS[best_i]
        if _commit():
            _flash(vp, "Dimension deleted", 2000)
        vp.update()
    else:
        _flash(vp, "No dimension near that click", 2000)


# -----------------------------------------------------------------------------
# MENU COMMANDS - undo / clear / info
# -----------------------------------------------------------------------------
def _undo_last() -> None:
    """Cancel a half-finished dimension, or else remove the newest saved one."""
    vp = _APP.viewport
    # If the draw tool is active and the user is part-way through, just cancel.
    tool = getattr(vp, "active_tool", None) or getattr(vp, "_active_tool", None)
    if _TOOL_CLASS is not None and isinstance(tool, _TOOL_CLASS) and tool.is_in_progress():
        tool._reset()
        _flash(vp, "Cancelled", 2000)
        vp.update()
        return

    if _DIMS:
        _DIMS.pop()                        # remove the newest
        if _commit():
            _flash(vp, "Last dimension removed", 2000)
    else:
        _flash(vp, "Nothing to undo", 2000)


def _clear_all() -> None:
    """Delete every dimension, after asking the user to confirm."""
    vp = _APP.viewport
    if not _DIMS:
        _flash(vp, "Nothing to undo", 2000)
        return
    answer = QMessageBox.question(
        vp, "Clear all angle dims", "Delete ALL angle dimensions?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,       # "No" is the safe default
    )
    if answer == QMessageBox.StandardButton.Yes:
        _DIMS.clear()
        if _commit():
            _flash(vp, "All angle dimensions cleared", 2000)


def _show_about() -> None:
    """Show the version and where the dimensions of this drawing come from."""
    vp = _APP.viewport
    text = (
        f"Angle Dimension  {__version__}\n"
        f"Licence: {__license__}\n\n"
        f"Dimensions in the open drawing: {len(_DIMS)}\n"
        f"Loaded from: {_SOURCE}"
    )
    QMessageBox.information(vp, "About angle dim", text)


# -----------------------------------------------------------------------------
# MENU HELPER - add one item (with shortcut) to a sub-menu
# -----------------------------------------------------------------------------
def _add_menu_item(menu, text, fn, shortcut, tip):
    """Add a command to `menu`; `fn` is called with no arguments when chosen."""
    action = QAction(text, menu)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    if tip:
        action.setStatusTip(tip)
    action.triggered.connect(lambda _checked=False: fn())
    menu.addAction(action)
    return action


# -----------------------------------------------------------------------------
# EXTENSION ENTRY POINT - IngeTrazo calls setup(app) once when it loads this file
# -----------------------------------------------------------------------------
def setup(app) -> None:
    """Connect to the drawing, register the overlay, and build the menus."""
    global _APP

    # --- Part 0: make sure this IngeTrazo is new enough. If not, say so
    #             clearly and do nothing else, instead of failing oddly. ---
    api = getattr(app, "api_version", None)
    if not isinstance(api, int) or api < MIN_API_VERSION:
        message = (f"Angle Dimension needs IngeTrazo extension API "
                   f"{MIN_API_VERSION} or newer (this IngeTrazo reports {api}).")
        print(f"[Angle Dimension] {message}")
        _flash(app.viewport, message, 8000)
        return

    _APP = app            # remembered so the rest of the file can use IngeTrazo's functions
    vp = app.viewport

    # --- Part 1: load the dimensions already stored in the open drawing,
    #             and reload them whenever the drawing changes (Open / New / Undo...) ---
    _refresh_from_document()
    app.on_document_changed(_refresh_from_document)

    # --- Part 2: have IngeTrazo call our drawing routine on every frame ---
    app.add_overlay(_saved_overlay)

    # --- Part 3: menus ---
    def start_draw() -> None:
        vp.set_active_tool(_tool_class()())                    # normal drawing mode
        vp.setFocus()

    def start_delete() -> None:
        vp.set_active_tool(_tool_class()(delete_mode=True))    # pick-to-delete mode
        vp.setFocus()

    # The main command sits directly in the Extensions menu.
    app.add_menu_action("Draw angle dim", start_draw, SHORTCUT,
                        tip="Measure and save permanent angle dimensions.")

    # The secondary commands go into their own sub-menu.
    commands = [
        ("Undo last angle dim", _undo_last, SHORTCUT_UNDO,
         "Cancel the current dimension, or remove the newest one."),
        ("Delete angle dim", start_delete, SHORTCUT_DELETE,
         "Click on a dimension to delete it."),
        ("Clear all angle dims", _clear_all, SHORTCUT_CLEAR,
         "Remove every angle dimension (asks first)."),
        ("About angle dim", _show_about, SHORTCUT_ABOUT,
         "Show the version and where the dimensions are stored."),
    ]
    submenu = app.add_menu(SUBMENU_TITLE)
    if submenu is not None:
        for text, fn, shortcut, tip in commands:
            _add_menu_item(submenu, text, fn, shortcut, tip)
    else:
        # No sub-menu available here: fall back to plain Extensions-menu entries.
        for text, fn, shortcut, tip in commands:
            app.add_menu_action(text, fn, shortcut, tip=tip)
