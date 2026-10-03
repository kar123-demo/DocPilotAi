# AI Docs Generator

FastAPI service + React frontend that converts a public GitHub repository into a software-project report,
both as a downloadable DOCX and as a browsable web report. It uses safe shallow cloning, static code
analysis, Groq text generation, PlantUML structural and behavioral diagrams, and
`python-docx`.

## Features

- Public HTTPS GitHub URLs only; shallow clone and no source-code execution.
- Detects Python, Java, JavaScript, TypeScript, C, and C++ source files.
- Uses Python's real `ast` parser and conservative symbol extraction for other languages.
- Uses Groq for report prose, UML diagrams, and repository chat. Static analysis and source-derived fallback
  content remain available when `GROQ_API_KEY` is not configured.
- The report contains a title page plus seven requested sections: Abstract, Introduction, Literature Survey,
  Structural and Behavioral Diagrams, Technology Stack, Limitations, and Conclusion.
- Report prose is limited to five LLM requests, sent sequentially with a short pause between requests to reduce
  rate-limit bursts. Configure separate Groq models for quality prose, fast prose, UML generation, and source-code
  chat with `GROQ_MODEL_QUALITY`, `GROQ_MODEL_FAST`, `GROQ_MODEL_UML`, and `GROQ_MODEL_CHAT`. Optional per-section
  overrides are `GROQ_MODEL_ABSTRACT`, `GROQ_MODEL_INTRODUCTION`, `GROQ_MODEL_LITERATURE_SURVEY`,
  `GROQ_MODEL_LIMITATIONS`, and `GROQ_MODEL_CONCLUSION`.
- Uses one additional grounded LLM request to generate six project-specific PlantUML UML diagrams: structural
  class, component, and package diagrams; behavioral use-case, activity, and sequence diagrams. Each receives
  retrieved source evidence from the hybrid index. Source-derived fallback diagrams are used if the LLM is
  unavailable. Kroki renders each diagram as a PNG for the report and browser; PlantUML source is also included
  in the architecture artifact. Diagram source is sent to the public Kroki renderer; use a trusted/self-hosted
  renderer if repository-derived diagram text must remain within your environment.
- Automatic repository sync before each report and chat request, indexed code chunks, hybrid retrieval,
  repository-aware assistant chat, and generated README/API/architecture markdown artifacts.
- A React UI presents the requested report sections and a source-code assistant grounded in the analyzed repository.

## System architecture

```text
Git repository -> Tree-sitter parsing and code chunks -> persistent hybrid index
                                             -> grounded Groq LLM generation
                                             -> DOCX, README, API reference, architecture guide
Developer -> React UI -> sync, report generation, and indexed code chat
```

## Backend pipeline (matches the architecture diagram)

The backend is arranged as four explicit stages. It uses an **on-disk persistent hybrid index** rather than claiming to
use Pinecone/PostgreSQL; replacing that storage with an external vector database can be a later deployment change.

1. **Source code analysis and storage** — `app/main.py` safely clones/synchronizes a repository. `app/parser.py`
   uses Tree-sitter to extract syntax-aware chunks, symbols, signatures, docstrings, imports, and parser diagnostics.
2. **Core RAG engine** — `app/rag.py` persists project metadata, Tree-sitter symbols/chunks, TF-IDF vectors, and lexical term data in
   `temp/indexes/<project-id>.sqlite3`. Tree-sitter creates syntax-aware chunks and extracts symbol metadata;
   `retrieve()` combines lexical, TF-IDF similarity, file-name, syntax, and symbol matches.
   `build_grounded_context()` formats only the retrieved evidence that is supplied to the LLM.
3. **Grounded Groq LLM and documentation artifacts** — `app/llm.py` uses the configured quality and fast Groq models
   for report prose and the UML model for six diagrams. `app/artifacts.py` writes README, API reference, and
   architecture markdown; `app/docx_builder.py` writes the DOCX.
