"""Guardrails for respond/compose prompts: next-move contract + catalog grounding."""

from __future__ import annotations

from agent.catalog import catalog
from agent.graph import (
    _CAPABILITIES,
    _CAPABILITIES_COMPOSE,
    _COMPOSE_SYSTEM,
    _EARLIER_DATASET_CAP,
    _RESPOND_SYSTEM,
    _build_compose_system,
    _compact_datasets,
    _ensure_brief_actions,
    _message_text,
    _next_to_actions_block,
    _sanitize_user_facing,
    _system_message,
)
from agent.ui.catalog import as_prompt_text as widget_catalog_text



def test_historical_day_recipe_fetches_person_and_weather() -> None:
    caps = _CAPABILITIES.casefold()
    respond = _RESPOND_SYSTEM.casefold()
    compose = _COMPOSE_SYSTEM.casefold()
    assert "persona" in caps
    assert "/v1/clima/historico" in _CAPABILITIES
    assert "/v1/presidentes" in _RESPOND_SYSTEM
    assert "do not leave clima" in respond or "not [[next]]" in caps
    assert "weatherunit" in compose
    assert "never bind personcard to historico/dia" in compose
    catalog_text = catalog.as_prompt_text("data")
    assert "persona" in catalog_text
    widgets = widget_catalog_text().casefold()
    assert "historico/dia" in widgets
    assert "never historico/dia" in widgets or "not personcard" in widgets


def test_capability_map_names_real_families_and_bans_out_of_catalog() -> None:
    text = _CAPABILITIES.casefold()
    for needle in (
        "blue",
        "riesgo",
        "confianza",
        "actas",
        "presidentes",
        "uva",
        "reservas",
        "emae",
        "desempleo",
        "open-meteo",
    ):
        assert needle in text
    # Still out of catalog — listed under NEVER propose.
    for banned in ("merval", "ticket"):
        assert banned in text
    # Activity is EMAE now; bare PBI remains out of the offer list.
    never = text.split("out of catalog", 1)[-1]
    assert "merval" in never
    assert "pbi" not in never or "emae" in text


def test_respond_prompt_requires_next_block() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "[[next]]" in text
    assert "CRUCE" in text
    assert "en barras" in text.casefold() or "sumando el oficial" in text.casefold()
    assert "blue+riesgo" in text or "blue + riesgo" in text.casefold()
    assert "/v1/cotizaciones/dolares" in text  # full catalog still injected


def test_respond_prompt_requires_inline_boton_not_paths() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "[boton]" in text
    assert "[/boton]" in text
    compose = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "[boton]" in compose


def test_sanitize_user_facing_strips_catalog_paths() -> None:
    raw = (
        "Si querés una entidad, traigo las tasas "
        "(/v1/finanzas/rendimientos/{entidad}) o el detalle."
    )
    out = _sanitize_user_facing(raw)
    assert "/v1/" not in out
    assert "rendimientos" not in out
    assert "Si querés una entidad, traigo las tasas" in out


def test_sanitize_user_facing_strips_derived_paths() -> None:
    raw = (
        "Puse en pantalla dos visualizaciones: (1) barras con el máximo "
        'del dólar blue por mandato (usé derived/period_levels, "máximo") '
        "y (2) la superposición completa de la serie durante esos mandatos "
        "(derived/period_overlay)."
    )
    out = _sanitize_user_facing(raw)
    assert "derived/" not in out
    assert "period_levels" not in out
    assert "period_overlay" not in out
    assert "máximo del dólar blue" in out
    assert "superposición" in out


def test_compose_brief_bans_derived_paths() -> None:
    text = _COMPOSE_SYSTEM
    assert "puse en pantalla" in text
    never = text.split("NEVER mention", 1)[-1][:600]
    assert "derived" in never


def test_compose_prompt_grounds_brief_in_capabilities() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "[[next]]\n- Cruzar el pico con actas del Senado\n[[/next]]",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "What we can actually do" in text
    assert "Cruzar el pico con actas del Senado" in text
    assert "settings menu" in text.casefold() or "en barras" in text.casefold()
    assert "emae" in text.casefold() or "reservas" in text.casefold()
    assert "merval" in text.casefold()


def test_compose_catalog_includes_box_last_resort() -> None:
    catalog = widget_catalog_text().casefold()
    assert "### box" in catalog
    assert "svg" in catalog
    assert "visual form" in catalog or "structure" in catalog
    assert "dataref" in catalog  # banned on Box (when_not / props)
    assert "user-named form" in catalog or "beats the default" in catalog
    compose = _COMPOSE_SYSTEM.casefold()
    assert "box" in compose
    assert "svg" in compose
    assert "suggests" in compose
    assert "box craft" in compose or "cold-bulletin" in compose
    assert "not a mandatory pigeonhole" in compose or "named form" in compose
    assert "flechas" not in compose  # principle, not keyword triggers


def test_respond_routes_structured_comparison_to_compose() -> None:
    text = _RESPOND_SYSTEM.casefold()
    assert "custom visual" in text or "box" in text
    assert "box" in text
    assert "markdown table" in text
    assert "named form" in text or "chart kind" in text
    assert "flechas" not in text


