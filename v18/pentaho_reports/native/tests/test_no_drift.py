"""Every vNN/pentaho_reports/native must be a byte-identical copy of engine/native.
Skips when not running inside the repo (e.g. a copied-out module)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()


def _repo_root():
    for parent in HERE.parents:
        if (parent / "tools" / "check_drift.py").exists() and (parent / "engine" / "native").is_dir():
            return parent
    return None


def test_native_copies_do_not_drift():
    repo = _repo_root()
    if repo is None:
        pytest.skip("not inside the pentaho_odoo_workbench repo")
    sys.path.insert(0, str(repo / "tools"))
    import check_drift  # noqa: E402
    assert check_drift.find_drift(repo) == []
