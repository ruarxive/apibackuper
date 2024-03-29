#!/usr/bin/env python
"""The main entry point. Invoke as `apibackuper' or `python -m apibackuper`.

"""
import sys


def main():
    """Main function"""
    try:
        from .core import cli

        exit_status = cli()
    except KeyboardInterrupt:
        print("Ctrl-C pressed. Aborting")
    sys.exit(0)


if __name__ == "__main__":
    main()
