"""Persistencia por rondas del ciclo correctivo `06 <-> 07`
(``writer_verifier_cycle/round_NN/``).

Ciclo de vida transaccional de UNA ronda, en dos fases explícitas que NO
se pisan entre sí:

- **Fase 07** (``create_round_awaiting_revision``): crea la ronda de
  forma atómica (staging + rename del directorio completo) con los
  artefactos de 07 (borrador de entrada, resultado de 07,
  ``writer_revision_request.json``, transición, fingerprints). Estado
  final: ``AWAITING_REVISION``.
- **Fase 06** (``complete_round_revision``): COMPLETA esa misma ronda ya
  creada -- nunca la vuelve a crear. Valida que la ronda exista, que
  pertenezca al mismo experimento/ciclo/número de ronda, y que el hash del
  ``writer_revision_request`` coincida exactamente con el que 07 dejó al
  crearla. Escribe los artefactos de 06 en un staging interno a la ronda,
  los mueve uno por uno (rename atómico por archivo) y actualiza el
  archivo de estado AL FINAL (también vía staging + rename atómico de ese
  archivo puntual). Estado final: ``REVISION_COMPLETED``. Un segundo
  intento de completar la misma ronda falla explícitamente.

Ninguna excepción se silencia en ningún punto: ``FileExistsError`` por
sobrescritura, ``RuntimeError`` por inconsistencia (experimento/ronda/hash
distintos, ronda ya completada), o cualquier error de escritura/
serialización se propaga tal cual.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

CYCLE_DIRECTORY_NAME = "writer_verifier_cycle"
ROUND_STATUS_FILENAME = "_round_status.json"

STATUS_AWAITING_REVISION = "AWAITING_REVISION"
STATUS_REVISION_COMPLETED = "REVISION_COMPLETED"
STATUS_REVERIFIED = "REVERIFIED"


def round_directory(project_dir: str | Path, experiment_id: str, round_number: int) -> Path:
    return (
        Path(project_dir)
        / experiment_id
        / "05_outputs"
        / CYCLE_DIRECTORY_NAME
        / f"round_{round_number:02d}"
    )


def _serialize(content: Any) -> str:
    if isinstance(content, (dict, list, tuple)):
        return json.dumps(content, ensure_ascii=False, indent=2, default=str)
    return str(content)


def _stable_hash(value: Any) -> str:
    from src.state.fingerprints import fingerprint_mapping

    if isinstance(value, dict):
        return fingerprint_mapping(value)
    return fingerprint_mapping({"value": value})


def read_round_status(*, project_dir: str | Path, experiment_id: str, round_number: int) -> dict[str, Any] | None:
    status_path = round_directory(project_dir, experiment_id, round_number) / ROUND_STATUS_FILENAME
    if not status_path.is_file():
        return None
    return json.loads(status_path.read_text(encoding="utf-8"))


def create_round_awaiting_revision(
    *,
    project_dir: str | Path,
    experiment_id: str,
    cycle_id: str,
    round_number: int,
    writer_revision_request: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Path]:
    """Fase 07: crea atómicamente ``round_NN`` (staging + rename del
    directorio completo). Lanza ``FileExistsError`` si la ronda ya existe
    -- nunca se sobrescribe. ``artifacts`` debe incluir
    ``"writer_revision_request.json": writer_revision_request`` (se exige
    explícitamente para poder fijar el hash de referencia que
    ``complete_round_revision`` validará después)."""

    if "writer_revision_request.json" not in artifacts:
        raise ValueError(
            "create_round_awaiting_revision requiere 'writer_revision_request.json' "
            "en artifacts -- es el ancla de consistencia para la fase 06."
        )
    if not artifacts:
        raise ValueError("create_round_awaiting_revision requiere al menos un artefacto.")

    final_dir = round_directory(project_dir, experiment_id, round_number)
    if final_dir.exists():
        raise FileExistsError(
            f"La ronda {round_number} ya está persistida en {final_dir} "
            "-- no se sobrescriben rondas anteriores."
        )

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = final_dir.parent / f".staging_round_{round_number:02d}_{uuid.uuid4().hex[:8]}"
    staging_dir.mkdir(parents=True, exist_ok=False)

    try:
        for filename, content in artifacts.items():
            (staging_dir / filename).write_text(_serialize(content), encoding="utf-8")

        status = {
            "status": STATUS_AWAITING_REVISION,
            "experiment_id": experiment_id,
            "cycle_id": cycle_id,
            "round_number": round_number,
            "writer_revision_request_hash": _stable_hash(writer_revision_request),
        }
        (staging_dir / ROUND_STATUS_FILENAME).write_text(_serialize(status), encoding="utf-8")

        missing = [name for name in list(artifacts) + [ROUND_STATUS_FILENAME] if not (staging_dir / name).is_file()]
        if missing:
            raise OSError(f"Artefactos faltantes tras escribir el staging de la ronda {round_number}: {missing}")

        staging_dir.rename(final_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return {filename: final_dir / filename for filename in artifacts}



def list_persisted_rounds(*, project_dir: str | Path, experiment_id: str) -> list[int]:
    base = Path(project_dir) / experiment_id / "05_outputs" / CYCLE_DIRECTORY_NAME
    if not base.is_dir():
        return []
    rounds = []
    for entry in base.iterdir():
        if entry.is_dir() and entry.name.startswith("round_"):
            try:
                rounds.append(int(entry.name.split("_")[1]))
            except (IndexError, ValueError):
                continue
    return sorted(rounds)


def read_round_artifact(*, project_dir: str | Path, experiment_id: str, round_number: int, filename: str) -> Any:
    path = round_directory(project_dir, experiment_id, round_number) / filename
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def round_is_persisted(*, project_dir: str | Path, experiment_id: str, round_number: int) -> bool:
    return round_directory(project_dir, experiment_id, round_number).is_dir()
