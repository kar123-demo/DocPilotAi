from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

IGNORED_DIRECTORIES = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "coverage", ".next", "vendor", "target", ".idea", ".vscode",
}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
}
MAX_FILE_BYTES = 512_000
MAX_FILES = 1_500


def validate_github_url(repo_url: str) -> str:
    """Allow only public GitHub repository URLs; prevents arbitrary git transports."""
    parsed = urlparse(repo_url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or len(parts) < 2:
        raise ValueError("Provide a public URL such as https://github.com/owner/repository")
    owner, repository = parts[0], parts[1].removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise ValueError("The repository URL contains unsupported characters.")
    return f"https://github.com/{owner}/{repository}.git"


def job_id_for(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def is_source_file(path: Path) -> bool:
    return path.suffix.lower() in LANGUAGES and path.stat().st_size <= MAX_FILE_BYTES


def is_ignored(path: Path, root: Path) -> bool:
    try:
        return any(part in IGNORED_DIRECTORIES for part in path.relative_to(root).parts)
    except ValueError:
        return True


def read_readme_excerpt(repository_root: Path, max_chars: int = 3000) -> str:
    """Best-effort excerpt of the analyzed repository's own README, used only to ground the
    generated narrative in what this specific project actually says about itself."""
    if not repository_root.exists():
        return ""
    for name in ("README.md", "README.rst", "README.txt", "readme.md", "Readme.md"):
        candidate = repository_root / name
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace")[:max_chars]
            except OSError:
                return ""
    return ""


CORE_ABBREVIATIONS: dict[str, str] = {
    "AST": "Abstract Syntax Tree - a structural, tree-form representation of parsed source code.",
    "API": "Application Programming Interface - the contract this service exposes at /api/*.",
    "LLM": "Large Language Model - the configured Groq model used to turn verified repository facts into narrative text.",
    "RAG": "Retrieval-Augmented Generation - grounding chat answers in retrieved source-code chunks.",
    "UML": "Unified Modeling Language - a standard notation for modeling software structure and behavior.",
    "DOCX": "Office Open XML Word document format, the report's download format.",
    "JSON": "JavaScript Object Notation - the request/response payload format for the API.",
    "HTTP": "Hypertext Transfer Protocol - the transport used between the browser and FastAPI.",
    "URL": "Uniform Resource Locator - identifies the public GitHub repository to analyze.",
    "PNG": "Portable Network Graphics - the rendered architecture diagram image format.",
}
LANGUAGE_ABBREVIATIONS: dict[str, str] = {
    "Python": "PY - a high-level, dynamically typed general-purpose language, parsed here with the standard ast module.",
    "JavaScript": "JS - the scripting language of the web platform, parsed here with conservative regular expressions.",
    "TypeScript": "TS - a statically typed superset of JavaScript.",
    "Java": "A class-based, statically typed, compiled object-oriented language.",
    "C": "A low-level, procedural systems programming language.",
    "C++": "CPP - a compiled, multi-paradigm extension of C with object-oriented features.",
}


def build_abbreviations(languages: list[str]) -> list[dict[str, str]]:
    """Return a de-duplicated, sorted abbreviation glossary relevant to this report."""
    entries = dict(CORE_ABBREVIATIONS)
    for language in languages:
        if language in LANGUAGE_ABBREVIATIONS:
            entries[language.upper()] = LANGUAGE_ABBREVIATIONS[language]
    return [{"term": term, "definition": definition} for term, definition in sorted(entries.items())]


LANGUAGE_DOCS: dict[str, tuple[str, str]] = {
    "Python": ("Python language documentation", "https://docs.python.org/3/"),
    "JavaScript": ("MDN JavaScript reference", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    "TypeScript": ("TypeScript handbook", "https://www.typescriptlang.org/docs/"),
    "Java": ("Java SE documentation", "https://docs.oracle.com/en/java/"),
    "C": ("C language reference (cppreference)", "https://en.cppreference.com/w/c"),
    "C++": ("C++ language reference (cppreference)", "https://en.cppreference.com/w/cpp"),
}


def build_references(repository_url: str, analysis: dict[str, Any], repository_root: Path | None = None) -> list[dict[str, str]]:
    """Structured, project-specific reference list: the repository itself, its own README
    and license when present, and official docs for its primary detected language(s)."""
    homepage = repository_url.removesuffix(".git")
    references: list[dict[str, str]] = [
        {
            "title": "Analyzed source repository",
            "url": homepage,
            "description": "The public GitHub repository this report was generated from.",
        }
    ]
    # README/LICENSE are not source-code files, so look at the actual clone on disk rather
    # than the parsed-source-file list. "HEAD" in the blob URL lets GitHub resolve the
    # correct default branch (main/master/etc.) without us needing to know it.
    if repository_root is not None and repository_root.exists():
        root_entries = {entry.name.lower(): entry.name for entry in repository_root.iterdir() if entry.is_file()}
        for candidates, title, description in (
            (("readme.md", "readme", "readme.rst", "readme.txt"), "Repository README",
             "The project's own README, as published in this repository."),
            (("license", "license.md", "license.txt", "copying"), "Repository license",
             "The license under which this repository is distributed."),
        ):
            match = next((root_entries[name] for name in candidates if name in root_entries), None)
            if match:
                references.append({"title": title, "url": f"{homepage}/blob/HEAD/{match}", "description": description})
    for language in analysis["summary"].get("languages", []):
        if language in LANGUAGE_DOCS and len(references) < 6:
            title, url = LANGUAGE_DOCS[language]
            references.append({"title": title, "url": url, "description": f"Official reference for {language}, the primary language used in this repository."})
    if len(references) < 3:
        references.append({
            "title": "GitHub repository structure",
            "url": f"{homepage}/tree/HEAD",
            "description": "Browse the analyzed repository's file tree directly on GitHub.",
        })
    return references
