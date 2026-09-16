"""Widget catalog for the UI composer.

Each ``WidgetDef`` describes one widget in the registry: purpose, usage
guidance, and prop contract.  ``as_prompt_text()`` renders the full catalog
as a compact block injected into the compose_ui system prompt.

Adding a new widget requires only:
  1. A new ``WidgetDef`` entry here.
  2. A Pydantic schema in ``ui/schemas.py``.
  3. A React component + Zod schema in the frontend registry.
No changes to graph.py or the system prompt template.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WidgetDef:
    type: str       # Registry key — must match the frontend registry exactly.
    role: str       # "leaf" | "container"
    purpose: str    # One-line description of what the widget shows.
    when_to_use: str   # Guidance for the LLM on when to pick this widget.
    when_not: str      # Counter-examples / what to pick instead.
    props: str         # Compact prop description (name, type, required?).
    data: str | None = None  # Data-binding description, if applicable.
    #: Prop that receives the bound rows when the node carries a ``dataRef``.
    #: Chart/List read them from ``data``; PersonCard expects ``people``.
    data_prop: str = "data"
    #: For widgets with a named-field contract: target field → candidate row
    #: keys, tried in order, used to fill anything the composer's own `fields`
    #: mapping left out.  A tuple of keys means "join these values", and is
    #: only used when every key in it is present.
    field_aliases: dict[str, tuple] = field(default_factory=dict)


def _widget(widget_type: str) -> WidgetDef | None:
    for widget in WIDGET_CATALOG:
        if widget.type == widget_type:
            return widget
    return None


def data_prop_for(widget_type: str) -> str:
    """Which prop the bound rows go into for *widget_type*."""
    widget = _widget(widget_type)
    return widget.data_prop if widget else "data"


def field_aliases_for(widget_type: str) -> dict[str, tuple]:
    """Fallback row keys per target field for *widget_type*."""
    widget = _widget(widget_type)
    return widget.field_aliases if widget else {}


def requires_data_ref(widget_type: str) -> bool:
    """Whether a catalog widget is backed by a fetched dataset."""
    widget = _widget(widget_type)
    return bool(widget and widget.data)


WIDGET_CATALOG: list[WidgetDef] = [
    WidgetDef(
        type="Metric",
        role="leaf",
        purpose="Single key-value figure with optional percentage delta and trend.",
        when_to_use=(
            "One spot value: current FX rate, inflation reading, yield, country risk. "
            "Use for the most recent / current snapshot of a single indicator."
        ),
        when_not=(
            "2–6 spot values side by side (spread, blue+oficial+MEP) → MetricRow. "
            "Multiple values over time → Chart. "
            "A list of people (senators, deputies) → PersonCard. "
            "A list of other comparable records/options → List."
        ),
        props="label(str*); value(str|number*); unit?(str); delta?(number); trend?(up|down|flat)",
        data=None,
    ),
    WidgetDef(
        type="MetricRow",
        role="leaf",
        purpose="Horizontal strip of 2–6 spot Metrics (FX casas, spread KPIs).",
        when_to_use=(
            "Same-day comparison of a few scalars the user wants to scan together: "
            "blue vs oficial vs MEP, spread + riesgo, two mandate peaks. "
            "Inline items[] like Metric (no dataRef)."
        ),
        when_not=(
            "One figure → Metric. Time series → Chart. "
            "Spread evolution / serie del spread over days → Chart on "
            "derived/fx_spread (not spot MetricRow). "
            "One value per mandate/era with labels → PeriodBars."
        ),
        props=(
            "items([{label,value,unit?,delta?,trend?}]*, min 2 max 6) — "
            "same fields as Metric, authored from analyst [[values]] / notes"
        ),
        data=None,
    ),
    WidgetDef(
        type="WeatherUnit",
        role="leaf",
        purpose="Weather cards: icon + temp + min/max + rain, one per day.",
        when_to_use=(
            "/v1/clima/historico, /pronostico, or one-province /actual. "
            "Historical day: bind the same-fecha CABA (or row.provincia) "
            "clima fetch — NEVER paste °C into Text. "
        ),
        when_not=(
            "All 24 provinces current temp → ProvinceMap. "
            "Long climate series as evolution → Chart kind=line."
        ),
        props="dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)",
        data="dataRef = a /v1/clima/* dataset. Keys: fecha, provincia, tmin, tmax, temperatura, precipitacion, weather_code.",
    ),
    WidgetDef(
        type="Text",
        role="leaf",
        purpose="One-line caveat that sits under a data widget (source, lag, definition).",
        when_to_use=(
            "A short note that labels a Chart/List/Metric already on the canvas "
            "(e.g. 'Serie mensual, última observación agosto'). Keep it to one "
            "or two sentences. "
            "Historical-day context from historico/dia or wiki/summary: use "
            "Text with the full extract (3–6 sentences) — title = event headline. "
            "PersonCard for the day's protagonists is a separate official-roster "
            "or wiki/personas fetch, not this Text."
        ),
        when_not=(
            "The answer to a question, a list of suggestions, 'qué más podríamos "
            "agregar', explanations, chitchat, or a failed search ('no se "
            "encontraron registros para X') — those go in `brief`, never on "
            "the canvas. A highlighted finding under a chart → Callout. "
            "Numeric series → Chart. A spot value → Metric. "
            "Climate (tmin/tmax/temperatura, 'T° media… mm') → WeatherUnit "
            "on the clima dataRef — never paste °C into content."
        ),
        props="content(str*)",
        data=None,
    ),
    WidgetDef(
        type="Callout",
        role="leaf",
        purpose="Short anchored finding (peak date, join insight) under a chart.",
        when_to_use=(
            "One punchy takeaway that belongs next to a Chart/AnnotatedTimeline "
            "(e.g. 'Pico de riesgo el 12-mar; ese día no hubo sesión'). "
            "Keep to 1–2 sentences. tone=insight|info|warning."
        ),
        when_not=(
            "Full answer / chat reply → brief. Source caveats → Text. "
            "Raw numbers without a finding → Metric. "
            "NEVER dump same-day spot values (blue/MEP/CCL/riesgo/spreads, "
            "'valores del día', detalle de una fecha) as a prose paragraph — "
            "that is a key-value List on derived/values (or MetricRow)."
        ),
        props="content(str*); eyebrow?(str); tone?(insight|info|warning)",
        data=None,
    ),
    WidgetDef(
        type="Chart",
        role="leaf",
        purpose=(
            "Numeric chart: line/area/bar, dual-axis line, scatter, or heatmap."
        ),
        when_to_use=(
            "kind=line|area for ordered X (time/sequence). kind=bar for "
            "totals/categories (few rows; xKey=label). "
            "HARD: 2+ measures same X → ONE Chart with multiple series[] "
            "(prefer derived/series_overlay). "
            "Spread evolution → derived/fx_spread (xKey=fecha, "
            "series spread|spread_pct) — replace spot Metric/MetricRow. "
            "Dual scale: yAxisIndex 0|1. scatter=two numerics; heatmap=matrix. "
            "Vote by bloque: kind=bar, xKey=bloque, series "
            "afirmativo/negativo/abstencion/ausente on raw …/votos rows."
        ),
        when_not=(
            "Spot → Metric/MetricRow. Marks/bands → AnnotatedTimeline. "
            "One value per period → PeriodBars. "
            "National 'distribución del voto' (no bloque) → VoteBreakdown. "
            "Same-day FX 'de ese día' → Metric/MetricRow from [[values]], "
            "not Chart kind=line. Provinces → ProvinceMap. People → PersonCard. "
            "Table → List. NEVER N Charts for shared axes. "
            "Cruce ('quiénes + blue'): pair Charts with a political layer "
            "(Acta/PersonCard/VoteBreakdown/ProvinceMap)."
        ),
        props=(
            "kind(line|bar|area|scatter|heatmap*); xKey(str*); "
            "yKey?(str — scatter/heatmap); "
            "seriesBy?(str — long-format category); "
            "valueKey?(str — long-format measure or heatmap value); "
            "series([{key,label,color?,yAxisIndex?(0|1)}]*); "
            "selectAs?(persona|provincia|fecha|fila); dataRef(str*); "
            "sort?({key,dir}); limit?(int). Omit color unless user names hex."
        ),
        data=(
            "dataRef = dataset id. series[].key must exist OR be vote labels "
            "when xKey=bloque|partido. "
            "Long-format team-season rows: xKey=season, seriesBy=team, "
            "valueKey=the metric (for example pointsPerGame or "
            "goalDifferencePerGame), and one series key per exact team value. "
            "Never use team names as series keys without seriesBy+valueKey; "
            "never bind two teams to one winRate series. For home/away columns "
            "such as homePointsPerGame and awayPointsPerGame, use one Chart per "
            "team with scalar where={team: exactName}; do not put two teams in "
            "the same Chart because season repeats. "
            "derived/series_overlay: xKey=params.x; one series per other key; "
            "labels from params.labels. "
            "derived/fx_spread: xKey=params.x; series spread|spread_pct. "
            "sort+limit for 'últimos N' — never assume pre-trimmed size."
        ),
    ),
    WidgetDef(
        type="AnnotatedTimeline",
        role="leaf",
        purpose=(
            "Time series with event markLines and/or mandate/era band overlays."
        ),
        when_to_use=(
            "Blue/riesgo around a vote day; series + 'inicio de mandato'; "
            "FX with colored bands per presidency. Peak of a series + "
            "Congreso that day → mark the peak ISO (from the analyst note) "
            "and List the day's actas underneath (or Callout if no session). "
            "marks[] and bands[] are authored by compose (dates from the "
            "analyst note), data via dataRef. Do not redraw the series as Box SVG."
        ),
        when_not=(
            "Plain series with no events/bands → Chart kind=line. "
            "One number per period → PeriodBars. Dual unrelated scales without "
            "marks → Chart with yAxisIndex."
        ),
        props=(
            "xKey(str*); series([{key,label,color?}]*); "
            "marks?([{x,label}]); bands?([{from,to,label,color?}]); "
            "dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "dataRef → dated numeric rows. marks.x / bands.from|to should match "
            "values present (or nearest) on the x axis (fecha ISO)."
        ),
    ),
    WidgetDef(
        type="PeriodBars",
        role="leaf",
        purpose="One bar per period/mandate with optional date-range sublabel.",
        when_to_use=(
            "Máximo blue por mandato, inflación media por gobierno — few "
            "rows with a period label + numeric value (+ optional sublabel "
            "with date window)."
        ),
        when_not=(
            "Long time series → Chart/AnnotatedTimeline. "
            "Same-day FX casas → MetricRow or Chart bar."
        ),
        props=(
            "labelKey(str*); valueKey(str*); sublabelKey?(str); "
            "selectAs?(persona|provincia|fecha|fila) — click-to-deepen "
            "when bars are people/places; omit to infer from row.entity; "
            "dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "dataRef rows must include labelKey + valueKey (+ sublabelKey). "
            "Prefer ``derived/period_levels`` (keys: label, value, sublabel) "
            "or ``derived/values`` (label, value). "
            "NEVER bind a raw dated series or a presidents roster alone — "
            "those have no per-period aggregate column."
        ),
    ),
    WidgetDef(
        type="VoteBreakdown",
        role="leaf",
        purpose="Donut/pie of AFIRMATIVO / NEGATIVO / ABSTENCIÓN counts.",
        when_to_use=(
            "Summarize one roll call's result composition — "
            "'distribución del voto', how the chamber split, "
            "AFIRMATIVO/NEGATIVO/ABSTENCIÓN shares. Pass the votos "
            "dataset; widget aggregates by voteKey (default 'voto')."
        ),
        when_not=(
            "Who voted how (people) → PersonCard or Acta. "
            "Split by bloque/partido → Chart kind=bar (xKey=bloque, "
            "series afirmativo/negativo/abstencion/ausente on the same "
            "votos rows). "
            "Many bills → List. Province lean → ProvinceMap. "
            "NEVER a Chart kind=line on votos rows."
        ),
        props=(
            "dataRef(str*); voteKey?(str=voto); kind?(donut|pie); "
            "sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data="dataRef = roll-call rows with a scalar voto field.",
    ),
    WidgetDef(
        type="ProvinceMap",
        role="leaf",
        purpose=(
            "Geographic comparison across Argentine provinces: makes regional "
            "concentration, gaps, and outliers visible at a glance."
        ),
        when_to_use=(
            "Prefer ProvinceMap whenever province is a meaningful comparison "
            "dimension — even if the request also asks for another grouping such "
            "as bloque, partido, category, or vote sense. Examples: vote lean or "
            "counts by provincia, negativos por provincia, senators by district, "
            "or any indicator available for several provinces. If the complete "
            "answer also needs a non-geographic breakdown, compose ProvinceMap "
            "with the appropriate Chart/VoteBreakdown instead of replacing the "
            "map with one crowded chart. The map encodes one measure: choose the "
            "measure emphasized by the question (for example 'negativo') and use "
            "the companion widget for the full multi-series breakdown. Set "
            "nameKey=provincia and valueKey to a numeric count column OR a vote "
            "label when rows are a raw roll call with provincia+voto; the widget "
            "counts matching rows per province."
        ),
        when_not=(
            "Person roster → PersonCard. National time series → Chart. "
            "Vote shares without geography → VoteBreakdown. Do not omit the map "
            "merely because the same request also mentions bloque or vote sense."
        ),
        props=(
            "dataRef(str*); nameKey?(str=provincia); valueKey(str*); "
            "sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "Prefer rows already counted per province "
            "(provincia + count/total/n). Raw …/votos rows also work: set "
            "valueKey to the vote to count (e.g. 'negativo') and nameKey="
            "provincia — the widget aggregates. Never invent province totals."
        ),
    ),
    WidgetDef(
        type="PersonCard",
        role="leaf",
        purpose=(
            "People with photo + name (+ optional role/party/province/voto, "
            "and on a single profile: email/phone/social + Wikipedia bio): "
            "one detailed profile, or a roster list/grid of many."
        ),
        when_to_use=(
            "Legislator/president profile, roster, OR …/votos with "
            "foto|imagen and/or bloque|partido — map voto→role, "
            "foto/imagen→photoUrl, bloque/partido→party. "
            "Historical day with persona: 1-row /v1/presidentes "
            "(name←nombre, photoUrl←imagen, party←partido, "
            "role←periodoPresidencial) — NEVER historico/dia. "
            "Other named public figures: /v1/wiki/personas "
            "(name←nombre, photoUrl←foto, party←partido, bio←bio, "
            "links←redes). Prefer official rosters when available. "
            "Film cast: bind /v1/cine/pelicula/{id} (nested elenco); "
            "name←name|nombre, photoUrl←foto, role←role|cargo. "
            "Single profile with email/telefono/redes → map those too. "
            "Wikipedia bio attaches automatically on 1-row cards. "
            "layout=list for long lists; grid (default) for compact. "
            "One row → profile; 2+ → roster."
        ),
        when_not=(
            "Names-only roll call (nombre+voto, no foto/bloque) → Acta. "
            "Tabular non-people → List. historico/dia → Text, not PersonCard. "
            "Series → Chart. Custom linked visual among people → Box."
        ),
        props=(
            "dataRef(str*); fields({name(*), photoUrl?, role?, party?, "
            "province?, email?, phone?, links?, bio?}*); layout?(grid|list); "
            "sort?({key,dir}); limit?(int)."
        ),
        data=(
            "dataRef = dataset id — NEVER type names/photos into props. "
            "`fields` maps card field → row key, e.g. "
            "{name:'nombre', photoUrl:'foto', party:'bloque'} or "
            "{name:'nombre', photoUrl:'imagen', role:'voto'} or "
            "{name:'nombre', photoUrl:'imagen', party:'partido', "
            "role:'periodoPresidencial'}. "
            "NEVER map role/party to nested objects (periodoLegal/Real). "
            "Never map role→bloque. Map email/telefono/redes/bio on profiles. "
            "Join split names: {name:['nombre','apellido']}. "
            "Non-key values are literals (role:'Senador')."
        ),
        data_prop="people",
        field_aliases={
            "name": (("nombre", "apellido"), "nombre", "name", "diputado", "senador"),
            "photoUrl": ("foto", "imagen", "photoUrl"),
            # partido = alianza electoral; bloque = bancada (prefer bloque on card)
            "party": ("bloque", "partido", "party"),
            "province": ("provincia", "province"),
            # Never alias role → bloque (that duplicates party). Literal
            # "Senador"/"Diputado" or voto / periodoPresidencial only.
            "role": ("voto", "periodoPresidencial", "role", "cargo", "character"),
            "email": ("email",),
            "phone": ("telefono", "phone"),
            "links": ("redes", "links"),
            "bio": ("bio", "extract"),
        },
    ),
    WidgetDef(
        type="FootballLineup",
        role="leaf",
        purpose=(
            "Confirmed or projected football lineups on a responsive pitch, "
            "with player portraits/names, formations, coaches and substitutes."
        ),
        when_to_use=(
            "Only for /v1/football/matches/{matchId}/lineup or "
            "/v1/football/league/latest-lineup. For a specific match, pass "
            "homeTeam/awayTeam and logos from its result when available. Show "
            "the two returned side rows together in one FootballLineup."
        ),
        when_not=(
            "Standings, results or team-season statistics → ComparisonTable, "
            "Chart or MetricRow. Do not render eleven PersonCards, a generic "
            "List, authored SVG players, or invented positions."
        ),
        props="dataRef(str*)",
        data=(
            "dataRef = lineup dataset. It already contains 1–2 rows shaped as "
            "side(home|away), team, logo?, formation?, isProjected, starting[], "
            "substitutes[] and coach?. No fields map and no authored player data."
        ),
    ),
    WidgetDef(
        type="Acta",
        role="leaf",
        purpose=(
            "One legislative vote: date, result and the official title once, "
            "then the roll call of how each legislator voted."
        ),
        when_to_use=(
            "A single acta / bill roll call that is NAMES + voto ONLY (no "
            "foto/imagen and no bloque/partido on the rows): 'cuándo se votó "
            "y cómo votó cada uno' before roster enrichment. Shared "
            "titulo/fecha/resultado belong in the header, not repeated per row."
        ),
        when_not=(
            "``/search/actas`` or any bill directory (titulo/fecha/resultado, "
            "no nombre+voto) → List — Acta would show an empty roll call. "
            "Rows with nombre+voto PLUS foto|imagen|bloque|partido → "
            "PersonCard layout=list (map voto→role, foto/imagen→photoUrl, "
            "bloque/partido→party). "
            "Several candidate bills (more than one distinct título, no voto "
            "column) → List. "
            "A directory of people without a vote column → PersonCard. "
            "A numeric series → Chart. "
            "NEVER render a nombre+voto dataset as List with columns "
            "titulo/fecha/resultado — that hides who voted."
        ),
        props="dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)",
        data=(
            "dataRef must be an id from the available datasets index — ONLY "
            "``…/actas/id/{actaId}/votos`` (or equivalent rows with nombre+voto). "
            "NEVER bind ``/search/actas`` hits here: those rows are "
            "id/titulo/fecha/resultado/camara with NO voto column → use List. "
            "You never type names or the acta title into props. The widget "
            "reads titulo/fecha/resultado once from the rows and lists each "
            "legislator's nombre + voto. Do NOT also emit a List of the same "
            "votes."
        ),
        field_aliases={
            "title": ("titulo", "title"),
            "date": ("fecha", "date"),
            "result": ("resultado", "result"),
            "voter": ("nombre", "diputado", "senador", "name"),
            "vote": ("voto", "tipoVoto", "vote"),
        },
    ),
    WidgetDef(
        type="News",
        role="leaf",
        purpose="Paginated news headlines with source, publication date and article link.",
        when_to_use=(
            "/v1/noticias results. Show every returned headline in this dedicated "
            "editorial list; pagination is handled inside the widget."
        ),
        when_not=(
            "Legislation or generic tabular records → List. Narrative context → "
            "Text. Never inline news rows in props."
        ),
        props="dataRef(str*)",
        data=(
            "dataRef = /v1/noticias dataset with title, source, publishedAt, url. "
            "No authored rows and no columns mapping."
        ),
    ),
    WidgetDef(
        type="List",
        role="leaf",
        purpose=(
            "Compact table of records — a set of items that share fields but "
            "aren't a numeric time series, a person, or a single acta roll call: "
            "many laws/sessions, bank rates, generic listings."
        ),
        when_to_use=(
            "Tabular SCALAR records (leyes título/fecha/resultado; "
            "derived/transform vote history titulo/fecha/voto). "
            "HARD — day snapshot / 'valores del día' / canvas fecha: with "
            "derived/values emit ONE List as a key-value table "
            "(columns label→Indicador, value→Valor, unit→Unidad). "
            "Never paste those figures into Callout."
        ),
        when_not=(
            "Series → Chart. People with foto → PersonCard. "
            "Full roll call nombre+voto → Acta. "
            "NEVER a ``votos`` array column (transform first). "
            "Spot → Metric/MetricRow. Climate → WeatherUnit. "
            "Fees/remesas → ComparisonTable. Narrative → Text."
        ),
        props=(
            "columns([{key,label,kind?(text|image|date|url|number)}]*); "
            "dataRef(str*); sort?({key,dir}); limit?(int). "
            "kind=image for foto URL fields (or inferred from .jpg/.png)."
        ),
        data=(
            "dataRef = dataset id. Scalar columns only — nested arrays "
            "(filmografia, votos, viajes) show a count; fetch a flat endpoint "
            "or columns foto+titulo+valor. "
            "All-fields asks → every scalar key. "
            "sort+limit REQUIRED for 'últimas N' — raw API order is not trimmed."
        ),
    ),
    WidgetDef(
        type="ComparisonTable",
        role="leaf",
        purpose=(
            "Side-by-side comparison of alternatives — fees, brokers, remesas, "
            "plazos fijos, hipotecarios UVA, short REM vs-real windows — with "
            "optional highlight of the best numeric value."
        ),
        when_to_use=(
            "/v1/plazos/ranking, /v1/hipotecarios-uva, "
            "/v1/finanzas/brokers/comisiones, cobros/comisiones, remesas, "
            "or a short /v1/rem/vs-real/{alias} slice where rows are options "
            "to weigh. primary=true on the entity column (entidad, "
            "nombreComercial, compania, periodo). "
            "highlight={key,direction:min|max} for best TNA (max) / cheapest "
            "fee / lowest mortgage TNA (min). "
            "Set kind explicitly per column (percent|money|number|date|url|"
            "text) — do not rely on key-name inference. "
            "Curated plazos/hipotecarios already expose TNA as percent "
            "(18.5). Raw fee tasas/aranceles are fractions (0.005); either "
            "kind=number or pre-scale — kind=percent prints the raw value + %."
        ),
        when_not=(
            "Long time series → Chart. Generic law/session listings → List. "
            "People rosters → PersonCard. Spot KPIs → Metric/MetricRow. "
            "Full REM history vs reality as evolution → Chart on "
            "/v1/rem/vs-real/{alias} (esperado+real or error). "
            "FCI history → Chart on /v1/fci/{slug}/historico."
        ),
        props=(
            "columns([{key,label,kind?(text|number|percent|money|date|url),"
            "primary?(bool)}]* min 2 max 8); dataRef(str*); "
            "highlight?({key,direction:min|max}); sort?({key,dir}); limit?(int)"
        ),
        data=(
            "dataRef = plazos/hipotecarios/fee/remesa/vs-real dataset. "
            "Plazos keys: entidad, tna, plazoDias. Hipotecarios: entidad, "
            "tna, plazoMaxAnios. Fee endpoints return flat rows "
            "(entidad, producto, tasa/arancel, …). vs-real keys: "
            "periodo/fecha, esperado, real, error, error_pct."
        ),
    ),
    WidgetDef(
        type="Stack",
        role="container",
        purpose="Vertical column layout for grouping 2–4 leaf widgets.",
        when_to_use=(
            "Combine a Chart with a Callout or Metric below/above it, "
            "or group widgets in a single column. "
            "Cruce (politics + economy): Stack with political layer "
            "(Acta/PersonCard/VoteBreakdown) then economic — MetricRow "
            "for same-day spots, Chart/AnnotatedTimeline for evolution. "
            "Historical day: include only relevant fetched leaves; usually "
            "Text + requested Chart, plus News for coverage/context."
        ),
        when_not=(
            "Single widget — no wrapper needed. "
            "Side-by-side layout (chart + roster, two charts) → Grid."
        ),
        props="gap?(sm|md|lg)  — controls vertical spacing between children",
        data=None,
    ),
    WidgetDef(
        type="Grid",
        role="container",
        purpose="Responsive 2–3 column layout for leaf widgets.",
        when_to_use=(
            "Put a Chart beside a VoteBreakdown/PersonCard, or two series "
            "side by side. columns=2 (default) or 3. "
            "ONLY when the user asked for side-by-side. Historical day "
            "defaults to Stack (PersonCard, Text, WeatherUnit, Chart)."
        ),
        when_not=(
            "Single column flow → Stack. "
            "One widget alone — no wrapper."
        ),
        props="columns?(2|3); gap?(sm|md|lg)",
        data=None,
    ),
    WidgetDef(
        type="Box",
        role="container",
        purpose=(
            "Free HTML/SVG layout when the user wants a visual form that "
            "catalog leaves cannot express (linked steps, ordered "
            "transitions, facet grids, conceptual matrices). Must match "
            "the bulletin look — not a bare wireframe."
        ),
        when_to_use=(
            "User asks for a visual form a catalog leaf would flatten wrong — "
            "diagram, flow, matrix, 'dibujame…', 'como un…', linked steps, "
            "ordered transitions — even if PersonCard/List/Chart could show "
            "the same facts. Also: conceptual matrices with no rows to bind. "
            "User-named form beats the default leaf. "
            "Craft: font-display for names, text-muted-foreground for "
            "secondary lines, text-accent + SVG currentColor connectors, "
            "gap-4/6 + border-rule blocks, bg-accent-soft pads. Build one "
            "subject-specific composition with a dominant focal point and "
            "meaningful spatial encoding; use hierarchy, whitespace and "
            "alignment deliberately. Never emit a naked stack of unstyled "
            "text or a generic grid of equal cards disguised as custom work. "
            "Optional suggests=PascalCaseName for a future named widget."
        ),
        when_not=(
            "Plain 'plot this series' / roll call / weather with no custom "
            "form ask → Chart / Acta / WeatherUnit. "
            "Spot figures → Metric/MetricRow. Punchy finding → Callout. "
            "Source caveat / wiki extract → Text. "
            "Default people roster with no special structure → PersonCard. "
            "NEVER put dataRef on Box — author copy from the analyst note."
        ),
        props=(
            "className?(safelist utilities); suggests?(PascalCase). "
            "Host child props: className?, text?, plus SVG attrs "
            "(viewBox, d, x1,y1,x2,y2, stroke, fill, markerEnd, strokeWidth). "
            "Hosts: div,p,span,h2,h3,ul,ol,li,dl,dt,dd,strong,em, "
            "svg,g,path,line,polyline,polygon,circle,rect,text,defs,marker."
        ),
        data=None,
    ),
]


def as_prompt_text() -> str:
    """Compact text block for the compose_ui system prompt.

    One section per widget type.  Kept short on purpose — the LLM only needs
    purpose + use-when guidance + props.  Avoid prose padding.
    """
    lines: list[str] = []
    for w in WIDGET_CATALOG:
        lines.append(f"### {w.type}  (role: {w.role})")
        lines.append(f"Purpose: {w.purpose}")
        lines.append(f"Use when: {w.when_to_use}")
        lines.append(f"Avoid when: {w.when_not}")
        lines.append(f"Props: {w.props}")
        if w.data:
            lines.append(f"Data: {w.data}")
        lines.append("")
    return "\n".join(lines).rstrip()


def widget_types() -> list[str]:
    """All registered widget type keys."""
    return [w.type for w in WIDGET_CATALOG]
