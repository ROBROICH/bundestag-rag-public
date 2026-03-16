"""
FastAPI application: Chat UI + MCP Server for Bundestag DIP API.
- GET  /           → Chat Web UI
- POST /api/chat   → OpenAI chat with DIP API function calling
- /mcp             → MCP Server (SSE transport)
"""
import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, field_validator

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load .env file from project root (override=True ensures .env values take precedence)
from dotenv import load_dotenv
load_dotenv(project_root / ".env", override=True)

from config.settings import BUNDESTAG_API_KEY, BUNDESTAG_API_BASE_URL
from src.web.openai_config import (
    CHARS_PER_TOKEN,
    MAX_CHUNK_CHARS,
    CHUNK_OVERLAP_CHARS,
    OPENAI_MAX_TOKENS,
    OPENAI_TIMEOUT,
    MODEL_CONTEXT_WINDOW,
    OUTPUT_TOKENS_RESERVED,
    SYSTEM_PROMPT_TOKENS,
    EMERGENCY_TRUNCATE_RATIO,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _get_openai_key() -> str:
    """Read the OpenAI API key fresh from the environment on every call.
    This avoids stale module-level caching issues with uvicorn --reload."""
    return os.getenv("OPENAI_API_KEY", "")

# ---------------------------------------------------------------------------
# Token estimation & text chunking (reuses project-wide config)
# ---------------------------------------------------------------------------
# Reserve budget for tool results: context window minus system prompt, output,
# and a buffer for conversation history (~20K tokens for 20 messages).
_CONVERSATION_HISTORY_BUDGET_TOKENS = 20000
_TOOL_RESULT_MAX_TOKENS = (
    MODEL_CONTEXT_WINDOW
    - OUTPUT_TOKENS_RESERVED
    - SYSTEM_PROMPT_TOKENS
    - _CONVERSATION_HISTORY_BUDGET_TOKENS
)
_TOOL_RESULT_MAX_CHARS = int(_TOOL_RESULT_MAX_TOKENS * CHARS_PER_TOKEN)

# Cap per-tool response to the proven chunk size for German parliamentary text
TOOL_RESPONSE_MAX_CHARS = min(_TOOL_RESULT_MAX_CHARS, MAX_CHUNK_CHARS * 3)


def _estimate_tokens(text: str) -> int:
    """Estimate token count using the project's German-optimised ratio."""
    return int(len(text) / CHARS_PER_TOKEN)


def _truncate_tool_response(text: str, max_chars: int = TOOL_RESPONSE_MAX_CHARS) -> str:
    """Truncate a tool response to fit within the token budget.

    Preserves sentence boundaries where possible and appends a notice
    so the model knows the text was shortened.
    """
    if len(text) <= max_chars:
        return text

    target = int(max_chars * EMERGENCY_TRUNCATE_RATIO)
    # Try to cut at a sentence boundary
    cut = text.rfind(". ", 0, target)
    if cut < target // 2:
        cut = text.rfind(" ", 0, target)
    if cut < target // 2:
        cut = target
    truncated = text[: cut + 1].rstrip()
    notice = (
        f"\n\n[... Text gekürzt: {len(text):,} → {len(truncated):,} Zeichen. "
        f"Bitte fasse den gezeigten Teil zusammen und weise darauf hin, "
        f"dass das Dokument länger ist.]"
    )
    return truncated + notice

# ---------------------------------------------------------------------------
# OpenAI function definitions (mirror MCP tools for function-calling)
# ---------------------------------------------------------------------------

# Map short/colloquial party names → formal DIP API urheber values
URHEBER_ALIASES = {
    "spd": "Fraktion der SPD",
    "cdu": "Fraktion der CDU/CSU",
    "csu": "Fraktion der CDU/CSU",
    "cdu/csu": "Fraktion der CDU/CSU",
    "afd": "Fraktion der AfD",
    "grüne": "Fraktion BÜNDNIS 90/DIE GRÜNEN",
    "grünen": "Fraktion BÜNDNIS 90/DIE GRÜNEN",
    "bündnis 90": "Fraktion BÜNDNIS 90/DIE GRÜNEN",
    "bündnis 90/die grünen": "Fraktion BÜNDNIS 90/DIE GRÜNEN",
    "linke": "Fraktion DIE LINKE",
    "die linke": "Fraktion DIE LINKE",
    "fdp": "Fraktion der FDP",
    "bsw": "Gruppe BSW",
    "bundesregierung": "Bundesregierung",
    "bundestag": "Bundestag",
    "bundesrat": "Bundesrat",
}


def _resolve_urheber(value: str | None) -> str | None:
    """Resolve a short party name to the formal DIP API urheber value."""
    if not value:
        return None
    return URHEBER_ALIASES.get(value.lower().strip(), value)


OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_vorgaenge",
            "description": "Search Bundestag Vorgänge (parliamentary procedures). "
                "Can filter by Fraktion/party (urheber), procedure type, and date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords (German works best). Can be empty when filtering by urheber."},
                    "wahlperiode": {"type": "integer", "description": "Parliamentary term number (e.g. 21 for current term)"},
                    "urheber": {
                        "type": "string",
                        "description": "Filter by originator (Fraktion/institution). Use formal names: "
                            "'Fraktion der SPD', 'Fraktion der CDU/CSU', 'Fraktion der AfD', "
                            "'Fraktion BÜNDNIS 90/DIE GRÜNEN', 'Fraktion DIE LINKE', 'Fraktion der FDP', "
                            "'Bundesregierung', 'Bundestag'. Short forms like 'SPD' or 'AfD' are auto-resolved.",
                    },
                    "vorgangstyp": {
                        "type": "string",
                        "description": "Filter by procedure type, e.g. 'Kleine Anfrage', 'Gesetzgebung', "
                            "'Antrag', 'Aktuelle Stunde', 'Rechtsverordnung', 'EU-Vorlage'.",
                    },
                    "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "Max results (default 25, max 50)", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_drucksachen",
            "description": "Search Bundestag Drucksachen (printed papers / official documents). "
                "Can filter by Fraktion/party (urheber) and document type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords. Can be empty when filtering by urheber."},
                    "wahlperiode": {"type": "integer", "description": "Parliamentary term number (e.g. 21)"},
                    "urheber": {
                        "type": "string",
                        "description": "Filter by originator Fraktion/institution (see search_vorgaenge for values).",
                    },
                    "drucksachetyp": {
                        "type": "string",
                        "description": "Filter by document type, e.g. 'Kleine Anfrage', 'Gesetzentwurf', "
                            "'Antrag', 'Antwort', 'Schriftliche Fragen', 'Beschlussempfehlung und Bericht', "
                            "'Unterrichtung', 'Bericht', 'Stellungnahme'.",
                    },
                    "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
                    "limit": {"type": "integer", "description": "Max results (default 25, max 50)", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_plenarprotokolle",
            "description": "Search Bundestag Plenarprotokolle (plenary session transcripts).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords"},
                    "wahlperiode": {"type": "integer"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                    "limit": {"type": "integer", "description": "Max results (default 25, max 50)", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vorgang",
            "description": "Get metadata of a specific Vorgang (procedure) by numeric ID. Returns metadata only, no full text. Use get_vorgang_details for metadata + full text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vorgang_id": {"type": "integer", "description": "Vorgang ID"},
                },
                "required": ["vorgang_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vorgang_details",
            "description": "Get full details of a Vorgang INCLUDING the relevant Drucksache full text. Automatically finds the matching Drucksache (even for 'Schriftliche Fragen' compilations) and extracts the relevant section. Use this when the user wants to read or summarise a Vorgang.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vorgang_id": {"type": "integer", "description": "Vorgang ID"},
                },
                "required": ["vorgang_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drucksache",
            "description": "Get details of a specific Drucksache (document) by numeric ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drucksache_id": {"type": "integer", "description": "Drucksache ID"},
                },
                "required": ["drucksache_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_personen",
            "description": "Search for Bundestag members by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Name to search"},
                    "wahlperiode": {"type": "integer"},
                    "limit": {"type": "integer", "description": "Max results (default 25, max 50)", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_aktivitaeten",
            "description": "Search Bundestag Aktivitäten (parliamentary activities like speeches, motions, votes). "
                "Can filter by Fraktion/party (urheber) and activity type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords. Can be empty when filtering by urheber."},
                    "wahlperiode": {"type": "integer"},
                    "urheber": {
                        "type": "string",
                        "description": "Filter by originator Fraktion/institution (see search_vorgaenge for values).",
                    },
                    "aktivitaetsart": {
                        "type": "string",
                        "description": "Filter by activity type.",
                    },
                    "limit": {"type": "integer", "description": "Max results (default 25, max 50)", "default": 25},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drucksache_text",
            "description": "Get the full text content of a Drucksache (printed paper / official document). Use this to read the actual question and government answer text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drucksache_id": {"type": "integer", "description": "Drucksache numeric ID"},
                },
                "required": ["drucksache_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plenarprotokoll_text",
            "description": "Get the full text of a Plenarprotokoll (plenary session transcript).",
            "parameters": {
                "type": "object",
                "properties": {
                    "protokoll_id": {"type": "integer", "description": "Plenarprotokoll numeric ID"},
                },
                "required": ["protokoll_id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# DIP API helper (shared with MCP tools)
# ---------------------------------------------------------------------------
import httpx
from functools import lru_cache
import hashlib

_http_client = None
_async_http_client = None


def _get_dip_client():
    global _http_client
    if _http_client is None:
        api_key = os.getenv("DIP_API_KEY") or os.getenv("BUNDESTAG_API_KEY") or BUNDESTAG_API_KEY
        _http_client = httpx.Client(
            base_url=BUNDESTAG_API_BASE_URL,
            headers={
                "Authorization": f"ApiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "Bundestag-Chat/1.0",
            },
            timeout=30.0,
        )
    return _http_client


def _get_async_dip_client():
    """Async DIP client with HTTP/2 and connection pooling for parallel requests."""
    global _async_http_client
    if _async_http_client is None:
        api_key = os.getenv("DIP_API_KEY") or os.getenv("BUNDESTAG_API_KEY") or BUNDESTAG_API_KEY
        _async_http_client = httpx.AsyncClient(
            base_url=BUNDESTAG_API_BASE_URL,
            headers={
                "Authorization": f"ApiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "Bundestag-Chat/1.0",
            },
            timeout=30.0,
            http2=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _async_http_client


# In-memory cache for DIP API responses (max 256 entries, 1h TTL)
_dip_cache: dict[str, tuple[float, dict]] = {}  # key -> (timestamp, data)
_DIP_CACHE_MAX = 256
_DIP_CACHE_TTL = 3600  # seconds


def _cache_key(endpoint: str, params: dict) -> str:
    raw = f"{endpoint}|{json.dumps(params, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _dip_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Synchronous DIP API request (used by non-streaming endpoint)."""
    import time as _t
    client = _get_dip_client()
    params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    key = _cache_key(endpoint, params)
    cached = _dip_cache.get(key)
    if cached and (_t.time() - cached[0]) < _DIP_CACHE_TTL:
        logger.debug(f"[cache hit] {endpoint}")
        return cached[1]
    resp = client.get(f"/{endpoint.lstrip('/')}", params=params)
    resp.raise_for_status()
    result = resp.json()
    if len(_dip_cache) >= _DIP_CACHE_MAX:
        _dip_cache.pop(next(iter(_dip_cache)))
    _dip_cache[key] = (_t.time(), result)
    return result


async def _dip_request_async(endpoint: str, params: Optional[dict] = None) -> dict:
    """Async DIP API request — no thread pool needed, true async I/O."""
    import time as _t
    client = _get_async_dip_client()
    params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
    key = _cache_key(endpoint, params)
    cached = _dip_cache.get(key)
    if cached and (_t.time() - cached[0]) < _DIP_CACHE_TTL:
        logger.debug(f"[cache hit] {endpoint}")
        return cached[1]
    resp = await client.get(f"/{endpoint.lstrip('/')}", params=params)
    resp.raise_for_status()
    result = resp.json()
    if len(_dip_cache) >= _DIP_CACHE_MAX:
        _dip_cache.pop(next(iter(_dip_cache)))
    _dip_cache[key] = (_t.time(), result)
    return result


def _drucksache_pdf_url(doc_nr: str) -> str:
    """Generate PDF download URL for a Bundestag Drucksache.
    Example: '21/4186' → 'https://dserver.bundestag.de/btd/21/041/2104186.pdf'
    """
    try:
        parts = doc_nr.split("/")
        if len(parts) != 2:
            return ""
        wp, nr = parts[0].strip(), parts[1].strip()
        nr_padded = nr.zfill(5)
        folder = nr_padded[:3]
        return f"https://dserver.bundestag.de/btd/{wp}/{folder}/{wp}{nr_padded}.pdf"
    except (ValueError, IndexError, AttributeError):
        return ""


def _slugify(text: str, max_len: int = 80) -> str:
    """Convert a German title to a URL-friendly slug for DIP web links."""
    import re as _re
    s = text.lower()
    # Replace German umlauts and ß
    for src, dst in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
        s = s.replace(src, dst)
    s = _re.sub(r"[^a-z0-9]+", "-", s)  # non-alphanum → hyphen
    s = _re.sub(r"-{2,}", "-", s).strip("-")  # collapse multiple hyphens
    return s[:max_len].rstrip("-") if len(s) > max_len else s


def _dip_web_url(doc_type: str, numeric_id: str, title: str = "") -> str:
    """Generate a DIP web link for documents without a PDF (Vorgänge, Aktivitäten, etc.).
    DIP requires format: /vorgang/{title-slug}/{id}
    """
    type_map = {
        "Vorgänge": "vorgang",
        "Aktivitäten": "aktivitaet",
        "Plenarprotokolle": "plenarprotokoll",
    }
    slug = type_map.get(doc_type, "vorgang")
    title_slug = _slugify(title) if title else "-"
    return f"https://dip.bundestag.de/{slug}/{title_slug}/{numeric_id}"


def _format_docs(result: dict, doc_type: str, collected_refs: list = None) -> str:
    """Format DIP API search results compactly to minimize token usage.
    If collected_refs is provided, appends {type, id, nr, title} for action tile generation.
    """
    docs = result.get("documents", [])
    total = result.get("numFound", 0)

    # Sort by date descending (newest first)
    docs.sort(key=lambda d: d.get("datum", d.get("aktualisiert", "")), reverse=True)

    lines = [f"Gefunden: {total} {doc_type} (zeige {len(docs)}).\n"]
    for doc in docs:
        title = doc.get("titel", doc.get("dokumentnummer", "N/A"))
        # Sanitize: replace newlines/pipes that break markdown tables
        title = " ".join(title.split())
        if len(title) > 120:
            title = title[:117] + "..."
        date = doc.get("datum", doc.get("aktualisiert", ""))
        doc_nr = doc.get("dokumentnummer", "")
        numeric_id = doc.get("id", "N/A")
        dtype = doc.get("vorgangstyp", doc.get("drucksachetyp", ""))

        id_part = f"[{doc_nr}|ID:{numeric_id}]" if doc_nr else f"[ID:{numeric_id}]"
        # Add plain-language classification for non-experts
        desc = _doc_type_description(dtype)
        desc_part = f" ({dtype} — {desc})" if dtype and desc else (f" ({dtype})" if dtype else "")
        pdf = _drucksache_pdf_url(doc_nr) if doc_nr else ""
        if not pdf:
            base_type = doc_type.split(" [")[0] if " [" in doc_type else doc_type
            pdf = _dip_web_url(base_type, str(numeric_id), title)
        pdf_part = f" [PDF]({pdf})" if pdf else ""

        lines.append(f"- {id_part} {title}{desc_part} — {date}{pdf_part}")

        if collected_refs is not None:
            short_title = (title[:60] + "...") if len(title) > 60 else title
            base_type = doc_type.split(" [")[0] if " [" in doc_type else doc_type
            collected_refs.append({
                "type": base_type,
                "id": str(numeric_id),
                "nr": doc_nr,
                "title": short_title,
                "full_title": title,
                "dtype": dtype,
                "desc": desc,
                "datum": date,
                "pdf": pdf,
            })
    return "\n".join(lines)


def _build_search_table(refs: list, language: str = "de") -> str:
    """Build a complete markdown search result table server-side from collected refs.
    Eliminates the need for a Phase 2 OpenAI call for search-only queries.
    """
    if not refs:
        return "Keine Ergebnisse gefunden." if language == "de" else "No results found."

    heading = f"## \U0001f3db\ufe0f {len(refs)} Treffer\n\n" if language == "de" else f"## \U0001f3db\ufe0f {len(refs)} Results\n\n"
    if language == "de":
        header = "| Nr. | Titel | Typ | Beschreibung | Datum | Aktionen |"
    else:
        header = "| No. | Title | Type | Description | Date | Actions |"
    sep = "|--:|---|---|---|---|---|"

    # Type name translations for English tables
    _TYPE_EN = {
        "Kleine Anfrage": "Minor Inquiry", "Große Anfrage": "Major Inquiry",
        "Gesetzentwurf": "Draft Bill", "Gesetzgebung": "Legislation",
        "Antrag": "Motion", "Antwort": "Answer",
        "Beschlussempfehlung": "Committee Recommendation",
        "Bericht": "Report", "Unterrichtung": "Government Report",
        "Schriftliche Frage": "Written Question", "Mündliche Frage": "Oral Question",
        "Entschließungsantrag": "Resolution Motion", "Verordnung": "Regulation",
        "Rechtsverordnung": "Ordinance", "Änderungsantrag": "Amendment",
        "Beschlussempfehlung und Bericht": "Committee Recommendation & Report",
        "Plenarprotokoll": "Plenary Transcript", "Stellungnahme": "Official Opinion",
        "Petition": "Petition", "Aktuelle Stunde": "Topical Debate",
        "EU-Vorlage": "EU Proposal", "Regierungserklärung": "Government Statement",
        "Befragung der Bundesregierung": "Government Questioning",
    }

    rows = []
    for i, ref in enumerate(refs, 1):
        title = ref.get("full_title", ref.get("title", ""))
        title = " ".join(title.split()).replace("|", "–")
        dtype = ref.get("dtype", "")
        # Re-derive description and type name in the correct language
        if language == "en":
            display_type = _TYPE_EN.get(dtype, dtype)
            desc = _doc_type_description(dtype, "en") or display_type
        else:
            display_type = dtype
            desc = ref.get("desc", "") or _doc_type_description(dtype, "de") or dtype
        datum = ref.get("datum", "")
        pdf = ref.get("pdf", "")
        doc_type = ref.get("type", "Drucksachen")
        doc_id = ref.get("id", "")
        doc_nr = ref.get("nr", "")
        # Fallback: generate DIP web link if no PDF URL
        if not pdf and doc_id:
            raw_title = ref.get("full_title", ref.get("title", ""))
            pdf = _dip_web_url(doc_type, doc_id, raw_title)
        # Merge links into one Actions cell — PDF label differs by link type
        parts = []
        if pdf:
            label = "📄 PDF" if "dserver.bundestag.de" in pdf else "📄 DIP"
            parts.append(f"[{label}]({pdf})")
        parts.append(f"[🤖 AI](ai:{doc_type}:{doc_id}:{doc_nr})")
        citizen_label = "👤 Citizens" if language == "en" else "👤 Bürger:innen"
        parts.append(f"[{citizen_label}](ci:{doc_type}:{doc_id}:{doc_nr})")
        actions = " ".join(parts)
        rows.append(f"| {i} | {title} | {display_type} | {desc} | {datum} | {actions} |")

    table = "\n".join([header, sep] + rows)

    # Static follow-up actions
    if language == "de":
        followup = [
            {"label": "\U0001f50e Weitere Suche", "prompt": "Suche nach verwandten Themen in Wahlperiode 21"},
            {"label": "\U0001f4ca Statistik", "prompt": "Wie viele Dokumente gibt es zu diesem Thema pro Fraktion?"},
        ]
    else:
        followup = [
            {"label": "\U0001f50e More results", "prompt": "Search for related topics in legislative period 21"},
            {"label": "\U0001f4ca Statistics", "prompt": "How many documents per party faction on this topic?"},
        ]
    import json as _json
    followup_html = f"<!-- FOLLOWUP: {_json.dumps(followup, ensure_ascii=False)} -->"
    return heading + table + "\n\n" + followup_html


async def _translate_titles_to_english(table_md: str, client) -> str:
    """Translate only the German document titles in a search table to English.
    Uses concurrent batches with sufficient token budget for GPT-5's reasoning.
    Limited to first MAX_TITLES for performance.
    """
    import re as _re
    import asyncio as _aio
    BATCH_SIZE = 10
    MAX_TITLES = 30  # Only translate visible titles for speed

    rows = table_md.split("\n")
    title_rows: list[tuple[int, str]] = []
    for idx, row in enumerate(rows):
        cells = row.split("|")
        if len(cells) >= 4 and cells[1].strip().isdigit():
            title = cells[2].strip()
            if title and any(c.isalpha() for c in title):
                title_rows.append((idx, title))
                if len(title_rows) >= MAX_TITLES:
                    break

    if not title_rows:
        return table_md

    logger.info("Title translation: %d titles in batches of %d", len(title_rows), BATCH_SIZE)

    async def _translate_batch(batch: list[tuple[int, str]], batch_num: int, total: int) -> dict[int, str]:
        titles = [t for _, t in batch]
        numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
        prompt = (
            f"Translate these {len(titles)} German parliamentary document titles to English.\n"
            f"Return EXACTLY {len(titles)} numbered lines. No extra text.\n\n"
            + numbered
        )
        try:
            resp = await client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=8192,
            )
            choice = resp.choices[0] if resp.choices else None
            if not choice:
                return {}
            text = choice.message.content or ""
            if not text:
                logger.warning("Batch %d/%d: empty (finish_reason=%s)",
                               batch_num, total, getattr(choice, 'finish_reason', '?'))
                return {}
            trans = []
            for line in text.strip().split("\n"):
                cleaned = _re.sub(r'^\d+[\.\)\:\-]\s*', '', line.strip())
                if cleaned:
                    trans.append(cleaned)
            if len(trans) == len(batch):
                return {row_idx: t for (row_idx, _), t in zip(batch, trans)}
            logger.warning("Batch %d/%d: count mismatch %d vs %d",
                           batch_num, total, len(trans), len(batch))
        except Exception as e:
            logger.warning("Batch %d/%d failed: %s", batch_num, total, e)
        return {}

    batches = [title_rows[i:i+BATCH_SIZE] for i in range(0, len(title_rows), BATCH_SIZE)]
    results = await _aio.gather(*[
        _translate_batch(b, i+1, len(batches)) for i, b in enumerate(batches)
    ])

    idx_to_title = dict(title_rows)
    translated = 0
    for mapping in results:
        for row_idx, new_title in mapping.items():
            orig_title = idx_to_title[row_idx]
            rows[row_idx] = rows[row_idx].replace(orig_title, new_title, 1)
            translated += 1

    logger.info("Title translation: %d/%d titles translated", translated, len(title_rows))
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Web Search: News coverage via OpenAI Responses API
# ---------------------------------------------------------------------------
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "false").lower() in ("true", "1", "yes")

_NEWS_DOMAINS = [
    "spiegel.de", "zeit.de", "tagesschau.de", "faz.net",
    "sueddeutsche.de", "handelsblatt.com", "welt.de",
    "tagesspiegel.de", "rnd.de", "ndr.de", "zdf.de",
    "deutschlandfunk.de", "br.de", "heise.de",
    "netzpolitik.org", "euractiv.de", "table.media",
    "reuters.com", "politico.eu",
]


async def _search_news_coverage(title: str, doc_type: str, language: str, client) -> str:
    """Search for news articles about a parliamentary document using OpenAI Responses API.
    Returns a markdown section with cited news links, or empty string if nothing found.
    """
    if not ENABLE_WEB_SEARCH:
        return ""

    # Build a focused search query from the document title
    # Always search in German since we target German news domains
    short_title = title[:200] if len(title) > 200 else title

    query = (
        f"Finde aktuelle Nachrichtenartikel und Medienberichte über dieses "
        f"Thema aus dem Deutschen Bundestag: {short_title}. "
        f"Bundestag Deutschland. Fokus auf Berichterstattung und Analyse."
    )
    if language == "en":
        section_header = "#### 📰 External Media Coverage"
        section_note = "*The following articles are independent media reports related to this topic — they are not referenced by or part of the parliamentary document.*"
    else:
        section_header = "#### 📰 Externe Medienberichte zur Thematik"
        section_note = "*Die folgenden Artikel sind unabhängige Medienberichte zum Thema — sie sind nicht Teil des parlamentarischen Dokuments und werden darin nicht referenziert.*"

    try:
        response = await client.responses.create(
            model=CHAT_MODEL,
            tools=[{
                "type": "web_search",
                "filters": {
                    "allowed_domains": _NEWS_DOMAINS,
                },
                "user_location": {
                    "type": "approximate",
                    "country": "DE",
                },
            }],
            include=["web_search_call.action.sources"],
            input=query,
            max_output_tokens=8192,
        )

        # Extract citations from response output
        citations = []
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content_block in getattr(item, "content", []):
                    for ann in getattr(content_block, "annotations", []):
                        if getattr(ann, "type", None) == "url_citation":
                            url = getattr(ann, "url", "")
                            ann_title = getattr(ann, "title", "")
                            if url and ann_title:
                                domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                                citations.append((ann_title, url, domain))

        if not citations:
            logger.info("Web search: no citations found for '%s'", short_title[:60])
            return ""

        # Deduplicate by URL
        seen_urls = set()
        unique = []
        for t, u, d in citations:
            if u not in seen_urls:
                seen_urls.add(u)
                unique.append((t, u, d))

        # Limit to top 5 results
        unique = unique[:5]

        lines = ["\n\n---", section_header, section_note]
        for ann_title, url, domain in unique:
            lines.append(f"- [{ann_title}]({url}) — *{domain}*")

        logger.info("Web search: found %d news links for '%s'", len(unique), short_title[:60])
        return "\n".join(lines)

    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return ""


# Plain-language descriptions of parliamentary document types for non-experts
_DOC_TYPE_DESCRIPTIONS_DE = {
    "Kleine Anfrage": "Fragen einer Fraktion an die Regierung",
    "Große Anfrage": "Umfangreiche Anfrage mit Debatte",
    "Gesetzentwurf": "Vorschlag für ein neues Gesetz oder Gesetzesänderung",
    "Gesetzgebung": "Gesetzgebungsverfahren im Bundestag",
    "Antrag": "Aufforderung an Regierung oder Bundestag zu handeln",
    "Antwort": "Antwort der Regierung auf eine Anfrage",
    "Beschlussempfehlung": "Empfehlung eines Ausschusses zur Abstimmung",
    "Bericht": "Informationsbericht zu einem Thema",
    "Unterrichtung": "Information der Regierung an den Bundestag",
    "Schriftliche Frage": "Einzelfrage eines Abgeordneten an die Regierung",
    "Mündliche Frage": "Frage in der Fragestunde im Plenum",
    "Entschließungsantrag": "Antrag zur Meinungsäußerung des Bundestags",
    "Verordnung": "Rechtsverbindliche Regel der Regierung",
    "Rechtsverordnung": "Verbindliche Vorschrift der Regierung",
    "Änderungsantrag": "Vorschlag zur Änderung eines Gesetzentwurfs",
    "Beschlussempfehlung und Bericht": "Ausschuss-Empfehlung mit Begründung",
    "Plenarprotokoll": "Wortprotokoll einer Bundestags-Sitzung",
    "Stellungnahme": "Offizielle Meinung einer Institution",
    "Wahlvorschlag": "Vorschlag zur Wahl einer Person",
    "Petition": "Bürgeranliegen an den Bundestag",
    "Aktuelle Stunde": "Kurzdebatte zu aktuellem Thema",
    "EU-Vorlage": "EU-Gesetzesvorlage zur Beratung",
    "Regierungserklärung": "Erklärung der Regierung im Plenum",
    "Mündliche Frage (Plenum)": "Frage in der Fragestunde im Plenum",
    "Befragung der Bundesregierung": "Befragung der Bundesregierung",
}

_DOC_TYPE_DESCRIPTIONS_EN = {
    "Kleine Anfrage": "Minor inquiry by a parliamentary group",
    "Große Anfrage": "Major inquiry requiring parliamentary debate",
    "Gesetzentwurf": "Draft bill for a new law or amendment",
    "Gesetzgebung": "Legislative procedure in the Bundestag",
    "Antrag": "Motion requesting government or parliamentary action",
    "Antwort": "Government response to an inquiry",
    "Beschlussempfehlung": "Committee recommendation for a vote",
    "Bericht": "Informational report on a topic",
    "Unterrichtung": "Government notification to the Bundestag",
    "Schriftliche Frage": "Written question by an MP to the government",
    "Mündliche Frage": "Oral question during plenary Q&A session",
    "Entschließungsantrag": "Resolution motion expressing parliamentary opinion",
    "Verordnung": "Legally binding government regulation",
    "Rechtsverordnung": "Binding government ordinance",
    "Änderungsantrag": "Amendment to a draft bill",
    "Beschlussempfehlung und Bericht": "Committee recommendation with rationale",
    "Plenarprotokoll": "Verbatim transcript of a plenary session",
    "Stellungnahme": "Official opinion of an institution",
    "Wahlvorschlag": "Nomination for election of a person",
    "Petition": "Citizen petition to the Bundestag",
    "Aktuelle Stunde": "Topical debate on a current issue",
    "EU-Vorlage": "EU legislative proposal for consultation",
    "Regierungserklärung": "Government statement in plenary",
    "Mündliche Frage (Plenum)": "Oral question during plenary Q&A session",
    "Befragung der Bundesregierung": "Questioning of the Federal Government",
}

# Keep backward compat alias
_DOC_TYPE_DESCRIPTIONS = _DOC_TYPE_DESCRIPTIONS_DE

def _doc_type_description(dtype: str, language: str = "de") -> str:
    """Return a plain-language description for a document type."""
    if not dtype:
        return ""
    descs = _DOC_TYPE_DESCRIPTIONS_EN if language == "en" else _DOC_TYPE_DESCRIPTIONS_DE
    if dtype in descs:
        return descs[dtype]
    for key, desc in descs.items():
        if key in dtype or dtype in key:
            return desc
    return ""


async def _multi_search_async(endpoint: str, query: str, base_params: dict,
                               doc_type: str, refs: list, max_rows: int = 10) -> str:
    """Smart search: split multi-word queries into individual keyword searches,
    run in parallel, and merge/deduplicate results by document ID.
    Single-word queries go straight through unchanged.
    """
    import re
    # Split on commas, semicolons, or 'OR' — then also split remaining multi-word phrases
    parts = re.split(r'[,;]\s*|\bOR\b', query, flags=re.IGNORECASE)
    keywords = [p.strip().strip('"').strip("'") for p in parts if p.strip()]
    # If only one keyword or query is very short, do a simple search
    if len(keywords) <= 1:
        params = {**base_params, "f.titel": query, "rows": max_rows}
        return _format_docs(await _dip_request_async(endpoint, params), doc_type, refs)

    # Parallel search for each keyword
    async def _search_one(kw):
        params = {**base_params, "f.titel": kw, "rows": max_rows}
        return await _dip_request_async(endpoint, params)

    results = await asyncio.gather(*[_search_one(kw) for kw in keywords[:4]])

    # Merge and deduplicate by document ID
    seen_ids = set()
    merged_docs = []
    total_found = 0
    for result in results:
        total_found += result.get("numFound", 0)
        for doc in result.get("documents", []):
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged_docs.append(doc)

    # Sort by date (newest first) — _format_docs also sorts, but this ensures merged order
    merged_docs.sort(key=lambda d: d.get("datum", ""), reverse=True)

    merged_result = {"numFound": total_found, "documents": merged_docs}
    kw_str = " / ".join(keywords[:4])
    return _format_docs(merged_result, f'{doc_type} [{kw_str}]', refs)


def _extract_section_from_text(full_text: str, keywords: list[str],
                               context_chars: int = 3000) -> Optional[str]:
    """Extract a relevant section from a large compiled document.

    Uses a scoring approach: finds all keyword positions, clusters them to
    find the region where the most keywords appear close together, then
    expands to paragraph boundaries.
    """
    if not keywords:
        return None

    text_lower = full_text.lower()

    # Find all match positions for each keyword
    positions = []
    for kw in keywords:
        kw_lower = kw.lower()
        pos = text_lower.find(kw_lower)
        while pos >= 0:
            positions.append((pos, kw))
            pos = text_lower.find(kw_lower, pos + 1)

    if not positions:
        return None

    positions.sort(key=lambda x: x[0])

    # Sliding window: find the region with the highest keyword density
    # (most unique keywords within a window)
    window_size = context_chars
    best_score = 0
    best_center = positions[0][0]

    for anchor_pos, _ in positions:
        window_kws = set()
        for pos, kw in positions:
            if anchor_pos <= pos <= anchor_pos + window_size:
                window_kws.add(kw.lower())
        score = len(window_kws)
        if score > best_score:
            best_score = score
            # Center on the middle of the matching region
            matching_positions = [p for p, k in positions if anchor_pos <= p <= anchor_pos + window_size]
            best_center = (min(matching_positions) + max(matching_positions)) // 2

    # Require at least 2 keyword matches for compiled documents
    if best_score < 2 and len(keywords) >= 3:
        return None

    # Expand to paragraph boundaries around the best center
    start = max(0, best_center - context_chars // 2)
    end = min(len(full_text), best_center + context_chars // 2)

    para_start = full_text.rfind("\n\n", start, best_center)
    if para_start > start:
        start = para_start + 2

    para_end = full_text.find("\n\n", best_center + 100, end + context_chars)
    if para_end > 0:
        end = para_end

    return full_text[start:end].strip()


def _resolve_vorgang_text(vorgang_id: int) -> str:
    """Smart lookup: Vorgang → matching Drucksache → relevant text section.

    For 'Schriftliche Frage' type Vorgänge, the DIP API does not directly
    link to the containing Drucksache. This function:
    1. Fetches Vorgang metadata (title, date, type)
    2. Searches for Drucksachen of matching type around the same date
    3. Fetches the full text of matching Drucksachen
    4. Extracts the relevant section by keyword matching
    """
    vorgang = _dip_request(f"vorgang/{vorgang_id}")
    titel = vorgang.get("titel", "")
    datum = vorgang.get("datum", "")
    vorgangstyp = vorgang.get("vorgangstyp", "")
    wahlperiode = vorgang.get("wahlperiode")

    meta = (
        f"## Vorgang {vorgang_id}\n"
        f"**Titel:** {titel}\n"
        f"**Typ:** {vorgangstyp}\n"
        f"**Datum:** {datum}\n"
        f"**Wahlperiode:** {wahlperiode}\n"
        f"**Beratungsstand:** {vorgang.get('beratungsstand', 'N/A')}\n"
    )
    deskriptoren = vorgang.get("deskriptor", [])
    if deskriptoren:
        meta += "**Deskriptoren:** " + ", ".join(d.get("name", "") for d in deskriptoren) + "\n"

    # Determine the Drucksache type to search for
    drs_type_map = {
        "Schriftliche Frage": "Schriftliche Fragen",
    }
    drucksache_type = drs_type_map.get(vorgangstyp)

    # Types whose text lives in Plenarprotokolle (oral questions, debates)
    _plenary_types = {"Mündliche Frage", "Aktuelle Stunde"}

    found_text = None

    # --- Path A: Resolve via linked Aktivitäten (fundstelle) ---
    # The DIP API links Vorgänge to Aktivitäten which contain exact page refs
    if vorgangstyp in _plenary_types and datum:
        try:
            akt_result = _dip_request("aktivitaet", {
                "f.aktivitaetsart": "Mündliche Frage",
                "f.datum.start": datum,
                "f.datum.end": datum,
                "f.wahlperiode": wahlperiode,
                "rows": 100,
            })
            # Find activities linked to this Vorgang via vorgangsbezug
            linked_acts = []
            for akt in akt_result.get("documents", []):
                for vb in akt.get("vorgangsbezug", []):
                    if str(vb.get("id", "")) == str(vorgang_id):
                        linked_acts.append(akt)
                        break

            if linked_acts:
                # Extract fundstelle info (persons, page refs, PDF URL)
                persons = []
                plp_fundstelle = None
                for act in linked_acts:
                    person_name = act.get("titel", "")
                    act_type = act.get("aktivitaetsart", "")
                    fs = act.get("fundstelle", {})
                    if person_name:
                        persons.append(f"**{person_name}** ({act_type})")
                    if fs.get("dokumentart") == "Plenarprotokoll" and not plp_fundstelle:
                        plp_fundstelle = fs

                if persons:
                    meta += "**Beteiligte:** " + ", ".join(persons) + "\n"

                if plp_fundstelle:
                    plp_nr = plp_fundstelle.get("dokumentnummer", "")
                    plp_id = plp_fundstelle.get("id", "")
                    pdf_url = plp_fundstelle.get("pdf_url", "")
                    seite = plp_fundstelle.get("seite", "")
                    anfang = plp_fundstelle.get("anfangsseite", 0)
                    ende = plp_fundstelle.get("endseite", 0)
                    meta += f"**Plenarprotokoll:** {plp_nr} (ID: {plp_id})\n"
                    if seite:
                        meta += f"**Seiten:** S. {seite}\n"
                    if pdf_url:
                        meta += f"**PDF:** {pdf_url}\n"

                    # Fetch Plenarprotokoll full text and extract by page number
                    if plp_id:
                        try:
                            text_data = _dip_request(f"plenarprotokoll-text/{plp_id}")
                            full_text = text_data.get("text", "")
                            if full_text and anfang:
                                # Use page marker (e.g. "7365") to find the section
                                page_marker = str(anfang)
                                # Build keywords from title + deskriptoren + page ref
                                _common = {"durch", "diese", "dieser", "einem", "einer",
                                           "einen", "nicht", "nach", "über", "werden",
                                           "wurde", "wird", "sind", "sein", "dass",
                                           "auch", "noch", "bereits", "sowie"}
                                keywords = [
                                    w for w in titel.split()
                                    if len(w) > 4 and w.lower() not in _common
                                ]
                                for desk in deskriptoren:
                                    dname = desk.get("name", "")
                                    if dname and dname not in keywords:
                                        keywords.append(dname)
                                # Add person names as high-priority keywords
                                for act in linked_acts:
                                    pname = act.get("titel", "").split(",")[0].strip()
                                    if pname and len(pname) > 3:
                                        keywords.append(pname)

                                section = _extract_section_from_text(
                                    full_text, keywords, context_chars=6000
                                )
                                if section:
                                    found_text = (
                                        f"\n\n## Volltext (aus Plenarprotokoll {plp_nr}"
                                        f"{', S. ' + seite if seite else ''})\n\n"
                                        f"{section}"
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to fetch Plenarprotokoll text {plp_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to resolve Aktivitäten for Vorgang {vorgang_id}: {e}")

    # --- Path B: Drucksache text for compiled document types ---
    if not found_text and drucksache_type and datum:
        # For compiled document types: search by type + date range
        from datetime import datetime, timedelta
        try:
            dt = datetime.strptime(datum, "%Y-%m-%d")
            date_start = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
            date_end = (dt + timedelta(days=14)).strftime("%Y-%m-%d")
        except ValueError:
            date_start, date_end = None, None

        if date_start:
            search = _dip_request("drucksache", {
                "f.drucksachetyp": drucksache_type,
                "f.datum.start": date_start,
                "f.datum.end": date_end,
                "f.wahlperiode": wahlperiode,
                "rows": 5,
            })
            for drs in search.get("documents", []):
                drs_id = drs.get("id")
                drs_nr = drs.get("dokumentnummer", "?")
                try:
                    text_data = _dip_request(f"drucksache-text/{drs_id}")
                    full_text = text_data.get("text", "")
                    if not full_text:
                        continue

                    # Build search keywords from title + deskriptoren
                    _common = {"durch", "diese", "dieser", "einem", "einer",
                               "einen", "nicht", "nach", "über", "werden",
                               "wurde", "wird", "sind", "sein", "dass",
                               "auch", "noch", "bereits", "sowie"}
                    keywords = [
                        w for w in titel.split()
                        if len(w) > 4 and w.lower() not in _common
                    ]
                    # Add deskriptor names as high-value keywords
                    for desk in deskriptoren:
                        dname = desk.get("name", "")
                        if dname and dname not in keywords:
                            keywords.append(dname)
                    section = _extract_section_from_text(full_text, keywords)
                    if section:
                        found_text = (
                            f"\n\n## Volltext (aus Drucksache {drs_nr})\n\n"
                            f"{section}"
                        )
                        meta += f"**Drucksache:** {drs_nr} (ID: {drs_id})\n"
                        meta += f"**PDF:** https://dserver.bundestag.de/btd/{str(wahlperiode)}/{drs_nr.split('/')[1][:3]}/{str(wahlperiode)}{drs_nr.split('/')[1]}.pdf\n"
                        break
                except Exception as e:
                    logger.warning(f"Failed to fetch text for Drucksache {drs_id}: {e}")

    if not found_text and titel:
        # Fallback: search Drucksachen by title keywords
        search = _dip_request("drucksache", {
            "f.titel": titel,
            "f.wahlperiode": wahlperiode,
            "rows": 5,
        })
        for drs in search.get("documents", []):
            drs_id = drs.get("id")
            drs_nr = drs.get("dokumentnummer", "?")
            try:
                text_data = _dip_request(f"drucksache-text/{drs_id}")
                full_text = text_data.get("text", "")
                if full_text:
                    found_text = (
                        f"\n\n## Volltext (aus Drucksache {drs_nr})\n\n"
                        f"{_truncate_tool_response(full_text)}"
                    )
                    meta += f"**Drucksache:** {drs_nr} (ID: {drs_id})\n"
                    break
            except Exception as e:
                logger.warning(f"Failed to fetch text for Drucksache {drs_id}: {e}")

    if not found_text:
        found_text = "\n\n*Volltext konnte nicht automatisch zugeordnet werden. Nutze `get_drucksache_text` mit einer bekannten Drucksache-ID, um den Text manuell abzurufen.*"

    result = meta + found_text
    return _truncate_tool_response(result)


# ---------------------------------------------------------------------------
# Tool execution dispatcher
# ---------------------------------------------------------------------------

def _extract_numeric_id(args: dict, *keys: str) -> Optional[int]:
    """Extract a numeric ID from LLM tool arguments, handling common malformations.
    Tries each key in order, strips prefixes like 'v', 'DIP-', 'd', etc.
    """
    import re as _re
    for key in keys:
        val = args.get(key)
        if val is not None:
            s = str(val).strip()
            # Strip common prefixes: v331472, DIP-331472, d12345
            m = _re.search(r'(\d+)', s)
            if m:
                return int(m.group(1))
    return None

def _unwrap_multi_tool_calls(tool_calls: list) -> list:
    """Unwrap OpenAI's internal multi_tool_use.parallel pseudo-tool into
    individual tool calls that our dispatcher can handle."""
    from types import SimpleNamespace
    unwrapped = []
    for tc in tool_calls:
        if tc.function.name == "multi_tool_use.parallel":
            try:
                wrapper = json.loads(tc.function.arguments)
                for i, use in enumerate(wrapper.get("tool_uses", [])):
                    real_name = use.get("recipient_name", "").replace("functions.", "")
                    real_args = json.dumps(use.get("parameters", {}))
                    fake_tc = SimpleNamespace(
                        id=f"{tc.id}_{i}",
                        function=SimpleNamespace(name=real_name, arguments=real_args),
                    )
                    unwrapped.append(fake_tc)
            except Exception:
                unwrapped.append(tc)
        else:
            unwrapped.append(tc)
    return unwrapped


def execute_tool(name: str, args: dict, collected_refs: list = None) -> str:
    """Execute a tool call and return the result as a string."""
    refs = collected_refs if collected_refs is not None else []
    try:
        if name == "search_vorgaenge":
            params = {
                "f.titel": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.vorgangstyp": args.get("vorgangstyp"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
                "rows": min(args.get("limit", 25), 50),
            }
            return _format_docs(_dip_request("vorgang", params), "Vorgänge", refs)

        elif name == "search_drucksachen":
            params = {
                "f.titel": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.drucksachetyp": args.get("drucksachetyp"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
                "rows": min(args.get("limit", 25), 50),
            }
            return _format_docs(_dip_request("drucksache", params), "Drucksachen", refs)

        elif name == "search_plenarprotokolle":
            params = {
                "f.titel": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
                "rows": min(args.get("limit", 25), 50),
            }
            return _format_docs(_dip_request("plenarprotokoll", params), "Plenarprotokolle", refs)

        elif name == "get_vorgang":
            doc = _dip_request(f"vorgang/{args['vorgang_id']}")
            return json.dumps(doc, ensure_ascii=False, indent=2)

        elif name == "get_vorgang_details":
            vid = _extract_numeric_id(args, "vorgang_id", "id", "doc_id")
            if not vid:
                return "Error: vorgang_id is required"
            return _resolve_vorgang_text(vid)

        elif name == "get_drucksache":
            did = _extract_numeric_id(args, "drucksache_id", "id", "doc_id")
            if not did:
                return "Error: drucksache_id is required"
            doc = _dip_request(f"drucksache/{did}")
            return json.dumps(doc, ensure_ascii=False, indent=2)

        elif name == "search_personen":
            params = {
                "f.vorname+nachname": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "rows": min(args.get("limit", 25), 50),
            }
            result = _dip_request("person", params)
            docs = result.get("documents", [])
            lines = [f"Found {result.get('numFound', 0)} Personen. Showing {len(docs)}:\n"]
            for doc in docs:
                name_str = f"{doc.get('vorname', '')} {doc.get('nachname', '')}".strip()
                lines.append(f"- [ID: {doc.get('id')}] {name_str}")
            return "\n".join(lines)

        elif name == "search_aktivitaeten":
            params = {
                "f.titel": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.aktivitaetsart": args.get("aktivitaetsart"),
                "rows": min(args.get("limit", 25), 50),
            }
            return _format_docs(_dip_request("aktivitaet", params), "Aktivitäten", refs)

        elif name == "get_drucksache_text":
            did = _extract_numeric_id(args, "drucksache_id", "id", "doc_id")
            if not did:
                return "Error: drucksache_id is required"
            doc = _dip_request(f"drucksache-text/{did}")
            raw = json.dumps(doc, ensure_ascii=False, indent=2)
            return _truncate_tool_response(raw)

        elif name == "get_plenarprotokoll_text":
            pid = _extract_numeric_id(args, "protokoll_id", "id", "doc_id")
            if not pid:
                return "Error: protokoll_id is required"
            doc = _dip_request(f"plenarprotokoll-text/{pid}")
            raw = json.dumps(doc, ensure_ascii=False, indent=2)
            return _truncate_tool_response(raw)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.error(f"Tool execution error ({name}): {e}", exc_info=True)
        return f"Error executing {name}: An internal error occurred. Please try again."


async def execute_tool_async(name: str, args: dict, collected_refs: list = None) -> str:
    """Async tool execution — uses true async I/O for DIP API calls."""
    refs = collected_refs if collected_refs is not None else []
    try:
        if name == "search_vorgaenge":
            max_rows = min(args.get("limit", 25), 50)
            base_params = {
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.vorgangstyp": args.get("vorgangstyp"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
            }
            return await _multi_search_async("vorgang", args.get("query", ""),
                                             base_params, "Vorgänge", refs, max_rows)

        elif name == "search_drucksachen":
            max_rows = min(args.get("limit", 25), 50)
            base_params = {
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.drucksachetyp": args.get("drucksachetyp"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
            }
            return await _multi_search_async("drucksache", args.get("query", ""),
                                             base_params, "Drucksachen", refs, max_rows)

        elif name == "search_plenarprotokolle":
            max_rows = min(args.get("limit", 25), 50)
            base_params = {
                "f.wahlperiode": args.get("wahlperiode"),
                "f.datum.start": args.get("date_from"),
                "f.datum.end": args.get("date_to"),
            }
            return await _multi_search_async("plenarprotokoll", args.get("query", ""),
                                             base_params, "Plenarprotokolle", refs, max_rows)

        elif name == "get_vorgang":
            vid = _extract_numeric_id(args, "vorgang_id", "id", "doc_id")
            if not vid:
                return "Error: vorgang_id is required"
            doc = await _dip_request_async(f"vorgang/{vid}")
            return json.dumps(doc, ensure_ascii=False, indent=2)

        elif name == "get_vorgang_details":
            vid = _extract_numeric_id(args, "vorgang_id", "id", "doc_id")
            if not vid:
                return "Error: vorgang_id is required"
            return await asyncio.to_thread(_resolve_vorgang_text, vid)

        elif name == "get_drucksache":
            did = _extract_numeric_id(args, "drucksache_id", "id", "doc_id")
            if not did:
                return "Error: drucksache_id is required"
            doc = await _dip_request_async(f"drucksache/{did}")
            return json.dumps(doc, ensure_ascii=False, indent=2)

        elif name == "search_personen":
            params = {
                "f.vorname+nachname": args.get("query"),
                "f.wahlperiode": args.get("wahlperiode"),
                "rows": min(args.get("limit", 25), 50),
            }
            result = await _dip_request_async("person", params)
            docs = result.get("documents", [])
            lines = [f"Found {result.get('numFound', 0)} Personen. Showing {len(docs)}:\n"]
            for doc in docs:
                name_str = f"{doc.get('vorname', '')} {doc.get('nachname', '')}".strip()
                lines.append(f"- [ID: {doc.get('id')}] {name_str}")
            return "\n".join(lines)

        elif name == "search_aktivitaeten":
            max_rows = min(args.get("limit", 25), 50)
            base_params = {
                "f.wahlperiode": args.get("wahlperiode"),
                "f.urheber": _resolve_urheber(args.get("urheber")),
                "f.aktivitaetsart": args.get("aktivitaetsart"),
            }
            return await _multi_search_async("aktivitaet", args.get("query", ""),
                                             base_params, "Aktivitäten", refs, max_rows)

        elif name == "get_drucksache_text":
            did = _extract_numeric_id(args, "drucksache_id", "id", "doc_id")
            if not did:
                return "Error: drucksache_id is required"
            doc = await _dip_request_async(f"drucksache-text/{did}")
            raw = json.dumps(doc, ensure_ascii=False, indent=2)
            return _truncate_tool_response(raw)

        elif name == "get_plenarprotokoll_text":
            pid = _extract_numeric_id(args, "protokoll_id", "id", "doc_id")
            if not pid:
                return "Error: protokoll_id is required"
            doc = await _dip_request_async(f"plenarprotokoll-text/{pid}")
            raw = json.dumps(doc, ensure_ascii=False, indent=2)
            return _truncate_tool_response(raw)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.error(f"Async tool execution error ({name}): {e}", exc_info=True)
        return f"Error executing {name}: An internal error occurred. Please try again."


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(application: FastAPI):
    key = _get_openai_key()
    logger.info("Bundestag DIP Chat & MCP Server starting")
    logger.info(f"OPENAI_API_KEY configured: {'yes' if key else 'NO — set OPENAI_API_KEY!'}")
    logger.info(f"BUNDESTAG_API_KEY configured: {'yes' if BUNDESTAG_API_KEY else 'NO — set BUNDESTAG_API_KEY!'}")
    yield

app = FastAPI(
    title="Bundestag DIP Chat & MCP Server",
    description="Chat with the German Bundestag parliamentary database. "
                "Also serves an MCP endpoint for LLM tool integration.",
    version="1.0.0",
    lifespan=_lifespan,
)

# CORS middleware — default restricts to same-origin; set ALLOWED_ORIGINS env var for Azure domain
_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins_raw if o.strip() and o.strip() != "*"]
if not _allowed_origins:
    logger.warning("No valid CORS origins configured — using localhost defaults")
    _allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# Security headers middleware
class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if os.getenv("ENABLE_HSTS", "").lower() == "true":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(_SecurityHeadersMiddleware)


# Simple in-memory rate limiter for chat endpoints
import time as _rl_time
from collections import defaultdict as _defaultdict

_rate_limit_store: dict[str, list[float]] = _defaultdict(list)
_RATE_LIMIT_WINDOW = 60   # seconds
_RATE_LIMIT_MAX = 30       # max requests per window per IP

# Mount MCP server (FastMCP v3 uses http_app() returning a Starlette ASGI app)
from src.mcp.server import mcp as mcp_server
app.mount("/mcp", mcp_server.http_app(transport="sse"))

# Serve static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ---------------------------------------------------------------------------
# System prompt – loads the detailed German prompt template at startup,
# then wraps it with chat-specific tool-use instructions.
# ---------------------------------------------------------------------------
def _load_prompt_file(filename: str) -> Optional[str]:
    """Load a prompt template from the src/web/ directory."""
    prompt_dir = Path(__file__).parent.parent / "web"
    path = prompt_dir / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning(f"Prompt file not found: {path}")
    return None


# ============================================================================
# Modular Prompt Architecture — English core, task-specific composition
# Phase 1 (tool selection): compact prompt (~900 chars)
# Phase 2 (answer generation): task-specific prompt swapped in
# ============================================================================

# Phase 1: Tool selection — compact English prompt for fast tool-calling
_PHASE1_PROMPT = """You are an expert on German parliamentary documentation (Bundestag).
You have access to the DIP API (Documentation and Information System for Parliamentary Materials).

## Critical Rule: NEVER Ask Clarifying Questions
- ALWAYS execute a search immediately. NEVER ask the user for clarification.
- If a query is broad (e.g. "Welche Gesetze wurden 2026 verabschiedet?"), search with reasonable
  defaults: use the current year, search Vorgänge with vorgangstyp=Gesetzgebung, limit=25.
- Interpret user intent generously and search. The user can always refine later.

## Tool Usage Rules
1. **BATCH searches:** Call max 2-3 search tools per round. Combine keywords
   comma-separated in ONE query (e.g. `query: "Digitalisierung, Datenschutz, KI"`) —
   the server splits and merges automatically. NEVER make separate calls per keyword.
2. **Set limit >= 25** to show all results. Do NOT restrict results.
3. Search results contain numeric IDs (e.g. `ID: 329620`). Use these for detail queries.
4. **Vorgang full text:** Use `get_vorgang_details` (NOT `get_vorgang_text` — doesn't exist).
5. **Drucksache full text:** Use `get_drucksache_text` with the Drucksache ID.
6. Do NOT confuse Vorgang IDs with Drucksache IDs — different entities.
7. **Max 1 round** of tool calls — then answer immediately with available results.
8. For Kleine/Grosse Anfragen: identify the requesting Fraktion and responsible ministry."""


# Phase 2 addon: Document analysis template (appended for non-search queries)
_ANALYSIS_PROMPT = """
## Document Summary & Analysis

You are an expert analyst of German parliamentary documents.
Provide clear, accurate summaries — journalistic in tone, neutral, in German.

### Instructions
1. **JSON Metadata First**: Extract drucksachetyp, urheber, autoren_anzeige, ressort,
   vorgangsbezug, document numbers, dates, electoral periods from the context metadata.
2. **Key Entities**: Political parties/coalitions (from urheber), individuals, organizations,
   government ministries (ressort).
3. **Named Persons from Document Text**: ALWAYS extract specific named individuals mentioned
   in the document text — speakers, questioners, responding officials, committee chairs.
   Include their full name, party affiliation (if stated), and role (e.g. "Parl. Staatssekretär",
   "Abgeordnete", "Vizepräsidentin"). For Plenarprotokolle and Fragestunden, list ALL speakers.
4. **Subject Domain**: Main topic (healthcare, climate, defense, etc.) + procedural context.
5. **Financial Aspects**: Budgets, proposed allocations, macroeconomic implications.
6. **Kleine/Große Anfragen & Antworten**: Always extract and name the requesting party
   from urheber. For "Antwort" documents, identify BOTH the responding authority AND
   the original requesting party.

### Output Format (German, Markdown)

### [Document Classification] — [Main Topic]

**Dokumentart:** *[drucksachetyp]*
**Urheber:** **[Party/author from metadata]**
**Ressort:** **[Responsible ministry]**
**Datum:** *[Date]*

#### 📋 Überblick
[2-3 paragraphs in journalistic tone explaining:
- WHAT is the problem this document addresses? (use "Problem und Ziel" section if available)
- WHAT solution or action is proposed?
- WHY does this matter? What is the real-world significance?
Do NOT just repeat the title — explain the substance in accessible language.]

#### 🎯 Kernpunkte
- [Substantive key point — what concretely changes or is proposed]
- [Key point 2 — specific provisions, numbers, or mechanisms]
- [Key point 3 — political or legal significance]

#### 👥 Hauptakteure
- **[Named Person]** ([Party], [Role — e.g. Parl. Staatssekretär, Abgeordnete]): [What they said/did]
- **[Named Person]** ([Party], [Role]): [What they said/did]
- **[Ministry/Institution]:** [Involvement]

#### 💰 Finanzielle Aspekte
[Financial info if relevant, or "Keine finanziellen Aspekte genannt."]

#### ⚡ Auswirkungen und nächste Schritte
[Implications, vorgangsbezug context, what happens next]

### Rules
- Cite document numbers (BT-Drs 21/4186) and dates
- Bold for key terms, names, numbers
- ALWAYS extract named individuals from the document TEXT, not only from metadata
- The Überblick section must explain the SUBSTANCE — never just list metadata
- For Gesetzentwürfe: explain the problem, the proposed solution, and real-world impact
- Be precise, journalistically neutral
- Integrate metadata naturally into the narrative
- If metadata fields are missing, focus on available information"""


# Search result table format (shared between analysis and search-only prompts)
_TABLE_FORMAT = """
## Search Result Tables
Format as: | No. | Title | Type | Description | Date | Actions |
- **Description**: Plain-language (max 10 words), derived from title + document type
- **Actions**: Combine links in ONE cell: `[📄 PDF](url) [🤖 AI](ai:DOCTYPE:ID:DOCNR) [👤 Bürger:innen](ci:DOCTYPE:ID:DOCNR)`
  - DOCTYPE = "Drucksachen", "Vorgänge", "Plenarprotokolle" or "Aktivitäten"
  - ID = numeric ID, DOCNR = document number or empty
- Sort by date DESC. Show ALL results."""


# Follow-up action instructions (appended to Phase 2 prompts)
_FOLLOWUP_PROMPT = """
## Follow-up Actions
At the END of EVERY response, add a hidden HTML comment with 3-5 context-specific actions:
<!-- FOLLOWUP: [{"label":"🔍 Label","prompt":"Full prompt text"},{"label":"📊 Label2","prompt":"Prompt2"}] -->
- Use emojis: 🔍🎤⏱️❓📋🏛️📜🔎📊⏰🗳️⚖️💰
- Prompts must work as direct user messages (include IDs when available)
- Actions SPECIFIC to the current content — no generic suggestions"""


# Lightweight Phase 2 prompt for search-only queries
_SEARCH_TABLE_PROMPT_DE = """Du formatierst DIP-API-Suchergebnisse als kompakte Markdown-Tabelle.

## Regeln
- Tabellenformat: | Nr. | Titel | Typ | Beschreibung | Datum | Aktionen |
- **Beschreibung**: Allgemeinverständliche Erklärung (max 10 Worte)
- **Aktionen**: In EINER Zelle: `[📄 PDF](url) [🤖 AI](ai:DOCTYPE:ID:DOCNR) [👤 Bürger:innen](ci:DOCTYPE:ID:DOCNR)`
  - DOCTYPE = "Drucksachen", "Vorgänge", "Plenarprotokolle" oder "Aktivitäten"
- Nach Datum absteigend sortieren. ALLE Ergebnisse zeigen.
- Beginne mit 🏛️ Überschrift und Trefferzahl.
- Am Ende: <!-- FOLLOWUP: [{"label":"🔎 ...","prompt":"..."},{"label":"📊 ...","prompt":"..."}] -->
- Nur Tabelle + ein Kontextsatz, keine Analyse."""

_SEARCH_TABLE_PROMPT_EN = """You format DIP API search results as a compact Markdown table.

## Rules
- Table: | No. | Title | Type | Description | Date | Actions |
- **Description**: Plain-language (max 10 words)
- **Actions**: In ONE cell: `[📄 PDF](url) [🤖 AI](ai:DOCTYPE:ID:DOCNR) [👤 Citizen](ci:DOCTYPE:ID:DOCNR)`
  - DOCTYPE = "Drucksachen", "Vorgänge", "Plenarprotokolle" or "Aktivitäten"
- Sort by date descending. Show ALL results.
- Start with 🏛️ heading and hit count.
- Translate all German titles/types to English.
- End with: <!-- FOLLOWUP: [{"label":"🔎 ...","prompt":"..."},{"label":"📊 ...","prompt":"..."}] -->
- Just table + one context sentence, no analysis."""


# Language output addons
_OUTPUT_DE = "\n\nAntworte auf Deutsch. Alle Texte, Tabellenüberschriften und Analysen auf Deutsch."

_OUTPUT_EN = """

## Language: English
- ALWAYS respond in English. Translate all German content from DIP API.
- Search queries: translate user keywords to German (e.g. "climate" -> "Klimaschutz").
- Keep document numbers unchanged (BT-Drs 21/4186).
- Keep link formats unchanged ([🤖 AI](ai:...), [👤 Citizens](ci:...)).
- Translate types: Kleine Anfrage->Minor Inquiry, Gesetzentwurf->Draft Bill, Antrag->Motion,
  Beschlussempfehlung->Committee Recommendation, Schriftliche Frage->Written Question.
- Follow-up actions in English.
- Use these English section headers instead of German ones:
  📋 Überblick -> 📋 Overview
  🎯 Kernpunkte -> 🎯 Key Points
  👥 Hauptakteure -> 👥 Key Actors
  💰 Finanzielle Aspekte -> 💰 Financial Aspects
  ⚡ Auswirkungen und nächste Schritte -> ⚡ Impact & Next Steps
  🔍 Was bedeutet das konkret? -> 🔍 What does this mean in practice?
  💡 Wer ist betroffen? -> 💡 Who is affected?
  📌 Was ändert sich? -> 📌 What changes?
  ⏳ Zeitlicher Rahmen -> ⏳ Timeline"""


# Lightweight translation prompt for search-only tables (English mode)
_TRANSLATE_TABLE_PROMPT = """Translate this German Bundestag search results table to English.

## Rules
- Translate ONLY the text content: titles, types, and descriptions
- Keep ALL markdown structure EXACTLY as-is (|, headers, separators)
- Keep ALL links EXACTLY as-is: [📄 PDF](...), [📄 DIP](...), [🤖 AI](...), [👤 Bürger:innen](...)
- Keep document numbers unchanged (e.g. 21/4186)
- Keep dates unchanged
- Keep row numbers unchanged
- Translate document types: Kleine Anfrage→Minor Inquiry, Große Anfrage→Major Inquiry,
  Gesetzentwurf→Draft Bill, Antrag→Motion, Beschlussempfehlung→Committee Recommendation,
  Schriftliche Frage→Written Question, Antwort→Answer, Unterrichtung→Report,
  Bericht→Report, Verordnung→Regulation, Entschließungsantrag→Resolution Motion
- Translate the heading (e.g. "## 🏛️ 10 Treffer" → "## 🏛️ 10 Results")
- Translate follow-up action labels and prompts in the FOLLOWUP comment to English
- Output ONLY the translated table, nothing else."""


# Dedicated Citizen Impact analysis prompt (used when user clicks "Citizen Impact" link)
_CITIZEN_IMPACT_PROMPT = """You are a citizen impact analyst for German Bundestag documents.
Analyze the document from a citizen's perspective, focusing on real-world impacts for everyday life.

IMPORTANT: The conversation includes complete JSON metadata from the German Bundestag API.
Use this metadata for document type, authors, responsible ministries, and procedural information.

## Instructions

1. **Document Classification**: Extract drucksachetyp, urheber, ressort, procedural stage from metadata.

2. **Named Persons**: ALWAYS extract specific named individuals from the document text —
   speakers, questioners, responding officials. Include full name, party affiliation, and role
   (e.g. "Parl. Staatssekretär", "Abgeordnete", "Vizepräsidentin"). NEVER say "nicht in Metadaten genannt"
   if names appear in the document text itself.

3. **Kleine/Große Anfragen & Antworten**: When analyzing "Antwort" documents:
   - ALWAYS extract the original requesting party from "urheber" metadata
   - Clearly state: "Antwort der [Authority] auf [Question Type] der [Requesting Party]"
   - Explain the political context of who asked and why it matters

3. **Direct Impact on Citizens**: How does this affect daily life (taxes, services, rights, obligations)?

4. **Who is Affected**: Identify specific groups (families, businesses, students, retirees, professions).

5. **Practical Changes**: Concrete changes citizens can expect in everyday experience.

6. **Timeline**: When do changes take effect? Transition periods?

7. **Citizen Actions Required**: What must citizens do? (apply, comply, take advantage of)

8. **Benefits and Challenges**: Balanced view of positives and concerns.

9. **Administrative Context**: Use vorgangsbezug/ressort to explain responsible authorities and next steps.

## Constraints
- **400 to 600 words**
- Written **entirely in German**
- Clear, accessible language — no complex legal jargon
- Focus on practical real-world implications
- Objective and balanced
- Integrate metadata naturally

## Output Format (German, Markdown)

### 🏛️ Bürger:innen-Auswirkungsanalyse: [Topic]

#### 📋 Dokumentenkontext
**Dokumenttyp:** *[drucksachetyp]*
**Urheber/Anfragende Partei:** **[Party from urheber — for Antworten: both responder AND original requester]**
**Zuständiges Ressort:** **[Ministry from ressort]**
**Verfahrensstand:** *[Current stage]*

#### 👥 Direkte Auswirkungen auf Bürger:innen
[How this affects daily life]

#### 🎯 Betroffene Gruppen
- **[Group 1]:** [Impact]
- **[Group 2]:** [Impact]

#### 🔄 Praktische Änderungen
[Concrete changes citizens will experience]

#### ⏱️ Zeitplan und Umsetzung
- **Wann:** *[Timeline]*
- **Nächste Schritte:** [What happens next]

#### ✅ Erforderliche Bürger:innen-Maßnahmen
1. [Action if any]

> **Wichtiger Hinweis:** [Key takeaway if applicable]

#### ⚖️ Vorteile und Herausforderungen
**Vorteile:**
- [Benefit]

**Mögliche Herausforderungen:**
- [Challenge]

#### 🏢 Zuständige Behörden und nächste Schritte
[Administrative context with responsible authorities]

End with:
<!-- FOLLOWUP: [{"label":"🔍 ...","prompt":"..."},{"label":"📊 ...","prompt":"..."}] -->"""


# ---------------------------------------------------------------------------
# Prompt composition functions
# ---------------------------------------------------------------------------

_SEARCH_TOOLS = frozenset({
    "search_vorgaenge", "search_drucksachen",
    "search_plenarprotokolle", "search_personen", "search_aktivitaeten",
})


def _is_search_only(tool_calls: list) -> bool:
    """True if all tool calls were search functions (no document loading)."""
    if not tool_calls:
        return False
    return all(tc["name"] in _SEARCH_TOOLS for tc in tool_calls)


_CITIZEN_IMPACT_MARKERS = frozenset({
    "bürgerperspektive", "bürger-auswirkung", "bürgerauswirkung",
    "citizen's perspective", "citizen impact of", "[citizen_impact]",
})

_SUMMARY_MARKERS = frozenset({
    "fasse die drucksache", "fasse den vorgang", "fasse das plenarprotokoll",
    "zusammenfassung von", "zusammenfassen",
    "summarize document", "summarize proceeding", "summarize plenary",
    "summary of",
})


def _is_citizen_impact(user_message: str) -> bool:
    """True if the user message is a citizen impact analysis request."""
    msg_lower = user_message.lower()
    return any(marker in msg_lower for marker in _CITIZEN_IMPACT_MARKERS)


def _is_summary_request(user_message: str) -> bool:
    """True if the user message is a document summary request (AI Summary link)."""
    msg_lower = user_message.lower()
    return any(marker in msg_lower for marker in _SUMMARY_MARKERS)


# Dedicated summary prompt — used when user clicks "AI Summary" on a search result
_SUMMARY_PROMPT = """You are an expert analyst of German parliamentary documents.
Provide clear, accurate summaries — journalistic in tone, neutral, entirely in German.

## Critical: Explain the SUBSTANCE, not just the metadata
- DO NOT output raw JSON. Output ONLY well-formatted Markdown.
- DO NOT just list metadata and procedural steps. Explain WHAT the document is actually about.
- For Gesetzentwürfe: Explain the PROBLEM the law addresses, WHY it is needed, and WHAT it changes.
  Use the "Problem und Ziel" / "A. Problem" section from the document text as your primary source.
- For Anfragen: Explain WHAT questions are asked and WHY they matter politically.
- For Antworten: Summarize the government's KEY POSITIONS and concrete answers.
- Write as a journalist would: Make the reader understand the real-world significance.
- Use vivid, concrete language. Instead of "betrifft den Bereich Strafrecht", write
  "erleichtert die Beschlagnahme von Vermögen aus Organisierter Kriminalität".

## Instructions
1. **JSON Metadata First**: Extract drucksachetyp, urheber, autoren_anzeige, ressort,
   vorgangsbezug, document numbers, dates from the context metadata.
2. **Document Content**: Read the FULL TEXT carefully. Extract the core argument, problem
   statement, proposed solution, and key provisions. This is the MOST IMPORTANT part.
3. **Key Entities**: Political parties (from urheber), named individuals, organizations, ministries.
4. **Kleine/Große Anfragen & Antworten**: Always name the requesting party from urheber.
   For "Antwort": identify BOTH responding authority AND original requester.
5. **Financial Aspects**: Budgets, proposed allocations, macroeconomic implications.

## Output Format (German, Markdown)

### [Document Classification] — [Main Topic]

**Dokumentart:** *[drucksachetyp]*
**Urheber:** **[Party/author from metadata]**
**Ressort:** **[Responsible ministry]**
**Datum:** *[Date]*

#### 📋 Überblick
[2-3 paragraphs in journalistic tone explaining:
- WHAT is the problem this document addresses? (use "Problem und Ziel" section if available)
- WHAT solution or action is proposed?
- WHY does this matter? What is the real-world significance?
Do NOT just repeat the title — explain the substance in accessible language.]

#### 🎯 Kernpunkte
- [Substantive key point — what concretely changes or is proposed]
- [Key point 2 — specific provisions, numbers, or mechanisms]
- [Key point 3 — political or legal significance]

#### 👥 Hauptakteure
- **[Named Person]** ([Party], [Role]): [What they said/did]
- **[Ministry/Institution]:** [Involvement]

#### 💰 Finanzielle Aspekte
[Financial info if relevant, or "Keine finanziellen Aspekte genannt."]

#### ⚡ Auswirkungen und nächste Schritte
[Implications, vorgangsbezug context, what happens next]

## Rules
- Cite document numbers (BT-Drs 21/4186) and dates
- Bold for key terms, names, numbers
- ALWAYS extract named individuals from the document TEXT, not only from metadata
- For Plenarprotokolle/Fragestunden: list ALL speakers with name, party, and role
- Journalistically neutral, formal German
- The Überblick section must explain the SUBSTANCE — never just list metadata
- 400-600 words

End with:
<!-- FOLLOWUP: [{"label":"🔍 ...","prompt":"..."},{"label":"📊 ...","prompt":"..."},{"label":"👤 ...","prompt":"..."}] -->
Include a follow-up for Citizen Impact analysis of this document."""


def _build_system_prompt(language: str = "de") -> str:
    """Full system prompt for non-streaming endpoint (all instructions combined)."""
    lang = _OUTPUT_EN if language == "en" else _OUTPUT_DE
    return _PHASE1_PROMPT + _ANALYSIS_PROMPT + _TABLE_FORMAT + _FOLLOWUP_PROMPT + lang


def _build_phase1_prompt(language: str = "de") -> str:
    """Compact prompt for Phase 1 (tool selection only — no formatting instructions)."""
    lang = _OUTPUT_EN if language == "en" else _OUTPUT_DE
    return _PHASE1_PROMPT + lang


def _build_phase2_prompt(language: str = "de", search_only: bool = False,
                        citizen_impact: bool = False, summary: bool = False) -> str:
    """Task-specific prompt for Phase 2 answer generation."""
    lang = _OUTPUT_EN if language == "en" else _OUTPUT_DE
    if search_only:
        return _SEARCH_TABLE_PROMPT_EN if language == "en" else _SEARCH_TABLE_PROMPT_DE
    if citizen_impact:
        return _CITIZEN_IMPACT_PROMPT + lang
    if summary:
        return _SUMMARY_PROMPT + lang
    return _PHASE1_PROMPT + _ANALYSIS_PROMPT + _TABLE_FORMAT + _FOLLOWUP_PROMPT + lang

CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=10000)
    history: list = Field(default_factory=list)
    language: str = Field(default="de", pattern=r"^(de|en)$")

    @field_validator("history")
    @classmethod
    def validate_history(cls, v):
        if len(v) > 50:
            v = v[-50:]
        return v


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list = []


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = _rl_time.time()
    window = _rate_limit_store[client_ip]
    # Purge old entries
    _rate_limit_store[client_ip] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_limit_store[client_ip].append(now)
    # Prevent unbounded growth: prune IPs with empty windows periodically
    if len(_rate_limit_store) > 1000:
        stale = [ip for ip, ts in _rate_limit_store.items() if not ts]
        for ip in stale:
            del _rate_limit_store[ip]
    return True


@app.post("/api/chat")
async def chat(request: ChatRequest, raw_request: Request):
    """Chat endpoint with OpenAI function calling backed by DIP API."""
    from openai import OpenAI
    from fastapi.responses import JSONResponse

    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

    openai_key = _get_openai_key()
    if not openai_key:
        return ChatResponse(reply="⚠️ OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=openai_key, timeout=120.0)

    messages = [{"role": "system", "content": _build_system_prompt(request.language)}]
    for msg in request.history[-20:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})

    tool_calls_log = []
    max_rounds = 3  # Reduced — system prompt instructs batching

    for _ in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                tools=OPENAI_TOOLS,
                max_completion_tokens=2048,
                parallel_tool_calls=True,
            )
        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            return ChatResponse(reply="⚠️ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" or choice.message.tool_calls:
            messages.append(choice.message)
            for tc in _unwrap_multi_tool_calls(choice.message.tool_calls):
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                logger.info(f"Calling tool: {fn_name}({fn_args})")

                result = execute_tool(fn_name, fn_args)
                logger.info(f"Tool {fn_name} returned {len(result):,} chars (~{_estimate_tokens(result):,} tokens)")
                tool_calls_log.append({"tool": fn_name, "args": fn_args})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            return ChatResponse(
                reply=choice.message.content or "",
                tool_calls=tool_calls_log,
            )

    return ChatResponse(
        reply="⚠️ Too many tool calls. Please try a more specific question.",
        tool_calls=tool_calls_log,
    )


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, raw_request: Request):
    """Streaming chat endpoint for real-time responses."""
    from openai import AsyncOpenAI
    from fastapi.responses import JSONResponse

    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        async def rate_limit_gen():
            yield "data: " + json.dumps({"error": "Rate limit exceeded. Try again later."}) + "\n\n"
        return StreamingResponse(rate_limit_gen(), media_type="text/event-stream")

    openai_key = _get_openai_key()
    if not openai_key:
        async def error_gen():
            yield "data: " + json.dumps({"error": "OpenAI API key not configured"}) + "\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    client = AsyncOpenAI(api_key=openai_key, timeout=120.0)

    messages = [{"role": "system", "content": _build_phase1_prompt(request.language)}]
    for msg in request.history[-20:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})

    max_rounds = 3  # Reduced from 5 — system prompt instructs batching
    tool_calls_made = []

    import time as _time

    # Friendly labels for each tool
    _tool_labels_de = {
        "search_vorgaenge": "Suche Vorgänge",
        "search_drucksachen": "Suche Drucksachen",
        "search_plenarprotokolle": "Suche Plenarprotokolle",
        "get_vorgang": "Lade Vorgang-Metadaten",
        "get_vorgang_details": "Lade Vorgang mit Volltext",
        "get_drucksache": "Lade Drucksache-Metadaten",
        "get_drucksache_text": "Lade Drucksache-Volltext",
        "get_plenarprotokoll_text": "Lade Plenarprotokoll-Volltext",
        "search_personen": "Suche Abgeordnete",
        "search_aktivitaeten": "Suche Aktivitäten",
    }
    _tool_labels_en = {
        "search_vorgaenge": "Search proceedings",
        "search_drucksachen": "Search documents",
        "search_plenarprotokolle": "Search plenary protocols",
        "get_vorgang": "Load proceeding metadata",
        "get_vorgang_details": "Load proceeding full text",
        "get_drucksache": "Load document metadata",
        "get_drucksache_text": "Load document full text",
        "get_plenarprotokoll_text": "Load plenary protocol text",
        "search_personen": "Search members",
        "search_aktivitaeten": "Search activities",
    }
    _tool_labels = _tool_labels_en if request.language == "en" else _tool_labels_de

    def _arg_hint(fn_args: dict) -> str:
        if "query" in fn_args:
            return f' „{fn_args["query"][:50]}"'
        for key in ("vorgang_id", "drucksache_id", "protokoll_id", "id"):
            if key in fn_args:
                return f" #{fn_args[key]}"
        return ""

    async def generate():
        nonlocal messages, tool_calls_made
        overall_t0 = _time.monotonic()
        collected_refs = []  # document references for action tiles

        # Emit full context for transparency
        sys_prompt = messages[0]["content"] if messages else ""
        yield "data: " + json.dumps({
            "phase": "context",
            "system_prompt_chars": len(sys_prompt),
            "system_prompt_preview": sys_prompt[:500] + ("..." if len(sys_prompt) > 500 else ""),
            "user_message": request.message,
            "history_count": len(request.history),
            "total_messages": len(messages),
        }) + "\n\n"

        # --- Phase 1: Tool resolution (1 round for speed, then stream answer) ---
        max_tool_rounds = 1
        for round_num in range(max_tool_rounds):
            if request.language == "en":
                model_label = "AI analyzing query..." if round_num == 0 else f"AI reviewing results (round {round_num + 1})..."
            else:
                model_label = "KI analysiert Anfrage..." if round_num == 0 else f"KI prüft Ergebnisse (Runde {round_num + 1})..."
            yield "data: " + json.dumps({
                "phase": "model_thinking",
                "round": round_num + 1,
                "label": model_label,
                "model": CHAT_MODEL,
                "max_completion_tokens": 2048,
                "tools_count": len(OPENAI_TOOLS),
                "parallel_tool_calls": True,
            }) + "\n\n"

            try:
                model_t0 = _time.monotonic()
                response = await client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    max_completion_tokens=2048,
                    parallel_tool_calls=True,
                )
                model_elapsed = _time.monotonic() - model_t0
            except Exception as e:
                logger.error(f"Phase 1 error: {e}", exc_info=True)
                yield "data: " + json.dumps({"error": "Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut."}) + "\n\n"
                return

            choice = response.choices[0]

            # Handle truncated responses (model ran out of tokens mid-tool-call)
            if choice.finish_reason == "length":
                logger.warning(f"[stream] Round {round_num+1} truncated (finish_reason=length)")
                yield "data: " + json.dumps({
                    "phase": "model_decided",
                    "round": round_num + 1,
                    "n_tools": 0,
                    "elapsed": round(model_elapsed, 1),
                    "label": "Ready to answer" if request.language == "en" else "Bereit für Antwort",
                }) + "\n\n"
                break

            has_tools = choice.finish_reason == "tool_calls" or choice.message.tool_calls

            if has_tools:
                raw_tool_calls = _unwrap_multi_tool_calls(choice.message.tool_calls)
                n_calls = len(raw_tool_calls)
                tool_names = [_tool_labels.get(tc.function.name, tc.function.name)
                              for tc in raw_tool_calls]
                if request.language == "en":
                    decided_label = f"Planning {n_calls} quer{'ies' if n_calls > 1 else 'y'}: {', '.join(tool_names)}"
                else:
                    decided_label = f"Plant {n_calls} Abfrage{'n' if n_calls > 1 else ''}: {', '.join(tool_names)}"
                yield "data: " + json.dumps({
                    "phase": "model_decided",
                    "round": round_num + 1,
                    "n_tools": n_calls,
                    "elapsed": round(model_elapsed, 1),
                    "label": decided_label,
                }) + "\n\n"

                messages.append(choice.message)

                tool_batch = []
                for tc in raw_tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        logger.warning(f"[stream] Skipping malformed tool args: {tc.function.arguments[:100]}")
                        continue
                    friendly = _tool_labels.get(fn_name, fn_name)
                    hint = _arg_hint(fn_args)
                    tool_batch.append((tc, fn_name, fn_args, friendly, hint))
                    logger.info(f"[stream] Queuing tool: {fn_name}({fn_args})")

                if not tool_batch:
                    break  # All tool calls had malformed args

                for tc, fn_name, fn_args, friendly, hint in tool_batch:
                    yield "data: " + json.dumps({
                        "phase": "tool_call",
                        "tool": fn_name,
                        "label": f"{friendly}{hint}",
                        "args": fn_args,
                    }) + "\n\n"

                async def _exec_timed(fn_name, fn_args, refs):
                    t0 = _time.monotonic()
                    result = await execute_tool_async(fn_name, fn_args, refs)
                    elapsed = _time.monotonic() - t0
                    return result, elapsed

                parallel_results = await asyncio.gather(
                    *[_exec_timed(fn_name, fn_args, collected_refs)
                      for _, fn_name, fn_args, _, _ in tool_batch]
                )

                for (tc, fn_name, fn_args, friendly, hint), (result, elapsed) in zip(tool_batch, parallel_results):
                    result_tokens = _estimate_tokens(result)
                    logger.info(f"[stream] Tool {fn_name} returned {len(result):,} chars (~{result_tokens:,} tokens) in {elapsed:.1f}s")

                    yield "data: " + json.dumps({
                        "phase": "tool_result",
                        "tool": fn_name,
                        "label": f"{friendly}{hint}",
                        "chars": len(result),
                        "elapsed": round(elapsed, 1),
                        "preview": result[:300] + ("..." if len(result) > 300 else ""),
                    }) + "\n\n"

                    tool_calls_made.append({"name": fn_name, "label": friendly, "elapsed": round(elapsed, 1)})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                # Continue loop — model may want more tools
            else:
                # No tools — model wants to answer
                phase1_content = choice.message.content or ""
                yield "data: " + json.dumps({
                    "phase": "model_decided",
                    "round": round_num + 1,
                    "n_tools": 0,
                    "elapsed": round(model_elapsed, 1),
                    "label": "Ready to answer" if request.language == "en" else "Bereit für Antwort",
                }) + "\n\n"

                if phase1_content:
                    # Extract dynamic follow-up actions from content
                    clean_content, followup = _extract_followup_actions(phase1_content)

                    # Compute context stats (same as Phase 2)
                    def _mc(m):
                        return (m.get("content", "") or "") if isinstance(m, dict) else (getattr(m, "content", "") or "")
                    def _mr(m):
                        return m.get("role", "") if isinstance(m, dict) else getattr(m, "role", "")
                    _p1_chars = sum(len(_mc(m)) for m in messages)
                    _p1_tokens = int(_p1_chars / CHARS_PER_TOKEN)
                    _p1_tool = sum(len(_mc(m)) for m in messages if _mr(m) == "tool")
                    _p1_detail = [{"role": _mr(m), "chars": len(_mc(m)), "preview": _mc(m)[:200] + ("..." if len(_mc(m)) > 200 else "")} for m in messages]

                    yield "data: " + json.dumps({
                        "phase": "answering",
                        "tools_used": [tc["name"] for tc in tool_calls_made],
                        "context_chars": _p1_chars,
                        "context_tokens_est": _p1_tokens,
                        "n_messages": len(messages),
                        "tool_data_chars": _p1_tool,
                        "model": CHAT_MODEL,
                        "messages_detail": _p1_detail,
                        "reuse_phase1": True,
                    }) + "\n\n"
                    chunk_size = 12
                    for i in range(0, len(clean_content), chunk_size):
                        yield "data: " + json.dumps({"content": clean_content[i:i+chunk_size]}) + "\n\n"
                        await asyncio.sleep(0.015)
                    total_elapsed = round(_time.monotonic() - overall_t0, 1)
                    actions = _build_action_tiles(collected_refs, request.language) + followup
                    yield "data: " + json.dumps({
                        "done": True,
                        "tools_used": [tc["name"] for tc in tool_calls_made],
                        "tool_details": tool_calls_made,
                        "total_elapsed": total_elapsed,
                        "actions": actions,
                    }) + "\n\n"
                    return
                break

        # --- Phase 2: Stream the final answer ---
        _search_only = _is_search_only(tool_calls_made)

        # FAST PATH: Build search table server-side — no Phase 2 OpenAI call needed
        if _search_only and collected_refs:
            _is_english = request.language == "en"
            yield "data: " + json.dumps({
                "phase": "answering",
                "tools_used": [t["name"] for t in tool_calls_made],
                "search_only": True,
                "server_formatted": True,
                "n_results": len(collected_refs),
                "model": "gpt-5-mini (titles)" if _is_english else "server-side (no AI)",
            }) + "\n\n"
            yield "data: " + json.dumps({"phase": "first_token", "ttft": 0.0}) + "\n\n"

            table_md = _build_search_table(collected_refs, request.language)

            # Translate document titles to English via lightweight LLM call
            if _is_english:
                table_md = await _translate_titles_to_english(table_md, client)

            clean_content, followup = _extract_followup_actions(table_md)

            # Stream in batches for smooth UI
            _chunk = 200
            for i in range(0, len(clean_content), _chunk):
                yield "data: " + json.dumps({"content": clean_content[i:i+_chunk]}) + "\n\n"
                await asyncio.sleep(0.01)

            total_elapsed = round(_time.monotonic() - overall_t0, 1)
            actions = _build_action_tiles(collected_refs, request.language) + followup
            yield "data: " + json.dumps({
                "done": True,
                "tools_used": [t["name"] for t in tool_calls_made],
                "tool_details": tool_calls_made,
                "total_elapsed": total_elapsed,
                "actions": actions,
            }) + "\n\n"
            return

        # STANDARD PATH: Use OpenAI Phase 2 for analysis/summary
        _citizen = _is_citizen_impact(request.message)
        _summary = not _citizen and _is_summary_request(request.message)
        _phase2_prompt = _build_phase2_prompt(
            request.language, search_only=False,
            citizen_impact=_citizen, summary=_summary,
        )
        if _citizen:
            logger.info("🏛️ Citizen Impact prompt activated")
        elif _summary:
            logger.info("📄 Summary prompt activated")

        # Launch web search in parallel for summary/citizen_impact requests
        _news_task = None
        if (_citizen or _summary) and ENABLE_WEB_SEARCH:
            # Extract document title from Phase 1 tool results (German title from DIP API)
            import re as _re_ws
            _doc_title = ""
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "tool":
                    tc = m.get("content", "")
                    # Try markdown format: **Titel:** <title>
                    _t_match = _re_ws.search(r'\*\*Titel:\*\*\s*(.{10,300})', tc)
                    if _t_match:
                        _doc_title = _t_match.group(1).split('\n')[0].strip()
                        break
                    # Try JSON format: "titel": "<title>"
                    _t_match = _re_ws.search(r'"titel"\s*:\s*"([^"]{10,300})"', tc)
                    if _t_match:
                        _doc_title = _t_match.group(1)
                        break
            if not _doc_title:
                # Fallback: extract from user message after colon
                _colon_idx = request.message.find(':')
                _doc_title = request.message[_colon_idx+1:].strip()[:200] if _colon_idx > 0 else request.message[:200]
            _news_task = asyncio.create_task(
                _search_news_coverage(_doc_title, "", request.language, client)
            )
            logger.info("📰 Web search launched for: %s", _doc_title[:80])
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "system":
                m["content"] = _phase2_prompt
                break
        # Compute context stats for the UI (messages may be dicts or pydantic objects)
        def _msg_content(m):
            if isinstance(m, dict):
                return m.get("content", "") or ""
            return getattr(m, "content", "") or ""
        def _msg_role(m):
            if isinstance(m, dict):
                return m.get("role", "")
            return getattr(m, "role", "")

        _ctx_chars = sum(len(_msg_content(m)) for m in messages)
        _ctx_tokens_est = int(_ctx_chars / CHARS_PER_TOKEN)
        # Dynamic Phase 2 token budget: scale down if context is huge
        _remaining = MODEL_CONTEXT_WINDOW - _ctx_tokens_est - SYSTEM_PROMPT_TOKENS
        _phase2_max_tokens = min(OPENAI_MAX_TOKENS, max(4096, _remaining))
        _n_msgs = len(messages)
        _tool_data_chars = sum(
            len(_msg_content(m))
            for m in messages if _msg_role(m) == "tool"
        )

        # Build per-message breakdown for full transparency
        _messages_detail = []
        for m in messages:
            role = _msg_role(m)
            content = _msg_content(m)
            _messages_detail.append({
                "role": role,
                "chars": len(content),
                "preview": content[:200] + ("..." if len(content) > 200 else ""),
            })

        yield "data: " + json.dumps({
            "phase": "answering",
            "tools_used": [t["name"] for t in tool_calls_made],
            "context_chars": _ctx_chars,
            "context_tokens_est": _ctx_tokens_est,
            "n_messages": _n_msgs,
            "tool_data_chars": _tool_data_chars,
            "model": CHAT_MODEL,
            "messages_detail": _messages_detail,
            "search_only": _search_only,
            "max_completion_tokens": _phase2_max_tokens,
        }) + "\n\n"

        try:
            _answer_t0 = _time.monotonic()
            stream = await client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages,
                max_completion_tokens=_phase2_max_tokens,
                stream=True,
            )
            full_content = ""
            _first_token = True
            _token_count = 0
            _last_progress = _time.monotonic()
            _batch_buf = ""
            _last_yield = _time.monotonic()
            _BATCH_CHARS = 200  # flush every ~200 chars (larger chunks for smoother UI)
            _BATCH_MS = 0.25   # or every 250ms

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_content += token
                    _batch_buf += token
                    _token_count += 1
                    if _first_token:
                        _first_token = False
                        _ttft = round(_time.monotonic() - _answer_t0, 1)
                        yield "data: " + json.dumps({
                            "phase": "first_token",
                            "ttft": _ttft,
                        }) + "\n\n"
                    # Periodic progress every 3s
                    _now = _time.monotonic()
                    if _now - _last_progress >= 3.0:
                        _last_progress = _now
                        yield "data: " + json.dumps({
                            "phase": "gen_progress",
                            "tokens": _token_count,
                            "chars": len(full_content),
                            "elapsed": round(_now - _answer_t0, 1),
                        }) + "\n\n"
                    # Batch content: flush every ~60 chars or 120ms
                    if len(_batch_buf) >= _BATCH_CHARS or (_now - _last_yield) >= _BATCH_MS:
                        yield "data: " + json.dumps({"content": _batch_buf}) + "\n\n"
                        _batch_buf = ""
                        _last_yield = _now
            # Flush remaining buffer
            if _batch_buf:
                yield "data: " + json.dumps({"content": _batch_buf}) + "\n\n"

            # Await web search results and append as news section
            if _news_task:
                try:
                    news_md = await _news_task
                    if news_md:
                        yield "data: " + json.dumps({"content": news_md}) + "\n\n"
                        logger.info("📰 News section appended (%d chars)", len(news_md))
                except Exception as e:
                    logger.warning("📰 Web search task failed: %s", e)

            total_elapsed = round(_time.monotonic() - overall_t0, 1)

            # Extract dynamic follow-up actions from streamed content
            _, followup = _extract_followup_actions(full_content)
            actions = _build_action_tiles(collected_refs, request.language) + followup

            yield "data: " + json.dumps({
                "done": True,
                "tools_used": [t["name"] for t in tool_calls_made],
                "tool_details": tool_calls_made,
                "total_elapsed": total_elapsed,
                "actions": actions,
            }) + "\n\n"
        except Exception as e:
            logger.error(f"Phase 2 error: {e}", exc_info=True)
            yield "data: " + json.dumps({"error": "Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut."}) + "\n\n"

    import re as _re

    def _extract_followup_actions(content: str) -> tuple[str, list]:
        """Extract <!-- FOLLOWUP: [...] --> block from content. Returns (clean_content, actions)."""
        match = _re.search(r'<!--\s*FOLLOWUP:\s*(\[.*?\])\s*-->', content, _re.DOTALL)
        if not match:
            return content, []
        try:
            actions = json.loads(match.group(1))
            if not isinstance(actions, list):
                return content, []
            # Validate structure
            valid = [a for a in actions if isinstance(a, dict) and "label" in a and "prompt" in a]
            clean = content[:match.start()].rstrip()
            return clean, valid[:6]
        except (json.JSONDecodeError, Exception):
            return content, []

    def _build_action_tiles(collected_refs, language: str = "de"):
        actions = []
        if language == "en":
            _action_map = {
                "Vorgänge": ("📋 Summarize", "Summarize proceeding {nr} (ID:{id})"),
                "Drucksachen": ("📄 Summarize", "Summarize document {nr} (ID:{id})"),
                "Plenarprotokolle": ("🎙️ Summarize", "Summarize plenary transcript (ID:{id})"),
                "Aktivitäten": ("📊 Details", "Show details for activity {nr} (ID:{id})"),
            }
        else:
            _action_map = {
                "Vorgänge": ("📋 Zusammenfassen", "Fasse den Vorgang {nr} zusammen (ID:{id})"),
                "Drucksachen": ("📄 Zusammenfassen", "Fasse die Drucksache {nr} zusammen (ID:{id})"),
                "Plenarprotokolle": ("🎙️ Zusammenfassen", "Fasse das Plenarprotokoll zusammen (ID:{id})"),
                "Aktivitäten": ("📊 Details", "Zeige Details zur Aktivität {nr} (ID:{id})"),
            }
        seen_ids = set()
        for ref in collected_refs[:8]:
            if ref["id"] in seen_ids:
                continue
            seen_ids.add(ref["id"])
            tpl = _action_map.get(ref["type"])
            if tpl:
                label_tpl, prompt_tpl = tpl
                nr_display = ref["nr"] or f'ID:{ref["id"]}'
                actions.append({
                    "label": f'{label_tpl}: {nr_display}',
                    "prompt": prompt_tpl.format(**ref),
                })
            if len(actions) >= 6:
                break
        return actions

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx/proxy buffering
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bundestag-dip-chat-mcp"}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the chat UI."""
    html_path = static_dir / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
