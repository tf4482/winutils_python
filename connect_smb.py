"""SMB share mapping helpers with config-driven password handling."""

import base64
import getpass
import hashlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from winutils_python import visual

DEFAULT_MAPPINGS: tuple[tuple[str, str], ...] = ()
DEFAULT_USER = ""
SMB_CONFIG_SECTION = "smb"
SMB_MAPPINGS_KEY = "mappings"
SMB_USER_KEY = "user"
SMB_ENCRYPTED_PASSWORD_KEY = "encrypted_password"
SMB_PASSWORD_FILE_KEY = "password_file"
SMB_PASSWORD_KEY = "password"
CONFIG_PATH_KEY = "__config_path__"
NET_USE_SUCCESS_EXIT_CODE = 0
NET_USE_ALREADY_ASSIGNED_EXIT_CODE = 2
NET_USE_SUCCESS_EXIT_CODES = (NET_USE_SUCCESS_EXIT_CODE,)
PASSWORD_KEY = (
    b"winutils_python_smb_password_key_v2__"
    b"2f4b64e8f52d49efb9ab6fdb79ce38a6__"
    b"0e1d7b2e4a1e4c6eb558ca69a822f43c__"
    b"9af7c446b6d44db3a8997ef1256ca7a0__"
    b"d538a23b6a3248dfb6bd71bb35c3904f__"
    b"compiled_scripts_can_embed_this_long_static_secret__"
    b"post_quantum_symmetric_security_relies_on_long_keys__"
    b"6e5f7d2b1a304b7f941c9b8b2c6d5e3a__"
    b"b7a5d6e4c2f14098a9b8c7d6e5f4a3b2__"
    b"f1e2d3c4b5a697887766554433221100__"
    b"00112233445566778899aabbccddeeff__"
    b"ffeeddccbbaa99887766554433221100__"
    b"5c4d3e2f1a0b9c8d7e6f504132231405"
)
PASSWORD_PREFIX = "wp1:"
CREATE_NO_WINDOW = 0x08000000


def subprocess_creationflags() -> int:
    """Return subprocess flags that hide child console windows on Windows."""

    if sys.platform == "win32":
        return CREATE_NO_WINDOW

    return 0


def is_successful_net_use_return_code(return_code: int) -> bool:
    """Return whether a ``net use`` return code is considered successful."""

    return return_code in NET_USE_SUCCESS_EXIT_CODES


@dataclass(frozen=True)
class SmbMappingResult:
    """Result for one attempted SMB drive mapping."""

    drive: str
    share: str
    return_code: int

    @property
    def failed(self) -> bool:
        """Return whether the SMB mapping failed."""

        return not is_successful_net_use_return_code(self.return_code)


class SmbConnectionError(RuntimeError):
    """Raised after one or more SMB mappings fail."""

    def __init__(self, results: list[SmbMappingResult]) -> None:
        """Build a summary error from mapping results."""

        self.results = results
        failed_results = [result for result in results if result.failed]
        summary = ", ".join(
            f"{result.drive} → {result.share}: exit code {result.return_code}"
            for result in failed_results
        )
        super().__init__(f"{len(failed_results)} SMB mapping(s) failed: {summary}")


def password_key_stream(length: int) -> bytes:
    """Return a deterministic key stream for lightweight password obfuscation."""

    stream = b""
    counter = 0

    while len(stream) < length:
        stream += hashlib.sha256(PASSWORD_KEY + counter.to_bytes(4, byteorder="little")).digest()
        counter += 1

    return stream[:length]


def encrypt_password(password: str) -> str:
    """Obfuscate an SMB password for storage in config files."""

    password_bytes = password.encode("utf-8")
    key_stream = password_key_stream(len(password_bytes))
    encrypted = xor_bytes(password_bytes, key_stream)
    return PASSWORD_PREFIX + base64.urlsafe_b64encode(encrypted).decode("ascii")


