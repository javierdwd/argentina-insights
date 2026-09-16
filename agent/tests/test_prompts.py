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
    _compose_message,
    _compact_datasets,
    _message_text,
    _next_to_actions_block,
    _sanitize_user_facing,
    _system_message,
)
from agent.ui.catalog import as_prompt_text as widget_catalog_text


def test_historical_day_recipe_fetches_only_relevant_context() -> None:
    caps = _CAPABILITIES.casefold()
    respond = _RESPOND_SYSTEM.casefold()
    compose = _COMPOSE_SYSTEM.casefold()
    assert "persona" in caps
    assert "weather" in caps
    assert "/v1/noticias" in _CAPABILITIES
    assert "equal weight" in respond
    assert "retrospective" in respond
    assert "period reporting" in respond
    assert "purely numeric" in respond
    assert "do not add unrelated source" in respond
    assert "spanish q" in respond
    assert "/v1/wiki/personas" in caps
    assert "official roster" in caps
    assert "both personcard and news" in caps
    assert "dataset shape" in compose
    catalog_text = catalog.as_prompt_text("data")
    assert "persona" in catalog_text
    widgets = widget_catalog_text().casefold()
    assert "/v1/" not in widgets
    assert "weather rows" in widgets
    assert "one person profile or a roster" in widgets


def test_query_routing_uses_structured_classification(monkeypatch) -> None:
    from langchain_core.messages import HumanMessage

    from agent.graph import classify_node

    class Classifier:
        def with_structured_output(self, schema, method=None):
            assert schema.__name__ == "_QueryClassification"
            assert method == "function_calling"
            return self

        def invoke(self, messages, config):
            assert messages
            classifier_prompt = messages[0][1]
            assert "resolved semantic request" in classifier_prompt
            assert "elliptical replies" in classifier_prompt
            assert "Assistant-authored process or control language" in classifier_prompt
            assert "choose data" in classifier_prompt
            return {"query_type": "ui"}

    monkeypatch.setattr("agent.graph.get_model", lambda role: Classifier())
    result = classify_node(
        {
            "messages": [HumanMessage(content="Transformá su presentación")],
            "query_type": "data",
        }
    )
    assert result == {"query_type": "ui"}


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


def test_broad_exploratory_asks_use_relevant_sources_and_synthesize() -> None:
    text = _system_message("data", {}).content
    folded = text.casefold()
    assert "qué sabés de x" in folded
    assert "materially relevant evidence role" in folded
    assert "latest 7 days" in folded
    assert "wikipedia" in folded
    assert "news" in folded
    assert "bloc/party composition" in folded
    assert "quantitative series" in folded
    assert "do not stop after one or two numeric series" in folded
    assert "reason across sources" in folded
    assert "association from causation" in folded
    assert "not permission to fetch the whole catalog" in folded
    broad_section = folded.split("## broad exploratory asks:", 1)[1].split(
        "## how to think", 1
    )[0]
    assert "javier milei" not in broad_section


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


def test_sanitize_user_facing_strips_residual_internal_tags() -> None:
    raw = (
        "No se encontraron eventos.\n"
        "[[next]]\n[boton]Revisar 2025[/boton]\n"
        "[[route]] chat [[/route]]"
    )
    out = _sanitize_user_facing(raw)
    assert "[[next]]" not in out
    assert "[[route]]" not in out
    assert "[boton]Revisar 2025[/boton]" in out


def test_compose_message_drops_internal_implementation_actions() -> None:
    out = _compose_message(
        "Comparación preparada.",
        [
            "Compará sus votos con los demás representantes de la provincia",
            "Revisá si el widget necesita patch en props.series",
            "Actualizá el dataRef a ds_abcdef12",
        ],
    )
    assert "Compará sus votos" in out
    assert "widget" not in out.casefold()
    assert "patch" not in out.casefold()
    assert "dataref" not in out.casefold()
    assert "ds_abcdef12" not in out


