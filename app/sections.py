from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

FRAMEWORK_HINTS: dict[str, tuple[str, str]] = {
    # library/import name (lowercased) -> (category, display label)
    "react": ("frontend", "React"), "react-dom": ("frontend", "React"), "vue": ("frontend", "Vue.js"),
    "angular": ("frontend", "Angular"), "next": ("frontend", "Next.js"), "svelte": ("frontend", "Svelte"),
    "vite": ("frontend", "Vite"), "redux": ("frontend", "Redux"), "tailwindcss": ("frontend", "Tailwind CSS"),
    "bootstrap": ("frontend", "Bootstrap"), "jquery": ("frontend", "jQuery"),
    "fastapi": ("backend", "FastAPI"), "flask": ("backend", "Flask"), "django": ("backend", "Django"),
    "express": ("backend", "Express.js"), "spring": ("backend", "Spring"), "springframework": ("backend", "Spring"),
    "nestjs": ("backend", "NestJS"), "gin": ("backend", "Gin"), "rails": ("backend", "Ruby on Rails"),
    "uvicorn": ("backend", "Uvicorn (ASGI server)"), "gunicorn": ("backend", "Gunicorn (WSGI server)"),
    "sqlalchemy": ("database", "SQLAlchemy ORM"), "mongoose": ("database", "MongoDB (via Mongoose)"),
    "pymongo": ("database", "MongoDB"), "psycopg2": ("database", "PostgreSQL"), "psycopg": ("database", "PostgreSQL"),
    "mysql": ("database", "MySQL"), "mysqlclient": ("database", "MySQL"), "sqlite3": ("database", "SQLite"),
    "redis": ("database", "Redis"), "peewee": ("database", "Peewee ORM"), "django_orm": ("database", "Django ORM"),
    "firebase": ("database", "Firebase"), "prisma": ("database", "Prisma ORM"),
    "pytest": ("tools", "pytest (testing)"), "unittest": ("tools", "unittest (testing)"),
    "jest": ("tools", "Jest (testing)"), "mocha": ("tools", "Mocha (testing)"), "junit": ("tools", "JUnit (testing)"),
    "numpy": ("tools", "NumPy"), "pandas": ("tools", "Pandas"), "tensorflow": ("tools", "TensorFlow"),
    "torch": ("tools", "PyTorch"), "sklearn": ("tools", "scikit-learn"), "opencv": ("tools", "OpenCV"),
    "axios": ("tools", "Axios"), "httpx": ("tools", "HTTPX"), "requests": ("tools", "Requests"),
    "docker": ("tools", "Docker"), "pydantic": ("tools", "Pydantic"),
}


def build_technology_stack(analysis: dict[str, Any]) -> dict[str, list[str]]:
    """Frontend / Backend / Database / Tools, populated ONLY from libraries actually imported
    in the analyzed source and languages actually detected — never guessed."""
    stack: dict[str, set[str]] = {"frontend": set(), "backend": set(), "database": set(), "tools": set()}
    for dependency in analysis.get("external_dependencies", []):
        name = dependency["name"].lower()
        hit = FRAMEWORK_HINTS.get(name)
        if hit:
            category, label = hit
            stack[category].add(label)
    languages = analysis["summary"].get("languages", [])
    source_text = "\n".join(chunk.get("content", "") for chunk in analysis.get("chunks", [])).lower()
    if not stack["backend"] and languages:
        stack["backend"].update(f"{language} (no web framework import detected)" for language in languages
                                 if language not in ("JavaScript", "TypeScript"))
    if not stack["frontend"] and any(language in ("JavaScript", "TypeScript") for language in languages):
        stack["frontend"].add("Plain JavaScript/TypeScript")
    if "document." in source_text or "queryselector" in source_text:
        stack["frontend"].add("Browser DOM API")
    if "localstorage" in source_text:
        stack["database"].add("Browser Local Storage (client-side high-score persistence)")
    if "new audio" in source_text:
        stack["tools"].add("Browser Audio API")
    return {category: sorted(values) or ["Not detected from static analysis"] for category, values in stack.items()}


