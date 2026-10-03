from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tree_sitter_language_pack import ProcessConfig, process as parse_with_tree_sitter

from .utils import LANGUAGES, MAX_FILE_BYTES, MAX_FILES, is_ignored, is_source_file


def _python_symbols(source: str, file_path: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"type": "function", "name": node.name,
                            "parameters": [argument.arg for argument in node.args.args],
                            "line": node.lineno, "file": file_path,
                            "docstring": ast.get_docstring(node) or ""})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"type": "class", "name": node.name,
                            "bases": [ast.unparse(base) for base in node.bases],
                            "line": node.lineno, "file": file_path,
                            "docstring": ast.get_docstring(node) or ""})
    return symbols


def _python_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


_IMPORT_PATTERNS = {
    "JavaScript": [r"(?:import[^'\"]*from\s+|require\()\s*['\"]([^'\"]+)['\"]"],
    "TypeScript": [r"(?:import[^'\"]*from\s+|require\()\s*['\"]([^'\"]+)['\"]"],
    "Java": [r"import\s+(?:static\s+)?([\w.]+)\s*;"],
    "C": [r'#include\s+"([^"]+)"'],
    "C++": [r'#include\s+"([^"]+)"'],
}


def _generic_imports(source: str, language: str) -> list[str]:
    """Conservative import/include extraction; only used to draw a real dependency diagram."""
    modules: list[str] = []
    for pattern in _IMPORT_PATTERNS.get(language, []):
        modules.extend(re.findall(pattern, source))
    return modules


