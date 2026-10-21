#!/usr/bin/env python3
"""
Traceability Validator（注釈方式）

要件・ADDR・実装タスク等の文書に書かれたIDと、
Production Code・Test Codeの `trace:` 注釈を正規表現で読み、
トレーサビリティの検査（C01〜C11）と、
派生成果物（Trace Map、要件トレーサビリティ表、確認結果、ADDR別一覧）の生成を行う。

AST解析は使わない。正本は各成果物の中のID参照だけで、
このスクリプトが出力するファイルはすべて毎回作り直す派生成果物である。

使い方:
  python .github/skills/traceability-audit/scripts/trace_check.py --scope IMPLEMENTATION

終了コード:
  0 = PASS（警告だけの場合を含む）
  1 = FAIL
  2 = Policy・引数の誤り
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SCOPES = ("REQUIREMENTS", "ARCHITECTURE", "ADDR", "IMPLEMENTATION", "UNIT_TEST", "INTEGRATION_TEST", "FULL")
DOC_KINDS = (
    "requirement",
    "acceptance",
    "addr",
    "entity",
    "file_definition",
    "task",
    "change",
)
CHECK_IDS = tuple(f"C{number:02d}" for number in range(1, 12))
DEFAULT_POLICY = ".github/skills/traceability-audit/policy/traceability-policy.yaml"

# 問題の原因がある成果物の種類 → 差し戻す工程
ROUTE_BY_ORIGIN = {
    "requirement": "REQUIREMENTS",
    "acceptance": "REQUIREMENTS",
    "addr": "ADDR",
    "entity": "ARCHITECTURE",
    "file_definition": "ARCHITECTURE",
    "task": "ARCHITECTURE",
    "change": "IMPLEMENTATION",
    "code": "IMPLEMENTATION",
    "unit_test": "UNIT_TEST",
    "integration_test": "INTEGRATION_TEST",
    "integration_plan": "INTEGRATION_TEST",
    "commit": "IMPLEMENTATION",
}

HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^(\s*)[-*+]\s+(.*)$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
# 表の行で定義されたIDの「名前」として使う列（見出しの名前）。なければ2列目。
TITLE_COLUMNS = (
    "機能名", "要件名", "名称", "タイトル", "Title", "要件項目", "データ名",
    "IF名称", "画面名", "帳票名", "ユースケース名", "条件", "受入条件",
)
FENCE = re.compile(r"^\s*(```|~~~)")
TOP_DEF = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)")
HASH_TRACE = re.compile(r"^\s*#\s*trace\s*:\s*(?P<v>.*?)\s*$", re.I)
TEMPLATE_TRACE = re.compile(
    r"\{#\s*trace\s*:\s*(?P<v>.*?)\s*#\}|<!--\s*trace\s*:\s*(?P<w>.*?)\s*-->", re.I
)
SLASH_TRACE = re.compile(
    r"//\s*trace\s*:\s*(?P<v>.*?)\s*$|/\*\s*trace\s*:\s*(?P<w>.*?)\s*\*/", re.I
)
TOKEN_SPLIT = re.compile(r"[\s,、，/／]+")

HASH_EXT = {".py", ".pyi", ".toml", ".yaml", ".yml", ".txt", ".cfg", ".ini", ".sh", ".rb"}
TEMPLATE_EXT = {".html", ".htm", ".jinja", ".jinja2", ".j2", ".tpl"}
SLASH_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".go",
    ".c", ".cpp", ".cs", ".css", ".scss", ".swift",
}


class PolicyError(Exception):
    """Policyファイルの読み込み・内容の誤り。"""


# ============================================================
# データ構造
# ============================================================


@dataclass
class Element:
    """文書の中で定義されたID 1件。"""

    id: str
    kind: str
    file: str
    line: int
    title: str = ""
    refs: set[str] = field(default_factory=set)
    status: str = ""
    design_type: str = ""
    req_refs: set[str] = field(default_factory=set)  # ADDRの関連要件欄だけ
    req_section_found: bool = False


@dataclass
class Symbol:
    name: str
    line: int
    own_ids: list[str] = field(default_factory=list)
    own_line: int = 0


@dataclass
class SourceFile:
    """注釈を読む対象のファイル（Production Code・Test Code）。"""

    path: str
    role: str  # code / unit_test / integration_test
    header_ids: list[str] = field(default_factory=list)
    header_line: int = 0
    symbols: list[Symbol] = field(default_factory=list)
    trace_lines: int = 0
    bad_tokens: list[tuple[int, str]] = field(default_factory=list)
    per_symbol_supported: bool = False

    def effective_ids(self, symbol: Symbol) -> list[str]:
        return symbol.own_ids or self.header_ids

    def all_ids(self) -> set[str]:
        ids = set(self.header_ids)
        for symbol in self.symbols:
            ids.update(symbol.own_ids)
        return ids


@dataclass
class PlanCase:
    case_id: str
    origin: str
    requirement_ids: list[str]
    related_addr: list[str]


@dataclass
class Issue:
    check: str
    level: str  # FAIL / WARN
    classification: str
    location: str
    message: str
    route: str

    def text(self) -> str:
        return f"[{self.check}] {self.location}: {self.message}（差し戻し先: {self.route}）"


# ============================================================
# Policy・ID規則
# ============================================================


def load_policy(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PolicyError(f"Policyが見つかりません: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise PolicyError(f"PolicyのYAMLを読めません: {error}") from error
    if not isinstance(data, dict):
        raise PolicyError("Policyの形式が正しくありません。")
    if data.get("version") != 3:
        raise PolicyError("Policyのversionは3である必要があります（注釈方式）。")
    for key in ("ids", "sources", "addr", "code", "unit_test", "integration_test", "checks"):
        if key not in data or not isinstance(data[key], dict):
            raise PolicyError(f"Policyに `{key}` がありません。")
    for key in ("outputs", "integration", "definition_fields"):
        if not isinstance(data.get(key, {}), dict):
            raise PolicyError(f"{key} must be an object")
    for kind in DOC_KINDS:
        prefixes = data["ids"].get(kind, [])
        if not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
            raise PolicyError(f"ids.{kind} must be a string array")
    for key in ("common_exclude", "document_exclude"):
        values = data.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise PolicyError(f"{key} must be a string array")
    for config in (data["code"], data["unit_test"], data["integration_test"]):
        allowed = config.get("allowed", [])
        if not isinstance(allowed, list) or any(kind not in DOC_KINDS for kind in allowed):
            raise PolicyError("allowed must contain known ID kinds")
    if not isinstance(data["checks"].get("scopes"), dict):
        raise PolicyError("checks.scopes must be an object")
    scopes = data["checks"].get("scopes", {})
    for scope in SCOPES:
        if scope not in scopes:
            raise PolicyError(f"Policyの checks.scopes に `{scope}` がありません。")
        if not isinstance(scopes[scope], dict):
            raise PolicyError(f"checks.scopes.{scope} must be an object")
        for level in ("fail", "warn"):
            if not isinstance(scopes[scope].get(level, []), list):
                raise PolicyError(f"checks.scopes.{scope}.{level} must be an array")
            unknown = set(scopes[scope].get(level, [])) - set(CHECK_IDS)
            if unknown:
                raise PolicyError(f"checks.scopes.{scope}.{level} に未知の検査があります: {sorted(unknown)}")
    for config in (data["sources"], data["code"], data["unit_test"], data["integration_test"]):
        for key, values in config.items():
            if key in ("include", "exclude", "junit") or config is data["sources"]:
                if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                    raise PolicyError(f"{key} must be a string array")
                for value in values:
                    safe_relative(value)
    safe_relative(data.get("outputs", {}).get("dir", "reports/traceability"))
    for config in (data["unit_test"], data["integration_test"]):
        for key in ("plan", "execution"):
            if key in config:
                safe_relative(config[key])
    return data


class IdRules:
    """接頭辞からIDの種類を判定し、テキストからIDを拾う。"""

    def __init__(self, policy: dict[str, Any]) -> None:
        ids = policy["ids"]
        self.prefix_kind: dict[str, str] = {}
        for kind in DOC_KINDS:
            for prefix in ids.get(kind, []) or []:
                prefix = str(prefix).strip()
                if not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
                    raise PolicyError(f"ids.{kind} の接頭辞が不正です: {prefix!r}")
                if prefix in self.prefix_kind:
                    raise PolicyError(f"接頭辞 {prefix} が複数の種類に設定されています。")
                self.prefix_kind[prefix] = kind
        if not self.prefix_kind:
            raise PolicyError("ids に接頭辞が1つもありません。")
        digits = ids.get("min_digits", 3)
        if type(digits) is not int or digits < 1:
            raise PolicyError("ids.min_digits must be a positive integer")
        alternation = "|".join(sorted(map(re.escape, self.prefix_kind), key=len, reverse=True))
        core = rf"(?:{alternation})(?:-[A-Z][A-Z0-9]*)*-\d{{{digits},}}"
        self.pattern = re.compile(rf"(?<![A-Za-z0-9_\-]){core}(?![A-Za-z0-9_])")
        self.full = re.compile(core)

    def kind_of(self, value: str) -> str | None:
        return self.prefix_kind.get(value.split("-", 1)[0])

    def find(self, text: str) -> list[str]:
        return [match.group(0) for match in self.pattern.finditer(text)]

    def is_id(self, token: str) -> bool:
        return bool(self.full.fullmatch(token))


# ============================================================
# ファイル収集
# ============================================================


def safe_relative(value: str) -> None:
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts or re.match(r"^[A-Za-z]:", value):
        raise PolicyError(f"Path must stay inside repository: {value}")


def collect_files(root: Path, include: list[str], exclude: list[str]) -> list[str]:
    found: set[str] = set()
    for pattern in include or []:
        safe_relative(pattern)
        for path in root.glob(pattern):
            if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                continue
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, ex) for ex in exclude or []):
                continue
            found.add(rel)
    return sorted(found)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="replace")


# ============================================================
# 文書（Markdown）の読み取り
# ============================================================


def blank_html_comments(text: str) -> str:
    return HTML_COMMENT.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def split_front_matter(lines: list[str]) -> tuple[dict[str, Any], int]:
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                try:
                    data = yaml.safe_load("\n".join(lines[1:index])) or {}
                except yaml.YAMLError:
                    data = {}
                return (data if isinstance(data, dict) else {}), index + 1
    return {}, 0


def clean_cell(value: str) -> str:
    return value.strip().strip("*`").strip()


def title_column(header: list[str]) -> int:
    for name in TITLE_COLUMNS:
        if name in header:
            return header.index(name)
    return 1


def strip_markup(value: str) -> str:
    value = re.sub(r"[`*]", "", value)
    return re.sub(r"\s+", " ", value).strip(" ：:-")


def heading_levels(lines: list[str], start: int) -> list[tuple[int, int, str]]:
    result = []
    in_fence = False
    for index in range(start, len(lines)):
        if FENCE.match(lines[index]):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(lines[index])
        if match:
            result.append((index, len(match.group(1)), match.group(2)))
    return result


def section_end(headings: list[tuple[int, int, str]], index: int, level: int, total: int) -> int:
    for other_index, other_level, _ in headings:
        if other_index > index and other_level <= level:
            return other_index
    return total


def parse_document(
    rel: str,
    text: str,
    kind: str,
    rules: IdRules,
    definition_fields: list[str] | None = None,
) -> tuple[list[Element], list[tuple[str, int]]]:
    """1つの文書から、その種類のID定義と、全ID参照（ID・行番号）を拾う。"""

    lines = blank_html_comments(text).split("\n")
    front, start = split_front_matter(lines)
    headings = heading_levels(lines, start)
    elements: list[Element] = []
    references: list[tuple[str, int]] = []

    def own_kind(value: str) -> bool:
        return rules.is_id(value) and rules.kind_of(value) == kind

    in_fence = False
    table_header: list[str] = []
    for index in range(start, len(lines)):
        line = lines[index]
        for found in rules.find(line):
            references.append((found, index + 1))
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = HEADING.match(line)
        if heading:
            body = re.sub(r"^[\d.]+\s+", "", heading.group(2)).strip()
            match = re.match(r"^[*`]*([A-Z][A-Z0-9-]*\d)[*`]*(.*)$", body)
            if match and own_kind(match.group(1)):
                level = len(heading.group(1))
                end = section_end(headings, index, level, len(lines))
                elements.append(
                    make_element(match.group(1), kind, rel, index, lines[index:end], rules, match.group(2))
                )
            continue

        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [clean_cell(cell) for cell in stripped.strip("|").split("|")]
            if index + 1 < len(lines) and TABLE_SEPARATOR.match(lines[index + 1]):
                table_header = cells
                continue
            if len(cells) > 1 and cells[0] in (definition_fields or []) and own_kind(cells[1]):
                elements.append(make_element(cells[1], kind, rel, index, lines[start:], rules, cells[1]))
                continue
            if cells and own_kind(cells[0]):
                column = title_column(table_header)
                title = cells[column] if column < len(cells) else (cells[1] if len(cells) > 1 else "")
                elements.append(make_element(cells[0], kind, rel, index, [line], rules, title))
            continue

        item = LIST_ITEM.match(line)
        if item:
            match = re.match(r"^[*`]*([A-Z][A-Z0-9-]*\d)[*`]*\s*[:：]\s*(.*)$", item.group(2))
            if match and own_kind(match.group(1)):
                indent = len(item.group(1).replace("\t", "    "))
                end = index + 1
                while end < len(lines):
                    nxt = lines[end]
                    if nxt.strip():
                        nxt_indent = len(nxt) - len(nxt.lstrip())
                        if nxt_indent <= indent or HEADING.match(nxt):
                            break
                    end += 1
                elements.append(
                    make_element(match.group(1), kind, rel, index, lines[index:end], rules, match.group(2))
                )

    if kind == "addr":
        elements = [parse_addr(rel, lines, front, start, headings, rules, references)]
        elements = [element for element in elements if element.id]
    return elements, references


def make_element(
    identifier: str,
    kind: str,
    rel: str,
    index: int,
    scope_lines: list[str],
    rules: IdRules,
    title: str,
) -> Element:
    refs: set[str] = set()
    for scope_line in scope_lines:
        refs.update(rules.find(scope_line))
    refs.discard(identifier)
    return Element(identifier, kind, rel, index + 1, strip_markup(title), refs)


def parse_addr(
    rel: str,
    lines: list[str],
    front: dict[str, Any],
    start: int,
    headings: list[tuple[int, int, str]],
    rules: IdRules,
    references: list[tuple[str, int]],
) -> Element:
    """ADDR（1ファイル＝1件）を読む。旧ADRテンプレート形式も読める。"""

    def addr_id(value: Any) -> str:
        value = str(value or "").strip()
        return value if rules.is_id(value) and rules.kind_of(value) == "addr" else ""

    identifier = addr_id(front.get("addr_id")) or addr_id(front.get("id"))
    if not identifier:
        for index, _, text in headings:
            found = [value for value in rules.find(text) if rules.kind_of(value) == "addr"]
            if found:
                identifier = found[0]
                break
    if not identifier:
        found = [value for value in rules.find(Path(rel).name) if rules.kind_of(value) == "addr"]
        identifier = found[0] if found else ""

    title = str(front.get("title") or "")
    if not title and headings:
        title = re.sub(rf"^{re.escape(identifier)}\s*", "", headings[0][2]) if identifier else headings[0][2]
        title = re.sub(r"^ADDR\s*[：:]\s*", "", title)

    status = str(front.get("status") or "").strip()
    if not status:
        for index, level, text in headings:
            if text.strip().lower() == "status":
                end = section_end(headings, index, level, len(lines))
                for body in lines[index + 1 : end]:
                    if body.strip():
                        status = body.strip()
                        break
                break
    if "/" in status or "／" in status:
        status = ""  # テンプレートのままの値は状態として扱わない

    element = Element(
        identifier,
        "addr",
        rel,
        1,
        strip_markup(title),
        status=status,
        design_type=str(front.get("design_type") or "").strip(),
    )
    element.refs = {value for value, _ in references if value != identifier}
    return element


def read_addr_requirements(
    element: Element,
    text: str,
    rules: IdRules,
    section_names: list[str],
) -> None:
    lines = blank_html_comments(text).split("\n")
    _, start = split_front_matter(lines)
    headings = heading_levels(lines, start)
    names = [name.lower() for name in section_names]
    for index, level, heading_text in headings:
        if any(name in heading_text.lower() for name in names):
            element.req_section_found = True
            end = section_end(headings, index, level, len(lines))
            body = lines[index + 1 : end]
            canonical_table = any("区分" in line and "参照先" in line for line in body)
            for line in body:
                if canonical_table:
                    cells = [clean_cell(value) for value in line.strip().strip("|").split("|")]
                    if len(cells) < 2 or cells[0] not in ("要件", "Requirement", "Requirements"):
                        continue
                    line = cells[1]
                element.req_refs.update(rules.find(line))
    for line in lines[start:]:
        match = re.match(r"^\s*[-*]?\s*([^:：|]+)[:：](.*)$", line)
        if match and any(name in match.group(1).lower() for name in names):
            element.req_section_found = True
            element.req_refs.update(rules.find(match.group(2)))
    element.req_refs = {value for value in element.req_refs if rules.kind_of(value) == "requirement"}


# ============================================================
# Production Code・Test Code の注釈の読み取り
# ============================================================


def parse_tokens(value: str, rules: IdRules) -> tuple[list[str], list[str]]:
    good: list[str] = []
    bad: list[str] = []
    for token in TOKEN_SPLIT.split(value or ""):
        token = token.strip()
        if not token:
            continue
        if rules.is_id(token) and rules.kind_of(token):
            if token not in good:
                good.append(token)
        else:
            bad.append(token)
    return good, bad


def parse_source(rel: str, text: str, role: str, rules: IdRules) -> SourceFile:
    suffix = Path(rel).suffix.lower()
    source = SourceFile(rel, role)
    lines = text.split("\n")

    def add_header(value: str, line_no: int) -> None:
        good, bad = parse_tokens(value, rules)
        for token in good:
            if token not in source.header_ids:
                source.header_ids.append(token)
        source.bad_tokens.extend((line_no, token) for token in bad)
        source.header_line = source.header_line or line_no
        source.trace_lines += 1

    if suffix in HASH_EXT:
        # ファイル先頭の注釈 = 最初のコメントのかたまり（空行またはコードまで）の中の trace 行
        header_end = len(lines)
        seen_comment = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                if seen_comment:
                    header_end = index
                    break
                continue
            if stripped.startswith("#"):
                seen_comment = True
                match = HASH_TRACE.match(line)
                if match:
                    add_header(match.group("v"), index + 1)
                continue
            header_end = index
            break
        if suffix in (".py", ".pyi"):
            source.per_symbol_supported = True
            parse_python_symbols(source, lines, rules, header_end)
        else:
            source.trace_lines += sum(1 for line in lines[header_end:] if HASH_TRACE.match(line))
    elif suffix in TEMPLATE_EXT or suffix in SLASH_EXT:
        pattern = TEMPLATE_TRACE if suffix in TEMPLATE_EXT else SLASH_TRACE
        in_header = True
        comment_end = ""
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            match = pattern.search(line)
            if in_header and match and not line[:match.start()].strip() and not line[match.end():].strip():
                add_header(match.group("v") or match.group("w") or "", index + 1)
                continue
            if match:
                source.trace_lines += 1
            if comment_end:
                if comment_end in stripped:
                    remainder = stripped.split(comment_end, 1)[1]
                    comment_end = ""
                    if remainder.strip():
                        in_header = False
                continue
            if in_header:
                starts = (("{#", "#}"), ("<!--", "-->")) if suffix in TEMPLATE_EXT else (("/*", "*/"),)
                opener = next(((opening, closing) for opening, closing in starts if stripped.startswith(opening)), None)
                if opener:
                    closing = opener[1]
                    if closing not in stripped:
                        comment_end = closing
                    elif stripped.split(closing, 1)[1].strip():
                        in_header = False
                elif not (suffix in SLASH_EXT and stripped.startswith(("//", "#!"))):
                    in_header = False
    return source


def parse_python_symbols(source: SourceFile, lines: list[str], rules: IdRules, start: int) -> None:
    """トップレベルのclass・関数と、その直前の `# trace:` 注釈を拾う（ASTは使わない）。"""

    in_string = False
    pending: tuple[list[str], int] | None = None
    depth = 0

    for index in range(start, len(lines)):
        line = lines[index]
        stripped = line.strip()
        quotes = line.count('"""') + line.count("'''")
        if in_string:
            if quotes % 2 == 1:
                in_string = False
            continue
        if depth > 0:
            depth = max(0, depth + bracket_delta(line))
            continue

        match = HASH_TRACE.match(line)
        if match and not line[:1].isspace():
            good, bad = parse_tokens(match.group("v"), rules)
            source.bad_tokens.extend((index + 1, token) for token in bad)
            source.trace_lines += 1
            pending = (good, index + 1)
            continue
        if match:
            source.trace_lines += 1
        if not stripped:
            pending = None
            continue
        if stripped.startswith("#"):
            continue
        if line.startswith("@"):
            depth = max(0, bracket_delta(line))
            continue
        definition = TOP_DEF.match(line)
        if definition:
            symbol = Symbol(definition.group(1), index + 1)
            if pending:
                symbol.own_ids, symbol.own_line = pending
            source.symbols.append(symbol)
            pending = None
            if quotes % 2 == 1:
                in_string = True
            continue
        pending = None
        if quotes % 2 == 1:
            in_string = True


