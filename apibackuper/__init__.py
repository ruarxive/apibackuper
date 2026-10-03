"""
apibackuper: a command-line tool and python library for API backuping

"""
try:
    # Source the version from the installed package metadata so the version
    # only needs to be bumped in one place — pyproject.toml. Falls back to a
    # hardcoded default for source-checkout use (where the package is not
    # installed and ``importlib.metadata`` cannot find it).
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    try:
        __version__ = _pkg_version("apibackuper")
    except PackageNotFoundError:
        __version__ = "1.0.15"
except ImportError:  # pragma: no cover - py<3.8 (project requires >=3.8)
    __version__ = "1.0.15"

__author__ = "Ivan Begtin"
__license__ = "MIT"
