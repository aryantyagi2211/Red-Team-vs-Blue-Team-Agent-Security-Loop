import importlib

import pytest


@pytest.mark.parametrize("package", ["api", "attacks", "cli", "core", "targets"])
def test_project_packages_import(package: str) -> None:
    assert importlib.import_module(package)


def test_python_version_requirement() -> None:
    import sys

    assert sys.version_info >= (3, 11)
