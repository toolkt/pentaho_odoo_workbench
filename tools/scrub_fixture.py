#!/usr/bin/env python3
"""Copy a .prpt while scrubbing its embedded JDBC connection details.

Every sql-ds.xml part (root and nested sub-reports) gets:
  user -> demo, password -> "", url -> jdbc:postgresql://localhost/demo,
  ::pentaho-reporting::hostname -> localhost, ::pentaho-reporting::name /
  ::pentaho-reporting::database-name -> demo.
Optionally rewrites the first <data:static-query> (--query) and the first
<core:value> label in layout.xml (--label) — used to derive synthetic fixtures.
All other parts are copied byte-for-byte; `mimetype` stays first and STORED.
"""
import argparse
import re
import zipfile
from pathlib import Path

_REPLACEMENTS = [
    (re.compile(r'(<data:property name="user">)[^<]*(</data:property>)'), r"\1demo\2"),
    (re.compile(r'(<data:property name="password">)[^<]*(</data:property>)'), r"\1\2"),
    (re.compile(r"(<data:url>)[^<]*(</data:url>)"), r"\1jdbc:postgresql://localhost/demo\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::hostname">)[^<]*(</data:property>)'), r"\1localhost\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::name">)[^<]*(</data:property>)'), r"\1demo\2"),
    (re.compile(r'(<data:property name="::pentaho-reporting::database-name">)[^<]*(</data:property>)'), r"\1demo\2"),
]


def _scrub_sql_ds(xml: str, query: str = None) -> str:
    for pattern, repl in _REPLACEMENTS:
        xml = pattern.sub(repl, xml)
    if query is not None:
        xml = re.sub(r"(<data:static-query>)(.*?)(</data:static-query>)",
                     lambda m: m.group(1) + _xml_escape(query) + m.group(3), xml, count=1, flags=re.S)
    return xml


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def scrub(src: Path, dest: Path, query: str = None, label: str = None) -> None:
    with zipfile.ZipFile(str(src)) as zin:
        infos = zin.infolist()
        parts = [(info, zin.read(info.filename)) for info in infos]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(dest), "w") as zout:
        for info, data in parts:
            name = info.filename
            if name.endswith("sql-ds.xml"):
                # only the ROOT sql-ds.xml gets the query rewrite; nested ones are scrubbed only
                data = _scrub_sql_ds(data.decode("utf-8"), query if name == "datasources/sql-ds.xml" else None).encode("utf-8")
            elif name == "layout.xml" and label is not None:
                data = re.sub(r"(<core:value>)[^<]*(</core:value>)", r"\g<1>%s\g<2>" % _xml_escape(label),
                              data.decode("utf-8"), count=1).encode("utf-8")
            out = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            out.compress_type = zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED
            out.external_attr = info.external_attr
            zout.writestr(out, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("dest", type=Path)
    ap.add_argument("--query", help="replace the root static-query SQL")
    ap.add_argument("--label", help="replace the first <core:value> label in layout.xml")
    args = ap.parse_args()
    scrub(args.src, args.dest, query=args.query, label=args.label)
    print("wrote", args.dest)


if __name__ == "__main__":
    main()
