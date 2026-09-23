from __future__ import annotations
import json
import re
from .retrieval import safe_str


# Conectores que disparan la regla 11 (dividir oraciones compuestas
# verificables). Se reutiliza tanto para redactar la instrucción como
# para validar que un ejemplo generado dinámicamente sí contenga uno.
RULE_11_CONNECTORS = ("aunque", "a pesar de", "sin embargo", "mientras que", "pero")

# Ejemplo estático de respaldo: deliberadamente neutral (sin vocabulario
# de ningún dominio real de evaluación), usado cuando no hay un ejemplo
# dinámico válido disponible en policy["dynamic_split_example"] (falló
# la llamada al LLM, falló la validación, o policy no lo trae porque
# viene de una versión anterior).
_STATIC_RULE_11_MAL = (
    'Aunque el enfoque propuesto por los autores obtuvo mejores\n'
    '      resultados que el método de referencia, su aplicabilidad se ve\n'
    '      limitada por el tamaño reducido de la muestra utilizada.'
)
_STATIC_RULE_11_BIEN = (
    'El enfoque propuesto por los autores obtuvo mejores\n'
    '        resultados que el método de referencia.',
    'La aplicabilidad del enfoque propuesto se ve limitada por\n'
    '        el tamaño reducido de la muestra utilizada.',
)


def build_dynamic_split_example_prompt(topic):
    """Prompt para generar, UNA vez por experimento, un ejemplo MAL/BIEN
    de la regla 11 con vocabulario del tema real de la corrida -- nunca
    con datos verificables (cifras, datasets, nombres de algoritmos
    reales), solo para dar sabor léxico. Nunca se usa como evidencia:
    el resultado se valida con validate_dynamic_split_example() antes
    de insertarse en build_section_prompt_v2(); si falla, se descarta
    en favor del ejemplo estático neutral."""
    topic_text = safe_str(topic) or "un tema científico general"
    return f"""
Vas a escribir un ejemplo DIDÁCTICO, completamente FICTICIO, para
enseñarle a otro modelo de lenguaje una regla de estilo. NO estás
redactando contenido real de ningún estado del arte.

TEMA GENERAL (solo para dar vocabulario apropiado, NO para afirmar nada
verificable sobre él): {topic_text}

TAREA: escribe UNA oración de ejemplo que combine, en una sola frase,
una afirmación de EFICACIA/VENTAJA y una afirmación de LIMITACIÓN,
unidas por uno de estos conectores: "aunque", "a pesar de", "sin
embargo", "mientras que" o "pero". Luego, la MISMA idea dividida en dos
oraciones independientes (una por afirmación).

PROHIBICIONES ESTRICTAS (el ejemplo es ilustrativo, no un hallazgo
real):
- NO uses ningún número, cifra, porcentaje, ni valor cuantitativo.
- NO nombres un algoritmo, método, dataset, autor, año o herramienta
  real y específico (nada de "SVM", "Random Forest", "BERT", "EU ETS",
  nombres de datasets, etc.) -- usa referencias genéricas como "el
  enfoque propuesto", "el método analizado", "la técnica estudiada".
- NO uses corchetes de cita ni ningún identificador técnico.
- El ejemplo debe sonar temáticamente relacionado con el tema general
  dado arriba (para que el vocabulario no sea genérico al punto de
  parecer de otro campo), pero sin afirmar ningún hecho verificable.

Devuelve ÚNICAMENTE este JSON, sin texto antes ni después, sin fences
de markdown:
{{
  "mal": "<la oración compuesta de ejemplo, con el conector>",
  "bien": [
    "<primera oración independiente, solo la afirmación de eficacia>",
    "<segunda oración independiente, solo la afirmación de limitación>"
  ]
}}
""".strip()


