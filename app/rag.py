from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _terms(value: str) -> list[str]:
    """Tokenize prose plus source identifiers (snake_case, kebab-case, CamelCase)."""
    raw_terms = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,}", value.lower())
    expanded: list[str] = []
    for term in raw_terms:
        expanded.append(term)
        expanded.extend(part for part in re.split(r"[_-]+", term) if len(part) > 1)
    return expanded


def _idf(document_frequency: Counter[str], total: int, term: str) -> float:
    return math.log((total + 1) / (document_frequency[term] + 1)) + 1.0


def _normalise(vector: dict[str, float]) -> dict[str, float]:
    magnitude = math.sqrt(sum(weight * weight for weight in vector.values())) or 1.0
    return {term: weight / magnitude for term, weight in vector.items()}


def build_index(index_path: Path, repository_url: str, analysis: dict[str, Any]) -> dict[str, Any]:
    """Persist project metadata, parsed symbols, and hybrid retrieval chunks in SQLite."""
    raw_chunks = []
    document_frequency: Counter[str] = Counter()
    file_symbols: dict[str, list[dict[str, Any]]] = {}
    for symbol in analysis["symbols"]:
        file_symbols.setdefault(symbol["file"], []).append(symbol)
    for chunk in analysis["chunks"]:
        semantic = chunk.get("semantic_metadata", {})
        symbol_context = " ".join(
            f"{symbol['name']} {symbol.get('signature', '')} {symbol.get('docstring', '')}"
            for symbol in file_symbols.get(chunk["file"], [])
        )
        terms = Counter(_terms(
            f"{chunk['file']} {chunk['language']} {chunk['content']} {symbol_context} "
            f"{' '.join(semantic.get('symbols_defined', []))} "
            f"{' '.join(semantic.get('node_types', []))} {' '.join(semantic.get('context_path', []))}"
        ))
        document_frequency.update(terms.keys())
        raw_chunks.append((chunk, terms))
    total = len(raw_chunks) or 1
    corpus = []
    for chunk, terms in raw_chunks:
        length = max(sum(terms.values()), 1)
        vector = _normalise({term: (count / length) * _idf(document_frequency, total, term) for term, count in terms.items()})
        corpus.append({**chunk, "terms": dict(terms), "vector": vector})
    payload = {
        "repository_url": repository_url,
        "summary": analysis["summary"],
        "files": analysis["files"],
        "symbols": analysis["symbols"],
        "chunks": corpus,
        "document_frequency": dict(document_frequency),
        "indexed_at": datetime.now(UTC).isoformat(),
        "index_type": "tree-sitter semantic chunks + hybrid TF-IDF lexical and symbol metadata",
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(index_path)) as connection, connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS project (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                repository_url TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                files_json TEXT NOT NULL,
                document_frequency_json TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                index_type TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                symbol_json TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS symbols_name_idx ON symbols(name)")
        connection.execute("CREATE INDEX IF NOT EXISTS symbols_file_idx ON symbols(file)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                file TEXT NOT NULL,
                language TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                content TEXT NOT NULL,
                terms_json TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                semantic_json TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS chunks_file_idx ON chunks(file)")
        connection.execute("BEGIN")
        connection.execute("DELETE FROM project")
        connection.execute("DELETE FROM symbols")
        connection.execute("DELETE FROM chunks")
        connection.execute(
            "INSERT INTO project VALUES (1, ?, ?, ?, ?, ?, ?)",
            (
                payload["repository_url"],
                json.dumps(payload["summary"]),
                json.dumps(payload["files"]),
                json.dumps(payload["document_frequency"]),
                payload["indexed_at"],
                payload["index_type"],
            ),
        )
        connection.executemany(
            "INSERT INTO symbols (name, kind, file, line, symbol_json) VALUES (?, ?, ?, ?, ?)",
            [
                (symbol["name"], symbol["type"], symbol["file"], symbol["line"], json.dumps(symbol))
                for symbol in payload["symbols"]
            ],
        )
        connection.executemany(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    chunk["id"],
                    chunk["file"],
                    chunk["language"],
                    chunk["start_line"],
                    chunk["end_line"],
                    chunk["content"],
                    json.dumps(chunk["terms"]),
                    json.dumps(chunk["vector"]),
                    json.dumps(chunk.get("semantic_metadata", {})),
                )
                for chunk in corpus
            ],
        )
    return payload


