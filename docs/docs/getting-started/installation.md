---
title: "Installation"
description: "Choose an isolated installation, verify the Python environment and add optional export or development dependencies"
---
# Installation

Install apibackuper in an isolated Python environment, verify that the CLI uses
that environment, then run the [local quick start](/getting-started/quick-start).
The base package includes backup, update, follow, built-in file downloads and
JSONL/gzip/zstd export. Add optional dependencies only for the features you need.

## Requirements and installation choices

The current source requires **Python 3.10 or newer**. Check the interpreter you
intend to use:

```bash
python --version
python -m pip --version
```

Use `python3` if that is the name of your Python 3 installation. On Windows,
`py -3 --version` can identify the selected Python 3 interpreter. Python 3.8/3.9
cannot run the current 2.x source; select a newer interpreter before creating
the environment. Repository CI covers Python 3.10–3.13 on Ubuntu and macOS;
the Windows commands below use PowerShell.

| Goal | Installation path |
|------|-------------------|
| Run backups and use the Python API | Virtual environment with pip |
| Try the bundled local API and examples | Repository checkout plus virtual environment |
| Keep a CLI managed by an existing tool manager | pipx or uv tool installation |
| Change code or run development checks | Editable source install with the `dev` extra |

A package installation does not provide a repository checkout containing
`examples/local-demo/server.py`. Choose the source path for the Quick Start.
Node.js/npm are needed to build the documentation site, not to run backups.

## Install with pip in a virtual environment

On Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install apibackuper
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install apibackuper
```

Run the commands in a working directory you can write to. Activation selects
that environment's interpreter and scripts for the current terminal; activate
it again in each new terminal. If activation is unavailable, invoke the
interpreter directly, such as `.venv/bin/python` on Linux/macOS or
`.venv\Scripts\python.exe` on Windows.

Using `python -m pip` ties installation to the interpreter used by
`python -m apibackuper`. It avoids accidentally installing into another Python
when several versions are available.

## Verify the installation

```bash
python -m apibackuper --help
apibackuper --help
python -m pip show apibackuper
python -m pip check
```

Help should list commands including `create`, `run`, `update`, `export` and
`validate-config`. These checks do not contact an API. `pip show` reports the
installed distribution version and location; there is no need for a CLI
`--version` flag.

If module invocation works but `apibackuper` is not found, the environment's
scripts directory is absent from your terminal's PATH. Reactivate the environment
or continue with `python -m apibackuper` as the equivalent command prefix.

To inspect the exact interpreter and imported package, save and run:

```python
import sys
from importlib.metadata import version
import apibackuper

print("Python:", sys.executable)
print("Package:", apibackuper.__file__)
print("Version:", version("apibackuper"))
```

## Install the repository and examples

For the documented local walkthrough and the current source:

```bash
git clone https://github.com/ruarxive/apibackuper.git
cd apibackuper
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

On PowerShell, use the environment creation/activation commands above, then
`python -m pip install -e .` from the checkout. An editable install imports
code from that checkout. Moving/deleting it breaks that link; dependency changes
still require another install. For a regular source install, use
`python -m pip install .` instead.

The documentation describes this checkout. If a separately installed release
has different flags or schema fields, inspect its command help or install the
matching source revision before following a source-only example.

## Optional dependencies

| Requirement | Install | What it adds |
|-------------|---------|--------------|
| JSONL, gzip, zstd and built-in downloads | Base package | No export/download extra required |
| Parquet export | `apibackuper[recommended]` | Includes pyarrow and pandas |
| External aria2 integration | Same extra, or `aria2p` separately | Python RPC client, not the aria2 service |
| Repository development | Editable `.[dev]` | Tests, linters, type checks and pre-commit |

For an existing package environment:

```bash
python -m pip install 'apibackuper[recommended]'
```

From a checkout, keep the editable source and add the extra with:

```bash
python -m pip install -e '.[recommended]'
```

Installing `aria2p` does not start a downloader. The integration needs a running
RPC service and has different credential/quota behavior from built-in downloads;
see [files](/configuration/files#aria2-integration).

For development, from the repository root:

```bash
python -m pip install -e '.[dev]'
```

Development dependencies are unnecessary for ordinary backups. See
[contributing](/development/contributing) for repository checks.

## Use an existing CLI tool manager

If pipx or uv is already your preferred CLI manager, choose one:

```bash
pipx install apibackuper
```

```bash
uv tool install apibackuper
```

Those tools maintain their own environments. Installing pyarrow with an unrelated
`python -m pip` does not add it to a tool-managed CLI. To include optional
features at installation, use the same package specification, for example
`pipx install 'apibackuper[recommended]'`. For the Python API, use a package
installed in the environment of your importing script.

## Upgrade without losing the project definition

In a pip-managed environment:

```bash
python -m pip install --upgrade apibackuper
python -m pip check
```

For repeatable jobs, record the version with `pip show` and retain your tested
dependency set. Upgrade the same environment that launches the command. Before
changing versions, preserve the project configuration, archive and successful
state, finish interrupted runs, then rerun the local walkthrough and validate
your real projects. Installing a new package does not validate existing API
contracts or migrate storage.

| Installation problem | Check |
|----------------------|-------|
| Python version rejected | Create the environment with Python 3.10+ rather than reusing an older one |
| Command not found | Activate the correct environment or use module invocation |
| `No module named apibackuper` | Install with that interpreter's `python -m pip` |
| Parquet dependency missing | Add the extra to the environment actually running the CLI |
| Package build fails | Interpreter/platform support and the first dependency error in pip output |
| `examples/` is missing | Clone the repository; it is not created by a package install |

Continue with the [Quick Start](/getting-started/quick-start), or use
[When to use](/getting-started/when-to-use) to assess an existing API.
