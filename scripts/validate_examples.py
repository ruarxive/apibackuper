"""Validate example files and Markdown YAML/JSON blocks without HTTP requests."""

import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from apibackuper.cmds.config_loader import load_schema, validate_yaml_config


def markdown_blocks(path):
    """Yield fenced language, metadata and body from a Markdown source file."""
    pattern = r"^```([\w+-]+)([^\n]*)\n(.*?)^```\s*$"
    for match in re.finditer(pattern, path.read_text(encoding="utf8"), re.MULTILINE | re.DOTALL):
        yield match.group(1), match.group(2).strip(), match.group(3)


def fragment_schema(value):
    """Allow omitted required fields in fragments while retaining field/type checks."""
    if isinstance(value, dict):
        return {key: fragment_schema(item) for key, item in value.items() if key != "required"}
    if isinstance(value, list):
        return [fragment_schema(item) for item in value]
    return value


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
    schema = load_schema()
    if schema is None:
        print("Cannot validate documentation: bundled schema is missing")
        return 1
    partial_validator = Draft7Validator(fragment_schema(schema))
    full_validator = Draft7Validator(schema)
    markdown = sorted(
        {
            root / "README.md",
            root / "SECURITY.md",
            root / "docs/README.md",
            root / "docs/GITHUB_PAGES_SETUP.md",
            root / ".github/workflows/README.md",
            *root.joinpath("docs/docs").rglob("*.md"),
            *root.joinpath("examples").rglob("*.md"),
        }
    )
    blocks = 0
    for path in markdown:
        for language, metadata, body in markdown_blocks(path):
            if language not in ("yaml", "yml", "json"):
                continue
            blocks += 1
            try:
                data = json.loads(body) if language == "json" else yaml.safe_load(body)
                if language in ("yaml", "yml"):
                    validator = (
                        full_validator
                        if "config" in metadata.split()
                        or isinstance(data, dict)
                        and set(schema["required"]).issubset(data)
                        else partial_validator
                    )
                    block_errors = list(validator.iter_errors(data))
                    if block_errors:
                        raise ValueError("; ".join(error.message for error in block_errors))
            except (ValueError, yaml.YAMLError) as error:
                invalid.append(path)
                print(f"{path.relative_to(root)}: {language} block: {error}")
    json_files = sorted(root.joinpath("examples").rglob("*.json"))
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf8"))
        except ValueError as error:
            invalid.append(path)
            print(f"{path.relative_to(root)}: {error}")
    print(
        f"Validated {len(examples)} configurations, {len(json_files)} JSON files and {blocks} Markdown blocks; {len(invalid)} invalid"
    )
    return int(bool(invalid))


if __name__ == "__main__":
    sys.exit(main())
