---
title: "Installation"
description: "Install apibackuper with pip, pipx, or from source"
---
# Installation

### Using pip

```bash
pip install --upgrade pip setuptools
pip install apibackuper
```

### Using pipx or uv (recommended for CLI use)

```bash
pipx install apibackuper
# or
uv tool install apibackuper
```

After installation the `apibackuper` command is available:

```bash
apibackuper --help
```

### Optional extras

Parquet export and accelerated file downloads are optional:

| Extra | Enables |
|-------|---------|
| `recommended` | `pandas` and `pyarrow` for Parquet export, plus `aria2p` for file downloads |

```bash
pip install "apibackuper[recommended]"
```

You can also install the pieces separately:

```bash
pip install pandas pyarrow   # Parquet export
pip install aria2p           # aria2-backed file downloads
```

### Requirements

- Python 3.8 or greater
- Linux, macOS, or Windows

### Install from source

```bash
git clone https://github.com/datacoon/apibackuper.git
cd apibackuper
python -m pip install --upgrade pip setuptools wheel
python -m pip install .
```

For development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Next steps

- [Quick start](/getting-started/quick-start)
- [When to use apibackuper](/getting-started/when-to-use)
- [Configuration](/configuration/)
