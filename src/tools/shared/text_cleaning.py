"""Contrato ÚNICO y compartido de truncado/limpieza de un campo de la KB
para incluirlo en el contexto de un prompt de LLM.

Extraído de dos reimplementaciones con el mismo nombre y propósito pero
comportamiento realmente distinto:
``src/tools/thematic_analysis/context_builder.py::clean_value`` (no manejaba
``NaN``/listas/dicts, no colapsaba espacios repetidos) y
``src/tools/outline_generation/context_builder.py::clean_value`` (manejaba
``pd.isna``, serializaba listas/dicts con ``json.dumps``, colapsaba espacios
con regex). Se promueve aquí la versión más robusta -- superset estricto de
lo que hacía la simple -- con ``max_chars`` configurable por llamada, para
que cada etapa siga usando su propio límite (3500 en análisis temático, 1800
en generación de esquema) sin reimplementar la lógica.
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd


def clean_value(value: Any, max_chars: int = 1800) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]