def test_prompt_templates_format_without_leftover_placeholders() -> None:
    respond = _RESPOND_SYSTEM.format(
        domain="data",
        catalog="CAT",
        datasets_index="IDX",
        capabilities="CAP",
        scope="SCOPE",
    )
    compose = _COMPOSE_SYSTEM.format(
        widget_catalog="W",
        datasets_index="IDX",
        respond_note="NOTE",
        fetch_outcomes="OUT",
        canvas_snapshot="CANVAS",
        capabilities="CAP",
        scope="SCOPE",
    )
    assert "{catalog}" not in respond
    assert "{capabilities}" not in respond
    assert "{capabilities}" not in compose
    assert "{scope}" not in respond
    assert "{scope}" not in compose
    assert "CAP" in respond and "CAP" in compose
    assert "SCOPE" in respond and "SCOPE" in compose


def test_scope_guardrail_limits_answers_to_catalog_sources() -> None:
    from agent.graph import _SCOPE

    scope = _SCOPE.casefold()
    assert "only with information grounded" in scope or "available sources" in scope
    assert "general knowledge" in scope
    assert "prompt injection" in scope or "ignore previous instructions" in scope
    assert "system prompts" in scope or "internal implementation" in scope
    respond = _system_message("data", {}).content.casefold()
    compose = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    ).casefold()
    assert "## scope" in respond
    assert "## scope" in compose
    assert "secrecy" in respond
    assert "secrecy" in compose
    assert "out of scope" in respond or "pokémon" in scope or "pokemon" in scope
    assert "tree" in compose and "null" in compose


def test_next_to_actions_block_for_clickable_chat() -> None:
    note = (
        "Nada que dibujar.\n"
        "[[next]]\n"
        "- Superponer riesgo país\n"
        "- Cortar por mandato\n"
        "[[/next]]"
    )
    out = _next_to_actions_block(note)
    assert "[[next]]" not in out
    assert "[[actions]]" in out
    assert "[[/actions]]" in out
    assert "Superponer riesgo país" in out


def test_ensure_brief_actions_lifts_from_respond_note() -> None:
    brief = "En pantalla: blue de la semana previa."
    note = "[[next]]\n- Superponer riesgo país\n- Traer el acta\n[[/next]]"
    out = _ensure_brief_actions(brief, note)
    assert out.startswith("En pantalla:")
    assert "[[actions]]" in out
    assert "Superponer riesgo país" in out
    assert "Traer el acta" in out


def test_ensure_brief_actions_skips_when_inline_boton_exists() -> None:
    brief = (
        "En pantalla verás la serie.\n"
        "[boton]Mostrá la diferencia porcentual[/boton]"
    )
    note = "[[next]]\n- Mostrá la diferencia porcentual\n[[/next]]"
    out = _ensure_brief_actions(brief, note)
    assert "[[actions]]" not in out
    assert "[boton]Mostrá la diferencia porcentual[/boton]" in out


def test_compose_prompt_requires_one_chart_for_shared_axes() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "Same axes" in text or "same X" in text
    assert "derived/series_overlay" in text
    assert "Stack of N Charts" in text
    assert "params.x" in text
    assert "derived/fx_spread" in text


def test_compose_prompt_requires_two_layers_for_cruce() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "two layers" in text.casefold() or "Cruce = two layers" in text
    assert "anti Chart-only" in text or "NEVER ship only Charts" in text
    assert "de ese día" in text.casefold()
    assert "VoteBreakdown" in text
    catalog = widget_catalog_text()
    assert "quiénes + blue" in catalog or "political layer" in catalog.casefold()
    assert "distribución del voto" in catalog.casefold()
    assert "de ese día" in catalog.casefold()


def test_respond_prompt_vote_composition_fetches_votos_and_same_day_spots() -> None:
    msg = _system_message("data", {})
    text = msg.content.casefold()
    assert "distribución del voto" in text
    assert "votos" in text
    assert "[[values]]" in msg.content
    assert "de ese día" in text


def test_compose_prompt_day_snapshot_uses_kv_list_not_callout() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "key-value" in text.casefold() or "Key-value" in text
    assert "valores del día" in text.casefold() or "Day snapshot" in text
    catalog = widget_catalog_text()
    assert "derived/values" in catalog
    assert "Callout" in catalog
    assert "valores del día" in catalog.casefold() or "day snapshot" in catalog.casefold()


def test_respond_prompt_mentions_spread_series_fetch() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "derived/fx_spread" in text
    assert "serie del spread" in text.casefold() or "Spread evolution" in text


def test_respond_prompt_peak_day_fetches_actas_by_date() -> None:
    msg = _system_message("data", {})
    text = msg.content.casefold()
    assert "había sesión" in text or "qué se votó ese día" in text
    assert "annotatedtimeline" in text
    compose = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "no hubo sesión" in compose.casefold()
    catalog = widget_catalog_text().casefold()
    assert "peak" in catalog or "pico" in catalog


