"""Proxy surface declaration — the single source of truth for what the LLM
can ask for.

Two kinds of capability are declared here:

  1. ``SYNTHETIC_ROUTES`` — paths the proxy serves that upstream does NOT
     have: acta detail by id, legislator profile by id.  Resolved by reading
     the cached list and picking the matching row.

  2. ``PARAM_SPECS`` — synthetic query params layered on existing upstream
     paths: ``fields`` (projection), ``title`` (search), ``province`` /
     ``name`` / ``names`` / ``active`` (roster), ``vote`` / ``includeVotes``
     (actas), ``desde`` / ``hasta`` (date range), ``refresh`` (cache bypass).

Both are read by ``catalog.py`` to describe the surface in the system prompt,
and by ``proxy/__init__.py`` to execute it.  Adding a capability means one
entry here, not changes spread across the tool, the catalog and the prompt.

"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Cache TTLs (seconds) ──────────────────────────────────────────────────────
# Floor of one day: upstream lists are heavy; short TTLs mostly burned CPU.
# Rosters barely move between elections; actas can wait a day for this product.
TTL_ACTAS = 24 * 60 * 60
TTL_ROSTER = 24 * 60 * 60
TTL_DEFAULT = 24 * 60 * 60


# ── Row caps ──────────────────────────────────────────────────────────────────
# A bare list must never blow the context window.  Three tiers, because the
# per-row weight differs by two orders of magnitude:
#   - rows carrying the full votos[] array (~70-257 entries each)
#   - normal rows with votos[] summarized
#   - rows projected down to a couple of fields via `fields=`
DETAIL_ROW_CAP = 5
SAFETY_CAP = 60
PROJECTED_CAP = 400


# ── Param specs ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParamSpec:
    """A synthetic (client-side) query param the proxy implements itself."""

    name: str
    type: str  # "string" | "boolean" | "integer"
    hint: str  # short phrase shown to the LLM in the catalog
    enum: tuple[str, ...] | None = None
    example: str | None = None


_FIELDS_HINT = (
    "comma-separated field names to keep per row; everything else is "
    "stripped server-side. Use it to scan a long list cheaply before "
    "asking for detail"
)


def fields_spec(example: str) -> ParamSpec:
    """``fields`` param carrying an example from the target's real schema.

    The example is per-endpoint on purpose: the acta id key differs by
    chamber (``actaId`` vs ``id``), and a wrong key costs a retry round-trip.
    """
    return ParamSpec(name="fields", type="string", hint=_FIELDS_HINT, example=example)


FIELDS_ROSTER = fields_spec("id,nombre,provincia,bloque,foto")
FIELDS_VOTES = fields_spec("nombre,voto")

#: Consumed by the proxy on every path but never advertised to the model:
#: ``fields`` is offered per endpoint with a real example (see above), and
#: ``refresh`` is an operational escape hatch, not a modelling decision.
ALWAYS_CLIENT: tuple[str, ...] = ("fields", "refresh")
DESDE = ParamSpec(name="desde", type="string", hint="ISO date lower bound (inclusive)")
HASTA = ParamSpec(name="hasta", type="string", hint="ISO date upper bound (inclusive)")
TITLE = ParamSpec(
    name="title",
    type="string",
    hint=(
        "accent/case-insensitive search over título / descripción / proyecto. "
        "All words must appear (not necessarily adjacent). Put the user's own "
        "law name here — never a sample name from the docs. Applied BEFORE "
        "any row cap, so it finds older actas the cap would drop"
    ),
)
INCLUDE_VOTES = ParamSpec(
    name="includeVotes",
    type="boolean",
    hint=(
        "keep the full per-legislator votos[] array (default: summarized to "
        "a count, since it is ~70-257 entries per acta)"
    ),
)
VOTE = ParamSpec(
    name="vote",
    type="string",
    hint=(
        "keep only votos[] entries with this vote, normalized across both "
        "chambers; implies includeVotes"
    ),
    enum=("afirmativo", "negativo", "abstencion", "ausente"),
)
PROVINCE = ParamSpec(
    name="province",
    type="string",
    hint="accent/case-insensitive match on the provincia field",
    example="Misiones",
)
NAME = ParamSpec(
    name="name",
    type="string",
    hint="accent/case-insensitive substring match on the legislator name",
)
NAMES = ParamSpec(
    name="names",
    type="string",
    hint=(
        "pipe-separated list of names; a row matches if ANY entry matches. "
        "Use it to enrich a whole votos[] list in ONE call (names contain "
        "commas, hence the pipe)"
    ),
    example="Abad, Maximiliano|Rojas Decut, Sonia Elizabeth",
)
ACTIVE = ParamSpec(
    name="active",
    type="boolean",
    hint=(
        "defaults to true — only legislators currently in office. Pass "
        "active=false to search the historical roster (which goes back to "
        "the 1940s)"
    ),
)


# ── Families ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ActasFamily:
    """One chamber's voting-record endpoints and row shape."""

    chamber: str  # "senado" | "diputados"
    list_path: str
    year_path: str
    detail_path: str
    votes_path: str
    id_field: str
    text_fields: tuple[str, ...]  # searched by `title`
    votes_field: str
    vote_key: str  # key holding the vote inside each votos[] entry
    voter_key: str  # key holding the legislator name
    #: canonical vote value → raw upstream value
    vote_values: dict[str, str]

    @property
    def raw_to_canonical(self) -> dict[str, str]:
        return {raw: canon for canon, raw in self.vote_values.items()}