def validate_dynamic_split_example(example):
    """Chequeo determinístico (sin LLM) del ejemplo generado
    dinámicamente -- rechaza cualquier cosa que se parezca a un hecho
    verificable o a evidencia real. Devuelve True solo si el ejemplo es
    seguro para insertarse en el prompt de la 06."""
    if not isinstance(example, dict):
        return False
    mal = example.get("mal")
    bien = example.get("bien")
    if not isinstance(mal, str) or not mal.strip():
        return False
    if not isinstance(bien, list) or len(bien) != 2:
        return False
    if not all(isinstance(s, str) and s.strip() for s in bien):
        return False

    combined = mal + " " + " ".join(bien)

    # Nada de cifras, porcentajes ni corchetes de cita/evidencia.
    if re.search(r"\d", combined):
        return False
    if "%" in combined or "[" in combined or "]" in combined:
        return False

    # El "mal" debe realmente contener uno de los conectores objetivo
    # (si no, no ilustra la regla que queremos enseñar).
    mal_lower = mal.casefold()
    if not any(connector in mal_lower for connector in RULE_11_CONNECTORS):
        return False

    # Longitud razonable -- ni vacío ni desproporcionado.
    if len(mal) > 400 or any(len(s) > 250 for s in bien):
        return False

    return True


def render_rule_11_example(policy):
    """Devuelve el bloque MAL/BIEN ya formateado para insertar en la
    regla 11 del prompt. Usa policy["dynamic_split_example"] si existe
    y pasa validate_dynamic_split_example(); si no, cae al ejemplo
    estático neutral -- nunca deja la regla sin ejemplo."""
    dynamic = policy.get("dynamic_split_example")
    if isinstance(dynamic, dict) and validate_dynamic_split_example(dynamic):
        mal = dynamic["mal"]
        bien = dynamic["bien"]
    else:
        mal = _STATIC_RULE_11_MAL
        bien = _STATIC_RULE_11_BIEN
    bien_block = ",\n".join(f'        "{s}"' for s in bien)
    return mal, bien_block


def language_instruction(output_language):
    normalized = safe_str(output_language).casefold()
    if normalized in {"es", "español", "espanol", "spanish"}:
        return "Redacta en español académico."
    if normalized in {"en", "inglés", "ingles", "english"}:
        return "Write in academic English."
    return f"Redacta todos los campos en {output_language}."


def assign_section_budgets(outline_sections, target_total_words):
    section_count = max(len(outline_sections), 1)
    base_target = max(80, int(int(target_total_words) / section_count))
    budgets = {}
    for section in outline_sections:
        section_id = safe_str(section.get("section_id"))
        budgets[section_id] = {
            "target_words": base_target,
            "minimum_words": max(50, int(base_target * 0.65)),
            "maximum_words": max(90, int(base_target * 1.40)),
        }
    return budgets


def build_source_free_organizational_section(section, output_language="español"):
    section_id = safe_str(section.get("section_id"))
    section_title = safe_str(section.get("section_title"))
    normalized_language = safe_str(output_language).casefold()
    if normalized_language in {"es", "español", "espanol", "spanish", "español académico"}:
        text = (
            "Esta sección presenta el alcance y la organización de la revisión. "
            "Su función es orientar la lectura y establecer la transición hacia "
            "el análisis de la evidencia científica desarrollado en las secciones siguientes."
        )
    elif normalized_language in {"en", "inglés", "ingles", "english", "academic english"}:
        text = (
            "This section presents the scope and organization of the review. "
            "Its purpose is to guide the reader and establish the transition toward "
            "the evidence-based analysis developed in the following sections."
        )
    else:
        raise ValueError(f"No existe una plantilla organizativa segura para el idioma de salida {output_language!r}.")
    return {
        "section_id": section_id,
        "section_title": section_title,
        "draft_text": text,
        "claims": [],
        "generation_attempt": 0,
        "section_validation": {
            "validation_ok": True,
            "errors": [],
            "citation_errors": [],
            "claim_errors": [],
            "numeric_errors": [],
            "valid_citation_count": 0,
            "substantive_sentence_count": 0,
            "source_free_organizational_section": True,
        },
        "deterministic_normalization": {
            "applied": True,
            "normalization_version": "v3_source_free_organizational_template",
            "source_free_organizational_section": True,
            "reason": "No evidence assigned by outline and section type permits an organizational introduction or conclusion.",
        },
    }


