from __future__ import annotations

from pathlib import Path
import os
import re
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from git import GitCommandError, InvalidGitRepositoryError, Repo
from pydantic import BaseModel, Field

from .docx_builder import build_report
from .llm import chat_model, configured_groq_models, generate_narrative_sections, generate_uml_diagrams, llm_provider, llm_ready, parse_bullets, parse_labeled_paragraphs, report_model_assignments, resolve_model
from .uml import render_plantuml_png
from .parser import analyze_repository
from .rag import build_index, build_project_overview, load_index, retrieve
from .artifacts import write_artifacts
from .sections import build_technology_stack
from .utils import build_abbreviations, build_references, job_id_for, read_readme_excerpt, validate_github_url

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)
SYNC_ROOT = ROOT / "temp" / "repositories"
SYNC_ROOT.mkdir(parents=True, exist_ok=True)
INDEX_ROOT = ROOT / "temp" / "indexes"
INDEX_ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="AI Docs Generator", version="1.0.0")
# The React app lives in /frontend. During development run it separately with
# `npm run dev` (it proxies /api to this server on port 8000, see vite.config.js).
# For a single-process deployment, `npm run build` produces frontend/dist, which
# this server then serves directly at "/".
FRONTEND_DIST = ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(examples=["https://github.com/tiangolo/fastapi"])
    project_name: str | None = None
    team_members: str | None = Field(default=None, description="Optional, one per line or comma-separated.")
    guide_name: str | None = None
    college_name: str | None = None


class AnalyzeResponse(BaseModel):
    report_id: str
    project_name: str
    repository_url: str
    summary: dict
    title_page: dict
    sections: dict
    llm_used: bool
    llm_status: str | None = None
    diagrams_llm_used: bool
    diagrams_llm_status: str | None = None
    diagram_render_status: str | None = None
    diagrams: dict[str, list[dict[str, str]]]
    structural_uml: str
    behavioral_uml: str
    abbreviations: list[dict[str, str]]
    references: list[dict[str, str]]
    code_samples: list[dict]
    download_url: str
    artifacts: dict[str, str]


class SyncRequest(BaseModel):
    repository_url: str = Field(examples=["https://github.com/tiangolo/fastapi"])


class SyncResponse(BaseModel):
    repository_url: str
    synced_path: str
    summary: dict
    status: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


class ChatResponse(BaseModel):
    answer: str
    llm_used: bool
    llm_status: str | None = None
    sources: list[dict]
    sync_status: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def frontend() -> FileResponse:
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run 'npm install && npm run build' in /frontend, "
            "or run 'npm run dev' there for local development (it proxies to this API).",
        )
    return FileResponse(index)


@app.get("/api/status")
async def status() -> dict[str, object]:
    """Only confirms configuration; secrets are never returned to a browser."""
    ready, model, error = await llm_ready()
    groq_configured = bool(os.environ.get("GROQ_API_KEY"))
    return {
        "provider": llm_provider(),
        "model": model,
        "report_models": report_model_assignments(model),
        "models": configured_groq_models(),
        "llm_configured": ready,
        "llm_status": error,
        "groq_configured": groq_configured,
    }


def sync_repository(repository_url: str) -> tuple[Path, dict, str]:
    """Create or refresh a managed shallow clone for each public repository."""
    clone_url = validate_github_url(repository_url)
    destination = SYNC_ROOT / job_id_for(clone_url)
    if not destination.exists():
        Repo.clone_from(clone_url, destination, depth=1, single_branch=True, no_tags=True)
        action = "Repository cloned"
    else:
        try:
            repo = Repo(destination)
            repo.remotes.origin.fetch(depth=1)
            repo.git.reset("--hard", "FETCH_HEAD")
            action = "Repository synchronized"
        except (InvalidGitRepositoryError, GitCommandError) as error:
            raise GitCommandError("sync", 1, str(error)) from error
    analysis = analyze_repository(destination)
    build_index(INDEX_ROOT / f"{job_id_for(clone_url)}.sqlite3", repository_url, analysis)
    return destination, analysis, action


