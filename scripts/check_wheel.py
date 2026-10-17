"""Check wheel contents and smoke-test an installed artifact outside the checkout."""

import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from zipfile import ZipFile


def main():
    wheel = Path(sys.argv[1]).resolve()
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        if any(name.startswith(("tests/", "docs/", "examples/")) for name in names):
            raise RuntimeError("Wheel contains development-only packages")
        if "apibackuper/schemas/config_schema.json" not in names:
            raise RuntimeError("Wheel is missing the configuration schema")
    with tempfile.TemporaryDirectory(prefix="apibackuper-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel)],
            cwd=root,
            check=True,
        )
        subprocess.run(
            [str(python), "-I", "-m", "apibackuper", "--help"],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "\n".join(
                    [
                        "from pathlib import Path",
                        "import sys, apibackuper",
                        "from apibackuper.cmds.config_loader import load_schema, validate_yaml_config",
                        "assert Path(apibackuper.__file__).is_relative_to(Path(sys.prefix))",
                        "assert load_schema()['title']",
                        "config = {'settings': {'name': 'smoke'}, 'project': {'url': 'https://example.test', 'http_mode': 'GET'}, 'params': {'page_size_limit': 1}, 'data': {}, 'storage': {'storage_type': 'zip'}}",
                        "assert validate_yaml_config(config)[0]",
                    ]
                ),
            ],
            cwd=root,
            check=True,
        )
    print("Installed-wheel CLI, bundled schema and package contents verified")


if __name__ == "__main__":
    main()
