"""Shared themed console for pretty pipeline output."""

import sys

# Force UTF-8 so rich can render emoji / unicode on Windows (cp1252 by default).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # older Python or already-wrapped streams

from rich.console import Console
from rich.theme import Theme

_theme = Theme({
    "stage": "bold cyan",
    "success": "bold green",
    "tool": "yellow",
    "error": "bold red",
    "muted": "dim",
    "accent": "magenta",
})

console = Console(theme=_theme)