@dataclass(frozen=True)
class RosterFamily:
    """One chamber's legislator directory."""

    chamber: str
    list_path: str
    detail_path: str
    id_field: str
    name_fields: tuple[str, ...]
    #: fields holding the end-of-term date, first non-null wins
    term_end_paths: tuple[tuple[str, ...], ...]


SENADO_ACTAS = ActasFamily(
    chamber="senado",
    list_path="/v1/senado/actas",
    year_path="/v1/senado/actas/{año}",
    detail_path="/v1/senado/actas/id/{actaId}",
    votes_path="/v1/senado/actas/id/{actaId}/votos",
    id_field="actaId",
    text_fields=("titulo", "descripcion", "proyecto"),
    votes_field="votos",
    vote_key="voto",
    voter_key="nombre",
    vote_values={
        "afirmativo": "si",
        "negativo": "no",
        "abstencion": "abstencion",
        "ausente": "ausente",
    },
)

DIPUTADOS_ACTAS = ActasFamily(
    chamber="diputados",
    list_path="/v1/diputados/actas",
    year_path="/v1/diputados/actas/{año}",
    detail_path="/v1/diputados/actas/id/{actaId}",
    votes_path="/v1/diputados/actas/id/{actaId}/votos",
    id_field="id",
    text_fields=("titulo",),
    votes_field="votos",
    vote_key="tipoVoto",
    voter_key="diputado",
    vote_values={
        "afirmativo": "afirmativo",
        "negativo": "negativo",
        "abstencion": "abstencion",
        "ausente": "ausente",
    },
)

SENADO_ROSTER = RosterFamily(
    chamber="senado",
    list_path="/v1/senado/senadores",
    detail_path="/v1/senado/senadores/{id}",
    id_field="id",
    name_fields=("nombre",),
    term_end_paths=(("periodoReal", "fin"), ("periodoLegal", "fin")),
)

DIPUTADOS_ROSTER = RosterFamily(
    chamber="diputados",
    list_path="/v1/diputados/diputados",
    detail_path="/v1/diputados/diputados/{id}",
    id_field="id",
    name_fields=("nombre", "apellido"),
    term_end_paths=(("ceseFecha",), ("periodoMandato", "fin")),
)

ACTAS_FAMILIES: tuple[ActasFamily, ...] = (SENADO_ACTAS, DIPUTADOS_ACTAS)
ROSTER_FAMILIES: tuple[RosterFamily, ...] = (SENADO_ROSTER, DIPUTADOS_ROSTER)


# ── Synthetic routes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SyntheticRoute:
    """A proxy path resolved from a cached upstream list.

    ``actas/id/{actaId}`` rather than ``actas/{actaId}`` on purpose: upstream
    already uses ``actas/{año}`` and Diputados acta ids run 1..6000, so a bare
    ``/actas/2026`` would be ambiguous between a year and an acta id.
    """

    path: str
    upstream: str
    id_param: str
    id_field: str
    ttl: float
    summary: str
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)
    #: when set, return this field of the matched row instead of the row —
    #: used by ``/votos`` so the result is a LIST of vote rows, which can be
    #: bound straight to a List/PersonCard widget
    subfield: str | None = None


SYNTHETIC_ROUTES: dict[str, SyntheticRoute] = {}

