#!/usr/bin/env python3
"""Diagnose an Aider Polyglot model response against benchmark references."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_BENCHMARK_ROOT = Path(
    "/data/sanil/browser-is-all-you-need-worktrees/H100/polyglot-benchmark"
)
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".go",
    ".rs",
    ".py",
    ".js",
    ".ts",
    ".java",
    ".cs",
    ".rb",
}
FILENAME_RE = re.compile(
    r"(?P<name>(?:[\w.+-]+/)*[\w.+-]+\.(?:c|cc|cpp|cxx|h|hh|hpp|hxx|go|rs|py|js|ts|java|cs|rb))"
)
FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([\w.+-]*)\s*$")
LOG_NEEDLES = (
    "error:",
    "undefined reference",
    "failed",
    "failure",
    "assert",
    "timeout",
    "timed out",
    "malformed",
    "context",
    "exhaust",
    "exception",
    "segmentation",
    "abort",
    "no visible",
)


@dataclass
class CandidateFile:
    name: str
    content: str
    source: str


@dataclass
class Evidence:
    category: str
    detail: str


def read_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(errors="replace")


def slug_forms(task: str) -> list[str]:
    base = task.strip().strip("/")
    forms = {base, base.replace("_", "-"), base.replace("-", "_")}
    return [f for f in forms if f]


def infer_task_from_text(*texts: str) -> str | None:
    patterns = [
        r"exercises/practice/([A-Za-z0-9_-]+)",
        r"practice/([A-Za-z0-9_-]+)",
        r"\btask(?:_id| slug|)=['\"]?([A-Za-z0-9_-]+)",
        r"\bexercise(?:_id| slug|)=['\"]?([A-Za-z0-9_-]+)",
    ]
    for text in texts:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return None


def resolve_exercise_dir(
    benchmark_root: Path, language: str, task: str | None, exercise_dir: Path | None
) -> Path:
    if exercise_dir is not None:
        if not exercise_dir.exists():
            raise SystemExit(f"Exercise directory does not exist: {exercise_dir}")
        return exercise_dir
    if not task:
        raise SystemExit("Could not infer task. Pass --task or --exercise-dir.")

    candidates: list[Path] = []
    for form in slug_forms(task):
        candidates.extend(
            [
                benchmark_root / language / "exercises" / "practice" / form,
                benchmark_root / "exercises" / "practice" / form,
                benchmark_root / form,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = "\n".join(f"- {p}" for p in candidates)
    raise SystemExit(f"Could not locate exercise directory for task {task!r}:\n{searched}")


def reference_files(exercise_dir: Path) -> list[Path]:
    meta = exercise_dir / ".meta"
    refs = sorted(
        p
        for p in meta.glob("example.*")
        if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES
    )
    if refs:
        return refs
    raise SystemExit(f"No .meta/example.* source files found in {exercise_dir}")


def starter_files(exercise_dir: Path) -> dict[str, Path]:
    files = {}
    for path in exercise_dir.iterdir():
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
            files[path.name] = path
    return files


def clean_filename_line(line: str) -> str | None:
    stripped = line.strip().strip("`").strip()
    stripped = stripped.removeprefix("File:").removeprefix("file:").strip()
    stripped = stripped.rstrip(":")
    match = FILENAME_RE.search(stripped)
    if not match:
        return None
    return Path(match.group("name")).name


def extract_candidate_files(model_output: str, output_path: Path | None) -> list[CandidateFile]:
    lines = model_output.splitlines()
    candidates: list[CandidateFile] = []
    i = 0
    while i < len(lines):
        fence = FENCE_RE.match(lines[i])
        if not fence:
            i += 1
            continue
        filename = None
        for back in range(max(0, i - 4), i):
            filename = clean_filename_line(lines[back])
            if filename:
                break
        start = i + 1
        i = start
        body: list[str] = []
        while i < len(lines) and not FENCE_RE.match(lines[i]):
            body.append(lines[i])
            i += 1
        if filename:
            candidates.append(
                CandidateFile(filename, "\n".join(body).rstrip() + "\n", "fenced block")
            )
        i += 1

    if not candidates and output_path and output_path.suffix.lower() in SOURCE_SUFFIXES:
        candidates.append(
            CandidateFile(output_path.name, model_output.rstrip() + "\n", "whole output file")
        )
    return candidates


def map_candidates_to_refs(
    candidates: list[CandidateFile], refs: list[Path], exercise_dir: Path
) -> dict[Path, CandidateFile | None]:
    by_name = {c.name: c for c in candidates}
    by_suffix: dict[str, list[CandidateFile]] = defaultdict(list)
    for candidate in candidates:
        by_suffix[Path(candidate.name).suffix.lower()].append(candidate)

    mapped: dict[Path, CandidateFile | None] = {}
    for ref in refs:
        root_names = [
            p.name
            for p in exercise_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ref.suffix.lower()
        ]
        chosen = None
        for name in [ref.name, *root_names]:
            if name in by_name:
                chosen = by_name[name]
                break
        if chosen is None:
            same_suffix = by_suffix.get(ref.suffix.lower(), [])
            if len(same_suffix) == 1:
                chosen = same_suffix[0]
        mapped[ref] = chosen
    return mapped


def line_blocks(lines: list[str], start: int, end: int, limit: int = 6) -> str:
    if start >= end:
        return "(no lines)"
    shown = lines[start:end][:limit]
    rendered = []
    for offset, line in enumerate(shown, start=start + 1):
        rendered.append(f"{offset}: {line}")
    if end - start > limit:
        rendered.append(f"... {end - start - limit} more line(s)")
    return "\n".join(rendered)


def diff_summary(ref_text: str, cand_text: str, max_regions: int) -> tuple[str, int]:
    ref_lines = ref_text.splitlines()
    cand_lines = cand_text.splitlines()
    matcher = difflib.SequenceMatcher(a=ref_lines, b=cand_lines, autojunk=False)
    parts: list[str] = []
    regions = 0
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            continue
        regions += 1
        if len(parts) >= max_regions:
            continue
        parts.append(
            "\n".join(
                [
                    f"- `{tag}` reference lines {a0 + 1}-{a1} vs model lines {b0 + 1}-{b1}",
                    "  Reference:",
                    indent_code(line_blocks(ref_lines, a0, a1)),
                    "  Model:",
                    indent_code(line_blocks(cand_lines, b0, b1)),
                ]
            )
        )
    if not parts:
        return "- No textual differences found.", regions
    if regions > max_regions:
        parts.append(f"- {regions - max_regions} additional changed region(s) omitted.")
    return "\n".join(parts), regions


def unified_diff(ref_path: Path, cand: CandidateFile, max_lines: int) -> str:
    ref_lines = ref_path.read_text(errors="replace").splitlines()
    cand_lines = cand.content.splitlines()
    diff = list(
        difflib.unified_diff(
            ref_lines,
            cand_lines,
            fromfile=str(ref_path),
            tofile=cand.name,
            lineterm="",
        )
    )
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... {len(diff) - max_lines} more diff line(s) omitted"]
    return "\n".join(diff) if diff else "(no diff)"


def indent_code(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


def collect_log_evidence(log_path: Path | None, task: str, names: Iterable[str], max_lines: int) -> list[str]:
    if log_path is None or not log_path.exists():
        return []
    lowered_names = {name.lower() for name in names if name}
    slug_names = {task.lower(), task.replace("-", "_").lower(), task.replace("_", "-").lower()}
    matches: list[str] = []
    with log_path.open(errors="replace") as handle:
        for lineno, line in enumerate(handle, start=1):
            low = line.lower()
            has_failure = any(needle in low for needle in LOG_NEEDLES)
            has_task = any(name in low for name in lowered_names | slug_names)
            if has_failure and (has_task or len(matches) < 20):
                matches.append(f"{lineno}: {line.rstrip()}")
            if len(matches) >= max_lines:
                break
    return matches


def infer_issues(
    candidates: list[CandidateFile],
    mapping: dict[Path, CandidateFile | None],
    starters: dict[str, Path],
    log_lines: list[str],
) -> list[Evidence]:
    issues: list[Evidence] = []
    if not candidates:
        issues.append(
            Evidence(
                "malformed-output",
                "No parseable Aider file block was found in the model response.",
            )
        )
    for ref, cand in mapping.items():
        if cand is None:
            issues.append(
                Evidence(
                    "missing-file",
                    f"No candidate file was mapped to reference `{ref.relative_to(ref.parents[1])}`.",
                )
            )
            continue
        ref_text = ref.read_text(errors="replace")
        cand_text = cand.content
        if cand.name in starters:
            starter_text = starters[cand.name].read_text(errors="replace").rstrip()
            if starter_text and starter_text == cand_text.rstrip():
                issues.append(
                    Evidence(
                        "starter-copy-or-no-op",
                        f"`{cand.name}` matches the root starter file, not `.meta/{ref.name}`.",
                    )
                )
        ref_namespaces = set(re.findall(r"\bnamespace\s+([A-Za-z_]\w*)", ref_text))
        cand_namespaces = set(re.findall(r"\bnamespace\s+([A-Za-z_]\w*)", cand_text))
        if ref_namespaces and ref_namespaces != cand_namespaces:
            issues.append(
                Evidence(
                    "namespace-mismatch",
                    f"`{cand.name}` namespaces {sorted(cand_namespaces)} differ from reference {sorted(ref_namespaces)}.",
                )
            )
        if ref.suffix.lower() in {".h", ".hpp", ".hh", ".hxx"} and ref_text != cand_text:
            issues.append(
                Evidence(
                    "api-signature-risk",
                    f"`{cand.name}` header differs from the reference header; check function signatures, const refs, includes, and namespace.",
                )
            )
        if "std::invalid_argument" in ref_text and "std::invalid_argument" not in cand_text:
            issues.append(
                Evidence(
                    "exception-policy-gap",
                    f"`{cand.name}` does not mirror the reference use of `std::invalid_argument`.",
                )
            )
        if ref_text != cand_text:
            issues.append(
                Evidence(
                    "algorithm-or-edge-case-gap",
                    f"`{cand.name}` differs from `{ref.name}`; inspect the line-level diff for missing edge cases or state transitions.",
                )
            )
    joined_log = "\n".join(log_lines).lower()
    if "context" in joined_log and ("exhaust" in joined_log or "length" in joined_log):
        issues.append(Evidence("context-exhaustion", "The eval log indicates context/token exhaustion."))
    if "error:" in joined_log or "undefined reference" in joined_log:
        issues.append(Evidence("compile-failure", "The eval log contains compiler/linker errors."))
    if "timeout" in joined_log or "timed out" in joined_log:
        issues.append(Evidence("timeout", "The eval log indicates a timeout or non-terminating behavior."))
    return dedupe_evidence(issues)


def dedupe_evidence(items: list[Evidence]) -> list[Evidence]:
    seen = set()
    out = []
    for item in items:
        key = (item.category, item.detail)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def recommendations(issues: list[Evidence]) -> list[str]:
    categories = {issue.category for issue in issues}
    recs: list[str] = []
    if "malformed-output" in categories:
        recs.append(
            "Tighten exporter/prompt validation around Aider whole-file format: require `filename` followed by one fenced code block per edited file, and reject prose-only or patch-only completions before training."
        )
    if "missing-file" in categories:
        recs.append(
            "Add training rows where both `.cpp` and `.h` edits are required; make missing companion files a labeled failure mode in repair data."
        )
    if "starter-copy-or-no-op" in categories:
        recs.append(
            "Filter no-op/starter-copy responses from SFT data and add retry examples where the model must replace root starter code with the `.meta/example.*` behavior."
        )
    if "api-signature-risk" in categories or "namespace-mismatch" in categories:
        recs.append(
            "Add header-sensitive examples and prompt wording that says public signatures, namespaces, includes, and const/reference qualifiers must match tests exactly."
        )
    if "exception-policy-gap" in categories:
        recs.append(
            "Add contrastive rows for invalid-input behavior, especially exception type and condition boundaries, because these are easy to miss from prose instructions."
        )
    if "compile-failure" in categories:
        recs.append(
            "Train on compiler-feedback repair turns that preserve the file-listing format and make the smallest signature/include/linkage correction."
        )
    if "timeout" in categories:
        recs.append(
            "Add examples that bound loops and recursive search, and include timeout logs as repair context for algorithmic tasks."
        )
    if "context-exhaustion" in categories:
        recs.append(
            "Reduce prompt baggage in the exporter or split retry context; context exhaustion is not a model reasoning failure if the needed files were truncated."
        )
    if "algorithm-or-edge-case-gap" in categories or not recs:
        recs.append(
            "Create targeted SFT repair rows from the changed reference regions: show the failed candidate, failing test/compiler evidence, and the minimal corrected whole-file output."
        )
    return recs


def md_escape(text: str) -> str:
    return text.replace("\u0000", "")


def appendix(text: str, max_chars: int) -> str:
    if max_chars == 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... truncated {len(text) - max_chars} character(s)."


def build_report(args: argparse.Namespace) -> str:
    model_input = read_text(args.model_input)
    model_output = read_text(args.model_output)
    inferred_task = args.task or infer_task_from_text(
        model_input,
        model_output,
        str(args.log or ""),
        str(args.model_input or ""),
        str(args.model_output or ""),
    )
    exercise_dir = resolve_exercise_dir(
        args.benchmark_root, args.language, inferred_task, args.exercise_dir
    )
    task = inferred_task or exercise_dir.name
    refs = reference_files(exercise_dir)
    starters = starter_files(exercise_dir)
    candidates = extract_candidate_files(model_output, args.model_output)
    mapping = map_candidates_to_refs(candidates, refs, exercise_dir)
    log_names = [c.name for c in candidates] + [p.name for p in refs]
    log_lines = collect_log_evidence(args.log, task, log_names, args.max_log_lines)
    issues = infer_issues(candidates, mapping, starters, log_lines)

    out: list[str] = []
    out.append(f"# Aider Output Diagnosis: {task}")
    out.append("")
    out.append("## Inputs")
    out.append("")
    out.append(f"- Exercise directory: `{exercise_dir}`")
    out.append(f"- Benchmark root: `{args.benchmark_root}`")
    out.append(f"- Model input: `{args.model_input}`" if args.model_input else "- Model input: not provided")
    out.append(f"- Model output: `{args.model_output}`" if args.model_output else "- Model output: not provided")
    out.append(f"- Failure log: `{args.log}`" if args.log else "- Failure log: not provided")
    out.append("")
    out.append("## Reference Solution")
    out.append("")
    for ref in refs:
        out.append(f"- `{ref.relative_to(exercise_dir)}`")
    out.append("")
    out.append("## Candidate Files")
    out.append("")
    if candidates:
        for candidate in candidates:
            out.append(f"- `{candidate.name}` ({candidate.source}, {len(candidate.content.splitlines())} lines)")
    else:
        out.append("- No parseable candidate files found.")
    out.append("")
    out.append("## Where The Model Lacked")
    out.append("")
    for ref, candidate in mapping.items():
        out.append(f"### `{ref.relative_to(exercise_dir)}`")
        out.append("")
        if candidate is None:
            out.append("- No matching model file was produced.")
            out.append("")
            continue
        summary, changed_regions = diff_summary(
            ref.read_text(errors="replace"), candidate.content, args.max_regions
        )
        out.append(f"- Matched model file: `{candidate.name}`")
        out.append(f"- Changed regions: {changed_regions}")
        out.append("")
        out.append(summary)
        out.append("")
    out.append("## Failure Log Evidence")
    out.append("")
    if log_lines:
        out.append("```text")
        out.extend(log_lines)
        out.append("```")
    else:
        out.append("- No matching failure evidence found or no log provided.")
    out.append("")
    out.append("## Underlying Issues")
    out.append("")
    if issues:
        for issue in issues:
            out.append(f"- `{issue.category}`: {issue.detail}")
    else:
        out.append("- No issue inferred from textual comparison. Check hidden tests or runtime behavior.")
    out.append("")
    out.append("## What To Improve")
    out.append("")
    for rec in recommendations(issues):
        out.append(f"- {rec}")
    out.append("")
    out.append("## Unified Diffs")
    out.append("")
    for ref, candidate in mapping.items():
        if candidate is None:
            continue
        out.append(f"### `{ref.relative_to(exercise_dir)}` vs `{candidate.name}`")
        out.append("")
        out.append("```diff")
        out.append(unified_diff(ref, candidate, args.max_diff_lines))
        out.append("```")
        out.append("")
    out.append("## Model Input Appendix")
    out.append("")
    out.append("```text")
    out.append(md_escape(appendix(model_input, args.max_appendix_chars)))
    out.append("```")
    out.append("")
    out.append("## Model Output Appendix")
    out.append("")
    out.append("```text")
    out.append(md_escape(appendix(model_output, args.max_appendix_chars)))
    out.append("```")
    out.append("")
    return "\n".join(out)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_BENCHMARK_ROOT)
    parser.add_argument("--language", default="cpp")
    parser.add_argument("--task")
    parser.add_argument("--exercise-dir", type=Path)
    parser.add_argument("--model-input", type=Path)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-regions", type=int, default=16)
    parser.add_argument("--max-diff-lines", type=int, default=240)
    parser.add_argument("--max-log-lines", type=int, default=80)
    parser.add_argument(
        "--max-appendix-chars",
        type=int,
        default=20000,
        help="Use 0 to include full prompt/output appendices.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(args)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
