"""Immutable schemas for the Aider C++ whole-file RL lane."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "aider-cpp-rl-task-v2"
REWARD_POLICY_VERSION = "aider-cpp-rubric-correctness-v2"
PARSER_VERSION = "aider-whole-strict-v1"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_PATH_COMPONENTS = {
    ".meta",
    ".mutants",
    ".private",
    ".reference",
    ".state",
    "tests",
    "test",
    "CMakeLists.txt",
}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


PARSER_FINGERPRINT = canonical_sha256(PARSER_VERSION)
REWARD_FINGERPRINT = canonical_sha256(REWARD_POLICY_VERSION)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_path(value: str) -> str:
    if not value or "\x00" in value or "\\" in value:
        raise ValueError("path must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        raise ValueError("absolute paths are forbidden")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path traversal and non-canonical paths are forbidden")
    if path.as_posix() != value:
        raise ValueError("path must be canonical POSIX syntax")
    return value


class EditableFile(BaseModel):
    """One ordered file that the policy must replace completely."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    reference_path: str
    starter_sha256: str
    max_bytes: int = Field(default=262_144, gt=0, le=1_048_576)

    _safe_path = field_validator("path", "reference_path")(validate_relative_path)

    @model_validator(mode="after")
    def _private_reference(self) -> "EditableFile":
        if not self.reference_path.startswith(".reference/"):
            raise ValueError("reference_path must stay under the private .reference directory")
        return self

    @field_validator("starter_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("starter_sha256 must be a lowercase SHA-256 digest")
        return value


class FileIdentity(BaseModel):
    """One immutable private file bound by its task-relative path and bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str

    _safe_path = field_validator("path")(validate_relative_path)

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("file identity must use a lowercase SHA-256 digest")
        return value


class CommandSpec(BaseModel):
    """Trusted argv templates executed inside the pinned grader container."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    configure: list[str]
    build_solution: list[str]
    build_tests: list[str]
    discover_visible: list[str]
    run_visible: list[str]
    discover_hidden: list[str]
    run_hidden: list[str]
    sanitizer_configure: list[str]
    sanitizer_build_solution: list[str]
    sanitizer_build_tests: list[str]
    sanitizer_discover_visible: list[str]
    sanitizer_run_visible: list[str]
    sanitizer_discover_hidden: list[str]
    sanitizer_run_hidden: list[str]
    configure_timeout_s: int = Field(default=30, gt=0, le=600)
    build_timeout_s: int = Field(default=120, gt=0, le=1800)
    test_timeout_s: int = Field(default=60, gt=0, le=600)

    @field_validator(
        "configure",
        "build_solution",
        "build_tests",
        "discover_visible",
        "run_visible",
        "discover_hidden",
        "run_hidden",
        "sanitizer_configure",
        "sanitizer_build_solution",
        "sanitizer_build_tests",
        "sanitizer_discover_visible",
        "sanitizer_run_visible",
        "sanitizer_discover_hidden",
        "sanitizer_run_hidden",
    )
    @classmethod
    def _nonempty_safe_argv(cls, value: list[str]) -> list[str]:
        if not value or any(not token or "\x00" in token for token in value):
            raise ValueError("grader commands must be non-empty argv arrays")
        allowed = {"{task}", "{build}"}
        for token in value:
            for match in re.findall(r"\{[^{}]+\}", token):
                if match not in allowed:
                    raise ValueError(f"unsupported command placeholder: {match}")
        return value

    @model_validator(mode="after")
    def _locked_cpp17_sanitizer_profile(self) -> "CommandSpec":
        normal = " ".join(self.configure)
        if "CMAKE_CXX_STANDARD=17" not in normal or "Unix Makefiles" not in normal:
            raise ValueError("normal configure command must lock C++17 and Unix Makefiles")
        sanitizer = " ".join(
            [
                *self.sanitizer_configure,
                *self.sanitizer_build_solution,
                *self.sanitizer_build_tests,
            ]
        )
        if "-fsanitize=address,undefined" not in sanitizer:
            raise ValueError("sanitizer commands must lock ASan and UBSan instrumentation")
        return self


class TestSuiteIdentity(BaseModel):
    """Private identity and positive discovery expectation for a test suite."""

    __test__ = False

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_count: int = Field(gt=0)
    files: list[FileIdentity] = Field(min_length=1)
    fingerprint: str

    @field_validator("fingerprint")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("test fingerprint must be a lowercase SHA-256 digest")
        return value

    @field_validator("files")
    @classmethod
    def _unique_files(cls, values: list[FileIdentity]) -> list[FileIdentity]:
        paths = [item.path for item in values]
        if len(paths) != len(set(paths)):
            raise ValueError("test-suite file paths must be unique")
        return values

    @model_validator(mode="after")
    def _fingerprint_matches_files(self) -> "TestSuiteIdentity":
        expected = canonical_sha256([(item.path, item.sha256) for item in self.files])
        if self.fingerprint != expected:
            raise ValueError("test fingerprint does not match its ordered file identities")
        return self


class TokenEvidence(BaseModel):
    """Counts measured with the exact tokenizer and chat template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tokenizer_fingerprint: str
    chat_template_fingerprint: str
    prompt_tokens: int = Field(ge=0)
    answer_tokens: int = Field(gt=0)
    loss_mask_tokens: int = Field(gt=0)
    total_tokens: int = Field(gt=0)
    prompt_hash: str
    answer_hash: str
    prompt_token_ids_hash: str
    answer_token_ids_hash: str
    response_budget: int = Field(gt=0)

    @field_validator(
        "tokenizer_fingerprint",
        "chat_template_fingerprint",
        "prompt_hash",
        "answer_hash",
        "prompt_token_ids_hash",
        "answer_token_ids_hash",
    )
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("token evidence fingerprints must be lowercase SHA-256 digests")
        return value

    @model_validator(mode="after")
    def _consistent_counts(self) -> "TokenEvidence":
        if self.loss_mask_tokens > self.answer_tokens:
            raise ValueError("loss_mask_tokens cannot exceed answer_tokens")
        if self.total_tokens != self.prompt_tokens + self.answer_tokens:
            raise ValueError("total_tokens must equal prompt plus answer tokens")
        if self.response_budget < self.answer_tokens:
            raise ValueError("response_budget must cover the measured reference answer")
        return self


class OracleReceipt(BaseModel):
    """Admission proof that the private reference passes the exact grader."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_version: Literal["aider-oracle-v1"] = "aider-oracle-v1"
    reference_fingerprint: str
    grader_image_digest: str
    compiler_fingerprint: str
    normal_visible_count: int = Field(gt=0)
    normal_hidden_count: int = Field(gt=0)
    sanitizer_visible_count: int = Field(gt=0)
    sanitizer_hidden_count: int = Field(gt=0)
    full_success: Literal[True] = True

    @field_validator("reference_fingerprint", "compiler_fingerprint")
    @classmethod
    def _sha256_identity(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("oracle fingerprints must be lowercase SHA-256 digests")
        return value

    @field_validator("grader_image_digest")
    @classmethod
    def _image_digest(cls, value: str) -> str:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError("grader image must be bound by a sha256 image ID")
        return value


class EvidenceReceipt(BaseModel):
    """Private provenance or contamination-screen admission receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str = Field(min_length=1)
    status: Literal["passed"] = "passed"
    fingerprint: str
    details: dict[str, str] = Field(default_factory=dict)

    @field_validator("fingerprint")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("evidence fingerprint must be a lowercase SHA-256 digest")
        return value


class DraftEditableFile(BaseModel):
    """Human-authored editable-file declaration before admission computes hashes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    reference_path: str
    max_bytes: int = Field(default=262_144, gt=0, le=1_048_576)

    _safe_path = field_validator("path", "reference_path")(validate_relative_path)

    @model_validator(mode="after")
    def _private_reference(self) -> "DraftEditableFile":
        if not self.reference_path.startswith(".reference/"):
            raise ValueError("reference_path must stay under the private .reference directory")
        if any(
            part in PRIVATE_PATH_COMPONENTS or part.startswith("test")
            for part in PurePosixPath(self.path).parts
        ):
            raise ValueError("editable files cannot include private tests, references, or build files")
        return self


class DraftTestSuite(BaseModel):
    """Human-authored private test paths and expected discovered case count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_count: int = Field(gt=0)
    files: list[str] = Field(min_length=1)

    @field_validator("files")
    @classmethod
    def _safe_unique_files(cls, values: list[str]) -> list[str]:
        validated = [validate_relative_path(value) for value in values]
        if len(validated) != len(set(validated)):
            raise ValueError("draft test file paths must be unique")
        return validated


class RubricTestGroup(BaseModel):
    """Private commands that isolate one rubric's tests in one suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    visibility: Literal["visible", "hidden"]
    expected_count: int = Field(gt=0)
    discover: list[str]
    run: list[str]
    sanitizer_discover: list[str]
    sanitizer_run: list[str]

    @field_validator("discover", "run", "sanitizer_discover", "sanitizer_run")
    @classmethod
    def _nonempty_safe_argv(cls, value: list[str]) -> list[str]:
        if not value or any(not token or "\x00" in token for token in value):
            raise ValueError("rubric commands must be non-empty argv arrays")
        allowed = {"{task}", "{build}"}
        for token in value:
            for match in re.findall(r"\{[^{}]+\}", token):
                if match not in allowed:
                    raise ValueError(f"unsupported rubric command placeholder: {match}")
        return value


class DraftTaskRubric(BaseModel):
    """A catalog rubric bound to private test commands by a task author."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rubric_id: str
    test_groups: list[RubricTestGroup] = Field(min_length=1, max_length=2)

    @field_validator("rubric_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("rubric_id must be a stable safe identifier")
        return value

    @field_validator("test_groups")
    @classmethod
    def _unique_visibility(cls, values: list[RubricTestGroup]) -> list[RubricTestGroup]:
        visibility = [item.visibility for item in values]
        if len(visibility) != len(set(visibility)):
            raise ValueError("a rubric may have at most one test group per visibility")
        return values


class RubricSpec(DraftTaskRubric):
    """Resolved failure-derived behavior and reward weight for one task rubric."""

    capability: str
    failure_mode_ids: list[str] = Field(min_length=1)
    desired_behavior: str = Field(min_length=1)
    undesirable_behaviors: list[str] = Field(min_length=1)
    critical: bool = False
    weight: float = Field(gt=0.0, le=100.0)

    @field_validator("capability")
    @classmethod
    def _safe_capability(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("rubric capability must be a stable safe identifier")
        return value

    @field_validator("failure_mode_ids")
    @classmethod
    def _unique_failure_modes(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not SAFE_ID_RE.fullmatch(v) for v in values):
            raise ValueError("failure-mode IDs must be unique safe identifiers")
        return values


class DraftMutantFile(BaseModel):
    """Private faulty source file substituted for one editable target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_path: str
    source_path: str

    _safe_path = field_validator("target_path", "source_path")(validate_relative_path)

    @model_validator(mode="after")
    def _private_source(self) -> "DraftMutantFile":
        if not self.source_path.startswith(".mutants/"):
            raise ValueError("mutant source_path must stay under the private .mutants directory")
        return self


class MutantFile(DraftMutantFile):
    """Immutable identity for a private faulty implementation file."""

    sha256: str

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("mutant file identity must use a lowercase SHA-256 digest")
        return value


class DraftMutant(BaseModel):
    """Expected diagnostic behavior of an intentional model-like defect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mutant_id: str
    files: list[DraftMutantFile] = Field(min_length=1)
    expected_fail_rubric_ids: list[str] = Field(min_length=1)
    expected_pass_rubric_ids: list[str] = Field(min_length=1)

    @field_validator("mutant_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("mutant_id must be a stable safe identifier")
        return value

    @field_validator("files")
    @classmethod
    def _unique_targets(cls, values: list[DraftMutantFile]) -> list[DraftMutantFile]:
        targets = [item.target_path for item in values]
        if len(targets) != len(set(targets)):
            raise ValueError("mutant target paths must be unique")
        return values

    @field_validator("expected_fail_rubric_ids", "expected_pass_rubric_ids")
    @classmethod
    def _unique_rubrics(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not SAFE_ID_RE.fullmatch(v) for v in values):
            raise ValueError("mutant rubric IDs must be unique safe identifiers")
        return values

    @model_validator(mode="after")
    def _disjoint_expectations(self) -> "DraftMutant":
        if set(self.expected_fail_rubric_ids) & set(self.expected_pass_rubric_ids):
            raise ValueError("mutant fail/pass rubric expectations must be disjoint")
        return self


class MutantSpec(DraftMutant):
    """Admitted mutant with immutable private source identities."""

    files: list[MutantFile] = Field(min_length=1)


class AiderTaskDraft(BaseModel):
    """Minimal task-author input from which admission computes immutable evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    family_id: str
    lineage_id: str
    split: Literal["train", "anchor", "validation", "internal_test"]
    capability_tags: list[str] = Field(min_length=1)
    rubrics: list[DraftTaskRubric] = Field(min_length=2)
    mutants: list[DraftMutant] = Field(min_length=1)
    introduction: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    editable_files: list[DraftEditableFile] = Field(min_length=1)
    build: CommandSpec
    visible_tests: DraftTestSuite
    hidden_tests: DraftTestSuite
    provenance_receipt: EvidenceReceipt
    contamination_receipt: EvidenceReceipt
    response_budget_margin: int = Field(default=64, ge=0, le=4096)

    @field_validator("task_id", "family_id", "lineage_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("task, family, and lineage IDs must be stable safe identifiers")
        return value

    @field_validator("capability_tags")
    @classmethod
    def _unique_tags(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not SAFE_ID_RE.fullmatch(value) for value in values):
            raise ValueError("capability tags must be unique safe identifiers")
        return values

    @model_validator(mode="after")
    def _curriculum_is_diagnostic(self) -> "AiderTaskDraft":
        _validate_curriculum_bindings(self.capability_tags, self.rubrics, self.mutants)
        editable_paths = {item.path for item in self.editable_files}
        if any({item.target_path for item in mutant.files} != editable_paths for mutant in self.mutants):
            raise ValueError("every mutant must replace every editable file exactly once")
        return self


class AiderTask(BaseModel):
    """One admitted clean-room task bound to an immutable private tree."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["aider-cpp-rl-task-v2"] = SCHEMA_VERSION
    task_id: str
    family_id: str
    lineage_id: str
    split: Literal["train", "anchor", "validation", "internal_test"]
    capability_tags: list[str] = Field(min_length=1)
    curriculum_fingerprint: str
    rubrics: list[RubricSpec] = Field(min_length=2)
    mutants: list[MutantSpec] = Field(min_length=1)
    introduction: str = Field(min_length=1)
    instructions: str = Field(min_length=1)
    editable_files: list[EditableFile] = Field(min_length=1)
    build: CommandSpec
    visible_tests: TestSuiteIdentity
    hidden_tests: TestSuiteIdentity
    tree_digest: str
    prompt_fingerprint: str
    parser_fingerprint: str
    reward_fingerprint: str
    grader_image: str
    grader_image_digest: str
    compiler_fingerprint: str
    provenance_fingerprint: str
    contamination_fingerprint: str
    provenance_receipt: EvidenceReceipt
    contamination_receipt: EvidenceReceipt
    split_fingerprint: str
    token_evidence: TokenEvidence
    oracle_receipt: OracleReceipt
    task_digest: str = ""

    @field_validator("task_id", "family_id", "lineage_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("task, family, and lineage IDs must be stable safe identifiers")
        return value

    @field_validator("capability_tags")
    @classmethod
    def _unique_tags(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not SAFE_ID_RE.fullmatch(value) for value in values):
            raise ValueError("capability tags must be unique safe identifiers")
        return values

    @field_validator("editable_files")
    @classmethod
    def _unique_files(cls, files: list[EditableFile]) -> list[EditableFile]:
        paths = [item.path for item in files]
        if len(paths) != len(set(paths)):
            raise ValueError("editable file paths must be unique")
        for path in paths:
            if any(part in PRIVATE_PATH_COMPONENTS or part.startswith("test") for part in PurePosixPath(path).parts):
                raise ValueError("editable files cannot include private tests, references, or build files")
        return files

    @field_validator(
        "tree_digest",
        "prompt_fingerprint",
        "parser_fingerprint",
        "reward_fingerprint",
        "provenance_fingerprint",
        "contamination_fingerprint",
        "split_fingerprint",
        "compiler_fingerprint",
        "curriculum_fingerprint",
    )
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("task fingerprints must be lowercase SHA-256 digests")
        return value

    @field_validator("grader_image_digest")
    @classmethod
    def _task_image_digest(cls, value: str) -> str:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
            raise ValueError("grader image must be bound by a sha256 image ID")
        return value

    @model_validator(mode="after")
    def _identity_is_consistent(self) -> "AiderTask":
        _validate_curriculum_bindings(self.capability_tags, self.rubrics, self.mutants)
        visible_rubric_count = sum(
            group.expected_count
            for rubric in self.rubrics
            for group in rubric.test_groups
            if group.visibility == "visible"
        )
        hidden_rubric_count = sum(
            group.expected_count
            for rubric in self.rubrics
            for group in rubric.test_groups
            if group.visibility == "hidden"
        )
        if visible_rubric_count != self.visible_tests.expected_count:
            raise ValueError("visible tests must be partitioned exactly once across rubrics")
        if hidden_rubric_count != self.hidden_tests.expected_count:
            raise ValueError("hidden tests must be partitioned exactly once across rubrics")
        visible_paths = {item.path for item in self.visible_tests.files}
        hidden_paths = {item.path for item in self.hidden_tests.files}
        editable_paths = set(self.allowed_paths)
        if any({item.target_path for item in mutant.files} != editable_paths for mutant in self.mutants):
            raise ValueError("every mutant must replace every editable file exactly once")
        if visible_paths & hidden_paths:
            raise ValueError("visible and hidden test file identities must be disjoint")
        if editable_paths & (visible_paths | hidden_paths):
            raise ValueError("editable files cannot overlap private test identities")
        if self.grader_image_digest != self.oracle_receipt.grader_image_digest:
            raise ValueError("task and oracle grader image identities differ")
        if self.compiler_fingerprint != self.oracle_receipt.compiler_fingerprint:
            raise ValueError("task and oracle compiler identities differ")
        if self.visible_tests.expected_count != self.oracle_receipt.normal_visible_count:
            raise ValueError("visible test identity differs from oracle receipt")
        if self.hidden_tests.expected_count != self.oracle_receipt.normal_hidden_count:
            raise ValueError("hidden test identity differs from oracle receipt")
        if self.oracle_receipt.sanitizer_visible_count != self.visible_tests.expected_count:
            raise ValueError("sanitizer visible test identity differs from normal discovery")
        if self.oracle_receipt.sanitizer_hidden_count != self.hidden_tests.expected_count:
            raise ValueError("sanitizer hidden test identity differs from normal discovery")
        if self.provenance_fingerprint != self.provenance_receipt.fingerprint:
            raise ValueError("provenance receipt fingerprint mismatch")
        if self.contamination_fingerprint != self.contamination_receipt.fingerprint:
            raise ValueError("contamination receipt fingerprint mismatch")
        if self.prompt_fingerprint != self.token_evidence.prompt_hash:
            raise ValueError("prompt and token-evidence fingerprints differ")
        if self.parser_fingerprint != PARSER_FINGERPRINT:
            raise ValueError("task was admitted for a different parser policy")
        if self.reward_fingerprint != REWARD_FINGERPRINT:
            raise ValueError("task was admitted for a different reward policy")
        expected = self.compute_digest()
        if self.task_digest and self.task_digest != expected:
            raise ValueError("task_digest does not match canonical task content")
        return self

    @property
    def allowed_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.editable_files)

    def compute_digest(self) -> str:
        payload = self.model_dump(mode="json")
        payload["task_digest"] = ""
        return canonical_sha256(payload)

    def with_computed_digest(self) -> "AiderTask":
        return self.model_copy(update={"task_digest": self.compute_digest()})

    @classmethod
    def read_json(cls, path: str | Path) -> "AiderTask":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def write_json(self, path: str | Path) -> Path:
        task = self if self.task_digest else self.with_computed_digest()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(task.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return output


class StageResult(BaseModel):
    """One configure/build/discover/test stage result."""

    model_config = ConfigDict(extra="forbid")

    attempted: bool = False
    passed: bool = False
    timed_out: bool = False
    returncode: int | None = None
    discovered: int = Field(default=0, ge=0)
    passed_tests: int = Field(default=0, ge=0)
    duration_s: float = Field(default=0.0, ge=0.0)


class RubricHarnessResult(BaseModel):
    """Isolated normal and sanitizer evidence for one behavior rubric."""

    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    normal_visible: StageResult = Field(default_factory=StageResult)
    normal_hidden: StageResult = Field(default_factory=StageResult)
    sanitizer_visible: StageResult = Field(default_factory=StageResult)
    sanitizer_hidden: StageResult = Field(default_factory=StageResult)


class AiderHarnessResult(BaseModel):
    """Private result from normal and fresh sanitizer grading."""

    model_config = ConfigDict(extra="forbid")

    receipt_version: Literal["aider-grade-v2"] = "aider-grade-v2"
    unsafe_edit: bool = False
    configure_error: bool = False
    compile_error: bool = False
    timeout: bool = False
    infrastructure_error: bool = False
    infrastructure_reason: str | None = None
    normal_visible: StageResult = Field(default_factory=StageResult)
    normal_hidden: StageResult = Field(default_factory=StageResult)
    sanitizer_visible: StageResult = Field(default_factory=StageResult)
    sanitizer_hidden: StageResult = Field(default_factory=StageResult)
    sanitizer_error: bool = False
    rubric_results: list[RubricHarnessResult] = Field(default_factory=list)
    logs: dict[str, str] = Field(default_factory=dict)
    grader_image_digest: str | None = None
    task_digest: str | None = None

    @property
    def normal_all_pass(self) -> bool:
        return (
            self.normal_visible.discovered > 0
            and self.normal_hidden.discovered > 0
            and self.normal_visible.passed
            and self.normal_hidden.passed
        )

    @property
    def full_success(self) -> bool:
        return (
            self.normal_all_pass
            and self.sanitizer_visible.discovered > 0
            and self.sanitizer_hidden.discovered > 0
            and self.sanitizer_visible.passed
            and self.sanitizer_hidden.passed
            and not self.sanitizer_error
            and not self.infrastructure_error
        )

    @staticmethod
    def _fraction(stage: StageResult) -> float:
        if stage.discovered <= 0:
            return 0.0
        return min(stage.passed_tests, stage.discovered) / stage.discovered

    @property
    def visible_fraction(self) -> float:
        return self._fraction(self.normal_visible)

    @property
    def hidden_fraction(self) -> float:
        return self._fraction(self.normal_hidden)


def _validate_curriculum_bindings(
    capability_tags: list[str],
    rubrics: list[DraftTaskRubric] | list[RubricSpec],
    mutants: list[DraftMutant] | list[MutantSpec],
) -> None:
    rubric_ids = [item.rubric_id for item in rubrics]
    if len(rubric_ids) != len(set(rubric_ids)):
        raise ValueError("task rubric IDs must be unique")
    if rubrics and isinstance(rubrics[0], RubricSpec):
        unknown_capabilities = {
            item.capability for item in rubrics if item.capability not in capability_tags
        }
        if unknown_capabilities:
            raise ValueError("rubric capabilities must appear in task capability_tags")
    mutant_ids = [item.mutant_id for item in mutants]
    if len(mutant_ids) != len(set(mutant_ids)):
        raise ValueError("task mutant IDs must be unique")
    known = set(rubric_ids)
    targeted: set[str] = set()
    for mutant in mutants:
        referenced = set(mutant.expected_fail_rubric_ids) | set(mutant.expected_pass_rubric_ids)
        if not referenced <= known:
            raise ValueError("mutant expectations reference an unknown task rubric")
        targeted.update(mutant.expected_fail_rubric_ids)
    if targeted != known:
        raise ValueError("every task rubric must be targeted by at least one mutant")