def test_respond_prompt_named_law_forces_search() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "hay ley" in text.casefold() or "named" in text.casefold()
    assert "search_actas" in text
    assert "previous canvas" in text.casefold() or "canvas still shows" in text.casefold()


def test_compose_prompt_bans_recycled_brief() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "THIS user message" in text or "only ask that matters" in text
    assert "Recycled briefs" in text or "previous topic" in text.casefold()
    assert "HARD bind" in text or "MUST bind" in text
    assert "datos concretos" in text
    assert "qué voy a mostrar" in text.casefold()


def test_compose_hides_old_canvas_when_this_turn_has_hits() -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    from agent.graph import _dataset_id

    path, params = "/search/actas", {"query": "micaela", "chamber": None}
    ds_id = _dataset_id(path, params)
    text = _build_compose_system(
        {
            "messages": [
                HumanMessage(content="que sabes de la ley micaela"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "c1",
                            "name": "search_actas",
                            "args": {"query": "micaela"},
                        }
                    ],
                ),
            ],
            "datasets": {
                ds_id: {
                    "id": ds_id,
                    "path": path,
                    "params": params,
                    "N": 3,
                    "keys": ["id", "titulo", "fecha"],
                    "rows": [],
                },
                "ds_olduva": {
                    "id": "ds_olduva",
                    "path": "/v1/finanzas/indices/uva",
                    "params": {},
                    "N": 100,
                    "keys": ["fecha", "valor"],
                    "rows": [],
                },
            },
            "respond_note": "Encontré actas de Micaela.",
            "ui_tree": {
                "id": "uva_stack",
                "type": "Stack",
                "children": [
                    {
                        "id": "uva_chart",
                        "type": "Chart",
                        "props": {"dataRef": "ds_olduva"},
                    }
                ],
            },
            "ui_tree_unbound": {
                "id": "uva_stack",
                "type": "Stack",
                "children": [
                    {
                        "id": "uva_chart",
                        "type": "Chart",
                        "props": {"dataRef": "ds_olduva"},
                    }
                ],
            },
        }
    )
    assert "obsolete for this turn" in text
    assert "uva_stack" not in text
    assert "MUST bind at least one" in text
    assert "hidden — this turn has new hits" in text
    assert "ds_olduva" not in text
    assert ds_id in text


def test_compose_stale_tree_guardrail() -> None:
    from agent.graph import (
        _brief_from_respond_note,
        _compose_tree_is_stale,
        _fallback_list_tree,
        _list_props_for_dataset,
        _tree_data_refs,
        _tree_has_inline_metrics,
    )

    tree = {
        "id": "uva_inflacion_stack",
        "type": "Stack",
        "children": [
            {
                "id": "uva_inflacion_chart",
                "type": "Chart",
                "props": {"dataRef": "ds_be7348b3"},
            }
        ],
    }
    assert _tree_data_refs(tree) == {"ds_be7348b3"}
    assert _compose_tree_is_stale(tree, {"ds_micaela"})
    assert not _compose_tree_is_stale(tree, {"ds_be7348b3"})
    assert _compose_tree_is_stale(
        {"id": "x", "type": "Callout", "props": {"content": "hola"}},
        {"ds_micaela"},
    )

    # Day-snapshot Metrics must survive even when the Acta dataRef is not a
    # this-turn hit (or the tree only has inline values + Text).
    day_tree = {
        "id": "stack_main",
        "type": "Stack",
        "children": [
            {
                "id": "metric_blue",
                "type": "Metric",
                "props": {"label": "Blue (venta)", "value": "1425", "unit": "ARS"},
            },
            {
                "id": "text_riesgo",
                "type": "Text",
                "props": {"content": "Sin riesgo país ese día."},
            },
            {
                "id": "acta_ba",
                "type": "Acta",
                "props": {"dataRef": "ds_old_acta"},
            },
        ],
    }
    assert _tree_has_inline_metrics(day_tree)
    assert not _compose_tree_is_stale(day_tree, {"ds_blue_series", "ds_riesgo"})
    assert not _compose_tree_is_stale(
        {
            "id": "metric_only",
            "type": "Metric",
            "props": {"label": "Blue", "value": 1425, "unit": "ARS"},
        },
        {"ds_blue_series"},
    )

    # Authored Box layouts must survive like Metrics — otherwise a previous
    # bound canvas + new conceptual comparison gets discarded as unbound.
    from agent.graph import _tree_has_authored_box, _tree_is_authored_canvas

    box_tree = {
        "id": "blue_vs_oficial",
        "type": "Box",
        "title": "Blue vs oficial",
        "props": {"className": "flex flex-col gap-4"},
        "children": [
            {
                "id": "cols",
                "type": "div",
                "props": {"className": "grid grid-cols-2 gap-6"},
                "children": [
                    {
                        "id": "oficial",
                        "type": "p",
                        "props": {
                            "className": "text-sm text-foreground",
                            "text": "Mercado formal regulado.",
                        },
                    },
                    {
                        "id": "blue",
                        "type": "p",
                        "props": {
                            "className": "text-sm text-foreground",
                            "content": "Mercado informal / paralelo.",
                        },
                    },
                ],
            }
        ],
    }
    assert _tree_has_authored_box(box_tree)
    assert _tree_is_authored_canvas(box_tree)
    assert not _compose_tree_is_stale(box_tree, {"ds_blue_series"})

    fb = _fallback_list_tree(
        {
            "id": "ds_micaela",
            "keys": ["titulo", "fecha", "resultado", "camara"],
        }
    )
    assert fb["children"][0]["props"]["dataRef"] == "ds_micaela"
    assert {c["key"] for c in fb["children"][0]["props"]["columns"]} >= {
        "titulo",
        "fecha",
    }

    fx_props = _list_props_for_dataset(
        {"id": "ds_blue", "keys": ["fecha", "compra", "venta"]}
    )
    assert {c["key"] for c in fx_props["columns"]} >= {"fecha", "venta"}

    brief = _brief_from_respond_note(
        "Encontré actas.\n[[next]]\n- Ver votos\n[[/next]]\n[[route]] compose [[/route]]"
    )
    assert "Encontré actas" in brief
    assert "[[route]]" not in brief
    assert "[[actions]]" in brief
    assert "Ver votos" in brief