4. **Repository source chatbot** — `POST /api/projects/{project_id}/chat` synchronizes the project when available,
   calls `retrieve()` for source-code context, then sends matching source chunks to `generate_grounded_answer()`
   using the separately configured `GROQ_MODEL_CHAT`. It carries the latest four successful chat turns into
   follow-up questions, includes repository metadata and README/setup docs, and cites retrieved file/line ranges.
   Source clones are in `temp/repositories/`; local SQLite retrieval databases are in `temp/indexes/`.
   Existing JSON indexes are upgraded to SQLite automatically when their project chat is opened.

The report-generation prompt is intentionally constructed as:

```text
SYSTEM: Use only verified facts and retrieved source context. Do not invent project claims.
USER: VERIFIED FACTS + RETRIEVED SOURCE CONTEXT + TASK FOR THIS REPORT SECTION
```

This means the LLM does not receive the entire repository or make unsupported claims; it receives a bounded context
selected by the hybrid retriever for the requested section.

## Run

### 1. Configure Groq models

Create a Groq API key in the Groq console, then set it and the four model roles in the same PowerShell terminal
used to start the backend. Replace model IDs with IDs enabled for your Groq account if needed:

```powershell
$env:GROQ_API_KEY = "<your Groq API key>"
$env:GROQ_MODEL_QUALITY = "openai/gpt-oss-120b"
$env:GROQ_MODEL_FAST = "openai/gpt-oss-20b"
$env:GROQ_MODEL_UML = "openai/gpt-oss-20b"
$env:GROQ_MODEL_CHAT = "openai/gpt-oss-20b"
```

Keep the API key in the backend environment; never put it in frontend code. The source chatbot uses indexed
repository code: cloned files are stored under `temp/repositories/<project-id>/`, and tree-sitter metadata,
semantic chunks, README/setup docs, and hybrid-search data are stored in
`temp/indexes/<project-id>.sqlite3`. Chat replies list the source filenames and lines used as evidence.

Set `PLANTUML_RENDERER_URL` to a trusted Kroki-compatible `/plantuml/png` endpoint to avoid sending
repository-derived diagram text to the public renderer.

### 2. Backend (FastAPI)

```powershell
cd "C:\Users\KARTHIK\Downloads\AI-Docs-Generator-fixed\project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is now on `http://127.0.0.1:8000`. API docs remain at `http://127.0.0.1:8000/docs`.

### 3. Frontend (React + Vite)

In a second terminal:

```powershell
cd "C:\Users\KARTHIK\Downloads\AI-Docs-Generator-fixed\project\frontend"
npm install
npm run dev
```

Open `http://127.0.0.1:5173/`. The dev server proxies every `/api/*` call to the FastAPI backend on port
8000 (see `frontend/vite.config.js`), so no extra configuration or CORS setup is needed.

### Production build (single process)

```powershell
cd frontend
npm run build
```

This produces `frontend/dist`. When that folder exists, the FastAPI server serves it directly at
`http://127.0.0.1:8000/` — you don't need the Vite dev server running.

```json
{
  "repository_url": "https://github.com/tiangolo/fastapi"
}
```

`GET /api/status` reports whether Groq is configured and the model IDs assigned to each role. If no Groq API key
is configured, the service still builds a report using static analysis and source-derived fallback content.

## API

- `GET /health` — health check
- `GET /api/status` — confirms whether Groq is configured and returns the configured model IDs (never the API key)
- `POST /api/sync` — refresh a managed shallow clone and return updated static-analysis counts
- `POST /api/analyze` — clone, analyze, narrate, generate six UML diagrams, and build a report. Returns the
  requested report narrative, six PlantUML sources and PNG URLs, an
  abbreviation glossary, and a structured reference list, in addition to the DOCX download link.
- `GET /api/reports/{report_id}` — download the DOCX report
- `GET /api/diagrams/{report_id}/{class|component|package|use-case|activity|sequence}.png` — download a rendered diagram image
- `GET /api/artifacts/{report_id}/{filename}` — download a generated markdown artifact
- `POST /api/projects/{project_id}/chat` — ask follow-up questions about the indexed repository source

## Production notes

For production, run cloning and report building in a worker queue, use an authenticated GitHub App for
private repositories, persist job status in a database, add antivirus scanning, or host your own Kroki-compatible
PlantUML renderer.