@app.post("/api/sync", response_model=SyncResponse)
async def sync(payload: SyncRequest) -> SyncResponse:
    try:
        repository_path, analysis, action = sync_repository(payload.repository_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except GitCommandError as error:
        raise HTTPException(status_code=400, detail="Unable to synchronize this public repository. Confirm its URL and accessibility.") from error
    return SyncResponse(repository_url=payload.repository_url, synced_path=str(repository_path.relative_to(ROOT)), summary=analysis["summary"], status=action)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        clone_url = validate_github_url(payload.repository_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    report_id = job_id_for(clone_url)
    output_path = OUTPUTS / f"{report_id}.docx"
    project_name = payload.project_name or clone_url.rstrip("/").split("/")[-1].removesuffix(".git")
    try:
        repository_path, analysis, _ = sync_repository(payload.repository_url)
        # Core RAG engine: the synchronized parser output is already persisted as
        # a hybrid vector/lexical index by sync_repository().
        project_index = load_index(INDEX_ROOT / f"{report_id}.sqlite3")
        readme_excerpt = read_readme_excerpt(repository_path)
        model = resolve_model()
        narrative, llm_used, llm_status = await generate_narrative_sections(
            project_name, payload.repository_url, analysis,
            model,
            readme_excerpt, index=project_index)
        diagrams, diagrams_llm_used, diagrams_llm_status = await generate_uml_diagrams(
            project_name, payload.repository_url, analysis, model, index=project_index)
        rendered_diagrams: dict[str, Path | None] = {}
        diagram_render_errors: list[str] = []
        for diagram in diagrams["structural"] + diagrams["behavioral"]:
            diagram_id = diagram["id"]
            image_path = OUTPUTS / f"{report_id}.{diagram_id}.png"
            rendered, render_error = await render_plantuml_png(diagram["code"], image_path)
            rendered_diagrams[diagram_id] = image_path if rendered else None
            if render_error:
                diagram_render_errors.append(f"{diagram_id}: {render_error}")
            diagram["image_path"] = str(rendered_diagrams[diagram_id] or "")
            diagram["image_url"] = (
                f"/api/diagrams/{report_id}/{diagram_id}.png"
                if rendered_diagrams[diagram_id] else ""
            )
        structural_diagrams = diagrams["structural"]
        behavioral_diagrams = diagrams["behavioral"]
        structural_uml = structural_diagrams[0]["code"]
        behavioral_uml = behavioral_diagrams[0]["code"]
        diagram_path = rendered_diagrams[structural_diagrams[0]["id"]]
        behavior_diagram_path = rendered_diagrams[behavioral_diagrams[0]["id"]]
        abbreviations = build_abbreviations(analysis["summary"]["languages"])
        references = build_references(payload.repository_url, analysis, repository_path)
        code_samples = [
            {"file": chunk["file"], "language": chunk["language"], "start_line": chunk["start_line"],
             "end_line": chunk["end_line"], "content": chunk["content"][:2400]}
            for chunk in analysis.get("chunks", [])[:6]
        ]
        artifact_paths = write_artifacts(
            OUTPUTS / report_id, project_name, payload.repository_url, analysis, diagrams
        )

        team_members = [name.strip() for name in re.split(r"[,\n]", payload.team_members or "") if name.strip()]
        title_page = {
            "project_name": project_name, "team_members": team_members,
            "guide_name": payload.guide_name or "Not specified",
            "college_name": payload.college_name or "Not specified",
            "repository_url": payload.repository_url,
        }
        sections: dict = {
            "abstract": narrative["abstract"],
            "introduction": parse_labeled_paragraphs(narrative["introduction"]),
            "literature_survey": narrative["literature_survey"],
            "technology_stack": build_technology_stack(analysis),
            "limitations": parse_bullets(narrative["limitations"]),
            "conclusion": narrative["conclusion"],
            "diagrams": diagrams,
        }
        build_report(output_path, project_name, payload.repository_url, narrative, structural_uml,
                      diagram_path, behavioral_uml, behavior_diagram_path,
                      title_page=title_page, sections=sections)
        for diagram in diagrams["structural"] + diagrams["behavioral"]:
            diagram.pop("image_path", None)
    except GitCommandError as error:
        raise HTTPException(status_code=400, detail="Unable to clone the public repository. Confirm its URL and accessibility.") from error
    artifact_urls = {name: f"/api/artifacts/{report_id}/{path.name}" for name, path in artifact_paths.items()}
    return AnalyzeResponse(
        report_id=report_id, project_name=project_name, repository_url=payload.repository_url,
        summary=analysis["summary"], title_page=title_page, sections=sections,
        llm_used=llm_used, llm_status=llm_status,
        diagrams_llm_used=diagrams_llm_used, diagrams_llm_status=diagrams_llm_status,
        diagram_render_status="; ".join(diagram_render_errors[:3]) if diagram_render_errors else None,
        diagrams=diagrams,
        structural_uml=structural_uml, behavioral_uml=behavioral_uml,
        abbreviations=abbreviations, references=references, code_samples=code_samples,
        download_url=f"/api/reports/{report_id}", artifacts=artifact_urls)


@app.get("/api/diagrams/{report_id}/{kind}")
async def download_diagram(report_id: str, kind: str) -> FileResponse:
    diagram_ids = {"class", "component", "package", "use-case", "activity", "sequence"}
    if not kind.endswith(".png") or kind[:-4] not in diagram_ids:
        raise HTTPException(status_code=404, detail="Diagram not found.")
    path = OUTPUTS / f"{report_id}.{kind[:-4]}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generate a report first.")
    return FileResponse(path, media_type="image/png")


@app.get("/api/reports/{report_id}")
async def download_report(report_id: str) -> FileResponse:
    path = OUTPUTS / f"{report_id}.docx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found. Generate it first.")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename="ai-docs-report.docx")


