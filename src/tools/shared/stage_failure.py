"""Clasificación de excepciones a ``reason_code`` y construcción del
``AgentResult`` de fallo -- compartido por 04, 05 y 06.

Antes, cada uno de esos tres agentes mantenía por separado: una lista
hardcodeada de reason codes conocidos (14 en 04, 10 en 05, 30 en 06), la
misma búsqueda ``next((c for c in known if c in str(exc)), DEFAULT)``, y
el mismo bloque ``AgentResult(execution_status=FAILED, ...)`` copiado casi
verbatim (mismo ``quality_status=REJECTED``, misma forma de
``warnings``/``failure_reason_codes``/``requested_transition``, mismo
``output_artifacts={}``). Se consolida aquí la MECÁNICA compartida; las
listas de reason codes siguen siendo explícitas y propias de cada etapa
(eso es información real de negocio, no duplicación accidental) y se
siguen pasando como parámetro.

03 (``extraction_agent.py::_technical_failure_reason_codes``) NO se toca:
usa un enfoque distinto y ya generalizado por palabras clave (no una
lista fija a mantener), no reimplementa el problema que esto resuelve."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from src.contracts.agent_result import (
    AgentResult,
    AgentWarning,
    DecisionInfo,
    ExecutionStatus,
    QualityStatus,
    RequestedTransition,
    ToolUsage,
    TransitionAction,
    WarningSeverity,
)

DEFAULT_STAGE_FAILURE_CODE = "RUNTIME_DEPENDENCY_FAILED"


def classify_stage_exception(
    exc: Exception,
    known_reason_codes: Sequence[str],
    *,
    file_not_found_code: str | None = None,
    default_code: str = DEFAULT_STAGE_FAILURE_CODE,
) -> str:
    """Reproduce EXACTAMENTE la búsqueda que hacían 04/05/06 por separado:
    el primer código de ``known_reason_codes`` que aparece como substring
    literal del mensaje de la excepción, en el orden de la lista.

    ``file_not_found_code``: 04 tenía un tercer nivel de fallback
    (``DEPENDENCY_NOT_FOUND`` si la excepción es ``FileNotFoundError`` y
    ningún código conocido apareció en el mensaje) que 05 y 06 nunca
    tuvieron. Se preserva como parámetro OPCIONAL (``None`` por defecto)
    en vez de generalizarlo silenciosamente a los tres -- eso sería un
    cambio de comportamiento real para 05/06, no una consolidación."""
    message = str(exc)
    for code in known_reason_codes:
        if code in message:
            return code
    if file_not_found_code is not None and isinstance(exc, FileNotFoundError):
        return file_not_found_code
    return default_code


def build_stage_failure_result(
    *,
    exc: Exception,
    code: str,
    decision_code: str,
    rationale: str,
    stage_name: str,
    attempt_number: int,
    started_at: str,
    tool_usage: ToolUsage,
) -> AgentResult:
    """Construye el ``AgentResult`` de fallo idéntico al que 04/05/06
    devolvían inline: ``FAILED``/``REJECTED``, un único ``AgentWarning``
    con el ``code`` ya clasificado, ``HALT_STAGE`` sin
    ``target_stage``, ``output_artifacts={}`` y el mismo ``error`` de
    diagnóstico (``type``/``message``/``stage``).

    ``tool_usage`` se recibe ya construido por el llamador porque cada
    etapa registra contadores distintos en el punto de fallo (04/05 solo
    ``llm_calls``; 06 además ``retrieval_rounds``/``validation_calls``) --
    esa parte sí es información real por etapa, no duplicación."""
    message = str(exc)
    return AgentResult(
        execution_status=ExecutionStatus.FAILED,
        quality_status=QualityStatus.REJECTED,
        decision=DecisionInfo(code=decision_code, rationale=rationale),
        quality_metrics={"scientific": {}, "technical": {}},
        warnings=(
            AgentWarning(
                code=code,
                severity=WarningSeverity.ERROR,
                blocking=True,
                message=message,
            ),
        ),
        failure_reason_codes=(code,),
        requested_transition=RequestedTransition(
            action=TransitionAction.HALT_STAGE,
            target_stage=None,
            reason_code=code,
            requires_human_confirmation=False,
        ),
        output_artifacts={},
        tool_usage=tool_usage,
        attempt_number=attempt_number,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc).isoformat(),
        error={
            "type": type(exc).__name__,
            "message": message,
            "stage": stage_name,
        },
    )