def test_sanitize_user_facing_drops_internal_implementation_sentences() -> None:
    out = _sanitize_user_facing(
        "Revisaré si el Widget B necesita patch en props.series. "
        "La comparación de votos sigue disponible."
    )
    assert out == "La comparación de votos sigue disponible."


def test_analyst_next_actions_drop_internal_implementation_actions() -> None:
    out = _next_to_actions_block(
        "[[next]]\n"
        "- Compará los votos por provincia\n"
        "- Aplicá un parche al widget actual\n"
        "[[/next]]"
    )
    assert "Compará los votos por provincia" in out
    assert "parche" not in out.casefold()
    assert "widget" not in out.casefold()


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


def test_compose_catalog_treats_box_as_first_class_authored_component() -> None:
    catalog = widget_catalog_text().casefold()
    assert "### box" in catalog
    assert "svg" in catalog
    assert "first-class" in catalog
    assert "semantic table" in catalog
    assert "ordinary nested html" in catalog
    assert "never invent scores/ranks" in catalog
    assert "dataref" in catalog  # banned on Box (when_not / props)
    assert "honor a user-named form" in catalog
    compose = _COMPOSE_SYSTEM.casefold()
    assert "box" in compose
    assert "substitute" in compose and "data-bound widget" in compose
    assert "box is a first-class authored component" in compose
    assert "semantic tables, nested divs" in compose
    assert "numeric axis is a factual claim" in compose
    assert "pseudo-scores" in compose
    assert "private layout preflight" in compose
    assert "narrow canvas" in compose
    assert "one responsive svg" in compose
    assert "never align html div/span labels" in compose
    assert "aesthetic judgment" in compose
    assert "focal point" in compose
    assert "repeated generic cards" in compose
    assert "semantic table for aligned values" in compose
    assert "well-structured table or document is a valid" in compose
    assert "does not need plotted marks" in compose
    assert "same grounding rule applies to text and callout" in compose
    assert "never write placeholders" in compose
    assert "inferred" in compose and "biographies" in compose
    assert "every node, including every html/svg host child" in compose
    assert "all host attributes" in compose
    assert "every child needs a unique id" in compose
    assert "flechas" not in compose  # principle, not keyword triggers
    assert "do not overlay absolute html labels" in catalog
    assert "preflight bounds, clipping and label collisions" in catalog
    assert "every host child requires id,type,props,children" in catalog
    assert "https href for image" in catalog


def test_respond_routes_structured_comparison_to_compose() -> None:
    text = _RESPOND_SYSTEM.casefold()
    assert "custom visual" in text or "box" in text
    assert "box" in text
    assert "markdown table" in text
    assert "named form" in text or "chart kind" in text
    assert "never create arbitrary scores" in text
    assert "is only for source-backed" in text
    assert "flechas" not in text


def test_respond_materializes_presidential_duration_aggregates() -> None:
    text = _RESPOND_SYSTEM.casefold()
    assert "group_duration" in text
    assert "dias_acumulados" in text
    assert "never claim an aggregate was calculated" in text


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


def test_scope_guardrail_allows_bounded_knowledge_after_acceptance() -> None:
    from agent.graph import _SCOPE

    scope = _SCOPE.casefold()
    assert "first decide whether the user's query is in" in scope
    assert "primary subject itself must belong" in scope
    assert "scope laundering" in scope
    assert '"qué es javascript en argentina"' in scope
    assert "must be refused without explaining javascript" in scope
    assert "once the query or an independently answerable part" in scope
    assert "pretrained knowledge only" in scope
    assert "does not broaden the accepted topic" in scope
    assert "political orientation is an approximate, contestable classification" in scope
    assert "out-of-scope sub-question" in scope
    assert "never use pretrained knowledge to supply or overwrite numbers" in scope
    assert "ui composer may render" in scope
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


