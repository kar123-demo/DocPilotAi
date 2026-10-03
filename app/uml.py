from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx


def _safe_id(value: str, prefix: str = "N") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not cleaned:
        return prefix
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return f"{prefix}_{cleaned}" if prefix != "N" else cleaned


def _quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'").replace("\r", " ").replace("\n", " ")


def build_fallback_uml_diagrams(analysis: dict[str, Any], project_name: str) -> dict[str, list[dict[str, str]]]:
    """Build six PlantUML views from detected source symbols when model generation fails."""
    files = analysis.get("files", [])
    symbols = analysis.get("symbols", [])
    class_lines = ["@startuml", f"title {_quoted(project_name)} - Class Diagram"]
    classes = [item for item in symbols if item["type"] == "class"][:12]
    if classes:
        for item in classes:
            class_id = _safe_id(item["name"], "C")
            class_lines.append(f'class "{_quoted(item["name"])}" as {class_id} {{')
            for method in [
                entry for entry in symbols
                if entry["type"] == "function" and entry.get("parent") == item["name"]
            ][:6]:
                class_lines.append(f"  +{_safe_id(method['name'])}()")
            class_lines.append("}")
        class_names = {item["name"] for item in classes}
        for item in classes:
            for base in item.get("bases", []):
                if base in class_names and base != item["name"]:
                    class_lines.append(f"{_safe_id(base, 'C')} <|-- {_safe_id(item['name'], 'C')}")
    else:
        functions_by_file: dict[str, list[str]] = defaultdict(list)
        for item in symbols:
            if item["type"] == "function":
                functions_by_file[item["file"]].append(item["name"])
        for file_path, function_names in functions_by_file.items():
            module_id = _safe_id(file_path, "M")
            class_lines.append(f'class "{_quoted(Path(file_path).name)}" as {module_id} <<module>>')
            for function_name in function_names[:12]:
                class_lines.append(f"{module_id} : +{_safe_id(function_name)}()")
    if len(class_lines) == 2:
        for file in files[:12]:
            class_lines.append(f'class "{_quoted(Path(file["path"]).name)}" as {_safe_id(file["path"], "M")}')
    if len(class_lines) == 2:
        class_lines.append(f'class "{_quoted(project_name)}" as Project')
    class_lines.append("@enduml")

    folder_files: dict[str, list[str]] = defaultdict(list)
    for file in files[:16]:
        parts = file["path"].replace("\\", "/").split("/")
        folder_files[parts[0] if len(parts) > 1 else "(root)"].append(file["path"])
    component_lines = ["@startuml", f"title {_quoted(project_name)} - Component Diagram"]
    for folder, folder_paths in folder_files.items():
        component_lines.append(f'package "{_quoted(folder)}" {{')
        for path in folder_paths[:8]:
            component_lines.append(f'  component "{_quoted(Path(path).name)}" as {_safe_id(path, "F")}')
        component_lines.append("}")
    if not folder_files:
        component_lines.append(f'component "{_quoted(project_name)}" as Project')
    for edge in analysis.get("dependencies", [])[:20]:
        component_lines.append(f'{_safe_id(edge["from"], "F")} --> {_safe_id(edge["to"], "F")} : depends on')
    component_lines.append("@enduml")

    package_lines = ["@startuml", f"title {_quoted(project_name)} - Package Diagram"]
    for folder, folder_paths in folder_files.items():
        package_lines.append(f'package "{_quoted(folder)}" {{')
        for path in folder_paths[:8]:
            package_lines.append(f'  class "{_quoted(Path(path).stem)}" as {_safe_id(path, "M")}')
        package_lines.append("}")
    if not folder_files:
        package_lines.extend([f'package "{_quoted(project_name)}" {{', "  class SourceCode", "}"])
    package_lines.append("@enduml")

    use_case_lines = [
        "@startuml",
        f"title {_quoted(project_name)} - Use Case Diagram",
        "note as N1",
        "Static source symbols do not establish user-facing goals.",
        "Generate behavioral use cases from verified project documentation.",
        "end note",
        "@enduml",
    ]

    activity_lines = [
        "@startuml",
        f"title {_quoted(project_name)} - Activity Diagram",
        "start",
        f":Static analysis detected {len(symbols)} named source symbols;",
        ":Runtime action order is not established by static analysis;",
        "stop",
        "@enduml",
    ]

    sequence_lines = [
        "@startuml",
        f"title {_quoted(project_name)} - Sequence Diagram",
        'participant "Runtime flow not inferred" as Runtime',
        "note over Runtime",
        "Runtime participants and message order are not established",
        "by static source analysis.",
        "end note",
        "@enduml",
    ]

    return {
        "structural": [
            {"id": "class", "title": "UML Class Diagram", "code": "\n".join(class_lines) + "\n"},
            {"id": "component", "title": "UML Component Diagram", "code": "\n".join(component_lines) + "\n"},
            {"id": "package", "title": "UML Package Diagram", "code": "\n".join(package_lines) + "\n"},
        ],
        "behavioral": [
            {"id": "use-case", "title": "UML Use Case Diagram", "code": "\n".join(use_case_lines) + "\n"},
            {"id": "activity", "title": "UML Activity Diagram", "code": "\n".join(activity_lines) + "\n"},
            {"id": "sequence", "title": "UML Sequence Diagram", "code": "\n".join(sequence_lines) + "\n"},
        ],
    }


async def render_plantuml_png(plantuml: str, output_path: Path) -> tuple[bool, str | None]:
    """Render PlantUML through Kroki. Report generation continues if the renderer is offline."""
    renderer_url = os.environ.get(
        "PLANTUML_RENDERER_URL", "https://kroki.io/plantuml/png"
    ).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                renderer_url,
                content=plantuml,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            response.raise_for_status()
            if not response.headers.get("content-type", "").startswith("image/png"):
                return False, "Renderer returned a non-PNG response."
        output_path.write_bytes(response.content)
        return True, None
    except (httpx.HTTPError, OSError) as error:
        return False, f"{type(error).__name__}: {error}"
