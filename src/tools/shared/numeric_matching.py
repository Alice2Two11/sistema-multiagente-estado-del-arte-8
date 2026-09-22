"""Contrato ÚNICO y compartido de coincidencia de literales numéricos dentro
de un texto, con límites de token explícitos vía regex.

Antes existían implementaciones independientes que hacían una comparación de
subcadena ingenua tras solo cambiar coma por punto -- ``"12" in "512"`` daba
``True`` -- en ``tools/draft_writing/validation.py::number_exists_in_text`` y
en ``tools/quantitative_extraction/evidence_verification.py::
numeric_token_found``/``value_found_in_text``. Esta es la reescritura única
(originalmente ``tools/draft_writing/numeric_literals.py``, promovida aquí
para que ambas etapas la importen en vez de reimplementar la comparación):
equivalencia coma/punto decimal, manejo correcto de porcentajes (un valor con
``%`` solo hace match contra un token con ``%`` en el texto, y viceversa), y
límites de palabra que impiden que un literal corto haga match dentro de uno
más largo.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_NUMERIC_VALUE_RE = re.compile(
    r"^\s*(?P<sign>[+-]?)(?P<integer>\d+)(?:[.,](?P<fraction>\d+))?(?P<percent>\s*%)?\s*$"
)


@dataclass(frozen=True)
class NumericLiteral:
    sign: str
    integer: str
    fraction: str | None
    is_percentage: bool

    @property
    def canonical_value(self) -> str:
        decimal = self.integer
        if self.fraction is not None:
            decimal = f"{decimal}.{self.fraction}"
        if self.sign:
            decimal = f"{self.sign}{decimal}"
        return f"{decimal}%" if self.is_percentage else decimal


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def parse_numeric_literal(value: Any) -> NumericLiteral | None:
    match = _NUMERIC_VALUE_RE.fullmatch(_safe_text(value))
    if match is None:
        return None
    return NumericLiteral(
        sign=match.group("sign") or "",
        integer=match.group("integer"),
        fraction=match.group("fraction"),
        is_percentage=bool(match.group("percent")),
    )


def _literal_pattern(literal: NumericLiteral) -> re.Pattern[str]:
    sign = re.escape(literal.sign)
    integer = re.escape(literal.integer)
    decimal = integer
    if literal.fraction is not None:
        decimal = rf"{integer}[.,]{re.escape(literal.fraction)}"

    percentage = r"\s*%" if literal.is_percentage else r"(?!\s*%)"
    return re.compile(
        rf"(?<![\w.,]){sign}{decimal}{percentage}(?![\w.,])"
    )


def numeric_literal_exists_in_text(value: Any, text: Any) -> bool:
    """
    Match a numeric literal as a complete token.

    Decimal comma and decimal point are treated as equivalent. Percentage
    values only match percentage tokens, and non-percentage values do not
    match percentage tokens. No semantic conversions, rounding or unit
    transformations are performed.
    """
    literal = parse_numeric_literal(value)
    if literal is None:
        return False
    return _literal_pattern(literal).search(_safe_text(text)) is not None


def numeric_token_exists_in_text(token: Any, text: Any) -> bool:
    """Same token-bounded matching as :func:`numeric_literal_exists_in_text`,
    for a single numeric token already extracted from a larger value (e.g.
    one of several numbers embedded in a range or a compound value). Falls
    back to the previous casefold substring behaviour only when ``token``
    cannot be parsed as a numeric literal -- this should not normally happen
    for tokens produced by a numeric-extraction regex, but stays fail-safe
    rather than silently dropping a candidate match."""
    literal = parse_numeric_literal(token)
    if literal is not None:
        return _literal_pattern(literal).search(_safe_text(text)) is not None
    return _safe_text(token).strip().casefold() in _safe_text(text).casefold()