def test_next_to_actions_block_salvages_unclosed_chat_next() -> None:
    note = (
        "No se encontraron eventos presidenciales registrados.\n\n"
        "[[next]]\n"
        "- [boton]Revisar eventos presidenciales de 2025[/boton]\n"
        "- [boton]Comparar riesgo país con inflación y confianza[/boton]"
    )
    out = _next_to_actions_block(note)
    assert "[[next]]" not in out
    assert "[[actions]]" in out
    assert "[[/actions]]" in out
    assert "Revisar eventos presidenciales de 2025" in out
    assert "Comparar riesgo país con inflación y confianza" in out


def test_compose_prompt_prefers_one_visual_for_compatible_measures() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "compatible" in text
    assert "one visual" in text
    assert "same X and grain" in text


def test_compose_prompt_separates_genuinely_different_layers() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    assert "different layers" in text.casefold()
    assert "VoteBreakdown" in text
    catalog = widget_catalog_text()
    assert "one roll-call vote" in catalog
    assert "values whose order, trend, or category spacing matters" in catalog.casefold()


def test_respond_prompt_vote_composition_fetches_votos_and_same_day_spots() -> None:
    msg = _system_message("data", {})
    text = msg.content.casefold()
    assert "distribución del voto" in text
    assert "votos" in text
    assert "[[values]]" in msg.content
    assert "de ese día" in text


def test_compose_prompt_keeps_raw_values_out_of_callout() -> None:
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
    catalog = widget_catalog_text()
    assert "Callout" in catalog
    assert "raw values without an interpretation" in catalog.casefold()


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
    assert "event markers or labeled intervals" in compose.casefold()


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


def test_compose_exposes_old_canvas_for_duplicate_detection() -> None:
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
    assert "current canvas is authoritative" in text.casefold()
    assert "never add a second widget" in text.casefold()
    assert "uva_stack" in text
    assert "MUST bind at least one" in text
    assert "hidden — this turn has new hits" in text
    assert "ds_olduva" in text
    assert ds_id in text




def test_compose_prompt_separates_prose_from_typed_actions() -> None:
    text = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    compact = " ".join(text.split())
    assert "`actions` is the only place for follow-up offers" in compact
    assert "Never put facts, markup, buttons, or protocol tags" in compact


def test_prompts_prevent_option_confirmation_loops() -> None:
    respond = _system_message("data", {}).content
    compose = _build_compose_system(
        {
            "messages": [],
            "datasets": {},
            "respond_note": "",
            "ui_tree": None,
            "ui_tree_unbound": None,
        }
    )
    respond_compact = " ".join(respond.split())
    compose_compact = " ".join(compose.split())

    assert "Resolve elliptical replies against conversation history" in respond_compact
    assert "execute the selected domain request" in respond_compact
    assert "presentation preference is NOT missing" in respond_compact
    assert "self-contained end-user domain request" in respond_compact
    assert "agent-control instructions" in respond_compact
    assert "Assistant-authored process/control language" in respond_compact

    assert "compact selection or answer" in compose_compact
    assert "never ask for the same choice or confirmation again" in compose_compact
    assert "Every action must be self-contained" in compose_compact
    assert "end-user domain outcomes" in compose_compact
    assert "implementation mechanisms" in compose_compact
    assert "assistant-authored process/control language" in compose_compact.casefold()
    assert "recover the unresolved domain goal from history" in compose_compact



def test_should_compose_routes_without_legacy_fallback() -> None:
    from agent.graph import _should_compose

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












def test_bind_chart_leaves_numeric_series_alone() -> None:
    from agent.ui.pipeline import bind_tree

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
    out = bind_tree(tree, datasets)
    assert out["props"]["data"] == datasets["ds_fx"]["rows"]


def test_chart_catalog_documents_generic_data_grain() -> None:
    text = widget_catalog_text()
    assert "Wide data requires one row per xKey" in text
    assert "For long data, set seriesBy" in text
    assert "exact category values as series keys" in text




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


def test_widget_catalog_is_independent_of_api_recipes() -> None:
    text = widget_catalog_text()
    assert "/v1/" not in text
    assert "derived/" not in text
    assert "homePointsPerGame" not in text
    assert "fx_spread" not in text


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
