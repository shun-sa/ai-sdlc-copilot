#!/usr/bin/env python3
"""
Deterministic AST support for Traceability Audit.

This module intentionally keeps semantic requirement/ADR judgement outside of the
AST layer. It only answers structural questions such as:

- Which production/test symbols physically exist?
- What qualified names can be derived from source structure?
- Which production symbols are called from a test symbol?
- Does a test contain an assertion?

Supported analyzers:
- Python: built-in ``ast`` module (no third-party dependency)
- Java: JDK Compiler Tree API via ``JavaAstAnalyzer.java``
- TypeScript/JavaScript: TypeScript Compiler API via
  ``typescript_ast_analyzer.cjs``

The Java/TypeScript analyzers are optional at runtime. Their availability is
reported in the generated index so policy can decide whether unavailability is
blocking.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

AST_INDEX_VERSION = 1
SUPPORTED_EXTENSIONS = {".py", ".java", ".ts", ".tsx", ".js", ".jsx"}
LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
}


def _posix(path: Path) -> str:
    return path.as_posix()


def _relative(path: Path, root: Path) -> str:
    try:
        return _posix(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return _posix(path.resolve())


def _module_name(path: Path, root: Path) -> str:
    rel = Path(_relative(path, root))
    without_suffix = rel.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def _is_under_roots(rel_path: str, roots: list[str]) -> bool:
    rel = rel_path.strip("/")
    for root in roots:
        normalized = root.strip().strip("/")
        if not normalized:
            continue
        if rel == normalized or rel.startswith(normalized + "/"):
            return True
    return False


def _discover_files(
    repo_root: Path,
    roots: list[str],
    extensions: set[str],
    exclude_globs: list[str],
) -> list[Path]:
    found: set[Path] = set()
    for root_value in roots:
        root = repo_root / root_value
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            rel = _relative(path, repo_root)
            if _matches_any(rel, exclude_globs):
                continue
            found.add(path.resolve())
    return sorted(found, key=lambda p: _relative(p, repo_root))


def _fingerprint(files: Iterable[Path], repo_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda p: _relative(p, repo_root)):
        rel = _relative(path, repo_root)
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    return sorted({str(v).strip() for v in values if str(v).strip()})


@dataclass
class CallRecord:
    raw: str
    qualified_name: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"raw": self.raw}
        if self.qualified_name:
            result["qualified_name"] = self.qualified_name
        if self.line is not None:
            result["line"] = self.line
        return result


@dataclass
class SymbolRecord:
    language: str
    file: str
    kind: str
    symbol: str
    qualified_name: str
    line: int | None = None
    calls: list[CallRecord] = field(default_factory=list)
    assertion_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "language": self.language,
            "file": self.file,
            "kind": self.kind,
            "symbol": self.symbol,
            "qualified_name": self.qualified_name,
            "calls": [call.to_dict() for call in self.calls],
            "assertion_count": self.assertion_count,
        }
        if self.line is not None:
            result["line"] = self.line
        return result


# ---------------------------------------------------------------------------
# Python analyzer
# ---------------------------------------------------------------------------


class _PythonModuleContext:
    def __init__(self, module: str) -> None:
        self.module = module
        self.import_symbols: dict[str, str] = {}
        self.import_modules: dict[str, str] = {}

    def resolve_name(self, name: str) -> str | None:
        if name in self.import_symbols:
            return self.import_symbols[name]
        if name in self.import_modules:
            return self.import_modules[name]
        return None


def _python_imports(tree: ast.AST, module: str) -> _PythonModuleContext:
    context = _PythonModuleContext(module)
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                context.import_modules[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            target_module = node.module or ""
            if node.level:
                module_parts = module.split(".")[:-1]
                keep = max(0, len(module_parts) - node.level + 1)
                prefix = module_parts[:keep]
                if target_module:
                    prefix.extend(target_module.split("."))
                target_module = ".".join(prefix)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                qn = f"{target_module}.{alias.name}" if target_module else alias.name
                context.import_symbols[local] = qn
    return context


def _attribute_chain(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return list(reversed(parts))
    return None


class _PythonFunctionInspector(ast.NodeVisitor):
    def __init__(
        self,
        module_context: _PythonModuleContext,
        module: str,
        class_qn: str | None,
    ) -> None:
        self.module_context = module_context
        self.module = module
        self.class_qn = class_qn
        self.calls: list[CallRecord] = []
        self.assertion_count = 0
        self.variable_types: dict[str, str] = {}

    def _resolve_callable(self, node: ast.AST) -> tuple[str, str | None]:
        try:
            raw = ast.unparse(node)
        except Exception:
            raw = node.__class__.__name__

        if isinstance(node, ast.Name):
            imported = self.module_context.resolve_name(node.id)
            if imported:
                return raw, imported
            if self.class_qn:
                return raw, f"{self.class_qn}.{node.id}"
            return raw, f"{self.module}.{node.id}" if self.module else node.id

        chain = _attribute_chain(node)
        if not chain:
            return raw, None

        first, *rest = chain
        if first in {"self", "cls"} and self.class_qn:
            return raw, ".".join([self.class_qn, *rest]) if rest else self.class_qn
        if first in self.variable_types:
            return raw, ".".join([self.variable_types[first], *rest])
        imported = self.module_context.resolve_name(first)
        if imported:
            return raw, ".".join([imported, *rest]) if rest else imported
        return raw, None

    def visit_Assign(self, node: ast.Assign) -> Any:
        if isinstance(node.value, ast.Call):
            _, qn = self._resolve_callable(node.value.func)
            if qn:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.variable_types[target.id] = qn
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if isinstance(node.target, ast.Name):
            annotation_qn: str | None = None
            if isinstance(node.annotation, ast.Name):
                annotation_qn = (
                    self.module_context.resolve_name(node.annotation.id)
                    or f"{self.module}.{node.annotation.id}"
                )
            elif isinstance(node.annotation, ast.Attribute):
                _, annotation_qn = self._resolve_callable(node.annotation)
            if annotation_qn:
                self.variable_types[node.target.id] = annotation_qn
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> Any:
        self.assertion_count += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        raw, qn = self._resolve_callable(node.func)
        self.calls.append(CallRecord(raw=raw, qualified_name=qn, line=node.lineno))

        call_name = raw.lower()
        if (
            call_name.startswith("assert")
            or ".assert" in call_name
            or call_name.endswith("pytest.raises")
            or call_name == "pytest.raises"
            or call_name.endswith("pytest.warns")
            or call_name == "pytest.warns"
        ):
            self.assertion_count += 1
        self.generic_visit(node)


def _analyze_python_file(path: Path, repo_root: Path) -> list[SymbolRecord]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    module = _module_name(path, repo_root)
    rel = _relative(path, repo_root)
    context = _python_imports(tree, module)
    records: list[SymbolRecord] = []

    def analyze_function(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_qn: str | None,
    ) -> None:
        qn = (
            f"{class_qn}.{node.name}"
            if class_qn
            else f"{module}.{node.name}" if module else node.name
        )
        inspector = _PythonFunctionInspector(context, module, class_qn)
        for statement in node.body:
            inspector.visit(statement)
        records.append(
            SymbolRecord(
                language="python",
                file=rel,
                kind="method" if class_qn else "function",
                symbol=node.name,
                qualified_name=qn,
                line=node.lineno,
                calls=inspector.calls,
                assertion_count=inspector.assertion_count,
            )
        )

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_qn = f"{module}.{node.name}" if module else node.name
            records.append(
                SymbolRecord(
                    language="python",
                    file=rel,
                    kind="class",
                    symbol=node.name,
                    qualified_name=class_qn,
                    line=node.lineno,
                )
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    analyze_function(child, class_qn)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            analyze_function(node, None)

    return records


# ---------------------------------------------------------------------------
# External analyzers
# ---------------------------------------------------------------------------


def _parse_external_json_lines(stdout: str) -> list[SymbolRecord]:
    records: list[SymbolRecord] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        calls = [
            CallRecord(
                raw=str(call.get("raw", "")),
                qualified_name=str(call.get("qualified_name", "")).strip() or None,
                line=call.get("line"),
            )
            for call in data.get("calls", [])
            if isinstance(call, dict)
        ]
        records.append(
            SymbolRecord(
                language=str(data["language"]),
                file=str(data["file"]),
                kind=str(data["kind"]),
                symbol=str(data["symbol"]),
                qualified_name=str(data["qualified_name"]),
                line=data.get("line"),
                calls=calls,
                assertion_count=int(data.get("assertion_count", 0)),
            )
        )
    return records


def _analyze_java(
    files: list[Path],
    repo_root: Path,
    helper_path: Path,
) -> tuple[list[SymbolRecord], str | None]:
    if not files:
        return [], None
    java = shutil.which("java")
    if not java:
        return [], "java executable was not found."
    if not helper_path.exists():
        return [], f"Java analyzer helper was not found: {helper_path}"

    records: list[SymbolRecord] = []
    batch_size = 200
    for offset in range(0, len(files), batch_size):
        batch = files[offset : offset + batch_size]
        command = [java, str(helper_path), str(repo_root), *[str(path) for path in batch]]
        completed = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            return [], f"Java AST analyzer failed: {message}"
        try:
            records.extend(_parse_external_json_lines(completed.stdout))
        except (json.JSONDecodeError, KeyError, ValueError) as error:
            return [], f"Java AST analyzer produced invalid output: {error}"
    return records, None


def _analyze_typescript(
    files: list[Path],
    repo_root: Path,
    helper_path: Path,
) -> tuple[list[SymbolRecord], str | None]:
    if not files:
        return [], None
    node = shutil.which("node")
    if not node:
        return [], "node executable was not found."
    if not helper_path.exists():
        return [], f"TypeScript analyzer helper was not found: {helper_path}"

    records: list[SymbolRecord] = []
    batch_size = 200
    for offset in range(0, len(files), batch_size):
        batch = files[offset : offset + batch_size]
        command = [node, str(helper_path), str(repo_root), *[str(path) for path in batch]]
        completed = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            return [], f"TypeScript AST analyzer failed: {message}"
        try:
            records.extend(_parse_external_json_lines(completed.stdout))
        except (json.JSONDecodeError, KeyError, ValueError) as error:
            return [], f"TypeScript AST analyzer produced invalid output: {error}"
    return records, None


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------


def _analysis_config(policy: dict[str, Any]) -> dict[str, Any]:
    config = policy.get("source_analysis", {})
    if not isinstance(config, dict):
        config = {}
    return config


def _language_file_groups(files: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {"python": [], "java": [], "typescript": []}
    for path in files:
        language = LANGUAGE_BY_EXTENSION.get(path.suffix.lower())
        if language:
            groups[language].append(path)
    return groups


def _test_file_summary(records: list[SymbolRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        item = grouped.setdefault(
            record.file,
            {
                "file": record.file,
                "calls": [],
                "assertion_count": 0,
            },
        )
        item["assertion_count"] += record.assertion_count
        item["calls"].extend(call.to_dict() for call in record.calls)
    result: list[dict[str, Any]] = []
    for file_value in sorted(grouped):
        item = grouped[file_value]
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for call in item["calls"]:
            key = (str(call.get("raw", "")), str(call.get("qualified_name", "")))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(call)
        item["calls"] = deduped
        result.append(item)
    return result


def analyze_repository(
    repo_root: Path,
    policy: dict[str, Any],
    scripts_dir: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    scripts_dir = (scripts_dir or Path(__file__).resolve().parent).resolve()
    config = _analysis_config(policy)

    production_roots = [str(v) for v in config.get("production_roots", ["src", "app"])]
    test_roots = [str(v) for v in config.get("test_roots", ["tests", "test", "src/test"])]
    test_file_patterns = [
        str(v)
        for v in config.get(
            "test_file_patterns",
            [
                "**/test_*.py",
                "**/*_test.py",
                "**/*.test.ts",
                "**/*.test.tsx",
                "**/*.spec.ts",
                "**/*.spec.tsx",
                "**/*.test.js",
                "**/*.test.jsx",
                "**/*.spec.js",
                "**/*.spec.jsx",
                "**/__tests__/**",
            ],
        )
    ]
    extensions = {
        str(v).lower() if str(v).startswith(".") else "." + str(v).lower()
        for v in config.get("include_extensions", sorted(SUPPORTED_EXTENSIONS))
    }
    extensions &= SUPPORTED_EXTENSIONS
    exclude_globs = [
        str(v)
        for v in config.get(
            "exclude_globs",
            [
                "**/.venv/**",
                "**/venv/**",
                "**/node_modules/**",
                "**/dist/**",
                "**/build/**",
                "**/generated/**",
                "**/__pycache__/**",
            ],
        )
    ]

    production_files = _discover_files(
        repo_root, production_roots, extensions, exclude_globs
    )
    test_files = _discover_files(repo_root, test_roots, extensions, exclude_globs)

    # Front-end projects frequently colocate tests under ``src`` (for example
    # ``UserService.test.ts`` or ``__tests__/``). Those files must be classified
    # as tests even when they live under a broad production root.
    colocated_tests = [
        path
        for path in production_files
        if _matches_any(_relative(path, repo_root), test_file_patterns)
    ]
    test_files = sorted(
        set(test_files) | set(colocated_tests),
        key=lambda p: _relative(p, repo_root),
    )

    all_files = sorted(
        set(production_files) | set(test_files),
        key=lambda p: _relative(p, repo_root),
    )

    test_set = {_relative(path, repo_root) for path in test_files}
    # Test roots take precedence over broad production roots such as ``src``.
    production_set = {
        _relative(path, repo_root)
        for path in production_files
        if _relative(path, repo_root) not in test_set
    }
    groups = _language_file_groups(all_files)

    analyzer_status: dict[str, dict[str, Any]] = {
        "python": {"status": "NOT_APPLICABLE", "files": 0},
        "java": {"status": "NOT_APPLICABLE", "files": 0},
        "typescript": {"status": "NOT_APPLICABLE", "files": 0},
    }
    all_records: list[SymbolRecord] = []

    python_files = groups["python"]
    if python_files:
        analyzer_status["python"] = {"status": "AVAILABLE", "files": len(python_files)}
        for path in python_files:
            try:
                all_records.extend(_analyze_python_file(path, repo_root))
            except (SyntaxError, UnicodeDecodeError) as error:
                analyzer_status["python"] = {
                    "status": "ERROR",
                    "files": len(python_files),
                    "error": str(error),
                }
                break

    java_files = groups["java"]
    if java_files:
        records, error = _analyze_java(
            java_files,
            repo_root,
            scripts_dir / "JavaAstAnalyzer.java",
        )
        if error:
            analyzer_status["java"] = {
                "status": "UNAVAILABLE",
                "files": len(java_files),
                "error": error,
            }
        else:
            analyzer_status["java"] = {
                "status": "AVAILABLE",
                "files": len(java_files),
            }
            all_records.extend(records)

    ts_files = groups["typescript"]
    if ts_files:
        records, error = _analyze_typescript(
            ts_files,
            repo_root,
            scripts_dir / "typescript_ast_analyzer.cjs",
        )
        if error:
            analyzer_status["typescript"] = {
                "status": "UNAVAILABLE",
                "files": len(ts_files),
                "error": error,
            }
        else:
            analyzer_status["typescript"] = {
                "status": "AVAILABLE",
                "files": len(ts_files),
            }
            all_records.extend(records)

    production_records = [
        record for record in all_records if record.file in production_set
    ]
    test_records = [record for record in all_records if record.file in test_set]

    production_records.sort(key=lambda item: (item.file, item.qualified_name, item.kind))
    test_records.sort(key=lambda item: (item.file, item.qualified_name, item.kind))

    return {
        "version": AST_INDEX_VERSION,
        "source_fingerprint": _fingerprint(all_files, repo_root),
        "source_files": [_relative(path, repo_root) for path in all_files],
        "production_roots": production_roots,
        "test_roots": test_roots,
        "test_file_patterns": test_file_patterns,
        "analyzers": analyzer_status,
        "production_symbols": [record.to_dict() for record in production_records],
        "test_symbols": [record.to_dict() for record in test_records],
        "test_files": _test_file_summary(test_records),
    }


def canonical_index(index: dict[str, Any]) -> str:
    return json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_index(path: Path, index: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def analyzer_language_for_file(file_value: str) -> str | None:
    return LANGUAGE_BY_EXTENSION.get(Path(file_value).suffix.lower())


def symbol_index_by_qn(index: dict[str, Any], *, tests: bool = False) -> dict[str, dict[str, Any]]:
    key = "test_symbols" if tests else "production_symbols"
    result: dict[str, dict[str, Any]] = {}
    for item in index.get(key, []):
        if isinstance(item, dict) and item.get("qualified_name"):
            result[str(item["qualified_name"])] = item
    return result


def symbols_for_file(
    index: dict[str, Any],
    file_value: str,
    *,
    tests: bool = False,
) -> list[dict[str, Any]]:
    key = "test_symbols" if tests else "production_symbols"
    return [
        item
        for item in index.get(key, [])
        if isinstance(item, dict) and str(item.get("file", "")) == file_value
    ]


def find_symbol(
    index: dict[str, Any],
    file_value: str,
    symbol: str | None,
    qualified_name: str | None,
    *,
    tests: bool = False,
) -> dict[str, Any] | None:
    candidates = symbols_for_file(index, file_value, tests=tests)
    if qualified_name:
        for item in candidates:
            if str(item.get("qualified_name", "")) == qualified_name:
                return item
        return None
    if symbol:
        exact = [item for item in candidates if str(item.get("symbol", "")) == symbol]
        if len(exact) == 1:
            return exact[0]
        if exact:
            return exact[0]
    return None


def resolved_call_targets(symbol_record: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for call in symbol_record.get("calls", []):
        if not isinstance(call, dict):
            continue
        qn = str(call.get("qualified_name", "")).strip()
        if qn:
            result.add(qn)
    return result


def production_call_graph(index: dict[str, Any]) -> dict[str, set[str]]:
    known = set(symbol_index_by_qn(index).keys())
    graph: dict[str, set[str]] = {}
    for symbol in index.get("production_symbols", []):
        if not isinstance(symbol, dict):
            continue
        qn = str(symbol.get("qualified_name", ""))
        if not qn:
            continue
        targets: set[str] = set()
        for call_target in resolved_call_targets(symbol):
            if call_target in known:
                targets.add(call_target)
            else:
                # Syntactic analyzers may omit package/module prefixes. Resolve a
                # unique suffix match without guessing when multiple matches exist.
                matches = [candidate for candidate in known if candidate.endswith("." + call_target)]
                if len(matches) == 1:
                    targets.add(matches[0])
        graph[qn] = targets
    return graph


def reachable_targets(
    start_targets: Iterable[str],
    graph: dict[str, set[str]],
    max_depth: int,
) -> set[str]:
    visited: set[str] = set()
    frontier = set(start_targets)
    depth = 0
    while frontier and depth <= max_depth:
        next_frontier: set[str] = set()
        for target in frontier:
            if target in visited:
                continue
            visited.add(target)
            next_frontier |= graph.get(target, set())
        frontier = next_frontier - visited
        depth += 1
    return visited


def mapped_production_targets(
    trace_map: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, set[str]]:
    """Return Requirement Reference -> production qualified names covered by mapping.

    Mapping granularity is intentionally respected:
    - file-only mapping covers every symbol in that file;
    - class mapping covers the class and its descendant methods;
    - function/method mapping covers only the exact symbol.
    """

    by_file: dict[str, list[dict[str, Any]]] = {}
    by_qn = symbol_index_by_qn(index)
    for item in index.get("production_symbols", []):
        if isinstance(item, dict):
            by_file.setdefault(str(item.get("file", "")), []).append(item)

    result: dict[str, set[str]] = {}
    for entry in trace_map.get("entries", []):
        if not isinstance(entry, dict):
            continue
        requirement_ref = str(entry.get("requirement_reference", "")).strip()
        if not requirement_ref:
            continue
        covered: set[str] = set()
        for mapping in entry.get("implementation", []) or []:
            if isinstance(mapping, str):
                file_value = mapping.strip()
                symbol = None
                qn = None
            elif isinstance(mapping, dict):
                file_value = str(mapping.get("file", "")).strip()
                symbol = str(mapping.get("symbol", "")).strip() or None
                qn = str(mapping.get("qualified_name", "")).strip() or None
            else:
                continue

            if not file_value:
                continue
            if qn and qn in by_qn:
                covered.add(qn)
                if str(by_qn[qn].get("kind", "")) == "class":
                    covered |= {candidate for candidate in by_qn if candidate.startswith(qn + ".")}
                continue
            if symbol:
                candidates = [
                    item
                    for item in by_file.get(file_value, [])
                    if str(item.get("symbol", "")) == symbol
                ]
                for item in candidates:
                    item_qn = str(item.get("qualified_name", ""))
                    covered.add(item_qn)
                    if str(item.get("kind", "")) == "class":
                        covered |= {
                            candidate for candidate in by_qn if candidate.startswith(item_qn + ".")
                        }
                continue
            covered |= {
                str(item.get("qualified_name", ""))
                for item in by_file.get(file_value, [])
                if str(item.get("qualified_name", ""))
            }
        # A mapped method/function inside a class also justifies the container
        # class itself; otherwise every method-level mapping would create a
        # false ORPHAN_IMPLEMENTATION for its owning class.
        class_qns = {
            qn
            for qn, item in by_qn.items()
            if str(item.get("kind", "")) == "class"
        }
        for candidate in list(covered):
            for class_qn in class_qns:
                if candidate.startswith(class_qn + "."):
                    covered.add(class_qn)
        result[requirement_ref] = covered
    return result


def orphan_production_symbols(
    trace_map: dict[str, Any],
    index: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    config = policy.get("implementation_analysis", {})
    if not isinstance(config, dict) or not bool(config.get("detect_orphan_symbols", False)):
        return []

    candidate_kinds = {
        str(value)
        for value in config.get("candidate_kinds", ["class", "function", "method"])
    }
    ignore_private = bool(config.get("ignore_private_symbols", True))
    ignore_symbol_patterns = [str(value) for value in config.get("ignore_symbol_patterns", [])]
    ignore_file_patterns = [str(value) for value in config.get("ignore_file_patterns", [])]

    covered = set().union(*mapped_production_targets(trace_map, index).values()) if trace_map.get("entries") else set()
    orphans: list[dict[str, Any]] = []
    for item in index.get("production_symbols", []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", ""))
        symbol = str(item.get("symbol", ""))
        qn = str(item.get("qualified_name", ""))
        file_value = str(item.get("file", ""))
        if kind not in candidate_kinds:
            continue
        if ignore_private and (symbol.startswith("_") or ".__" in qn):
            continue
        if _matches_any(file_value, ignore_file_patterns):
            continue
        if _matches_any(qn, ignore_symbol_patterns):
            continue
        if qn not in covered:
            orphans.append(item)
    return orphans


def find_test_record_for_mapping(
    index: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any] | None:
    file_value = str(mapping.get("file", "")).strip()
    symbol = str(mapping.get("symbol", "")).strip() or None
    qn = str(mapping.get("qualified_name", "")).strip() or None
    test_id = str(mapping.get("test_id", "")).strip()

    if file_value:
        record = find_symbol(index, file_value, symbol, qn, tests=True)
        if record:
            return record
        if test_id:
            leaf = test_id.split("::")[-1].split("[")[0]
            candidates = [
                item
                for item in symbols_for_file(index, file_value, tests=True)
                if str(item.get("symbol", "")) == leaf
                or str(item.get("symbol", "")).endswith(leaf)
            ]
            if len(candidates) == 1:
                return candidates[0]
    return None


def test_file_record(index: dict[str, Any], file_value: str) -> dict[str, Any] | None:
    for item in index.get("test_files", []):
        if isinstance(item, dict) and str(item.get("file", "")) == file_value:
            return item
    return None


def resolve_known_targets(targets: Iterable[str], known_qns: set[str]) -> set[str]:
    result: set[str] = set()
    for target in targets:
        if target in known_qns:
            result.add(target)
            continue
        matches = [candidate for candidate in known_qns if candidate.endswith("." + target)]
        if len(matches) == 1:
            result.add(matches[0])
    return result
