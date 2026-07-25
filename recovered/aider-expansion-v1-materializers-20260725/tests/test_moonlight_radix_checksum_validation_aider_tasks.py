from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_radix_checksum_validation_aider_tasks as tasks
from w8_biayn.integrations import moonlight_radix_checksum_validation_audit as independent_audit
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _independent_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|<!--.*?-->", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " literal ", text)
    text = re.sub(r"\b\d+[uUlL]*\b", " number ", text)
    words = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||[%*/+<>{}\[\]();,:?-]", text.lower()
    )
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "struct",
        "class",
        "public",
        "vector",
        "array",
        "string",
        "map",
        "set",
        "deque",
        "optional",
        "pair",
        "bool",
        "long",
        "int",
        "unsigned",
        "size_t",
        "static",
        "const",
        "auto",
        "void",
    }
    return tuple(word if word in keywords or not word[0].isalpha() else "id" for word in words)


def test_exact_binding_inventory_is_cartesian_and_unique() -> None:
    assert len(tasks.RADICES) == 10
    assert len(tasks.CHECKSUMS) == 10
    assert len(tasks.TASKS) == tasks.EXPECTED_ROOTS == 100
    assert len({spec.task_id for spec in tasks.TASKS}) == 100
    assert {(spec.radix.key, spec.checksum.key) for spec in tasks.TASKS} == {
        (radix.key, checksum.key) for radix in tasks.RADICES for checksum in tasks.CHECKSUMS
    }


def test_materialization_roles_and_prompt_boundary(tmp_path: Path) -> None:
    out = tmp_path / "family"
    result = tasks.build(out, testing=True)
    assert result["root_count"] == 100
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 100
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        prompt = build_prompt(load_task(root))
        assert f"{root.name}.h" in prompt and f"{root.name}.cpp" in prompt
        assert ".meta/" not in prompt
        assert "negative.cpp" not in prompt
        assert "CMakeLists.txt" not in prompt


def test_exact_output_guard_refuses_existing_trees() -> None:
    with pytest.raises(tasks.FamilyError, match="unsafe_path"):
        tasks._validate_output(tasks.LEGACY_ROOT)
    with pytest.raises(tasks.FamilyError, match="unsafe_path"):
        tasks._validate_output(tasks.REVERIFY_ROOT)
    with pytest.raises(tasks.FamilyError, match="unsafe_path"):
        tasks._validate_output(tasks.EXPANSION_ROOT / "another-family")


def test_rendered_mechanisms_and_negatives_are_not_one_shared_dispatcher(tmp_path: Path) -> None:
    rendered = {spec.task_id: tasks._render(spec) for spec in tasks.TASKS}
    references = {files[".meta/example.cpp"] for files in rendered.values()}
    negatives = {files[".meta/negative.cpp"] for files in rendered.values()}
    headers = {files[f"{task_id}.h"] for task_id, files in rendered.items()}
    assert len(references) == 100
    assert len(headers) == 100
    assert len(negatives) == 100
    semantic_hashes: set[str] = set()
    for task_id, files in rendered.items():
        path = tmp_path / f"{task_id}.cpp"
        path.write_text(files[".meta/negative.cpp"])
        semantic_hashes.add(independent_audit._semantic_negative_hash(path))
    assert len(semantic_hashes) == 100
    for spec in tasks.TASKS:
        source = rendered[spec.task_id][".meta/example.cpp"]
        assert spec.radix.decoder.strip() in source
        assert spec.checksum.algorithm.strip() in source
        assert "switch (" not in source


def test_core_screen_has_all_pairs_dimensions_and_real_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "family"
    tasks.build(out, testing=True)
    monkeypatch.setattr(
        tasks, "_holdout_and_lineage_screen", lambda _: {"holdout_count": 26, "test_stub": True}
    )
    receipt = tasks.verify_core(out)
    assert receipt["root_count"] == 100
    screen = json.loads((out / ".state/receipts/diversity-screen.json").read_text())
    assert screen["pair_count"] == 4950
    assert screen["dimensions"] == list(tasks.HARD_DIMENSIONS)
    assert len(screen["decisions"]) == 4950
    seen_pairs: set[tuple[str, str]] = set()
    for decision in screen["decisions"]:
        pair = (decision["left"], decision["right"])
        assert pair not in seen_pairs
        seen_pairs.add(pair)
        assert set(decision["dimensions"]) == set(tasks.HARD_DIMENSIONS)
        assert all(item["pass"] for item in decision["dimensions"].values())
    assert len(screen["controls"]) == 3
    source = out / tasks.TASKS[0].task_id
    source_files = "\n".join(
        path.read_text() for path in sorted(source.rglob("*")) if path.is_file()
    )
    for control in screen["controls"]:
        root = out / ".state/controls" / control["name"]
        control_files = "\n".join(
            path.read_text() for path in sorted(root.rglob("*")) if path.is_file()
        )
        assert source_files != control_files
        assert _independent_tokens(source_files)
        assert _independent_tokens(control_files)
        assert control["rejected_in_all_dimensions"] is True
        assert all(item["rejected_as_duplicate"] for item in control["dimensions"].values())