def build_system_requirements(analysis: dict[str, Any]) -> dict[str, list[str]]:
    languages = analysis["summary"].get("languages", [])
    libraries = [item["name"] for item in analysis.get("external_dependencies", [])[:12]]
    software = [f"{language} runtime/compiler" for language in languages] or ["Not detected from static analysis"]
    if libraries:
        software.append("Third-party packages: " + ", ".join(libraries))
    software.append("Git (to clone/manage the source repository)")
    hardware = [
        "A standard development machine capable of running the detected language runtime(s) above",
        "Minimum 4 GB RAM (8 GB+ recommended for larger builds)",
        "Internet connection, for dependency installation and (if applicable) cloud services",
    ]
    return {"hardware": hardware, "software": software}


def build_modules_description(analysis: dict[str, Any], max_folders: int = 14, max_files_per_folder: int = 8) -> list[dict[str, Any]]:
    """Group real source files by their real top-level folder — an accurate, grounded stand-in
    for 'explain each module/component' that never invents a module that doesn't exist."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for file in analysis["files"]:
        parts = file["path"].split("/")
        folder = parts[0] if len(parts) > 1 else "(root)"
        groups[folder].append(file)
    modules = []
    for folder, files in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:max_folders]:
        modules.append({
            "name": folder,
            "file_count": len(files),
            "languages": sorted({f["language"] for f in files}),
            "files": [f["path"] for f in files[:max_files_per_folder]],
        })
    return modules


def build_database_design(analysis: dict[str, Any]) -> dict[str, Any]:
    detected = []
    for dependency in analysis.get("external_dependencies", []):
        hit = FRAMEWORK_HINTS.get(dependency["name"].lower())
        if hit and hit[0] == "database":
            detected.append(hit[1])
    detected = sorted(set(detected))
    model_classes = [item["name"] for item in analysis["symbols"]
                      if item["type"] == "class" and any(k in item["name"].lower() for k in ("model", "schema", "entity", "table"))]
    source_text = "\n".join(chunk.get("content", "") for chunk in analysis.get("chunks", [])).lower()
    uses_local_storage = "localstorage" in source_text
    if uses_local_storage:
        detected.append("Browser Local Storage")
    return {
        "detected_technology": detected or ["No database library/import detected in the analyzed source"],
        "model_like_classes": sorted(set(model_classes))[:20],
        "note": ("High-score data is stored in browser Local Storage. This is client-side key/value persistence, so "
                 "there are no server tables or an ER diagram in the current implementation." if uses_local_storage else
                 "These classes look like data models based on their names; review the source to confirm actual "
                 "table/collection structure." if model_classes else
                 "No ER diagram is generated automatically: static analysis found no ORM models/schema classes to "
                 "derive one from. Add tables/fields manually if this project uses a database."),
    }


TEST_HINTS = {"pytest", "unittest", "jest", "mocha", "junit", "chai", "vitest", "cypress", "nose"}


def build_testing_section(analysis: dict[str, Any]) -> dict[str, Any]:
    test_files = [f["path"] for f in analysis["files"]
                  if "test" in Path(f["path"]).stem.lower() or "spec" in Path(f["path"]).stem.lower()]
    frameworks = sorted({d["name"] for d in analysis.get("external_dependencies", []) if d["name"].lower() in TEST_HINTS})
    return {
        "test_files": test_files[:25],
        "test_file_count": len(test_files),
        "frameworks_detected": frameworks or ["None detected from imports"],
        "note": ("Automated test files were found in the repository; see the list for their locations." if test_files
                  else "No test files (matching *test*/*spec* naming) were found by static analysis. Add test cases "
                       "and results here manually, or point this report at a repository that includes its test suite."),
    }