# ------------------------------------------------------------------
# Síntesis de secciones organizativas (introducción/conclusión/gaps/
# discusión) a partir del CONTENIDO PROPIO del estado del arte -- en
# vez del texto genérico fijo de build_source_free_organizational_section
# (idéntico en toda corrida, sin relación con el tema real) y en vez de
# someter estas secciones al mismo ciclo de recuperación adaptativa que
# las secciones con evidencia real (que compite por el mismo pool de
# papers con el mismo umbral de cobertura léxica -- diagnóstico real,
# experimento_paper_51: introducción/conclusión con evidence=[] tras
# agotar rondas, resultando siempre en el mismo texto fijo). Nunca
# inventa hallazgos ni cita evidencia -- solo sintetiza, en prosa,
# lo que ya está en las otras secciones del propio documento (ya
# redactadas) o, si aún no existen (típico de la introducción, que se
# procesa antes que el resto), en la propia planificación del esquema
# (título/propósito/argumentos clave/evidencia buscada -- ver
# build_section_query). Fail-safe en cada paso: cualquier fallo (LLM,
# forma inesperada de la respuesta, validación determinística) hace que
# el llamador (DraftWritingAgent._build_organizational_section) caiga
# al template estático histórico -- nunca deja una sección sin texto.
# ------------------------------------------------------------------

_ORGANIZATIONAL_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_ORGANIZATIONAL_NUMERIC_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*%?")


def _organizational_role(section):
    """Clasificación puramente textual (no normativa -- solo decide QUÉ
    instrucción de rol usar en el prompt de síntesis, nunca si la
    sección es o no source-free, eso lo sigue decidiendo exclusivamente
    section_source_requirement.py)."""
    haystack = (
        safe_str(section.get("section_type")) + " " + safe_str(section.get("section_title"))
    ).casefold()
    if any(token in haystack for token in ("conclu", "cierre", "closing")):
        return "conclusion"
    if any(token in haystack for token in ("introdu",)):
        return "introduccion"
    if any(token in haystack for token in ("gap", "vacio", "vací")):
        return "gaps"
    if any(token in haystack for token in ("discus",)):
        return "discusion"
    return "organizativa"


_ORGANIZATIONAL_ROLE_INSTRUCTIONS = {
    "introduccion": (
        "Escribe una INTRODUCCIÓN real para este estado del arte: presenta "
        "el problema general y por qué es relevante, y anticipa, en un par "
        "de frases, los grandes bloques temáticos que cubrirán las secciones "
        "listadas abajo (usa su contenido como guía temática, sin "
        "enumerarlas una por una como una lista)."
    ),
    "conclusion": (
        "Escribe una CONCLUSIÓN real para este estado del arte: retoma "
        "EXPLÍCITAMENTE 2 o 3 hallazgos concretos ya presentados en las "
        "secciones resumidas abajo (si alguno incluye una cifra concreta -- "
        "ej. una métrica de precisión -- cópiala EXACTAMENTE como aparece en "
        "el contexto, nunca la inventes ni la redondees), sintetiza en tus "
        "propias palabras la tensión o el patrón que esos hallazgos "
        "comparten, y cierra señalando hacia dónde apunta el trabajo futuro "
        "del área -- sin inventar ningún hallazgo, cifra o comparación que "
        "no esté ya reflejada en esos resúmenes."
    ),
    "gaps": (
        "Sintetiza, en tus propias palabras, los vacíos y limitaciones que "
        "ya emergen de las secciones resumidas abajo -- sin inventar ningún "
        "vacío que no esté reflejado en ellas."
    ),
    "discusion": (
        "Sintetiza, en tus propias palabras, la discusión general que se "
        "desprende de las secciones resumidas abajo -- sin inventar ningún "
        "argumento que no esté reflejado en ellas."
    ),
    "organizativa": (
        "Escribe un párrafo organizativo/de transición para esta sección, "
        "coherente con el resto del documento resumido abajo."
    ),
}


