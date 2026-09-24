"""Robocopy command builders and config-driven file operation runners."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from winutils_python import visual

Operation = dict[str, Any]
FILE_OPERATIONS_SECTION = "file_operations"
OPERATION_TYPES = ("mirror", "copy", "move", "sync")
ROBOCOPY_FAILURE_EXIT_CODE = 8


@dataclass(frozen=True)
class OperationResult:
    """Result for one Robocopy-backed file operation."""

    op_type: str
    source: str
    target: str
    return_code: int

    @property
    def failed(self) -> bool:
        """Return whether Robocopy reported a failure exit code."""

        return self.return_code >= ROBOCOPY_FAILURE_EXIT_CODE


class FileOperationError(RuntimeError):
    """Raised after one or more Robocopy operations fail."""

    def __init__(self, results: list[OperationResult]) -> None:
        """Build a summary error from operation results."""

        self.results = results
        failed_results = [result for result in results if result.failed]
        summary = ", ".join(
            f"{result.op_type} {result.source} → {result.target}: exit code {result.return_code}"
            for result in failed_results
        )
        super().__init__(f"{len(failed_results)} Robocopy operation(s) failed: {summary}")


EXCLUDE_DIRS = (
    "cache",
    "shadercache",
    ".recycle",
    "$RECYCLE.BIN",
    "System Volume Information",
    "My Music",
    "My Videos",
    "My Pictures",
)

EXCLUDE_FILES = (
    "desktop.ini",
)

COMMON_OPTIONS = (
    "/MT:32",
    "/W:2",
    "/R:10",
    "/XJ",
    "/XC",
    "/NFL",
    "/NDL",
    "/NC",
    "/NS",
    "/NP",
)

MIRROR_OPTIONS = (
    "/MIR",
    *COMMON_OPTIONS,
)

MOVE_OPTIONS = (
    "/MOV",
    "/E",
    *COMMON_OPTIONS,
)

COPY_OPTIONS = (
    "/E",
    *COMMON_OPTIONS,
)

SYNC_OPTIONS = (
    "/E",
    "/XO",
    *(option for option in COMMON_OPTIONS if option.upper() != "/XC"),
)

SYNC_INCOMPATIBLE_OPTIONS = {"/MIR", "/PURGE", "/MOV", "/MOVE", "/XC", "/XN", "/XL"}

OPERATION_OPTIONS = {
    "mirror": MIRROR_OPTIONS,
    "move": MOVE_OPTIONS,
    "copy": COPY_OPTIONS,
    "sync": SYNC_OPTIONS,
}


def build_exclude_params(
    exclude_dirs: tuple[str, ...] = EXCLUDE_DIRS,
    exclude_files: tuple[str, ...] = EXCLUDE_FILES,
) -> list[str]:
    """Build Robocopy exclude parameters for directories and files."""

    params: list[str] = []

    for directory in exclude_dirs:
        params.extend(("/XD", directory))

    for file_name in exclude_files:
        params.extend(("/XF", file_name))

    return params


def string_tuple(value: Any, *, name: str) -> tuple[str, ...]:
    """Normalize a string-or-list config value into a tuple of strings."""

    if value is None:
        return ()

    if isinstance(value, str):
        return (value,)

    if isinstance(value, list):
        return tuple(str(item) for item in value)

    raise TypeError(f"Configuration value '{name}' must be a string or a list")


def operation_set_robocopy_options(operation_set: dict[str, Any], op_type: str) -> tuple[str, ...]:
    """Return default Robocopy options for an operation type within a set."""

    robocopy_config = operation_set.get("robocopy", {})

    if robocopy_config is None:
        robocopy_config = {}

    if not isinstance(robocopy_config, dict):
        raise TypeError("File operation set value 'robocopy' must be a table")

    operation_options = robocopy_config.get(f"{op_type}_options")
    if operation_options is not None:
        return string_tuple(operation_options, name=f"robocopy.{op_type}_options")

    common_options = robocopy_config.get("common_options")
    if common_options is not None:
        specific_defaults = operation_specific_default_options(op_type)
        return (*specific_defaults, *string_tuple(common_options, name="robocopy.common_options"))

    return OPERATION_OPTIONS[op_type]


def operation_specific_default_options(op_type: str) -> tuple[str, ...]:
    """Return default options unique to one Robocopy operation type."""

    return tuple(option for option in OPERATION_OPTIONS[op_type] if option not in COMMON_OPTIONS)


def operation_group_options(operation_group: Any, op_type: str, default_options: tuple[str, ...]) -> tuple[str, ...]:
    """Return operation-group-specific options or inherited defaults."""

    if isinstance(operation_group, dict) and "options" in operation_group:
        return string_tuple(operation_group["options"], name=f"{op_type}.options")

    return default_options


def invoke_robocopy(
    source_dir: str,
    dest_dir: str,
    options: tuple[str, ...],
    *,
    overwrite: bool = True,
    exclude_dirs: tuple[str, ...] = EXCLUDE_DIRS,
    exclude_files: tuple[str, ...] = EXCLUDE_FILES,
) -> int:
    """Run Robocopy for one source/target pair and return its exit code."""

    command = build_robocopy_command(
        source_dir,
        dest_dir,
        options,
        overwrite=overwrite,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
    )

    visual.print_blank()
    visual.print_info(f"Robocopy: {source_dir} → {dest_dir}", emoji="package")

    result = subprocess.run(command, check=False)
    print_robocopy_result(result.returncode)

    return result.returncode


def build_robocopy_command(
    source_dir: str,
    dest_dir: str,
    options: tuple[str, ...],
    *,
    overwrite: bool,
    exclude_dirs: tuple[str, ...],
    exclude_files: tuple[str, ...],
) -> list[str]:
    """Build the command-line argument list for a Robocopy invocation."""

    effective_options = options if overwrite else (*options, "/XN", "/XO", "/XX")
    return [
        "robocopy",
        source_dir,
        dest_dir,
        *effective_options,
        *build_exclude_params(exclude_dirs, exclude_files),
    ]


def print_robocopy_result(return_code: int) -> None:
    """Print a Robocopy success or failure message for an exit code."""

    if return_code < ROBOCOPY_FAILURE_EXIT_CODE:
        visual.print_success(f"Robocopy finished: exit code {return_code}")
    else:
        visual.print_error(f"Robocopy failed: exit code {return_code}")


def mirror(source: str, target: str, *, overwrite: bool = True, options: tuple[str, ...] = MIRROR_OPTIONS) -> int:
    """Mirror a source directory to a target directory with Robocopy."""

    return invoke_robocopy(source, target, options, overwrite=overwrite)


def move(source: str, target: str, *, overwrite: bool = True, options: tuple[str, ...] = MOVE_OPTIONS) -> int:
    """Move files from source to target with Robocopy."""

    return invoke_robocopy(source, target, options, overwrite=overwrite)


def copy(source: str, target: str, *, overwrite: bool = True, options: tuple[str, ...] = COPY_OPTIONS) -> int:
    """Copy files from source to target with Robocopy."""

    return invoke_robocopy(source, target, options, overwrite=overwrite)


def validate_sync_paths(source: str, target: str) -> None:
    """Reject sync folder pairs that could recursively copy into themselves."""

    source_path = Path(source).resolve(strict=False)
    target_path = Path(target).resolve(strict=False)

    for label, path in (("source", source_path), ("target", target_path)):
        if not path.exists():
            raise FileNotFoundError(f"Sync {label} folder does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Sync {label} is not a folder: {path}")

    if source_path == target_path:
        raise ValueError(f"Sync source and target must be different folders: {source}")

    if source_path in target_path.parents or target_path in source_path.parents:
        raise ValueError(f"Sync folders must not contain one another: {source} ↔ {target}")


def combined_sync_return_code(forward_code: int, reverse_code: int) -> int:
    """Return a representative code for two Robocopy sync passes."""

    if forward_code >= ROBOCOPY_FAILURE_EXIT_CODE:
        return forward_code

    if reverse_code >= ROBOCOPY_FAILURE_EXIT_CODE:
        return reverse_code

    return forward_code | reverse_code


def effective_sync_options(options: tuple[str, ...]) -> tuple[str, ...]:
    """Enforce non-destructive, newer-file-wins options for both sync passes."""

    filtered_options = tuple(option for option in options if option.upper() not in SYNC_INCOMPATIBLE_OPTIONS)
    normalized_options = {option.upper() for option in filtered_options}
    required_options = tuple(option for option in ("/E", "/XO") if option not in normalized_options)
    return (*required_options, *filtered_options)


def sync(source: str, target: str, *, options: tuple[str, ...] = SYNC_OPTIONS) -> int:
    """Synchronize two folders bidirectionally, keeping the newer file version."""

    validate_sync_paths(source, target)
    safe_options = effective_sync_options(options)
    forward_code = invoke_robocopy(source, target, safe_options)
    if forward_code >= ROBOCOPY_FAILURE_EXIT_CODE:
        return forward_code

    reverse_code = invoke_robocopy(target, source, safe_options)
    return combined_sync_return_code(forward_code, reverse_code)


def run_operation(
    op_type: str,
    operation: Operation,
    *,
    default_overwrite: bool = True,
    options: tuple[str, ...],
) -> OperationResult:
    """Run one configured file operation and return its result."""

    source = str(operation["source"])
    target = str(operation["target"])
    overwrite = bool(operation.get("overwrite", default_overwrite))

    if op_type == "mirror":
        return_code = mirror(source, target, overwrite=overwrite, options=options)
        return OperationResult(op_type, source, target, return_code)

    if op_type == "move":
        return_code = move(source, target, overwrite=overwrite, options=options)
        return OperationResult(op_type, source, target, return_code)

    if op_type == "copy":
        return_code = copy(source, target, overwrite=overwrite, options=options)
        return OperationResult(op_type, source, target, return_code)

    if op_type == "sync":
        return_code = sync(source, target, options=options)
        return OperationResult(op_type, source, target, return_code)

    raise ValueError(f"Unsupported file operation type: {op_type}")


def run_operations(
    op_type: str,
    operations: list[Operation],
    *,
    default_overwrite: bool = True,
    options: tuple[str, ...],
) -> list[OperationResult]:
    """Run multiple configured operations of the same type."""

    results: list[OperationResult] = []

    for operation in operations:
        results.append(
            run_operation(
                op_type,
                operation,
                default_overwrite=default_overwrite,
                options=options,
            )
        )

    return results


def summarize_operation_results(results: list[OperationResult]) -> None:
    """Print a compact summary of Robocopy operation results."""

    if not results:
        visual.print_info("No Robocopy operations configured", emoji="package")
        return

    failed_results = [result for result in results if result.failed]
    successful_count = len(results) - len(failed_results)

    visual.print_blank()
    visual.print_info(
        "Robocopy summary: "
        f"{successful_count} succeeded, {len(failed_results)} failed, {len(results)} total",
        emoji="list",
    )

    for result in failed_results:
        visual.print_error(
            f"Failed {result.op_type}: {result.source} → {result.target} (exit code {result.return_code})"
        )


def operation_group_tasks(operation_group: Any) -> list[Operation]:
    """Return tasks from a list group or a table containing a task list."""

    if isinstance(operation_group, list):
        return operation_group

    if isinstance(operation_group, dict):
        tasks = operation_group.get("tasks", [])
        if isinstance(tasks, list):
            return tasks

    raise TypeError("File operation group must be a list or a table with a 'tasks' list")


def operation_group_overwrite(operation_group: Any) -> bool:
    """Return the default overwrite setting for an operation group."""

    if isinstance(operation_group, dict):
        return bool(operation_group.get("overwrite", True))

    return True


def get_operation_set(config: dict[str, Any], set_name: str) -> dict[str, Any]:
    """Return one file operation set from loaded config."""

    operation_sets = config.get(FILE_OPERATIONS_SECTION, {})

    if not isinstance(operation_sets, dict):
        raise TypeError(f"Configuration value '{FILE_OPERATIONS_SECTION}' must be a table")

    operation_set = operation_sets.get(set_name, {})

    if not isinstance(operation_set, dict):
        raise TypeError(f"File operation set '{set_name}' must be a table")

    return operation_set


def run_operation_set(config: dict[str, Any], set_name: str) -> None:
    """Run all configured mirror, copy, move, and sync operations in a set."""

    operation_set = get_operation_set(config, set_name)

    visual.print_info(f"Running file operation set: {set_name}", emoji="package")
    results: list[OperationResult] = []

    for op_type in OPERATION_TYPES:
        operation_group = operation_set.get(op_type, [])
        operations = operation_group_tasks(operation_group)
        default_overwrite = operation_group_overwrite(operation_group)
        default_options = operation_set_robocopy_options(operation_set, op_type)
        options = operation_group_options(operation_group, op_type, default_options)
        results.extend(
            run_operations(
                op_type,
                operations,
                default_overwrite=default_overwrite,
                options=options,
            )
        )

    summarize_operation_results(results)

    if any(result.failed for result in results):
        raise FileOperationError(results)
