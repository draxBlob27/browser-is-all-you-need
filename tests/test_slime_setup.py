from __future__ import annotations

from pathlib import Path

from w8_biayn.slime_integration.setup import (
    DEFAULT_BOOTSTRAP_RELATIVE,
    DEFAULT_LAUNCHER_RELATIVE,
    build_slime_setup_plan,
    write_slime_setup_files,
)


def test_build_slime_setup_plan_uses_repo_name_for_mount(tmp_path: Path) -> None:
    plan = build_slime_setup_plan(tmp_path / "pipe-slime")

    assert plan.repo_mount == "/workspace/pipe-slime"
    assert plan.launcher_path == (tmp_path / "pipe-slime" / DEFAULT_LAUNCHER_RELATIVE)
    assert plan.bootstrap_path == (tmp_path / "pipe-slime" / DEFAULT_BOOTSTRAP_RELATIVE)


def test_write_slime_setup_files_creates_docker_launcher_and_bootstrap(tmp_path: Path) -> None:
    repo_root = tmp_path / "pipe-slime"
    repo_root.mkdir()
    plan = build_slime_setup_plan(repo_root, image="slimerl/slime:test", container_name="slime-test")

    launcher_path, bootstrap_path = write_slime_setup_files(plan)

    launcher = launcher_path.read_text(encoding="utf-8")
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    assert "docker pull slimerl/slime:test" in launcher
    assert "--name slime-test" in launcher
    assert 'DOCKER_CLI="${SLIME_DOCKER_CLI:-$(command -v docker)}"' in launcher
    assert "docker CLI is required on the host" in launcher
    assert 'SLIME_HOST_TMPDIR="${SLIME_HOST_TMPDIR:-/tmp/w8-biayn-slime-${USER:-user}}"' in launcher
    assert 'mkdir -p "${SLIME_HOST_TMPDIR}" "${SLIME_HOST_TMPDIR}/ray"' in launcher
    assert "-v /var/run/docker.sock:/var/run/docker.sock" in launcher
    assert f"-v {repo_root}:{plan.repo_mount}" in launcher
    assert '-v "${SLIME_HOST_TMPDIR}":"${SLIME_HOST_TMPDIR}" \\' in launcher
    assert '-e TMPDIR="${SLIME_HOST_TMPDIR}" \\' in launcher
    assert '-e RAY_TMPDIR="${SLIME_HOST_TMPDIR}/ray" \\' in launcher
    assert "-e DOCKER_HOST=unix:///var/run/docker.sock" in launcher
    assert "echo tmpdir=\\${TMPDIR}" in launcher
    assert "echo ray_tmpdir=\\${RAY_TMPDIR}" in launcher
    assert "echo docker_cli=/usr/local/bin/docker" in launcher
    assert '-v "${HOST_MODELS_DIR:-$HOME/models}":/root/models \\' in launcher
    assert '-v "${DOCKER_CLI}":/usr/local/bin/docker:ro \\' in launcher
    assert "bash /workspace/pipe-slime/.w8-biayn/slime/bootstrap-inside-container.sh" in launcher
    assert "exec /bin/bash" in launcher
    assert "export PYTHONPATH=/root/Megatron-LM${PYTHONPATH:+:${PYTHONPATH}}" in bootstrap
    assert "cd /root/slime" in bootstrap
    assert "pip install -e . --no-deps" in bootstrap
    assert "python train.py --help >/tmp/slime-train-help.txt" in bootstrap