def decrypt_password(encrypted_password: str) -> str:
    """Decode an SMB password stored by :func:`encrypt_password`."""

    if not encrypted_password.startswith(PASSWORD_PREFIX):
        raise ValueError("Unsupported encrypted SMB password format")

    encrypted = base64.urlsafe_b64decode(encrypted_password.removeprefix(PASSWORD_PREFIX).encode("ascii"))
    key_stream = password_key_stream(len(encrypted))
    decrypted = xor_bytes(encrypted, key_stream)
    return decrypted.decode("utf-8")


def xor_bytes(data: bytes, key_stream: bytes) -> bytes:
    """XOR two byte strings of equal length."""

    return bytes(data_byte ^ key_byte for data_byte, key_byte in zip(data, key_stream, strict=True))


def parse_yaml(config_text: str) -> dict:
    """Parse YAML text into a dictionary, treating empty content as empty."""

    return yaml.safe_load(config_text) or {}


def dump_yaml(config: dict) -> str:
    """Serialize config while omitting internal helper keys."""

    clean = {key: value for key, value in config.items() if not str(key).startswith("__")}
    return yaml.safe_dump(clean, sort_keys=False, allow_unicode=True)


def replace_or_add_string_value(config_path: Path, table: str, key: str, value: str) -> None:
    """Replace or add a string value inside a YAML config table."""

    loaded_config = parse_yaml(config_path.read_text(encoding="utf-8"))
    table_config = loaded_config.setdefault(table, {})

    if not isinstance(table_config, dict):
        raise TypeError(f"Configuration value '{table}' must be a table")

    table_config[key] = value
    config_path.write_text(dump_yaml(loaded_config), encoding="utf-8")


def remove_value(config_path: Path, table: str, key: str) -> None:
    """Remove a key from a YAML config table when present."""

    loaded_config = parse_yaml(config_path.read_text(encoding="utf-8"))
    table_config = loaded_config.get(table, {})

    if isinstance(table_config, dict) and key in table_config:
        del table_config[key]
        config_path.write_text(dump_yaml(loaded_config), encoding="utf-8")


def store_prompted_password(config: dict, password: str, *, table: str = SMB_CONFIG_SECTION) -> None:
    """Persist a prompted SMB password and remove plaintext password keys."""

    config_path = config.get(CONFIG_PATH_KEY)

    if not isinstance(config_path, Path):
        raise TypeError(f"Loaded configuration is missing internal '{CONFIG_PATH_KEY}'")

    replace_or_add_string_value(config_path, table, SMB_ENCRYPTED_PASSWORD_KEY, encrypt_password(password))
    remove_value(config_path, table, SMB_PASSWORD_FILE_KEY)
    remove_value(config_path, table, SMB_PASSWORD_KEY)


def optional_smb_enabled(config: dict, *, error_label: str) -> bool:
    """Return whether a set-level optional SMB flag is enabled."""

    enabled = config.get(SMB_CONFIG_SECTION, False)

    if not isinstance(enabled, bool):
        raise TypeError(f"{error_label} must be true or false")

    return enabled


def scoped_config_for_optional_smb(config: dict, set_config: dict, *, error_label: str) -> dict:
    """Return full config when set-level SMB is enabled, otherwise without SMB."""

    scoped_config = dict(config)

    if optional_smb_enabled(set_config, error_label=error_label):
        return scoped_config

    scoped_config.pop(SMB_CONFIG_SECTION, None)
    return scoped_config


def store_prompted_password_if_enabled(
    config: dict,
    set_config: dict,
    password: str,
    *,
    error_label: str,
    table: str = SMB_CONFIG_SECTION,
) -> None:
    """Persist a prompted SMB password only when set-level SMB is enabled."""

    if optional_smb_enabled(set_config, error_label=error_label):
        store_prompted_password(config, password, table=table)


def prompt_password_window() -> str:
    """Placeholder for GUI password prompts."""

    raise NotImplementedError("GUI password prompts are not supported; use terminal input")


