from __future__ import annotations

from pathlib import Path
from typing import Any


def write_artifacts(
    output_dir: Path,
    project_name: str,
    repository_url: str,
    analysis: dict[str, Any],
    diagrams: dict[str, list[dict[str, str]]],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    readme = output_dir / "README.generated.md"
    api_reference = output_dir / "API_REFERENCE.md"
    architecture = output_dir / "ARCHITECTURE.md"
    summary = analysis["summary"]
    readme.write_text(
        f"# {project_name}\n\nGenerated repository documentation for {repository_url}.\n\n"
        f"- Source files: {summary['files']}\n- Languages: {', '.join(summary['languages'])}\n"
        f"- Classes: {summary['classes']}\n- Functions: {summary['functions']}\n", encoding="utf-8")
    functions = [item for item in analysis["symbols"] if item["type"] == "function"]
    api_reference.write_text("# API Reference\n\n" + "\n".join(
        f"- `{item['name']}({', '.join(item.get('parameters', []))})` - `{item['file']}:{item['line']}`"
        for item in functions[:150]), encoding="utf-8")
    architecture_content = [
        f"# Architecture Guide: {project_name}\n",
        "\n## System Architecture\n",
        "\n```mermaid\n",
        "flowchart LR\n",
        "  repo[GitHub repository] --> clone[Managed shallow clone]\n",
        "  clone --> parse[Tree-sitter and static analysis]\n",
        "  parse --> chunks[Symbols and source chunks]\n",
        "  parse --> index[PostgreSQL and pgvector hybrid index]\n",
        "  chunks --> index\n",
        "  question[Report or chat request] --> retrieve[Hybrid retrieval]\n",
        "  index --> retrieve\n",
        "  retrieve --> llm[Grounded Groq generation]\n",
        "  parse --> artifacts[DOCX, README, API reference, architecture]\n",
        "  llm --> artifacts\n",
        "  retrieve --> chat[Repository chat with source citations]\n",
        "```\n",
        "\nWith DATABASE_URL configured, PostgreSQL stores repository metadata, syntax-aware chunks, lexical terms, "
        "and fixed-size hashed TF-IDF vectors in pgvector for approximate-nearest-neighbor retrieval. Repository "
        "sync refreshes the managed clone and rebuilds the index; it does not push or auto-commit changes to Git. "
        "Without DATABASE_URL, the development setup retains its local SQLite index.\n",
    ]
    for category, entries in (("Structural UML", diagrams["structural"]), ("Behavioral UML", diagrams["behavioral"])):
        architecture_content.append(f"\n## {category}\n")
        for diagram in entries:
            architecture_content.extend(
                [f"\n### {diagram['title']}\n", f"\n```plantuml\n{diagram['code'].strip()}\n```\n"]
            )
    architecture.write_text("".join(architecture_content), encoding="utf-8")
    return {"readme": readme, "api_reference": api_reference, "architecture": architecture}
