"""Recuperación adaptativa (Agentic Retrieval) para el Agente 06 --
adaptación del patrón ya usado en verificación (Stage 07,
``src/tools/verification/agentic_retrieval_*.py``) a la etapa de
REDACCIÓN, para mejorar la evidencia usada en la GENERACIÓN del borrador
en vez de usarla solo para verificar después de redactar.

Diferencia con SciRAG (motivación original de este módulo): SciRAG usa
recuperación adaptativa para generar mejor, no para verificar después de
redactar. En este repositorio, 07 ya implementaba el ciclo
RETRIEVE -> GRADE_EVIDENCE -> (REWRITE_QUERY | ADJUST_TOP_K | ACCEPT_EVIDENCE)
pero únicamente en verificación post-borrador. Este módulo lleva el mismo
ciclo a 06, antes de redactar cada sección.

Reutiliza directamente de ``src/config/agentic_retrieval_policy_config.py``
los umbrales y la mecánica genéricos (``DEFAULT_GRADER_THRESHOLDS``,
``DEFAULT_MINIMUM_VIABLE_THRESHOLDS``, ``next_top_k``,
``validate_effective_top_k_max``) porque esa parte no depende de la forma
del candidato.

NO reutiliza sin cambios ``agentic_retrieval_grader.py`` /
``agentic_retrieval_query_rewrite.py`` de 07 porque ambos exigen
``candidate["native_scores_by_retriever"]["chroma"]`` (vía
``extract_candidate_relevance_score``) -- los candidatos que produce
``tools/draft_writing/retrieval.py`` usan una clave plana ``"score"``, y
además mezclan filas reales de Chroma (``retrieval_method ==
"chroma_restricted"``) con filas de respaldo léxico CSV
(``retrieval_method == "csv_lexical_restricted"``) que no tienen ningún
score nativo de Chroma. Este módulo re-implementa la misma lógica,
adaptada a esa forma de candidato, en vez de forzar el contrato de 07
sobre datos que no lo cumplen.

Simplificación deliberada frente a 07: la elección entre REWRITE_QUERY y
ADJUST_TOP_K aquí es DETERMINÍSTICA (no hay planner LLM): se intenta
primero REWRITE_QUERY, y solo si la expansión de query no aporta ningún
término nuevo se recurre a ADJUST_TOP_K. Esto evita una llamada LLM
adicional por sección durante la redacción (costo/latencia). Si se
necesita paridad exacta con el planner LLM de 07, es un cambio de alcance
distinto, no cubierto aquí.
"""

from __future__ import annotations

import re
from typing import Any

from src.config.agentic_retrieval_policy_config import (
    DEFAULT_GRADER_THRESHOLDS,
    DEFAULT_MINIMUM_VIABLE_THRESHOLDS,
    GRADE_REASON_CODES,
    GRADE_RESULT_VALUES,
    next_top_k,
    validate_effective_top_k_max,
    validate_grader_thresholds,
    validate_minimum_viable_thresholds,
)

# Mismas stopwords mínimas ES/EN que agentic_retrieval_grader.py (Stage 07)
# -- no se importan de ahí porque son un detalle interno con nombre "privado"
# (_STOPWORDS); se duplica la constante, no la lógica de negocio.
_STOPWORDS = frozenset({
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "en", "y", "o",
    "que", "con", "por", "para", "es", "son", "se", "su", "sus", "al", "the",
    "an", "of", "in", "and", "or", "that", "with", "for", "is", "are", "to", "on", "as",
})

DEFAULT_MAX_NEW_TERMS_PER_EXPANSION = 8
DEFAULT_MAX_EXPANDED_QUERY_LENGTH = 500
DEFAULT_MAX_ADDITIONAL_RETRIEVAL_ROUNDS = 2


def _extract_terms(text: str) -> set[str]:
    tokens = re.findall(r"[a-záéíóúñ0-9]+", str(text).lower())
    return {t for t in tokens if len(t) > 2 and t not in _STOPWORDS}


