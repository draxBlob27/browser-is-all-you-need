"""Modal 8x H100 runner for the GLM-4.7-Flash Miles lane.

One app, one heavy function. Every stage (convert / probe / sft / grpo) runs
the repo's own launcher scripts inside the Miles image on a single 8x H100
container; volumes carry the model, data, and run outputs across containers.

Stages:
    modal run examples/modal/modal_app.py::download_weights
    modal run examples/modal/modal_app.py::convert
    modal run examples/modal/modal_app.py::probe
    modal run examples/modal/modal_app.py::sft
    modal run examples/modal/modal_app.py::grpo

Discipline (from the slime-sss lane, reimplemented Modal-native):
- fail-fast W&B auth check before any GPU minute is spent
- per-stage receipt (env + git SHA + timing) written to the runs volume
- C++ runtime preflight (local backend) before reward-bearing stages
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import modal

REPO_URL = "https://github.com/tokenbender/browser-is-all-you-need.git"
REPO_REF = os.environ.get("W8_MODAL_REPO_REF", "pie-slime-posttraining")
MILES_IMAGE = os.environ.get("W8_MODAL_MILES_IMAGE", "radixark/miles:latest-cu12")
HF_MODEL_ID = "zai-org/GLM-4.7-Flash"

REPO_DIR = "/workspace/browser-is-all-you-need"
MODELS_DIR = "/root/models"
HF_DIR = "/hfmodels"
RUNS_DIR = "/workspace/runs"
DATA_DIR = "/data"

app = modal.App("glm47-pie-cpp")

# glm47-models2 is a VolumeFS v2 volume: the original v1 volume served
# inconsistent views of the checkpoint prefix after delete/recommit churn
# (listings oscillated between snapshots with no containers running). The
# static HF weights stay on the old v1 volume, which has always read fine.
models_vol = modal.Volume.from_name("glm47-models2")
hf_vol = modal.Volume.from_name("glm47-models")
data_vol = modal.Volume.from_name("glm47-data", create_if_missing=True)
runs_vol = modal.Volume.from_name("glm47-runs", create_if_missing=True)

# The gcc:13 sandbox image used on the A100 line compiled with GCC 13; install
# the same major version from the toolchain PPA so oracle-vs-candidate timing
# runs under the closest compiler. Reward fairness is relative (both sides use
# the same g++), but keeping the major version avoids gratuitous drift.
image = (
    modal.Image.from_registry(MILES_IMAGE)
    .apt_install("software-properties-common", "rsync", "gawk", "util-linux", "git")
    .run_commands(
        "add-apt-repository -y ppa:ubuntu-toolchain-r/test && apt-get update "
        "&& DEBIAN_FRONTEND=noninteractive apt-get install -y g++-13 gcc-13 "
        "&& update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 100 "
        "&& update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 100 "
        "|| echo 'gcc-13 PPA unavailable; falling back to distro g++'",
    )
    .pip_install("huggingface_hub[hf_transfer]")
    # The image ships sglang-kernel 0.4.2.post2+cu129 but its sglang engine
    # asserts >=0.4.4 at boot. Fires on any Engine init (standalone eval,
    # GRPO rollouts); SFT's debug-train-only path never boots an engine,
    # which is why the fit probe passed without it.
    .run_commands("pip install 'sglang-kernel>=0.4.4' --force-reinstall --no-deps")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

GPU_KW = dict(
    image=image,
    gpu="H100!:8",
    cpu=48.0,
    memory=(262_144, 1_048_576),  # request 256 GiB host RAM (trainer offload ~150 GiB), no tight cap
    timeout=86_400,
    volumes={MODELS_DIR: models_vol, HF_DIR: hf_vol, DATA_DIR: data_vol, RUNS_DIR: runs_vol},
    secrets=[modal.Secret.from_name("wandb-glm47")],
)


def _sh(
    cmd: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    log: str | None = None,
) -> None:
    """Run a shell command; with log=, tee output to a durable file on the runs
    volume so failures survive Modal's log retention window.

    Uses bash -c (not -lc): login shells on some images re-source profiles that
    drop non-standard env vars, which broke W8_CPP_SANDBOX_BACKEND=local on the
    first probe and fell through to the docker CLI preflight.
    """
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        cmd = f"set -o pipefail; ({cmd}) 2>&1 | tee {log}"
    print(f"+ {cmd}", flush=True)
    # subprocess requires str values; filter None that can appear from os.environ edge cases
    merged = {k: str(v) for k, v in {**os.environ, **(env or {})}.items() if v is not None}
    try:
        subprocess.run(["bash", "-c", cmd], cwd=cwd, env=merged, check=True)
    except subprocess.CalledProcessError:
        if log:
            runs_vol.commit()
            print(f"stage failed; full log preserved at {log}", flush=True)
            print(Path(log).read_text()[-4000:], flush=True)
        raise


def _checkout(sha: str) -> None:
    if not Path(REPO_DIR, ".git").exists():
        _sh(f"git clone --branch {REPO_REF} {REPO_URL} {REPO_DIR}")
    _sh(f"git fetch origin {REPO_REF} && git checkout {sha or f'origin/{REPO_REF}'}", cwd=REPO_DIR)
    _sh("git rev-parse HEAD", cwd=REPO_DIR)


def _wandb_check() -> None:
    """Fail before burning GPU time if W&B capture cannot work."""
    _sh(
        "python -c \"import os,wandb;"
        "assert os.environ.get('WANDB_API_KEY'),'WANDB_API_KEY missing';"
        "v=wandb.Api(timeout=30).viewer; print('wandb_auth_ok', v.entity)\""
    )


def _reward_preflight() -> None:
    """Prove local-backend CPU-time measurement works before reward stages."""
    env = {**os.environ, "W8_CPP_SANDBOX_BACKEND": "local", "PYTHONPATH": f"{REPO_DIR}/src"}
    out = subprocess.run(
        [
            "python",
            "-c",
            "from w8_biayn.cpp_perf.sandbox import run_runtime_preflight;"
            "import json; r = run_runtime_preflight(cpu='3');"
            "print(json.dumps(r.as_dict(), default=str))",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    print(out.stdout[-2000:], out.stderr[-2000:], flush=True)
    payload = json.loads(out.stdout.strip().splitlines()[-1])
    if not payload.get("ok"):
        raise RuntimeError(f"local reward preflight failed: {payload.get('reason')}")
    print(f"reward_preflight_ok cpu_ns={payload['runtime_cpu_ns']}", flush=True)

    # Granularity check: the canonical preflight binary is ~0.1ms and can
    # legitimately measure ~0 under coarse clocks. Real PIE benchmarks run for
    # milliseconds-to-seconds, so what matters is that a ~200ms busy loop
    # measures within a sane band — a clamped-zero clock here would corrupt
    # every speedup reward.
    check = subprocess.run(
        [
            "bash",
            "-lc",
            "cd $(mktemp -d) && cat > busy.cpp <<'CPP'\n"
            "#include <cstdio>\n"
            "int main(){volatile unsigned long long s=0;"
            "for(unsigned long long i=0;i<400000000ULL;i++) s+=i;"
            "printf(\"%llu\\n\", s); return 0;}\n"
            "CPP\n"
            "g++ -O0 busy.cpp -o busy && "
            "python3 -c \"import os,time,subprocess;"
            "t=time.monotonic(); r=subprocess.run(['./busy'],capture_output=True);"
            "u=os.times(); wall=time.monotonic()-t;"
            "print(f'child_cpu_s={u.children_user+u.children_system:.4f} wall_s={wall:.4f}')\"",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    print(f"timing_granularity: {check.stdout.strip()}", flush=True)
    fields = dict(kv.split("=") for kv in check.stdout.split())
    child_cpu = float(fields["child_cpu_s"])
    wall = float(fields["wall_s"])
    if not (0.25 * wall <= child_cpu <= 2.0 * wall) or child_cpu < 0.05:
        raise RuntimeError(
            f"child CPU-time accounting looks broken (cpu={child_cpu}s wall={wall}s); "
            "rewards would be garbage — stop before GRPO"
        )
    print("timing_granularity_ok", flush=True)


def _receipt(stage: str, run_id: str, extra: dict) -> None:
    receipt_dir = Path(RUNS_DIR, "receipts")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True
    ).stdout.strip()
    body = {
        "stage": stage,
        "run_id": run_id,
        "repo_sha": sha,
        "image": MILES_IMAGE,
        "env": {k: v for k, v in os.environ.items() if k.startswith(("MILES_", "W8_"))},
        **extra,
    }
    (receipt_dir / f"{run_id}.{stage}.json").write_text(json.dumps(body, indent=2))
    runs_vol.commit()


def _base_env(run_id: str) -> dict[str, str]:
    return {
        "MILES_RUN_ID": run_id,
        "MILES_RUN_ROOT": f"{RUNS_DIR}/issue10-miles/{run_id}",
        "MILES_HF_CHECKPOINT": f"{HF_DIR}/GLM-4.7-Flash",
        "MILES_REF_LOAD_DIR": f"{MODELS_DIR}/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8",
        "MILES_CPP_DATA_DIR": f"{DATA_DIR}/glm47-pie-data-sft-full-seq4096",
        "MILES_CPP_TASKS_DIR": f"{DATA_DIR}/pie-tasks-full-20260706",
        "W8_CPP_SANDBOX_BACKEND": "local",
        "W8_CPP_REWARD_WORKERS": "32",
        "WANDB_MODE": os.environ.get("WANDB_MODE", "online"),
        "WANDB_DIR": f"{RUNS_DIR}/wandb",
        "PYTHONUNBUFFERED": "1",
    }


def _ckpt_meta_path(ref: Path) -> Path:
    """Resolve the dist-ckpt .metadata path for either marker convention:
    a numeric iteration (iter_NNNNNNN/) or the converter's weights-only
    'release' tag (release/)."""
    tag = (ref / "latest_checkpointed_iteration.txt").read_text().strip()
    dirname = "release" if tag == "release" else f"iter_{int(tag):07d}"
    return ref / dirname / ".metadata"


def _require_ref_checkpoint(env: dict[str, str]) -> None:
    """Fail in seconds — not after a five-minute Ray boot — if the converted
    checkpoint is absent or incomplete (missing .metadata = unfinalized save
    or an unpropagated volume commit)."""
    ref = Path(env["MILES_REF_LOAD_DIR"])
    marker = ref / "latest_checkpointed_iteration.txt"
    if not marker.exists():
        raise RuntimeError(f"ref checkpoint missing: {marker}; run the convert stage first")
    meta = _ckpt_meta_path(ref)
    if not meta.exists():
        raise RuntimeError(
            f"ref checkpoint incomplete: {meta} missing — the conversion save "
            "did not finalize or its volume commit has not propagated; "
            "re-run convert or wait and retry"
        )
    print(f"ref_checkpoint_ok {meta.parent}", flush=True)


def _run_stage(script: str, run_id: str, env: dict[str, str], stage: str) -> None:
    _wandb_check()
    _require_ref_checkpoint(env)
    started = time.time()
    Path(RUNS_DIR, "wandb").mkdir(parents=True, exist_ok=True)
    # PYTHONPATH must stay unset at launch (sitecustomize import storm breaks
    # Ray node start); the runner rebuilds it inside the Ray runtime env.
    _sh(
        f"unset PYTHONPATH && cd {REPO_DIR} && bash {script}",
        env=env,
        log=f"{RUNS_DIR}/receipts/{run_id}.{stage}.log",
    )
    _receipt(stage, run_id, {"wall_s": round(time.time() - started, 1), "script": script})


slim_image = (
    modal.Image.debian_slim()
    .pip_install("huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)


@app.function(image=slim_image, timeout=14_400, cpu=16.0, volumes={HF_DIR: hf_vol})
def download_weights() -> None:
    """Pull the HF checkpoint into the weights volume (CPU-only container)."""
    target = f"{HF_DIR}/GLM-4.7-Flash"
    _sh(f"hf download {HF_MODEL_ID} --local-dir {target}")
    _sh(f"ls {target} | head; du -sh {target}")
    hf_vol.commit()


@app.function(**GPU_KW)
def run(stage: str, sha: str = "", run_id: str = "", env_overrides: str = "{}") -> str:
    """Run one lane stage on the 8x H100 container."""
    _checkout(sha)
    _sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | sort | uniq -c")
    rid = run_id or f"glm47_h100_{stage}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    env = _base_env(rid)
    env.update(json.loads(env_overrides))

    if stage == "convert":
        started = time.time()
        _sh(
            f"cd {REPO_DIR} && unset PYTHONPATH && "
            "bash examples/miles/glm47_h100_convert_tp4_pp1_ep8.sh",
            env=env,
            log=f"{RUNS_DIR}/receipts/{rid}.convert.log",
        )
        # The dist save's .metadata is written at finalize; wait for it before
        # committing so an unfinalized save can never be committed as a
        # checkpoint (that failure mode cost two debugging rounds).
        ref = Path(env["MILES_REF_LOAD_DIR"])
        marker = ref / "latest_checkpointed_iteration.txt"
        if not marker.exists():
            raise RuntimeError(f"conversion produced no checkpoint marker at {marker}")
        meta = _ckpt_meta_path(ref)
        for _ in range(60):
            if meta.exists():
                break
            time.sleep(5)
        else:
            raise RuntimeError(f"conversion save never finalized: {meta} missing after 300s")
        models_vol.commit()
        _receipt(stage, rid, {"wall_s": round(time.time() - started, 1)})
    elif stage == "probe":
        # Short SFT over the 64 longest rows: fit + DeepEP-under-gVisor check.
        # Separate data dir so the runner's build-data step constructs the
        # 64-row size-sorted subset instead of skipping on the full manifest.
        env["MILES_CPP_DATA_DIR"] = f"{RUNS_DIR}/probe-data"
        env.setdefault("MILES_SFT_NUM_EPOCH", "1")
        env.setdefault("MILES_CPP_TRAIN_LIMIT", "64")
        env.setdefault("MILES_CPP_EVAL_LIMIT", "4")
        env.setdefault("MILES_CPP_SORT_BY_SIZE", "1")
        _reward_preflight()
        _run_stage("examples/miles/glm47_cpp_perf_lora_r16_h100_sft.sh", rid, env, stage)
    elif stage == "sft":
        _run_stage("examples/miles/glm47_cpp_perf_lora_r16_h100_sft.sh", rid, env, stage)
    elif stage == "eval":
        # Standalone eval, flag-identical to the A100 anchor recipe
        # (base_spec.receipt.json): greedy, 1536-token budget, vendor no-think
        # template, 1 sample/task. Uses HF weights directly — no ref checkpoint.
        model = env.get("W8_EVAL_MODEL", f"{HF_DIR}/GLM-4.7-Flash")
        adapter = env.get("W8_EVAL_ADAPTER", "")
        label = env.get("W8_EVAL_LABEL", "base_h100_spec")
        out_dir = f"{RUNS_DIR}/issue10-miles/{rid}/eval"
        _wandb_check()
        _reward_preflight()
        started = time.time()
        lora_flags = ""
        if adapter:
            lora_flags = (
                f"--adapter {adapter} "
                "--lora-target-modules q_a_proj,kv_a_proj_with_mqa,o_proj,gate_proj,up_proj,down_proj "
                "--experts-shared-outer-loras --lora-use-virtual-experts "
            )
        _sh(
            f"cd {REPO_DIR} && PYTHONPATH={REPO_DIR}/src python3 scripts/eval_sglang_lora_cpp_perf.py "
            f"--data-dir {env['MILES_CPP_DATA_DIR']} --model {model} {lora_flags}"
            f"--label {label} --output-dir {out_dir} --backend sglang "
            "--samples-per-task 1 --temperature 0.0 --top-p 1.0 --max-tokens 1536 "
            f"--tp-size {env.get('W8_EVAL_TP', '8')} --mem-fraction-static 0.85 "
            "--cuda-graph-max-bs 64 --batch-size 64 --score-workers 32 "
            "--apply-chat-template --chat-template-kwargs '{\"enable_thinking\": false}' "
            f"--wandb-project glm47-pie-cpp-posttraining --wandb-group glm47-h100-evals "
            f"--wandb-run-id {rid}",
            env=env,
            log=f"{RUNS_DIR}/receipts/{rid}.eval.log",
        )
        _receipt(stage, rid, {"wall_s": round(time.time() - started, 1), "label": label, "model": model, "adapter": adapter})
    elif stage == "grpo":
        env.setdefault("MILES_LORA_ADAPTER_PATH", f"{DATA_DIR}/adapter_warmstart_iter_0000244")
        _reward_preflight()
        _run_stage("examples/miles/glm47_cpp_perf_lora_r16_h100_grpo.sh", rid, env, stage)
    else:
        raise ValueError(f"unknown stage: {stage}")

    runs_vol.commit()
    return rid


@app.local_entrypoint()
def convert(sha: str = ""):
    print(run.remote("convert", sha=sha))


@app.local_entrypoint()
def probe(sha: str = ""):
    print(run.remote("probe", sha=sha))


@app.local_entrypoint()
def sft(sha: str = "", run_id: str = ""):
    print(run.remote("sft", sha=sha, run_id=run_id))


@app.local_entrypoint()
def grpo(sha: str = "", run_id: str = "", env_overrides: str = "{}"):
    print(run.remote("grpo", sha=sha, run_id=run_id, env_overrides=env_overrides))


@app.local_entrypoint()
def evaluate(sha: str = "", run_id: str = "", env_overrides: str = "{}"):
    print(run.remote("eval", sha=sha, run_id=run_id, env_overrides=env_overrides))
