"""Reusable config completeness checks with console reporting."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from winutils_python import visual


@dataclass(frozen=True)
class RequiredKey:
    """Description of a required config key."""

    key: str
    label: str | None = None
    allow_empty: bool = False


def required_key(key: str, *, label: str | None = None, allow_empty: bool = False) -> RequiredKey:
    """Return a required-key descriptor."""

    return RequiredKey(key, label=label, allow_empty=allow_empty)


def missing_keys(config: dict[str, Any], required_keys: Iterable[RequiredKey]) -> list[str]:
    """Return labels for required keys that are missing or empty."""

    missing: list[str] = []

    for required in required_keys:
        label = required.label or required.key
        if required.key not in config:
            missing.append(label)
            continue

        value = config[required.key]
        if required.allow_empty:
            continue

        if value is None or value == "" or value == [] or value == {}:
            missing.append(label)

    return missing


def report_missing_keys(missing: list[str]) -> None:
    """Print missing config keys to the console."""

    if not missing:
        return

    visual.print_error("Missing required configuration option(s):")
    for key in missing:
        visual.print_error(f"- {key}")


def require_keys(config: dict[str, Any], required_keys: Iterable[RequiredKey]) -> None:
    """Print and fail when required config keys are missing."""

    missing = missing_keys(config, required_keys)
    report_missing_keys(missing)

    if missing:
        raise SystemExit(1)


def require_set_keys(
    config: dict[str, Any],
    section: str,
    set_name: str,
    required_keys: Iterable[RequiredKey],
) -> None:
    """Validate required keys for a named config set."""

    prefixed_keys = (
        required_key(
            required.key,
            label=required.label or f"{section}.{set_name}.{required.key}",
            allow_empty=required.allow_empty,
        )
        for required in required_keys
    )
    require_keys(config, prefixed_keys)


def require_list_item_keys(
    items: list[Any],
    item_label: str,
    required_keys: Iterable[RequiredKey],
) -> None:
    """Validate required keys for every table in a config list."""

    missing: list[str] = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            missing.append(f"{item_label}[{index}] must be a table")
            continue

        item_missing = missing_keys(
            item,
            (
                required_key(
                    required.key,
                    label=required.label or f"{item_label}[{index}].{required.key}",
                    allow_empty=required.allow_empty,
                )
                for required in required_keys
            ),
        )
        missing.extend(item_missing)

    report_missing_keys(missing)

    if missing:
        raise SystemExit(1)