def _extract_terms_in_order(text: str) -> list[str]:
    """Como ``_extract_terms`` pero preservando el orden de aparición --
    necesario para una expansión aditiva reproducible (no alfabética)."""
    tokens = re.findall(r"[a-záéíóúñ0-9]+", str(text).lower())
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if len(token) > 2 and token not in _STOPWORDS and token not in seen:
            ordered.append(token)
            seen.add(token)
    return ordered


def _candidate_score(candidate: dict[str, Any]) -> float:
    """Extrae el score de un candidato de 06 (clave plana ``"score"``, a
    diferencia de 07 que exige ``native_scores_by_retriever["chroma"]``).
    Válido tanto para filas reales de Chroma (``1 - distancia``) como para
    filas de respaldo léxico CSV (``overlap / total_query_tokens``) --
    ambas ya normalizadas a ``[0, 1]`` por ``retrieval.py``."""
    if not isinstance(candidate, dict):
        raise TypeError(f"candidate debe ser dict, recibido {type(candidate).__name__}.")
    score = candidate.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise TypeError(
            f"candidate['score'] debe ser numérico, recibido {type(score).__name__} ({score!r})."
        )
    return float(score)


def _authorized_sources_for_section(section: dict[str, Any]) -> frozenset[str]:
    from src.tools.draft_writing.retrieval import safe_str

    names = [
        safe_str(paper.get("source_filename") if isinstance(paper, dict) else paper)
        for paper in (section.get("papers_to_use") or [])
    ]
    return frozenset(name for name in names if name)


def grade_section_evidence(
    *,
    section_query: str,
    candidates: list[dict[str, Any]],
    thresholds: dict | None = None,
) -> dict[str, Any]:
    """Adaptación de ``agentic_retrieval_grader.grade_evidence`` (Stage 07)
    a evidencia de sección de 06: las mismas 4 señales (conteo de
    candidatos, diversidad de fuentes, relevancia máxima, cobertura
    léxica), pero medidas contra ``section_query`` (no un claim de
    verificación) y leyendo ``candidate["score"]`` en vez del extractor
    estricto de score nativo de Chroma de 07."""
    if thresholds is None:
        thresholds = DEFAULT_GRADER_THRESHOLDS
    thresholds = validate_grader_thresholds(thresholds)

    candidate_count = len(candidates)
    source_diversity = len({c.get("source_filename") for c in candidates})
    scores = [_candidate_score(c) for c in candidates]
    max_relevance_score = max(scores) if scores else 0.0

    query_terms = _extract_terms(section_query)
    if query_terms:
        candidate_terms: set[str] = set()
        for candidate in candidates:
            candidate_terms |= _extract_terms(str(candidate.get("text", "")))
        lexical_overlap_ratio = len(query_terms & candidate_terms) / len(query_terms)
    else:
        lexical_overlap_ratio = 0.0

    reason_codes: list[str] = []
    if candidate_count < thresholds["min_candidate_count"]:
        reason_codes.append("LOW_CANDIDATE_COUNT")
    if (
        candidate_count >= thresholds["min_candidate_count_for_diversity_check"]
        and source_diversity < thresholds["min_source_diversity"]
    ):
        reason_codes.append("LOW_SOURCE_DIVERSITY")
    if max_relevance_score < thresholds["min_relevance_score"]:
        reason_codes.append("LOW_RELEVANCE")
    if lexical_overlap_ratio < thresholds["min_lexical_overlap_ratio"]:
        reason_codes.append("LOW_COVERAGE")

    grade_result = "INSUFFICIENT" if reason_codes else "SUFFICIENT"
    assert grade_result in GRADE_RESULT_VALUES, grade_result
    for code in reason_codes:
        assert code in GRADE_REASON_CODES, code

    return {
        "grade_result": grade_result,
        "reason_codes": tuple(reason_codes),
        "candidate_count": candidate_count,
        "source_diversity": source_diversity,
        "max_relevance_score": max_relevance_score,
        "lexical_overlap_ratio": lexical_overlap_ratio,
    }


