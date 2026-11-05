"""
The system's colours for AEAM's interface (owner request, 2026-11-06).

AEAM's design is drawn in greys from black to white. Each grey keeps its place on that scale but is
mapped onto the system's own background and text colours: black becomes the system background,
white the system text, and a grey in between the same mix of the two. Contrast and layout stay as
designed; light or dark follows the system. Selections use the system accent. Colours with a hue
(red errors, green online dots, gold) keep their meaning and are left alone.

It follows the system live: change a colour in the system settings and AEAM's windows change with
it, within a second, without a restart.

Where the colours come from, first found wins:
  1. Infynitae's settings (~/.config/infynitae/config): SURFACE_COLOR (background), TEXT_COLOR (text)
     and BORDER_ACTIVE (the accent: the active window's border, also GTK's selection colour), or the
     GNOME accent setting (gsettings accent-color) when there is no BORDER_ACTIVE.
  2. The Qt platform palette (Window, WindowText, Highlight) on any other desktop.
  3. AEAM's original black and white.
AEAM_THEME=original keeps the original greys.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

HEX = re.compile(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b")
# a property that paints an area; the rest (color, border…) are lines and text
_SELECTION = re.compile(r"(selection-background-color\s*:\s*)(#[0-9A-Fa-f]{3,6})\b")

# GNOME's accent names (libadwaita 1.6 accent colours)
ACCENTS = {
    "blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800", "orange": "#ed5b00",
    "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac", "slate": "#6f8396",
}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(c: tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(v))) for v in c))


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[float, float, float]:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _infynitae() -> dict[str, str]:
    path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "infynitae" / "config"
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r'^([A-Z_]+)=(?:"([^"]*)"|(\S*))', line)
            if m:
                out[m.group(1)] = (m.group(2) if m.group(2) is not None else m.group(3)).strip()
    except OSError:
        pass
    return out


def _gnome_accent() -> str | None:
    if not shutil.which("gsettings"):
        return None
    try:
        name = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "accent-color"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip().strip("'")
    except (OSError, subprocess.SubprocessError):
        return None
    return ACCENTS.get(name)


def _qt_palette() -> tuple[str, str, str] | None:
    try:
        from PyQt6 import QtGui, QtWidgets
    except ImportError:
        return None
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None
    pal = app.palette()
    role = QtGui.QPalette.ColorRole
    return pal.color(role.Window).name(), pal.color(role.WindowText).name(), pal.color(role.Highlight).name()


@lru_cache(maxsize=1)
def palette() -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]] | None:
    """(background, text, accent), or None to keep the original greys."""
    if os.environ.get("AEAM_THEME", "").lower() == "original":
        return None
    cfg = _infynitae()
    if HEX.fullmatch(cfg.get("SURFACE_COLOR", "")) and HEX.fullmatch(cfg.get("TEXT_COLOR", "")):
        bg, text = cfg["SURFACE_COLOR"], cfg["TEXT_COLOR"]
        accent = cfg.get("BORDER_ACTIVE", "")
        if not HEX.fullmatch(accent):
            accent = _gnome_accent() or ACCENTS["blue"]
    else:
        qt = _qt_palette()
        if qt is None:
            return None
        bg, text, accent = qt
    return _rgb(bg), _rgb(text), _rgb(accent)


def _grey(c: tuple[int, int, int]) -> bool:
    return max(c) - min(c) <= 12


@lru_cache(maxsize=4096)
def color(h: str) -> str:
    """One colour of the design, in the system's colours."""
    pal = palette()
    if pal is None:
        return h
    c = _rgb(h)
    if not _grey(c):
        return h
    bg, text, _ = pal
    return _hex(_mix(bg, text, sum(c) / (3 * 255)))


def css(sheet: str) -> str:
    """A style sheet or rich text with every grey in the system's colours."""
    if not isinstance(sheet, str) or "#" not in sheet or palette() is None:
        return sheet
    accent = _hex(palette()[2])
    sheet = _SELECTION.sub(lambda m: m.group(1) + accent, sheet)
    return HEX.sub(lambda m: color(m.group(0)), sheet)


_ORIGINAL: dict[str, object] = {}
_APP_SHEET: list[str] = []
_watch: list[object] = []


