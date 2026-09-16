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


FIELDS_ROSTER = fields_spec(
    "id,nombre,provincia,partido,bloque,foto,email,telefono,redes,bio"
)
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
            "flat list of rows with nombre, voto, plus bloque/partido/foto|"
            "imagen/provincia stamped from the chamber roster when matched — "
            "THE endpoint for 'cómo votó cada uno' / 'quiénes votaron a "
            "favor|en contra' (PersonCard-ready). Pass vote= to keep only "
            "one side"
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

#: Calendars / event lists — date-filter BEFORE SAFETY_CAP (not chart series).
CALENDAR_PATHS: tuple[str, ...] = (
    "/v1/eventos/presidenciales",
    "/v1/feriados/{año}",
    "/v1/feriados-bancarios/{año}",
)

for _path in DATE_SERIES_PATHS:
    PARAM_SPECS[_path] = (DESDE, HASTA)

PARAM_SPECS["/v1/eventos/presidenciales"] = (DESDE, HASTA)
PARAM_SPECS["/v1/feriados/{año}"] = (DESDE, HASTA)
PARAM_SPECS["/v1/feriados-bancarios/{año}"] = (DESDE, HASTA)

PARAM_SPECS["/v1/presidentes"] = (
    NAME,
    NAMES,
    fields_spec("nombre,inicio,fin,partido,imagen,bio"),
)


# ── External upstream routes (BCRA / Series / Open-Meteo) ─────────────────────


@dataclass(frozen=True)
class ExternalRoute:
    """A proxy path served by a non-ArgentinaDatos upstream."""

    path: str
    domain: str  # finance | politics | other
    summary: str
    params: tuple[ParamSpec, ...] = field(default_factory=tuple)
    #: path-param names (e.g. alias, serieId) — required when present
    path_params: tuple[str, ...] = ()


PROVINCIA = ParamSpec(
    name="provincia",
    type="string",
    hint="Argentine province name (or CABA). Omit to return all 24 jurisdictions",
    example="Córdoba",
)
DIAS = ParamSpec(
    name="dias",
    type="integer",
    hint="forecast horizon in days (1–16, default 7)",
    example="7",
)
Q_SEARCH = ParamSpec(
    name="q",
    type="string",
    hint=(
        "Spanish search text for Series de Tiempo (e.g. 'EMAE', 'desempleo'). "
        "Returns top matches with serieId — then fetch /v1/series/id/{serieId}"
    ),
    example="EMAE",
)
FECHA = ParamSpec(
    name="fecha",
    type="string",
    hint="ISO date (YYYY-MM-DD) for a curated historical day",
    example="2023-12-10",
)
Q_WIKI = ParamSpec(
    name="q",
    type="string",
    hint="Spanish Wikipedia article title for REST summary (extract, foto, url)",
    example="Presidencia de Javier Milei",
)
NAMES_WIKI = ParamSpec(
    name="names",
    type="string",
    hint=(
        "pipe-separated full names of public figures to resolve through "
        "Wikidata/Wikipedia as PersonCard-ready rows"
    ),
    example="Luis Caputo|Kristalina Georgieva",
)
Q_NEWS = ParamSpec(
    name="q",
    type="string",
    hint=(
        "concise SPANISH Google News search terms chosen from the user's topic, "
        "even if the user wrote in another language. Use names and distinctive "
        "concepts, not a full conversational sentence"
    ),
    example="Milei inflación",
)
Q_CINE = ParamSpec(
    name="q",
    type="string",
    hint="Search text for Argentine films or people (TMDB)",
    example="Relatos salvajes",
)
ANIO_CINE = ParamSpec(
    name="anio",
    type="integer",
    hint="Release year filter (YYYY)",
    example="2014",
)
GENERO_CINE = ParamSpec(
    name="genero",
    type="string",
    hint=(
        "Genre name (drama, comedia, documental, thriller, terror, romance, "
        "accion, …) or TMDB genre id"
    ),
    example="drama",
)
SORT_CINE = ParamSpec(
    name="sort",
    type="string",
    hint=(
        "TMDB sort_by (default popularity.desc). Also: vote_average.desc, "
        "primary_release_date.desc, title.asc"
    ),
    example="popularity.desc",
)
PAGE_CINE = ParamSpec(
    name="page",
    type="integer",
    hint="TMDB page (default 1)",
    example="1",
)
REM_ALIAS = ParamSpec(
    name="alias",
    type="string",
    hint=(
        "Curated REM indicator: ipc, ipc_nucleo, tc, desempleo. "
        "Omit on /v1/rem/ultimo|/informe to return every indicador"
    ),
    example="ipc",
    enum=("ipc", "ipc_nucleo", "tc", "desempleo"),
)
REM_MUESTRA = ParamSpec(
    name="muestra",
    type="string",
    hint="REM sample: todos (default) or top_10",
    enum=("todos", "top_10"),
    example="todos",
)
REM_HORIZON = ParamSpec(
    name="horizon",
    type="string",
    hint=(
        "vs-real join: 1m = forecast from the previous month (default), "
        "nowcast = same-month forecast, all = every past forecast"
    ),
    enum=("1m", "nowcast", "all"),
    example="1m",
)
REM_ANIO = ParamSpec(
    name="año",
    type="integer",
    hint="REM informe year (2016+)",
    example="2024",
)
REM_MES = ParamSpec(
    name="mes",
    type="string",
    hint="REM informe month as two digits (01–12)",
    example="06",
)
Q_FCI = ParamSpec(
    name="q",
    type="string",
    hint="Spanish fund name fragment (e.g. 'Delta Pesos'). All words must match",
    example="Delta Pesos",
)
LIMIT_PLAZOS = ParamSpec(
    name="limit",
    type="integer",
    hint="Max banks to return (default 25, max 40)",
    example="15",
)

