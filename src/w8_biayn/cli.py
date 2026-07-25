"""Aider benchmark SFT task CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

app = typer.Typer(help="Aider benchmark SFT task utilities.")
data_app = typer.Typer(help="Build and verify Aider SFT data.")
data_aider_sft_app = typer.Typer(help="Build reviewed Aider-style C++ SFT data.")

app.add_typer(data_app, name="data")
data_app.add_typer(data_aider_sft_app, name="aider-sft")

console = Console()


@app.command("scope")
def scope() -> None:
    """Print the branch scope document path."""

    console.print("docs/AIDER_BENCHMARK_SFT_TASK_BRANCH_SCOPE.md")


def _aider_sft_call(operation: Any) -> dict[str, Any]:
    from .aider_sft.errors import AiderSftError

    try:
        result = operation()
    except AiderSftError as exc:
        console.print_json(data=exc.as_dict())
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    return result


@data_aider_sft_app.command("plan")
def data_aider_sft_plan(
    config: Path = typer.Option(..., "--config", help="Strict Aider SFT profile TOML."),
) -> None:
    """Validate frozen identities without spending or generating."""

    from .aider_sft.pipeline import plan_dataset

    _aider_sft_call(lambda: plan_dataset(config_path=config, repo_root=Path(".").resolve()))


@data_aider_sft_app.command("inventory")
def data_aider_sft_inventory(
    config: Path = typer.Option(..., "--config", help="Strict Aider SFT profile TOML."),
    out: Path = typer.Option(..., "--out", help="Ignored construction root."),
) -> None:
    """Discover the exact source inventory and profile deficit cells."""

    from .aider_sft.pipeline import inventory_dataset

    _aider_sft_call(
        lambda: inventory_dataset(
            config_path=config,
            output_root=out.resolve(),
            repo_root=Path(".").resolve(),
        )
    )


@data_aider_sft_app.command("prepare-tokenizer")
def data_aider_sft_prepare_tokenizer(
    out: Path = typer.Option(..., "--out", help="Pinned local tokenizer-only snapshot."),
) -> None:
    """Download and validate only the profile's pinned tokenizer assets."""

    from .aider_sft.runtime_assets import prepare_tokenizer_snapshot

    _aider_sft_call(lambda: prepare_tokenizer_snapshot(output_root=out.resolve()))


@data_aider_sft_app.command("prepare-seccomp")
def data_aider_sft_prepare_seccomp(
    out: Path = typer.Option(..., "--out", help="Pinned local seccomp JSON path."),
) -> None:
    """Download and validate the repository-pinned seccomp profile."""

    from .aider_sft.runtime_assets import prepare_seccomp_profile

    _aider_sft_call(lambda: prepare_seccomp_profile(output_path=out.resolve()))


@data_aider_sft_app.command("inventory-promote")
def data_aider_sft_inventory_promote(
    proposal: Path = typer.Option(..., "--proposal"),
    decisions: Path = typer.Option(..., "--decisions"),
    out: Path = typer.Option(..., "--out"),
    config: Path = typer.Option(..., "--config", help="Profile TOML."),
) -> None:
    """Promote only an exactly approved source proposal."""

    from .aider_sft.pipeline import promote_inventory

    _aider_sft_call(
        lambda: promote_inventory(
            proposal_path=proposal,
            decisions_path=decisions,
            output_path=out,
            repo_root=Path(".").resolve(),
            config_path=config,
        )
    )


@data_aider_sft_app.command("build")
def data_aider_sft_build(
    config: Path = typer.Option(..., "--config", help="Strict Aider SFT profile TOML."),
    out: Path = typer.Option(..., "--out", help="Ignored construction root."),
    resume: bool = typer.Option(False, "--resume", help="Resume a matching incomplete root."),
    acknowledge_paid_llm_calls: bool = typer.Option(
        False,
        "--acknowledge-paid-llm-calls",
        help="Permit budgeted authoring calls after all approval gates.",
    ),
) -> None:
    """Build or resume canonical candidates and review queues."""

    from .aider_sft.pipeline import build_dataset

    _aider_sft_call(
        lambda: build_dataset(
            config_path=config,
            output_root=out.resolve(),
            repo_root=Path(".").resolve(),
            resume=resume,
            acknowledge_paid_llm_calls=acknowledge_paid_llm_calls,
        )
    )


@data_aider_sft_app.command("review-export")
def data_aider_sft_review_export(
    root: Path = typer.Option(..., "--root"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Export deterministic, fingerprint-bound review subjects."""

    from .aider_sft.pipeline import review_export

    _aider_sft_call(lambda: review_export(root=root.resolve(), output=out.resolve()))


@data_aider_sft_app.command("review-import")
def data_aider_sft_review_import(
    root: Path = typer.Option(..., "--root"),
    decisions: Path = typer.Option(..., "--decisions"),
) -> None:
    """Import authorized structured review decisions without editing tasks."""

    from .aider_sft.pipeline import review_import

    _aider_sft_call(lambda: review_import(root=root.resolve(), decisions_path=decisions.resolve()))


@data_aider_sft_app.command("finalize")
def data_aider_sft_finalize(
    root: Path = typer.Option(..., "--root"),
) -> None:
    """Freeze an approved split, render rows, and write readiness."""

    from .aider_sft.pipeline import finalize_dataset

    _aider_sft_call(lambda: finalize_dataset(root=root.resolve()))


@data_aider_sft_app.command("verify")
def data_aider_sft_verify(
    root: Path = typer.Option(..., "--root"),
    rerun_oracles: bool = typer.Option(False, "--rerun-oracles"),
    scratch_parent: Optional[Path] = typer.Option(None, "--scratch-parent"),
) -> None:
    """Recompute readiness and evidence."""

    from .aider_sft.pipeline import verify_dataset

    _aider_sft_call(
        lambda: verify_dataset(
            root=root.resolve(),
            rerun_oracles=rerun_oracles,
            scratch_parent=scratch_parent.resolve() if scratch_parent else None,
        )
    )


@data_aider_sft_app.command("export")
def data_aider_sft_export(
    root: Path = typer.Option(..., "--root"),
    audience: str = typer.Option(..., "--audience"),
    out: Path = typer.Option(..., "--out"),
) -> None:
    """Export an allowlist-only consumer bundle."""

    from .aider_sft.pipeline import export_dataset

    _aider_sft_call(
        lambda: export_dataset(
            root=root.resolve(),
            audience=audience,
            output=out.resolve(),
        )
    )


@data_aider_sft_app.command("verify-export")
def data_aider_sft_verify_export(
    root: Path = typer.Option(..., "--root"),
) -> None:
    """Independently reconcile a sanitized consumer bundle."""

    from .aider_sft.pipeline import verify_export

    _aider_sft_call(lambda: verify_export(root=root.resolve()))


@data_aider_sft_app.command("export-minimal")
def data_aider_sft_export_minimal(
    root: Path = typer.Option(..., "--root"),
    out: Path = typer.Option(..., "--out"),
    model_family: str = typer.Option("aider-sft", "--model-family"),
    purpose: str = typer.Option("aider-task-sft", "--purpose"),
    source_prefix: str = typer.Option("exercism-cpp", "--source-prefix"),
) -> None:
    """Project a ready dataset to a minimal train.jsonl."""

    from .aider_sft.pipeline import export_minimal_dataset

    _aider_sft_call(
        lambda: export_minimal_dataset(
            root=root.resolve(),
            output=out.resolve(),
            model_family=model_family,
            purpose=purpose,
            source_prefix=source_prefix,
        )
    )
