#!/usr/bin/env python
"""The main entry point. Invoke as `apibackuper' or `python -m apibackuper`.

"""
import sys


def main() -> None:
    """Main function"""
    try:
        from .core import cli

        cli()
    except KeyboardInterrupt:
        print("Ctrl-C pressed. Aborting")
        sys.exit(1)


if __name__ == "__main__":
    main()