def is_section_evidence_minimum_viable(
    *,
    candidates: list[dict[str, Any]],
    authorized_sources: frozenset[str] | set[str],
    thresholds: dict | None = None,
) -> bool:
    """Adaptación de ``is_minimum_viable_evidence`` (Stage 07): al menos un
    candidato con score >= umbral mínimo y de fuente autorizada. Más laxo
    que ``grade_section_evidence`` -- se usa solo para decidir, al agotar
    el presupuesto de rondas adicionales, si vale la pena conservar lo
    mejor encontrado en vez de descartarlo."""
    if thresholds is None:
        thresholds = DEFAULT_MINIMUM_VIABLE_THRESHOLDS
    thresholds = validate_minimum_viable_thresholds(thresholds)
    if not isinstance(authorized_sources, (frozenset, set)):
        raise TypeError(
            f"authorized_sources debe ser frozenset/set, recibido "
            f"{type(authorized_sources).__name__}."
        )
    if len(candidates) < thresholds["min_candidate_count"]:
        return False
    return any(
        _candidate_score(c) >= thresholds["min_relevance_score"]
        and c.get("source_filename") in authorized_sources
        for c in candidates
    )


def expand_section_query(
    *,
    current_query: str,
    candidates: list[dict[str, Any]],
    authorized_sources: frozenset[str] | set[str],
    max_new_terms: int = DEFAULT_MAX_NEW_TERMS_PER_EXPANSION,
    max_length: int = DEFAULT_MAX_EXPANDED_QUERY_LENGTH,
) -> str | None:
    """Adaptación determinística de ``generate_query_rewrite`` (Stage 07):
    expansión aditiva por retroalimentación pseudo-relevante (los
    candidatos ya recuperados aportan vocabulario nuevo), restringida a
    fuentes autorizadas de la sección, ordenados por score descendente y
    con desempate determinístico (source_filename, chunk_id).

    A diferencia de 07 -- que lanza ``QueryRewriteError`` cuando no hay
    términos nuevos disponibles, porque ahí REWRITE_QUERY es una acción ya
    elegida explícitamente por el planner -- aquí se devuelve ``None`` para
    que el llamador decida usar ADJUST_TOP_K en su lugar sin necesitar
    manejo de excepciones. Tampoco reproduce los guardrails de
    instruction-leakage/trazabilidad estricta de 07: esta query nunca se le
    muestra a un LLM como si fuera contenido autorizado por el usuario, solo
    alimenta una nueva consulta de recuperación léxica/vectorial."""
    current_query = str(current_query or "").strip()
    if not current_query:
        return None

    existing_terms = _extract_terms(current_query)
    authorized_candidates = [
        c for c in candidates if c.get("source_filename") in authorized_sources
    ]
    ranked = sorted(
        authorized_candidates,
        key=lambda c: (
            -_candidate_score(c),
            str(c.get("source_filename", "")),
            str(c.get("chunk_id", "")),
        ),
    )

    selected_terms: list[str] = []
    seen: set[str] = set()
    for candidate in ranked:
        if len(selected_terms) >= max_new_terms:
            break
        for term in _extract_terms_in_order(str(candidate.get("text", ""))):
            if len(selected_terms) >= max_new_terms:
                break
            if term in existing_terms or term in seen:
                continue
            candidate_query = f"{current_query} {' '.join(selected_terms + [term])}".strip()
            if len(candidate_query) > max_length:
                continue
            selected_terms.append(term)
            seen.add(term)

    if not selected_terms:
        return None

    return f"{current_query} {' '.join(selected_terms)}".strip()