def build_organizational_context_block(context_sections):
    """Arma el bloque CONTEXTO compartido por el prompt de síntesis
    (``build_organizational_synthesis_prompt``) y por la validación
    determinística (``validate_organizational_synthesis``) -- ambos deben
    ver EXACTAMENTE el mismo texto (incluido el truncado a 600 caracteres
    por sección) para que una cifra que el LLM copia del contexto real
    nunca sea rechazada por no encontrarse en un texto distinto al que de
    verdad se le mostró."""
    return "\n\n".join(
        f"- {safe_str(ctx.get('section_title'))}: {safe_str(ctx.get('text'))[:600]}"
        for ctx in context_sections
        if safe_str(ctx.get("text")).strip()
    ) or (
        "(No hay otras secciones disponibles todavía; usa únicamente el "
        "título de esta sección como guía temática.)"
    )


def build_organizational_synthesis_prompt(section, context_sections, output_language="español"):
    """``context_sections`` es una lista de ``{"section_title", "text"}``
    de las DEMÁS secciones del esquema: ``text`` es el ``draft_text`` real
    si esa sección ya fue redactada (permite una síntesis genuina, sobre
    todo en conclusión/discusión/gaps), o la descripción de planificación
    del esquema (``build_section_query``) si todavía no existe (típico de
    la introducción)."""
    section_title = safe_str(section.get("section_title"))
    role_instruction = _ORGANIZATIONAL_ROLE_INSTRUCTIONS[_organizational_role(section)]
    context_block = build_organizational_context_block(context_sections)
    return f"""
Eres el agente redactor de un sistema multiagente para estados del arte
científicos, escribiendo AHORA la sección organizativa "{section_title}".

{role_instruction}

REGLAS ESTRICTAS:
1. Si necesitas retomar una cifra o dato cuantitativo para tu síntesis,
   ÚSALA EXACTAMENTE como aparece en el CONTEXTO de abajo -- nunca
   inventes, redondees ni calcules un valor nuevo que no esté ya ahí.
   Si no hay ninguna cifra relevante en el contexto, no uses ninguna.
2. NO uses corchetes de cita (ej. "[archivo.pdf | chunk_0001]") ni ningún
   identificador técnico -- esta sección NO tiene evidencia asignada y no
   debe simular que la tiene, ni siquiera copiando uno del contexto.
3. NO nombres ningún autor, dataset, algoritmo o herramienta específica
   que no aparezca ya mencionada en el contexto de abajo.
4. NO inventes ningún hallazgo, comparación o resultado nuevo -- solo
   sintetiza lo que ya está reflejado en el contexto.
5. {language_instruction(output_language)}
6. Devuelve ÚNICAMENTE el texto de la sección, en prosa continua (sin
   títulos, sin listas, sin JSON, sin comillas envolventes).

CONTEXTO (otras secciones del mismo estado del arte, ya redactadas o
planeadas):
{context_block}

Extensión objetivo: 3 a 6 oraciones.
""".strip()


def extract_plain_text_response(raw):
    """Extrae el texto plano de una respuesta cruda del LLM -- mismo
    desempaquetado de ``content``/bloques de proveedor (Anthropic/OpenAI)
    que ``DraftWritingRuntime.parse()``, pero SIN forzar un parseo JSON
    (aquí se espera prosa libre, no ``{"section_id": ...}``). Nunca
    lanza -- ante una forma inesperada cae a ``str(raw)``, dejando que
    ``validate_organizational_synthesis`` decida si el resultado es
    aceptable."""
    content = getattr(raw, "content", raw)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                block_text = block.get("text")
                if isinstance(block_text, str):
                    parts.append(block_text)
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts)
    if not isinstance(content, str):
        content = str(content)
    return content.strip()


