from __future__ import annotations

import itertools
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_bounded_circular_storage_expansion as family
from w8_biayn.integrations.moonlight_bounded_circular_storage_cases import CASES


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "aider-tasks")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "aider-tasks-reverify")
    return expansion / "state-concurrency" / "bounded-circular-storage"


def test_catalog_is_exact_count_plan_cell() -> None:
    ids = [case.task_id for case in CASES]
    assert len(ids) == len(set(ids)) == 60
    assert not set(ids) & family.HOLDOUTS
    assert {case.task_id for case in CASES} >= {
        "extent-compaction-ledger",
        "framed-byte-wrap-log",
        "reference-bit-clock-cache",
        "atomic-dual-key-index",
        "inverse-mutation-journal",
        "rollback-spill-routing-banks",
    }
    assert all(case.mechanism not in {"", "bounded sequence state"} for case in CASES)


def test_generator_materializes_roles_boundaries_and_1770_pairs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    roots = family.build(out)
    assert len(roots) == 60
    family.verify_core(out)
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 60
    diversity = manifest["screen"]["diversity"]
    assert diversity["pair_count"] == 1770
    assert all(all(row["decisions"].values()) for row in diversity["pairs"])
    assert all(
        not any(control["decisions"].values())
        for control in diversity["controls"].values()
    )
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        task_id = root.name
        assert config["files"]["solution"] == [f"{task_id}.h", f"{task_id}.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp"]
        prompt = family.build_prompt(family.load_task(root))
        assert ".meta/" not in prompt
        assert "negative_false_substitute" not in prompt
        assert (root / ".meta/example.cpp").read_text() != (
            root / ".meta/negative_false_substitute.cpp"
        ).read_text()


def test_independent_pair_recomputation_does_not_call_production_pair() -> None:
    # Independent artifact-level evaluator. It consumes the emitted roles but
    # does not call family.material(), family.pair(), or family.normalized().
    # Identifiers, literals, and endpoint words are normalized so renamed or
    # constant-only clone controls cannot escape this class of comparison.
    keywords = {
        "auto", "bool", "class", "const", "else", "for", "if", "int",
        "private", "public", "return", "struct", "throw", "void", "while",
        "std", "deque", "map", "optional", "set", "vector", "size_t",
        "uint64_t", "nullopt", "sort", "find", "erase", "insert", "clear",
        "begin", "end", "ENDPOINT", "LIT",
    }

    def normalize(text: str) -> tuple[str, ...]:
        text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
        text = re.sub(r'"(?:\\.|[^"\\])*"', " LIT ", text)
        text = re.sub(r"\b(?:true|false)\b|-?\d+(?:[uUlL]+)?", " LIT ", text)
        tokens = re.findall(
            r"[A-Za-z_][A-Za-z_0-9]*|<=|>=|==|!=|&&|\|\||[-+*/%<>{}()[\];,?:=.]",
            text,
        )
        endpoints = {
            "front": "ENDPOINT", "back": "ENDPOINT",
            "first": "ENDPOINT", "last": "ENDPOINT",
            "left": "ENDPOINT", "right": "ENDPOINT",
            "spill": "ENDPOINT", "overflow_route": "ENDPOINT",
            "push_front": "PUSH_ENDPOINT", "push_back": "PUSH_ENDPOINT",
            "pop_front": "POP_ENDPOINT", "pop_back": "POP_ENDPOINT",
        }
        return tuple(
            endpoints.get(
                token.lower(),
                token
                if token in keywords or not re.match(r"^[A-Za-z_]", token)
                else "ID",
            )
            for token in tokens
        )

    profiles: dict[str, tuple[tuple[str, ...], ...]] = {}
    for case in CASES:
        files = family.render(case)
        header = files[f"{case.task_id}.h"]
        reference = files[".meta/example.cpp"]
        instructions = files[".docs/instructions.md"]
        assert instructions.startswith("# Instructions\n")
        assert "## Examples" in instructions
        assert case.forbidden in instructions
        for banned in (
            "clean-room",
            "Required mechanism",
            "must own the mechanism",
            "may not replace",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
        ):
            assert banned not in instructions, (case.task_id, banned)
        introduction = files[".docs/introduction.md"]
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
        visible = files["task_visible_test.cpp"]
        hidden = files[".meta/task_hidden_test.cpp"]
        negative = files[".meta/negative_false_substitute.cpp"]
        private = header.split("private:", 1)[1] if "private:" in header else header
        profiles[case.task_id] = tuple(
            normalize(subject)
            for subject in (
                header.split("private:", 1)[0],
                private + reference,
                instructions + reference,
                instructions + hidden,
                reference,
                visible + hidden,
                negative + visible + hidden,
            )
        )
    decisions = []
    for left, right in itertools.combinations(sorted(profiles), 2):
        row = tuple(a != b for a, b in zip(profiles[left], profiles[right]))
        assert all(row), (left, right, row)
        decisions.append(row)
    assert len(decisions) == 1770