for _actas in ACTAS_FAMILIES:
    SYNTHETIC_ROUTES[_actas.detail_path] = SyntheticRoute(
        path=_actas.detail_path,
        upstream=_actas.list_path,
        id_param="actaId",
        id_field=_actas.id_field,
        ttl=TTL_ACTAS,
        summary=(
            f"One {_actas.chamber.capitalize()} acta by id, WITH the full "
            "per-legislator votos[] breakdown (nombre + voto, normalized). "
            f"Get the id from {_actas.list_path} first "
            f"(fields={_actas.id_field},titulo or title=<name>)"
        ),
        params=(VOTE, fields_spec(f"{_actas.id_field},titulo,votos")),
    )
    SYNTHETIC_ROUTES[_actas.votes_path] = SyntheticRoute(
        path=_actas.votes_path,
        upstream=_actas.list_path,
        id_param="actaId",
        id_field=_actas.id_field,
        ttl=TTL_ACTAS,
        summary=(
            f"How each {_actas.chamber} legislator voted on one acta, as a "
            "flat list of {nombre, voto} rows — THE endpoint for 'cómo votó "
            "cada uno' / 'quiénes votaron a favor|en contra'. Pass vote= to "
            "keep only one side"
        ),
        params=(VOTE, FIELDS_VOTES),
        subfield=_actas.votes_field,
    )

for _roster in ROSTER_FAMILIES:
    _entity = "senador" if _roster.chamber == "senado" else "diputado"
    SYNTHETIC_ROUTES[_roster.detail_path] = SyntheticRoute(
        path=_roster.detail_path,
        upstream=_roster.list_path,
        id_param="id",
        id_field=_roster.id_field,
        ttl=TTL_ROSTER,
        summary=f"One {_entity} profile by id (photo, party, province, term)",
        params=(FIELDS_ROSTER,),
    )


# ── Param registry per path ───────────────────────────────────────────────────

#: proxy/upstream path → synthetic params the proxy implements for it.
PARAM_SPECS: dict[str, tuple[ParamSpec, ...]] = {}

for _actas in ACTAS_FAMILIES:
    _fields = fields_spec(f"{_actas.id_field},titulo,fecha")
    for _path in (_actas.list_path, _actas.year_path):
        PARAM_SPECS[_path] = (TITLE, VOTE, INCLUDE_VOTES, DESDE, HASTA, _fields)

for _roster in ROSTER_FAMILIES:
    PARAM_SPECS[_roster.list_path] = (ACTIVE, PROVINCE, NAME, NAMES, FIELDS_ROSTER)

for _route in SYNTHETIC_ROUTES.values():
    PARAM_SPECS[_route.path] = _route.params

#: Date-filterable series (the proxy filters them client-side on `fecha`).
DATE_SERIES_PATHS: tuple[str, ...] = (
    "/v1/cotizaciones/dolares",
    "/v1/cotizaciones/dolares/{casa}",
    "/v1/finanzas/indices/inflacion",
    "/v1/finanzas/indices/inflacionInteranual",
    "/v1/finanzas/indices/uva",
    "/v1/finanzas/indices/riesgo-pais",
    "/v1/politica/indices/confianza-gobierno",
    "/v1/finanzas/tasas/depositos30Dias",
    "/v1/finanzas/rendimientos/{entidad}",
)

for _path in DATE_SERIES_PATHS:
    PARAM_SPECS[_path] = (DESDE, HASTA)

PARAM_SPECS["/v1/presidentes"] = (
    fields_spec("nombre,inicio,fin,partido,imagen"),
)


#: param name → spec, so the catalog can render each hint once in a legend
#: instead of repeating it on every path that accepts it.
PARAM_BY_NAME: dict[str, ParamSpec] = {
    spec.name: spec
    for specs in PARAM_SPECS.values()
    for spec in specs
}


def params_for(path: str) -> tuple[ParamSpec, ...]:
    """Synthetic params advertised to the model for *path*.

    Paths with nothing useful to add (single-value endpoints, small lists)
    advertise nothing — ``fields`` and ``refresh`` still work everywhere, see
    ``client_param_names``, they just aren't worth the prompt tokens on 70
    endpoints.
    """
    return PARAM_SPECS.get(path, ())


def client_param_names(path: str) -> set[str]:
    """Params the proxy consumes itself and never forwards upstream."""
    return {spec.name for spec in params_for(path)} | set(ALWAYS_CLIENT)


def ttl_for(path: str) -> float:
    """Cache TTL for an upstream list path."""
    if any(path.startswith(f.list_path) for f in ACTAS_FAMILIES):
        return TTL_ACTAS
    if any(path.startswith(f.list_path) for f in ROSTER_FAMILIES):
        return TTL_ROSTER
    return TTL_DEFAULT


def actas_family_for(path: str) -> ActasFamily | None:
    for family in ACTAS_FAMILIES:
        if path in (
            family.list_path,
            family.year_path,
            family.detail_path,
            family.votes_path,
        ):
            return family
    return None


def roster_family_for(path: str) -> RosterFamily | None:
    for family in ROSTER_FAMILIES:
        if path in (family.list_path, family.detail_path):
            return family
    return None