def validate_organizational_synthesis(text, context_text=""):
    """Guardia determinística (sin LLM), SIEMPRE aplicada antes de
    aceptar un texto organizativo sintetizado por el LLM -- si falla, el
    llamador cae al template estático fijo
    (``build_source_free_organizational_section``), nunca deja pasar
    texto sin revisar.

    Corchetes de cita: SIEMPRE rechazados (evidencia simulada, prohibida
    en una sección sin evidencia asignada, ni siquiera copiando uno del
    contexto).

    Cifras: ya NO se rechazan en bloque -- se permite que la conclusión
    retome un hallazgo cuantitativo real (ej. una métrica de precisión ya
    mencionada en el cuerpo del documento), pero SOLO si cada token
    numérico del texto aparece, LITERAL, dentro de ``context_text`` (el
    mismo bloque CONTEXTO que se le mostró al LLM --
    ``build_organizational_context_block``). Cualquier cifra que no esté
    ahí se trata como inventada y rechaza el texto completo. Si no se pasa
    ``context_text`` (compatibilidad con llamadores antiguos), se vuelve
    al comportamiento estricto original: cualquier cifra rechaza.

    También exige una longitud razonable (ni vacío ni desproporcionado)."""
    if not isinstance(text, str):
        return False
    cleaned = text.strip()
    if not cleaned:
        return False
    if _ORGANIZATIONAL_BRACKET_RE.search(cleaned):
        return False
    numeric_tokens = _ORGANIZATIONAL_NUMERIC_TOKEN_RE.findall(cleaned)
    if numeric_tokens:
        context_text = safe_str(context_text)
        if not context_text:
            return False
        if any(token not in context_text for token in numeric_tokens):
            return False
    word_count = len(cleaned.split())
    if word_count < 15 or word_count > 220:
        return False
    return True


def build_llm_synthesized_organizational_section(section, text):
    """Misma forma de salida que ``build_source_free_organizational_
    section`` (consumida idénticamente por build_draft_reports/
    validate_draft_global -- ``source_free_organizational_section: True``
    exime del chequeo de citas/densidad y de rango de palabras), pero con
    el texto sintetizado a partir del propio documento en vez del template
    fijo."""
    return {
        "section_id": safe_str(section.get("section_id")),
        "section_title": safe_str(section.get("section_title")),
        "draft_text": text.strip(),
        "claims": [],
        "generation_attempt": 0,
        "section_validation": {
            "validation_ok": True,
            "errors": [],
            "citation_errors": [],
            "claim_errors": [],
            "numeric_errors": [],
            "valid_citation_count": 0,
            "substantive_sentence_count": 0,
            "source_free_organizational_section": True,
        },
        "deterministic_normalization": {
            "applied": True,
            "normalization_version": "v4_llm_synthesized_organizational_section",
            "source_free_organizational_section": True,
            "reason": (
                "No evidence assigned by outline; section synthesized from "
                "the state-of-the-art's own generated/planned content "
                "instead of the fixed generic template."
            ),
        },
    }


