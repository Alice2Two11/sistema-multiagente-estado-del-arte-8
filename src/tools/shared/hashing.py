"""Contrato ÚNICO y compartido de hash estable (orden de claves fijo) de un
diccionario JSON-serializable.

Antes existían dos implementaciones idénticas en comportamiento pero
copiadas en vez de importadas: ``src/tools/extraction/stage_artifacts.py::
stable_hash_dict`` y ``src/adapters/evaluation_fingerprint.py::
stable_hash_dict`` (esta última con un comentario explícito admitiendo que
la función "se porta aquí" en vez de importarse). Ambas hacían
``json.dumps(..., sort_keys=True, default=str)`` seguido de
``sha256().hexdigest()``; se consolidan aquí para que un cambio futuro no
diverja entre las dos copias.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_hash_dict(data: Any) -> str:
    """Hash SHA-256 estable de un valor JSON-serializable (orden de claves
    fijo vía ``sort_keys=True``, valores no serializables convertidos con
    ``str`` vía ``default=str``)."""
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