def test_reference_claims_match_independent_python_checks() -> None:
    expected = {
        checksum.key: tasks._checksum_expected(checksum.key) for checksum in tasks.CHECKSUMS
    }
    assert expected == {
        "weighted": 3,
        "alternating": 2,
        "luhn-fold": 14,
        "fletcher-pair": 209,
        "adler-pair": 6543,
        "polynomial": 16,
        "crc-bits": 193,
        "quasigroup": 0,
        "complement": 2,
        "diagonal": 12,
    }


def _write_fake_receipts(out: Path, *, host: bool = True, stale_host: bool = False) -> None:
    receipts = out / ".state/receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    tree = tasks._tree_hash(out)
    (receipts / "creator-preflight.json").write_text(json.dumps({"subject_hash": "sha256:test"}))
    (receipts / "docker-sanity.json").write_text(
        json.dumps({"tree_hash": tree, "normal_test_count": 200, "sanitizer_test_count": 200})
    )
    (receipts / "diversity-screen.json").write_text(json.dumps({"pair_count": 4950, "pass": True}))
    if host:
        (receipts / "host-verify.json").write_text(
            json.dumps(
                {
                    "tree_hash": "sha256:stale" if stale_host else tree,
                    "generator_revision": tasks._generator_revision(),
                    "normal_test_count": 200,
                    "sanitizer_test_count": 200,
                    "negative_rejections": 100,
                }
            )
        )


def test_audit_is_subject_bound_and_immutable(tmp_path: Path) -> None:
    out = tmp_path / "family"
    tasks.build(out, testing=True)
    _write_fake_receipts(out)
    report = tasks.audit(out, cycle=1)
    assert report["decision"] == "local_family_verified"
    assert report["confirmed_counts"]["roots"] == 100
    assert report["confirmed_counts"]["host_normal_tests"] == 200
    assert report["subject_bindings"]["host_verify_hash"] is not None
    assert Path(report["report_path"]).is_file()
    assert tasks.audit(out, cycle=1)["audit_subject_hash"] == report["audit_subject_hash"]


def test_audit_requires_current_host_verify(tmp_path: Path) -> None:
    out = tmp_path / "family"
    tasks.build(out, testing=True)
    _write_fake_receipts(out, host=False)
    missing = tasks.audit(out, cycle=2)
    assert [finding["id"] for finding in missing["findings"]] == [
        "cycle-02/family/host-verify-missing"
    ]
    assert missing["findings"][0]["severity"] == "moderate"
    assert missing["decision"] == "repair-and-reverify"
    shutil.rmtree(out / ".state/audits")
    _write_fake_receipts(out, stale_host=True)
    stale = tasks.audit(out, cycle=3)
    assert [finding["id"] for finding in stale["findings"]] == [
        "cycle-03/family/stale-host-verify"
    ]
    assert stale["findings"][0]["severity"] == "blocker"


def test_verify_runner_is_one_parametrized_script() -> None:
    docker = tasks._verify_runner("/work", "/input/family.tar")
    assert "/work/family" in docker and "/input/family.tar" in docker
    assert "@WORK@" not in docker and "@INPUT@" not in docker
    host = tasks._verify_runner("/tmp/host-work", "/tmp/host-family.tar")
    assert "/tmp/host-work/family" in host and "/tmp/host-family.tar" in host
    assert "@WORK@" not in host and "@INPUT@" not in host
    assert docker.replace("/work", "@W@").replace("/input/family.tar", "@I@") == host.replace(
        "/tmp/host-work", "@W@"
    ).replace("/tmp/host-family.tar", "@I@")


def test_cli_exposes_verify_host() -> None:
    args = tasks._parser().parse_args(["--verify-host"])
    assert args.verify_host is True
