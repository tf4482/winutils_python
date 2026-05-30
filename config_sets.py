"""Helpers for selecting named configuration sets from YAML config files."""

import sys
from collections.abc import Sequence
from typing import Any

from winutils_python import config as config_utils
from winutils_python import menu


def section_sets(config: dict[str, Any], section: str) -> dict[str, Any]:
    """Return configured sets from a top-level config section."""

    return config_utils.get_table(config, section)


def config_key(section: str, set_name: str, name: str) -> str:
    """Return a dotted config key for human-readable error messages."""

    return f"{section}.{set_name}.{name}"


def validate_set_name(
    config: dict[str, Any],
    section: str,
    set_name: str,
    *,
    label: str,
    allow_cancel: bool = False,
) -> str:
    """Validate a requested configured set name and return it unchanged."""

    if allow_cancel and menu.is_cancel_choice(set_name):
        raise SystemExit(0)

    sets = section_sets(config, section)

    if set_name not in sets:
        available_sets = ", ".join(sets) or "none"
        raise SystemExit(f"Unknown {label} '{set_name}'. Available sets: {available_sets}")

    return set_name


def get_set_config(
    config: dict[str, Any],
    section: str,
    set_name: str,
    *,
    label: str,
    allow_cancel: bool = False,
    error_cls: type[Exception] = TypeError,
    not_table_message: str | None = None,
) -> dict[str, Any]:
    """Return one configured set table from a top-level config section."""

    if allow_cancel and menu.is_cancel_choice(set_name):
        raise SystemExit(0)

    set_config = section_sets(config, section).get(set_name)

    if not isinstance(set_config, dict):
        message = not_table_message or f"{label} '{set_name}' must be a table"
        raise error_cls(message)

    return set_config


def choose_set_terminal(
    config: dict[str, Any],
    section: str,
    *,
    header: str,
    empty_message: str,
    prompt: str = menu.DEFAULT_PROMPT,
) -> str:
    """Prompt the user to choose one configured set from the terminal."""

    return menu.choose_mapping_key_terminal(
        section_sets(config, section),
        header=header,
        empty_message=empty_message,
        prompt=prompt,
    )


def selected_set_name(
    config: dict[str, Any],
    section: str,
    *,
    label: str,
    header: str,
    empty_message: str,
    prompt: str = menu.DEFAULT_PROMPT,
    argv: Sequence[str] | None = None,
    allow_cancel: bool = False,
) -> str:
    """Return a configured set selected from CLI args or terminal menu."""

    arguments = sys.argv if argv is None else argv

    if len(arguments) > 1:
        return validate_set_name(
            config,
            section,
            menu.normalize_selection_name(arguments[1]),
            label=label,
            allow_cancel=allow_cancel,
        )

    return choose_set_terminal(
        config,
        section,
        header=header,
        empty_message=empty_message,
        prompt=prompt,
    )
