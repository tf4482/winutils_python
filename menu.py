"""Terminal selection helpers for choosing named config entries."""

from collections.abc import Mapping
from typing import Any

from winutils_python import visual

CANCEL_CHOICES = {"exit", "quit", "cancel"}
DEFAULT_PROMPT = "Select set by number or name (or 'exit' to cancel): "


def normalize_selection_name(selection: str) -> str:
    """Normalize a CLI/menu selection by stripping option prefixes."""

    return selection.lstrip("/-")


def is_cancel_choice(choice: str) -> bool:
    """Return whether a selection should cancel the menu."""

    return choice.lower() in CANCEL_CHOICES


def choose_mapping_key_terminal(
    options: Mapping[str, Any],
    *,
    header: str,
    empty_message: str,
    prompt: str = DEFAULT_PROMPT,
) -> str:
    """Prompt until the user chooses a key by name or number."""

    if not options:
        raise SystemExit(empty_message)

    names = list(options.keys())
    print_options(header, names)

    while True:
        selected_name = read_selection(prompt, options, names)

        if selected_name is not None:
            return selected_name

        visual.print_warning("Invalid selection. Try again.")


def print_options(header: str, names: list[str]) -> None:
    """Print a numbered option list."""

    visual.print_list_header(header)
    for index, name in enumerate(names, start=1):
        visual.print_list_item(index, name)


def read_selection(prompt: str, options: Mapping[str, Any], names: list[str]) -> str | None:
    """Read one selection and return a matching option key when valid."""

    choice = input(prompt).strip()

    if not choice or is_cancel_choice(choice):
        raise SystemExit(0)

    normalized = normalize_selection_name(choice)
    if normalized in options:
        return normalized

    if choice.isdigit():
        return name_from_number(int(choice), names)

    return None


def name_from_number(number: int, names: list[str]) -> str | None:
    """Return the option name for a 1-based menu number."""

    if 1 <= number <= len(names):
        return names[number - 1]

    return None