def load_index(index_path: Path) -> dict[str, Any]:
    if index_path.suffix.lower() == ".json":
        return json.loads(index_path.read_text(encoding="utf-8"))
    with closing(sqlite3.connect(index_path)) as connection:
        project = connection.execute(
            "SELECT repository_url, summary_json, files_json, document_frequency_json, indexed_at, index_type "
            "FROM project WHERE id = 1"
        ).fetchone()
        if project is None:
            raise ValueError(f"Project index database '{index_path}' has no project metadata.")
        symbols = [
            json.loads(row[0])
            for row in connection.execute("SELECT symbol_json FROM symbols ORDER BY id")
        ]
        chunks = [
            {
                "id": row[0],
                "file": row[1],
                "language": row[2],
                "start_line": row[3],
                "end_line": row[4],
                "content": row[5],
                "terms": json.loads(row[6]),
                "vector": json.loads(row[7]),
                "semantic_metadata": json.loads(row[8]),
            }
            for row in connection.execute(
                "SELECT id, file, language, start_line, end_line, content, terms_json, vector_json, semantic_json "
                "FROM chunks ORDER BY rowid"
            )
        ]
    return {
        "repository_url": project[0],
        "summary": json.loads(project[1]),
        "files": json.loads(project[2]),
        "document_frequency": json.loads(project[3]),
        "indexed_at": project[4],
        "index_type": project[5],
        "symbols": symbols,
        "chunks": chunks,
    }


def retrieve(index: dict[str, Any], question: str, limit: int = 5) -> list[dict[str, Any]]:
    query_terms = Counter(_terms(question))
    if not query_terms:
        return []
    total = len(index["chunks"]) or 1
    document_frequency = Counter(index.get("document_frequency", {}))
    query_vector = _normalise({term: count * _idf(document_frequency, total, term) for term, count in query_terms.items()})
    symbol_names = {symbol["name"].lower() for symbol in index.get("symbols", [])}
    symbols_by_file: dict[str, list[dict[str, Any]]] = {}
    for symbol in index.get("symbols", []):
        symbols_by_file.setdefault(symbol["file"], []).append(symbol)
    walkthrough_intent = bool(re.search(r"\b(steps?|workflow|walkthrough|how|run|start|build)\b", question.lower()))
    scored = []
    for chunk in index["chunks"]:
        terms = chunk["terms"]
        length = max(sum(terms.values()), 1)
        lexical = sum((terms.get(term, 0) / length) * _idf(document_frequency, total, term) * count for term, count in query_terms.items())
        vector_similarity = sum(query_vector.get(term, 0.0) * weight for term, weight in chunk.get("vector", {}).items())
        semantic = chunk.get("semantic_metadata", {})
        metadata = sum(0.35 for term in query_terms if term in chunk["file"].lower())
        metadata += sum(0.2 for term in query_terms if term in symbol_names and term in chunk["content"].lower())
        metadata += sum(
            0.25 for term in query_terms
            if any(term in symbol["name"].lower() or term in symbol.get("signature", "").lower()
                   or term in symbol.get("docstring", "").lower()
                   for symbol in symbols_by_file.get(chunk["file"], []))
        )
        metadata += sum(
            0.15 for term in query_terms
            if any(term in symbol.lower() for symbol in semantic.get("symbols_defined", []))
        )
        documentation_boost = 0.3 if walkthrough_intent and chunk.get("language") in {
            "Markdown", "reStructuredText", "Text", "JSON", "TOML", "XML", "Gradle", "Kotlin"
        } else 0.0
        score = (0.4 * lexical) + (0.4 * vector_similarity) + (0.2 * metadata) + documentation_boost
        if score > 0:
            scored.append((score, chunk))
    excluded = {"terms", "vector"}
    return [{key: value for key, value in chunk.items() if key not in excluded}
            for _, chunk in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def build_grounded_context(index: dict[str, Any], query: str, limit: int = 4, max_chars: int = 2400) -> str:
    """Format hybrid-retrieved chunks as the exact evidence sent to the LLM.

    This is the explicit bridge between the persistent local vector/lexical index
    and grounded generation. It deliberately excludes unrelated repository files.
    """
    chunks = retrieve(index, query, limit=limit)
    if not chunks:
        return "No relevant source chunks were retrieved for this section."
    blocks: list[str] = []
    used = 0
    for chunk in chunks:
        block = (
            f"FILE: {chunk['file']} (lines {chunk['start_line']}-{chunk['end_line']})\n"
            f"LANGUAGE: {chunk['language']}\n{chunk['content'].strip()}"
        )
        if used + len(block) > max_chars:
            block = block[:max(0, max_chars - used)]
        if block:
            blocks.append(block)
            used += len(block)
        if used >= max_chars:
            break
    return "\n\n--- RETRIEVED SOURCE EVIDENCE ---\n".join(blocks)


def build_project_overview(index: dict[str, Any], max_files: int = 24) -> str:
    """Return compact repository facts that orient chat without describing this tool."""
    summary = index.get("summary", {})
    files = index.get("files", [])
    symbols = index.get("symbols", [])
    key_symbols = ", ".join(
        f"{symbol['name']} ({symbol['file']}:{symbol['line']})"
        for symbol in symbols[:24]
    ) or "No named classes/functions were detected."
    file_list = ", ".join(file["path"] for file in files[:max_files]) or "No source files were indexed."
    return (
        f"Repository: {index.get('repository_url', 'unknown')}\n"
        f"Languages: {', '.join(summary.get('languages', [])) or 'not detected'}\n"
        f"Indexed source files: {summary.get('files', len(files))}\n"
        f"Files: {file_list}\n"
        f"Detected classes/functions: {key_symbols}"
    )
