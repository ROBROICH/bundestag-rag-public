"""
MCP Server exposing Bundestag DIP API as tools.
Uses FastMCP for decorator-based tool registration.
"""
import os
import sys
import logging
from typing import Optional
from pathlib import Path

from fastmcp import FastMCP

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import BUNDESTAG_API_KEY, BUNDESTAG_API_BASE_URL

logger = logging.getLogger(__name__)

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

mcp = FastMCP(
    "Bundestag DIP API",
    instructions="Search and retrieve documents from the German Bundestag parliamentary documentation system (DIP API). "
                 "Access Vorgänge (procedures), Drucksachen (printed papers), Plenarprotokolle (plenary protocols), "
                 "Personen (members), and Aktivitäten (activities).",
)

# Lazy-initialized shared HTTP client
_http_client = None


def _get_client():
    """Get or create a shared httpx client for DIP API calls."""
    global _http_client
    if _http_client is None:
        import httpx
        api_key = os.getenv("DIP_API_KEY") or os.getenv("BUNDESTAG_API_KEY") or BUNDESTAG_API_KEY
        _http_client = httpx.Client(
            base_url=BUNDESTAG_API_BASE_URL,
            headers={
                "Authorization": f"ApiKey {api_key}",
                "Accept": "application/json",
                "User-Agent": "Bundestag-MCP-Server/1.0",
            },
            timeout=30.0,
        )
    return _http_client