def bracket_delta(line: str) -> int:
    code = re.sub(r"(\"[^\"]*\"|'[^']*')", "", line.split("#", 1)[0])
    return sum(code.count(ch) for ch in "([{") - sum(code.count(ch) for ch in ")]}")


def considered_symbols(source: SourceFile) -> list[Symbol]:
    if source.role == "code":
        return source.symbols
    return [
        symbol
        for symbol in source.symbols
        if symbol.name.startswith("test") or "Test" in symbol.name
    ]


# ============================================================
# 結合テスト計画・テスト結果（JUnit XML）
# ============================================================


def read_plan(path: Path) -> list[PlanCase]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError("Integration plan must contain a cases array")
    cases = []
    seen = set()
    for item in data["cases"]:
        if not isinstance(item, dict) or not str(item.get("case_id", "")).strip():
            raise ValueError("Integration plan case_id is missing")
        if item["case_id"] in seen:
            raise ValueError("Integration plan case_id is duplicated")
        seen.add(item["case_id"])

        def as_list(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            return [item.strip() for item in re.split(r"[,、，\s]+", str(value)) if item.strip()]

        cases.append(
            PlanCase(
                str(item["case_id"]).strip(),
                str(item.get("origin", "")).strip(),
                as_list(item.get("requirement_id")),
                as_list(item.get("related_adr")),
            )
        )
    return cases


def read_junit(root: Path, patterns: list[str]) -> list[tuple[str, str, str]]:
    """(classname, name, status) の一覧。status は PASS / FAIL / SKIP。"""

    results = []
    for pattern in patterns or []:
        for path in sorted(root.glob(pattern)):
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue
            for case in tree.iter("testcase"):
                status = "PASS"
                if case.find("failure") is not None or case.find("error") is not None:
                    status = "FAIL"
                elif case.find("skipped") is not None:
                    status = "SKIP"
                name = re.sub(r"\[.*\]$", "", case.get("name", ""))
                results.append((case.get("classname", ""), name, status))
    return results


def symbol_status(source: SourceFile, symbol: Symbol, junit: list[tuple[str, str, str]]) -> str:
    module = source.path.rsplit(".", 1)[0].split("/")
    statuses = []
    for classname, name, status in junit:
        parts = classname.split(".")
        if symbol.name[:1].isupper() and not symbol.name.startswith("test"):
            if not parts or parts[-1] != symbol.name:
                continue
            parts = parts[:-1]
        elif name != symbol.name:
            continue
        if parts == module:
            statuses.append(status)
    if not statuses:
        return "NOT_RUN"
    if "FAIL" in statuses:
        return "FAIL"
    if "SKIP" in statuses:
        return "SKIP"
    return "PASS"


# ============================================================
# Git
# ============================================================


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hashes(root: Path, paths: list[str]) -> list[dict[str, str]]:
    return [{"path": relative, "sha256": hashlib.sha256((root / relative).read_bytes()).hexdigest()} for relative in sorted(set(paths)) if (root / relative).is_file()]


def test_input_fingerprint(root: Path, policy: dict[str, Any], role: str) -> str:
    common = policy.get("common_exclude", [])
    paths = set()
    for patterns in policy["sources"].values():
        paths.update(collect_files(root, patterns, common + policy.get("document_exclude", [])))
    for key in ("code", role):
        paths.update(collect_files(root, policy[key].get("include", []), common + policy[key].get("exclude", [])))
    for relative in (policy[role].get("plan"), "reports/architecture/design-manifest.json", "reports/architecture/design-input.json", "reports/architecture/addr-result.json", "reports/architecture/design-gate.json", "reports/addr/implementation-handoff.json"):
        if relative and (root / relative).is_file():
            paths.add(relative)
    payload = {"files": file_hashes(root, sorted(paths)), "policy": policy}
    return text_hash(json.dumps(payload, sort_keys=True))


def record_test_run(root: Path, policy: dict[str, Any], role: str) -> None:
    patterns = policy[role].get("junit", [])
    results = file_hashes(root, collect_files(root, patterns, []))
    if not results:
        raise PolicyError("Test execution recording requires existing JUnit results")
    fingerprint = test_input_fingerprint(root, policy, role)
    commit = git(root, "rev-parse", "HEAD")
    dirty = git(root, "status", "--porcelain")
    revision = commit.strip() if commit and not (dirty and dirty.strip()) else f"WORKTREE:{fingerprint}"
    payload = {"revision": revision, "git_commit": commit.strip() if commit else None, "input_fingerprint": fingerprint, "junit_files": results}
    destination = policy[role].get("execution")
    if not destination:
        raise PolicyError(f"{role}.execution is not configured")
    write(root / destination, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


# ============================================================
# 監査本体
# ============================================================


class Auditor:
    def __init__(self, root: Path, policy: dict[str, Any], scope: str) -> None:
        self.root = root
        self.policy = policy
        self.scope = scope
        self.rules = IdRules(policy)
        self.elements: dict[str, Element] = {}
        self.duplicates: list[tuple[str, str, str]] = []
        self.doc_refs: list[tuple[str, str, str, int]] = []  # (kind, file, id, line)
        self.sources: list[SourceFile] = []
        self.plan: list[PlanCase] = []
        self.junit: list[tuple[str, str, str]] = []
        self.issues: list[Issue] = []
        self.input_paths: set[str] = set()
        self.junit_by_role: dict[str, list[tuple[str, str, str]]] = {}
        self.execution: dict[str, dict[str, Any]] = {}
        self.requirement_fallback: set[str] = set()
        self.plan_error = ""
        self.workflow_unresolved: list[dict[str, Any]] = []
        scope_policy = policy["checks"]["scopes"][scope]
        self.fail_checks = set(scope_policy.get("fail", []))
        self.warn_checks = set(scope_policy.get("warn", []))

    # ---------- 読み込み ----------

    def load(self) -> None:
        ledger_path = self.root / "reports/loop-control/retry-ledger.json"
        if ledger_path.is_file():
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "failure-triage/scripts"))
            from loop_control import ledger, verified_issue
            for issue in ledger(self.root)["issues"].values():
                if issue["state"] == "UNRESOLVED":
                    verified_issue(self.root, issue)
                    self.workflow_unresolved.append({"issue_id": issue["issue_id"], "signature": issue["signature"], "impact": issue["impact"], "recommended_route": issue["recommended_route"], "status": "UNRESOLVED", "repair_cycles": issue["cycle"]})
            self.workflow_unresolved.sort(key=lambda issue: issue["issue_id"])
        common_exclude = list(self.policy.get("common_exclude", []))
        section_names = self.policy["addr"].get("related_sections", ["関連要件", "Related Requirements"])
        for kind in DOC_KINDS:
            if self.scope == "REQUIREMENTS" and kind not in ("requirement", "acceptance"):
                continue
            for rel in collect_files(self.root, self.policy["sources"].get(kind, []), common_exclude + self.policy.get("document_exclude", [])):
                self.input_paths.add(rel)
                text = read_text(self.root / rel)
                elements, references = parse_document(rel, text, kind, self.rules, self.policy.get("definition_fields", {}).get(kind, []))
                for found, line in references:
                    self.doc_refs.append((kind, rel, found, line))
                for element in elements:
                    if element.kind == "addr":
                        read_addr_requirements(element, text, self.rules, section_names)
                    self.add_element(element)

        self.load_addr_bindings()
        roles = [] if self.scope in ("REQUIREMENTS", "ARCHITECTURE", "ADDR") else [("code", self.policy["code"])]
        if self.scope in ("UNIT_TEST", "INTEGRATION_TEST", "FULL"):
            roles.append(("unit_test", self.policy["unit_test"]))
        if self.scope in ("INTEGRATION_TEST", "FULL"):
            roles.append(("integration_test", self.policy["integration_test"]))
        test_files = set()
        for section in ("unit_test", "integration_test"):
            config = self.policy[section]
            test_files.update(
                collect_files(self.root, config.get("include", []), common_exclude + config.get("exclude", []))
            )
        for role, config in roles:
            exclude = common_exclude + list(config.get("exclude", []))
            for rel in collect_files(self.root, config.get("include", []), exclude):
                if role == "code" and (rel in test_files or (Path(rel).name == "__init__.py" and not read_text(self.root / rel).strip())):
                    continue
                self.input_paths.add(rel)
                self.sources.append(parse_source(rel, read_text(self.root / rel), role, self.rules))

        plan_path = self.policy["integration_test"].get("plan")
        if plan_path and self.scope in ("INTEGRATION_TEST", "FULL"):
            if (self.root / plan_path).is_file():
                self.input_paths.add(plan_path)
            try:
                self.plan = read_plan(self.root / plan_path)
            except (ValueError, TypeError):
                self.plan_error = "Integration plan is malformed"
        for role in ("unit_test", "integration_test"):
            if role == "unit_test" and self.scope in ("REQUIREMENTS", "ARCHITECTURE", "ADDR", "IMPLEMENTATION"):
                continue
            if role == "integration_test" and self.scope not in ("INTEGRATION_TEST", "FULL"):
                continue
            config = self.policy[role]
            self.junit_by_role[role] = read_junit(self.root, config.get("junit", []))
            self.junit.extend(self.junit_by_role[role])
            self.input_paths.update(collect_files(self.root, config.get("junit", []), []))
            metadata = config.get("execution")
            if metadata and (self.root / metadata).is_file():
                self.input_paths.add(metadata)
                try:
                    value = json.loads(read_text(self.root / metadata))
                    self.execution[role] = value if isinstance(value, dict) else {}
                except ValueError:
                    self.execution[role] = {}

    def load_addr_bindings(self) -> None:
        final = self.root / "reports/architecture/design-manifest.json"
        if self.scope in ("REQUIREMENTS", "ARCHITECTURE") or not final.is_file():
            return
        try:
            manifest = json.loads(read_text(final))
            if manifest.get("version") != 2:
                return
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addr/scripts"))
            from design_common import HANDOFF, RESULT, validate_design_gate, validate_handoff
            from validate_addr import validate_addr
            errors = validate_design_gate(self.root) + validate_handoff(self.root) + validate_addr(self.root, final=True)
            self.input_paths.update({"reports/architecture/design-manifest.json", "reports/architecture/design-gate.json", RESULT, HANDOFF})
            if errors:
                for error in errors:
                    self.report("C01", "ADDR_HANDOFF_INVALID", HANDOFF, error, "ADDR")
                return
            artifacts = {item["artifact_id"]: item for item in manifest["artifacts"]}
            handoff = json.loads(read_text(self.root / HANDOFF))
            for binding in handoff["artifact_links"]:
                path = artifacts[binding["artifact_id"]]["path"]
                for identifier in binding["element_ids"]:
                    element = self.elements.get(identifier)
                    if element is None or element.file != path or element.kind not in ("task", "file_definition"):
                        self.report("C01", "ADDR_BINDING_INVALID", HANDOFF, f"Binding has no matching source definition: {identifier}", "ADDR")
                    else:
                        element.refs.add(binding["related_addr_id"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.report("C01", "ADDR_HANDOFF_INVALID", str(final), str(error), "ADDR")

    def add_element(self, element: Element) -> None:
        existing = self.elements.get(element.id)
        if existing is None:
            self.elements[element.id] = element
        elif existing.file == element.file:
            existing.refs.update(element.refs)
            existing.req_refs.update(element.req_refs)
            existing.title = existing.title or element.title
        else:
            self.duplicates.append((element.id, existing.file, element.file))

    # ---------- 補助 ----------

    def report(self, check: str, classification: str, location: str, message: str, route: str) -> None:
        if check in self.fail_checks:
            level = "FAIL"
        elif check in self.warn_checks:
            level = "WARN"
        else:
            return
        self.issues.append(Issue(check, level, classification, location, message, route))

    def runs(self, check: str) -> bool:
        return check in self.fail_checks or check in self.warn_checks

    def kinds(self, values: set[str] | list[str], *kinds: str) -> set[str]:
        return {value for value in values if self.rules.kind_of(value) in kinds}

    def addr_state(self, element: Element) -> str:
        status = element.status.lower()
        addr = self.policy["addr"]
        if status in [value.lower() for value in addr.get("retired_status", [])]:
            return "retired"
        if status in [value.lower() for value in addr.get("current_status", [])]:
            return "current"
        if status in [value.lower() for value in addr.get("proposed_status", [])]:
            return "proposed"
        return "unknown"

    def live_addrs(self) -> list[Element]:
        allowed = {"current"} | ({"proposed", "unknown"} if self.scope == "ARCHITECTURE" else set())
        return [
            element
            for element in self.elements.values()
            if element.kind == "addr" and self.addr_state(element) in allowed
        ]

    def tests(self) -> list[SourceFile]:
        return [source for source in self.sources if source.role != "code"]

    def code(self) -> list[SourceFile]:
        return [source for source in self.sources if source.role == "code"]

    # ---------- 検査 ----------

    def check_all(self, commit_range: str | None) -> None:
        self.check_architecture_gate()
        self.c01_references(commit_range)
        self.c02_retired_addr()
        self.c03_addr_requirements()
        self.c04_task_sources()
        self.c05_c06_annotations()
        self.c07_tests_have_requirements()
        self.c08_commits(commit_range)
        self.c09_addr_implemented()
        self.c10_requirements_tested()

    def check_architecture_gate(self) -> None:
        config = self.policy.get("integration", {})
        final = self.root / "reports/architecture/design-manifest.json"
        new_design = final.is_file() or any(element.id.startswith("ADDR-") for element in self.elements.values() if element.kind == "addr")
        if self.scope in ("REQUIREMENTS", "ARCHITECTURE", "ADDR") or not new_design or not config.get("preserve_architecture_gate", True):
            return
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "addr/scripts"))
        from design_common import validate_gate
        errors = validate_gate(self.root)
        for error in errors:
            self.report("C01", "ARCHITECTURE_GATE_INVALID", "reports/architecture/architecture-gate.json", error, "ARCHITECTURE")
        if errors or not config.get("allow_requirement_when_addr_not_needed", False):
            return
        result_path = self.root / "reports/architecture/addr-result.json"
        try:
            draft_path = final if final.is_file() and json.loads(read_text(final)).get("version") == 2 else self.root / "reports/architecture/design-input.json"
            result = json.loads(read_text(result_path))
            draft = json.loads(read_text(draft_path))
            rejected = {choice["target_id"] for choice in result.get("addr_creation_results", []) if choice.get("needed") is True}
            approved = {choice["target_id"] for choice in result.get("addr_creation_results", []) if choice.get("needed") is False} - rejected
            for target in draft.get("targets", []):
                if target.get("target_id") in approved:
                    self.requirement_fallback.update(target.get("basis_ids", []))
            covered = {identifier for decision in self.live_addrs() for identifier in decision.req_refs}
            self.requirement_fallback.difference_update(covered)
        except (OSError, ValueError, TypeError, KeyError):
            self.report("C01", "ARCHITECTURE_GATE_INVALID", str(result_path), "Invalid no-ADDR target approval.", "ARCHITECTURE")

    def c01_references(self, commit_range: str | None) -> None:
        if not any(element.kind == "requirement" for element in self.elements.values()):
            self.report("C01", "REQUIREMENTS_MISSING", "docs/requirements", "No primary requirement definitions were found.", "REQUIREMENTS")
        for identifier, first, second in self.duplicates:
            self.report(
                "C01", "DUPLICATE_ID", second,
                f"{identifier} が {first} でも定義されています。IDは全体で一意にしてください。",
                ROUTE_BY_ORIGIN[self.elements[identifier].kind],
            )
        seen: set[tuple[str, str]] = set()

        def check(identifier: str, origin: str, location: str) -> None:
            if identifier in self.elements or (identifier, location) in seen:
                return
            seen.add((identifier, location))
            kind = self.rules.kind_of(identifier)
            classification = {
                "requirement": "INVALID_REQUIREMENT_REFERENCE",
                "acceptance": "INVALID_REQUIREMENT_REFERENCE",
                "addr": "INVALID_ADR_REFERENCE",
            }.get(kind or "", "INVALID_REFERENCE")
            self.report(
                "C01", classification, location,
                f"{identifier} はどの成果物にも定義されていません。",
                ROUTE_BY_ORIGIN[origin],
            )

        for kind, rel, identifier, line in self.doc_refs:
            check(identifier, kind, f"{rel}:{line}")
        for source in self.sources:
            for identifier in source.header_ids:
                check(identifier, source.role, f"{source.path}:{source.header_line}")
            for symbol in source.symbols:
                for identifier in symbol.own_ids:
                    check(identifier, source.role, f"{source.path}:{symbol.own_line}")
        plan_path = self.policy["integration_test"].get("plan", "")
        if self.plan_error:
            self.report("C01", "INVALID_INTEGRATION_PLAN", plan_path, self.plan_error, "INTEGRATION_TEST")
        for case in self.plan:
            if not case.requirement_ids:
                self.report("C01", "INVALID_REQUIREMENT_REFERENCE", f"{plan_path}#{case.case_id}", "requirement_id is required", "INTEGRATION_TEST")
            for identifier in case.requirement_ids + case.related_addr:
                if self.rules.is_id(identifier):
                    check(identifier, "integration_plan", f"{plan_path}#{case.case_id}")
                else:
                    self.report(
                        "C01", "INVALID_REQUIREMENT_REFERENCE", f"{plan_path}#{case.case_id}",
                        f"{identifier!r} はIDの形式になっていません。", "INTEGRATION_TEST",
                    )
            for identifiers, kind in ((case.requirement_ids, "requirement"), (case.related_addr, "addr")):
                for identifier in identifiers:
                    if self.rules.kind_of(identifier) != kind:
                        self.report("C01", "INVALID_INTEGRATION_PLAN", f"{plan_path}#{case.case_id}", f"{identifier} is not a {kind} ID", "INTEGRATION_TEST")

    def c02_retired_addr(self) -> None:
        retired = {
            element.id for element in self.elements.values()
            if element.kind == "addr" and self.addr_state(element) != "current"
        }
        for source in self.sources:
            for identifier in sorted(source.all_ids() & retired):
                self.report(
                    "C02", "SUPERSEDED_ADR_REFERENCE", f"{source.path}:{source.header_line}",
                    f"廃止された {identifier} を指しています。後継のADDRへ付け替えてください。",
                    ROUTE_BY_ORIGIN[source.role],
                )
        for kind, rel, identifier, line in self.doc_refs:
            if kind != "addr" and identifier in retired:
                self.report("C02", "SUPERSEDED_ADR_REFERENCE", f"{rel}:{line}", f"Retired decision {identifier} is referenced.", ROUTE_BY_ORIGIN[kind])
        for case in self.plan:
            for identifier in set(case.related_addr) & retired:
                self.report("C02", "SUPERSEDED_ADR_REFERENCE", case.case_id, f"Retired decision {identifier} is referenced.", "INTEGRATION_TEST")

    def c03_addr_requirements(self) -> None:
        for element in self.elements.values():
            if element.kind == "addr" and (self.addr_state(element) == "unknown" or (element.id.startswith("ADDR-") and element.status.upper() not in ("ACTIVE", "SUPERSEDED"))):
                self.report("C03", "ADR_STATUS_UNKNOWN", element.file, f"Invalid decision status: {element.status}", "ADDR")
        for element in sorted(self.live_addrs(), key=lambda item: item.id):
            if not element.req_refs:
                where = "関連要件の欄はありますが要件IDがありません" if element.req_section_found else "関連要件の欄がありません"
                self.report(
                    "C03", "ADR_REQUIREMENT_MISSING", element.file,
                    f"{element.id}: {where}。", "ADDR",
                )

    def c04_task_sources(self) -> None:
        for element in sorted(self.elements.values(), key=lambda item: item.id):
            if element.kind != "task":
                continue
            if not self.kinds(element.refs, "requirement", "addr", "entity"):
                self.report(
                    "C04", "TASK_SOURCE_MISSING", f"{element.file}:{element.line}",
                    f"{element.id} に対応する要件・ADDR・DB論理設計書のIDがありません。", "ARCHITECTURE",
                )

    def c05_c06_annotations(self) -> None:
        for source in self.sources:
            config = self.policy[source.role]
            allowed = set(config.get("allowed", []))
            route = ROUTE_BY_ORIGIN[source.role]
            for line_no, token in source.bad_tokens:
                self.report(
                    "C05", "TRACE_ANNOTATION_INVALID", f"{source.path}:{line_no}",
                    f"trace注釈の {token!r} はIDとして読めません。", route,
                )
            if not source.header_ids:
                self.report(
                    "C05", "TRACE_ANNOTATION_MISSING", source.path,
                    "ファイル先頭（docstringやimportより前）に trace注釈がありません。", route,
                )
                continue
            for identifier in sorted(source.all_ids()):
                kind = self.rules.kind_of(identifier)
                fallback = source.role == "code" and identifier in self.requirement_fallback
                if kind not in allowed and not fallback:
                    self.report(
                        "C05", "TRACE_ANNOTATION_INVALID", f"{source.path}:{source.header_line}",
                        f"{identifier} は {source.role} の注釈に書けない種類です（書けるもの: {', '.join(sorted(allowed))}）。",
                        route,
                    )
            if not source.per_symbol_supported:
                continue
            symbols = source.symbols
            for symbol in source.symbols:
                extra = [identifier for identifier in symbol.own_ids if identifier not in source.header_ids]
                if extra:
                    self.report(
                        "C06", "SYMBOL_ANNOTATION_INCONSISTENT", f"{source.path}:{symbol.own_line}",
                        f"{symbol.name} の注釈 {', '.join(extra)} がファイル先頭の注釈にありません。",
                        route,
                    )
            if len(source.header_ids) >= 2 and len(symbols) >= 2:
                for symbol in symbols:
                    if not symbol.own_ids:
                        self.report(
                            "C06", "SYMBOL_ANNOTATION_MISSING", f"{source.path}:{symbol.line}",
                            f"{symbol.name} の直前に trace注釈がありません（ファイルに複数のIDがあるため必要）。",
                            route,
                        )

    def c07_tests_have_requirements(self) -> None:
        for source in self.tests():
            if not source.header_ids:
                continue
            route = ROUTE_BY_ORIGIN[source.role]
            symbols = considered_symbols(source) if source.per_symbol_supported else []
            targets = [(symbol.name, symbol.line, source.effective_ids(symbol)) for symbol in symbols]
            if not targets:
                targets = [("(ファイル)", source.header_line, source.header_ids)]
            for name, line, ids in targets:
                if not self.kinds(ids, "requirement"):
                    self.report(
                        "C07", "ORPHAN_TEST", f"{source.path}:{line}",
                        f"{name} が確かめる要件IDが注釈にありません。", route,
                    )

    def c08_commits(self, commit_range: str | None) -> None:
        if not self.runs("C08") or not commit_range:
            return
        log = git(self.root, "log", "--format=%h%x1f%s", commit_range)
        if log is None:
            self.report("C08", "COMMIT_TRACE_MISSING", "git", f"コミット範囲 {commit_range} を読めません。", "IMPLEMENTATION")
            return
        prefixes = set(self.policy["checks"].get("commit_prefixes", ["TASK", "CR"]))
        for row in log.splitlines():
            if "\x1f" not in row:
                continue
            short, subject = row.split("\x1f", 1)
            prefix_match = re.match(r"^\[([A-Z][A-Z0-9-]*-\d+)\]", subject)
            ids = [prefix_match.group(1)] if prefix_match and prefix_match.group(1).split("-", 1)[0] in prefixes else []
            if not ids:
                self.report(
                    "C08", "COMMIT_TRACE_MISSING", f"commit {short}",
                    f"コミットメッセージに [TASK-nnn] または [CR-nnn] がありません: {subject[:60]}",
                    "IMPLEMENTATION",
                )
            for identifier in ids:
                if identifier not in self.elements:
                    self.report(
                        "C08", "COMMIT_TRACE_MISSING", f"commit {short}",
                        f"コミットメッセージの {identifier} はどの成果物にも定義されていません。", "IMPLEMENTATION",
                    )

    def c09_addr_implemented(self) -> None:
        if self.scope in ("REQUIREMENTS", "ARCHITECTURE", "ADDR"):
            return
        exempt = set(self.policy["checks"].get("addr_without_code", []))
        used = set()
        for source in self.code():
            used.update(source.all_ids())
        for element in self.elements.values():
            if element.kind in ("entity", "file_definition") and element.id in used:
                used.update(self.kinds(element.refs, "addr"))
        for element in sorted(self.live_addrs(), key=lambda item: item.id):
            if element.id not in used and element.id not in exempt:
                self.report(
                    "C09", "ADR_IMPLEMENTATION_MISSING", element.file,
                    f"{element.id} を指すProduction Codeがありません。", "IMPLEMENTATION",
                )

    def c10_requirements_tested(self) -> None:
        if self.scope in ("REQUIREMENTS", "ARCHITECTURE", "ADDR", "IMPLEMENTATION"):
            return
        prefixes = set(self.policy["checks"].get("require_test_for", []))
        tested = self.tested_requirements()
        for element in sorted(self.elements.values(), key=lambda item: item.id):
            if element.kind != "requirement" or element.id.split("-", 1)[0] not in prefixes:
                continue
            if element.id not in tested:
                route = "UNIT_TEST" if self.scope == "UNIT_TEST" else "INTEGRATION_TEST"
                self.report(
                    "C10", "TEST_TRACEABILITY_MISSING", f"{element.file}:{element.line}",
                    f"{element.id} を確かめるテストがありません。", route,
                )

    def tested_requirements(self) -> set[str]:
        tested: set[str] = set()
        for source in self.tests():
            tested.update(source.all_ids())
        for case in self.plan:
            tested.update(case.requirement_ids)
        return tested

    # ---------- 派生成果物 ----------

    def locations(self, targets: set[str], role: str) -> list[str]:
        result: set[str] = set()
        for source in self.sources:
            if source.role != role:
                continue
            if role != "code" and source.per_symbol_supported:
                tests = considered_symbols(source)
                if tests:
                    result.update(
                        f"{source.path}::{symbol.name}"
                        for symbol in tests
                        if set(source.effective_ids(symbol)) & targets
                    )
                    continue
            own = [symbol for symbol in source.symbols if set(symbol.own_ids) & targets]
            if own:
                result.update(f"{source.path}::{symbol.name}" for symbol in own)
            elif set(source.header_ids) & targets:
                result.add(source.path)
        return sorted(result)

    def requirement_rows(self) -> list[dict[str, Any]]:
        live = {element.id for element in self.live_addrs()}
        rows = []
        for element in sorted(self.elements.values(), key=lambda item: item.id):
            if element.kind != "requirement":
                continue
            rid = element.id
            addrs = sorted(
                item.id for item in self.elements.values()
                if item.kind == "addr" and item.id in live and rid in item.req_refs
            )
            entities = sorted(
                item.id for item in self.elements.values() if item.kind == "entity" and item.refs & {rid, *addrs}
            )
            targets = {rid, *addrs, *entities}
            targets.update(element.id for element in self.elements.values() if element.kind == "file_definition" and element.refs & targets)
            tasks = sorted(
                item.id for item in self.elements.values() if item.kind == "task" and item.refs & targets
            )
            acceptance = sorted(
                item.id for item in self.elements.values() if item.kind == "acceptance" and rid in item.refs
            )
            code = self.locations(targets, "code")
            unit = self.locations({rid}, "unit_test")
            integration = self.locations({rid}, "integration_test")
            cases = sorted(case.case_id for case in self.plan if rid in case.requirement_ids)
            rows.append(
                {
                    "要件ID": rid,
                    "要件名": element.title,
                    "ADDR": addrs,
                    "DB": entities,
                    "TASK": tasks,
                    "コード": code,
                    "単体テスト": unit,
                    "結合テスト": integration + cases,
                    "受入条件": acceptance,
                    "リンク": "あり" if (addrs or entities or code) else "なし",
                    "テスト": "あり" if (unit or integration or cases) else "なし",
                }
            )
        return rows

    def addr_rows(self) -> list[dict[str, Any]]:
        rows = []
        for element in sorted(self.elements.values(), key=lambda item: item.id):
            if element.kind != "addr":
                continue
            target = {element.id}
            target.update(item.id for item in self.elements.values() if item.kind == "file_definition" and element.id in item.refs)
            tasks = sorted(item.id for item in self.elements.values() if item.kind == "task" and element.id in item.refs)
            rows.append(
                {
                    "ADDR": element.id,
                    "タイトル": element.title,
                    "状態": element.status or "不明",
                    "種別": element.design_type,
                    "要件": sorted(element.req_refs),
                    "TASK": tasks,
                    "コード": self.locations(target, "code"),
                    "単体テスト": self.locations(target, "unit_test"),
                    "結合テスト": self.locations(target, "integration_test"),
                }
            )
        return rows

    def check_rows(self, requirement_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        status_by_location: dict[str, str] = {}
        for source in self.tests():
            for symbol in considered_symbols(source):
                status_by_location[f"{source.path}::{symbol.name}"] = symbol_status(source, symbol, self.junit_by_role.get(source.role, []))
        rows = []
        for row in requirement_rows:
            tests = [loc for loc in row["単体テスト"] + row["結合テスト"] if "::" in loc]
            statuses = [status_by_location.get(loc, "NOT_RUN") for loc in tests]
            revisions = []
            verified = True
            for role, locations in (("unit_test", row["単体テスト"]), ("integration_test", row["結合テスト"])):
                if not locations:
                    continue
                execution = self.execution.get(role, {})
                revision_value = execution.get("revision") if self.execution_matches(role, execution) else None
                if revision_value:
                    revisions.append(f"{role}: {revision_value}")
                else:
                    verified = False
                    revisions.append(f"{role}: 実行版未記録／再確認")
            pending = []
            if not row["コード"]:
                pending.append("実装へのリンクなし")
            if row["テスト"] == "なし":
                pending.append("テストなし")
            failed = [loc for loc, st in zip(tests, statuses) if st == "FAIL"]
            not_run = [loc for loc, st in zip(tests, statuses) if st in ("NOT_RUN", "SKIP")]
            if failed:
                result = "不合格"
                pending.append("不合格: " + ", ".join(failed))
            elif not tests:
                result = "－"
            elif not_run:
                result = "未実行あり"
                pending.append(f"未実行・スキップ {len(not_run)}件")
            else:
                result = "合格"
            if not verified:
                pending.append("実行版未確認／再実行が必要")
            if failed and verified:
                verdict = "不合格"
            elif row["コード"] and row["テスト"] == "あり" and result == "合格" and verified:
                verdict = "充足"
            else:
                verdict = "未確認"
            outstanding = [issue["issue_id"] for issue in self.workflow_unresolved if row["要件ID"] in self.rules.find(issue["signature"]["requirement_reference"])]
            if outstanding:
                pending.extend(outstanding)
                verdict = "未解決あり"
            rows.append(
                {
                    "要件ID": row["要件ID"],
                    "要件名": row["要件名"],
                    "確認した版": "; ".join(revisions) or "未記録",
                    "リンク": row["リンク"],
                    "テスト": row["テスト"],
                    "合否": result,
                    "判定": verdict,
                    "未対応事項": pending,
                }
            )
        return rows

    def execution_matches(self, role: str, execution: dict[str, Any]) -> bool:
        if not isinstance(execution, dict) or not execution.get("revision"):
            return False
        if execution.get("input_fingerprint") != test_input_fingerprint(self.root, self.policy, role):
            return False
        expected = file_hashes(self.root, collect_files(self.root, self.policy[role].get("junit", []), []))
        return bool(expected) and execution.get("junit_files") == expected

    def source_snapshot(self) -> dict[str, Any]:
        paths = set(self.input_paths)
        for relative in ("reports/architecture/design-manifest.json", "reports/architecture/design-input.json", "reports/architecture/addr-result.json", "reports/architecture/design-gate.json", "reports/addr/implementation-handoff.json"):
            if (self.root / relative).is_file():
                paths.add(relative)
        return {"files": file_hashes(self.root, sorted(paths)), "policy_sha256": text_hash(json.dumps(self.policy, sort_keys=True)), "workflow_unresolved": self.workflow_unresolved}

    def trace_map(self) -> dict[str, Any]:
        return {
            "version": 3,
            "method": "inline-annotation",
            "audit_scope": self.scope,
            "source_snapshot": self.source_snapshot(),
            "elements": {
                element.id: {
                    "kind": element.kind,
                    "file": element.file,
                    "line": element.line,
                    "title": element.title,
                    "status": element.status,
                    "references": sorted(element.refs),
                    **({"related_requirements": sorted(element.req_refs)} if element.kind == "addr" else {}),
                }
                for element in sorted(self.elements.values(), key=lambda item: item.id)
            },
            "sources": [
                {
                    "path": source.path,
                    "role": source.role,
                    "trace": source.header_ids,
                    "symbols": [
                        {"name": symbol.name, "line": symbol.line, "trace": symbol.own_ids}
                        for symbol in source.symbols
                        if symbol.own_ids
                    ],
                }
                for source in self.sources
            ],
            "integration_test_cases": [
                {"case_id": case.case_id, "origin": case.origin, "requirement_id": case.requirement_ids, "related_adr": case.related_addr}
                for case in self.plan
            ],
        }

    def coverage(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(rows)

        def rate(key: str) -> dict[str, Any]:
            count = sum(1 for row in rows if row[key])
            return {"covered": count, "total": total, "rate": round(100 * count / total, 1) if total else None}

        return {
            "requirement_to_addr": rate("ADDR"),
            "requirement_to_implementation": rate("コード"),
            "requirement_to_unit_test": rate("単体テスト"),
            "requirement_to_integration_test": rate("結合テスト"),
        }

    def annotation_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for role in ("code", "unit_test", "integration_test"):
            files = [source for source in self.sources if source.role == role]
            if not files:
                continue
            stats[role] = {
                "files": len(files),
                "annotated_files": sum(1 for source in files if source.header_ids),
                "trace_lines": sum(source.trace_lines for source in files),
                "symbol_annotations": sum(1 for source in files for symbol in source.symbols if symbol.own_ids),
            }
        return stats


# ============================================================
# 出力
# ============================================================


def cell(value: Any, sep: str = "<br>") -> str:
    if isinstance(value, list):
        value = sep.join(value) if value else "－"
    return str(value or "－").replace("|", "\\|").replace("\n", " ")


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        out.append("| " + " | ".join(cell(row.get(column)) for column in columns) + " |")
    return "\n".join(out) + "\n"


def csv_text(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["; ".join(value) if isinstance(value, list) else value for value in (row.get(column, "") for column in columns)])
    return buffer.getvalue()


REQ_COLUMNS = ["要件ID", "要件名", "ADDR", "DB", "TASK", "コード", "単体テスト", "結合テスト", "受入条件", "リンク", "テスト"]
ADDR_COLUMNS = ["ADDR", "タイトル", "状態", "種別", "要件", "TASK", "コード", "単体テスト", "結合テスト"]
CHECK_COLUMNS = ["要件ID", "要件名", "確認した版", "リンク", "テスト", "合否", "判定", "未対応事項"]


def derived_tables(auditor: Auditor) -> dict[str, str]:
    req_rows = auditor.requirement_rows()
    addr_rows = auditor.addr_rows()
    note = "> 自動生成。手で直さないこと（trace_check.py が正本から毎回作り直す）。\n\n"
    files = {
        "requirements-traceability-matrix.md": "# 要件トレーサビリティ表\n\n" + note + markdown_table(req_rows, REQ_COLUMNS),
        "requirements-traceability-matrix.csv": csv_text(req_rows, REQ_COLUMNS),
        "addr-index.md": "# ADDR別一覧\n\n" + note + markdown_table(addr_rows, ADDR_COLUMNS),
        "addr-index.csv": csv_text(addr_rows, ADDR_COLUMNS),
    }
    return files


def report_markdown(auditor: Auditor, status: str, coverage: dict[str, Any], stats: dict[str, Any]) -> str:
    fails = [issue for issue in auditor.issues if issue.level == "FAIL"]
    warns = [issue for issue in auditor.issues if issue.level == "WARN"]
    counts: dict[str, int] = {}
    for element in auditor.elements.values():
        counts[element.kind] = counts.get(element.kind, 0) + 1
    lines = [
        "# Traceability Report",
        "",
        f"- Audit Scope: {auditor.scope}",
        f"- 判定: **{status}**（不合格 {len(fails)}件・警告 {len(warns)}件）",
        f"- 方式: 注釈方式（AST解析なし）",
        "",
        "## 定義されたIDの数",
        "",
        "| 種類 | 件数 |",
        "| --- | ---: |",
        *[f"| {kind} | {counts.get(kind, 0)} |" for kind in DOC_KINDS],
        "",
        "## Coverage",
        "",
        "| 項目 | 件数 | 率 |",
        "| --- | ---: | ---: |",
    ]
    for key, value in coverage.items():
        rate = "－" if value["rate"] is None else f"{value['rate']}%"
        lines.append(f"| {key} | {value['covered']}/{value['total']} | {rate} |")
    lines += ["", "## 注釈の量（付与の手間の目安）", "", "| 対象 | ファイル | 注釈ありファイル | 注釈行 | 定義ごとの注釈 |", "| --- | ---: | ---: | ---: | ---: |"]
    for role, value in stats.items():
        lines.append(
            f"| {role} | {value['files']} | {value['annotated_files']} | {value['trace_lines']} | {value['symbol_annotations']} |"
        )
    lines += ["", "## Issues", ""]
    if auditor.workflow_unresolved:
        lines += ["## 3回修正後の未解決事項", "", "工程継続許可は検査PASSではありません。", ""]
        lines += [f"- {issue['issue_id']}: {issue['impact']} / 対応先 {issue['recommended_route']}" for issue in auditor.workflow_unresolved]
        lines += [""]
    if not auditor.issues:
        lines.append("問題はありません。")
    else:
        lines += ["| 検査 | 判定 | 分類 | 場所 | 内容 | 差し戻し先 |", "| --- | --- | --- | --- | --- | --- |"]
        for issue in auditor.issues:
            lines.append(
                f"| {issue.check} | {issue.level} | {issue.classification} | {cell(issue.location)} | {cell(issue.message)} | {issue.route} |"
            )
    return "\n".join(lines) + "\n"


def write(path: Path, text: str, bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8", newline="\n")


def generated_outputs(auditor: Auditor, output_dir: str) -> dict[str, str]:
    files = derived_tables(auditor)
    rows = auditor.requirement_rows()
    if auditor.scope in ("UNIT_TEST", "INTEGRATION_TEST", "FULL"):
        checks = auditor.check_rows(rows)
        files["requirements-traceability-check.md"] = "# 要件トレーサビリティ確認結果\n\n" + markdown_table(checks, CHECK_COLUMNS)
        files["requirements-traceability-check.csv"] = csv_text(checks, CHECK_COLUMNS)
    status = "FAIL" if any(issue.level == "FAIL" for issue in auditor.issues) else "PASS"
    coverage = auditor.coverage(rows)
    stats = auditor.annotation_stats()
    baseline = auditor.root / ("reports/addr/implementation-handoff.json" if auditor.scope == "ADDR" else "reports/architecture/design-manifest.json")
    baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline.is_file() else None
    report = {
        "version": 3, "status": status, "audit_scope": auditor.scope,
        "method": "inline-annotation", "source_baseline_sha256": baseline_hash,
        "trace_map": {"path": output_dir + "/trace-map.json", "version": 3},
        "coverage": coverage, "annotation_stats": stats,
        "issues": [issue.__dict__ for issue in auditor.issues],
        "workflow_unresolved": auditor.workflow_unresolved,
    }
    files["trace-map.json"] = json.dumps(auditor.trace_map(), ensure_ascii=False, indent=2) + "\n"
    files["traceability-report.json"] = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    files["traceability-report.md"] = report_markdown(auditor, status, coverage, stats)
    return files


def run(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    out_dir = root / "reports/traceability"
    policy_path = Path(args.policy)
    policy_path = policy_path if policy_path.is_absolute() else root / policy_path
    try:
        policy = load_policy(policy_path)
        output_dir = policy.get("outputs", {}).get("dir", "reports/traceability")
        configured_output = root / output_dir
        if not configured_output.resolve().is_relative_to(root):
            raise PolicyError("Output directory must stay inside repository")
        out_dir = configured_output
        if getattr(args, "record_test_run", None):
            record_test_run(root, policy, args.record_test_run)
            return 0
        auditor = Auditor(root, policy, args.scope)
        auditor.load()
        auditor.check_all(args.commits)
        files = generated_outputs(auditor, output_dir)
        if args.no_write and auditor.runs("C11"):
            for name, text in files.items():
                path = out_dir / name
                existing = path.read_text(encoding="utf-8-sig") if path.is_file() else None
                if existing != text:
                    auditor.report("C11", "DERIVED_ARTIFACT_OUTDATED", path.relative_to(root).as_posix(),
                                   "正本から再生成した内容と一致しません。", "TRACEABILITY_REGENERATE")
        if not args.no_write:
            for name, text in files.items():
                write(out_dir / name, text, bom=name.endswith(".csv"))
        failures = [issue for issue in auditor.issues if issue.level == "FAIL"]
        warnings = [issue for issue in auditor.issues if issue.level == "WARN"]
        baseline = root / ("reports/addr/implementation-handoff.json" if args.scope == "ADDR" else "reports/architecture/design-manifest.json")
        result = {
            "status": "FAIL" if failures else "PASS", "audit_scope": args.scope,
            "method": "inline-annotation",
            "source_baseline_sha256": hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline.is_file() else None,
            "errors": [issue.text() for issue in failures], "warnings": [issue.text() for issue in warnings],
            "issues": [issue.__dict__ for issue in auditor.issues],
        }
        write(out_dir / "validation-result.json", json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(f"[{result['status']}] {args.scope}: 不合格 {len(failures)}件・警告 {len(warnings)}件")
        for issue in auditor.issues:
            print(issue.text())
        return int(bool(failures))
    except (PolicyError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        failure = {"status": "FAIL", "audit_scope": args.scope, "method": "inline-annotation", "errors": [str(error)], "warnings": [], "issues": []}
        try:
            write(out_dir / "validation-result.json", json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
        except OSError:
            print("[ERROR] Could not invalidate the prior validation result", file=sys.stderr)
        return 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="注釈方式のトレーサビリティ検査と表の生成")
    parser.add_argument("--scope", choices=SCOPES, help="Orchestratorのaudit_scope")
    parser.add_argument("--record-test-run", choices=["unit_test", "integration_test"])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--commits", default=None, help="C08で見るコミット範囲（例: main..HEAD）")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="派生成果物を書き換えず、既存の表が最新か（C11）を確かめる",
    )
    args = parser.parse_args(argv)
    if not args.scope and not args.record_test_run:
        parser.error("--scope or --record-test-run is required")
    return args


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
