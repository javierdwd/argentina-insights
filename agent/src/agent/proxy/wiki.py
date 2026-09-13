"""Wikipedia / Wikidata enrichment for a single person profile.

Only used when the proxy is about to return ONE person — never on full
rosters or roll calls (rate limits + latency).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from . import upstream
from .cache import cache

WIKIDATA_BASE = "https://www.wikidata.org"
WIKIPEDIA_BASE = "https://es.wikipedia.org"
TTL = 7 * 24 * 60 * 60

_COMMONS_FILE = re.compile(r"^File:", re.IGNORECASE)

# Schema / mapping leftovers that must never hit Wikipedia (e.g. "name" → Ñame).
_JUNK_PERSON_NAMES = frozenset(
    {
        "name",
        "nombre",
        "apellido",
        "photo",
        "photourl",
        "foto",
        "imagen",
        "role",
        "cargo",
        "party",
        "partido",
        "bloque",
        "province",
        "provincia",
        "email",
        "phone",
        "telefono",
        "links",
        "redes",
        "bio",
        "extract",
        "titulo",
        "title",
        "overview",
        "elenco",
        "unknown",
        "null",
        "none",
        "n/a",
    }
)


def looks_like_person_name(name: str) -> bool:
    """True when *name* is safe to send to Wikipedia / Wikidata search."""
    text = " ".join(str(name or "").split()).strip()
    if len(text) < 3:
        return False
    if text.casefold() in _JUNK_PERSON_NAMES:
        return False
    # Bare schema-ish tokens ("name", "photoUrl") without a real anthroponym.
    if " " not in text and text.isidentifier() and text[:1].islower():
        return False
    return True


def display_name(row: dict) -> str:
    """Build a search-friendly name from a roster / president / PersonCard row."""
    card_name = str(row.get("name") or "").strip()
    nombre = str(row.get("nombre") or "").strip()
    apellido = str(row.get("apellido") or "").strip()
    if apellido and nombre and "," not in nombre:
        # Diputados: separate fields → "Apellido, Nombre" then flip for wiki.
        return f"{nombre} {apellido}".strip()
    if "," in nombre:
        # "Apellido, Nombre" → "Nombre Apellido"
        left, _, right = nombre.partition(",")
        flipped = f"{right.strip()} {left.strip()}".strip()
        return flipped or nombre
    return nombre or apellido or card_name


async def enrich_person(row: dict, *, refresh: bool = False) -> dict:
    """Stamp ``bio`` / photo / partido onto a copy of *row* when found."""
    name = display_name(row)
    if not looks_like_person_name(name):
        return row

    cache_key = f"wiki:person:{name.casefold()}"
    if not refresh:
        cached = cache.peek(cache_key)
        if isinstance(cached, dict):
            return _merge(row, cached)

    try:
        enrichment = await _lookup(name)
    except upstream.UpstreamError as exc:
        if "429" in str(exc) or "Too Many Requests" in str(exc):
            enrichment = await _wikipedia_summary(name)
        else:
            return row
    except Exception:
        return row

    if enrichment:
        cache.put(cache_key, enrichment, TTL)
        return _merge(row, enrichment)
    return row


def _merge(row: dict, enrichment: dict) -> dict:
    out = dict(row)
    wiki_url = enrichment.get("url")
    for key, value in enrichment.items():
        if key == "url" or value in (None, "", []):
            continue
        if out.get(key) in (None, "", []):
            out[key] = value
    if wiki_url:
        links = out.get("redes")
        if not isinstance(links, list):
            links = [links] if links else []
        if wiki_url not in links:
            out["redes"] = [*links, wiki_url]
    return out


async def enrich_person_card(person: dict, *, refresh: bool = False) -> dict:
    """Stamp Wikipedia bio / photo / link onto a bound PersonCard entry.

    PersonCard rows are already mapped (``name``, ``photoUrl``, ``links``).
    Roster-shaped rows still work because ``enrich_person`` reads both.
    """
    if not isinstance(person, dict):
        return person
    probe = str(person.get("name") or person.get("nombre") or "").strip()
    if not looks_like_person_name(probe):
        return person
    row = {
        "nombre": person.get("name") or person.get("nombre"),
        "apellido": person.get("apellido"),
        "foto": person.get("photoUrl") or person.get("foto") or person.get("imagen"),
        "partido": person.get("party") or person.get("partido"),
        "bio": person.get("bio"),
        "redes": person.get("links") or person.get("redes"),
    }
    enriched = await enrich_person(row, refresh=refresh)
    out = dict(person)
    if not out.get("bio") and enriched.get("bio"):
        out["bio"] = enriched["bio"]
    photo = enriched.get("foto") or enriched.get("imagen")
    if not out.get("photoUrl") and photo:
        out["photoUrl"] = photo
    if not out.get("party") and enriched.get("partido"):
        out["party"] = enriched["partido"]
    links = out.get("links")
    if not isinstance(links, list):
        links = [links] if links else []
    wiki_url = enriched.get("url")
    redes = enriched.get("redes") if isinstance(enriched.get("redes"), list) else []
    for href in (*redes, wiki_url):
        if href and href not in links:
            links.append(href)
    if links:
        out["links"] = links
    return out


async def _lookup(name: str) -> dict[str, Any]:
    search = await upstream.get(
        "/w/api.php",
        query={
            "action": "wbsearchentities",
            "search": name,
            "language": "es",
            "uselang": "es",
            "type": "item",
            "limit": 5,
            "format": "json",
        },
        ttl=TTL,
        base_url=WIKIDATA_BASE,
    )
    hits = search.get("search") if isinstance(search, dict) else None
    if not isinstance(hits, list) or not hits:
        # Fall back to Wikipedia summary search by title.
        return await _wikipedia_summary(name)

    qid = None
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        # Prefer humans when the description hints at it.
        desc = str(hit.get("description") or "").casefold()
        if any(
            token in desc
            for token in (
                "político",
                "politico",
                "senador",
                "diputad",
                "presidenta",
                "presidente",
                "argentin",
            )
        ):
            qid = hit.get("id")
            break
    if qid is None and isinstance(hits[0], dict):
        qid = hits[0].get("id")
    if not qid:
        return await _wikipedia_summary(name)

    entities = await upstream.get(
        "/w/api.php",
        query={
            "action": "wbgetentities",
            "ids": qid,
            "props": "claims|sitelinks|labels",
            "languages": "es",
            "format": "json",
        },
        ttl=TTL,
        base_url=WIKIDATA_BASE,
    )
    entity = ((entities or {}).get("entities") or {}).get(qid) or {}
    claims = entity.get("claims") or {}
    sitelinks = entity.get("sitelinks") or {}

    out: dict[str, Any] = {}

    # P18 image
    image = _claim_string(claims.get("P18"))
    if image:
        out["foto"] = _commons_thumb(image)
        out["imagen"] = out["foto"]

    # P102 party
    party_qid = _claim_entity(claims.get("P102"))
    if party_qid:
        party_label = await _entity_label(party_qid)
        if party_label:
            out["partido"] = party_label

    eswiki = sitelinks.get("eswiki") or {}
    title = eswiki.get("title") if isinstance(eswiki, dict) else None
    if title:
        summary = await _wikipedia_summary(str(title))
        out.update({k: v for k, v in summary.items() if v})
    elif not out:
        return await _wikipedia_summary(name)

    return out


async def _entity_label(qid: str) -> str | None:
    raw = await upstream.get(
        "/w/api.php",
        query={
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels",
            "languages": "es|en",
            "format": "json",
        },
        ttl=TTL,
        base_url=WIKIDATA_BASE,
    )
    entity = ((raw or {}).get("entities") or {}).get(qid) or {}
    labels = entity.get("labels") or {}
    for lang in ("es", "en"):
        block = labels.get(lang)
        if isinstance(block, dict) and block.get("value"):
            return str(block["value"])
    return None


async def fetch_summary(title: str, *, refresh: bool = False) -> dict[str, Any]:
    """Public Wikipedia REST summary for any article title."""
    cache_key = f"wiki:summary:{title.casefold()}"
    if not refresh:
        cached = cache.peek(cache_key)
        if isinstance(cached, dict):
            return cached
    out = await _wikipedia_summary(title)
    if out:
        cache.put(cache_key, out, TTL)
    return out


async def _wikipedia_summary(title: str) -> dict[str, Any]:
    encoded = quote(title.replace(" ", "_"), safe="")
    try:
        raw = await upstream.get(
            f"/api/rest_v1/page/summary/{encoded}",
            ttl=TTL,
            base_url=WIKIPEDIA_BASE,
        )
    except upstream.UpstreamError:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    extract = raw.get("extract") or raw.get("description")
    if extract:
        text = str(extract).strip()
        out["extract"] = text
        out["bio"] = text
    page_title = raw.get("title")
    if page_title:
        out["titulo"] = str(page_title)
    content_url = raw.get("content_urls") or {}
    desktop = content_url.get("desktop") or {}
    if isinstance(desktop, dict) and desktop.get("page"):
        out["url"] = str(desktop["page"])
    thumb = raw.get("thumbnail") or {}
    if isinstance(thumb, dict) and thumb.get("source"):
        out.setdefault("foto", thumb["source"])
        out.setdefault("imagen", thumb["source"])
    return out


def _claim_string(claims: Any) -> str | None:
    if not isinstance(claims, list) or not claims:
        return None
    mainsnak = (claims[0] or {}).get("mainsnak") or {}
    datavalue = mainsnak.get("datavalue") or {}
    value = datavalue.get("value")
    return str(value) if value else None


def _claim_entity(claims: Any) -> str | None:
    if not isinstance(claims, list) or not claims:
        return None
    mainsnak = (claims[0] or {}).get("mainsnak") or {}
    datavalue = mainsnak.get("datavalue") or {}
    value = datavalue.get("value") or {}
    if isinstance(value, dict) and value.get("id"):
        return str(value["id"])
    return None


def _commons_thumb(filename: str, width: int = 320) -> str:
    name = _COMMONS_FILE.sub("", filename).strip().replace(" ", "_")
    return (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        f"{quote(name, safe='')}?width={width}"
    )
