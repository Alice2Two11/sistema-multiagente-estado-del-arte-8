"""Contrato ÚNICO y compartido de parseo de booleanos "sueltos" (strings
provenientes de CSV/JSON de notebooks anteriores: "true"/"1"/"yes"/"sí"/"si").

Extraído de 4 reimplementaciones independientes y equivalentes que existían
en el repo (misma cascada de valores truthy, sin reutilizarse entre sí):
``src/tools/extraction/stage_artifacts.py::_to_bool``,
``src/tools/extraction/chunk_validation.py::to_bool_series``,
``src/tools/quantitative_extraction/input_validation.py::to_bool`` y
``src/tools/thematic_analysis/corpus_filtering.py::_b``. Sin cambios de
comportamiento respecto a ninguna de las cuatro -- mismo conjunto de
valores truthy, sin distinguir mayúsculas/minúsculas.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

TRUTHY_STRING_VALUES = frozenset({"true", "1", "yes", "sí", "si"})


def to_bool(value: Any) -> bool:
    """Interpreta ``value`` como booleano: ``bool`` real se devuelve tal
    cual; cualquier otro valor se normaliza a texto (strip + casefold) y
    se compara contra :data:`TRUTHY_STRING_VALUES`."""
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in TRUTHY_STRING_VALUES


def to_bool_series(series: pd.Series) -> pd.Series:
    """Versión vectorizada de :func:`to_bool` para una columna completa de
    un ``DataFrame`` (NaN se trata como ``False`` antes de comparar)."""
    return (
        series.fillna(False)
        .astype(str)
        .str.strip()
        .str.casefold()
        .isin(TRUTHY_STRING_VALUES)
    )