def test_path_guard_rejects_existing_roots_and_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.EXPANSION_ROOT.mkdir(parents=True)
    family.LEGACY_ROOT.mkdir()
    family.REVERIFY_ROOT.mkdir()
    with pytest.raises(RuntimeError, match="unsafe_path"):
        family.validate_out(family.LEGACY_ROOT / "forbidden")
    with pytest.raises(RuntimeError, match="unsafe_path"):
        family.validate_out(family.REVERIFY_ROOT / "forbidden")
    link = family.EXPANSION_ROOT / "linked"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        family.validate_out(link / "family")
    family.validate_out(out)


def test_rebuild_without_force_refreshes_state_inventory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.build(out)
    # A verify-only rerun regenerates deterministically; the timestamped
    # .state inventory snapshot must not break it with FileExistsError.
    family.build(out)


def test_verify_host_fails_closed_without_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.build(out)
    with pytest.raises(RuntimeError, match="generator_output_drift"):
        family.verify_host(out)


def test_host_root_verification_executes_reference_and_rejects_negative(
    tmp_path: Path,
) -> None:
    compiler = shutil.which("c++")
    if compiler is None or shutil.which("cmake") is None:
        pytest.skip("host C++ toolchain unavailable; pinned Docker remains authoritative")
    case = next(c for c in CASES if c.task_id == "capacity-buddy-pool")
    root = tmp_path / case.task_id
    for relative, content in family.render(case).items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    records = family._host_verify_root(root, tmp_path / "work", compiler, negative=True)
    assert {row["mode"] for row in records} == {
        "normal",
        "sanitizer",
        "negative-normal",
        "negative-sanitizer",
    }
    assert {row["test_count"] for row in records} == {2}


def test_all_reference_and_negative_sources_compile_and_execute(tmp_path: Path) -> None:
    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("host C++ compiler unavailable; pinned Docker remains authoritative")
    failures: list[str] = []
    for case in CASES:
        root = tmp_path / case.task_id
        for relative, content in family.render(case).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        outcomes: dict[str, int] = {}
        for source_name, test_name, mode in (
            (".meta/example.cpp", "task_visible_test.cpp", "reference-visible"),
            (".meta/example.cpp", ".meta/task_hidden_test.cpp", "reference-hidden"),
            (".meta/negative_false_substitute.cpp", "task_visible_test.cpp", "negative-visible"),
            (".meta/negative_false_substitute.cpp", ".meta/task_hidden_test.cpp", "negative-hidden"),
        ):
            binary = root / mode
            built = subprocess.run(
                [
                    compiler,
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    "-Wpedantic",
                    "-Werror",
                    "-I",
                    str(root),
                    str(root / source_name),
                    str(root / test_name),
                    "-o",
                    str(binary),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            if built.returncode:
                failures.append(f"{case.task_id}/{mode} compile: {built.stderr[-1200:]}")
                continue
            outcomes[mode] = subprocess.run([binary], check=False).returncode
        if outcomes.get("reference-visible") != 0 or outcomes.get("reference-hidden") != 0:
            failures.append(f"{case.task_id}: reference outcomes {outcomes}")
        if outcomes.get("negative-visible") == 0 and outcomes.get("negative-hidden") == 0:
            failures.append(f"{case.task_id}: negative accepted by both tests")
    assert not failures, "\n".join(failures)