def test_brief_from_respond_note_drops_analyst_fact_dump() -> None:
    from agent.graph import _brief_from_respond_note, _strip_fact_dump_from_brief

    note = (
        "Analista — datos concretos obtenidos\n"
        "- Día: 2020-05-22 — \"Oferta de canje de deuda\"\n"
        "- Ventana usada: 2020-05-15 → 2020-05-29\n"
        "Qué voy a mostrar en el canvas\n"
        "- A la izquierda: el extracto\n"
        "[[next]]\n"
        "- Compará el blue con MEP y CCL\n"
        "- Mostrá la tabla diaria\n"
        "[[/next]]\n"
        "[[route]] compose [[/route]]"
    )
    brief = _brief_from_respond_note(note)
    assert "Analista" not in brief
    assert "Ventana usada" not in brief
    assert "A la izquierda" not in brief
    assert "Oferta de canje de deuda (2020-05-22)" in brief
    assert "Compará el blue con MEP y CCL" in brief
    assert "[[actions]]" in brief

    dumped = (
        "Analista — datos concretos obtenidos\n"
        "- Día: 2020-05-22 — oferta\n"
        "- A la derecha: gráfico diario\n"
        "[[actions]]\n"
        "Compará el blue con MEP y CCL\n"
        "[[/actions]]"
    )
    cleaned = _strip_fact_dump_from_brief(dumped)
    assert "Analista" not in cleaned
    assert "A la derecha" not in cleaned
    assert "Compará el blue" in cleaned


def test_fallback_fx_series_is_line_chart() -> None:
    from agent.graph import (
        _coerce_series_list_widgets,
        _fallback_tree_for_hits,
    )

    rows = [
        {"fecha": f"2020-05-{day:02d}", "compra": 120 + day, "venta": 128 + day}
        for day in range(15, 30)
    ]
    ds = {
        "id": "ds_blue",
        "path": "/v1/cotizaciones/dolares/blue",
        "params": {"casa": "blue"},
        "keys": ["fecha", "compra", "venta"],
        "N": len(rows),
        "rows": rows,
    }
    tree = _fallback_tree_for_hits({"ds_blue": ds}, {"ds_blue"})
    assert tree is not None
    chart = tree["children"][0]
    assert chart["type"] == "Chart"
    assert chart["props"]["kind"] == "line"
    assert chart["props"]["xKey"] == "fecha"
    assert any(s["key"] == "venta" for s in chart["props"]["series"])

    listed = {
        "id": "root",
        "type": "Stack",
        "children": [
            {
                "id": "turn_list",
                "type": "List",
                "title": "Resultados de esta consulta",
                "props": {
                    "dataRef": "ds_blue",
                    "columns": [
                        {"key": "fecha", "label": "Fecha"},
                        {"key": "venta", "label": "Blue"},
                    ],
                },
            }
        ],
    }
    coerced = _coerce_series_list_widgets(listed, {"ds_blue": ds})
    assert coerced["children"][0]["type"] == "Chart"
    assert coerced["children"][0]["props"]["kind"] == "line"


def test_fallback_keeps_acta_hits_as_list() -> None:
    from agent.graph import _fallback_tree_for_hits

    ds = {
        "id": "ds_micaela",
        "path": "/v1/senado/actas",
        "keys": ["titulo", "fecha", "resultado", "camara"],
        "N": 3,
        "rows": [
            {
                "titulo": "Ley Micaela",
                "fecha": "2019-01-01",
                "resultado": "AFIRMATIVA",
                "camara": "Senado",
            }
        ],
    }
    tree = _fallback_tree_for_hits({"ds_micaela": ds}, {"ds_micaela"})
    assert tree is not None
    assert tree["children"][0]["type"] == "List"
    assert tree["children"][0]["props"]["dataRef"] == "ds_micaela"


