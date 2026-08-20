# apibackuper

> A command-line tool to archive and backup REST APIs

**Version:** 1.0.13

**apibackuper** downloads paginated REST APIs into local storage and exports
the archive as JSON Lines, gzip, zstd, or Parquet. It is designed for
repeatable, long-running backups rather than one-off HTTP requests.

## Features

- GET and POST iterative APIs (page, skip/offset, or range pagination)
- Full, incremental, and update work modes, with resume from checkpoints
- ZIP, filesystem, or SQLite storage
- Export to JSON Lines, gzip, Zstandard, or Parquet
- YAML configuration (INI still loaded, but deprecated)
- Authentication: Basic, Bearer, API Key, OAuth2
- Rate limiting, retries, concurrency, and SSL controls
- Follow-up requests for related objects and associated file downloads
- Optional Python hooks for custom pipeline steps

## Documentation

The full documentation site (Docusaurus) lives in [`docs/`](docs/) and is
published at **[ruarxive.org/apibackuper](https://ruarxive.org/apibackuper/)**.

| Section | What it covers |
|---------|----------------|
| [Getting started](https://ruarxive.org/apibackuper/getting-started/installation) | Install, quick start, positioning |
| [Cookbook](https://ruarxive.org/apibackuper/getting-started/cookbook) | Task index by goal |
| [CLI reference](https://ruarxive.org/apibackuper/commands/) | Every command |
| [Configuration](https://ruarxive.org/apibackuper/configuration/) | YAML sections and field reference |
| [Examples](https://ruarxive.org/apibackuper/examples/) | Working projects and templates |
| [Troubleshooting](https://ruarxive.org/apibackuper/getting-started/troubleshooting) | SSL, pagination, rate limits |

Source pages: [`docs/docs/`](docs/docs/). Changelog: [`CHANGELOG.md`](CHANGELOG.md).

## Installation

### Using pip

```bash
pip install --upgrade pip setuptools
pip install apibackuper
```

### Using pipx or uv

```bash
pipx install apibackuper
# or
uv tool install apibackuper
```

Parquet export and aria2 downloads:

```bash
pip install "apibackuper[recommended]"
```

### Requirements

- Python 3.8 or greater

### Install from source

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install .
```

## Quick start

```bash
apibackuper create etrust
cd etrust
# edit apibackuper.yaml (and params.json for POST APIs)
apibackuper estimate full
apibackuper run full
apibackuper export etrust.jsonl
```

A worked POST API example is in the
[quick start](https://ruarxive.org/apibackuper/getting-started/quick-start).
Starter YAML files are in `examples/templates/`.

## Commands

```bash
apibackuper create <name>
apibackuper detect [--url URL] [--write-config]
apibackuper estimate full
apibackuper run full [--resume]
apibackuper update [--resume]
apibackuper follow full|continue
apibackuper getfiles
apibackuper export output.jsonl
apibackuper info [--json]
apibackuper validate-config
```

```bash
apibackuper --help
apibackuper run --help
```

## Contributing

See the [development docs](https://ruarxive.org/apibackuper/development/contributing).

## License

MIT License — see [LICENSE](LICENSE).

## Links

- [Documentation](https://ruarxive.org/apibackuper/)
- [GitHub](https://github.com/datacoon/apibackuper)
- [PyPI](https://pypi.org/project/apibackuper/)
- [Changelog](CHANGELOG.md)
- [Issue tracker](https://github.com/datacoon/apibackuper/issues)
