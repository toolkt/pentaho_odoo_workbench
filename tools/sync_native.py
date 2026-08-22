#!/usr/bin/env python3
"""Copy the canonical engine (engine/native) into every vNN/pentaho_reports/native.

Also copies fixtures/partner_list.prpt into vNN/pentaho_reports/tests/fixtures/.
Idempotent. Run from anywhere; paths are resolved relative to this file.
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "engine" / "native"
FIXTURE = REPO / "fixtures" / "partner_list.prpt"
VERSIONS = list(range(11, 20))
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store")


def sync(repo: Path = REPO) -> list:
    synced = []
    for n in VERSIONS:
        module = repo / ("v%d" % n) / "pentaho_reports"
        if not module.is_dir():
            continue
        target = module / "native"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(ENGINE, target, ignore=IGNORE)
        if FIXTURE.exists():
            dest = module / "tests" / "fixtures" / FIXTURE.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(FIXTURE, dest)
        synced.append(str(target.relative_to(repo)))
    return synced


if __name__ == "__main__":
    for t in sync():
        print("synced", t)
    sys.exit(0)