def test_fallback_peak_series_and_actas_is_chart_plus_list() -> None:
    from agent.graph import _fallback_tree_for_hits

    riesgo_rows = [
        {"fecha": f"2026-01-{day:02d}", "valor": 800 + day}
        for day in range(1, 10)
    ]
    riesgo_rows[4]["valor"] = 2400  # 2026-01-05
    riesgo = {
        "id": "ds_riesgo",
        "path": "/v1/finanzas/indices/riesgo-pais",
        "keys": ["fecha", "valor"],
        "N": len(riesgo_rows),
        "rows": riesgo_rows,
    }
    actas = {
        "id": "ds_actas",
        "path": "/v1/senado/actas",
        "keys": ["titulo", "fecha", "resultado"],
        "N": 1,
        "rows": [
            {
                "titulo": "Modernización laboral",
                "fecha": "2026-01-05",
                "resultado": "AFIRMATIVA",
            }
        ],
    }
    tree = _fallback_tree_for_hits(
        {"ds_riesgo": riesgo, "ds_actas": actas},
        {"ds_riesgo", "ds_actas"},
    )
    assert tree is not None
    types = [c["type"] for c in tree["children"]]
    assert "Chart" in types
    assert "List" in types
    chart = next(c for c in tree["children"] if c["type"] == "Chart")
    assert chart["props"]["dataRef"] == "ds_riesgo"
    actas_list = next(c for c in tree["children"] if c["type"] == "List")
    assert actas_list["props"]["dataRef"] == "ds_actas"


def test_fallback_peak_series_without_session_adds_callout() -> None:
    from agent.graph import _fallback_tree_for_hits

    riesgo_rows = [
        {"fecha": f"2026-03-{day:02d}", "valor": 500 + day}
        for day in range(1, 8)
    ]
    riesgo = {
        "id": "ds_riesgo",
        "path": "/v1/finanzas/indices/riesgo-pais",
        "keys": ["fecha", "valor"],
        "N": len(riesgo_rows),
        "rows": riesgo_rows,
    }
    miss = {
        "id": "ds_actas",
        "path": "/v1/senado/actas",
        "keys": ["titulo", "fecha", "resultado"],
        "N": 0,
        "rows": [],
    }
    tree = _fallback_tree_for_hits(
        {"ds_riesgo": riesgo, "ds_actas": miss},
        {"ds_riesgo"},
        {"ds_riesgo", "ds_actas"},
    )
    assert tree is not None
    types = [c["type"] for c in tree["children"]]
    assert "Chart" in types
    assert "Callout" in types
    callout = next(c for c in tree["children"] if c["type"] == "Callout")
    assert "Senado" in callout["props"]["content"]


def test_brief_from_respond_note_keeps_peak_facts() -> None:
    from agent.graph import _brief_from_respond_note

    note = (
        "Riesgo país máximo: 2026-01-15 con 2143 puntos.\n"
        "Ese día el Senado votó la modernización laboral (AFIRMATIVA).\n"
        "[[next]]\n"
        "- Mostrá el roll call de esa acta\n"
        "[[/next]]\n"
        "[[route]] compose [[/route]]"
    )
    brief = _brief_from_respond_note(note)
    assert "2143" in brief or "Senado" in brief
    assert "[[actions]]" in brief
    assert "roll call" in brief.casefold() or "Mostrá el roll" in brief


def test_compose_null_tree_with_hits_needs_fallback() -> None:
    from agent.graph import _compose_tree_needs_fallback, _should_compose

    hits = {"ds_x"}
    datasets = {"ds_x": {"id": "ds_x", "N": 3, "rows": [{}]}}
    assert _compose_tree_needs_fallback(None, hits, datasets)
    assert not _compose_tree_needs_fallback(None, set(), datasets)
    good = {"id": "c", "type": "Chart", "props": {"dataRef": "ds_x"}}
    assert not _compose_tree_needs_fallback(good, hits, datasets)

    leak = (
        "Puse en pantalla dos visualizaciones "
        "(derived/period_overlay). [[route]] chat [[/route]]"
    )
    assert _should_compose(leak, fetched_hits=False, route="chat")
    # No tools this turn → compose owns the reply (even short / chat-marked).
    assert _should_compose(
        "hola", fetched_hits=False, route=None, fetched_this_turn=False
    )
    assert _should_compose(
        "listo", fetched_hits=False, route="chat", fetched_this_turn=False
    )
    # Tools ran, every call missed → stay in chat (no empty widgets).
    assert (
        _should_compose(
            "No encontré esa ley.",
            fetched_hits=False,
            route="chat",
            fetched_this_turn=True,
        )
        is False
    )
    # A deepen may fetch the existing collection yet find no dedicated detail.
    # Explicit chat keeps the current canvas instead of redrawing those rows.
    assert (
        _should_compose(
            "No hay una ficha ni estadísticas adicionales para este feriado.",
            fetched_hits=True,
            route="chat",
            fetched_this_turn=True,
        )
        is False
    )

    explainer = (
        "El dólar blue es el tipo de cambio que surge del mercado informal "
        "y suele usarse como referencia para operaciones fuera del circuito "
        "bancario; el dólar oficial es el tipo de cambio regulado por el "
        "mercado formal, aplicado en bancos y operaciones autorizadas. "
        "La brecha entre ambos refleja restricciones, impuestos, demanda "
        "y expectativas. [[route]] chat [[/route]]"
    )
    assert _should_compose(
        explainer, fetched_hits=False, route="chat", fetched_this_turn=False
    )


