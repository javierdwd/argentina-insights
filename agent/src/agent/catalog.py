"""Compact endpoint catalog derived from the ArgentinaDatos OpenAPI spec.

Loaded once at module import; the parsed catalog is held in process memory.
The LLM never receives the raw OpenAPI JSON — only the compact representation
filtered by domain (finance | politics | other).

Token budget reference (measured against openapi.json as of 2026-09):
  Full OpenAPI JSON        ~108 k chars
  Full compact catalog     ~  4 k chars   (all 71 ops, text format)
  Finance subset           ~  2 k chars   (~34 ops)
  Politics subset          ~  1.5 k chars (~30 ops)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_OPENAPI_PATH = (
    Path(__file__).parent.parent.parent / "argentina-datos" / "openapi.json"
)

# Path-prefix → domain mapping (first match wins).
_DOMAIN_PREFIXES: list[tuple[str, str]] = [
    ("/v1/finanzas/", "finance"),
    ("/v1/cotizaciones/", "finance"),
    ("/v1/senado/", "politics"),
    ("/v1/diputados/", "politics"),
    ("/v1/politica/", "politics"),
]

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

    # ── Queries ───────────────────────────────────────────────────────────────

    def for_domain(self, domain: str) -> list[Operation]:
        """Return operations matching *domain*.

        Returns all operations for 'unknown' or 'other' (full catalog fallback).
        """
        if domain in ("unknown", "other"):
            return self._all
        return [op for op in self._all if op.domain == domain]

    def get(self, path: str) -> Operation | None:
        """Look up an operation by its exact path template."""
        return self._by_path.get(path)

    def paths(self) -> list[str]:
        return list(self._by_path)

    def __len__(self) -> int:
        return len(self._all)

    # ── Serialization ─────────────────────────────────────────────────────────

    def as_prompt_text(self, domain: str) -> str:
        """Compact newline-separated catalog for inclusion in a system prompt.

        Format per line:
          - /path/template  # Summary  params: name(*|?)[enum|…]
        where * = required, ? = optional.
        """
        ops = self.for_domain(domain)
        lines: list[str] = []
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
            param_str = (
                f"  params: {', '.join(param_parts)}" if param_parts else ""
            )
            lines.append(f"- {op.path}  # {op.summary}{param_str}")
        return "\n".join(lines)


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


def _parse_param(raw: dict) -> Param:
    schema = raw.get("schema", {})
    type_ = schema.get("type", "string")
    enum = schema.get("enum")
    example = raw.get("example")
    return Param(
        name=raw["name"],
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
    for path, item in spec.get("paths", {}).items():
        get_op = item.get("get")
        if not get_op:
            continue  # all ArgentinaDatos ops are GET

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

    result = Catalog(ops)

    # Inject synthetic client-side date params for filterable endpoints.
    # ``location="client"`` marks them as never forwarded to the HTTP API.
    # Import here (after ops are built) to avoid load-order concerns.
    from .filters import FILTERABLE_PATHS  # noqa: PLC0415

    for op in result._all:
        if op.path not in FILTERABLE_PATHS:
            continue
        existing = {p.name for p in op.params}
        for name in ("desde", "hasta"):
            if name not in existing:
                op.params.append(
                    Param(
                        name=name,
                        location="client",
                        required=False,
                        type="string",
                    )
                )

    return result


# ── Singleton — parsed once at import time ────────────────────────────────────
catalog: Catalog = _load_catalog()
