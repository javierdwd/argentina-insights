"""Compact endpoint catalog for the in-process proxy.

Built from two sources:
  1. The ArgentinaDatos OpenAPI spec — upstream paths and their real params.
  2. ``proxy/routes.py`` — the synthetic routes and query params the proxy
     adds on top (``/actas/id/{actaId}``, ``fields``, ``title``, ``province``,
     ``active``, ``vote``, …).

The catalog therefore describes what the agent can actually call, which is
the proxy surface, not raw upstream.  Loaded once at module import; the LLM
never receives the OpenAPI JSON, only the compact per-domain rendering.

Token budget reference (measured as of 2026-09):
  Full OpenAPI JSON        ~108 k chars
  Politics subset          ~  4 k chars
  Finance subset           ~  3 k chars
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .proxy.routes import (
    EXTERNAL_ROUTES,
    PARAM_BY_NAME,
    SYNTHETIC_ROUTES,
    ParamSpec,
    params_for,
)

_OPENAPI_PATH = (
    Path(__file__).parent.parent.parent / "argentina-datos" / "openapi.json"
)

# Path-prefix → domain mapping (first match wins).
_DOMAIN_PREFIXES: list[tuple[str, str]] = [
    ("/v1/finanzas/", "finance"),
    ("/v1/cotizaciones/", "finance"),
    ("/v1/bcra/", "finance"),
    ("/v1/cammesa", "finance"),
    ("/v1/rem", "finance"),
    ("/v1/series", "finance"),
    ("/v1/senado/", "politics"),
    ("/v1/diputados/", "politics"),
    ("/v1/politica/", "politics"),
    ("/v1/presidentes", "politics"),
    ("/v1/clima/", "other"),
    ("/v1/historico/", "other"),
    ("/v1/wiki/", "other"),
    ("/v1/cine/", "other"),
]

# Always appended to every *narrow* domain catalog. Unused when domain is
# ``data`` / ``unknown`` (full list). Kept so legacy finance/politics filters
# still surface presidents for FX×term joins; clima for date/province crosses.
_CROSS_CUTTING_PATHS: frozenset[str] = frozenset(
    {
        "/v1/presidentes",
        "/v1/clima/historico",
        "/v1/clima/pronostico",
        "/v1/clima/actual",
        "/v1/historico/dias",
        "/v1/historico/dia",
        "/v1/wiki/summary",
        "/v1/cine/discover",
        "/v1/cine/search",
        "/v1/cine/pelicula/{id}",
        "/v1/cine/persona/search",
        "/v1/cine/persona/{id}",
        "/v1/cine/persona/{id}/filmografia",
    }
)

# Enums wider than this are truncated in prompt text (full values stay in memory).
_MAX_ENUM_SIZE = 12


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class Param:
    name: str
    location: str  # "path" | "query" | "header" | "client"
    required: bool
    type: str  # "string" | "integer" | "number" | "boolean"
    enum: list[str] | None = None
    example: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "in": self.location,
            "required": self.required,
            "type": self.type,
        }
        if self.enum:
            d["enum"] = self.enum
        if self.example:
            d["example"] = self.example
        return d


@dataclass
class Operation:
    id: str
    path: str
    domain: str  # "finance" | "politics" | "other"
    summary: str
    params: list[Param] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "domain": self.domain,
            "summary": self.summary,
            "params": [p.to_dict() for p in self.params],
        }


# ── Catalog ───────────────────────────────────────────────────────────────────


class Catalog:
    def __init__(self, operations: list[Operation]) -> None:
        self._all = operations
        self._by_path: dict[str, Operation] = {op.path: op for op in operations}
        self._matchers = _build_matchers(operations)

    # ── Queries ───────────────────────────────────────────────────────────────

    def for_domain(self, domain: str) -> list[Operation]:
        """Return operations for *domain*.

        ``data`` / ``unknown`` / ``other`` → full catalog (respond's default).
        ``finance`` / ``politics`` → that slice plus cross-cutting paths.
        """
        if domain in ("data", "unknown", "other", ""):
            return self._all
        primary = [op for op in self._all if op.domain == domain]
        seen = {op.path for op in primary}
        extra = [
            op for op in self._all
            if op.path in _CROSS_CUTTING_PATHS and op.path not in seen
        ]
        return primary + extra

    def get(self, path: str) -> Operation | None:
        """Look up an operation by its exact path template."""
        return self._by_path.get(path)

    def match(self, path: str) -> tuple[Operation, dict[str, str]] | None:
        """Resolve a path the model supplied, template OR already filled in.

        The catalog lists templates (``/v1/diputados/actas/id/{actaId}``) but
        models routinely send the concrete path (``…/actas/id/5995``) with an
        empty params dict.  Rejecting that wastes a whole turn on a retry
        loop, so match it back to its template and hand the extracted values
        over as path params.

        Returns the operation plus any params recovered from the path, or
        None when nothing matches.
        """
        op = self._by_path.get(path)
        if op is not None:
            return op, {}

        for candidate, pattern, names in self._matchers:
            found = pattern.fullmatch(path)
            if found:
                return candidate, dict(zip(names, found.groups(), strict=True))
        return None

    def paths(self) -> list[str]:
        return list(self._by_path)

    def __len__(self) -> int:
        return len(self._all)

    # ── Serialization ─────────────────────────────────────────────────────────

    def as_prompt_text(self, domain: str) -> str:
        """Compact newline-separated catalog for inclusion in a system prompt.

        Format per line:
          - /path/template  # Summary — hint  params: name(*|?)[enum|…]
        where * = required, ? = optional.  The hint (see _SUMMARY_HINTS) is
        only present for endpoints whose official summary doesn't match the
        words users actually use.

        Proxy params (``fields``, ``title``, ``active``, …) are listed per
        endpoint but explained ONCE in a legend at the end, since the same
        handful repeats across many paths.
        """
        ops = self.for_domain(domain)
        lines: list[str] = []
        used_specs: dict[str, ParamSpec] = {}

        for op in ops:
            param_parts: list[str] = []
            for p in op.params:
                marker = "*" if p.required else "?"
                s = f"{p.name}({marker})"
                if p.enum:
                    joined = "|".join(p.enum[:_MAX_ENUM_SIZE])
                    if len(p.enum) > _MAX_ENUM_SIZE:
                        joined += "|…"
                    s += f"[{joined}]"
                elif p.example:
                    s += f"[{p.example}]"
                elif p.type != "string":
                    s += f"[{p.type}]"
                param_parts.append(s)

                spec = PARAM_BY_NAME.get(p.name)
                if p.location == "client" and spec is not None:
                    used_specs[p.name] = spec

            param_str = (
                f"  params: {', '.join(param_parts)}" if param_parts else ""
            )
            hint = _SUMMARY_HINTS.get(op.path)
            summary = f"{op.summary} — {hint}" if hint else op.summary
            lines.append(f"- {op.path}  # {summary}{param_str}")

        if used_specs:
            lines.append("")
            lines.append("Query params above (handled server-side, exact spelling):")
            for name in sorted(used_specs):
                lines.append(f"  {name} — {used_specs[name].hint}")

        return "\n".join(lines)


# ── Semantic hints ────────────────────────────────────────────────────────────

#: path → short phrase appended to the summary in the prompt catalog.
#: Only for endpoints whose official summary is too terse to connect with the
#: words users actually type ("Actas" tells the model nothing about it being
#: the record of how a bill was voted).  Without this the model hedges and
#: asks clarifying questions instead of committing to the endpoint.
_ACTAS_LIST_HINT = (
    "{chamber} voting record (one row/vote: {id_field}, titulo, fecha, "
    "resultado). 'últimas leyes' / 'leyes durante el mandato' → desde/hasta; "
    "named law → search_actas. Roll call → {votes_path}. One legislator's "
    "votes across bills → includeVotes=true + date bounds + transform "
    "unnest_match on votos (never List raw votos[])"
)

_ROSTER_HINT = (
    "{entity} directory ({fields}). Default: in office today ({seats}); "
    "active=false for history. Filter province=/name=/names=. Roll call → "
    "…/votos (already carries bloque/foto from roster)"
)


#: path → short phrase appended to the summary in the prompt catalog.
#: Only for endpoints whose official summary is too terse to connect with the
#: words users actually type ("Actas" tells the model nothing about it being
#: the record of how a bill was voted).  Without this the model hedges and
#: asks clarifying questions instead of committing to the endpoint.
_SUMMARY_HINTS: dict[str, str] = {
    "/v1/cotizaciones/dolares": (
        "All FX houses (casa, compra, venta, fecha). Side-by-side bars → "
        "desde=hasta=one day; Chart kind=bar xKey=casa series=venta. "
        "History for one house → /v1/cotizaciones/dolares/{casa}"
    ),
    "/v1/senado/actas": _ACTAS_LIST_HINT.format(
        chamber="Senado",
        id_field="actaId",
        votes_path="/v1/senado/actas/id/{actaId}/votos",
    ),
    "/v1/senado/actas/{año}": "same as /v1/senado/actas, scoped to one year",
    "/v1/diputados/actas": _ACTAS_LIST_HINT.format(
        chamber="Diputados",
        id_field="id",
        votes_path="/v1/diputados/actas/id/{actaId}/votos",
    ),
    "/v1/diputados/actas/{año}": "same as /v1/diputados/actas, scoped to one year",
    "/v1/senado/senadores": _ROSTER_HINT.format(
        entity="senadores",
        seats="72 — 3 per province",
        fields="id, nombre, provincia, partido, bloque, foto, email, telefono, redes",
    ),
    "/v1/diputados/diputados": _ROSTER_HINT.format(
        entity="diputados",
        seats="257",
        fields="id, nombre+apellido, provincia, bloque, genero, periodoMandato (no foto)",
    ),
    "/v1/presidentes": (
        "Terms: nombre, inicio, fin (null=current), partido, imagen. "
        "Who was president on a fecha → compare inicio/fin. Mandate cuts → "
        "fetch WITH the measure series. name=/names= for lookups — don't dump "
        "the full list"
    ),
    "/v1/eventos/presidenciales": (
        "Dated political events — overlay on FX/inflación/riesgo/confianza "
        "(cruce), not a standalone dump. Pair /v1/presidentes for mandate cuts"
    ),
    "/v1/bcra/{alias}": (
        "BCRA stocks/rates (reservas, base_monetaria, depositos_*, "
        "tasa_depositos_30d). 'por mandato' → fetch WITH /v1/presidentes"
    ),
    "/v1/cammesa/demanda": (
        "Monthly demand + CAMMESA temp wide — Chart demanda_total vs "
        "temperatura. Mention CAMMESA once"
    ),
    "/v1/cammesa/{alias}": (
        "Single monthly series; prefer /v1/cammesa/demanda for demand×temp"
    ),
    "/v1/series/{alias}": (
        "INDEC/MECON curated (emae, desempleo, pobreza, ripte, ipc, "
        "exportaciones, importaciones). Unknown → /v1/series/search first"
    ),
    "/v1/series/search": (
        "Find Series de Tiempo id by Spanish name → /v1/series/id/{serieId}"
    ),
    "/v1/clima/historico": (
        "Past weather by province capital. Join acta/FX fecha. Needs "
        "desde+hasta. Compose WeatherUnit"
    ),
    "/v1/clima/actual": (
        "Current weather: one province → WeatherUnit; all 24 → ProvinceMap"
    ),
    "/v1/historico/dias": (
        "~16 curated dates (persona+provincia). Then /dia + FX + clima + "
        "presidentes"
    ),
    "/v1/historico/dia": (
        "Wikipedia extract for one date. SAME turn: FX ±7d, clima, "
        "presidentes if persona. Stack: PersonCard, Text, WeatherUnit, Chart"
    ),
    "/v1/wiki/summary": "Ad-hoc Wikipedia when date isn't in historico/dias",
    "/v1/cine/discover": (
        "Browse AR films (TMDB). List foto+titulo+valor; then pelicula/{id}"
    ),
    "/v1/cine/search": "Find AR film by title (q=)",
    "/v1/cine/pelicula/{id}": (
        "Ficha: Text + MetricRow + PersonCard on SAME dataRef (elenco). "
        "Mention TMDB once"
    ),
    "/v1/cine/persona/search": (
        "Find person → /persona/{id} + /persona/{id}/filmografia"
    ),
    "/v1/cine/persona/{id}": (
        "PersonCard bio. Nested filmografia[] not List-ready — fetch flat path"
    ),
    "/v1/cine/persona/{id}/filmografia": (
        "FLAT AR films — List foto+titulo+fecha+valor"
    ),
    "/v1/rem/vs-real/{alias}": (
        "REM mediana vs reality (ipc/tc/desempleo). Chart esperado+real; "
        "short window → ComparisonTable. Default horizon=1m"
    ),
    "/v1/rem/{alias}": (
        "REM nowcasts by informe. Pair vs-real when asking how wrong it was"
    ),
    "/v1/finanzas/brokers/comisiones": (
        "Broker fees — ComparisonTable (highlight cheapest)"
    ),
    "/v1/finanzas/cobros/comisiones": (
        "Payment-processor fees — ComparisonTable by arancel"
    ),
    "/v1/finanzas/remesas": "Remittance platforms — ComparisonTable",
    "/v1/diputados/diputados/{id}/viajes": (
        "One deputy's trips as FLAT rows (origen, destino, anio, mesNombre)"
    ),
    "/v1/senado/senadores/{id}/viajes": "One senator's trips as FLAT rows",
    "/v1/diputados/viajes/nacionales": (
        "Flat national trips for all deputies (prefer over index)"
    ),
    "/v1/diputados/misiones/lista": (
        "Flat foreign missions (prefer over /misiones index)"
    ),
}


# ── Parser ────────────────────────────────────────────────────────────────────


def _fix_mojibake(s: str) -> str:
    """Fix summaries/descriptions stored with UTF-8 bytes interpreted as latin-1.

    The ArgentinaDatos OpenAPI file has Spanish accented characters that were
    double-encoded.  Re-encoding to latin-1 then decoding as UTF-8 recovers the
    original text (e.g. "DÃ³lares" → "Dólares").
    """
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _infer_domain(path: str) -> str:
    for prefix, domain in _DOMAIN_PREFIXES:
        if path.startswith(prefix):
            return domain
    return "other"


#: Not ``\w+``: placeholder names carry accents (``{año}``), and ``ñ`` is not
#: a word character in every decoding we may see.
_PLACEHOLDER = re.compile(r"\{([^}]+)\}")


def _build_matchers(
    operations: list[Operation],
) -> list[tuple[Operation, re.Pattern[str], list[str]]]:
    """Compile one regex per templated path, most specific first.

    A placeholder matches a single segment (``[^/]+``), so
    ``/v1/senado/actas/{año}`` can never swallow
    ``/v1/senado/actas/id/2802``.  Ordering by fewest placeholders then
    longest literal keeps the more specific template winning.
    """
    matchers = []
    for op in operations:
        names = _PLACEHOLDER.findall(op.path)
        if not names:
            continue
        pattern = re.compile(_PLACEHOLDER.sub(r"([^/]+)", re.escape(op.path).replace(r"\{", "{").replace(r"\}", "}")))
        matchers.append((op, pattern, names))

    matchers.sort(key=lambda m: (len(m[2]), -len(m[0].path)))
    return matchers


def _client_param(spec: ParamSpec) -> Param:
    """Turn a proxy ParamSpec into a catalog Param (never sent upstream)."""
    return Param(
        name=spec.name,
        location="client",
        required=False,
        type=spec.type,
        enum=list(spec.enum) if spec.enum else None,
        example=spec.example,
    )


def _synthetic_operations() -> list[Operation]:
    """Catalog entries for proxy-only routes (acta detail, votes, profiles)."""
    ops: list[Operation] = []
    for route in SYNTHETIC_ROUTES.values():
        params = [
            Param(
                name=route.id_param,
                location="path",
                required=True,
                type="string",
            ),
            *(_client_param(spec) for spec in route.params),
        ]
        ops.append(
            Operation(
                id=route.path,
                path=route.path,
                domain=_infer_domain(route.path),
                summary=route.summary,
                params=params,
            )
        )
    return ops


def _external_operations() -> list[Operation]:
    """Catalog entries for BCRA / Series / Open-Meteo proxy routes."""
    ops: list[Operation] = []
    for route in EXTERNAL_ROUTES.values():
        params = [
            Param(
                name=name,
                location="path",
                required=True,
                type="string",
            )
            for name in route.path_params
        ]
        params.extend(_client_param(spec) for spec in route.params)
        ops.append(
            Operation(
                id=route.path,
                path=route.path,
                domain=route.domain,
                summary=route.summary,
                params=params,
            )
        )
    return ops


def _parse_param(raw: dict) -> Param:
    schema = raw.get("schema", {})
    type_ = schema.get("type", "string")
    enum = schema.get("enum")
    example = raw.get("example")
    return Param(
        name=_fix_mojibake(raw["name"]),
        location=raw.get("in", "query"),
        required=bool(raw.get("required", False)),
        type=type_,
        enum=[str(e) for e in enum] if enum else None,
        example=str(example) if example is not None else None,
    )


def _load_catalog(openapi_path: Path = _OPENAPI_PATH) -> Catalog:
    with openapi_path.open(encoding="utf-8") as f:
        spec = json.load(f)

    ops: list[Operation] = []
    for raw_path, item in spec.get("paths", {}).items():
        get_op = item.get("get")
        if not get_op:
            continue  # all ArgentinaDatos ops are GET

        # Nine spec paths carry a double-encoded "{año}".  Fixing it here is
        # safe because a placeholder is always substituted before the URL is
        # built, and it spares both the model and us from typing "{aÃ±o}".
        path = _fix_mojibake(raw_path)
        params = [_parse_param(p) for p in get_op.get("parameters", [])]
        ops.append(
            Operation(
                id=get_op.get("operationId", path),
                path=path,
                domain=_infer_domain(path),
                summary=_fix_mojibake(get_op.get("summary", "")),
                params=params,
            )
        )

    # Layer the proxy surface on top of upstream: synthetic query params the
    # proxy implements itself (location="client" — never forwarded upstream),
    # plus the routes upstream doesn't have at all.
    for op in ops:
        existing = {p.name for p in op.params}
        for spec in params_for(op.path):
            if spec.name not in existing:
                op.params.append(_client_param(spec))

    ops.extend(_synthetic_operations())
    ops.extend(_external_operations())

    return Catalog(ops)


# ── Singleton — parsed once at import time ────────────────────────────────────
catalog: Catalog = _load_catalog()
