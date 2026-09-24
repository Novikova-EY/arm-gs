# -*- coding: utf-8 -*-
"""Очистка кэша агрегаций не должна падать на Windows-консоли (cp1251)."""

import ast
import io
from pathlib import Path
from unittest.mock import patch

_AGGREGATION_CACHE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "generation"
    / "services"
    / "station_services"
    / "aggregation_cache.py"
)


def _print_string_literals(src: str) -> list[str]:
    tree = ast.parse(src)
    literals: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "print"):
            continue
        for arg in node.args:
            for child in ast.walk(arg):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    literals.append(child.value)
    return literals


def test_aggregation_cache_print_literals_encode_to_cp1251():
    src = _AGGREGATION_CACHE_PATH.read_text(encoding="utf-8")
    for literal in _print_string_literals(src):
        literal.encode("cp1251")


def test_clear_aggregation_cache_prints_on_cp1251_stdout():
    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding="cp1251", errors="strict")

    with patch(
        "app.generation.services.station_services.aggregation_cache.get_redis_client",
        return_value=None,
    ), patch("sys.stdout", stream):
        from app.generation.services.station_services.aggregation_cache import (
            clear_aggregation_cache,
        )

        clear_aggregation_cache()

    stream.flush()
    output = buf.getvalue().decode("cp1251")
    assert "CACHE CLEARED" in output