@app.get("/api/artifacts/{report_id}/{filename}")
async def download_artifact(report_id: str, filename: str) -> FileResponse:
    allowed = {"README.generated.md", "API_REFERENCE.md", "ARCHITECTURE.md"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = OUTPUTS / report_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Generate a report first.")
    return FileResponse(path, media_type="text/markdown", filename=filename)


@app.post("/api/projects/{project_id}/chat", response_model=ChatResponse)
async def chat(project_id: str, payload: ChatRequest) -> ChatResponse:
    index_path = INDEX_ROOT / f"{project_id}.sqlite3"
    if not index_path.exists():
        legacy_index_path = INDEX_ROOT / f"{project_id}.json"
        if legacy_index_path.exists():
            legacy_index = load_index(legacy_index_path)
            build_index(index_path, legacy_index["repository_url"], legacy_index)
        else:
            raise HTTPException(status_code=404, detail="Project index not found. Generate a report for the repository first.")
    # Refresh source context when possible; otherwise answer from the last indexed snapshot.
    index = load_index(index_path)
    repository_url = index["repository_url"]
    try:
        _, _, sync_status = sync_repository(repository_url)
        index = load_index(index_path)
    except GitCommandError:
        sync_status = "Repository refresh failed; using the last indexed snapshot."
    recent_user_context = " ".join(
        turn.content for turn in payload.history if turn.role == "user"
    )
    retrieval_query = f"{recent_user_context} {payload.question}".strip()
    chunks = retrieve(index, retrieval_query)
    from .llm import generate_grounded_answer
    answer, llm_used, llm_status = await generate_grounded_answer(
        payload.question,
        chunks,
        chat_model(),
        history=[turn.model_dump() for turn in payload.history],
        project_overview=build_project_overview(index),
    )
    sources = [{"file": chunk["file"], "lines": f"{chunk['start_line']}-{chunk['end_line']}"} for chunk in chunks]
    return ChatResponse(answer=answer, llm_used=llm_used, llm_status=llm_status, sources=sources, sync_status=sync_status)
