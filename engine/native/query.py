"""Turn a Pentaho ${param} SQL query into a psycopg2 query + parameter list."""
from __future__ import annotations

import re

_PLACEHOLDER = re.compile(r"\$\{(\w+)\}")


def prepare_sql(sql: str, parameters: dict) -> tuple[str, list]:
    """Replace every ${name} with %s placeholders (lists expand element-wise).

    Values are always passed as bind parameters, never interpolated. An empty
    list becomes the literal NULL so IN () stays valid SQL and matches nothing.
    Literal % characters (ILIKE patterns, TO_CHAR masks) are doubled so
    psycopg2 does not mistake them for placeholders.
    """
    params: list = []
    pieces: list[str] = []
    last = 0

    for match in _PLACEHOLDER.finditer(sql):
        pieces.append(sql[last:match.start()].replace("%", "%%"))
        last = match.end()
        name = match.group(1)
        if name not in parameters:
            raise KeyError(name)
        value = parameters[name]
        if isinstance(value, (list, tuple, set)):
            values = list(value)
            if not values:
                pieces.append("NULL")
                continue
            params.extend(values)
            pieces.append(",".join(["%s"] * len(values)))
        else:
            params.append(value)
            pieces.append("%s")

    pieces.append(sql[last:].replace("%", "%%"))
    return "".join(pieces), params
