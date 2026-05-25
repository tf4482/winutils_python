"""Terminal output helpers for colored status messages and emojis."""

import sys


RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
DEFAULT_SUCCESS_EMOJI = "success"

EMOJIS = {
    "archive": "🖼️",
    "connect": "🔌",
    "done": "🎉",
    "error": "❌",
    "list": "📋",
    "move": "📦",
    "package": "📦",
    "select": "👉",
    "start": "🚀",
    "success": "✅",
    "warning": "⚠️",
}

COLORS = {
    "error": RED,
    "info": CYAN,
    "start": BOLD + CYAN,
    "success": GREEN,
    "warning": YELLOW,
    "done": BOLD + GREEN,
}


def is_terminal() -> bool:
    """Return whether stdout is an interactive terminal."""

    return bool(sys.stdout and sys.stdout.isatty())


def emoji_for(name: str) -> str:
    """Return a configured emoji by symbolic name, or the name itself."""

    return EMOJIS.get(name, name)


def color_for(name: str) -> str:
    """Return an ANSI color by symbolic name, or the name itself."""

    return COLORS.get(name, name)


def colorize(message: str, color: str = "", *, enabled: bool | None = None) -> str:
    """Wrap a message in ANSI color codes when color output is enabled."""

    if enabled is None:
        enabled = is_terminal()

    if not enabled or not color:
        return message

    return f"{color}{message}{RESET}"


def print_status(message: str, color: str = "") -> None:
    """Print a raw colored status message in interactive terminals."""

    if not is_terminal():
        return

    print(colorize(message, color, enabled=True), flush=True)


def visual_message(message: str, *, emoji: str = "", color: str = "") -> str:
    """Build a colorized message with an optional emoji prefix."""

    text = prefix_emoji(message, emoji)
    return colorize(text, color_for(color), enabled=True)


def prefix_emoji(message: str, emoji: str = "") -> str:
    """Prefix a message with an emoji when one is configured."""

    icon = emoji_for(emoji)

    if not icon:
        return message

    return f"{icon} {message}"


def print_visual(message: str, *, emoji: str = "", color: str = "") -> None:
    """Print a visual status message in interactive terminals."""

    if not is_terminal():
        return

    print(visual_message(message, emoji=emoji, color=color), flush=True)


def print_blank() -> None:
    """Print a blank line in interactive terminals."""

    if not is_terminal():
        return

    print(flush=True)


def print_start(message: str) -> None:
    """Print a start status message."""

    print_visual(message, emoji="start", color="start")


def print_info(message: str, *, emoji: str = "") -> None:
    """Print an informational status message."""

    print_visual(message, emoji=emoji, color="info")


def print_list_header(message: str) -> None:
    """Print a formatted list header."""

    print_visual(message, emoji="list", color="info")


def print_list_item(index: int, message: str) -> None:
    """Print one numbered list item."""

    print_visual(f"{index}. {message}", emoji="select", color="info")


def print_success(message: str, *, emoji: str = DEFAULT_SUCCESS_EMOJI) -> None:
    """Print a success status message."""

    print_visual(message, emoji=emoji, color="success")


def print_warning(message: str) -> None:
    """Print a warning status message."""

    print_visual(message, emoji="warning", color="warning")


def print_error(message: str) -> None:
    """Print an error status message."""

    print_visual(message, emoji="error", color="error")


def print_done(message: str) -> None:
    """Print a completion status message."""

    print_visual(message, emoji="done", color="done")
