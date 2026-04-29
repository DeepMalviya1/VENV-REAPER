"""Rich theme that mirrors the Streamlit hacker palette.

Color tokens are intentionally identical to the CSS :root variables in
reaper_theme.css so CLI output and the web UI stay visually unified.
"""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

REAPER_THEME = Theme(
    {
        # Core palette (matches CSS --green / --green-dim / --red / etc.)
        "reaper.green":     "#00ff41",
        "reaper.green_dim": "#00bb30",
        "reaper.green_dark": "#004d10",
        "reaper.red":       "#ff2222",
        "reaper.yellow":    "#f0e040",
        "reaper.cyan":      "#00e5ff",
        "reaper.text":      "#b0ffb8",
        "reaper.text_dim":  "#4a7a50",
        "reaper.orange":    "#ff8c00",

        # Severity tiers (mirrors sz-ok/med/high/crit)
        "sz.ok":   "#00ff41",
        "sz.med":  "#f0e040",
        "sz.high": "#ff8c00",
        "sz.crit": "#ff2222",

        # Terminal log message kinds (mirrors t-ok/info/warn/err/dim)
        "log.ok":   "bold #00ff41",
        "log.info": "#00e5ff",
        "log.warn": "#f0e040",
        "log.err":  "bold #ff2222",
        "log.dim":  "#4a7a50",

        # Headings / labels
        "h1": "bold #00ff41 on default",
        "h2": "bold #00e5ff",
        "label": "#4a7a50",
        "value": "#b0ffb8",
        "primary": "bold #00ff41",
        "danger":  "bold #ff2222",
    }
)


def make_console() -> Console:
    """Build a Console wired to the REAPER_THEME, defaulting to truecolor."""
    return Console(theme=REAPER_THEME, highlight=False, soft_wrap=False)