def _api_request(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make a request to the DIP API and return JSON."""
    client = _get_client()
    params = {k: v for k, v in (params or {}).items() if v is not None}
    resp = client.get(f"/{endpoint.lstrip('/')}", params=params)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def search_vorgaenge(
    query: Optional[str] = None,
    wahlperiode: Optional[int] = None,
    urheber: Optional[str] = None,
    vorgangstyp: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search Bundestag Vorgänge (parliamentary procedures).

    Args:
        query: Search keywords (German text works best). Can be empty when filtering by urheber.
        wahlperiode: Parliamentary term number (e.g. 21 for current term)
        urheber: Filter by originator Fraktion/institution. Use formal names like
            'Fraktion der SPD', 'Fraktion der AfD', 'Fraktion der CDU/CSU',
            'Fraktion BÜNDNIS 90/DIE GRÜNEN', 'Fraktion DIE LINKE', 'Bundesregierung'.
            Short forms like 'SPD' or 'AfD' are auto-resolved.
        vorgangstyp: Filter by procedure type, e.g. 'Kleine Anfrage', 'Gesetzgebung', 'Antrag'
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        limit: Max results to return (default 10)
    """
    import json
    params = {
        "f.titel": query,
        "f.wahlperiode": wahlperiode,
        "f.urheber": _resolve_urheber(urheber),
        "f.vorgangstyp": vorgangstyp,
        "f.datum.start": date_from,
        "f.datum.end": date_to,
        "rows": min(limit, 50),
    }
    result = _api_request("vorgang", params)
    docs = result.get("documents", [])
    summary_lines = [f"Found {result.get('numFound', 0)} Vorgänge. Showing {len(docs)}:\n"]
    for doc in docs:
        summary_lines.append(
            f"- [{doc.get('id')}] {doc.get('titel', 'N/A')} "
            f"(Type: {doc.get('vorgangstyp', 'N/A')}, "
            f"Date: {doc.get('datum', doc.get('aktualisiert', 'N/A'))}, "
            f"WP: {doc.get('wahlperiode', 'N/A')})"
        )
    return "\n".join(summary_lines)


@mcp.tool()
def search_drucksachen(
    query: Optional[str] = None,
    wahlperiode: Optional[int] = None,
    urheber: Optional[str] = None,
    drucksachetyp: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search Bundestag Drucksachen (printed papers / official documents).

    Args:
        query: Search keywords. Can be empty when filtering by urheber.
        wahlperiode: Parliamentary term number (e.g. 21)
        urheber: Filter by originator Fraktion/institution (see search_vorgaenge for values)
        drucksachetyp: Filter by document type, e.g. 'Kleine Anfrage', 'Gesetzentwurf',
            'Antrag', 'Antwort', 'Schriftliche Fragen', 'Beschlussempfehlung und Bericht'
        date_from: Start date filter (YYYY-MM-DD)
        date_to: End date filter (YYYY-MM-DD)
        limit: Max results (default 10)
    """
    import json
    params = {
        "f.titel": query,
        "f.wahlperiode": wahlperiode,
        "f.urheber": _resolve_urheber(urheber),
        "f.drucksachetyp": drucksachetyp,
        "f.datum.start": date_from,
        "f.datum.end": date_to,
        "rows": min(limit, 50),
    }
    result = _api_request("drucksache", params)
    docs = result.get("documents", [])
    summary_lines = [f"Found {result.get('numFound', 0)} Drucksachen. Showing {len(docs)}:\n"]
    for doc in docs:
        summary_lines.append(
            f"- [{doc.get('dokumentnummer', doc.get('id'))}] {doc.get('titel', 'N/A')} "
            f"(Type: {doc.get('drucksachetyp', 'N/A')}, Date: {doc.get('datum', 'N/A')})"
        )
    return "\n".join(summary_lines)


@mcp.tool()
def search_plenarprotokolle(
    query: str,
    wahlperiode: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search Bundestag Plenarprotokolle (plenary session protocols/transcripts).

    Args:
        query: Search keywords
        wahlperiode: Filter by parliamentary term
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        limit: Max results (default 10)
    """
    import json
    params = {
        "f.titel": query,
        "f.wahlperiode": wahlperiode,
        "f.datum.start": date_from,
        "f.datum.end": date_to,
        "rows": min(limit, 50),
    }
    result = _api_request("plenarprotokoll", params)
    docs = result.get("documents", [])
    summary_lines = [f"Found {result.get('numFound', 0)} Plenarprotokolle. Showing {len(docs)}:\n"]
    for doc in docs:
        summary_lines.append(
            f"- [{doc.get('dokumentnummer', doc.get('id'))}] {doc.get('titel', 'N/A')} "
            f"(Date: {doc.get('datum', 'N/A')}, WP: {doc.get('wahlperiode', 'N/A')})"
        )
    return "\n".join(summary_lines)


@mcp.tool()
def get_vorgang(vorgang_id: int) -> str:
    """Get details of a specific Bundestag Vorgang (procedure) by ID.

    Args:
        vorgang_id: The numeric ID of the Vorgang
    """
    import json
    doc = _api_request(f"vorgang/{vorgang_id}")
    return json.dumps(doc, ensure_ascii=False, indent=2)


@mcp.tool()
def get_drucksache(drucksache_id: int) -> str:
    """Get details of a specific Drucksache (printed paper) by ID.

    Args:
        drucksache_id: The numeric ID of the Drucksache
    """
    import json
    doc = _api_request(f"drucksache/{drucksache_id}")
    return json.dumps(doc, ensure_ascii=False, indent=2)


@mcp.tool()
def get_drucksache_text(drucksache_id: int) -> str:
    """Get the full text content of a Drucksache (printed paper).

    Args:
        drucksache_id: The numeric ID of the Drucksache
    """
    import json
    doc = _api_request(f"drucksache-text/{drucksache_id}")
    return json.dumps(doc, ensure_ascii=False, indent=2)


@mcp.tool()
def get_plenarprotokoll_text(protokoll_id: int) -> str:
    """Get the full text of a Plenarprotokoll (plenary session transcript).

    Args:
        protokoll_id: The numeric ID of the Plenarprotokoll
    """
    import json
    doc = _api_request(f"plenarprotokoll-text/{protokoll_id}")
    return json.dumps(doc, ensure_ascii=False, indent=2)


@mcp.tool()
def search_personen(
    query: Optional[str] = None,
    wahlperiode: Optional[int] = None,
    limit: int = 10,
) -> str:
    """Search for Bundestag members (Personen / Abgeordnete).

    Args:
        query: Name or keyword to search for
        wahlperiode: Filter by parliamentary term
        limit: Max results (default 10)
    """
    import json
    params = {
        "f.vorname+nachname": query,
        "f.wahlperiode": wahlperiode,
        "rows": min(limit, 50),
    }
    result = _api_request("person", params)
    docs = result.get("documents", [])
    summary_lines = [f"Found {result.get('numFound', 0)} Personen. Showing {len(docs)}:\n"]
    for doc in docs:
        name = f"{doc.get('vorname', '')} {doc.get('nachname', '')}".strip()
        summary_lines.append(f"- [{doc.get('id')}] {name}")
    return "\n".join(summary_lines)


@mcp.tool()
def search_aktivitaeten(
    query: Optional[str] = None,
    wahlperiode: Optional[int] = None,
    urheber: Optional[str] = None,
    aktivitaetsart: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Search Bundestag Aktivitäten (parliamentary activities like speeches, votes).

    Args:
        query: Search keywords. Can be empty when filtering by urheber.
        wahlperiode: Filter by parliamentary term
        urheber: Filter by originator Fraktion/institution (see search_vorgaenge for values)
        aktivitaetsart: Filter by activity type
        limit: Max results (default 10)
    """
    import json
    params = {
        "f.titel": query,
        "f.wahlperiode": wahlperiode,
        "f.urheber": _resolve_urheber(urheber),
        "f.aktivitaetsart": aktivitaetsart,
        "rows": min(limit, 50),
    }
    result = _api_request("aktivitaet", params)
    docs = result.get("documents", [])
    summary_lines = [f"Found {result.get('numFound', 0)} Aktivitäten. Showing {len(docs)}:\n"]
    for doc in docs:
        summary_lines.append(
            f"- [{doc.get('id')}] {doc.get('titel', 'N/A')} "
            f"(Date: {doc.get('datum', 'N/A')})"
        )
    return "\n".join(summary_lines)
