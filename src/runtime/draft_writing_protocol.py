from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone
from src.state.fingerprints import build_stage_fingerprints
from src.contracts.agent_result import *
@dataclass(frozen=True)
class DraftWritingTransactionResult:prepare:object;agent_result:object;persisted_result_path:str;committed_state:object
def build_draft_fingerprints(agent_input):return build_stage_fingerprints(input_data={'experiment_id':agent_input.experiment_id,'run_id':agent_input.run_id,'stage_name':agent_input.stage_name,'attempt_number':agent_input.attempt_number},config_data=dict(agent_input.policy),dependencies_data={k:v.to_dict() for k,v in agent_input.dependencies.items()})
def resolve_draft_resume(*,store,agent_input,observations=None):return store.resolve_resume(stage_name=agent_input.stage_name,fingerprints=build_draft_fingerprints(agent_input),observations=dict(observations or {}))
