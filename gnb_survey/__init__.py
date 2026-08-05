"""gNB field survey toolkit."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gnb-field-survey")
except PackageNotFoundError:
    # Editable-installed dev checkouts always resolve above; this only
    # covers running straight out of a source tree with no install at all.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
