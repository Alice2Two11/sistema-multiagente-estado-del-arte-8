"""Contratos internos de Fase 6.1 para reverificación virtual.

No ejecuta reverificación, no compara resultados, no agrega métricas y no
escribe artefactos. La aplicación física sigue reservada exclusivamente a 07C.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


TRACEABILITY_PROVISIONAL_UNITS = {
    "claims": ("claim_id",),
    "corrections": ("correction_id",),
    "issues": ("claim_id", "issue_code"),
    "evidence": ("claim_id", "correction_id", "evidence_id"),
}


# Phase 6.3R terminal contracts. Historical superseded definitions removed in Phase 6.7.
@dataclass(frozen=True, slots=True)
class CorrectionReverificationPrecheckResult:
    correction_id: str
    claim_id: str
    section_id: str
    virtual_proposed_claim_text: str
    precheck_status: str
    contract_valid: bool
    fingerprints_valid: bool
    spans_valid: bool
    evidence_valid: bool
    textual_integrity_valid: bool
    action_validation_valid: bool
    reason_codes: tuple[str, ...]
    technical_issue_codes: tuple[str, ...]
    virtual_proposed_claim_text_fingerprint: str = ""
    proposal_fingerprint: str = ""
    base_claim_fingerprint: str = ""
    base_section_fingerprint: str = ""
    frozen_evidence_snapshot_fingerprint: str = ""
    reverification_policy_fingerprint: str = ""
    reverification_context_fingerprint: str = ""
    diagnostic_details: tuple[Mapping[str, Any], ...] = ()
    llm_calls: int = 0
    correction_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrectionIndependentReverificationResult:
    correction_id: str
    claim_id: str
    section_id: str
    reverification_execution_status: str
    proposed_verdict: str
    support_level: str
    observed_issue_codes: tuple[str, ...]
    target_issues_resolved_reported: tuple[str, ...]
    evidence_ids_used: tuple[str, ...]
    supported_meaning_preserved: bool
    intended_semantic_change_valid: bool
    unintended_semantic_change_absent: bool
    scope_assessment: str
    numeric_assessment: str
    attribution_assessment: str
    citation_assessment: str
    manual_review_recommended: bool
    reason_codes: tuple[str, ...]
    technical_issue_codes: tuple[str, ...]
    rationale: str
    confidence: float | None
    prompt_version: str
    raw_attempts: tuple[Mapping[str, Any], ...]
    decision_trace: tuple[Mapping[str, Any], ...]
    reverification_llm_calls: int
    format_attempts: int
    format_retries: int
    schema_attempts: int
    schema_retries: int
    proposal_fingerprint: str
    virtual_proposed_claim_text_fingerprint: str
    frozen_evidence_snapshot_fingerprint: str = ""
    reverification_context_fingerprint: str = ""
    tool_names_considered: tuple[str, ...] = ("ReverificationLLM",)
    tool_names_selected: tuple[str, ...] = ()
    correction_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrectionBeforeAfterComparisonResult:
    correction_id: str
    claim_id: str
    section_id: str
    correction_action_type: str
    original_verdict: str
    proposed_verdict: str
    source_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    target_issue_codes: tuple[str, ...]
    resolved_issue_codes: tuple[str, ...]
    remaining_issue_codes: tuple[str, ...]
    new_issue_codes: tuple[str, ...]
    target_issues_resolved: bool
    reported_resolution_matches: bool
    hallucination_risk_before: str
    hallucination_risk_after: str
    hallucination_risk_delta: str
    risk_policy_version: str
    risk_before_recomputed: bool
    risk_after_computed: bool
    supported_meaning_preserved: bool
    intended_semantic_change_valid: bool
    unintended_semantic_change_absent: bool
    scope_assessment: str
    numeric_assessment: str
    attribution_assessment: str
    citation_assessment: str
    acceptance_decision: str
    manual_review_required: bool
    reason_codes: tuple[str, ...]
    technical_issue_codes: tuple[str, ...]
    decision_trace: tuple[Mapping[str, Any], ...]
    proposal_fingerprint: str
    virtual_proposed_claim_text_fingerprint: str
    frozen_evidence_snapshot_fingerprint: str
    reverification_context_fingerprint: str
    result_contract_valid: bool
    additional_llm_calls: int = 0
    retrieval_rounds: int = 0
    correction_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

# Phase 6.5.1A: structural-only provisional aggregation contracts.
@dataclass(frozen=True, slots=True)
class ProvisionalVerificationAggregationInput:
    claim_verification_records: tuple[Mapping[str, Any], ...] = ()
    correction_proposals: tuple[Mapping[str, Any], ...] = ()
    correction_reverification_inputs: tuple[Mapping[str, Any], ...] = ()
    correction_precheck_results: tuple[Mapping[str, Any], ...] = ()
    independent_reverification_results: tuple[Mapping[str, Any], ...] = ()
    before_after_comparison_results: tuple[Mapping[str, Any], ...] = ()
    policy_versions: Mapping[str, str] = None  # type: ignore[assignment]
    schema_versions: Mapping[str, str] = None  # type: ignore[assignment]
    additional_llm_calls: int = 0
    additional_retrieval_rounds: int = 0
    correction_applied: bool = False
    official_artifacts_created: bool = False

    def __post_init__(self) -> None:
        if self.policy_versions is None: object.__setattr__(self, "policy_versions", {})
        if self.schema_versions is None: object.__setattr__(self, "schema_versions", {})

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float | None
    numerator: int
    denominator: int
    status: str
    unit_definition: str
    population_filter: str

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ClaimTraceabilityRow:
    claim_id: str
    section_id: str
    claim_type: str
    original_claim_text: str
    source_verdict: str
    source_issue_codes: tuple[str, ...]
    source_hallucination_risk: str
    terminal_correction_recommendation: bool
    has_correction_proposal: bool
    correction_ids: tuple[str, ...]
    individual_proposal_decisions: tuple[str, ...]
    individual_accepted_correction_ids: tuple[str, ...]
    individual_rejected_correction_ids: tuple[str, ...]
    individual_deferred_correction_ids: tuple[str, ...]
    provisional_remaining_issue_codes: tuple[str, ...]
    manual_review_required: bool
    correction_applied: bool = False
    # Agent07 bundle V3 compatibility extension: preserve source confidence when available.
    source_verification_confidence: float | None = None
    source_confidence_status: str = "NOT_AVAILABLE_IN_SOURCE_CONTRACT"
    # Identidad estable (ver src/tools/draft_writing/claim_identity.py) --
    # "" para claims legacy sin identidad estable todavía.
    claim_uid: str = ""
    # Diagnóstico real (experimento_paper_52, Stage08): 11/37 claims
    # terminaron en NOT_EVALUATED con evidence_pair_count=0 en el reporte
    # final, y hasta ahora era imposible distinguir, sin volcar el JSON
    # crudo de Agent07, si la causa era falta de evidencia, un corte
    # deliberado (deterministic_precheck) o un bloqueo técnico (LLM no
    # disponible, recuperación adicional agotada/no disponible, etc.).
    # ClaimVerificationResult.technical_status/technical_issue_codes ya
    # traían esta respuesta -- solo nunca se propagaban hasta esta fila,
    # que es lo único que sobrevive hasta el CSV final de Stage08. Ambos
    # campos son un espejo 1:1 de esos dos campos de
    # ClaimVerificationResult (nunca se derivan/infieren aquí), y llevan
    # default para no romper ninguna otra construcción histórica de esta
    # dataclass que no los pase explícitamente.
    technical_status: str = "OK"
    technical_issue_codes: tuple[str, ...] = ()
    # Diagnóstico real (experimento_paper_52, segunda vuelta): con
    # technical_status/technical_issue_codes ya visibles, los 10 claims
    # NOT_EVALUATED de esa corrida resultaron TODOS
    # "LLM_VALIDATION_ATTEMPTS_EXHAUSTED" -- es decir, el LLM verificador
    # nunca produjo una respuesta que pasara
    # validate_llm_verification_response (format/schema), agotando los
    # reintentos, para claims de tipos y cantidades de evidencia
    # dispares (QUANTITATIVE, COMPARATIVE, SUBSTANTIVE_FACTUAL,
    # METHODOLOGICAL; 1 a 3 citas) -- sin un patrón obvio visible desde
    # fuera. La causa raíz real está en CUÁL regla de
    # validate_llm_verification_response se violó en cada intento
    # (ValueError con códigos cortos y seguros, ej.
    # "UNKNOWN_EVIDENCE_ID:E5", "SUPPORTED_REQUIRES_STRONG_SUPPORT" --
    # nunca texto crudo del LLM), y eso solo vivía en
    # ClaimVerificationResult.raw_attempts[].validation_errors, que
    # nunca salía de Agent07 (traceability.py ya solo conservaba un
    # conteo + fingerprint de raw_attempts, nunca los códigos). Este
    # campo es la UNIÓN (deduplicada, ordenada) de esos códigos de error
    # across TODOS los intentos de un claim -- nunca el texto crudo de
    # la respuesta del LLM, nunca el prompt.
    llm_validation_error_codes: tuple[str, ...] = ()
    # Diagnóstico agregado junto con el criterio CAUSAL_CLAUSE_REASONABLE_INFERENCE
    # (verification_policy_config.SEMANTIC_REASON_CODES / prompting.py): el campo
    # ``source_issue_codes`` de esta misma fila NO transporta el ``reason_codes``
    # crudo que el LLM devuelve por claim -- se construye como
    # ``deterministic_issue_codes + semantic_issue_codes`` (ver
    # build_provisional_traceability_rows), que son códigos DERIVADOS del
    # veredicto/contradicción/numérico/atribución/extrapolación, nunca el
    # ``reason_codes`` original. Sin este campo, un reason_code que el LLM SÍ
    # devuelve explícitamente -- como CAUSAL_CLAUSE_REASONABLE_INFERENCE, usado
    # para dejar constancia de que aplicó el criterio más laxo a una cláusula
    # causal/de propósito de un claim compuesto -- quedaría invisible en el CSV
    # final, haciendo imposible auditar cuántas veces se usó y sobre qué claims.
    # Espejo 1:1 de ClaimVerificationResult.reason_codes (el campo crudo
    # validado, nunca derivado ni filtrado aquí).
    llm_reason_codes: tuple[str, ...] = ()
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrectionTraceabilityRow:
    correction_id: str
    claim_id: str
    section_id: str
    action_type: str | None
    is_scientific_correction_action: bool
    is_gate_result: bool
    proposal_stage_availability: str
    precheck_stage_availability: str
    reverification_stage_availability: str
    comparison_stage_availability: str
    proposal_status: str | None
    precheck_status: str | None
    reverification_execution_status: str | None
    acceptance_decision: str | None
    target_issue_codes: tuple[str, ...]
    resolved_issue_codes: tuple[str, ...]
    remaining_issue_codes: tuple[str, ...]
    new_issue_codes: tuple[str, ...]
    hallucination_risk_before: str | None
    hallucination_risk_after: str | None
    hallucination_risk_delta: str | None
    proposal_fingerprint: str | None
    virtual_proposed_claim_text_fingerprint: str | None
    frozen_evidence_snapshot_fingerprint: str | None
    reverification_context_fingerprint: str | None
    precheck_reason_codes: tuple[str, ...]
    precheck_technical_issue_codes: tuple[str, ...]
    comparison_reason_codes: tuple[str, ...]
    comparison_technical_issue_codes: tuple[str, ...]
    gate_classification: str | None
    manual_review_required: bool
    correction_applied: bool = False
    # Phase 6.6 blocking context: copied from the already validated CorrectionProposal.
    original_claim_fingerprint: str | None = None
    target_span_in_claim: Mapping[str, Any] | None = None
    replacement_text: str | None = None
    proposed_claim_text: str | None = None
    # Trazabilidad terminal completa (una CorrectionProposal SIEMPRE trae
    # estos datos -- ver CorrectionProposal en corrections.py -- pero
    # antes se descartaban al construir la fila del bundle). Copiados
    # directamente desde la CorrectionProposal.to_dict() unida por
    # correction_id, sin inventar nada: si la propuesta no los tenía
    # (ej. un dict legacy incompleto en un fixture antiguo), quedan en
    # su default explícito, nunca se sintetiza un valor.
    correction_decision: str | None = None
    final_proposal_status: str | None = None
    requires_manual_review: bool = False
    accepted_for_reverification: bool = False
    reason_codes: tuple[str, ...] = ()
    validation_issue_codes: tuple[str, ...] = ()
    decision_path: tuple[str, ...] = ()
    retry_metrics: Mapping[str, int] | None = None
    # Referencia SEGURA a raw_attempts -- nunca el texto crudo del LLM
    # embebido en la fila de trazabilidad (podría ser grande y no aporta
    # auditoría adicional sobre el conteo/fingerprint): cuántos intentos
    # hubo y un fingerprint determinista de su contenido, suficiente
    # para correlacionar con el artefacto raw real si hace falta
    # inspeccionarlo.
    raw_attempts_count: int = 0
    raw_attempts_fingerprint: str | None = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ClaimEvidenceTraceabilityRow:
    claim_id: str
    section_id: str
    evidence_id: str
    source_filename: str
    chunk_id: str
    text_fingerprint: str
    usage_role: str
    authorized_for_section: bool
    used_in_original_verification: bool
    supports_original_claim: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrectionEvidenceTraceabilityRow:
    claim_id: str
    correction_id: str
    section_id: str
    evidence_id: str
    source_filename: str
    chunk_id: str
    usage_role: str
    authorized_for_section: bool
    used_in_correction: bool
    used_in_reverification: bool
    supports_proposed_claim: str
    frozen_evidence_snapshot_fingerprint: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ReverificationTraceabilityRow:
    correction_id: str
    claim_id: str
    section_id: str
    prompt_version: str
    reverification_execution_status: str
    reverification_llm_calls: int
    format_attempts: int
    format_retries: int
    schema_attempts: int
    schema_retries: int
    evidence_ids_used: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    target_issues_resolved_reported: tuple[str, ...]
    reported_resolution_matches: bool
    manual_review_recommended: bool
    acceptance_decision: str | None
    proposal_fingerprint: str
    virtual_proposed_claim_text_fingerprint: str
    frozen_evidence_snapshot_fingerprint: str
    reverification_context_fingerprint: str
    correction_applied: bool = False
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvisionalVerificationMetrics:
    claims_verified: int = 0
    claims_with_terminal_correction_recommendation: int = 0
    claims_with_correction_proposals: int = 0
    claims_with_accepted_proposals: int = 0
    claims_requiring_manual_review: int = 0
    corrections_proposed: int = 0
    corrections_precheck_passed: int = 0
    corrections_precheck_blocked: int = 0
    corrections_precheck_rejected: int = 0
    corrections_reverified: int = 0
    corrections_failed_reverification: int = 0
    corrections_accepted_for_07c: int = 0
    corrections_rejected: int = 0
    corrections_deferred: int = 0
    issues_before: int = 0
    candidate_claim_issues_resolved: int = 0
    accepted_claim_issues_resolved: int = 0
    issues_remaining: int = 0
    new_issues_introduced: int = 0
    corrections_with_new_issues: int = 0
    risk_reduced: int = 0
    risk_unchanged: int = 0
    risk_increased: int = 0
    risk_not_comparable: int = 0
    verification_llm_calls: int = 0
    correction_llm_calls: int = 0
    reverification_llm_calls: int = 0
    additional_llm_calls: int = 0
    total_llm_calls: int = 0
    verification_retrieval_rounds: int = 0
    incremental_retrieval_requests: int = 0
    correction_retrieval_rounds: int = 0
    reverification_retrieval_rounds: int = 0
    comparison_retrieval_rounds: int = 0
    additional_retrieval_rounds: int = 0
    invalid_gate_results: int = 0
    temporary_technical_blocks: int = 0
    permanent_contractual_blocks: int = 0
    deterministic_scientific_rejections: int = 0
    unknown_precheck_reason_codes: int = 0
    not_available_action_results: int = 0
    candidate_issue_resolution_rate: MetricValue | None = None
    accepted_issue_resolution_rate: MetricValue | None = None
    correction_acceptance_rate: MetricValue | None = None
    new_issue_rate: MetricValue | None = None
    hallucination_risk_reduction_rate: MetricValue | None = None
    recommendations_generated: MetricValue | None = None
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvisionalVerificationTraceabilityBundle:
    claim_traceability_rows: tuple[Mapping[str, Any], ...]
    correction_traceability_rows: tuple[Mapping[str, Any], ...]
    claim_evidence_traceability_rows: tuple[Mapping[str, Any], ...]
    correction_evidence_traceability_rows: tuple[Mapping[str, Any], ...]
    reverification_traceability_rows: tuple[Mapping[str, Any], ...]
    metrics: Mapping[str, Any]
    aggregation_status: str
    metrics_status: str
    partial_reason_codes: tuple[str, ...]
    aggregation_issue_codes: tuple[str, ...]
    aggregation_warnings: tuple[str, ...]
    normalized_bundle_status: str
    normalized_bundle_fingerprint: str | None
    aggregation_audit_fingerprint: str | None
    input_collection_fingerprints: Mapping[str, str | None]
    policy_versions: Mapping[str, str]
    schema_versions: Mapping[str, str]
    correction_applied: bool = False
    official_artifacts_created: bool = False
    additional_llm_calls: int = 0
    additional_retrieval_rounds: int = 0
    result_contract_valid: bool = False

    def to_dict(self) -> dict[str, Any]: return asdict(self)

# Phase 6.5.2: internal collection-validation result. No cross-collection joins.
@dataclass(frozen=True, slots=True)
class ProvisionalCollectionValidationResult:
    normalized_claim_verification_records: tuple[Mapping[str, Any], ...]
    normalized_correction_proposals: tuple[Mapping[str, Any], ...]
    normalized_correction_reverification_inputs: tuple[Mapping[str, Any], ...]
    normalized_correction_precheck_results: tuple[Mapping[str, Any], ...]
    normalized_independent_reverification_results: tuple[Mapping[str, Any], ...]
    normalized_before_after_comparison_results: tuple[Mapping[str, Any], ...]
    primary_indexes: Mapping[str, Mapping[str, Mapping[str, Any]]]
    duplicate_records: tuple[Mapping[str, Any], ...]
    invalid_element_records: tuple[Mapping[str, Any], ...]
    collection_issue_codes: tuple[str, ...]
    collection_warnings: tuple[str, ...]
    collection_validation_status: str
    aggregation_status: str
    metrics_status: str
    result_contract_valid: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

# Phase 6.5.4: full referential context and provisional row construction.
@dataclass(frozen=True, slots=True)
class ProvisionalReferentialIntegrityResult:
    joined_claim_records: tuple[Mapping[str, Any], ...]
    joined_correction_records: tuple[Mapping[str, Any], ...]
    rejected_join_candidates: tuple[Mapping[str, Any], ...]
    referential_issue_codes: tuple[str, ...]
    referential_warnings: tuple[str, ...]
    orphan_records: tuple[Mapping[str, Any], ...]
    identity_conflicts: tuple[Mapping[str, Any], ...]
    referential_validation_status: str
    aggregation_status: str
    metrics_status: str
    result_contract_valid: bool = False
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True, slots=True)
class ProvisionalTraceabilityRowsResult:
    claim_traceability_rows: tuple[Mapping[str, Any], ...]
    correction_traceability_rows: tuple[Mapping[str, Any], ...]
    claim_evidence_traceability_rows: tuple[Mapping[str, Any], ...]
    correction_evidence_traceability_rows: tuple[Mapping[str, Any], ...]
    reverification_traceability_rows: tuple[Mapping[str, Any], ...]
    row_issue_codes: tuple[str, ...]
    row_warnings: tuple[str, ...]
    row_build_status: str
    aggregation_status: str
    metrics_status: str
    result_contract_valid: bool = False
    def to_dict(self) -> dict[str, Any]: return asdict(self)


# Phase 6.5.5: metrics aggregation result. No bundle fingerprints.
@dataclass(frozen=True, slots=True)
class ProvisionalMetricsAggregationResult:
    metrics: Mapping[str, Any]
    metric_issue_codes: tuple[str, ...]
    metric_warnings: tuple[str, ...]
    metrics_status: str
    aggregation_status: str
    result_contract_valid: bool = False
    def to_dict(self) -> dict[str, Any]: return asdict(self)