def build_section_prompt_v2(section, evidence, quantitative_context, previous_errors, policy):
    """Prompt del contrato canonical_sentences_v2 (Fase 3, evidence
    handles) -- SEPARADO por completo de ``build_section_prompt``
    (legacy), nunca lo reutiliza ni comparte texto de reglas con él.
    El LLM produce EXCLUSIVAMENTE ``{"section_id": ..., "sentences":
    [...]}`` -- nunca ``draft_text``/``claims`` directamente (eso lo
    deriva el sistema, determinísticamente, en
    ``materialize_initial_section_v2``).

    Evidence handles: el LLM NUNCA escribe ``source_filename``/
    ``chunk_id``/``supporting_citations``/strings ``[source | chunk]``
    -- solo referencia evidencia mediante identificadores opacos
    (``"E1"``, ``"E2"``, ...) que el SISTEMA asignó determinísticamente
    (``build_evidence_handle_map``, ``canonical_sentences.py``, mismo
    orden que ``evidence``) antes de construir este prompt. El LLM ve
    cada evidencia numerada con su ``source_filename``/``chunk_id``/
    ``text`` reales -- pero solo puede DEVOLVER el número, nunca los
    identificadores técnicos en sí. Esto elimina estructuralmente la
    posibilidad de que el LLM invente o combine un ``source_filename``
    con un ``chunk_id`` que no correspondan juntos: no existe ningún
    campo de salida donde pueda escribir esos valores.

    Prohibiciones explícitas en el propio prompt: el LLM NO debe
    producir ``supporting_citations``/``source_filename``/``chunk_id``/
    ``claim``/``claim_id``/``claim_uid``/``sentence_id``/
    ``identity_action``/``parent_claim_uids`` en ningún elemento de
    ``sentences[]`` -- el sistema los asigna/resuelve después
    (``validate_and_parse_sentences_v2`` rechaza explícitamente
    cualquiera de estos si el LLM los envía)."""

    section_id = safe_str(section.get("section_id"))
    evidence_handles = [
        {"handle": f"E{i + 1}", "source_filename": row["source_filename"], "chunk_id": row["chunk_id"], "text": row.get("text", "")}
        for i, row in enumerate(evidence)
    ]
    budgets = policy.get("section_budgets") or assign_section_budgets(
        policy.get("outline_sections") or [section],
        policy["target_total_words"],
    )
    budget = budgets[section_id]
    rule_11_mal, rule_11_bien_block = render_rule_11_example(policy)
    return f"""
Eres el agente redactor de un sistema multiagente para estados del arte científicos.

CONTRATO DE SALIDA: canonical_sentences_v2 -- produces ÚNICAMENTE una
lista de oraciones estructuradas, NUNCA texto de sección ni claims
directamente. El sistema construye el borrador final a partir de lo
que devuelvas -- tu única responsabilidad es el CONTENIDO de cada
oración y a QUÉ evidencia (por número) corresponde.

REGLAS:
1. Usa exclusivamente la evidencia proporcionada en EVIDENCIA_DISPONIBLE.
2. No uses conocimiento externo ni Ground Truth.
3. No referencies ningún número de evidencia (handle) fuera de los
   listados en EVIDENCIA_DISPONIBLE. El handle más alto disponible es
   "E{len(evidence_handles)}" -- NO EXISTE ningún handle mayor a ese
   número (nunca "E{len(evidence_handles) + 1}" ni superior), aunque el
   texto de la evidencia contenga números de cita propios del paper
   original (ej. "[45]", "[3]") -- esos números NO son handles, son
   parte del contenido citado y nunca deben confundirse con
   "supporting_evidence_ids".
4. No inventes autores, años, datasets, métricas, valores ni resultados.
5. No sustituyas un handle de evidencia por otro.
6. El estilo bibliográfico {policy.get('citation_style', '')} no autoriza inventar autores o años.
7. {language_instruction(policy.get('output_language', 'español académico'))}
8. Modo de escritura: {policy.get('writing_mode', '')}. Enfoque: {policy.get('focus_mode', '')}.
9. Extensión objetivo: {budget['target_words']} palabras;
   rango orientativo: {budget['minimum_words']}-{budget['maximum_words']}.
10. UNA oración por elemento de "sentences" -- nunca combines dos
    oraciones en un solo "text", nunca dejes un "text" vacío.
11. Si una idea combina varias afirmaciones distintas unidas por
    conectores como "aunque", "a pesar de", "sin embargo", "mientras
    que", "pero", divide cada afirmación verificable en un elemento de
    "sentences" separado, cada uno con su propio handle de evidencia.
    Ejemplo de lo que NUNCA debes hacer (una sola oración mezclando
    eficacia y limitación -- el patrón es estructural/gramatical, no
    depende del tema del que trate el estado del arte):
      MAL: "{rule_11_mal}"
    En su lugar, divide SIEMPRE en dos oraciones independientes, cada
    una con el/los handles que la respaldan específicamente a ELLA:
      BIEN: [
{rule_11_bien_block}
      ]
    Esta regla es obligatoria, no opcional: cualquier oración que
    contenga "aunque", "a pesar de", "sin embargo", "mientras que" o
    "pero" uniendo dos ideas verificables por separado debe dividirse
    -- sin excepción, incluso si la evidencia disponible respalda
    ambas partes.
12. "text" contiene ÚNICAMENTE el texto de la oración -- SIN ningún
    identificador técnico ni número de evidencia dentro. Nunca escribas
    "source_filename", "chunk_id", corchetes de cita, ni el propio
    handle (ej. "E1") dentro de "text".
13. "supporting_evidence_ids" solo puede contener HANDLES (los números
    "E1", "E2", ... tal como aparecen en EVIDENCIA_DISPONIBLE) -- NUNCA
    el source_filename ni el chunk_id en sí. Un handle que no exista en
    EVIDENCIA_DISPONIBLE invalida la respuesta completa.
14. Un valor numérico solo puede escribirse si aparece literalmente en
    el texto de uno de los handles de evidencia citados por esa misma
    oración.
15. Toda oración con contenido factual/científico debe llevar al menos
    un handle en "supporting_evidence_ids". Omite cualquier oración que
    no tenga evidencia documental real.
16. Cuando dos o más evidencias de EVIDENCIA_DISPONIBLE reporten
    resultados cuantitativos comparables para el mismo problema (ej.
    accuracy, F1, precisión, tiempo de entrenamiento, tamaño de
    modelo), redacta al menos una oración que los contraste
    EXPLÍCITAMENTE citando ambos handles juntos -- nunca te limites a
    mencionar cada resultado por separado en oraciones distintas sin
    conectarlos. El contraste debe seguir siendo UNA sola oración
    verificable con sus propios handles (regla 10/11: si la
    comparación combina una ventaja y una limitación con conectores
    como "aunque" o "mientras que", sigue dividiéndola en dos
    oraciones, cada una con el contraste que le corresponde). No
    inventes un tercer valor para la comparación -- usa únicamente los
    números que aparecen literalmente en la evidencia citada (regla
    14).
17. PROHIBIDO incluir en cualquier elemento de "sentences" los campos:
    "supporting_citations", "source_filename", "chunk_id", "claim",
    "claim_id", "claim_uid", "sentence_id", "identity_action",
    "parent_claim_uids". El sistema los asigna/resuelve después -- si
    los incluyes, la respuesta completa será rechazada.
18. Devuelve ÚNICAMENTE JSON válido -- sin fences de Markdown (nunca
    ```json ni ```), sin texto antes ni después del JSON.

FORMATO EXACTO (el único permitido):
{{
  "section_id": "{section_id}",
  "sentences": [
    {{
      "text": "Una sola oración, sin identificadores técnicos dentro.",
      "supporting_evidence_ids": ["E1"]
    }}
  ]
}}

SECCIÓN DEL ESQUEMA:
{json.dumps(section, ensure_ascii=False, indent=2)}

EVIDENCIA_DISPONIBLE (referencia cada una ÚNICAMENTE por su "handle" -- nunca por source_filename/chunk_id).
Hay EXACTAMENTE {len(evidence_handles)} evidencias disponibles, numeradas "E1" a "E{len(evidence_handles)}".
No existe "E{len(evidence_handles) + 1}" ni ningún handle posterior -- si necesitas respaldar una idea y ninguno de estos {len(evidence_handles)} handles la respalda, omite esa oración en vez de inventar un handle:
{json.dumps(evidence_handles, ensure_ascii=False, indent=2)}

CONTEXTO CUANTITATIVO CONFIRMADO:
{json.dumps(quantitative_context, ensure_ascii=False, indent=2)}

ERRORES DE UN INTENTO ANTERIOR:
{json.dumps(previous_errors or [], ensure_ascii=False, indent=2)}
""".strip()