def test_coerce_acta_search_hits_to_list() -> None:
    from agent.graph import _coerce_acta_widgets, _dataset_looks_like_roll_call

    search_ds = {
        "id": "ds_search",
        "keys": ["id", "titulo", "fecha", "resultado", "camara"],
        "N": 2,
        "rows": [],
    }
    votos_ds = {
        "id": "ds_votos",
        "keys": ["nombre", "voto", "titulo", "fecha"],
        "N": 10,
        "rows": [],
    }
    summarized_ds = {
        "id": "ds_list",
        "keys": ["id", "titulo", "fecha", "resultado", "votos"],
        "N": 3,
        "sample": [
            {
                "id": 1,
                "titulo": "Ley X",
                "fecha": "2026-01-01",
                "resultado": "AFIRMATIVA",
                "votos": "afirmativo: 40, negativo: 10",
            }
        ],
        "rows": [],
    }
    assert not _dataset_looks_like_roll_call(search_ds)
    assert _dataset_looks_like_roll_call(votos_ds)
    assert not _dataset_looks_like_roll_call(summarized_ds)

    nested_ds = {
        "id": "ds_detail",
        "keys": ["id", "titulo", "fecha", "resultado", "votos"],
        "N": 1,
        "sample": [
            {
                "id": 2623,
                "titulo": "Modernización Laboral",
                "fecha": "2026-02-12",
                "resultado": "AFIRMATIVA",
                "votos": [
                    {"nombre": "A", "voto": "afirmativo"},
                    {"nombre": "B", "voto": "negativo"},
                ],
            }
        ],
        "rows": [],
    }
    assert _dataset_looks_like_roll_call(nested_ds)

    tree = {
        "id": "root",
        "type": "Stack",
        "children": [
            {
                "id": "bad_acta",
                "type": "Acta",
                "title": "Hits",
                "props": {"dataRef": "ds_search"},
            },
            {
                "id": "ok_acta",
                "type": "Acta",
                "title": "Roll call",
                "props": {"dataRef": "ds_votos"},
            },
            {
                "id": "summarized_acta",
                "type": "Acta",
                "title": "Summarized",
                "props": {"dataRef": "ds_list"},
            },
        ],
    }
    out = _coerce_acta_widgets(
        tree,
        {
            "ds_search": search_ds,
            "ds_votos": votos_ds,
            "ds_list": summarized_ds,
        },
    )
    assert out["children"][0]["type"] == "List"
    assert out["children"][0]["props"]["dataRef"] == "ds_search"
    assert out["children"][0]["props"]["columns"][0]["key"] == "titulo"
    assert out["children"][1]["type"] == "Acta"
    assert out["children"][2]["type"] == "List"


def test_bind_list_expands_nested_filmografia_column() -> None:
    """A filmografia column on the person row used to render as \"20\"."""
    from agent.graph import _bind_node

    films = [
        {"titulo": "Nueve reinas", "fecha": "2000-08-31", "foto": "https://x/a.jpg", "valor": 7.9},
        {"titulo": "El secreto de sus ojos", "fecha": "2009-08-13", "foto": "https://x/b.jpg", "valor": 8.2},
    ]
    datasets = {
        "ds_persona": {
            "id": "ds_persona",
            "keys": ["nombre", "foto", "bio", "filmografia"],
            "N": 1,
            "rows": [
                {
                    "nombre": "Ricardo Darín",
                    "foto": "https://x/darin.jpg",
                    "bio": "Actor",
                    "filmografia": films,
                }
            ],
        }
    }
    tree = {
        "id": "list",
        "type": "List",
        "title": "Filmografía",
        "props": {
            "dataRef": "ds_persona",
            "columns": [{"key": "filmografia", "label": "Filmografía"}],
        },
    }
    out = _bind_node(tree, datasets)
    rows = out["props"]["data"]
    assert len(rows) == 2
    assert rows[0]["titulo"] == "Nueve reinas"
    col_keys = [c["key"] for c in out["props"]["columns"]]
    assert "filmografia" not in col_keys
    assert "titulo" in col_keys


def test_bind_list_expands_filmografia_when_columns_are_movie_fields() -> None:
    from agent.graph import _bind_node

    datasets = {
        "ds_persona": {
            "id": "ds_persona",
            "N": 1,
            "rows": [
                {
                    "nombre": "Ricardo Darín",
                    "foto": "https://x/darin.jpg",
                    "filmografia": [
                        {"titulo": "Nueve reinas", "foto": "https://x/a.jpg", "valor": 7.9},
                    ],
                }
            ],
        }
    }
    tree = {
        "id": "list",
        "type": "List",
        "props": {
            "dataRef": "ds_persona",
            "columns": [
                {"key": "foto", "label": "Foto"},
                {"key": "titulo", "label": "Título"},
                {"key": "valor", "label": "Rating"},
            ],
        },
    }
    out = _bind_node(tree, datasets)
    rows = out["props"]["data"]
    assert len(rows) == 1
    assert rows[0]["titulo"] == "Nueve reinas"


