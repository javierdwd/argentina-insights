"""Statistical Analyst graph routing and structured-output tests."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from agent import graph as graph_module
from agent.analytics.report import StatisticalFinding, StatisticalReport
from agent.series_util import _dataset_id


def _state() -> dict:
    path = "/v1/football/league/team-stats"
    params = {"teams": "River Plate|Boca Juniors", "seasons": "2023"}
    dataset_id = _dataset_id(path, params)
    return {
        "messages": [
            HumanMessage(content="Compará River y Boca en 2023"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "fetch_argentinadatos",
                        "args": {"path": path, "params": params},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        "datasets": {
            dataset_id: {
                "id": dataset_id,
                "path": path,
                "params": params,
                "rows": [
                    {
                        "team": "River Plate",
                        "season": "2023",
                        "played": 27,
                        "won": 19,
                        "winRate": 19 / 27,
                    },
                    {
                        "team": "Boca Juniors",
                        "season": "2023",
                        "played": 27,
                        "won": 13,
                        "winRate": 13 / 27,
                    },
                ],
                "N": 2,
                "status": "hit",
            }
        },
        "has_tool_calls": False,
        "skip_compose": False,
        "respond_note": "sample-only note",
    }


def test_respond_router_sends_team_stats_to_statistical_analysis() -> None:
    assert graph_module._respond_router(_state()) == "statistical_analysis"


def test_statistical_analysis_node_replaces_sample_note(monkeypatch) -> None:
    expected = StatisticalReport(
        summary="River mostró mayor proporción de victorias.",
        findings=[
            StatisticalFinding(
                title="Ventaja descriptiva",
                conclusion="River ganó una mayor fracción de sus partidos.",
                strength="moderate",
                evidence=["19 de 27 victorias frente a 13 de 27."],
                caveat="Una temporada no establece causalidad.",
            )
        ],
        limitations=["Comparación descriptiva."],
        nextSteps=["Compará ambos equipos durante las últimas cinco temporadas"],
    )

    class FakeStructured:
        def invoke(self, messages, config=None):
            assert "aggregateRows" in messages[-1].content
            assert config == {"metadata": {"emit-messages": False}}
            return expected

    class FakeModel:
        def with_structured_output(self, schema, method=None):
            assert schema is StatisticalReport
            assert method == "function_calling"
            return FakeStructured()

    monkeypatch.setattr(graph_module, "get_model", lambda role: FakeModel())
    update = graph_module.statistical_analysis_node(_state())
    assert update["statistical_report"]["summary"] == expected.summary
    assert "19 de 27" in update["respond_note"]
    assert "[[next]]" in update["respond_note"]


def test_expert_report_is_anchored_below_charts() -> None:
    tree = {
        "id": "comparison",
        "type": "Stack",
        "props": {"gap": "md"},
        "children": [
            {
                "id": "points",
                "type": "Chart",
                "title": "Puntos por partido",
                "props": {},
                "children": [],
            }
        ],
    }
    report = {
        "summary": "River sostuvo una ventaja leve.",
        "findings": [
            {
                "conclusion": "La mayor diferencia apareció en 2023.",
            }
        ],
        "limitations": ["Los formatos de temporada no son idénticos."],
    }
    output = graph_module._append_statistical_callout(tree, report)
    assert output is not None
    callout = output["children"][-1]
    assert callout["type"] == "Callout"
    assert callout["title"] == "Lectura del analista"
    assert "River sostuvo" in callout["props"]["content"]
    assert "Límite:" in callout["props"]["content"]
