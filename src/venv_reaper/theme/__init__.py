"""Reaper hacker-aesthetic theme — shared across CLI, TUI, Streamlit, IDE webview."""

from __future__ import annotations

from importlib.resources import files


def load_css() -> str:
    """Return the global hacker theme CSS (without surrounding <style> tags)."""
    return files("venv_reaper.theme").joinpath("reaper_theme.css").read_text(encoding="utf-8")


def load_matrix_rain_js() -> str:
    """Return the Matrix-rain canvas script (without surrounding <script> tags)."""
    return files("venv_reaper.theme").joinpath("matrix_rain.js").read_text(encoding="utf-8")


def style_block() -> str:
    """Return the CSS wrapped in a <style> tag, ready for st.markdown(unsafe_allow_html=True)."""
    return f"<style>\n{load_css()}\n</style>"


def matrix_rain_block() -> str:
    """Return the Matrix-rain JS wrapped in a <script> tag, ready for st.html()."""
    return f"<script>\n{load_matrix_rain_js()}\n</script>"


from venv_reaper.theme.ascii_art import REAPER_BANNER, TAGLINE, banner_lines
from venv_reaper.theme.rich_theme import REAPER_THEME, make_console

__all__ = [
    "REAPER_BANNER",
    "REAPER_THEME",
    "TAGLINE",
    "banner_lines",
    "load_css",
    "load_matrix_rain_js",
    "make_console",
    "matrix_rain_block",
    "style_block",
]
