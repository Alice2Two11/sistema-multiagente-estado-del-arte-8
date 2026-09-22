"""Decisión compartida de "¿reutilizo o reconstruyo?" para etapas con
manifest + fingerprint (03, 05, 06 -- y el mismo patrón, no consolidado
aquí, aparece también en la celda 15 de 08 vía
``src/adapters/evaluation_fingerprint.py::resolve_rebuild_decision``).

Antes existía una única función aislada para esto
(``src/tools/extraction/stage_artifacts.py::decide_extraction_rebuild``,
usada solo por 03) mientras que 05 (``outline_generation_agent.py``) y 06
(``draft_writing_agent.py``) reimplementaban la misma decisión inline,
cada uno con su propia lista de archivos requeridos y ya divergidos en el
detalle (05 no valida el mismo campo de "outputs_exist" que 06, y
ninguno de los dos reproducía el guardrail de ``auto_rebuild`` que sí
tiene 03). Se consolida aquí la ÚNICA rama de decisión real: force_rebuild
> ausencia de manifiesto previo > outputs faltantes > fingerprint
obsoleto > vigente.

IMPORTANTE -- el guardrail de ``auto_rebuild`` (si hace falta reconstruir
y ``auto_rebuild`` es ``False``, falla con ``RuntimeError`` en vez de
reconstruir en silencio) es OPCIONAL aquí (``auto_rebuild=None`` lo
desactiva por completo). Esto no es un descuido de la consolidación: 05 y
06 nunca tuvieron ese campo -- ``CONFIG-F`` (ver
``src/config/draft_writing_policy_config.py`` y
``src/config/outline_generation_policy_config.py``) auditó ``auto_rebuild``
explícitamente como ``TRUE_STALE_CONFIG`` para ambas etapas y lo retiró
sin reemplazo, porque nunca tuvo ningún consumidor real. Consolidar la
mecánica compartida no reintroduce ese gate donde nunca existió de
verdad; solo 03 lo pasa con un valor real.

También nota: cuando ``auto_rebuild`` SÍ se usa (caso de 03), el gate NO
exime a ``force_rebuild`` -- si ``force_rebuild`` es verdadero pero
``auto_rebuild`` es ``False``, esta función igual lanza ``RuntimeError``.
Esto reproduce EXACTAMENTE el comportamiento real y ya existente de
``decide_extraction_rebuild`` (03) tal como estaba antes de esta
consolidación -- no es una decisión de diseño nueva. (El módulo hermano
de 08, ``resolve_rebuild_decision``, sí exime a ``force_rebuild`` del
gate -- una divergencia adicional entre 03 y 08 detectada durante esta
consolidación, pero fuera de alcance: 08 no se toca aquí.)"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def resolve_stage_reuse_decision(
    *,
    force_rebuild: Any,
    previous_manifest: Mapping[str, Any] | None,
    outputs_exist: Any,
    current_fingerprint: str,
    auto_rebuild: Any | None = None,
    force_rebuild_status: str = "force_rebuild_requested",
    no_manifest_status: str = "no_previous_manifest",
    missing_outputs_status: str = "missing_outputs",
    stale_status: str = "stale_outputs_config_changed",
    current_status: str = "outputs_are_current",
    auto_rebuild_disabled_message: str | None = None,
) -> dict[str, Any]:
    """Calcula el status y las banderas de reconstrucción de una etapa.

    ``outputs_exist``: ya evaluado por el llamador (cada etapa tiene su
    propia noción de "outputs completos" -- p.ej. 03 solo revisa que los
    archivos existan, 05/06 además exigen que el reporte de validación
    guardado sea ``validation_ok``). Esta función no conoce esos detalles
    por etapa a propósito -- eso sigue siendo responsabilidad del
    llamador, exactamente como antes.

    Los parámetros ``*_status`` permiten a cada etapa conservar sus
    propias cadenas de status si ya las expone en su manifiesto (03 y 06
    ya difieren en el texto exacto, p.ej. ``"force_rebuild_requested"``
    vs ``"force_rebuild"``) sin que la consolidación fuerce un
    vocabulario nuevo.

    ``auto_rebuild=None`` (default): sin gate -- ``should_rebuild`` es
    simplemente ``rebuild_required`` (comportamiento histórico de 05/06).
    ``auto_rebuild=True/False``: aplica el guardrail real de 03 -- ver
    docstring del módulo."""

    if force_rebuild:
        status, rebuild_required = force_rebuild_status, True
    elif previous_manifest is None:
        status, rebuild_required = no_manifest_status, True
    elif not outputs_exist:
        status, rebuild_required = missing_outputs_status, True
    elif previous_manifest.get("fingerprint") != current_fingerprint:
        status, rebuild_required = stale_status, True
    else:
        status, rebuild_required = current_status, False

    if auto_rebuild is not None and rebuild_required and not auto_rebuild:
        raise RuntimeError(
            auto_rebuild_disabled_message
            or "La etapa necesita regenerarse, pero auto_rebuild es False."
        )

    if auto_rebuild is None:
        should_rebuild = rebuild_required
    else:
        should_rebuild = (rebuild_required and auto_rebuild) or force_rebuild

    return {
        "status": status,
        "rebuild_required": rebuild_required,
        "should_rebuild": should_rebuild,
    }