EXTERNAL_ROUTES: dict[str, ExternalRoute] = {
    "/v1/bcra/variables": ExternalRoute(
        path="/v1/bcra/variables",
        domain="finance",
        summary=(
            "Curated BCRA monetary variables (reservas, base_monetaria, "
            "depositos_privados, depositos_plazo, tasa_depositos_30d). "
            "Use the alias on /v1/bcra/{alias}"
        ),
    ),
    "/v1/bcra/{alias}": ExternalRoute(
        path="/v1/bcra/{alias}",
        domain="finance",
        summary=(
            "BCRA daily series as {fecha, valor, unidad, kind}. "
            "Aliases: reservas, base_monetaria, depositos_privados, "
            "depositos_plazo, tasa_depositos_30d. Stocks (reservas, "
            "depósitos, base) → pair with /v1/presidentes for mandate "
            "levels (last/delta). Pass desde/hasta ISO"
        ),
        params=(DESDE, HASTA),
        path_params=("alias",),
    ),
    "/v1/cammesa": ExternalRoute(
        path="/v1/cammesa",
        domain="finance",
        summary=(
            "Curated CAMMESA electricity aliases (demanda, residencial, "
            "comercio, grandes_usuarios, temperatura, potencia_maxima). "
            "Monthly GWh / °C / MW from datos.gob.ar (SSPM). Prefer "
            "/v1/cammesa/demanda for demanda×temperatura on one Chart"
        ),
    ),
    "/v1/cammesa/demanda": ExternalRoute(
        path="/v1/cammesa/demanda",
        domain="finance",
        summary=(
            "Wide monthly rows: fecha, demanda_total, demanda_residencial, "
            "comercio_industria, grandes_usuarios, temperatura, "
            "potencia_maxima. Chart dual series demanda_total+temperatura "
            "(heatwave × load). Pass desde/hasta. Attribution: CAMMESA"
        ),
        params=(DESDE, HASTA),
    ),
    "/v1/cammesa/{alias}": ExternalRoute(
        path="/v1/cammesa/{alias}",
        domain="finance",
        summary=(
            "One CAMMESA monthly series as {fecha, valor, unidad}. "
            "Aliases: demanda, residencial, comercio, grandes_usuarios, "
            "temperatura, potencia_maxima. Pair with /v1/clima/historico "
            "or EMAE for cruces"
        ),
        params=(DESDE, HASTA),
        path_params=("alias",),
    ),
    "/v1/series": ExternalRoute(
        path="/v1/series",
        domain="finance",
        summary=(
            "Curated INDEC/MECON Series de Tiempo aliases (emae, emae_var, "
            "desempleo, pobreza, ripte, ipc, exportaciones, importaciones). "
            "For anything else use /v1/series/search?q="
        ),
    ),
    "/v1/series/search": ExternalRoute(
        path="/v1/series/search",
        domain="finance",
        summary=(
            "Text search over the Series de Tiempo catalog. Returns top "
            "hits with serieId/titulo/unidades — then fetch "
            "/v1/series/id/{serieId}"
        ),
        params=(Q_SEARCH,),
    ),
    "/v1/series/{alias}": ExternalRoute(
        path="/v1/series/{alias}",
        domain="finance",
        summary=(
            "One curated series as {fecha, valor, titulo, unidad}. "
            "Aliases: emae, emae_var, desempleo, pobreza, ripte, ipc, "
            "exportaciones, importaciones. Pass desde/hasta. Pair with "
            "presidentes for per-mandate levels"
        ),
        params=(DESDE, HASTA),
        path_params=("alias",),
    ),
    "/v1/series/id/{serieId}": ExternalRoute(
        path="/v1/series/id/{serieId}",
        domain="finance",
        summary=(
            "Raw Series de Tiempo id (from /v1/series/search). Same "
            "{fecha, valor} shape as curated aliases"
        ),
        params=(DESDE, HASTA),
        path_params=("serieId",),
    ),
    "/v1/clima/historico": ExternalRoute(
        path="/v1/clima/historico",
        domain="other",
        summary=(
            "Daily historical weather by province capital (Open-Meteo). "
            "Rows: fecha, provincia, tmin, tmax, temperatura, precipitacion, "
            "weather_code, valor(=temp media). Requires desde+hasta. "
            "Omit provincia for all 24. Bind WeatherUnit. "
            "Join with actas/FX on fecha. Attribution: Open-Meteo"
        ),
        params=(PROVINCIA, DESDE, HASTA),
    ),
    "/v1/clima/pronostico": ExternalRoute(
        path="/v1/clima/pronostico",
        domain="other",
        summary=(
            "Daily forecast (1–16 days, default 7) by province capital. "
            "Same row shape as historico. Bind WeatherUnit. "
            "Omit provincia for all 24"
        ),
        params=(PROVINCIA, DIAS),
    ),
    "/v1/clima/actual": ExternalRoute(
        path="/v1/clima/actual",
        domain="other",
        summary=(
            "Current temperature + weather_code by province. One place → "
            "WeatherUnit; all 24 → ProvinceMap (provincia, temperatura)"
        ),
        params=(PROVINCIA,),
    ),
    "/v1/historico/dias": ExternalRoute(
        path="/v1/historico/dias",
        domain="other",
        summary=(
            "Curated Argentine historical days (2016–2024): fecha, titulo, "
            "categoria, wiki title, series_sugeridas, provincia, optional "
            "persona. Browse before /v1/historico/dia"
        ),
        params=(DESDE, HASTA),
    ),
    "/v1/historico/dia": ExternalRoute(
        path="/v1/historico/dia",
        domain="other",
        summary=(
            "One curated day + Wikipedia extract (bio), foto, wikipedia_url, "
            "provincia, optional persona. Requires fecha=ISO. SAME turn: "
            "only requested series/climate, period /v1/noticias for narrative "
            "context, and an official roster or /v1/wiki/personas for requested "
            "public-figure PersonCards"
        ),
        params=(FECHA,),
    ),
    "/v1/wiki/summary": ExternalRoute(
        path="/v1/wiki/summary",
        domain="other",
        summary=(
            "Wikipedia REST summary for any Spanish article title (q=). "
            "Returns extract, foto, url — use for ad-hoc context when the "
            "day is not in /v1/historico/dias"
        ),
        params=(Q_WIKI,),
    ),
    "/v1/wiki/personas": ExternalRoute(
        path="/v1/wiki/personas",
        domain="other",
        summary=(
            "Profiles of named public figures from Wikidata/Wikipedia. "
            "Returns nombre, foto, bio, partido and redes when available. "
            "Use for PersonCard when the figure is not available from the "
            "official president or congressional rosters"
        ),
        params=(NAMES_WIKI,),
    ),
    "/v1/noticias": ExternalRoute(
        path="/v1/noticias",
        domain="other",
        summary=(
            "Google News RSS search for Argentine Spanish results. "
            "Rows: title, source, publishedAt, url. Choose concise SPANISH q "
            "keywords from the user's topic; optional desde/hasta ISO dates "
            "support historical search. Bind News (client-side pagination)."
        ),
        params=(Q_NEWS, DESDE, HASTA),
    ),
    "/v1/cine/discover": ExternalRoute(
        path="/v1/cine/discover",
        domain="other",
        summary=(
            "Argentine cinema browse (TMDB discover, origin_country=AR fixed). "
            "Rows: id, titulo, fecha, overview, foto, valor(=vote_average), "
            "votos, popularidad. Optional anio, genero, sort, page. "
            "Compose List with foto + titulo + valor. Attribution: TMDB"
        ),
        params=(ANIO_CINE, GENERO_CINE, SORT_CINE, PAGE_CINE),
    ),
    "/v1/cine/search": ExternalRoute(
        path="/v1/cine/search",
        domain="other",
        summary=(
            "Search Argentine films by title (q= required). Filters to "
            "origin_country AR. Same row shape as discover. Then "
            "/v1/cine/pelicula/{id} for cast + synopsis"
        ),
        params=(Q_CINE, ANIO_CINE),
    ),
    "/v1/cine/pelicula/{id}": ExternalRoute(
        path="/v1/cine/pelicula/{id}",
        domain="other",
        summary=(
            "One Argentine film: overview, runtime, generos, valor, foto, "
            "elenco (PersonCard: name, photoUrl, role), trailer_url. "
            "Rejects non-AR origin. Stack: Text + MetricRow + PersonCards"
        ),
        path_params=("id",),
    ),
    "/v1/cine/persona/search": ExternalRoute(
        path="/v1/cine/persona/search",
        domain="other",
        summary=(
            "Search people (actors/directors) by name (q=). Rows: id, nombre, "
            "foto, conocido_por. Then /v1/cine/persona/{id} (PersonCard) and "
            "/v1/cine/persona/{id}/filmografia (List)"
        ),
        params=(Q_CINE,),
    ),
    "/v1/cine/persona/{id}": ExternalRoute(
        path="/v1/cine/persona/{id}",
        domain="other",
        summary=(
            "Person bio for PersonCard (nombre, foto, bio). Also embeds "
            "filmografia[] — do NOT List that nested array (shows a count); "
            "fetch …/filmografia for flat movie rows, or bind List columns "
            "titulo/foto/valor (bind expands filmografia)"
        ),
        path_params=("id",),
    ),
    "/v1/cine/persona/{id}/filmografia": ExternalRoute(
        path="/v1/cine/persona/{id}/filmografia",
        domain="other",
        summary=(
            "FLAT Argentine-origin films for one person (titulo, fecha, foto, "
            "valor, overview). Prefer this for List over nested filmografia "
            "on /v1/cine/persona/{id}. Columns: foto + titulo + fecha + valor"
        ),
        path_params=("id",),
    ),
    "/v1/rem": ExternalRoute(
        path="/v1/rem",
        domain="finance",
        summary=(
            "Curated BCRA REM aliases (ipc, ipc_nucleo, tc, desempleo) with "
            "the realized series each joins against. Prefer these over raw "
            "/v1/finanzas/rem for charts and vs-real"
        ),
    ),
    "/v1/rem/ultimo": ExternalRoute(
        path="/v1/rem/ultimo",
        domain="finance",
        summary=(
            "Latest REM survey rows. Pass alias=ipc|tc|desempleo to keep one "
            "indicator (muestra=todos default). Snapshot / ComparisonTable / "
            "MetricRow — not a long Chart"
        ),
        params=(REM_ALIAS, REM_MUESTRA),
    ),
    "/v1/rem/informe": ExternalRoute(
        path="/v1/rem/informe",
        domain="finance",
        summary=(
            "One REM informe by año+mes (e.g. 2024 + 06). Optional alias= / "
            "muestra=. Use before vs-real when the user names a survey month"
        ),
        params=(REM_ANIO, REM_MES, REM_ALIAS, REM_MUESTRA),
    ),
    "/v1/rem/{alias}": ExternalRoute(
        path="/v1/rem/{alias}",
        domain="finance",
        summary=(
            "REM nowcast mediana over successive informes as {fecha, mediana, "
            "valor, unidad}. Aliases: ipc, ipc_nucleo, tc, desempleo. Chart "
            "kind=line. Pass desde/hasta on informe months"
        ),
        params=(DESDE, HASTA),
        path_params=("alias",),
    ),
    "/v1/rem/vs-real/{alias}": ExternalRoute(
        path="/v1/rem/vs-real/{alias}",
        domain="finance",
        summary=(
            "REM expectation vs realized outcome. Rows: fecha, esperado, real, "
            "error, error_abs, error_pct, informe. Aliases: ipc (vs inflación "
            "mensual), tc (vs oficial venta), desempleo (vs EPH). "
            "horizon=1m|nowcast|all (default 1m). Chart dual series "
            "esperado+real OR error; ComparisonTable for a short window"
        ),
        params=(DESDE, HASTA, REM_HORIZON),
        path_params=("alias",),
    ),
    "/v1/plazos": ExternalRoute(
        path="/v1/plazos",
        domain="finance",
        summary=(
            "Curated plazo-fijo surface. Prefer /v1/plazos/ranking over raw "
            "/v1/finanzas/tasas/plazoFijo (nested tasas[]). Pair with "
            "inflaciónInteranual or /v1/rem/ultimo alias=ipc for real yield"
        ),
    ),
    "/v1/plazos/ranking": ExternalRoute(
        path="/v1/plazos/ranking",
        domain="finance",
        summary=(
            "Banks ranked by best TNA (%). Rows: entidad, tna, plazoDias, "
            "valor(=tna), unidad. ComparisonTable highlight max tna; "
            "MetricRow for top bank vs inflación. Optional limit="
        ),
        params=(LIMIT_PLAZOS,),
    ),
    "/v1/hipotecarios-uva": ExternalRoute(
        path="/v1/hipotecarios-uva",
        domain="finance",
        summary=(
            "UVA mortgage TNAs flattened (%). Rows: entidad, tna, "
            "plazoMaxAnios, relacionCuotaIngreso, financiamiento. "
            "ComparisonTable highlight min tna. Pair /v1/finanzas/indices/uva "
            "+ /v1/rem for cuota risk — prefer over raw hipotecariosUva"
        ),
    ),
    "/v1/fci": ExternalRoute(
        path="/v1/fci",
        domain="finance",
        summary=(
            "Curated FCI aliases (delta_pesos_a, mercado_fondo_a). "
            "Unknown fund → /v1/fci/search?q= then /v1/fci/{slug}/historico"
        ),
    ),
    "/v1/fci/search": ExternalRoute(
        path="/v1/fci/search",
        domain="finance",
        summary=(
            "Search FCI by Spanish name (q=). Rows: slug, nombre, tipoRenta, "
            "horizonte, administradora. Then /v1/fci/{slug} or …/historico"
        ),
        params=(Q_FCI,),
    ),
    "/v1/fci/{slug}": ExternalRoute(
        path="/v1/fci/{slug}",
        domain="finance",
        summary=(
            "One FCI detail (slug or alias). MetricRow / Text — then "
            "/v1/fci/{slug}/historico for Chart"
        ),
        path_params=("slug",),
    ),
    "/v1/fci/{slug}/historico": ExternalRoute(
        path="/v1/fci/{slug}/historico",
        domain="finance",
        summary=(
            "FCI cuotaparte history as {fecha, valor}. Chart kind=line. "
            "Slug from /v1/fci/search or curated alias. Pass desde/hasta"
        ),
        params=(DESDE, HASTA),
        path_params=("slug",),
    ),
}

for _ext in EXTERNAL_ROUTES.values():
    if _ext.params:
        PARAM_SPECS[_ext.path] = _ext.params


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
