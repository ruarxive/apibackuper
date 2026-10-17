"""Validate shipped configurations without contacting their API endpoints."""

import sys
from pathlib import Path

import yaml

from apibackuper.cmds.config_loader import validate_yaml_config


def main():
    root = Path(__file__).resolve().parents[1]
    examples = sorted(
        {
            *root.joinpath("examples").rglob("apibackuper.y*ml"),
            *root.joinpath("examples/templates").glob("*.yaml"),
        }
    )
    invalid = []
    for path in examples:
        valid, errors = validate_yaml_config(yaml.safe_load(path.read_text(encoding="utf8")))
        if not valid:
            invalid.append(path)
            for error in errors:
                print(f"{path.relative_to(root)}:{error['path']}: {error['message']}")
    print(f"Validated {len(examples)} example/template configurations; {len(invalid)} invalid")
    return int(bool(invalid))


if __name__ == "__main__":
    sys.exit(main())
