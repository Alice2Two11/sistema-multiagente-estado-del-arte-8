"""Strict compatibility adapter from committed Agent 07 contracts to the original 07C notebook inputs."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import csv, hashlib, io, json, math
from typing import Any, Mapping, Sequence

from src.tools.verification.validation import validate_provisional_verification_traceability_bundle_contract
from src.tools.verification.resolution import validate_provisional_multi_proposal_resolution_result

HISTORICAL_COMPATIBILITY_MATRIX={
 "verification_report.csv":"bundle.claim_traceability_rows V3 with source confidence status",
 "hallucination_report.csv":"claim rows.source_hallucination_risk + correction risk before/after/delta",
 "citation_check.csv":"claim_evidence_traceability_rows",
 "claim_traceability_matrix.csv":"claim/correction/evidence/reverification rows",
 "auto_corrections_log.csv":"resolution plans.selected_patch_records + virtual_result_text",
 "claim_atomization_log.csv":"claim rows preserving claim_id, section_id, original_claim_text",
}

AGENT07C_REQUIRED_ARTIFACTS=(
 "verified_state_of_art.json","verified_state_of_art.md","verification_report.csv",
 "claim_traceability_matrix.csv","auto_corrections_log.csv",
 "verification_validation_report.json","verification_traceability_manifest.json",
)
VERIFICATION_REPORT_COLUMNS=("claim_id","section_id","claim","verdict","confidence","hallucination_risk","correction_needed","evidence_used_ids","confidence_status")
CORRECTION_LOG_COLUMNS=("claim_id","section_id","status","application_scope","original_draft_modified","action","old_fragment","new_fragment","correction_id")
SCIENTIFIC_HANDOFF_CHECK_NAMES=("claim_coverage_ok","section_identity_ok","authorized_evidence_ok","eligible_manual_disjoint_ok","source_draft_fingerprint_ok","patch_application_ok","json_markdown_consistency_ok","correction_log_consistency_ok","claim_traceability_consistency_ok")

REQUIRED_SAFETY_POLICY={
 "uses_ground_truth":False,"uses_external_knowledge":False,"uses_section_evidence_fallback":False,
 "uses_fuzzy_citation_repair":False,"uses_chunks_clean_for_rag":True,
 "performs_independent_rag_per_claim":True,"restricts_retrieval_to_outline_sources":True,
 "validates_all_claims_returned":True,"validates_llm_evidence_against_claim_candidates":True,
}

@dataclass(frozen=True, slots=True)
class Agent07CPreparedInput:
    experiment_id: str
    verified_state_of_art: Mapping[str,Any]
    eligible_claim_ids: tuple[str,...]
    manual_review_claim_ids: tuple[str,...]
    post_correction_reverification_claim_ids: tuple[str,...]
    artifact_payloads: Mapping[str,bytes]
    artifact_hashes: Mapping[str,str]
    optional_artifact_payloads: Mapping[str,bytes]
    optional_artifact_hashes: Mapping[str,str]
    source_draft_fingerprint: str
    prepared_draft_fingerprint: str
    correction_applied_to_copy: bool
    original_draft_modified: bool
    evaluation_ready_emitted: bool
    result_contract_valid: bool
    def to_dict(self): return asdict(self)

def _sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def _csv_rows(raw:bytes)->tuple[list[str],list[dict[str,str]]]:
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")));return list(reader.fieldnames or ()),[dict(r) for r in reader]
def _exact_keys(value:Mapping[str,Any],expected:set[str],code:str)->None:
    if set(value)!=expected:raise ValueError(f"{code}:SCHEMA")
def _section_text_key(section:Mapping[str,Any])->str:
    keys=[k for k in ("section_text","text","content") if isinstance(section.get(k),str)]
    if len(keys)!=1:raise ValueError("AGENT07C_SECTION_TEXT_FIELD_AMBIGUOUS")
    return keys[0]
def _validate_safety(policy:Mapping[str,Any])->None:
    if not isinstance(policy,Mapping):raise ValueError("AGENT07C_SAFETY_POLICY_INVALID")
    for key,expected in REQUIRED_SAFETY_POLICY.items():
        if policy.get(key) is not expected:raise ValueError(f"AGENT07C_SAFETY_POLICY_MISMATCH:{key}")


def validate_original_agent07c_input_artifacts(*, artifact_payloads:Mapping[str,bytes], experiment_id:str)->dict[str,Any]:
    """Executable extraction of the original notebook 07C input gate (cell 3)."""
    missing=sorted(set(AGENT07C_REQUIRED_ARTIFACTS)-set(artifact_payloads))
    if missing:raise ValueError("AGENT07C_REQUIRED_INPUT_MISSING:"+",".join(missing))
    if set(artifact_payloads)!=set(AGENT07C_REQUIRED_ARTIFACTS):raise ValueError("AGENT07C_ARTIFACT_SET_INVALID")
    try:
        verified=json.loads(artifact_payloads["verified_state_of_art.json"])
        report=json.loads(artifact_payloads["verification_validation_report.json"])
        manifest=json.loads(artifact_payloads["verification_traceability_manifest.json"])
    except Exception as exc:raise ValueError("AGENT07C_JSON_INPUT_INVALID") from exc
    for name,obj in (("verified",verified),("validation_report",report),("manifest",manifest)):
        if not isinstance(obj,dict):raise ValueError(f"AGENT07C_{name.upper()}_NOT_OBJECT")
    if report.get("experiment_id")!=experiment_id or manifest.get("experiment_id")!=experiment_id:raise ValueError("AGENT07C_EXPERIMENT_MISMATCH")
    checks=report.get("scientific_handoff_checks")
    if not isinstance(checks,dict) or set(checks)!=set(SCIENTIFIC_HANDOFF_CHECK_NAMES) or any(type(v) is not bool for v in checks.values()):raise ValueError("AGENT07C_SCIENTIFIC_HANDOFF_CHECKS_INVALID")
    if report.get("scientific_handoff_validation_ok") is not all(checks.values()):raise ValueError("AGENT07C_SCIENTIFIC_HANDOFF_GLOBAL_MISMATCH")
    expected_validation=bool(report.get("structural_validation_ok") and report.get("scientific_handoff_validation_ok") and report.get("original_07c_artifact_gate_ok"))
    if report.get("validation_ok") is not expected_validation:raise ValueError("AGENT07C_VALIDATION_REPORT_GLOBAL_MISMATCH")
    if report.get("validation_ok") is not True:raise ValueError("AGENT07C_VALIDATION_REPORT_NOT_OK")
    if not isinstance(report.get("validation_errors"),list) or not isinstance(report.get("validation_warnings"),list):raise ValueError("AGENT07C_VALIDATION_REPORT_SCHEMA_INVALID")
    if manifest.get("validation_report",{}).get("validation_ok") is not True:raise ValueError("AGENT07C_MANIFEST_VALIDATION_NOT_OK")
    workflow=manifest.get("workflow_state")
    if not isinstance(workflow,dict) or workflow.get("verification_completed") is not True or not isinstance(workflow.get("post_correction_recheck_required"),bool):raise ValueError("AGENT07C_MANIFEST_WORKFLOW_INVALID")
    _validate_safety(manifest.get("safety_policy",{}))
    vcols,vrows=_csv_rows(artifact_payloads["verification_report.csv"])
    required={"claim_id","section_id","claim","verdict","confidence","hallucination_risk","correction_needed","evidence_used_ids"}
    if not required.issubset(vcols):raise ValueError("AGENT07C_VERIFICATION_REPORT_COLUMNS_INVALID")
    if not vrows:raise ValueError("AGENT07C_VERIFICATION_REPORT_EMPTY")
    ids=[r["claim_id"].strip() for r in vrows]
    if not all(ids) or len(ids)!=len(set(ids)):raise ValueError("AGENT07C_VERIFICATION_REPORT_CLAIM_IDS_INVALID")
    ccols,crows=_csv_rows(artifact_payloads["auto_corrections_log.csv"])
    if not {"claim_id","section_id","status","action","old_fragment","new_fragment"}.issubset(ccols):raise ValueError("AGENT07C_CORRECTION_LOG_COLUMNS_INVALID")
    unknown=sorted({r["claim_id"].strip() for r in crows if r["claim_id"].strip()}-set(ids))
    if unknown:raise ValueError("AGENT07C_CORRECTION_LOG_UNKNOWN_CLAIM")
    applied=[r for r in crows if r["status"].strip()=="applied"]
    if len([r["claim_id"] for r in applied])!=len({r["claim_id"] for r in applied}):raise ValueError("AGENT07C_MULTIPLE_APPLIED_PER_CLAIM")
    if workflow["post_correction_recheck_required"] != bool(applied):raise ValueError("AGENT07C_RECHECK_FLAG_MISMATCH")
    sections=verified.get("sections")
    if not isinstance(sections,list) or not sections:raise ValueError("AGENT07C_VERIFIED_SECTIONS_INVALID")
    section_ids=[str(s.get("section_id") or s.get("id") or "") for s in sections if isinstance(s,dict)]
    if len(section_ids)!=len(sections) or not all(section_ids) or len(section_ids)!=len(set(section_ids)):raise ValueError("AGENT07C_VERIFIED_SECTION_IDS_INVALID")
    md=artifact_payloads["verified_state_of_art.md"].decode("utf-8")
    for section in sections:
        text=section[_section_text_key(section)]
        if text not in md:raise ValueError("AGENT07C_JSON_MARKDOWN_DIVERGENCE")
    return {"validation_ok":True,"verification_rows":len(vrows),"applied_corrections":len(applied)}

def _validate_prepared_payload(value:Mapping[str,Any],*,allow_unvalidated:bool=False)->dict[str,Any]:
    expected=set(Agent07CPreparedInput.__dataclass_fields__)
    _exact_keys(value,expected,"AGENT07C_PREPARED_INPUT_INVALID")
    if not isinstance(value["experiment_id"],str) or not value["experiment_id"].strip():raise ValueError("AGENT07C_EXPERIMENT_ID_INVALID")
    payloads=value["artifact_payloads"]
    if not isinstance(payloads,Mapping) or set(payloads)!=set(AGENT07C_REQUIRED_ARTIFACTS) or any(not isinstance(v,bytes) for v in payloads.values()):raise ValueError("AGENT07C_ARTIFACT_PAYLOADS_INVALID")
    hashes=value["artifact_hashes"]
    if not isinstance(hashes,Mapping) or set(hashes)!=set(payloads):raise ValueError("AGENT07C_ARTIFACT_HASHES_INVALID")
    for name,raw in payloads.items():
        if hashes[name]!=_sha(raw):raise ValueError("AGENT07C_ARTIFACT_HASH_MISMATCH")
    optional=value["optional_artifact_payloads"]; optional_hashes=value["optional_artifact_hashes"]
    allowed_optional={"hallucination_report.csv","citation_check.csv","claim_atomization_log.csv","manual_review_queue.csv"}
    if not isinstance(optional,Mapping) or set(optional)-allowed_optional or any(not isinstance(v,bytes) for v in optional.values()): raise ValueError("AGENT07C_OPTIONAL_ARTIFACT_PAYLOADS_INVALID")
    if not isinstance(optional_hashes,Mapping) or set(optional_hashes)!=set(optional): raise ValueError("AGENT07C_OPTIONAL_ARTIFACT_HASHES_INVALID")
    for name,raw in optional.items():
        if optional_hashes[name]!=_sha(raw): raise ValueError("AGENT07C_OPTIONAL_ARTIFACT_HASH_MISMATCH")
    validate_original_agent07c_input_artifacts(artifact_payloads=payloads,experiment_id=value["experiment_id"])
    for name in ("eligible_claim_ids","manual_review_claim_ids","post_correction_reverification_claim_ids"):
        seq=value[name]
        if type(seq) not in (tuple,list) or any(not isinstance(x,str) or not x for x in seq) or len(seq)!=len(set(seq)):raise ValueError(f"AGENT07C_{name.upper()}_INVALID")
    if set(value["eligible_claim_ids"])!=set(value["post_correction_reverification_claim_ids"]):raise ValueError("AGENT07C_REVERIFICATION_CLAIM_SET_MISMATCH")
    manifest=json.loads(payloads["verification_traceability_manifest.json"])
    workflow=manifest.get("workflow_state",{})
    expected_manual=tuple(sorted(value["manual_review_claim_ids"]))
    manifest_manual=tuple(sorted(str(x) for x in workflow.get("manual_review_claim_ids",())))
    if manifest_manual!=expected_manual:raise ValueError("AGENT07C_MANUAL_REVIEW_MANIFEST_MISMATCH")
    if bool(expected_manual) is not bool(workflow.get("pending_manual_review",False)):raise ValueError("AGENT07C_MANUAL_REVIEW_FLAG_MISMATCH")
    for name in ("source_draft_fingerprint","prepared_draft_fingerprint"):
        fp=value[name]
        if not isinstance(fp,str) or len(fp)!=64 or any(c not in "0123456789abcdef" for c in fp):raise ValueError(f"AGENT07C_{name.upper()}_INVALID")
    if value["original_draft_modified"] is not False or value["evaluation_ready_emitted"] is not False:raise ValueError("AGENT07C_ISOLATION_INVALID")
    expected_applied=bool(value["eligible_claim_ids"])
    if value["correction_applied_to_copy"] is not expected_applied:raise ValueError("AGENT07C_COPY_APPLICATION_FLAG_MISMATCH")
    if not allow_unvalidated and value["result_contract_valid"] is not True:raise ValueError("AGENT07C_RESULT_CONTRACT_NOT_DERIVED")
    return dict(value)

def validate_agent07c_prepared_input_contract(value:Agent07CPreparedInput|Mapping[str,Any])->dict[str,Any]:
    return _validate_prepared_payload(value.to_dict() if isinstance(value,Agent07CPreparedInput) else value)

def create_agent07c_prepared_input(**kwargs:Any)->Agent07CPreparedInput:
    if "result_contract_valid" in kwargs:raise TypeError("result_contract_valid is derived")
    provisional=Agent07CPreparedInput(result_contract_valid=False,**kwargs)
    normalized=_validate_prepared_payload(provisional.to_dict(),allow_unvalidated=True)
    normalized["result_contract_valid"]=True
    final=Agent07CPreparedInput(**normalized)
    validate_agent07c_prepared_input_contract(final)
    return final

