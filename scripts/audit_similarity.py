#!/usr/bin/env python3
"""Measure source overlap between Fangcun Guard and a local reference tree.

The report deliberately separates same-path overlap from repository-wide line
containment. The latter still catches files that were moved during refactors.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
from typing import Iterable


DEFAULT_REFERENCE = Path.home() / "Desktop" / "openguardrails 2"
IGNORED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
IGNORED_FILENAMES = {".DS_Store", "package-lock.json"}
TEXT_SUFFIXES = {
    ".conf",
    ".css",
    ".example",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {".dockerignore", ".gitignore", "Dockerfile", "LICENSE", "VERSION"}
BRAND_PATTERN = re.compile(r"open[ _-]?guardrails|fangcun[ _-]?guard", re.IGNORECASE)
PRODUCTION_PREFIXES = ("backend/", "frontend/src/", "fangcunguard-cli/fangcunguard/")
NON_PRODUCTION_PARTS = {"docs", "migrations", "scripts", "tests"}


@dataclass(frozen=True)
class TreeSnapshot:
    files: dict[str, list[str]]

    @property
    def paths(self) -> set[str]:
        return set(self.files)

    @property
    def line_count(self) -> int:
        return sum(len(lines) for lines in self.files.values())


@dataclass(frozen=True)
class SimilarityReport:
    candidate_root: str
    reference_root: str
    candidate_files: int
    reference_files: int
    common_paths: int
    path_jaccard: float
    exact_same_path_files: int
    same_path_line_similarity: float
    candidate_line_containment: float
    reference_line_containment: float
    repository_line_dice: float
    normalized_brand_names: bool
    production_only: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="tree being audited (default: repository root)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
        help=f"local comparison tree (default: {DEFAULT_REFERENCE})",
    )
    parser.add_argument(
        "--normalize-brands",
        action="store_true",
        help="treat OpenGuardrails and Fangcun Guard spellings as equivalent",
    )
    parser.add_argument(
        "--production-only",
        action="store_true",
        help="audit runtime source only; exclude tests, docs, scripts, and migrations",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--max-reference-containment",
        type=float,
        help="exit non-zero when reference line containment exceeds this percentage",
    )
    return parser.parse_args()


def is_audited_text_file(path: Path, root: Path, production_only: bool) -> bool:
    relative_path = path.relative_to(root)
    if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
        return False
    if path.name in IGNORED_FILENAMES:
        return False
    if production_only:
        relative_text = str(relative_path)
        if not relative_text.startswith(PRODUCTION_PREFIXES):
            return False
        if any(part in NON_PRODUCTION_PARTS for part in relative_path.parts):
            return False
    return path.name in TEXT_FILENAMES or path.suffix.lower() in TEXT_SUFFIXES


def normalize_line(line: str, normalize_brands: bool) -> str:
    normalized = line.strip()
    if normalize_brands:
        normalized = BRAND_PATTERN.sub("product-brand", normalized)
    return normalized


def load_tree(root: Path, normalize_brands: bool, production_only: bool = False) -> TreeSnapshot:
    if not root.is_dir():
        raise FileNotFoundError(f"source tree does not exist: {root}")

    files: dict[str, list[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or not is_audited_text_file(path, root, production_only):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files[str(path.relative_to(root))] = [
            normalize_line(line, normalize_brands) for line in text.splitlines()
        ]
    return TreeSnapshot(files=files)


def matching_line_count(left: Iterable[str], right: Iterable[str]) -> int:
    blocks = SequenceMatcher(None, list(left), list(right), autojunk=False).get_matching_blocks()
    return sum(block.size for block in blocks)


def dice(shared: int, left_total: int, right_total: int) -> float:
    total = left_total + right_total
    return (2 * shared / total) if total else 1.0


def meaningful_lines(snapshot: TreeSnapshot) -> Counter[str]:
    return Counter(
        line
        for lines in snapshot.files.values()
        for line in lines
        if len(line) >= 8
    )


def build_report(
    candidate_root: Path,
    reference_root: Path,
    normalize_brands: bool,
    production_only: bool = False,
) -> SimilarityReport:
    candidate = load_tree(candidate_root, normalize_brands, production_only)
    reference = load_tree(reference_root, normalize_brands, production_only)
    shared_paths = candidate.paths & reference.paths
    union_paths = candidate.paths | reference.paths

    exact_files = 0
    same_path_matches = 0
    same_path_candidate_lines = 0
    same_path_reference_lines = 0
    for relative_path in shared_paths:
        candidate_lines = candidate.files[relative_path]
        reference_lines = reference.files[relative_path]
        if candidate_lines == reference_lines:
            exact_files += 1
        same_path_matches += matching_line_count(candidate_lines, reference_lines)
        same_path_candidate_lines += len(candidate_lines)
        same_path_reference_lines += len(reference_lines)

    candidate_counter = meaningful_lines(candidate)
    reference_counter = meaningful_lines(reference)
    repository_matches = sum((candidate_counter & reference_counter).values())
    candidate_meaningful_lines = sum(candidate_counter.values())
    reference_meaningful_lines = sum(reference_counter.values())

    return SimilarityReport(
        candidate_root=str(candidate_root.resolve()),
        reference_root=str(reference_root.resolve()),
        candidate_files=len(candidate.files),
        reference_files=len(reference.files),
        common_paths=len(shared_paths),
        path_jaccard=(len(shared_paths) / len(union_paths)) if union_paths else 1.0,
        exact_same_path_files=exact_files,
        same_path_line_similarity=dice(
            same_path_matches,
            same_path_candidate_lines,
            same_path_reference_lines,
        ),
        candidate_line_containment=(
            repository_matches / candidate_meaningful_lines if candidate_meaningful_lines else 1.0
        ),
        reference_line_containment=(
            repository_matches / reference_meaningful_lines if reference_meaningful_lines else 1.0
        ),
        repository_line_dice=dice(
            repository_matches,
            candidate_meaningful_lines,
            reference_meaningful_lines,
        ),
        normalized_brand_names=normalize_brands,
        production_only=production_only,
    )


def print_human_report(report: SimilarityReport) -> None:
    print(f"Candidate:  {report.candidate_root}")
    print(f"Reference:  {report.reference_root}")
    print(f"Scope:      {'production source' if report.production_only else 'all audited text'}")
    print(f"Files:      {report.candidate_files} candidate / {report.reference_files} reference")
    print(f"Same path:  {report.common_paths} files ({report.path_jaccard:.2%} Jaccard)")
    print(f"Exact:      {report.exact_same_path_files} same-path files")
    print(f"Path lines: {report.same_path_line_similarity:.2%} similar")
    print(f"Containment:{report.reference_line_containment:.2%} of reference lines found in candidate")
    print(f"Candidate:  {report.candidate_line_containment:.2%} of candidate lines found in reference")
    print(f"Repo Dice:  {report.repository_line_dice:.2%}")


def main() -> int:
    args = parse_args()
    try:
        report = build_report(
            args.candidate,
            args.reference,
            args.normalize_brands,
            args.production_only,
        )
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=True, indent=2))
    else:
        print_human_report(report)

    if (
        args.max_reference_containment is not None
        and report.reference_line_containment > args.max_reference_containment / 100
    ):
        print(
            "reference containment exceeds configured maximum: "
            f"{report.reference_line_containment:.2%} > {args.max_reference_containment:.2f}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
