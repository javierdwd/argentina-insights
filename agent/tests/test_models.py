"""ChatOpenAI kwargs for CopilotKit reasoning summaries + Responses API."""

from __future__ import annotations

from agent.models import chat_kwargs, get_model


def test_strong_skips_summary_by_default(monkeypatch):
    monkeypatch.setenv("MODEL_STRONG", "gpt-5-mini")
    monkeypatch.setenv("REASONING_STRONG", "low")
    monkeypatch.delenv("REASONING_SUMMARY", raising=False)
    kwargs = chat_kwargs("strong")
    assert kwargs["use_responses_api"] is True
    assert kwargs["output_version"] == "responses/v1"
    assert kwargs["reasoning"] == {"effort": "low"}
    assert "reasoning_effort" not in kwargs


def test_strong_can_opt_into_concise_summary(monkeypatch):
    monkeypatch.setenv("MODEL_STRONG", "gpt-5-mini")
    monkeypatch.setenv("REASONING_STRONG", "low")
    monkeypatch.setenv("REASONING_SUMMARY", "concise")
    kwargs = chat_kwargs("strong")
    assert kwargs["reasoning"] == {"effort": "low", "summary": "concise"}


def test_fast_skips_summary_even_with_effort(monkeypatch):
    monkeypatch.setenv("MODEL_FAST", "gpt-5-nano")
    monkeypatch.setenv("REASONING_FAST", "low")
    kwargs = chat_kwargs("fast")
    assert kwargs["reasoning"] == {"effort": "low"}
    assert "summary" not in kwargs["reasoning"]


def test_none_effort_omits_summary(monkeypatch):
    monkeypatch.setenv("MODEL_STRONG", "gpt-5.4-mini")
    monkeypatch.setenv("REASONING_STRONG", "none")
    kwargs = chat_kwargs("strong")
    assert kwargs["reasoning"] == {"effort": "none"}


def test_summary_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MODEL_STRONG", "gpt-5-mini")
    monkeypatch.setenv("REASONING_STRONG", "low")
    monkeypatch.setenv("REASONING_SUMMARY", "off")
    kwargs = chat_kwargs("strong")
    assert kwargs["reasoning"] == {"effort": "low"}


def test_non_reasoning_model_has_no_reasoning_kwargs(monkeypatch):
    monkeypatch.setenv("MODEL_DEFAULT", "gpt-4o-mini")
    kwargs = chat_kwargs("default")
    assert kwargs == {"model": "gpt-4o-mini"}


def test_get_model_builds_chat_openai(monkeypatch):
    monkeypatch.setenv("MODEL_STRONG", "gpt-5-mini")
    monkeypatch.setenv("REASONING_STRONG", "low")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = get_model("strong")
    assert getattr(model, "model_name", None) == "gpt-5-mini" or getattr(
        model, "model", None
    ) == "gpt-5-mini"
    assert model.use_responses_api is True
    assert model.reasoning == {"effort": "low"}
