"""${param} → psycopg2 substitution. Never string-interpolate values."""
import pytest

from native.query import prepare_sql


def test_ids_list_expands_to_placeholders():
    sql, params = prepare_sql("SELECT 1 WHERE sp.id IN (${ids}) AND q > 0", {"ids": [2, 3]})
    assert sql == "SELECT 1 WHERE sp.id IN (%s,%s) AND q > 0"
    assert params == [2, 3]


def test_single_int_id():
    sql, params = prepare_sql("WHERE am.id IN (${ids})", {"ids": 42})
    assert sql == "WHERE am.id IN (%s)"
    assert params == [42]


def test_scalar_parameter():
    sql, params = prepare_sql("WHERE x = ${foo}", {"foo": "bar"})
    assert sql == "WHERE x = %s"
    assert params == ["bar"]


def test_empty_ids_yields_null():
    # empty selection must produce zero rows, not a SQL syntax error
    sql, params = prepare_sql("WHERE sp.id IN (${ids})", {"ids": []})
    assert sql == "WHERE sp.id IN (NULL)"
    assert params == []


def test_missing_parameter_raises():
    with pytest.raises(KeyError):
        prepare_sql("WHERE x = ${nope}", {})


def test_literal_percent_is_escaped_for_psycopg2():
    sql, params = prepare_sql(
        "WHERE name ILIKE '%Withholding%' AND id IN (${ids})", {"ids": [1]}
    )
    assert sql == "WHERE name ILIKE '%%Withholding%%' AND id IN (%s)"
    assert params == [1]


def test_repeated_placeholder():
    sql, params = prepare_sql("WHERE a IN (${ids}) OR b IN (${ids})", {"ids": [7]})
    assert sql == "WHERE a IN (%s) OR b IN (%s)"
    assert params == [7, 7]
