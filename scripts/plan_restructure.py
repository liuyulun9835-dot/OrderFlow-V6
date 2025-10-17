#!/usr/bin/env python3
"""Planning and execution tooling for migrating the repository to the layered architecture.

The script operates in two modes:

```
python scripts/plan_restructure.py --mode plan   # dry-run planning that writes CSV plans
python scripts/plan_restructure.py --mode apply  # execute file moves and import rewrites
```

The plan mode enumerates all tracked source files, infers their target layer based on the
current path and simple keyword rules, and writes move / import rewrite plans under
``docs/migrations``.  The apply mode consumes those plans, performs the filesystem moves,
creates compatibility re-export shims, and rewrites imports as requested while recording
comprehensive audit logs.

The code purposely avoids touching governance artefacts in the repository root such as
README, TODO, CONTROL_*, RULES_*, SCHEMA_* files, and engineering logs.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import re
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import py_compile
except Exception as exc:  # pragma: no cover - defensive guard when py_compile missing
    raise RuntimeError("py_compile is required for syntax validation") from exc

REPO_GOVERNANCE_PREFIXES = ("CONTROL_", "RULES_", "SCHEMA_")
ROOT_PROTECTED_FILES = {
    "README.md",
    "order_flow_v_6_todo.md",
}

ROOT_CONFIG_FILES = {
    "pyproject.toml",
    "poetry.lock",
    "requirements.txt",
    "Makefile",
}

# Engineering log files are kept in the root with the prefix shown below.
ENGINEERING_LOG_PREFIX = "工程日志"

SOURCE_EXTENSIONS = {
    ".py",
    ".ipynb",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".txt",
}

LAYER_KEYWORDS = {
    "data": ("data", "dataset", "preprocess", "ingest", "etl", "feature", "clean"),
    "model": ("model", "train", "predict", "ml", "neural", "xgboost", "lstm"),
    "decision": ("decision", "strategy", "logic", "rules", "signal", "policy"),
    "execution": ("execution", "executor", "order", "trade", "broker", "client", "api"),
    "output": ("output", "report", "analysis", "visual", "notebook", "export", "result"),
}
DEFAULT_LAYER = "execution"

# Components that should be dropped when computing the new relative path under the layer.
DROP_TOP_LEVEL_COMPONENTS = {
    "orderflow_v6",
    "orderflow_v_6",
    "src",
}

# Components that should be replaced with a different spelling for the destination path.
COMPONENT_RENAMES = {
    "models": "model",
}

SKIP_DIRECTORIES = {
    ".git",
    "__pycache__",
    "build",
    "dist",
    "docs/migrations",
    "orderflow_v_6/compat",
}

INTERNAL_TOOLING_PATHS = {
    Path("scripts/plan_restructure.py"),
    Path("scripts/run_restructure.sh"),
}

MOVE_PLAN_HEADERS = ("src_path", "dst_path", "layer_reason")
IMPORT_PLAN_HEADERS = ("file", "old_import", "new_import")
IMPORT_LOG_HEADERS = ("file", "old_import", "new_import", "status", "message")


@dataclasses.dataclass
class MovePlan:
    src_path: Path
    dst_path: Path
    layer_reason: str


@dataclasses.dataclass
class ImportRewritePlan:
    file: Path
    old_import: str
    new_import: str


@dataclasses.dataclass
class LayerInference:
    layer: str
    reason: str
    matched_component: Optional[str] = None
    matched_index: Optional[int] = None


def debug(msg: str) -> None:
    """Central debug printer that respects a simple environment flag."""

    if os.environ.get("PLAN_RESTRUCTURE_DEBUG"):
        print(f"[DEBUG] {msg}")


def resolve_repo_root(script_path: Path) -> Path:
    return script_path.resolve().parents[1]


def should_skip(path: Path, repo_root: Path) -> bool:
    """Determine whether a file should be skipped from planning."""

    rel = path.relative_to(repo_root)
    if rel in INTERNAL_TOOLING_PATHS:
        return True

    if len(rel.parts) == 1 and rel.name in ROOT_CONFIG_FILES:
        return True

    if rel.parts[0] in {".git", "venv", "env", "node_modules"}:
        return True

    if rel.parts[0] == "docs" and len(rel.parts) > 1 and rel.parts[1] == "migrations":
        return True

    if rel.parts[0] == "orderflow_v_6" and len(rel.parts) > 1 and rel.parts[1] == "compat":
        return True

    if rel.parts[0] in {".github", "releases"}:
        return True

    if rel.name.startswith(".") and rel.name not in {".env", ".env.example"}:
        return True

    if rel.suffix not in SOURCE_EXTENSIONS:
        return True

    if len(rel.parts) == 1:
        # Root-level file; protect governance artefacts.
        if rel.name in ROOT_PROTECTED_FILES:
            return True
        if rel.name.startswith(ENGINEERING_LOG_PREFIX):
            return True
        if rel.name.startswith(REPO_GOVERNANCE_PREFIXES):
            return True

    return False


def infer_layer_from_path(rel_path: Path) -> LayerInference:
    parts = [p.lower() for p in rel_path.parts]
    for index, part in enumerate(parts):
        for layer, keywords in LAYER_KEYWORDS.items():
            if any(keyword in part for keyword in keywords):
                reason = f"Matched keyword '{keywords[0]}' in path component '{rel_path.parts[index]}'"
                return LayerInference(layer=layer, reason=reason, matched_component=rel_path.parts[index], matched_index=index)

    return LayerInference(layer=DEFAULT_LAYER, reason=f"Fell back to default layer '{DEFAULT_LAYER}'")


def build_destination_path(rel_path: Path, layer: str, matched_index: Optional[int]) -> Path:
    parts: List[str] = list(rel_path.parts)
    if parts and parts[0] == layer:
        return rel_path

    if parts and parts[0] in COMPONENT_RENAMES:
        parts[0] = COMPONENT_RENAMES[parts[0]]

    if parts and parts[0] in DROP_TOP_LEVEL_COMPONENTS:
        parts = parts[1:]

    if matched_index is not None and matched_index < len(parts):
        # Remove matched component if it duplicates the layer name to avoid redundant nesting.
        candidate = parts[matched_index]
        if candidate.lower() == layer:
            parts.pop(matched_index)

    destination_parts = [layer]
    destination_parts.extend(parts)
    return Path(*destination_parts)


def scan_source_files(repo_root: Path) -> List[Path]:
    files: List[Path] = []
    for root, dirnames, filenames in os.walk(repo_root):
        rel_root = Path(root).relative_to(repo_root)
        rel_root_str = str(rel_root).replace("\\", "/")
        if rel_root_str in SKIP_DIRECTORIES:
            debug(f"Skipping directory tree {rel_root_str}")
            dirnames[:] = []
            continue

        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "build", "dist"}]

        for filename in filenames:
            path = Path(root) / filename
            if should_skip(path, repo_root):
                continue
            files.append(path)
    return files


def generate_move_plan(repo_root: Path) -> List[MovePlan]:
    plans: List[MovePlan] = []
    for file_path in scan_source_files(repo_root):
        rel_path = file_path.relative_to(repo_root)
        inference = infer_layer_from_path(rel_path)
        destination = build_destination_path(rel_path, inference.layer, inference.matched_index)
        if destination == rel_path:
            continue
        plans.append(MovePlan(src_path=rel_path, dst_path=destination, layer_reason=inference.reason))
    return plans


def path_to_module_name(path: Path) -> Optional[str]:
    if path.suffix != ".py":
        return None
    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return None
    return ".".join(parts)


def build_module_mapping(move_plans: Sequence[MovePlan]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for plan in move_plans:
        old_module = path_to_module_name(plan.src_path)
        new_module = path_to_module_name(plan.dst_path)
        if not old_module or not new_module:
            continue
        mapping[old_module] = new_module
    return mapping


def suggest_import_rewrites(repo_root: Path, move_plans: Sequence[MovePlan]) -> List[ImportRewritePlan]:
    module_mapping = build_module_mapping(move_plans)
    if not module_mapping:
        return []

    # Sort keys by length descending to handle nested modules first.
    mapping_items = sorted(module_mapping.items(), key=lambda item: len(item[0]), reverse=True)

    rewrites: List[ImportRewritePlan] = []

    for file_path in scan_source_files(repo_root):
        if file_path.suffix != ".py":
            continue
        rel_path = file_path.relative_to(repo_root)
        if rel_path in INTERNAL_TOOLING_PATHS:
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        try:
            import ast
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    replacement = find_replacement(module_name, mapping_items)
                    if replacement:
                        rewrites.append(ImportRewritePlan(file=rel_path, old_import=module_name, new_import=replacement))
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                module_name = node.module
                replacement = find_replacement(module_name, mapping_items)
                if replacement:
                    rewrites.append(ImportRewritePlan(file=rel_path, old_import=module_name, new_import=replacement))

    unique: Dict[Tuple[Path, str, str], ImportRewritePlan] = {}
    for item in rewrites:
        key = (item.file, item.old_import, item.new_import)
        if key not in unique:
            unique[key] = item
    return list(unique.values())


def find_replacement(module_name: str, mapping_items: Sequence[Tuple[str, str]]) -> Optional[str]:
    if module_name.startswith("."):
        return None
    for old, new in mapping_items:
        if module_name == old:
            return new
        if module_name.startswith(old + "."):
            suffix = module_name[len(old):]
            return new + suffix
    return None


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)


def read_move_plan(path: Path) -> List[MovePlan]:
    if not path.exists():
        raise FileNotFoundError(f"Move plan CSV not found at {path}")
    rows: List[MovePlan] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            rows.append(MovePlan(src_path=Path(raw["src_path"]), dst_path=Path(raw["dst_path"]), layer_reason=raw.get("layer_reason", "")))
    return rows


def read_import_plan(path: Path) -> List[ImportRewritePlan]:
    if not path.exists():
        return []
    rows: List[ImportRewritePlan] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            rows.append(ImportRewritePlan(file=Path(raw["file"]), old_import=raw["old_import"], new_import=raw["new_import"]))
    return rows


def apply_move(plan: MovePlan, repo_root: Path) -> None:
    src = repo_root / plan.src_path
    dst = repo_root / plan.dst_path
    ensure_directory(dst.parent)
    if not src.exists():
        raise FileNotFoundError(f"Source file missing: {src}")
    debug(f"Moving {src} -> {dst}")
    shutil.move(str(src), str(dst))


def create_compat_stub(plan: MovePlan, repo_root: Path) -> None:
    compat_root = repo_root / "orderflow_v_6" / "compat"
    ensure_directory(compat_root)

    module_path = plan.src_path
    if module_path.suffix == ".py":
        module_path = module_path.with_suffix("")

    stub_path = compat_root / module_path
    ensure_directory(stub_path.parent)

    new_module = plan.dst_path.with_suffix("") if plan.dst_path.suffix else plan.dst_path
    new_module_import = ".".join(new_module.parts)

    contents = textwrap.dedent(
        f"""
        \"\"\"Compatibility re-export for the migrated module.\"\"\"
        from {new_module_import} import *  # noqa: F401,F403
        """
    ).strip() + "\n"

    stub_file = stub_path.with_suffix(".py")
    if not stub_file.exists():
        stub_file.write_text(contents, encoding="utf-8")


def record_move_log(path: Path, plan: MovePlan) -> None:
    ensure_directory(path.parent)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if not file_exists:
            writer.writerow(MOVE_PLAN_HEADERS)
        writer.writerow([str(plan.src_path), str(plan.dst_path), plan.layer_reason])


def replace_imports_in_line(line: str, old: str, new: str) -> Tuple[str, bool]:
    changed = False

    def replace_from(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return f"{match.group(1)}{new}{match.group(2)}"

    pattern_from = re.compile(rf"(\bfrom\s+){re.escape(old)}(\s+import\b)")
    line, count = pattern_from.subn(replace_from, line)
    if count:
        return line, True

    import_pattern = re.compile(r"^\s*import\s+(.+)$")
    match = import_pattern.match(line)
    if not match:
        # Also support inline imports that contain commas (e.g., inside parentheses)
        inline_pattern = re.compile(rf"(\bimport\s+){re.escape(old)}(\b)")
        line, count = inline_pattern.subn(rf"\1{new}\2", line)
        if count:
            return line, True
        return line, False

    imports_segment = match.group(1)
    segments = [segment.strip() for segment in imports_segment.split(",")]
    new_segments = []
    for segment in segments:
        if not segment:
            continue
        if segment.startswith(old + " ") or segment == old or segment.startswith(old + "."):
            changed = True
            new_segment = new + segment[len(old):]
            new_segments.append(new_segment)
        else:
            new_segments.append(segment)
    if changed:
        line = line.replace(imports_segment, ", ".join(new_segments))
    return line, changed


def rewrite_import(plan: ImportRewritePlan, repo_root: Path) -> Tuple[bool, str]:
    file_path = repo_root / plan.file
    if not file_path.exists():
        return False, "file missing"

    try:
        original_text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "unable to read file"

    lines = original_text.splitlines()
    changed_any = False
    for idx, line in enumerate(lines):
        new_line, changed = replace_imports_in_line(line, plan.old_import, plan.new_import)
        if changed:
            lines[idx] = new_line
            changed_any = True
    if not changed_any:
        return False, "no occurrences replaced"

    updated_text = "\n".join(lines) + ("\n" if original_text.endswith("\n") else "")
    file_path.write_text(updated_text, encoding="utf-8")

    try:
        py_compile.compile(str(file_path), doraise=True)
    except Exception as exc:
        file_path.write_text(original_text, encoding="utf-8")
        return False, f"py_compile failed: {exc}"  # type: ignore[str-bytes-safe]

    return True, "applied"


def append_import_log(path: Path, record: Sequence[str]) -> None:
    ensure_directory(path.parent)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if not file_exists:
            writer.writerow(IMPORT_LOG_HEADERS)
        writer.writerow(record)


def apply(repo_root: Path, move_plan_path: Path, import_plan_path: Path) -> None:
    move_plans = read_move_plan(move_plan_path)
    if not move_plans:
        print("No move plans detected; nothing to apply.")
        return

    import_plans = read_import_plan(import_plan_path)

    move_log_path = repo_root / "docs/migrations/file_moves.csv"
    for plan in move_plans:
        apply_move(plan, repo_root)
        record_move_log(move_log_path, plan)
        create_compat_stub(plan, repo_root)

    if not import_plans:
        print("No import rewrites requested; skipping import modifications.")
        return

    applied_path = repo_root / "docs/migrations/import_rewrites_applied.csv"
    failed_path = repo_root / "docs/migrations/import_rewrites_failed.csv"
    audit_path = repo_root / "docs/migrations/import_rewrites.csv"

    for plan in import_plans:
        success, message = rewrite_import(plan, repo_root)
        status = "applied" if success else "skipped"
        append_import_log(audit_path, (str(plan.file), plan.old_import, plan.new_import, status, message))
        if success:
            append_import_log(applied_path, (str(plan.file), plan.old_import, plan.new_import, status, message))
        else:
            append_import_log(failed_path, (str(plan.file), plan.old_import, plan.new_import, status, message))


def run_plan(repo_root: Path, move_plan_path: Path, import_plan_path: Path) -> None:
    move_plans = generate_move_plan(repo_root)
    write_csv(move_plan_path, MOVE_PLAN_HEADERS, ((str(plan.src_path), str(plan.dst_path), plan.layer_reason) for plan in move_plans))

    import_plans = suggest_import_rewrites(repo_root, move_plans)
    write_csv(import_plan_path, IMPORT_PLAN_HEADERS, ((str(plan.file), plan.old_import, plan.new_import) for plan in import_plans))

    print(f"Planned {len(move_plans)} file moves and {len(import_plans)} import rewrites.")
    print("Review docs/migrations/file_moves_plan.csv and docs/migrations/import_rewrite_plan.csv before applying.")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan and apply repository restructure")
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan", help="plan (dry-run) or apply the restructure")
    parser.add_argument("--repo-root", default=None, help="Optional repository root override")
    parser.add_argument("--move-plan", default="docs/migrations/file_moves_plan.csv", help="Path to the file move plan CSV")
    parser.add_argument("--import-plan", default="docs/migrations/import_rewrite_plan.csv", help="Path to the import rewrite plan CSV")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    script_path = Path(__file__)
    repo_root = Path(args.repo_root) if args.repo_root else resolve_repo_root(script_path)
    move_plan_path = repo_root / args.move_plan
    import_plan_path = repo_root / args.import_plan

    if args.mode == "plan":
        run_plan(repo_root, move_plan_path, import_plan_path)
    else:
        apply(repo_root, move_plan_path, import_plan_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