def _generic_symbols(source: str, file_path: str, language: str) -> list[dict[str, Any]]:
    """Conservative fallback extractors for languages without a parser dependency."""
    patterns = {
        "JavaScript": (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", r"(?:export\s+)?class\s+(\w+)"),
        "TypeScript": (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)"),
        "Java": (r"(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\], ?]+\s+(\w+)\s*\(([^)]*)\)\s*\{", r"(?:public\s+)?class\s+(\w+)"),
        "C": (r"[\w*\s]+\s+(\w+)\s*\(([^;{}]*)\)\s*\{", r"(?:struct|class)\s+(\w+)"),
        "C++": (r"[\w:*<>\s]+\s+(\w+)\s*\(([^;{}]*)\)\s*(?:const\s*)?\{", r"(?:class|struct)\s+(\w+)"),
    }
    function_pattern, class_pattern = patterns[language]
    result: list[dict[str, Any]] = []
    for match in re.finditer(class_pattern, source):
        result.append({"type": "class", "name": match.group(1), "bases": [], "line": source.count("\n", 0, match.start()) + 1, "file": file_path})
    for match in re.finditer(function_pattern, source):
        parameters = [item.strip().split()[-1] for item in match.group(2).split(",") if item.strip() and item.strip() != "void"]
        result.append({"type": "function", "name": match.group(1), "parameters": parameters, "line": source.count("\n", 0, match.start()) + 1, "file": file_path})
    return result


_TREE_SITTER_LANGUAGES = {
    "Python": "python",
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "Java": "java",
    "C": "c",
    "C++": "cpp",
}


def _tree_sitter_symbols(parsed: Any, file_path: str) -> list[dict[str, Any]]:
    docstrings = {
        (symbol.name, symbol.span.start_line): symbol.doc
        for symbol in parsed.symbols
        if symbol.doc
    }
    symbols: list[dict[str, Any]] = []

    def visit(items: list[Any], parent_name: str | None = None) -> None:
        for item in items:
            kind = str(item.kind).lower()
            symbol_type = (
                "class" if any(token in kind for token in ("class", "interface", "enum", "struct"))
                else "function" if any(token in kind for token in ("function", "method", "constructor"))
                else None
            )
            name = item.name
            signature = item.signature or ""
            if not name and signature:
                match = re.search(r"(?:class|struct|interface|enum)\s+([A-Za-z_]\w*)", signature)
                if not match:
                    match = re.search(r"([A-Za-z_]\w*)\s*\(", signature)
                name = match.group(1) if match else None
            if name and symbol_type:
                start_line = item.span.start_line
                parameters_match = re.search(r"\(([^()]*)\)", signature)
                parameters = (
                    [part.strip().split()[-1] for part in parameters_match.group(1).split(",") if part.strip()]
                    if parameters_match else []
                )
                symbols.append({
                    "type": symbol_type,
                    "name": name,
                    "parameters": parameters,
                    "line": start_line + 1,
                    "end_line": item.span.end_line + 1,
                    "file": file_path,
                    "signature": signature,
                    "docstring": item.doc_comment or docstrings.get((name, start_line), ""),
                    "parent": parent_name,
                })
            visit(item.children, name if symbol_type == "class" else parent_name)

    visit(parsed.structure)
    return symbols


_PROJECT_DOCUMENTS = {
    "readme.md": "Markdown", "readme.rst": "reStructuredText", "readme.txt": "Text",
    "readme": "Text", "package.json": "JSON", "pyproject.toml": "TOML",
    "requirements.txt": "Text", "cargo.toml": "TOML", "go.mod": "Go",
    "pom.xml": "XML", "build.gradle": "Gradle", "build.gradle.kts": "Kotlin",
}


def _project_document_chunks(root: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    found_names: set[str] = set()
    for path in root.iterdir():
        language = _PROJECT_DOCUMENTS.get(path.name.lower())
        if not path.is_file() or language is None or path.name.lower() in found_names:
            continue
        found_names.add(path.name.lower())
        try:
            source = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
        except OSError:
            continue
        lines = source.splitlines()
        for offset in range(0, len(lines), 80):
            content = "\n".join(lines[offset:offset + 80]).strip()
            if content:
                chunks.append({
                    "id": f"{path.name}:{offset + 1}",
                    "file": path.name,
                    "language": language,
                    "start_line": offset + 1,
                    "end_line": min(offset + 80, len(lines)),
                    "content": content,
                    "semantic_metadata": {
                        "node_types": ["project_document"],
                        "symbols_defined": [],
                        "context_path": [],
                        "has_error_nodes": False,
                    },
                })
    return chunks



def analyze_repository(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    syntax_errors = 0
    raw_imports: list[tuple[str, list[str]]] = []  # (file, [imported module/path strings])
    for path in root.rglob("*"):
        if len(files) >= MAX_FILES:
            break
        if not path.is_file() or is_ignored(path, root) or not is_source_file(path):
            continue
        relative = path.relative_to(root).as_posix()
        language = LANGUAGES[path.suffix.lower()]
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append({"path": relative, "language": language, "bytes": path.stat().st_size})
        parsed = parse_with_tree_sitter(
            source,
            ProcessConfig(
                language=_TREE_SITTER_LANGUAGES[language],
                symbols=True,
                docstrings=True,
                diagnostics=True,
                chunk_max_size=6000,
            ),
        )
        if parsed.metrics is not None:
            syntax_errors += parsed.metrics.error_count
        syntax_symbols = _tree_sitter_symbols(parsed, relative)
        if language == "Python":
            python_symbols = _python_symbols(source, relative)
            syntax_by_key = {(item["name"], item["line"]): item for item in syntax_symbols}
            for item in python_symbols:
                item.update({
                    key: value for key, value in syntax_by_key.get((item["name"], item["line"]), {}).items()
                    if key not in {"type", "name", "parameters", "line", "file"}
                    and (key != "docstring" or value)
                })
            symbols.extend(python_symbols)
        else:
            symbols.extend(syntax_symbols)
            if language in {"C", "C++"}:
                existing = {(item["type"], item["name"], item["line"]) for item in syntax_symbols}
                symbols.extend(
                    item for item in _generic_symbols(source, relative, language)
                    if (item["type"], item["name"], item["line"]) not in existing
                )
            elif not syntax_symbols:
                symbols.extend(_generic_symbols(source, relative, language))
        raw_imports.append((relative, _python_imports(source) if language == "Python" else _generic_imports(source, language)))
        for index, parsed_chunk in enumerate(parsed.chunks):
            metadata = parsed_chunk.metadata
            chunks.append({
                "id": f"{relative}:{parsed_chunk.start_line + 1}:{index}",
                "file": relative,
                "language": language,
                "start_line": parsed_chunk.start_line + 1,
                "end_line": parsed_chunk.end_line + 1,
                "content": parsed_chunk.content.strip(),
                "semantic_metadata": {
                    "node_types": metadata.node_types if metadata else [],
                    "symbols_defined": metadata.symbols_defined if metadata else [],
                    "context_path": metadata.context_path if metadata else [],
                    "has_error_nodes": metadata.has_error_nodes if metadata else False,
                },
            })
    chunks.extend(_project_document_chunks(root))
    languages = sorted(set(item["language"] for item in files))
    dependencies = _resolve_internal_imports(files, raw_imports)
    external_dependencies = _external_dependencies(files, raw_imports)
    return {
        "files": files,
        "symbols": symbols,
        "chunks": chunks,
        "dependencies": dependencies,
        "external_dependencies": external_dependencies,
        "syntax_errors": syntax_errors,
        "summary": {
            "files": len(files), "languages": languages,
            "functions": sum(item["type"] == "function" for item in symbols),
            "classes": sum(item["type"] == "class" for item in symbols),
            "files_by_language": dict(Counter(item["language"] for item in files)),
            "parser": "tree-sitter",
            "syntax_errors": syntax_errors,
        },
    }


_STDLIB_NOISE = {
    "os", "sys", "re", "json", "typing", "pathlib", "collections", "itertools", "functools",
    "abc", "dataclasses", "enum", "math", "time", "datetime", "logging", "unittest", "asyncio",
    "contextlib", "copy", "io", "traceback", "warnings", "subprocess", "shutil", "hashlib",
    "__future__", "React", "react", "react-dom",
}


def _external_dependencies(files: list[dict[str, Any]], raw_imports: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    """Top-level modules imported across the repo that do NOT resolve to another file in this
    same repo, i.e. third-party libraries/frameworks actually used by this project. This is what
    grounds the Technology Stack / Database Design / System Requirements sections in real evidence
    instead of an LLM guess."""
    internal_stems = {Path(file["path"]).stem.lower() for file in files}
    counts: Counter[str] = Counter()
    for _source_file, modules in raw_imports:
        for module in modules:
            if not module:
                continue
            top = re.split(r"[./\\]", module)[0].lstrip("@").strip()
            if not top or top.lower() in internal_stems or top in _STDLIB_NOISE:
                continue
            counts[top] += 1
    return [{"name": name, "count": count} for name, count in counts.most_common(20)]


def _resolve_internal_imports(files: list[dict[str, Any]], raw_imports: list[tuple[str, list[str]]]) -> list[dict[str, str]]:
    """Match each raw import string against real repo files by filename stem, so the
    behavioural diagram reflects this specific project instead of a fixed template."""
    stem_to_files: dict[str, list[str]] = {}
    for file in files:
        stem = Path(file["path"]).stem.lower()
        stem_to_files.setdefault(stem, []).append(file["path"])
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source_file, modules in raw_imports:
        for module in modules:
            segment = re.split(r"[./\\]", module)[-1].lower() if module else ""
            if not segment:
                continue
            for target_file in stem_to_files.get(segment, []):
                if target_file == source_file or (source_file, target_file) in seen:
                    continue
                seen.add((source_file, target_file))
                edges.append({"from": source_file, "to": target_file})
    return edges