def test_bind_acta_expands_nested_votos() -> None:
    from agent.graph import _bind_node

    datasets = {
        "ds_detail": {
            "id": "ds_detail",
            "keys": ["id", "titulo", "fecha", "resultado", "votos"],
            "N": 1,
            "rows": [
                {
                    "id": 2623,
                    "titulo": "Modernización Laboral",
                    "fecha": "2026-02-12",
                    "resultado": "AFIRMATIVA",
                    "votos": [
                        {"nombre": "Ana", "voto": "afirmativo", "bloque": "A"},
                        {"nombre": "Bruno", "voto": "negativo", "bloque": "B"},
                    ],
                }
            ],
        }
    }
    tree = {
        "id": "acta",
        "type": "Acta",
        "title": "Acta",
        "props": {"dataRef": "ds_detail"},
    }
    out = _bind_node(tree, datasets)
    rows = out["props"]["data"]
    assert len(rows) == 2
    assert rows[0]["voter"] == "Ana"
    assert rows[0]["vote"] == "afirmativo"
    assert rows[0]["title"] == "Modernización Laboral"
    assert rows[0]["date"] == "2026-02-12"
    assert rows[1]["voter"] == "Bruno"
    assert "votos" not in rows[0]


def test_bind_chart_pivots_votes_by_bloque() -> None:
    from agent.graph import _bind_node

    datasets = {
        "ds_votos": {
            "id": "ds_votos",
            "keys": ["nombre", "voto", "bloque"],
            "N": 6,
            "rows": [
                {"nombre": "A", "voto": "afirmativo", "bloque": "UCR"},
                {"nombre": "B", "voto": "afirmativo", "bloque": "UCR"},
                {"nombre": "C", "voto": "negativo", "bloque": "UCR"},
                {"nombre": "D", "voto": "negativo", "bloque": "LLA"},
                {"nombre": "E", "voto": "negativo", "bloque": "LLA"},
                {"nombre": "F", "voto": "ausente", "bloque": "LLA"},
            ],
        }
    }
    tree = {
        "id": "vote_by_block_chart",
        "type": "Chart",
        "title": "Votos por bloque",
        "props": {
            "kind": "bar",
            "xKey": "bloque",
            "dataRef": "ds_votos",
            "series": [
                {"key": "afirmativo", "label": "Afirmativo"},
                {"key": "negativo", "label": "Negativo"},
                {"key": "abstencion", "label": "Abstención"},
                {"key": "ausente", "label": "Ausente"},
            ],
            "sort": {"key": "negativo", "dir": "desc"},
        },
    }
    out = _bind_node(tree, datasets)
    rows = out["props"]["data"]
    assert [r["bloque"] for r in rows] == ["LLA", "UCR"]
    by_block = {r["bloque"]: r for r in rows}
    assert by_block["UCR"]["afirmativo"] == 2
    assert by_block["UCR"]["negativo"] == 1
    assert by_block["UCR"]["ausente"] == 0
    assert by_block["LLA"]["negativo"] == 2
    assert by_block["LLA"]["ausente"] == 1
    assert by_block["LLA"]["afirmativo"] == 0
    assert "dataRef" not in out["props"]
    assert "sort" not in out["props"]


def test_bind_chart_leaves_numeric_series_alone() -> None:
    from agent.graph import _bind_node

    datasets = {
        "ds_fx": {
            "id": "ds_fx",
            "keys": ["fecha", "venta"],
            "N": 2,
            "rows": [
                {"fecha": "2026-01-01", "venta": 1400},
                {"fecha": "2026-01-02", "venta": 1410},
            ],
        }
    }
    tree = {
        "id": "blue",
        "type": "Chart",
        "props": {
            "kind": "line",
            "xKey": "fecha",
            "dataRef": "ds_fx",
            "series": [{"key": "venta", "label": "Blue"}],
        },
    }
    out = _bind_node(tree, datasets)
    assert out["props"]["data"] == datasets["ds_fx"]["rows"]


def test_chart_catalog_mentions_vote_by_bloque() -> None:
    text = widget_catalog_text()
    assert "xKey=bloque" in text
    assert "afirmativo/negativo" in text


def test_compose_keeps_previous_tree_when_new_tree_binds_empty() -> None:
    from agent.graph import _tree_would_bind_rows

    empty_tree = {
        "id": "root",
        "type": "Stack",
        "children": [
            {
                "id": "ghost",
                "type": "PersonCard",
                "props": {"dataRef": "ds_missing"},
            }
        ],
    }
    good_tree = {
        "id": "root",
        "type": "Stack",
        "children": [
            {
                "id": "roster",
                "type": "PersonCard",
                "props": {"dataRef": "ds_votos"},
            }
        ],
    }
    datasets = {
        "ds_votos": {
            "id": "ds_votos",
            "N": 10,
            "rows": [{"nombre": "A", "voto": "afirmativo"}],
            "keys": ["nombre", "voto"],
        }
    }
    assert not _tree_would_bind_rows(empty_tree, datasets)
    assert _tree_would_bind_rows(good_tree, datasets)