def prompt_password() -> str:
    """Prompt for an SMB password in the terminal without echoing input."""

    if sys.stdin is None or not sys.stdin.isatty():
        raise RuntimeError(
            "SMB password is unavailable in non-interactive mode. "
            "Run once interactively to store it before unattended execution."
        )

    return getpass.getpass("SMB password: ")


def test_password(password: str, smb_config: dict) -> bool:
    """Test an SMB password against the first configured mapping."""

    mappings = mappings_from_config(smb_config)
    user = user_from_config(smb_config)

    for drive, share in mappings[:1]:
        return run_net_use(drive, share, password, user=user, quiet=True) == 0

    return False


def resolve_password_from_config(smb_config: dict) -> tuple[str, bool]:
    """Return an SMB password and whether it was prompted interactively."""

    encrypted_password = smb_config.get(SMB_ENCRYPTED_PASSWORD_KEY)

    if isinstance(encrypted_password, str):
        try:
            return decrypt_password(encrypted_password), False
        except (ValueError, UnicodeError) as error:
            visual.print_warning(f"Stored SMB password could not be used: {error}")

    return prompt_password(), True


def get_password_from_config(
    smb_config: dict,
    *,
    on_password_prompted: Callable[[str], None] | None = None,
) -> str:
    """Return the configured SMB password, prompting when none can be used."""

    password, prompted = resolve_password_from_config(smb_config)
    if prompted and on_password_prompted is not None:
        on_password_prompted(password)
    return password


def mappings_from_config(smb_config: dict) -> tuple[tuple[str, str], ...]:
    """Return configured SMB drive/share mapping pairs."""

    mappings = smb_config.get(SMB_MAPPINGS_KEY)

    if not isinstance(mappings, list):
        raise TypeError(f"SMB configuration must define a '{SMB_MAPPINGS_KEY}' list")

    normalized_mappings: list[tuple[str, str]] = []
    for index, mapping in enumerate(mappings, start=1):
        if not isinstance(mapping, dict):
            raise TypeError(f"SMB mapping {index} must be a table")

        drive = str(mapping.get("drive", "")).strip()
        share = str(mapping.get("share", "")).strip()
        if not drive or not share:
            raise ValueError(f"SMB mapping {index} must define non-empty 'drive' and 'share' values")

        normalized_mappings.append((drive, share))

    return tuple(normalized_mappings)


def user_from_config(smb_config: dict) -> str:
    """Return the configured SMB user or raise when it is missing."""

    user = str(smb_config.get(SMB_USER_KEY, DEFAULT_USER)).strip()

    if not user:
        raise ValueError(
            "SMB configuration must define a non-empty 'user'. "
            f"Set '{SMB_CONFIG_SECTION}.{SMB_USER_KEY}', for example "
            "'DOMAIN\\user', 'SERVER\\user' or '.\\local_user'."
        )

    return user


def has_smb_config(config: dict) -> bool:
    """Return whether config contains usable top-level SMB mappings."""

    smb_config = config.get(SMB_CONFIG_SECTION)

    if smb_config is None:
        return False

    if not isinstance(smb_config, dict):
        raise TypeError(f"Configuration value '{SMB_CONFIG_SECTION}' must be a table")

    mappings = smb_config.get(SMB_MAPPINGS_KEY)
    if mappings is None:
        return False
    if not isinstance(mappings, list):
        raise TypeError(f"SMB configuration value '{SMB_MAPPINGS_KEY}' must be a list")

    return bool(mappings)


def normalize_unc_path(path: str) -> str:
    """Normalize a UNC path for case-insensitive comparison."""

    return path.rstrip("\\/").casefold()


def existing_drive_mapping(drive: str) -> str | None:
    """Return the UNC share currently mapped to a drive, if available."""

    result = subprocess.run(
        ["net", "use", drive],
        check=False,
        capture_output=True,
        text=True,
        encoding="oem",
        errors="replace",
        creationflags=subprocess_creationflags(),
    )

    if result.returncode != NET_USE_SUCCESS_EXIT_CODE:
        return None

    output = f"{result.stdout}\n{result.stderr}"
    for line in output.splitlines():
        parts = line.split()
        for part in parts:
            if part.startswith("\\\\"):
                return part

    return None


