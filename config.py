"""Shared helpers for locating, loading, and validating YAML config files."""

import sys
from math import isfinite
from pathlib import Path
from typing import Any

import yaml

BOOLEAN_VALUES = {"true": True, "false": False}
CONFIG_PATH_KEY = "__config_path__"


def parse_scalar(value: str) -> Any:
    """Parse a small YAML-like scalar used by lightweight config editors."""

    normalized_value = value.strip()

    if not normalized_value:
        return ""

    if normalized_value in BOOLEAN_VALUES:
        return BOOLEAN_VALUES[normalized_value]

    if is_single_quoted(normalized_value):
        return normalized_value[1:-1].replace("''", "'")

    if is_double_quoted(normalized_value):
        return normalized_value[1:-1]

    try:
        return int(normalized_value)
    except ValueError:
        return normalized_value


def is_single_quoted(value: str) -> bool:
    """Return whether a scalar is wrapped in single quotes."""

    return value.startswith("'") and value.endswith("'")


def is_double_quoted(value: str) -> bool:
    """Return whether a scalar is wrapped in double quotes."""

    return value.startswith('"') and value.endswith('"')


def parse_yaml(config_text: str) -> dict[str, Any]:
    """Parse YAML text into a dictionary, treating empty content as empty."""

    loaded = yaml.safe_load(config_text)
    if loaded is None:
        return {}

    if not isinstance(loaded, dict):
        raise TypeError("Configuration root must be a table")

    return loaded


def dump_yaml(config: dict[str, Any]) -> str:
    """Serialize config while omitting internal helper keys."""

    clean = {key: value for key, value in config.items() if not key.startswith("__")}
    return yaml.safe_dump(clean, sort_keys=False, allow_unicode=True)


def get_table(config: dict[str, Any], name: str) -> dict[str, Any]:
    """Return a top-level table from config or raise for invalid shape."""

    value = config.get(name, {})

    if not isinstance(value, dict):
        raise TypeError(f"Configuration value '{name}' must be a table")

    return value


def required_str(config: dict[str, Any], key: str, *, label: str) -> str:
    """Return a required non-empty string config value."""

    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

    return value.strip()


def optional_bool(config: dict[str, Any], key: str, *, label: str, default: bool) -> bool:
    """Return an optional strict boolean config value."""

    value = config.get(key, default)
    if not isinstance(value, bool):
        raise TypeError(f"Configuration value '{label}' must be true or false")

    return value


def required_list(
    config: dict[str, Any],
    key: str,
    *,
    label: str,
    non_empty: bool = False,
    empty_message: str | None = None,
) -> list[Any]:
    """Return a list config value, optionally requiring at least one item."""

    value = config.get(key, [])

    if not isinstance(value, list):
        raise TypeError(f"Configuration value '{label}' must be a list")

    if non_empty and not value:
        message = empty_message or f"Configuration value '{label}' must define at least one entry"
        raise ValueError(message)

    return value


def normalized_string_set(
    config: dict[str, Any],
    key: str,
    *,
    label: str,
    non_empty: bool = False,
    empty_list_message: str | None = None,
    empty_normalized_message: str | None = None,
) -> set[str]:
    """Return a normalized lowercase string set from a list config value."""

    values = required_list(
        config,
        key,
        label=label,
        non_empty=non_empty,
        empty_message=empty_list_message,
    )
    normalized_values = {str(value).strip().lower() for value in values if str(value).strip()}

    if not normalized_values:
        message = empty_normalized_message or f"Configuration value '{label}' must define at least one entry"
        raise ValueError(message)

    return normalized_values


def normalized_extension_set(
    config: dict[str, Any],
    key: str,
    *,
    label: str,
    non_empty: bool = False,
    empty_list_message: str | None = None,
) -> set[str]:
    """Return normalized lowercase file extensions from a list config value."""

    return normalized_string_set(
        config,
        key,
        label=label,
        non_empty=non_empty,
        empty_list_message=empty_list_message,
        empty_normalized_message=f"Configuration value '{label}' must define at least one extension",
    )


def required_int_in_range(
    config: dict[str, Any],
    key: str,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    """Return an integer config value within an inclusive range."""

    value = config.get(key)

    if isinstance(value, int) and not isinstance(value, bool):
        number = value
    elif isinstance(value, str) and value.isdigit():
        number = int(value)
    else:
        raise ValueError(f"{label} must be an integer")

    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be in range {minimum}..{maximum}")

    return number


def optional_positive_float(config: dict[str, Any], key: str, *, label: str) -> float | None:
    """Return an optional positive numeric config value."""

    value = config.get(key)

    if value is None:
        return None

    if isinstance(value, int | float) and not isinstance(value, bool):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a positive number") from error
    else:
        raise TypeError(f"{label} must be a positive number")

    if not isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be greater than 0")

    return number


def app_dir(script_file: str | Path) -> Path:
    """Return the script directory, or executable directory when frozen."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(script_file).resolve().parent


def script_dir(script_file: str | Path) -> Path:
    """Return the directory used for script-local runtime files."""

    return app_dir(script_file)


def config_path(script_file: str | Path, filename: str = "config.yaml") -> Path:
    """Return the config file path next to a script or frozen executable."""

    return script_dir(script_file) / filename


def find_config_path(script_file: str | Path, filename: str = "config.yaml") -> Path:
    """Return the config path, creating an empty file when missing."""

    path = config_path(script_file, filename)

    if not path.exists():
        path.write_text("", encoding="utf-8")

    return path


def load(script_file: str | Path, filename: str = "config.yaml") -> dict[str, Any]:
    """Load a YAML config and attach its path under an internal key."""

    path = find_config_path(script_file, filename)
    loaded_config = parse_yaml(path.read_text(encoding="utf-8"))
    loaded_config[CONFIG_PATH_KEY] = path
    return loaded_config


def append_section_yaml(config: dict[str, Any], section_yaml: str) -> None:
    """Append a default YAML section to the loaded config file."""

    path = config.get(CONFIG_PATH_KEY)

    if not isinstance(path, Path):
        return

    existing = path.read_text(encoding="utf-8").rstrip()
    separator = "\n\n" if existing else ""
    path.write_text(existing + separator + section_yaml.strip() + "\n", encoding="utf-8")
