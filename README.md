# 🏛️ Bundestag AI Lens — Chat with Your Parliament

**An open-source AI application that makes German parliamentary documents accessible, searchable, and understandable for everyone.**

> **Note:** This project is for **educational and research purposes**. Please respect the [Bundestag DIP API terms of service](https://dip.bundestag.de/über-dip/hilfe/api). The code was developed with GenAI support — not intended for production use without review.

[![Live Demo](https://img.shields.io/badge/🔗_Live_Demo-Azure_Container_Apps-blue)](https://bundestag-mcp-chat.victoriouswater-1ba7ee2d.westeurope.azurecontainerapps.io/)

> ⏳ **Cold start:** The demo runs on Azure Container Apps with **scale-to-zero** enabled to minimize costs. The first request after inactivity may take 30–60 seconds while the container starts up.

---

## 💡 What This Does

Citizens, journalists, and researchers can **ask questions in plain language** about German parliamentary activity and receive:

- **AI-powered summaries** of 50+ page legal documents — explained like a journalist would
- **Citizen impact analysis** — what does this law mean for everyday people?
- **External media coverage** — AI-curated news links from major German outlets (optional, via OpenAI web search)
- **Structured search results** across Vorgänge (procedures), Drucksachen (documents), and Plenarprotokolle (transcripts)
- **Bilingual support** — German and English interface with LLM-based title translation
- **Full transparency** — see which tools the AI calls, what data it fetches, and how long each step takes

---

## 👥 Who Benefits

| Audience | Value |
|----------|-------|
| 🧑‍🤝‍🧑 **Citizens** | Understand complex legislation without legal expertise. Direct access to government decisions. |
| 📰 **Journalists** | Quickly find and summarize parliamentary activity across legislative periods. |
| 🎓 **Researchers** | Search structured parliamentary data with filters for party, document type, and date ranges. |
| 🏛️ **Government** | Demonstrate transparent, digital-first citizen engagement. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (SPA)                         │
│  Vanilla JS · SSE Streaming · Reasoning Panel · i18n    │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /api/chat/stream
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Python)                     │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Phase 1:    │  │ Tool         │  │ Phase 2:       │  │
│  │ LLM decides │─▶│ Dispatcher   │─▶│ LLM generates  │  │
│  │ which tools │  │ (10 tools)   │  │ answer         │  │
│  └─────────────┘  └──────┬───────┘  └───────┬────────┘  │
│                          │                  │            │
│  ┌───────────────────────▼──────────────────▼────────┐   │
│  │ Security: Rate Limit · Input Validation · CSP     │   │
│  │           Security Headers · CORS · HSTS (opt)    │   │
│  └───────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────────┐ ┌───────────┐ ┌───────────────────────┐
│ OpenAI GPT-5     │ │ OpenAI    │ │ Bundestag DIP API     │
│ mini (400K ctx)  │ │ Web Search│ │ search.dip.bundestag  │
│ Function calling │ │ (optional)│ │ .de/api/v1            │
└──────────────────┘ └───────────┘ └───────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single-file HTML UI** | Zero build tools, instant reload, no npm/webpack complexity |
| **SSE streaming** | Real-time token-by-token display with reasoning transparency |
| **Server-side table formatting** | Search results bypass the LLM entirely → faster, cheaper |
| **2-phase LLM approach** | Phase 1 (compact) picks tools; Phase 2 (task-specific) generates answer |
| **MCP + REST dual interface** | Same tools exposed as both OpenAI functions and MCP protocol |
| **OpenAI Web Search** | Optional news coverage via Responses API — runs parallel to Phase 2, zero added latency |

---

## 🔄 Data Flow

```
User types: "Welche Klimaschutzgesetze wurden 2026 verabschiedet?"
  │
  ▼
1. POST /api/chat/stream { message, history, language }
  │
  ▼
2. Phase 1 LLM (GPT-5 mini, compact prompt)
   → Decides: call search_vorgaenge(query="Klimaschutz", vorgangstyp="Gesetzgebung", date_from="2026-01-01")
  │
  ▼
3. Tool Dispatcher executes async DIP API calls
   → GET /vorgang?f.suche=Klimaschutz&f.vorgangstyp=Gesetzgebung&f.datum.start=2026-01-01
   → Results cached (SHA-256 key, 1h TTL, 256 entries)
  │
  ▼
4. Results formatted as Markdown table (search-only fast path)
   → No Phase 2 LLM call needed for pure searches
   → Each row has: [📄 DIP] [🤖 AI Summary] [👤 Citizen Impact] links
  │
  ▼
5. SSE events streamed to browser:
   → "model_thinking" → "tool_call" → "tool_result" → "content" → "done"
   → Reasoning panel shows each step with live timers
```

**When user clicks "🤖 AI Summary":**
```
6. New chat message: "Fasse den Vorgang 332067 zusammen (ID:332067)"
  │
  ▼
7. Phase 1 → calls get_vorgang_details(332067) + fetches Drucksache/Plenarprotokoll text
  │
  ▼
8. Phase 2 (Summary prompt) → Journalistic explanation of the law's substance:
   problem it solves, real-world significance, key actors, financial impact
   ║
   ║ (parallel)  Web Search → OpenAI Responses API with domain-filtered
   ║              news search → appends "📰 External Media Coverage" section
   ▼
9. Complete response with AI summary + optional news links
```

---

## 🛡️ Security

| Layer | Implementation |
|-------|---------------|
| **Rate Limiting** | 30 requests/minute per IP (in-memory, sliding window) |
| **Input Validation** | Message: max 10,000 chars · History: max 50 messages · Language: `de`\|`en` only |
| **Security Headers** | `X-Frame-Options: DENY` · `X-Content-Type-Options: nosniff` · `Referrer-Policy` · `Permissions-Policy` |
| **CSP** | `default-src 'self'` · `frame-ancestors 'none'` · `img-src 'self' data: https:` |
| **HSTS** | Opt-in via `ENABLE_HSTS=true` (recommended for production) |
| **XSS Prevention** | No inline `onclick` handlers — delegated event listeners with `data-*` attributes · URL scheme validation blocks `javascript:`/`data:` |
| **CORS** | Configurable origins (no wildcard) · Defaults to localhost |
| **Error Sanitization** | Internal errors never exposed to client — generic messages only |
| **XSRF Protection** | Enabled in Streamlit config |
| **Docker** | Non-root `appuser` · Minimal base image (`python:3.11-slim`) |
| **Azure Secrets** | Managed identity for ACR · `@secure()` Bicep parameters · No admin credentials |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [OpenAI API key](https://platform.openai.com/api-keys) (GPT-5 mini access)
- [Bundestag DIP API key](https://dip.bundestag.de/über-dip/hilfe/api) (free registration)

### Local Development (Chat App)
```powershell
# 1. Clone and setup
git clone https://github.com/ROBROICH/bundestag-rag-public.git
cd bundestag-rag-public

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-mcp.txt

# 3. Configure environment
cp env.template .env
# Edit .env with your API keys

# 4. Start the Chat App
python -m uvicorn src.chat.app:app --host 127.0.0.1 --port 8000 --reload
```

**Access at**: [http://localhost:8000](http://localhost:8000)

### Docker
```bash
docker build -f deployment/docker/Dockerfile.mcp -t bundestag-chat .
docker run -p 8000:8000 --env-file .env bundestag-chat
```

### Azure Container Apps
```powershell
.\deployment\azure\deploy-container-apps.ps1 `
    -ResourceGroup "rg-bundestag" `
    -Location "westeurope"
```
See [Azure Deployment Docs](deployment/docs/) for full guide.

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key with GPT-5 mini access |
| `BUNDESTAG_API_KEY` | ✅ | [DIP API key](https://dip.bundestag.de/über-dip/hilfe/api) (free) |
| `ALLOWED_ORIGINS` | ❌ | CORS origins (default: `localhost:8000`) |
| `ENABLE_HSTS` | ❌ | Enable Strict-Transport-Security (default: `false`) |
| `ENABLE_WEB_SEARCH` | ❌ | Enable news coverage via OpenAI web search in summaries (default: `false`) |
| `MCP_HOST` | ❌ | Bind address (default: `127.0.0.1`) |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |

---

## 📂 Project Structure

```
bundestag-rag-api/
├── src/
│   ├── chat/
│   │   ├── app.py              # FastAPI backend — endpoints, tools, prompts, security
│   │   └── static/
│   │       └── index.html      # Single-file chat UI (vanilla JS, SSE streaming)
│   ├── mcp/
│   │   └── server.py           # MCP server (10 tools via FastMCP SSE transport)
│   └── web/
│       └── openai_config.py    # Model configuration (GPT-5 mini, token limits)
├── config/
│   └── settings.py             # API URLs, timeouts, cache settings
├── deployment/
│   ├── docker/                 # Dockerfile, Dockerfile.mcp, Dockerfile.optimized
│   ├── azure/                  # Bicep template + deploy script for Container Apps
│   └── local/                  # docker-compose.yml for local dev
├── main.py                     # Entry point (chat/mcp/streamlit modes)
├── requirements.txt            # Full dependencies (pinned versions)
├── requirements-mcp.txt        # Minimal production dependencies
└── env.template                # Environment variable template
```

---

## 🛠️ API Tools

The LLM has access to **10 tools** that query the official Bundestag DIP API:

| Tool | Description |
|------|-------------|
| `search_vorgaenge` | Search parliamentary procedures (filter by party, type, date, legislative period) |
| `search_drucksachen` | Search official printed documents |
| `search_plenarprotokolle` | Search plenary session transcripts |
| `get_vorgang` | Get procedure metadata by ID |
| `get_vorgang_details` | Get full procedure with linked Drucksache text |
| `get_drucksache` | Get document metadata |
| `get_drucksache_text` | Get full document text (up to 250K chars) |
| `get_plenarprotokoll_text` | Get full plenary transcript text |
| `search_personen` | Search Bundestag members by name |
| `search_aktivitaeten` | Search parliamentary activities (speeches, votes, motions) |

These same tools are exposed via **MCP protocol** at `/mcp` for integration with other LLM clients.

---

## 🎯 UI Features

| Feature | Description |
|---------|-------------|
| 🌍 **Language Toggle** | German / English with LLM-based table translation |
| 🧠 **Reasoning Panel** | Real-time display of tool calls, timing, and intermediate results |
| 📊 **Search Tables** | Server-formatted Markdown tables with DIP links, PDF links, AI Summary & Citizen Impact actions |
| 🗺️ **Guided Search** | Topic cards → Party filter → Document type → Auto-generated query |
| 📅 **Wahlperiode Slider** | Filter by legislative period (WP 1–21, 1949–2026+) |
| 💬 **Streaming Responses** | Token-by-token display with live progress indicators |
| 📎 **Action Tiles** | Follow-up buttons: 📄 DIP / 🤖 AI Summary / 👤 Citizen Impact |
| 📰 **Media Coverage** | Optional news links from curated German outlets appended to AI summaries |

---

## 🔗 Resources

- [Bundestag DIP API Documentation](https://dip.bundestag.de/über-dip/hilfe/api)
- [DIP API Terms of Service](https://dip.bundestag.de/über-dip/nutzungsbedingungen)
- [Live Demo](https://bundestag-mcp-chat.victoriouswater-1ba7ee2d.westeurope.azurecontainerapps.io/)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

> **Note:** This project is for **educational and research purposes**. Please respect the [Bundestag DIP API terms of service](https://dip.bundestag.de/über-dip/nutzungsbedingungen).

---

For deployment issues, see the [Azure Deployment Documentation](deployment/docs/deploy-streamlit-app-documentation.md) troubleshooting section.