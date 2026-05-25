# 🪟 winutils_python

> Tiny Python helpers for configuration-driven Windows utilities.

**winutils_python** is a small helper package for building Windows automation scripts. It provides reusable Windows operations and generic YAML helpers, but it does not own any application configuration file.

## 🌱 Vision

In the future, winutils_python may help with:

- 💾 Robocopy-based file operations
- 🔌 SMB network share connections
- ⚙️ Generic YAML parsing helpers
- 🎨 Friendly terminal status output
- 🚀 Small reusable Windows automation helpers

## 🧩 Modules

- [`config.py`](config.py) provides YAML parsing, config file discovery, table validation, and typed config readers for strings, lists, extension sets, integer ranges, and optional positive numbers.
- [`config_sets.py`](config_sets.py) provides reusable helpers for selecting named configuration sets from CLI arguments or terminal menus.
- [`connect_smb.py`](connect_smb.py) connects configured SMB shares with `net use`, handles prompted password persistence, and supports set-level optional SMB scoping.
- [`file_ops.py`](file_ops.py) builds Robocopy commands and runs configured copy, move, and mirror operation sets.
- [`menu.py`](menu.py) provides terminal selection helpers for mapping keys by name or number.
- [`visual.py`](visual.py) provides colorful terminal output helpers with emoji-prefixed status messages.

## 📚 Inline documentation

The Python modules include concise module, class, and function docstrings for public helpers. These docstrings document intent and expected behavior without replacing the source code as the canonical API reference.

Useful entry points:

- `config.load()` loads an application-owned YAML config and stores the config path under an internal helper key.
- `config.required_list()` and related typed readers centralize common config validation.
- `config_sets.selected_set_name()` handles the common “CLI argument or interactive menu” selection flow.
- `connect_smb.connect_from_config()` connects top-level SMB mappings from a loaded config dictionary.
- `connect_smb.scoped_config_for_optional_smb()` removes SMB settings from a copied config when a selected operation set does not opt in to SMB.
- `file_ops.run_operation_set()` runs all configured Robocopy tasks in a named file operation set.

## ⚙️ Configuration

The package is designed to be used by application entry scripts, such as `connect_smb.pyw` and `file_operations.pyw` in Config Ops.

Important boundary: application scripts own their configuration files. Generic helpers can locate, load, and validate config data when called by an application, but the application decides when to create defaults or persist changes. If an application wants to persist a prompted SMB password, it provides a callback to `connect_smb.connect_from_config()` or uses the password persistence helpers explicitly.

In Config Ops, SMB credentials and mappings are defined at the top level of application config. File operation sets only opt in or out with a boolean `smb` value.

Example file operation set:

```yaml
file_operations:
  backup:
    smb: true
    robocopy:
      common_options: ['/MT:32', '/W:2', '/R:10', '/XJD', '/XJF', '/XJ', '/XC', '/ETA', '/TEE']
    mirror:
      - source: 'C:\path\to\source'
        target: 'R:\path\to\target'
    copy:
      overwrite: false
      options: ['/E', '/MT:16', '/W:2', '/R:5', '/XJD', '/XJF', '/XJ', '/XC', '/ETA', '/TEE']
      tasks:
        - source: 'C:\path\to\source'
          target: 'E:\path\to\target'
```

Example SMB configuration:

```yaml
smb:
  user: 'DOMAIN\user'
  mappings:
    - drive: 'R:'
      share: '\\server\share'
```

For local-only operation sets, application config can omit `smb` or set it to `false`. Set-specific SMB tables are intentionally not used in Config Ops.

## 🚧 Status

This package is early-stage and currently focused on the needs of Config Ops. APIs may still change while the tools are being shaped.
