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
    #: When non-empty, rows containing all these keys require this specialized
    #: widget instead of a generic/text-only representation.
    required_data_keys: frozenset[str] = field(default_factory=frozenset)


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


def required_widgets_for_dataset_keys(keys: set[str]) -> set[str]:
    """Specialized widgets whose declared row contract matches ``keys``."""
    return {
        widget.type
        for widget in WIDGET_CATALOG
        if widget.required_data_keys
        and widget.required_data_keys.issubset(keys)
    }


WIDGET_CATALOG: list[WidgetDef] = [
    WidgetDef(
        type="Metric",
        role="leaf",
        purpose="Single key-value figure with optional percentage delta and trend.",
        when_to_use=(
            "Use when one scalar is the complete visual message and its label "
            "provides enough context. Delta and trend may add a compact comparison."
        ),
        when_not=(
            "Several peer scalars → MetricRow. Values indexed by time or category "
            "→ Chart. Repeated structured records → List or a subject-specific widget."
        ),
        props="label(str*); value(str|number*); unit?(str); delta?(number); trend?(up|down|flat)",
        data=None,
    ),
    WidgetDef(
        type="MetricRow",
        role="leaf",
        purpose="Horizontal strip of 2–6 related scalar metrics.",
        when_to_use=(
            "Use for a small set of peer values that should be scanned and compared "
            "as one snapshot. Items are authored inline and share Metric semantics."
        ),
        when_not=(
            "One scalar → Metric. Values whose order, trend, or category spacing "
            "matters → Chart or PeriodBars. More than six records → List."
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
        purpose="Weather observations or forecasts as icon-led cards.",
        when_to_use=(
            "Use for one or more weather rows when temperature, conditions, "
            "minimum/maximum, or precipitation are the primary information."
        ),
        when_not=(
            "Geographic comparison across provinces → ProvinceMap. "
            "A long numeric evolution → Chart. Do not reproduce weather values in Text."
        ),
        props="dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)",
        data=(
            "Rows may provide date, location, temperature, minimum, maximum, "
            "precipitation and weather-code fields recognized by the widget."
        ),
    ),
    WidgetDef(
        type="Text",
        role="leaf",
        purpose="Short contextual prose that belongs on the canvas.",
        when_to_use=(
            "Use for a source note, definition, caveat, or short narrative extract "
            "that materially explains nearby widgets. Prefer one or two sentences; "
            "a sourced narrative may be longer when prose itself is the content."
        ),
        when_not=(
            "Conversation, follow-up suggestions, errors, or search misses → brief. "
            "A highlighted conclusion → Callout. Structured or numeric data → the "
            "corresponding data widget; do not transcribe it into prose."
        ),
        props="content(str*)",
        data=None,
    ),
    WidgetDef(
        type="Callout",
        role="leaf",
        purpose="Short emphasized finding anchored to nearby evidence.",
        when_to_use=(
            "Use for one evidence-backed takeaway that deserves emphasis next to "
            "the widget that supports it. Keep it to one or two sentences."
        ),
        when_not=(
            "Full answer → brief. Source or methodology note → Text. "
            "Raw values without an interpretation → Metric, MetricRow, or List."
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
            "Use line or area for an ordered numeric evolution, bar for a small "
            "categorical comparison, scatter for the relationship between two "
            "numeric variables, and heatmap for a numeric matrix. Put compatible "
            "measures sharing the same X and grain in one Chart; use yAxisIndex "
            "when their scales differ."
        ),
        when_not=(
            "Spot → Metric/MetricRow. Marks/bands → AnnotatedTimeline. "
            "One value per period → PeriodBars. "
            "Qualitative positions, spectra, relationships, flows, hierarchies "
            "or matrices with no source-backed numeric magnitude → authored "
            "Box. Never invent scores/ranks to force qualitative labels into "
            "bars or numeric axes. "
            "Geographic values → ProvinceMap. People → PersonCard. "
            "Simple record lookup → List. Do not split compatible series that "
            "share an axis and grain into multiple charts."
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
            "series[].key must name numeric row columns. Wide data requires one "
            "row per xKey after filtering. For long data, set seriesBy to the "
            "category field, valueKey to the numeric measure, and use exact "
            "category values as series keys. Apply sort and limit explicitly "
            "when the requested order or count matters."
        ),
    ),
    WidgetDef(
        type="AnnotatedTimeline",
        role="leaf",
        purpose=(
            "Time series with event markLines and/or mandate/era band overlays."
        ),
        when_to_use=(
            "Use when event markers or labeled intervals are essential to "
            "interpreting a dated numeric series. Author marks and bands from "
            "source-backed dates; bind the numeric series through dataRef."
        ),
        when_not=(
            "Plain series with no events/bands → Chart kind=line. "
            "One aggregate per labeled period → PeriodBars. Multiple scales without "
            "annotations → Chart. Do not redraw a standard timeline as Box SVG."
        ),
        props=(
            "xKey(str*); series([{key,label,color?}]*); "
            "marks?([{x,label}]); bands?([{from,to,label,color?}]); "
            "dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "Rows need an ordered x field and numeric series fields. marks.x and "
            "bands.from|to must use values compatible with the x-axis domain."
        ),
    ),
    WidgetDef(
        type="PeriodBars",
        role="leaf",
        purpose="One prominent value per labeled period with an optional sublabel.",
        when_to_use=(
            "Use for a small set of already aggregated period rows where the "
            "period labels and values matter more than within-period evolution."
        ),
        when_not=(
            "Raw or long time series → Chart/AnnotatedTimeline. "
            "Unordered categories → Chart bar. A scalar snapshot → MetricRow."
        ),
        props=(
            "labelKey(str*); valueKey(str*); sublabelKey?(str); "
            "selectAs?(persona|provincia|fecha|fila) — click-to-deepen "
            "when bars are people/places; omit to infer from row.entity; "
            "dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "dataRef rows must include labelKey + valueKey (+ sublabelKey). "
            "Each row must already represent one period and one aggregate value; "
            "the widget does not aggregate raw observations into periods."
        ),
    ),
    WidgetDef(
        type="VoteBreakdown",
        role="leaf",
        purpose="Donut or pie showing the composition of one roll-call vote.",
        when_to_use=(
            "Use when the primary question is how one roll call divides across "
            "vote categories. The widget counts rows by voteKey."
        ),
        when_not=(
            "Individual voters → PersonCard or Acta. Vote categories crossed with "
            "another dimension → Chart. Multiple roll calls → List. Geographic "
            "distribution → ProvinceMap."
        ),
        props=(
            "dataRef(str*); voteKey?(str=voto); kind?(donut|pie); "
            "sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data="Rows must contain one scalar vote category per voter under voteKey.",
    ),
    WidgetDef(
        type="ProvinceMap",
        role="leaf",
        purpose=(
            "Geographic comparison across Argentine provinces: makes regional "
            "concentration, gaps, and outliers visible at a glance."
        ),
        when_to_use=(
            "Use when province is a meaningful comparison dimension and spatial "
            "patterns are part of the answer. Encode one measure; add a companion "
            "widget if another non-geographic breakdown is also required."
        ),
        when_not=(
            "Geography is incidental or only one province is present → another "
            "widget. Time evolution → Chart. People → PersonCard. Non-geographic "
            "composition → Chart or a subject-specific breakdown."
        ),
        props=(
            "dataRef(str*); nameKey?(str=provincia); valueKey(str*); "
            "sort?({key,dir:asc|desc}); limit?(int)"
        ),
        data=(
            "nameKey identifies the province. valueKey identifies the numeric "
            "measure, or a supported category to count when rows are nominal. "
            "Never invent or infer missing provincial values."
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
            "Use for one person profile or a roster when identity and person-specific "
            "attributes are the primary content. One row renders a profile; multiple "
            "rows render a grid or list."
        ),
        when_not=(
            "A roll call whose structure matters → Acta. Non-people records → List. "
            "Numeric series → Chart. A custom relationship among people → Box."
        ),
        props=(
            "dataRef(str*); fields({name(*), photoUrl?, role?, party?, "
            "province?, email?, phone?, links?, bio?}*); layout?(grid|list); "
            "sort?({key,dir}); limit?(int)."
        ),
        data=(
            "dataRef = dataset id — NEVER type names/photos into props. "
            "`fields` maps semantic card fields to scalar row keys. A field may "
            "join multiple keys, and literal values are allowed for shared metadata. "
            "Do not map fields to nested objects."
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
            "Use for one match's lineup data when player positions, formation, "
            "starters, substitutes, and coaches should be read as a team shape. "
            "Show both returned sides together in one widget."
        ),
        when_not=(
            "Standings, results, or aggregate statistics → ComparisonTable, Chart, "
            "or MetricRow. Do not replace a lineup with PersonCards/List or invent "
            "missing positions."
        ),
        props="dataRef(str*)",
        data=(
            "Rows must use the lineup contract: "
            "side(home|away), team, logo?, formation?, isProjected, starting[], "
            "substitutes[] and coach?. No fields map and no authored player data."
        ),
        required_data_keys=frozenset({"side", "team", "starting"}),
    ),
    WidgetDef(
        type="Acta",
        role="leaf",
        purpose=(
            "One legislative vote: date, result and the official title once, "
            "then the roll call of how each legislator voted."
        ),
        when_to_use=(
            "Use for one legislative roll call when the act metadata and each "
            "legislator's vote should be read as one document. Shared metadata "
            "appears once in the header."
        ),
        when_not=(
            "A directory of acts or bills without voter rows → List. Multiple "
            "distinct roll calls → List first. A people directory without votes "
            "→ PersonCard. Numeric evolution → Chart."
        ),
        props="dataRef(str*); sort?({key,dir:asc|desc}); limit?(int)",
        data=(
            "Rows must represent one roll call and contain voter + vote fields; "
            "title, date, and result may repeat and are rendered once. Do not "
            "author names or metadata in props or duplicate the same votes in List."
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
            "Use for a collection of news articles when headline, source, date, "
            "and link are the relevant fields. Pagination is internal."
        ),
        when_not=(
            "Legislation or generic tabular records → List. Narrative context → "
            "Text. Never inline news rows in props."
        ),
        props="dataRef(str*)",
        data=(
            "Rows must follow the news contract with title, source, publication "
            "date, and URL. No authored rows or columns mapping."
        ),
    ),
    WidgetDef(
        type="List",
        role="leaf",
        purpose=(
            "Compact table of records — a set of items that share fields but "
            "are not better represented by a semantic or quantitative widget."
        ),
        when_to_use=(
            "Use for repeated scalar records, directories, search results, or a "
            "key-value detail whose columns are important and comparable."
        ),
        when_not=(
            "Numeric evolution → Chart. People → PersonCard. One roll call → Acta. "
            "A decision-oriented comparison → ComparisonTable. Scalar highlights "
            "→ Metric/MetricRow. Narrative → Text. A bespoke grouped or hierarchical "
            "table whose structure cannot be expressed by columns → Box."
        ),
        props=(
            "columns([{key,label,kind?(text|image|date|url|number)}]*); "
            "dataRef(str*); sort?({key,dir}); limit?(int). "
            "kind=image for foto URL fields (or inferred from .jpg/.png)."
        ),
        data=(
            "Columns should reference scalar row keys. Nested collections are not "
            "expanded as records; transform them first or show only an intentional "
            "summary. Apply sort and limit explicitly when order or count matters."
        ),
    ),
    WidgetDef(
        type="ComparisonTable",
        role="leaf",
        purpose=(
            "Side-by-side comparison of alternatives with typed columns and an "
            "optional best-value highlight."
        ),
        when_to_use=(
            "Use when rows are alternatives the user may evaluate across the same "
            "criteria. Mark the identifying column as primary and use highlight "
            "only when a lower-is-better or higher-is-better rule is valid. Set "
            "column kinds explicitly; percent expects values already in display units."
        ),
        when_not=(
            "Time evolution → Chart. Records not being weighed as alternatives "
            "→ List. People → PersonCard. Scalar snapshot → Metric/MetricRow."
        ),
        props=(
            "columns([{key,label,kind?(text|number|percent|money|date|url),"
            "primary?(bool)}]* min 2 max 8); dataRef(str*); "
            "highlight?({key,direction:min|max}); sort?({key,dir}); limit?(int)"
        ),
        data=(
            "Rows must be flat alternatives with one scalar value per criterion. "
            "Column keys and highlight.key must exist in the rows."
        ),
    ),
    WidgetDef(
        type="Stack",
        role="container",
        purpose="Vertical column layout for grouping 2–4 leaf widgets.",
        when_to_use=(
            "Use to group related widgets in a deliberate top-to-bottom reading "
            "order, especially a primary visual followed by context or a finding."
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
            "Use when two or three peer widgets benefit from direct side-by-side "
            "comparison and remain readable at equal hierarchy."
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
            "Exceptional authored HTML/SVG composition for structures that fixed "
            "widgets cannot express honestly: semantic tables, diagrams, flows, "
            "hierarchies, visual matrices, and bespoke relationships. "
            "It must look native to the existing site, not like an embedded microsite."
        ),
        when_to_use=(
            "Use only when no standard semantic widget can preserve the essential "
            "meaning, or when the user explicitly requests a bespoke relationship "
            "or visual form, and that functional benefit clearly outweighs losing "
            "data binding, normalization, interaction, accessibility, and tested "
            "responsive behavior. When uncertain, use the standard widget. Custom "
            "styling alone never justifies Box. Because Box visibly identifies "
            "itself as AI-generated, it must provide an immediately legible visual "
            "or structural gain—not a generic card, heading plus paragraph, or "
            "single prose block. "
            "It may be ordinary nested HTML, a semantic table, or SVG; custom does "
            "not imply chart-like. Honor a user-named form. "
            "Follow the site's editorial bulletin system: restrained surfaces, "
            "font-display for headings or names, font-sans for body copy, "
            "text-muted-foreground for secondary lines, text-accent sparingly, "
            "border-rule separators, and the existing spacing scale. Reuse only "
            "allowlisted theme tokens; never introduce a competing palette or "
            "unrelated visual language. Build one "
            "coherent composition with clear reading order; use semantic hierarchy, "
            "whitespace, alignment, and emphasis deliberately. A restrained table "
            "or nested document structure is valid when it best serves the content. "
            "For positioned diagrams, use one responsive SVG viewBox for BOTH "
            "marks and their text labels. Do not overlay absolute HTML labels: "
            "arbitrary position classes are not in the safelist and will be "
            "stripped. Preflight bounds, clipping and label collisions before "
            "returning; reposition with SVG leader lines when needed. "
            "Optional suggests=PascalCaseName for a future named widget."
        ),
        when_not=(
            "A standard semantic or data widget already expresses the relationship "
            "honestly → use that widget. "
            "Spot figures → Metric/MetricRow. Punchy finding → Callout. "
            "Source caveat or narrative extract → Text. "
            "Plain prose, styled text, or a generic card → Text/Callout. "
            "ANY single-person profile or people roster → PersonCard; never rebuild "
            "name, role, party, province, vote, photo, bio, or contacts in Box. "
            "NEVER put dataRef on Box — author copy from the analyst note."
        ),
        props=(
            "className?(safelist utilities); suggests?(PascalCase). "
            "Every host child requires id,type,props,children; ALL content/style/"
            "geometry belongs inside props, never directly on the node. "
            "Host child props: className?, text?, plus SVG attrs "
            "(viewBox, d, x/y, x1/y1/x2/y2, cx/cy/r, width/height, stroke, "
            "fill, markerEnd, strokeWidth, textAnchor, fontSize/fontWeight, "
            "preserveAspectRatio, and HTTPS href for image). "
            "Hosts: div,section,header,p,span,h2,h3,ul,ol,li,dl,dt,dd,strong,em, "
            "table,thead,tbody,tr,th,td, "
            "svg,g,path,line,polyline,polygon,circle,rect,text,image,defs,marker."
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