def install() -> None:
    """Make every style sheet, label and colour name in the app follow the system's colours, now
    and whenever they change.

    Call once, after the QApplication exists and before any window is built. The design's greys are
    written all over the interface (about 300 places), so they are translated where Qt receives
    them rather than rewritten by hand; each widget keeps its untranslated sheet so a change of
    system colours can paint it again."""
    if os.environ.get("AEAM_THEME", "").lower() == "original" or _ORIGINAL:
        return
    from PyQt6 import QtCore, QtGui, QtWidgets

    _ORIGINAL["widget_sheet"] = QtWidgets.QWidget.setStyleSheet
    _ORIGINAL["app_sheet"] = QtWidgets.QApplication.setStyleSheet
    _ORIGINAL["label_text"] = QtWidgets.QLabel.setText
    _ORIGINAL["color"] = QtGui.QColor

    def widget_sheet(self, sheet):
        self.setProperty("_aeam_css", sheet)
        return _ORIGINAL["widget_sheet"](self, css(sheet))

    def app_sheet(self, sheet):
        _APP_SHEET[:] = [sheet]
        return _ORIGINAL["app_sheet"](self, css(sheet))

    def label_text(self, text):
        if isinstance(text, str) and "#" in text:
            self.setProperty("_aeam_text", text)
        return _ORIGINAL["label_text"](self, css(text))

    QtWidgets.QWidget.setStyleSheet = widget_sheet
    QtWidgets.QApplication.setStyleSheet = app_sheet
    QtWidgets.QLabel.setText = label_text

    class QLabel(QtWidgets.QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if args and isinstance(args[0], str):
                label_text(self, args[0])

    class QColor(_ORIGINAL["color"]):
        def __init__(self, *args):
            if len(args) == 1 and isinstance(args[0], str) and HEX.fullmatch(args[0]):
                args = (color(args[0]),)
            super().__init__(*args)

    QtWidgets.QLabel = QLabel
    QtGui.QColor = QColor
    _apply_palette()

    # follow the system: Infynitae's settings file (often replaced, not written in place, so its
    # folder is watched too) and dconf, where the GNOME accent lives
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    paths = [str(p) for p in (cfg / "infynitae" / "config", cfg / "infynitae", cfg / "dconf" / "user") if p.exists()]
    watcher = QtCore.QFileSystemWatcher(paths)
    timer = QtCore.QTimer(singleShot=True, interval=300)

    def changed(_path=""):
        # a replaced file drops out of the watch; add it back
        for p in paths:
            if p not in watcher.files() + watcher.directories() and Path(p).exists():
                watcher.addPath(p)
        timer.start()

    watcher.fileChanged.connect(changed)
    watcher.directoryChanged.connect(changed)
    timer.timeout.connect(refresh)
    _watch[:] = [watcher, timer]


def refresh() -> None:
    """Paint the app again in the system's current colours (after a change)."""
    from PyQt6 import QtWidgets

    before = palette()
    palette.cache_clear()
    color.cache_clear()
    if palette() == before:
        return
    app = QtWidgets.QApplication.instance()
    _apply_palette()
    if _APP_SHEET:
        _ORIGINAL["app_sheet"](app, css(_APP_SHEET[0]))
    for w in app.allWidgets():
        sheet = w.property("_aeam_css")
        if sheet is not None:
            _ORIGINAL["widget_sheet"](w, css(sheet))
        text = w.property("_aeam_text")
        if text is not None and isinstance(w, QtWidgets.QLabel):
            _ORIGINAL["label_text"](w, css(text))


def _apply_palette() -> None:
    """Native parts Qt draws itself (scroll areas, menus, tooltips) in the same colours."""
    from PyQt6 import QtGui, QtWidgets

    pal_now = palette()
    if pal_now is None:
        return
    bg, text, accent = pal_now
    make = _ORIGINAL.get("color", QtGui.QColor)
    app = QtWidgets.QApplication.instance()
    pal = app.palette()
    role = QtGui.QPalette.ColorRole
    on_accent = (0, 0, 0) if sum(accent) > 3 * 150 else (255, 255, 255)
    for r, c in ((role.Window, bg), (role.Base, bg), (role.AlternateBase, _mix(bg, text, 0.04)),
                 (role.WindowText, text), (role.Text, text), (role.ButtonText, text),
                 (role.Button, _mix(bg, text, 0.06)), (role.ToolTipBase, bg), (role.ToolTipText, text),
                 (role.Highlight, accent), (role.HighlightedText, on_accent)):
        pal.setColor(r, make(_hex(c)))
    app.setPalette(pal)