def test_respond_prompt_handles_canvas_selection() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "Profundizá" in text or "profundizar" in text.casefold()
    assert "Seleccioné en el canvas:" in text  # legacy still documented
    assert "Canvas selection" in text or "Canvas deepen" in text
    assert "[[values]]" in text


def test_respond_prompt_topic_switch_fetches_from_catalog() -> None:
    msg = _system_message("data", {})
    text = msg.content
    assert "memory, not a ceiling" in text
    assert "Topic switches" in text or "topic switches" in text.casefold()
    assert "ya está en pantalla" in text.casefold()
    assert "leyes durante el mandato" in text.casefold() or "mandate" in text.casefold()


def test_chart_catalog_mentions_series_overlay() -> None:
    text = widget_catalog_text()
    assert "derived/series_overlay" in text
    assert "params.x" in text
    assert "derived/fx_spread" in text


def test_eventos_presidenciales_are_in_catalog_prompt() -> None:
    text = catalog.as_prompt_text("data")
    assert "/v1/eventos/presidenciales" in text
    assert "overlay" in text.casefold()


def test_message_text_skips_reasoning_blocks() -> None:
    content = [
        {"type": "reasoning", "summary": [{"text": "voy a buscar el blue"}]},
        {"type": "text", "text": "Acá va el brief."},
    ]
    assert _message_text(content) == "Acá va el brief."


def test_compose_uses_slim_capabilities_not_fetch_recipes() -> None:
    """Compose grounds suggestions without paying for respond's fetch recipes."""
    slim = _CAPABILITIES_COMPOSE.casefold()
    full = _CAPABILITIES.casefold()
    assert "merval" in slim
    assert "emae" in slim
    assert "reservas" in slim
    # Full recipes stay on respond only.
    assert "/v1/historico/dia" in full or "historico/dia" in full
    assert "includevotes=true" not in slim
    assert len(_CAPABILITIES_COMPOSE) < len(_CAPABILITIES) * 0.55
    compose = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "Families we CAN suggest" in compose
    assert "Families we CAN fetch" not in compose


def test_respond_datasets_index_caps_earlier_and_samples() -> None:
    from langchain_core.messages import AIMessage, HumanMessage

    from agent.graph import _dataset_id

    earlier = {}
    for i in range(_EARLIER_DATASET_CAP + 4):
        path = f"/v1/finanzas/extra/{i}"
        ds_id = _dataset_id(path, {})
        earlier[ds_id] = {
            "id": ds_id,
            "path": path,
            "params": {},
            "N": 10,
            "keys": ["fecha", "valor"],
            "rows": [{"fecha": f"2024-01-{j+1:02d}", "valor": j} for j in range(8)],
        }

    path, params = "/v1/cotizaciones/dolares", {"casa": "blue"}
    now_id = _dataset_id(path, params)
    datasets = {
        **earlier,
        now_id: {
            "id": now_id,
            "path": path,
            "params": params,
            "N": 3,
            "keys": ["fecha", "venta"],
            "rows": [
                {"fecha": "2024-06-01", "venta": 1000},
                {"fecha": "2024-06-02", "venta": 1010},
                {"fecha": "2024-06-03", "venta": 1020},
            ],
        },
    }
    messages = [
        HumanMessage(content="mostrá el blue"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "name": "fetch_argentinadatos",
                    "args": {"path": path, "params": params},
                }
            ],
        ),
    ]
    text = _system_message("data", datasets, messages).content
    assert "This turn:" in text
    assert "Earlier (memory" in text
    assert now_id in text
    # Oldest earlier datasets age out.
    dropped = list(earlier.keys())[0]
    kept = list(earlier.keys())[-1]
    assert dropped not in text
    assert kept in text
    # Sample rows capped (3 this-turn / 2 earlier) — not the old 8.
    assert text.count('"fecha":') <= (_EARLIER_DATASET_CAP * 2) + 3 + 5


def test_compact_datasets_respond_keeps_earlier_when_this_turn_hits() -> None:
    """Unlike compose, respond must still see earlier memory for follow-ups."""
    now = {
        "id": "now",
        "path": "/v1/a",
        "params": {},
        "N": 1,
        "keys": ["x"],
        "rows": [{"x": 1}],
    }
    old = {
        "id": "old",
        "path": "/v1/b",
        "params": {},
        "N": 1,
        "keys": ["y"],
        "rows": [{"y": 2}],
    }
    respond = _compact_datasets(
        {"now": now, "old": old}, this_turn={"now"}, audience="respond"
    )
    compose = _compact_datasets(
        {"now": now, "old": old}, this_turn={"now"}, audience="compose"
    )
    assert "old" in respond
    assert "hidden" not in respond.casefold()
    assert "old" not in compose or "hidden" in compose.casefold()