def run_net_use(
    drive: str,
    share: str,
    password: str,
    *,
    user: str = DEFAULT_USER,
    quiet: bool = True,
) -> int:
    """Run ``net use`` for one drive/share mapping and return its exit code."""

    stdout = subprocess.DEVNULL if quiet else None
    stderr = subprocess.DEVNULL if quiet else None

    result = subprocess.run(
        [
            "net",
            "use",
            drive,
            share,
            password,
            f"/USER:{user}",
            "/Y",
            "/persistent:yes",
        ],
        check=False,
        stdout=stdout,
        stderr=stderr,
        creationflags=subprocess_creationflags(),
    )

    if result.returncode != NET_USE_ALREADY_ASSIGNED_EXIT_CODE:
        return result.returncode

    existing_share = existing_drive_mapping(drive)
    if existing_share is None:
        return NET_USE_ALREADY_ASSIGNED_EXIT_CODE

    if normalize_unc_path(existing_share) == normalize_unc_path(share):
        return NET_USE_SUCCESS_EXIT_CODE

    return result.returncode


def connect_smb_shares(
    password: str,
    mappings: tuple[tuple[str, str], ...] = DEFAULT_MAPPINGS,
    *,
    user: str = DEFAULT_USER,
    quiet: bool | None = None,
) -> list[SmbMappingResult]:
    """Connect SMB shares and raise when any mapping fails."""

    if quiet is None:
        quiet = True

    if not mappings:
        if not quiet:
            visual.print_info("No SMB mappings configured; skipping SMB connection", emoji="connect")
        return []

    if not quiet:
        visual.print_info("Connecting SMB shares", emoji="start")

    results: list[SmbMappingResult] = []

    for drive, share in mappings:
        if not quiet:
            visual.print_info(f"Mapping {drive} → {share}", emoji="connect")

        return_code = run_net_use(drive, share, password, user=user, quiet=quiet)
        results.append(SmbMappingResult(drive, share, return_code))

        if not quiet:
            print_mapping_result(drive, return_code)

    if not quiet:
        visual.print_done("SMB share connection finished")

    failed_results = [result for result in results if result.failed]
    if failed_results:
        raise SmbConnectionError(results)

    return results


def print_mapping_result(drive: str, return_code: int) -> None:
    """Print a human-readable status for one SMB mapping result."""

    if return_code == NET_USE_SUCCESS_EXIT_CODE:
        visual.print_success(f"Mapping {drive}: OK")
        return

    if return_code == NET_USE_ALREADY_ASSIGNED_EXIT_CODE:
        visual.print_warning(f"Mapping {drive}: already in use by a different share")
        return

    visual.print_warning(f"Mapping {drive}: exit code {return_code}")


def get_table(config: dict, name: str) -> dict:
    """Return a top-level config table or raise when shape is invalid."""

    value = config.get(name, {})

    if not isinstance(value, dict):
        raise TypeError(f"Configuration value '{name}' must be a table")

    return value


def connect_from_config(
    config: dict,
    *,
    on_password_prompted: Callable[[str], None] | None = None,
) -> list[SmbMappingResult]:
    """Connect SMB shares from a loaded top-level config dictionary."""

    if not has_smb_config(config):
        visual.print_info("No SMB mappings configured; skipping SMB connection", emoji="connect")
        return []

    smb_config = get_table(config, SMB_CONFIG_SECTION)
    password, prompted = resolve_password_from_config(smb_config)
    mappings = mappings_from_config(smb_config)
    user = user_from_config(smb_config)
    results = connect_smb_shares(password, mappings, user=user, quiet=True)

    if prompted and on_password_prompted is not None:
        on_password_prompted(password)

    return results


def main() -> None:
    """Prompt for a password and connect default mappings when run directly."""

    password = prompt_password()
    connect_smb_shares(password, quiet=None)


if __name__ == "__main__":
    main()
