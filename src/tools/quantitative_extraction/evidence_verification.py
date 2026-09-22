from __future__ import annotations
from .input_validation import safe_str
from .normalization import extract_numeric_tokens
from .source_context import get_source_chunk_context
from src.tools.shared.numeric_matching import numeric_token_exists_in_text

def numeric_token_found(value,text):
    """Coincidencia de cada literal numérico embebido en ``value`` con
    límites de token explícitos (ver ``src/tools/shared/numeric_matching.py``)
    -- antes era una comparación de subcadena ingenua (``casefold`` sin
    límites), la misma consolidada en ``draft_writing/validation.py::
    number_exists_in_text``, para que ambas etapas usen el mismo criterio de
    "número soportado por la evidencia"."""
    tokens=extract_numeric_tokens(value)
    return bool(tokens) and all(numeric_token_exists_in_text(token,text) for token in tokens)

def value_found_in_text(value,text):
    value=safe_str(value).strip(); text=safe_str(text)
    return bool(value) and (value.casefold() in text.casefold() or numeric_token_found(value,text))

def verify_quantitative_rows(rows, *, kb_rows_by_source, chunks, allow_all_clean_chunks_fallback):
    verified=[]
    for row in rows:
        source=row["source_filename"]; kb_row=kb_rows_by_source[source]
        from .prompting import compact_row_text
        kb_text=compact_row_text(kb_row); context=get_source_chunk_context(kb_row,chunks,allow_all_clean_chunks_fallback=allow_all_clean_chunks_fallback)
        in_kb=value_found_in_text(row["value"],kb_text); in_chunk=value_found_in_text(row["value"],context["text"])
        status="confirmed_in_source_chunk" if in_chunk else ("found_only_in_kb_text" if in_kb else "not_confirmed")
        row=dict(row); row.update({"value_found_in_kb_text":in_kb,"value_found_in_source_chunk":in_chunk,"source_chunk_scope":context["scope"],"source_chunk_ids_checked":";".join(context["chunk_ids"]),"verification_status":status}); verified.append(row)
    return verified
