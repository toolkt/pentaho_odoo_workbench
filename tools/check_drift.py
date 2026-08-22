#!/usr/bin/env python3
"""Fail if any vNN/pentaho_reports/native differs from engine/native
(or any vNN/.../tests/fixtures/partner_list.prpt differs from fixtures/).

Exit 0 = identical, 1 = drift (first differences printed).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERSIONS = list(range(11, 20))
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def _files(root: Path) -> dict:
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not (SKIP_PARTS & set(p.parts)) and p.suffix != ".pyc" and p.name != ".DS_Store":
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


def find_drift(repo: Path = REPO) -> list:
    engine = _files(repo / "engine" / "native")
    fixture = repo / "fixtures" / "partner_list.prpt"
    problems = []
    for n in VERSIONS:
        module = repo / ("v%d" % n) / "pentaho_reports"
        if not module.is_dir():
            continue
        copy_dir = module / "native"
        if not copy_dir.is_dir():
            problems.append("v%d: native/ missing" % n)
            continue
        copy = _files(copy_dir)
        for rel in sorted(set(engine) | set(copy)):
            if rel not in copy:
                problems.append("v%d: missing native/%s" % (n, rel))
            elif rel not in engine:
                problems.append("v%d: extra native/%s" % (n, rel))
            elif engine[rel] != copy[rel]:
                problems.append("v%d: differs native/%s" % (n, rel))
        if fixture.exists():
            dest = module / "tests" / "fixtures" / fixture.name
            if not dest.exists():
                problems.append("v%d: missing tests/fixtures/partner_list.prpt" % n)
            elif dest.read_bytes() != fixture.read_bytes():
                problems.append("v%d: differs tests/fixtures/partner_list.prpt" % n)
    return problems


if __name__ == "__main__":
    drift = find_drift()
    for line in drift:
        print(line)
    print("OK: all native copies identical to engine/native" if not drift else "DRIFT: %d problem(s)" % len(drift))
    sys.exit(1 if drift else 0)