def retrieve_section_evidence_adaptive(
    *,
    section: dict[str, Any],
    collection,
    chunks_df,
    initial_top_k: int,
    max_evidence_chars: int = 18000,
    min_relevance_score: float = 0.0,
    min_overlap_tokens: int = 1,
    effective_top_k_max: int | None = None,
    max_additional_retrieval_rounds: int = DEFAULT_MAX_ADDITIONAL_RETRIEVAL_ROUNDS,
    grader_thresholds: dict | None = None,
    minimum_viable_thresholds: dict | None = None,
) -> dict[str, Any]:
    """Ciclo adaptativo RETRIEVE -> GRADE -> (REWRITE_QUERY | ADJUST_TOP_K)
    para una sección de 06, análogo al controller de 07
    (``agentic_retrieval_controller.py``) pero con decisión determinística
    (ver docstring del módulo) y candidatos con forma de 06.

    No reemplaza el manejo existente de "sin evidencia" en
    ``draft_writing_agent.py`` (``MISSING_SECTION_EVIDENCE`` /
    ``section_allows_no_sources``): si no hay fuentes autorizadas o ninguna
    ronda produce evidencia, ``evidence`` regresa vacía igual que antes."""
    from src.tools.draft_writing.retrieval import (
        build_section_query,
        retrieve_section_evidence,
    )

    authorized_sources = _authorized_sources_for_section(section)
    query = build_section_query(section)

    if not authorized_sources:
        return {
            "evidence": [],
            "final_query": query,
            "additional_retrieval_rounds_used": 0,
            "final_grade": None,
            "minimum_viable_when_insufficient": None,
        }

    top_k = int(initial_top_k)
    resolved_top_k_max = validate_effective_top_k_max(
        int(effective_top_k_max) if effective_top_k_max is not None else top_k
    )
    if resolved_top_k_max < top_k:
        # Nunca reducir por debajo del top_k inicial ya configurado --
        # este campo solo sirve para AMPLIAR el techo de ADJUST_TOP_K.
        resolved_top_k_max = top_k

    rounds_used = 0
    evidence = retrieve_section_evidence(
        section,
        collection,
        chunks_df,
        top_k,
        max_evidence_chars,
        min_relevance_score=min_relevance_score,
        min_overlap_tokens=min_overlap_tokens,
        query_override=query,
    )
    grade = grade_section_evidence(
        section_query=query, candidates=evidence, thresholds=grader_thresholds
    )

    while grade["grade_result"] == "INSUFFICIENT" and rounds_used < max_additional_retrieval_rounds:
        expanded_query = expand_section_query(
            current_query=query,
            candidates=evidence,
            authorized_sources=authorized_sources,
        )
        can_adjust_top_k = top_k < resolved_top_k_max

        if expanded_query is not None:
            query = expanded_query
        elif can_adjust_top_k:
            top_k = next_top_k(current_top_k=top_k, effective_top_k_max=resolved_top_k_max)
        else:
            # Ni REWRITE_QUERY ni ADJUST_TOP_K son viables -- se detiene,
            # equivalente a FINISH_UNRESOLVED de 07 pero sin descartar la
            # mejor evidencia ya encontrada.
            break

        rounds_used += 1
        evidence = retrieve_section_evidence(
            section,
            collection,
            chunks_df,
            top_k,
            max_evidence_chars,
            min_relevance_score=min_relevance_score,
            min_overlap_tokens=min_overlap_tokens,
            query_override=query,
        )
        grade = grade_section_evidence(
            section_query=query, candidates=evidence, thresholds=grader_thresholds
        )

    minimum_viable_when_insufficient = None
    if grade["grade_result"] == "INSUFFICIENT" and evidence:
        minimum_viable_when_insufficient = is_section_evidence_minimum_viable(
            candidates=evidence,
            authorized_sources=authorized_sources,
            thresholds=minimum_viable_thresholds,
        )

    return {
        "evidence": evidence,
        "final_query": query,
        "additional_retrieval_rounds_used": rounds_used,
        "final_grade": grade,
        "minimum_viable_when_insufficient": minimum_viable_when_insufficient,
    }
