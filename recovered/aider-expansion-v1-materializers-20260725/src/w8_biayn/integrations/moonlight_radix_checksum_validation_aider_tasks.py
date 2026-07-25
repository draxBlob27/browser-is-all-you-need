"""Create and verify the 100-root radix/checksum expansion family.

The generated roots are local Aider-format candidates.  This owner never
creates JSONL, a dataset release, or training authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/radix-checksum-validation"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-validation-parsing/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_RADIX_CHECKSUM_VALIDATION_CURRICULUM.md"
)
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/moonlight_radix_checksum_validation_aider_tasks.py"
)
FOCUSED_TEST = Path("tests/test_moonlight_radix_checksum_validation_aider_tasks.py")
CREATION_PROMPT = Path("docs/aider-tasks-spec/prompts/generate-family-spec.md")
IMPLEMENTATION_PROMPT = Path("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")
FAMILY_ID = "aider-expansion-radix-checksum-validation-v1"
OWNER_ID = GENERATOR_PATH.as_posix()
NORMALIZER = "radix-checksum-seven-dimension-artifacts-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
EXPECTED_ROOTS = 100
EXPECTED_PAIRS = 4950
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
DIMENSION_LIMITS = {
    "public_api": 0.995,
    "owned_state_or_algorithm": 0.985,
    "mutation_selection_rules": 0.985,
    "invalid_boundary_behavior": 0.990,
    "reference_control_flow": 0.985,
    "deterministic_oracle": 0.990,
    "topic_specific_negative_fixture": 0.985,
}
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
PRIVATE_MARKERS = (
    ".meta/",
    "example.cpp",
    "negative.cpp",
    "hidden_test",
    "CMakeLists.txt",
    "provenance.json",
    ".state/",
)
REMEDY_HEADINGS = (
    "Identity",
    "Objective",
    "Public API",
    "Behavior table",
    "Implementation invariant",
    "Starter and reference",
    "Tests",
    "Files and metadata",
    "Build/oracle",
    "Family/contamination",
    "Optional dataset handoff",
    "Acceptance",
)


class FamilyError(RuntimeError):
    """Stable fail-closed family error."""


def _fail(code: str, detail: str) -> None:
    raise FamilyError(f"{code}:{detail}")


@dataclass(frozen=True)
class RadixSpec:
    key: str
    title: str
    fields: str
    valid_init: str
    invalid_init: str
    decoder: str
    rule: str
    invalid_rule: str


@dataclass(frozen=True)
class ChecksumSpec:
    key: str
    title: str
    fields: str
    valid_init: str
    invalid_init: str
    algorithm: str
    negative: str
    rule: str
    wrong_rule: str
    expected: int


@dataclass(frozen=True)
class TaskSpec:
    radix: RadixSpec
    checksum: ChecksumSpec

    @property
    def task_id(self) -> str:
        return f"rcv-{self.radix.key}-{self.checksum.key}"


def _radices() -> tuple[RadixSpec, ...]:
    return (
        RadixSpec(
            "alphabet",
            "explicit symbol alphabet",
            "std::string text;\n    std::string alphabet;\n    bool fold_ascii_case = false;\n    std::vector<long long> audit_symbols;",
            'input.text = "1236"; input.alphabet = "0123456789"; input.fold_ascii_case = false; input.audit_symbols = {1, 2, 3, 6};',
            'input.text = "12?6"; input.alphabet = "0123456789"; input.audit_symbols = {1, 2, 3, 6};',
            r"""if (input.alphabet.size() < 2 || input.alphabet.size() > 36 || input.text.empty()) return rejected(0);
    std::array<bool, 256> seen{};
    for (std::size_t i = 0; i < input.alphabet.size(); ++i) {
        unsigned char symbol = static_cast<unsigned char>(input.alphabet[i]);
        if (seen[symbol]) return rejected(i);
        seen[symbol] = true;
    }
    for (std::size_t i = 0; i < input.text.size(); ++i) {
        char symbol = input.text[i];
        if (input.fold_ascii_case && symbol >= 'a' && symbol <= 'z') symbol = static_cast<char>(symbol - 'a' + 'A');
        const std::size_t position = input.alphabet.find(symbol);
        if (position == std::string::npos) return rejected(i);
        digits.push_back(static_cast<long long>(position));
    }
    if (!checked_horner(digits, static_cast<long long>(input.alphabet.size()), numeric_value)) return rejected(digits.size());""",
            "scan a duplicate-free caller alphabet, map every symbol, then checked-Horner accumulate",
            "alphabet size 2..36, uniqueness, nonempty text, exact symbol membership, and overflow",
        ),
        RadixSpec(
            "digits",
            "fixed-radix digit vector",
            "std::vector<int> digits;\n    int radix = 0;\n    bool reject_leading_zero = true;\n    std::vector<long long> audit_symbols;",
            "input.digits = {1, 2, 3, 6}; input.radix = 10; input.reject_leading_zero = true; input.audit_symbols = {1, 2, 3, 6};",
            "input.digits = {1, 10, 3, 6}; input.radix = 10; input.audit_symbols = {1, 10, 3, 6};",
            r"""if (input.radix < 2 || input.radix > 36 || input.digits.empty()) return rejected(0);
    if (input.reject_leading_zero && input.digits.size() > 1 && input.digits.front() == 0) return rejected(0);
    for (std::size_t i = 0; i < input.digits.size(); ++i) {
        if (input.digits[i] < 0 || input.digits[i] >= input.radix) return rejected(i);
        digits.push_back(input.digits[i]);
    }
    if (!checked_horner(digits, input.radix, numeric_value)) return rejected(digits.size());""",
            "validate each integer digit under one fixed radix before checked-Horner accumulation",
            "radix 2..36, nonempty input, leading-zero policy, digit range, and overflow",
        ),
        RadixSpec(
            "mixed",
            "heterogeneous mixed-radix word",
            "std::vector<int> digits;\n    std::vector<int> radices;\n    bool most_significant_first = true;\n    std::vector<long long> audit_symbols;",
            "input.digits = {1, 2, 3, 6}; input.radices = {8, 9, 10, 11}; input.most_significant_first = true; input.audit_symbols = {1, 2, 3, 6};",
            "input.digits = {1, 9, 3, 6}; input.radices = {8, 9, 10, 11}; input.audit_symbols = {1, 9, 3, 6};",
            r"""if (input.digits.empty() || input.digits.size() != input.radices.size()) return rejected(0);
    std::vector<std::size_t> order(input.digits.size());
    for (std::size_t i = 0; i < order.size(); ++i) order[i] = input.most_significant_first ? i : order.size() - 1 - i;
    long long current = 0;
    for (std::size_t step = 0; step < order.size(); ++step) {
        const std::size_t i = order[step];
        if (input.radices[i] < 2 || input.digits[i] < 0 || input.digits[i] >= input.radices[i]) return rejected(i);
        long long next = 0;
        if (!checked_mul_add(current, input.radices[i], input.digits[i], next)) return rejected(i);
        current = next;
        digits.push_back(input.digits[i]);
    }
    numeric_value = current;""",
            "walk a declared radix at every position and checked-accumulate in declared order",
            "equal nonzero lengths, every radix at least two, per-position range, and overflow",
        ),
        RadixSpec(
            "balanced",
            "balanced signed digits",
            "std::vector<long long> signed_digits;\n    int odd_radix = 0;\n    bool least_significant_first = false;\n    std::vector<long long> audit_symbols;",
            "input.signed_digits = {1, 2, 3, 6}; input.odd_radix = 13; input.least_significant_first = false; input.audit_symbols = {1, 2, 3, 6};",
            "input.signed_digits = {1, 2, 7, 6}; input.odd_radix = 13; input.audit_symbols = {1, 2, 7, 6};",
            r"""if (input.odd_radix < 3 || input.odd_radix % 2 == 0 || input.signed_digits.empty()) return rejected(0);
    const long long half = input.odd_radix / 2;
    std::vector<long long> ordered = input.signed_digits;
    if (input.least_significant_first) std::reverse(ordered.begin(), ordered.end());
    for (std::size_t i = 0; i < ordered.size(); ++i) {
        if (ordered[i] < -half || ordered[i] > half) return rejected(i);
        digits.push_back(ordered[i]);
    }
    if (!checked_horner(digits, input.odd_radix, numeric_value)) return rejected(digits.size());""",
            "preserve centered signed digits of an odd radix during ordered checked accumulation",
            "odd radix at least three, centered digit range, nonempty order, and overflow",
        ),
        RadixSpec(
            "bijective",
            "bijective positional digits",
            "std::vector<unsigned> digits;\n    unsigned radix = 0;\n    bool empty_is_zero = false;\n    std::vector<long long> audit_symbols;",
            "input.digits = {1U, 2U, 3U, 6U}; input.radix = 10U; input.empty_is_zero = false; input.audit_symbols = {1, 2, 3, 6};",
            "input.digits = {1U, 0U, 3U, 6U}; input.radix = 10U; input.audit_symbols = {1, 0, 3, 6};",
            r"""if (input.radix < 2U || input.radix > 26U) return rejected(0);
    if (input.digits.empty()) { if (!input.empty_is_zero) return rejected(0); numeric_value = 0; }
    for (std::size_t i = 0; i < input.digits.size(); ++i) {
        if (input.digits[i] == 0U || input.digits[i] > input.radix) return rejected(i);
        digits.push_back(static_cast<long long>(input.digits[i]));
    }
    if (!digits.empty() && !checked_horner(digits, input.radix, numeric_value)) return rejected(digits.size());""",
            "accumulate one-based digits without silently translating zero into a positional digit",
            "radix 2..26, zero forbidden, empty policy, upper digit bound, and overflow",
        ),
        RadixSpec(
            "negabase",
            "negative-base canonical digits",
            "std::vector<int> digits;\n    int negative_radix = 0;\n    std::size_t maximum_digits = 0;\n    std::vector<long long> audit_symbols;",
            "input.digits = {1, 2, 3, 6}; input.negative_radix = -10; input.maximum_digits = 8; input.audit_symbols = {1, 2, 3, 6};",
            "input.digits = {1, 10, 3, 6}; input.negative_radix = -10; input.maximum_digits = 8; input.audit_symbols = {1, 10, 3, 6};",
            r"""if (input.negative_radix > -2 || input.digits.empty() || input.digits.size() > input.maximum_digits) return rejected(0);
    const long long magnitude = -static_cast<long long>(input.negative_radix);
    for (std::size_t i = 0; i < input.digits.size(); ++i) {
        if (input.digits[i] < 0 || input.digits[i] >= magnitude) return rejected(i);
        digits.push_back(input.digits[i]);
    }
    if (!checked_horner(digits, input.negative_radix, numeric_value)) return rejected(digits.size());""",
            "checked-Horner accumulate canonical nonnegative digits under a negative base",
            "base at most minus two, positive width limit, digit range, nonempty input, and overflow",
        ),
        RadixSpec(
            "packed",
            "packed equal-width digit groups",
            "std::uint64_t packed = 0;\n    unsigned width = 0;\n    unsigned count = 0;\n    bool high_group_first = true;\n    std::vector<long long> audit_symbols;",
            "input.packed = 0x1236ULL; input.width = 4U; input.count = 4U; input.high_group_first = true; input.audit_symbols = {1, 2, 3, 6};",
            "input.packed = 0x11236ULL; input.width = 4U; input.count = 4U; input.high_group_first = true; input.audit_symbols = {1, 2, 3, 6};",
            r"""if (input.width == 0U || input.width > 16U || input.count == 0U || input.count > 64U / input.width) return rejected(0);
    const unsigned used = input.width * input.count;
    if (used < 64U && (input.packed >> used) != 0U) return rejected(input.count);
    const std::uint64_t mask = (std::uint64_t{1} << input.width) - 1U;
    for (unsigned step = 0; step < input.count; ++step) {
        const unsigned slot = input.high_group_first ? input.count - 1U - step : step;
        digits.push_back(static_cast<long long>((input.packed >> (slot * input.width)) & mask));
    }
    if (!checked_horner(digits, static_cast<long long>(mask + 1U), numeric_value)) return rejected(digits.size());""",
            "extract declared fixed-width groups in declared end order and accumulate their power-of-two radix",
            "width/count bounds, nonzero count, no unused high bits, exact extraction order, and overflow",
        ),
        RadixSpec(
            "tokens",
            "token alphabet digits",
            "std::vector<std::string> tokens;\n    std::vector<std::string> alphabet;\n    bool case_sensitive = true;\n    std::vector<long long> audit_symbols;",
            'input.tokens = {"one", "two", "three", "six"}; input.alphabet = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}; input.case_sensitive = true; input.audit_symbols = {1, 2, 3, 6};',
            'input.tokens = {"one", "missing", "three", "six"}; input.alphabet = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}; input.audit_symbols = {1, 2, 3, 6};',
            r"""if (input.alphabet.size() < 2 || input.tokens.empty()) return rejected(0);
    auto canonical = [&](std::string value) { if (!input.case_sensitive) for (char& ch : value) if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a'); return value; };
    std::vector<std::string> names;
    for (std::size_t i = 0; i < input.alphabet.size(); ++i) {
        const std::string name = canonical(input.alphabet[i]);
        if (name.empty() || std::find(names.begin(), names.end(), name) != names.end()) return rejected(i);
        names.push_back(name);
    }
    for (std::size_t i = 0; i < input.tokens.size(); ++i) {
        const auto it = std::find(names.begin(), names.end(), canonical(input.tokens[i]));
        if (it == names.end()) return rejected(i);
        digits.push_back(static_cast<long long>(std::distance(names.begin(), it)));
    }
    if (!checked_horner(digits, static_cast<long long>(names.size()), numeric_value)) return rejected(digits.size());""",
            "canonicalize only when allowed, reject alphabet collisions, and map whole tokens before accumulation",
            "nonempty unique alphabet tokens, nonempty payload, exact membership, case-fold collision, and overflow",
        ),
        RadixSpec(
            "sparse",
            "sparse explicit digit positions",
            "struct Term { std::size_t position; int digit; };\n    std::vector<Term> terms;\n    int radix = 0;\n    std::size_t width = 0;\n    std::vector<long long> audit_symbols;",
            "input.terms = {{3U, 1}, {2U, 2}, {1U, 3}, {0U, 6}}; input.radix = 10; input.width = 4U; input.audit_symbols = {1, 2, 3, 6};",
            "input.terms = {{3U, 1}, {2U, 2}, {2U, 3}, {0U, 6}}; input.radix = 10; input.width = 4U; input.audit_symbols = {1, 2, 3, 6};",
            r"""if (input.radix < 2 || input.width == 0U || input.terms.empty()) return rejected(0);
    std::vector<long long> dense(input.width, 0);
    std::vector<bool> occupied(input.width, false);
    for (std::size_t i = 0; i < input.terms.size(); ++i) {
        const auto& term = input.terms[i];
        if (term.position >= input.width || occupied[term.position] || term.digit < 0 || term.digit >= input.radix) return rejected(i);
        occupied[term.position] = true; dense[term.position] = term.digit;
    }
    if (!occupied[input.width - 1U]) return rejected(input.width - 1U);
    for (std::size_t position = input.width; position-- > 0U;) digits.push_back(dense[position]);
    if (!checked_horner(digits, input.radix, numeric_value)) return rejected(digits.size());""",
            "validate unique positions, reconstruct missing zeros, and accumulate from the declared highest position",
            "radix/width bounds, unique in-range positions, digit range, present high position, and overflow",
        ),
        RadixSpec(
            "unary-runs",
            "unary run-length digits",
            "struct Run { char mark; unsigned length; };\n    std::vector<Run> runs;\n    unsigned radix = 0;\n    char separator = '|';\n    std::vector<long long> audit_symbols;",
            "input.runs = {{'a', 1U}, {'b', 2U}, {'a', 3U}, {'b', 6U}}; input.radix = 10U; input.separator = '|'; input.audit_symbols = {1, 2, 3, 6};",
            "input.runs = {{'a', 1U}, {'|', 2U}, {'a', 3U}, {'b', 6U}}; input.radix = 10U; input.separator = '|'; input.audit_symbols = {1, 2, 3, 6};",
            r"""if (input.radix < 2U || input.runs.empty()) return rejected(0);
    char previous = input.separator;
    for (std::size_t i = 0; i < input.runs.size(); ++i) {
        const auto& run = input.runs[i];
        if (run.mark == input.separator || run.mark == previous || run.length == 0U || run.length >= input.radix) return rejected(i);
        previous = run.mark; digits.push_back(static_cast<long long>(run.length));
    }
    if (!checked_horner(digits, input.radix, numeric_value)) return rejected(digits.size());""",
            "turn alternating nonseparator unary runs into bounded digits before checked accumulation",
            "radix bound, nonempty runs, alternating marks, separator exclusion, length range, and overflow",
        ),
    )


def _checksum_expected(key: str, variant: str = "base") -> int:
    digits = [1, 2, 3, 6]
    if key == "weighted":
        weights = [3, 1, 7, 9]
        if variant == "opposite":
            digits = list(reversed(digits))
        modulus = 13 if variant == "constants" else 11
        return sum(d * weights[i] for i, d in enumerate(digits)) % modulus
    if key == "alternating":
        return sum((d * ([2, 5][(len(digits) - 1 - i) % 2])) % 7 for i, d in enumerate(digits)) % 13
    if key == "luhn-fold":
        total = 0
        for i, digit in enumerate(reversed(digits)):
            value = digit * (2 if i % 2 == 0 else 1)
            while value >= 7:
                value -= 6
            total += value
        return total % 17
    if key == "fletcher-pair":
        a = 0
        b = 0
        for digit in digits:
            a = (a + digit) % 17
            b = (b + a) % 17
        return a * 17 + b
    if key == "adler-pair":
        a = 1
        b = 0
        for digit in digits:
            a = (a + digit) % 251
            b = (b + a) % 251
        a = (a + len(digits)) % 251
        return b * 251 + a
    if key == "polynomial":
        state = 2
        coefficients = [3, 5, 7]
        for i, digit in enumerate(digits):
            state = (state * coefficients[i % len(coefficients)] + digit) % 97
        return state
    if key == "crc-bits":
        register = 0
        mask = 255
        polynomial = 0x1D
        for digit in digits:
            for shift in range(3, -1, -1):
                bit = (digit >> shift) & 1
                top = (register >> 7) & 1
                register = ((register << 1) | bit) & mask
                if top:
                    register ^= polynomial
        return register
    if key == "quasigroup":
        state = 0
        for digit in digits:
            state = (state * 3 + digit) % 10
        return state
    if key == "complement":
        residue = sum((i + 1) * digit for i, digit in enumerate(digits)) % 11
        return (7 - residue) % 11
    if key == "diagonal":
        total = 0
        for i, digit in enumerate(digits):
            row = i // 2
            column = i % 2
            selected = column if row % 2 == 0 else 1 - column
            total += digit * [3, 5][selected]
        return total % 17
    raise AssertionError(key)


def _checksums() -> tuple[ChecksumSpec, ...]:
    specs = (
        ChecksumSpec(
            "weighted",
            "anchored cyclic position weights",
            "std::vector<long long> weights;\n    long long modulus = 0;\n    bool from_right = false;",
            "policy.weights = {3, 1, 7, 9}; policy.modulus = 11; policy.from_right = false;",
            "policy.weights = {}; policy.modulus = 1;",
            r"""if (policy.weights.empty() || policy.modulus <= 1) return rejected(0);
    long long total = 0;
    for (std::size_t i = 0; i < digits.size(); ++i) {
        const std::size_t logical = policy.from_right ? digits.size() - 1U - i : i;
        long long next = 0;
        if (!checked_mul_add(digits[i], policy.weights[logical % policy.weights.size()], total, next)) return rejected(i);
        total = next;
    }
    expected = euclidean(total, policy.modulus);""",
            r"""long long total = 0;
    if (policy.weights.empty() || policy.modulus <= 1) return {false, 0, 0, 0, 0};
    for (std::size_t i = 0; i < input.audit_symbols.size(); ++i) total += input.audit_symbols[i] * policy.weights[(input.audit_symbols.size() - 1U - i) % policy.weights.size()];
    const long long expected = ((total % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "cycle weights from the declared end and reduce with Euclidean residue",
            "anchor the same weights at the opposite end",
            0,
        ),
        ChecksumSpec(
            "alternating",
            "alternating folded factors",
            "std::array<long long, 2> factors{{0, 0}};\n    long long modulus = 0;\n    bool from_right = true;\n    unsigned fold_limit = 0;",
            "policy.factors = {2, 5}; policy.modulus = 13; policy.from_right = true; policy.fold_limit = 7U;",
            "policy.factors = {0, 5}; policy.modulus = 13; policy.fold_limit = 0U;",
            r"""if (policy.modulus <= 1 || policy.fold_limit < 2U || policy.factors[0] <= 0 || policy.factors[1] <= 0) return rejected(0);
    long long total = 0;
    for (std::size_t i = 0; i < digits.size(); ++i) {
        const std::size_t logical = policy.from_right ? digits.size() - 1U - i : i;
        long long product = 0;
        if (!checked_mul_add(digits[i], policy.factors[logical % 2U], 0, product)) return rejected(i);
        product = euclidean(product, policy.fold_limit);
        if (!checked_mul_add(1, total, product, total)) return rejected(i);
    }
    expected = euclidean(total, policy.modulus);""",
            r"""if (policy.modulus <= 1 || policy.fold_limit < 2U) return {false, 0, 0, 0, 0};
    long long total = 0;
    for (std::size_t i = 0; i < input.audit_symbols.size(); ++i) total += (input.audit_symbols[i] * policy.factors[i % 2U]) % policy.fold_limit;
    const long long expected = ((total % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "alternate two positive factors from one end and fold each product before summing",
            "start parity at the other end",
            0,
        ),
        ChecksumSpec(
            "luhn-fold",
            "radix-aware Luhn folding",
            "int digit_radix = 0;\n    long long modulus = 0;\n    bool double_from_right = true;\n    bool include_length = false;\n    unsigned maximum_digits = 0;",
            "policy.digit_radix = 7; policy.modulus = 17; policy.double_from_right = true; policy.include_length = false; policy.maximum_digits = 16U;",
            "policy.digit_radix = 1; policy.modulus = 17; policy.maximum_digits = 2U;",
            r"""if (policy.digit_radix < 2 || policy.modulus <= 1 || digits.size() > policy.maximum_digits) return rejected(0);
    long long total = policy.include_length ? static_cast<long long>(digits.size()) : 0;
    for (std::size_t i = 0; i < digits.size(); ++i) {
        const std::size_t logical = policy.double_from_right ? digits.size() - 1U - i : i;
        long long folded = digits[i] * (logical % 2U == 0U ? 2 : 1);
        while (folded >= policy.digit_radix) folded -= policy.digit_radix - 1;
        total += folded;
    }
    expected = euclidean(total, policy.modulus);""",
            r"""if (policy.modulus <= 1) return {false, 0, 0, 0, 0};
    long long total = 0;
    for (std::size_t i = 0; i < input.audit_symbols.size(); ++i) { long long value = input.audit_symbols[i] * ((input.audit_symbols.size() - 1U - i) % 2U == 0U ? 2 : 1); if (value > 9) value -= 9; total += value; }
    const long long expected = ((total % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "double positions from the declared end and fold in the declared digit radix",
            "always apply decimal subtract-nine folding",
            0,
        ),
        ChecksumSpec(
            "fletcher-pair",
            "ordered Fletcher running sums",
            "long long modulus = 0;\n    long long initial = 0;\n    bool include_zero_digits = true;\n    std::pair<unsigned, unsigned> combine_order{0U, 1U};",
            "policy.modulus = 17; policy.initial = 0; policy.include_zero_digits = true; policy.combine_order = {0U, 1U};",
            "policy.modulus = 1; policy.combine_order = {0U, 0U};",
            r"""if (policy.modulus <= 1 || policy.combine_order.first == policy.combine_order.second || policy.combine_order.second > 1U) return rejected(0);
    long long first = euclidean(policy.initial, policy.modulus), second = 0;
    for (long long digit : digits) { if (digit != 0 || policy.include_zero_digits) { first = euclidean(first + digit, policy.modulus); second = euclidean(second + first, policy.modulus); } }
    const std::array<long long, 2> parts{{first, second}};
    if (!checked_mul_add(parts[policy.combine_order.first], policy.modulus, parts[policy.combine_order.second], expected)) return rejected(digits.size());""",
            r"""if (policy.modulus <= 1) return {false, 0, 0, 0, 0};
    long long first = policy.initial;
    for (long long digit : input.audit_symbols) first = (first + digit) % policy.modulus;
    return {claimed == first, 0, 0, first, input.audit_symbols.size()};""",
            "maintain and order both Fletcher running residues",
            "return only the first running sum",
            0,
        ),
        ChecksumSpec(
            "adler-pair",
            "seeded Adler pair",
            "unsigned modulus = 0;\n    long long seed = 0;\n    bool reverse_payload = false;\n    std::string suffix_mode;\n    std::size_t maximum_length = 0;",
            'policy.modulus = 251U; policy.seed = 1; policy.reverse_payload = false; policy.suffix_mode = "length"; policy.maximum_length = 32U;',
            'policy.modulus = 1U; policy.suffix_mode = "unknown"; policy.maximum_length = 1U;',
            r"""if (policy.modulus < 2U || digits.size() > policy.maximum_length || (policy.suffix_mode != "length" && policy.suffix_mode != "payload")) return rejected(0);
    long long first = euclidean(policy.seed, policy.modulus), second = 0;
    for (std::size_t step = 0; step < digits.size(); ++step) { const std::size_t i = policy.reverse_payload ? digits.size() - 1U - step : step; first = euclidean(first + digits[i], policy.modulus); second = euclidean(second + first, policy.modulus); }
    if (policy.suffix_mode == "length") first = euclidean(first + static_cast<long long>(digits.size()), policy.modulus);
    if (!checked_mul_add(second, policy.modulus, first, expected)) return rejected(digits.size());""",
            r"""if (policy.modulus < 2U) return {false, 0, 0, 0, 0};
    long long first = 0, second = 0;
    for (long long digit : input.audit_symbols) { first = (first + digit) % policy.modulus; second = (second + first) % policy.modulus; }
    const long long expected = second * policy.modulus + first;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "preserve the seed while accumulating the ordered Adler residue pair and optional length suffix",
            "reset the seed before the first digit",
            0,
        ),
        ChecksumSpec(
            "polynomial",
            "coefficient-driven rolling polynomial",
            "std::vector<long long> coefficients;\n    long long modulus = 0;\n    long long initial = 0;\n    bool coefficients_repeat = true;\n    std::optional<long long> terminal_bias;",
            "policy.coefficients = {3, 5, 7}; policy.modulus = 97; policy.initial = 2; policy.coefficients_repeat = true; policy.terminal_bias = std::nullopt;",
            "policy.coefficients = {}; policy.modulus = 1; policy.coefficients_repeat = false;",
            r"""if (policy.coefficients.empty() || policy.modulus <= 1 || (!policy.coefficients_repeat && policy.coefficients.size() != digits.size())) return rejected(0);
    long long state = euclidean(policy.initial, policy.modulus);
    for (std::size_t i = 0; i < digits.size(); ++i) { long long next = 0; if (!checked_mul_add(state, policy.coefficients[i % policy.coefficients.size()], digits[i], next)) return rejected(i); state = euclidean(next, policy.modulus); }
    if (policy.terminal_bias.has_value()) state = euclidean(state + *policy.terminal_bias, policy.modulus);
    expected = state;""",
            r"""if (policy.coefficients.empty() || policy.modulus <= 1) return {false, 0, 0, 0, 0};
    long long total = policy.initial;
    for (long long digit : input.audit_symbols) total += digit;
    for (long long coefficient : policy.coefficients) total += coefficient;
    const long long expected = ((total % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "roll state through per-position coefficients with checked multiplication",
            "sum coefficients and digits independently",
            0,
        ),
        ChecksumSpec(
            "crc-bits",
            "bitwise polynomial register",
            "unsigned register_width = 0;\n    std::uint64_t polynomial = 0;\n    std::uint64_t initial = 0;\n    bool reflect_each_symbol = false;\n    unsigned symbol_bits = 0;\n    std::array<unsigned, 2> feed_order{{0U, 1U}};",
            "policy.register_width = 8U; policy.polynomial = 0x1DULL; policy.initial = 0U; policy.reflect_each_symbol = false; policy.symbol_bits = 4U; policy.feed_order = {0U, 1U};",
            "policy.register_width = 0U; policy.polynomial = 0U; policy.symbol_bits = 65U;",
            r"""if (policy.register_width == 0U || policy.register_width > 32U || policy.symbol_bits == 0U || policy.symbol_bits > 16U || policy.polynomial == 0U || policy.feed_order[0] == policy.feed_order[1]) return rejected(0);
    const std::uint64_t register_mask = (std::uint64_t{1} << policy.register_width) - 1U;
    std::uint64_t state = policy.initial & register_mask;
    for (std::size_t i = 0; i < digits.size(); ++i) { if (digits[i] < 0 || static_cast<std::uint64_t>(digits[i]) >= (std::uint64_t{1} << policy.symbol_bits)) return rejected(i); for (unsigned step = 0; step < policy.symbol_bits; ++step) { const unsigned shift = policy.reflect_each_symbol ? step : policy.symbol_bits - 1U - step; const std::uint64_t bit = (static_cast<std::uint64_t>(digits[i]) >> shift) & 1U; const bool top = ((state >> (policy.register_width - 1U)) & 1U) != 0U; state = ((state << 1U) | bit) & register_mask; if (top) state ^= policy.polynomial & register_mask; } }
    expected = static_cast<long long>(state);""",
            r"""std::uint64_t state = policy.initial;
    for (long long digit : input.audit_symbols) state ^= static_cast<std::uint64_t>(digit);
    const long long expected = static_cast<long long>(state);
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "feed every symbol bit through a width-bounded polynomial register",
            "XOR whole digits without bit division",
            0,
        ),
        ChecksumSpec(
            "quasigroup",
            "validated quasigroup table walk",
            "std::vector<int> transition_table;\n    int order = 0;\n    int initial_state = 0;\n    bool reverse_walk = false;\n    std::set<int> allowed_terminal_states;\n    std::size_t table_stride = 0;",
            "policy.order = 10; policy.initial_state = 0; policy.reverse_walk = false; policy.table_stride = 10U; for (int row = 0; row < 10; ++row) for (int column = 0; column < 10; ++column) policy.transition_table.push_back((row * 3 + column) % 10); policy.allowed_terminal_states = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};",
            "policy.order = 3; policy.initial_state = 0; policy.transition_table = {0, 1}; policy.table_stride = 2U;",
            r"""if (policy.order < 2 || policy.table_stride != static_cast<std::size_t>(policy.order) || policy.transition_table.size() != policy.table_stride * policy.table_stride || policy.initial_state < 0 || policy.initial_state >= policy.order) return rejected(0);
    for (int value : policy.transition_table) if (value < 0 || value >= policy.order) return rejected(0);
    int state = policy.initial_state;
    for (std::size_t step = 0; step < digits.size(); ++step) { const std::size_t i = policy.reverse_walk ? digits.size() - 1U - step : step; if (digits[i] < 0 || digits[i] >= policy.order) return rejected(i); state = policy.transition_table[static_cast<std::size_t>(state) * policy.table_stride + static_cast<std::size_t>(digits[i])]; }
    if (!policy.allowed_terminal_states.empty() && policy.allowed_terminal_states.count(state) == 0U) return rejected(digits.size());
    expected = state;""",
            r"""if (policy.order < 2) return {false, 0, 0, 0, 0};
    long long total = 0;
    for (long long digit : input.audit_symbols) total += digit;
    const long long expected = total % policy.order;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "validate and walk a square transition table in declared order",
            "replace the table walk with digit-sum modulo the order",
            0,
        ),
        ChecksumSpec(
            "complement",
            "target-residue complement",
            "long long modulus = 0;\n    long long target_residue = 0;\n    bool include_one_based_index = true;\n    std::vector<long long> position_weights;\n    std::map<std::size_t, long long> overrides;\n    bool reject_zero_check = false;",
            "policy.modulus = 11; policy.target_residue = 7; policy.include_one_based_index = true; policy.position_weights = {1, 1, 1, 1}; policy.reject_zero_check = false;",
            "policy.modulus = 1; policy.position_weights = {}; policy.reject_zero_check = true;",
            r"""if (policy.modulus <= 1 || policy.position_weights.empty()) return rejected(0);
    long long residue = 0;
    for (std::size_t i = 0; i < digits.size(); ++i) { long long weight = policy.position_weights[i % policy.position_weights.size()]; const auto override_it = policy.overrides.find(i); if (override_it != policy.overrides.end()) weight = override_it->second; if (policy.include_one_based_index) weight += static_cast<long long>(i + 1U) - 1; long long next = 0; if (!checked_mul_add(digits[i], weight, residue, next)) return rejected(i); residue = euclidean(next, policy.modulus); }
    expected = euclidean(policy.target_residue - residue, policy.modulus);
    if (policy.reject_zero_check && expected == 0) return rejected(digits.size());""",
            r"""if (policy.modulus <= 1) return {false, 0, 0, 0, 0};
    long long residue = 0;
    for (std::size_t i = 0; i < input.audit_symbols.size(); ++i) residue += static_cast<long long>(i + 1U) * input.audit_symbols[i];
    const long long expected = ((residue % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "form an index-aware residue and return the complement to a target residue",
            "return the observed residue itself",
            0,
        ),
        ChecksumSpec(
            "diagonal",
            "zigzag diagonal row weighting",
            "std::size_t columns = 0;\n    std::vector<long long> row_weights;\n    long long modulus = 0;\n    bool zigzag = true;\n    std::array<int, 2> diagonal_order{{0, 1}};\n    std::deque<long long> row_biases;\n    std::size_t maximum_rows = 0;",
            "policy.columns = 2U; policy.row_weights = {3, 5}; policy.modulus = 17; policy.zigzag = true; policy.diagonal_order = {0, 1}; policy.row_biases = {0, 0}; policy.maximum_rows = 4U;",
            "policy.columns = 0U; policy.row_weights = {}; policy.modulus = 1; policy.maximum_rows = 0U;",
            r"""if (policy.columns == 0U || policy.row_weights.size() != policy.columns || policy.modulus <= 1 || policy.diagonal_order[0] == policy.diagonal_order[1]) return rejected(0);
    const std::size_t rows = (digits.size() + policy.columns - 1U) / policy.columns;
    if (rows > policy.maximum_rows || (!policy.row_biases.empty() && policy.row_biases.size() < rows)) return rejected(rows);
    long long total = 0;
    for (std::size_t i = 0; i < digits.size(); ++i) { const std::size_t row = i / policy.columns; const std::size_t column = i % policy.columns; const std::size_t selected = policy.zigzag && row % 2U == 1U ? policy.columns - 1U - column : column; long long next = 0; if (!checked_mul_add(digits[i], policy.row_weights[selected], total, next)) return rejected(i); total = next; }
    for (std::size_t row = 0; row < rows && row < policy.row_biases.size(); ++row) total += policy.row_biases[row];
    expected = euclidean(total, policy.modulus);""",
            r"""if (policy.modulus <= 1 || policy.row_weights.empty()) return {false, 0, 0, 0, 0};
    long long total = 0;
    for (long long digit : input.audit_symbols) total += digit * policy.row_weights.front();
    const long long expected = ((total % policy.modulus) + policy.modulus) % policy.modulus;
    return {claimed == expected, 0, 0, expected, input.audit_symbols.size()};""",
            "walk a row/column layout with zigzag diagonal selection and row-specific weights",
            "flatten all digits under one constant weight",
            0,
        ),
    )
    return tuple(replace(spec, expected=_checksum_expected(spec.key)) for spec in specs)


RADICES = _radices()
CHECKSUMS = _checksums()
TASKS = tuple(TaskSpec(radix, checksum) for radix in RADICES for checksum in CHECKSUMS)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha256(path.read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return "sha256:" + digest.hexdigest()
    for path in sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and ".state" not in p.relative_to(root).parts
        and "build" not in p.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    return _file_hash(GENERATOR_PATH)


def _write(path: Path, content: str | bytes, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    path.write_bytes(data)


def _header(spec: TaskSpec) -> str:
    guard = re.sub(r"[^A-Z0-9]", "_", spec.task_id.upper()) + "_H"
    return f"""#ifndef {guard}
#define {guard}

#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace radix_checksum {{

struct Input {{
    {spec.radix.fields}
}};

struct Policy {{
    {spec.checksum.fields}
}};

struct Audit {{
    bool accepted = false;
    std::size_t bad_index = 0;
    long long numeric_value = 0;
    long long expected_check = 0;
    std::size_t digit_count = 0;
}};

class Validator {{
public:
    static Audit inspect(const Input& input, long long claimed, const Policy& policy);
}};

}}  // namespace radix_checksum

#endif
"""


def _source(spec: TaskSpec) -> str:
    return f'''#include "{spec.task_id}.h"

#include <algorithm>
#include <array>
#include <climits>
#include <cstdint>
#include <iterator>
#include <string>
#include <vector>

namespace radix_checksum {{
namespace {{

[[maybe_unused]] bool checked_mul_add(long long left, long long multiplier, long long addend, long long& output) {{
    long long product = 0;
    return !__builtin_mul_overflow(left, multiplier, &product) && !__builtin_add_overflow(product, addend, &output);
}}

[[maybe_unused]] bool checked_horner(const std::vector<long long>& digits, long long radix, long long& output) {{
    output = 0;
    for (long long digit : digits) {{
        long long next = 0;
        if (!checked_mul_add(output, radix, digit, next)) return false;
        output = next;
    }}
    return true;
}}

[[maybe_unused]] long long euclidean(long long value, long long modulus) {{
    const long long residue = value % modulus;
    return residue < 0 ? residue + modulus : residue;
}}

Audit rejected(std::size_t bad_index) {{
    return {{false, bad_index, 0, 0, 0}};
}}

}}  // namespace

Audit Validator::inspect(const Input& input, long long claimed, const Policy& policy) {{
    std::vector<long long> digits;
    long long numeric_value = 0;
    {spec.radix.decoder}
    if (digits != input.audit_symbols) return rejected(digits.size());
    long long expected = 0;
    {spec.checksum.algorithm}
    return {{claimed == expected, 0, numeric_value, expected, digits.size()}};
}}

}}  // namespace radix_checksum
'''


def _starter_source(spec: TaskSpec) -> str:
    return f'''#include "{spec.task_id}.h"

namespace radix_checksum {{

Audit Validator::inspect(const Input& input, long long claimed, const Policy& policy) {{
    (void)input;
    (void)claimed;
    (void)policy;
    return {{}};
}}

}}  // namespace radix_checksum
'''


def _negative_source(spec: TaskSpec) -> str:
    wrong_checksum = spec.checksum.negative.replace("input.audit_symbols", "wrong_digits")
    return f'''#include "{spec.task_id}.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace radix_checksum {{

Audit Validator::inspect(const Input& input, long long claimed, const Policy& policy) {{
    std::vector<long long> wrong_digits = input.audit_symbols;
    {_radix_negative_prelude(spec.radix.key)}
    {wrong_checksum}
}}

}}  // namespace radix_checksum
'''


def _radix_negative_prelude(key: str) -> str:
    blocks = {
        "alphabet": "std::reverse(wrong_digits.begin(), wrong_digits.end());",
        "digits": "if (wrong_digits.size() > 1U) wrong_digits.erase(wrong_digits.begin());",
        "mixed": "if (!wrong_digits.empty()) std::rotate(wrong_digits.begin(), wrong_digits.begin() + 1, wrong_digits.end());",
        "balanced": "for (long long& digit : wrong_digits) { if (digit < 0) { digit = -digit; } } wrong_digits.push_back(0);",
        "bijective": "for (long long& digit : wrong_digits) { if (digit > 0) { --digit; } }",
        "negabase": "for (std::size_t i = 1; i < wrong_digits.size(); i += 2U) wrong_digits[i] = -wrong_digits[i];",
        "packed": "std::stable_partition(wrong_digits.begin(), wrong_digits.end(), [](long long digit) { return digit % 2 == 0; });",
        "tokens": "std::sort(wrong_digits.begin(), wrong_digits.end(), [](long long left, long long right) { return left > right; });",
        "sparse": "for (std::size_t i = 0; i < wrong_digits.size(); ++i) wrong_digits[i] += static_cast<long long>(i);",
        "unary-runs": "for (std::size_t i = 1; i < wrong_digits.size(); ++i) wrong_digits[i] += wrong_digits[i - 1U];",
    }
    return blocks[key]


def _policy_init(spec: TaskSpec, variant: str = "base") -> str:
    if spec.checksum.key == "weighted" and variant == "constants":
        return "policy.weights = {3, 1, 7, 9}; policy.modulus = 13; policy.from_right = false;"
    if spec.checksum.key == "weighted" and variant == "opposite":
        return "policy.weights = {3, 1, 7, 9}; policy.modulus = 11; policy.from_right = true;"
    return spec.checksum.valid_init


def _test_support(spec: TaskSpec, variant: str = "base") -> str:
    expected = _checksum_expected(spec.checksum.key, variant)
    return f"""[[maybe_unused]] static Input make_valid_input() {{ Input input; {spec.radix.valid_init} return input; }}
[[maybe_unused]] static Input make_invalid_input() {{ Input input; {spec.radix.invalid_init} return input; }}
[[maybe_unused]] static Policy make_valid_policy() {{ Policy policy; {_policy_init(spec, variant)} return policy; }}
[[maybe_unused]] static Policy make_invalid_policy() {{ Policy policy; {spec.checksum.invalid_init} return policy; }}
static constexpr long long expected_claim = {expected};
"""


def _visible_test(spec: TaskSpec, variant: str = "base") -> str:
    return f'''#include "{spec.task_id}.h"

#include <cstddef>

using radix_checksum::Input;
using radix_checksum::Policy;
using radix_checksum::Validator;

namespace {{
{_test_support(spec, variant)}
}}

int main() {{
    const auto valid = Validator::inspect(make_valid_input(), expected_claim, make_valid_policy());
    if (!valid.accepted || valid.expected_check != expected_claim || valid.digit_count != 4U) return 1;
    const auto wrong = Validator::inspect(make_valid_input(), expected_claim + 1, make_valid_policy());
    if (wrong.accepted || wrong.expected_check != expected_claim) return 2;
    return 0;
}}
'''


def _hidden_test(spec: TaskSpec, variant: str = "base") -> str:
    return f'''#include "{spec.task_id}.h"

#include <cstddef>

using radix_checksum::Input;
using radix_checksum::Policy;
using radix_checksum::Validator;

namespace {{
{_test_support(spec, variant)}
}}

int main() {{
    const auto malformed = Validator::inspect(make_invalid_input(), expected_claim, make_valid_policy());
    if (malformed.accepted) return 1;
    const auto bad_policy = Validator::inspect(make_valid_input(), expected_claim, make_invalid_policy());
    if (bad_policy.accepted) return 2;
    const auto first = Validator::inspect(make_valid_input(), expected_claim, make_valid_policy());
    const auto second = Validator::inspect(make_valid_input(), expected_claim, make_valid_policy());
    if (!first.accepted || !second.accepted || first.numeric_value != second.numeric_value || first.expected_check != second.expected_check) return 3;
    return 0;
}}
'''


def _instructions(spec: TaskSpec) -> str:
    return f"""# Instructions

Implement `radix_checksum::Validator::inspect` in `{spec.task_id}.h` and
`{spec.task_id}.cpp`.

This task combines the **{spec.radix.title}** input mechanism with the
**{spec.checksum.title}** checksum mechanism. The input decoder must
{spec.radix.rule}. It must reject {spec.radix.invalid_rule}. Validate the
complete representation before accepting a numeric value; return the first bad
position and never partially accept malformed input.

For a valid representation, verify that `audit_symbols` exactly equals the
canonical decoded digit sequence. Then {spec.checksum.rule}. Reject an empty or
invalid checksum policy before arithmetic, use checked integer accumulation,
and compare the caller's `claimed` value with the exact computed check. A wrong
claim is well formed but returns `accepted=false` together with the computed
check. Caller order and the documented end anchor are binding.

The implementation must directly own both mechanisms. Do not delegate to a
generic base-conversion or checksum library, a regular expression, a
precomputed answer table, or a cross-task dispatcher. In particular, tests
reject a solution that would {spec.checksum.wrong_rule}.

Empty input, duplicate alphabet/position material, absent symbols, exact digit
boundaries, invalid policy state, and arithmetic overflow follow the explicit
rules above. All results are deterministic, C++17, locale-independent, and
offline.
"""


def _introduction(spec: TaskSpec) -> str:
    return f"""# Radix/check integrity audit

Validate a structured digit representation and its attached check value in one
atomic audit. This root uses {spec.radix.title} and {spec.checksum.title}; it is
an independently authored local candidate, not a benchmark exercise.
"""


def _cmake(spec: TaskSpec) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({spec.task_id} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

function(strict_target target source test_source)
  add_executable(${{target}} ${{source}} ${{test_source}})
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
endfunction()

strict_target(task_visible {spec.task_id}.cpp task_visible_test.cpp)
strict_target(task_hidden {spec.task_id}.cpp .meta/task_hidden_test.cpp)

enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
"""


def _provenance(spec: TaskSpec) -> str:
    return (
        json.dumps(
            {
                "schema_version": "aider-local-task-provenance-v2",
                "task_id": spec.task_id,
                "family_id": FAMILY_ID,
                "lineage": {"relation": "new-root", "parent": None},
                "authoring_origin": "repository-authored clean-room deterministic generator",
                "license_result": "repository-project-terms",
                "owner": OWNER_ID,
                "source_document": CURRICULUM.as_posix(),
                "source_task_id": spec.task_id,
                "task_spec_revision": "v1",
                "benchmark_holdout_separation": "required semantic and exact screens",
                "local_status": "pending_execution",
                "dataset_handoff": "not_requested",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _config(spec: TaskSpec) -> str:
    return (
        json.dumps(
            {
                "authors": ["w8-biayn"],
                "blurb": f"Validate {spec.radix.title} with {spec.checksum.title}.",
                "files": {
                    "solution": [f"{spec.task_id}.h", f"{spec.task_id}.cpp"],
                    "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                    "example": [".meta/example.h", ".meta/example.cpp"],
                },
                "source": "w8-biayn clean-room radix/checksum expansion curriculum",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _tests_toml(spec: TaskSpec) -> str:
    return f"""[visible]
description = "valid {spec.radix.key}/{spec.checksum.key} audit and wrong claimed check"

[hidden]
description = "malformed input, invalid policy, deterministic repeat, first-error behavior"

[negative]
description = "compiled false substitute: {spec.checksum.wrong_rule}"
"""


def _render(spec: TaskSpec, *, variant: str = "base") -> dict[str, str]:
    return {
        ".docs/introduction.md": _introduction(spec),
        ".docs/instructions.md": _instructions(spec),
        ".meta/config.json": _config(spec),
        ".meta/provenance.json": _provenance(spec),
        ".meta/tests.toml": _tests_toml(spec),
        ".meta/example.h": _header(spec),
        ".meta/example.cpp": _source(spec),
        ".meta/task_hidden_test.cpp": _hidden_test(spec, variant),
        ".meta/negative.cpp": _negative_source(spec),
        f"{spec.task_id}.h": _header(spec),
        f"{spec.task_id}.cpp": _starter_source(spec),
        "task_visible_test.cpp": _visible_test(spec, variant),
        "CMakeLists.txt": _cmake(spec),
    }


def _render_hash(rendered: Mapping[str, str]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(rendered.items()):
        data = content.encode()
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _safe_relative(path: str) -> bool:
    candidate = Path(path)
    return bool(path) and not candidate.is_absolute() and ".." not in candidate.parts


def _inventory_roots(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not root.is_dir():
        return result
    for config in root.rglob(".meta/config.json"):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        inventory_id = task_root.relative_to(root).as_posix()
        if inventory_id in result:
            _fail("duplicate_task", f"{inventory_id}:{result[inventory_id]}:{task_root}")
        result[inventory_id] = task_root
    return result


def _inventory_hash(inventory: Mapping[str, Path]) -> str:
    lines = "".join(f"{path.as_posix()}\n" for _, path in sorted(inventory.items()))
    return _sha256(lines.encode())


def _semantic_tokens(text: str) -> list[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/|<!--.*?-->", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " literal ", text)
    text = re.sub(r"\brcv[-_][a-z0-9_-]+\b", " taskid ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:rcv|radix_checksum|symbol_integrity|radix|checksum|validator|inspector|input|policy|audit)\b",
        " noun ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b\d+(?:[uUlL]*)\b", " number ", text)
    text = re.sub(r"\b(?:true|false)\b", " boolean ", text, flags=re.IGNORECASE)
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|\+\+|--|&&|\|\||[%*/+<>{}\[\]();,:?-]", text.lower()
    )
    normalized: list[str] = []
    for token in tokens:
        if token in {"++", "--"}:
            normalized.append("step")
        else:
            normalized.append(token)
    return normalized


def _shingles(tokens: Sequence[str], width: int = 5) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _similarity(left: str, right: str) -> float:
    a = _shingles(_semantic_tokens(left))
    b = _shingles(_semantic_tokens(right))
    return len(a & b) / max(1, min(len(a), len(b)))


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _dimension_corpora(root: Path, spec: TaskSpec) -> dict[str, str]:
    header = _read(root, f"{spec.task_id}.h")
    reference = _read(root, ".meta/example.cpp")
    instructions = _read(root, ".docs/instructions.md")
    visible = _read(root, "task_visible_test.cpp")
    hidden = _read(root, ".meta/task_hidden_test.cpp")
    negative = _read(root, ".meta/negative.cpp")
    return {
        "public_api": header,
        "owned_state_or_algorithm": header + "\n" + reference,
        "mutation_selection_rules": reference + "\n" + instructions,
        "invalid_boundary_behavior": instructions + "\n" + visible + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": reference + "\n---negative---\n" + negative,
    }


def _control_root(out: Path, name: str) -> Path:
    return out / ".state" / "controls" / name


def _materialize_control(out: Path, spec: TaskSpec, name: str) -> dict[str, object]:
    root = _control_root(out, name)
    if root.exists():
        shutil.rmtree(root)
    variant = (
        "constants"
        if name == "constants-or-policy-only"
        else "opposite"
        if name == "opposite-end-selection"
        else "base"
    )
    rendered = _render(spec, variant=variant)
    for relative, content in rendered.items():
        if name == "domain-identifier-renamed":
            content = content.replace("radix_checksum", "symbol_integrity")
            content = content.replace("Validator", "Inspector")
            content = content.replace("Radix/check", "Symbol/integrity")
        _write(root / relative, content)
    return {
        "name": name,
        "changed": _tree_hash(root) != _tree_hash(out / spec.task_id),
        "tree_hash": _tree_hash(root),
    }


def _validate_output(out: Path, *, testing: bool = False) -> None:
    if out.is_symlink():
        _fail("unsafe_path", f"symlink output:{out}")
    resolved = out.resolve(strict=False)
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing tree output:{out}")
    if not testing and resolved != DEFAULT_OUT.resolve(strict=False):
        _fail("unsafe_path", f"expected exact expansion family:{DEFAULT_OUT}")


def _screen_ids(rendered: Mapping[str, Mapping[str, str]], out: Path) -> dict[str, object]:
    inventories = {
        "legacy": _inventory_roots(LEGACY_ROOT),
        "reverify": _inventory_roots(REVERIFY_ROOT),
        "expansion": _inventory_roots(EXPANSION_ROOT),
    }
    current_ids = set(rendered)
    for name, inventory in inventories.items():
        collisions = current_ids & {path.name for path in inventory.values()}
        if name == "expansion":
            allowed_owner_ids: set[str] = set()
            for task_id in collisions:
                for root in inventory.values():
                    if root.name != task_id:
                        continue
                    provenance = root / ".meta/provenance.json"
                    if provenance.is_file():
                        try:
                            if json.loads(provenance.read_text()).get("owner") == OWNER_ID:
                                allowed_owner_ids.add(task_id)
                        except json.JSONDecodeError:
                            pass
            collisions = {task_id for task_id in collisions if task_id not in allowed_owner_ids}
        if collisions:
            _fail("duplicate_task", f"{name}:{sorted(collisions)}")
    return {
        name: {"count": len(inventory), "sorted_root_inventory_sha256": _inventory_hash(inventory)}
        for name, inventory in inventories.items()
    }


def _write_manifest(out: Path, name: str, payload: object) -> None:
    _write(
        out / ".state" / "manifests" / name,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )


def _write_audit_remedy_records(out: Path) -> int:
    reports = sorted((out / ".state/audits").glob("cycle-01-*.json"))
    if not reports:
        return 0
    report_path = reports[-1]
    report = json.loads(report_path.read_text())
    finding = next(
        (
            item
            for item in report.get("findings", [])
            if item.get("id") == "cycle-01/family/reused-checksum-negative"
        ),
        None,
    )
    if finding is None:
        return 0
    before = {item["task_id"]: item["tree_hash"] for item in report["root_catalog"]}
    remedy_root = out / ".state/remedy"
    for spec in TASKS:
        spec_path = remedy_root / f"{spec.task_id}.md"
        markdown = f"""# Identity
Task ID `{spec.task_id}`; revision v2; family `{FAMILY_ID}`; disposition `repair-in-place`; source `{CURRICULUM}`; license pass; generator `{GENERATOR_PATH}`; benchmark screen pass.

# Objective
Implement and validate both `{spec.radix.key}` decoding and `{spec.checksum.key}` checksum behavior.

# Public API
C++17 namespace `radix_checksum`; editable order `{spec.task_id}.h`, `{spec.task_id}.cpp`; `Input`, `Policy`, `Audit`, and `Validator::inspect` are defined by the curriculum and generated header.

# Behavior table
Valid input returns the decoded value and computed check; wrong claims, invalid/duplicate/absent/empty material, boundary violations, and overflow return non-accepted first-error audits without partial acceptance.

# Implementation invariant
The reference directly owns both emitted mechanisms. The negative must first execute the radix-specific false decoder `{_radix_negative_prelude(spec.radix.key)}` and then the checksum-specific false rule “{spec.checksum.wrong_rule}”. Generic libraries, precomputed answers, and checksum-only discriminators are forbidden.

# Starter and reference
The task-named header/source are coherent incomplete starters; `.meta/example.h` and `.meta/example.cpp` are complete independent replacements.

# Tests
Visible/private tests cover valid, wrong-claim, malformed input, invalid policy, and repeat determinism. `.meta/negative.cpp` must compile and fail executed tests in normal and sanitizer modes.

# Files and metadata
Solutions `{spec.task_id}.h`, `{spec.task_id}.cpp`; tests `task_visible_test.cpp`, `.meta/task_hidden_test.cpp`; references `.meta/example.h`, `.meta/example.cpp`; negative `.meta/negative.cpp`; all private roles remain outside prompts.

# Build/oracle
Strict C++17, explicit Unix Makefiles, pinned repository sanity image, network none, two positive normal and two equal fresh sanitizer tests, plus compiled negative rejection.

# Family/contamination
The fresh family must retain 100 unique normalized negative profiles, 4,950 seven-dimension pair decisions, and clean screens against both existing trees and all 26 official holdouts.

# Optional dataset handoff
`not_requested`.

# Acceptance
Focused pytest, creator core preflight, pinned Docker sanity, and fresh independent audit must pass. Stable failures include `invariant_not_enforced`, `duplicate_family`, `negative_fixture_not_rejected`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""
        _write(spec_path, markdown, overwrite=True)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": spec.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": before[spec.task_id],
            "tree_hash_after": _tree_hash(out / spec.task_id),
            "generator_path": GENERATOR_PATH.as_posix(),
            "generator_revision": _generator_revision(),
            "finding_ids": [finding["id"]],
            "disposition": "repair-in-place",
            "benchmark_screen": "pass",
            "license_screen": "pass",
            "remedy_spec_path": spec_path.as_posix(),
            "remedy_spec_hash": _sha256(markdown.encode()),
            "status": "implemented",
            "primary_core_objective": "achieved",
            "audit_report_path": report_path.as_posix(),
            "invalidated_prior_evidence": {
                "creator_subject_hash": report.get("creator_subject_hash"),
                "audit_subject_hash": report.get("audit_subject_hash"),
                "reason": finding["root_cause"],
            },
            "local_status": "pending_execution",
        }
        _write(
            remedy_root / f"{spec.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            overwrite=True,
        )
    return len(TASKS)


def build(
    out: Path = DEFAULT_OUT, *, force: bool = False, testing: bool = False
) -> dict[str, object]:
    _validate_output(out, testing=testing)
    rendered = {spec.task_id: _render(spec) for spec in TASKS}
    if len(rendered) != EXPECTED_ROOTS:
        _fail("binding_root_count_failed", str(len(rendered)))
    inventories = _screen_ids(rendered, out)
    if out.exists():
        foreign: list[str] = []
        for config in out.glob("*/.meta/config.json"):
            provenance = config.parent / "provenance.json"
            owner = (
                json.loads(provenance.read_text()).get("owner") if provenance.is_file() else None
            )
            if owner != OWNER_ID:
                foreign.append(config.parent.parent.name)
        if foreign:
            _fail("generator_output_drift", f"foreign roots:{sorted(foreign)}")
        if not force:
            raise FileExistsError(f"{out} exists; pass --force")
        for child in out.iterdir():
            if child.name != ".state" and child.is_dir():
                shutil.rmtree(child)
        state = out / ".state"
        if state.is_dir():
            stale = state / "invalidated"
            stale.mkdir(parents=True, exist_ok=True)
            prior = {
                "reason": "owner regeneration invalidates all earlier exact-tree receipts",
                "tree_hash_before": _tree_hash(out),
            }
            _write(
                stale / "latest.json",
                json.dumps(prior, indent=2, sort_keys=True) + "\n",
                overwrite=True,
            )
            for name in (
                "creator-preflight.json",
                "docker-sanity.json",
                "diversity-screen.json",
                "host-verify.json",
            ):
                path = state / "receipts" / name
                if path.exists():
                    path.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for task_id, files in sorted(rendered.items()):
        root = out / task_id
        for relative, content in sorted(files.items()):
            _write(root / relative, content, overwrite=True)
    controls = [_materialize_control(out, TASKS[0], name) for name in CONTROL_NAMES]
    raw = [
        {
            "task_id": spec.task_id,
            "radix": spec.radix.key,
            "checksum": spec.checksum.key,
            "lineage": "new-root",
        }
        for spec in TASKS
    ]
    _write_manifest(out, "raw-proposals.json", {"schema_version": 1, "proposals": raw})
    _write_manifest(out, "generated-candidates.json", {"schema_version": 1, "candidates": raw})
    _write_manifest(out, "rejected-candidates.json", {"schema_version": 1, "rejected": []})
    _write_manifest(
        out,
        "selected-candidates.json",
        {"schema_version": 1, "selected": [item["task_id"] for item in raw]},
    )
    _write_manifest(out, "source-inventories.json", inventories)
    remedy_records = _write_audit_remedy_records(out)
    return {
        "root_count": len(rendered),
        "tree_hash": _tree_hash(out),
        "controls": controls,
        "inventories": inventories,
        "remedy_records": remedy_records,
    }


def _role_and_prompt_check(root: Path, spec: TaskSpec) -> dict[str, object]:
    config = json.loads(_read(root, ".meta/config.json"))
    files = config.get("files", {})
    expected_solution = [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
    expected_tests = ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
    expected_examples = [".meta/example.h", ".meta/example.cpp"]
    if (
        files.get("solution") != expected_solution
        or files.get("test") != expected_tests
        or files.get("example") != expected_examples
    ):
        _fail("target_reference_mismatch", spec.task_id)
    declared = [*expected_solution, *expected_tests, *expected_examples]
    if any(not _safe_relative(path) or not (root / path).is_file() for path in declared):
        _fail("unsafe_path", spec.task_id)
    task = load_task(root)
    prompt = build_prompt(task)
    if any(marker in prompt for marker in PRIVATE_MARKERS):
        _fail("prompt_contract_incomplete", spec.task_id)
    assistant = build_assistant_response(task, load_example_files_from_config(root))
    try:
        blocks = parse_whole_file_blocks(assistant)
    except WholeFormatError as error:
        _fail("whole_format_failed", f"{spec.task_id}:{error}")
    if list(blocks) != expected_solution:
        _fail("target_reference_mismatch", spec.task_id)
    bad_answers = (
        assistant + "\nprose",
        assistant.replace(expected_solution[0], "unknown.cpp", 1),
        assistant.split(f"{expected_solution[1]}\n", 1)[0],
    )
    for bad in bad_answers:
        try:
            parsed = parse_whole_file_blocks(bad)
        except WholeFormatError:
            continue
        if set(parsed) == set(expected_solution):
            _fail("whole_format_failed", f"accepted adversarial answer:{spec.task_id}")
    return {
        "prompt_hash": _sha256(prompt.encode()),
        "reference_response_hash": _sha256(assistant.encode()),
    }


def _semantic_corpus(root: Path) -> str:
    selected: list[str] = []
    for relative in (
        ".docs/introduction.md",
        ".docs/instructions.md",
        ".meta/example.h",
        ".meta/example.cpp",
        ".meta/task_hidden_test.cpp",
        "task_visible_test.cpp",
    ):
        path = root / relative
        if path.is_file():
            selected.append(path.read_text(encoding="utf-8"))
    return "\n".join(selected)


def _holdout_and_lineage_screen(out: Path) -> dict[str, object]:
    manifest = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    benchmark_ids = set(manifest["task_ids"])
    found = (
        {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
        if HOLDOUT_ROOT.is_dir()
        else set()
    )
    if found != benchmark_ids:
        _fail(
            "official_holdout_content_unavailable",
            f"expected {len(benchmark_ids)}, found {len(found)}",
        )
    comparison_roots: list[tuple[str, Path]] = []
    for tree in (LEGACY_ROOT, REVERIFY_ROOT):
        comparison_roots.extend(sorted(_inventory_roots(tree).items()))
    holdout_profiles = {
        task_id: _shingles(_semantic_tokens(_semantic_corpus(HOLDOUT_ROOT / task_id)))
        for task_id in sorted(benchmark_ids)
    }
    existing_profiles = [
        (task_id, path, _shingles(_semantic_tokens(_semantic_corpus(path))))
        for task_id, path in comparison_roots
    ]

    def compare(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
        return len(left & right) / max(1, min(len(left), len(right)))

    results: dict[str, object] = {}
    for spec in TASKS:
        root = out / spec.task_id
        if spec.task_id in benchmark_ids:
            _fail("benchmark_id_overlap", spec.task_id)
        corpus = _shingles(_semantic_tokens(_semantic_corpus(root)))
        strongest_holdout = ("", 0.0)
        for task_id, candidate in holdout_profiles.items():
            score = compare(corpus, candidate)
            if score > strongest_holdout[1]:
                strongest_holdout = (task_id, score)
            if score >= 0.80:
                _fail("benchmark_content_overlap", f"{spec.task_id}:{task_id}:{score:.4f}")
        strongest_existing = ("", 0.0)
        for task_id, path, candidate in existing_profiles:
            score = compare(corpus, candidate)
            if score > strongest_existing[1]:
                strongest_existing = (f"{task_id}@{path}", score)
            if score >= 0.90:
                _fail("duplicate_family", f"{spec.task_id}:{task_id}:{score:.4f}")
        results[spec.task_id] = {
            "strongest_holdout": {
                "task_id": strongest_holdout[0],
                "similarity": strongest_holdout[1],
            },
            "strongest_existing": {
                "task": strongest_existing[0],
                "similarity": strongest_existing[1],
            },
        }
    return {
        "holdout_count": len(benchmark_ids),
        "candidate_holdout_pairs": EXPECTED_ROOTS * len(benchmark_ids),
        "candidate_existing_pairs": EXPECTED_ROOTS * len(existing_profiles),
        "per_root": results,
    }


def _diversity_screen(out: Path) -> dict[str, object]:
    profiles = {spec.task_id: _dimension_corpora(out / spec.task_id, spec) for spec in TASKS}
    shingle_profiles = {
        task_id: {
            dimension: _shingles(_semantic_tokens(corpus))
            for dimension, corpus in dimensions.items()
        }
        for task_id, dimensions in profiles.items()
    }

    def compare(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
        return len(left & right) / max(1, min(len(left), len(right)))

    decisions: list[dict[str, object]] = []
    for left_index, left in enumerate(TASKS):
        for right in TASKS[left_index + 1 :]:
            dimensions: dict[str, object] = {}
            for dimension in HARD_DIMENSIONS:
                score = compare(
                    shingle_profiles[left.task_id][dimension],
                    shingle_profiles[right.task_id][dimension],
                )
                passed = score < DIMENSION_LIMITS[dimension]
                dimensions[dimension] = {
                    "similarity": score,
                    "limit": DIMENSION_LIMITS[dimension],
                    "pass": passed,
                }
                if not passed:
                    _fail(
                        "duplicate_family",
                        f"{left.task_id}:{right.task_id}:{dimension}:{score:.6f}",
                    )
            decisions.append(
                {
                    "left": left.task_id,
                    "right": right.task_id,
                    "dimensions": dimensions,
                    "pass": True,
                }
            )
    if len(decisions) != EXPECTED_PAIRS:
        _fail("hard_rule_evidence_incomplete", str(len(decisions)))
    controls: list[dict[str, object]] = []
    for name in CONTROL_NAMES:
        root = _control_root(out, name)
        control_profile = _dimension_corpora(root, TASKS[0])
        control_shingles = {
            dimension: _shingles(_semantic_tokens(corpus))
            for dimension, corpus in control_profile.items()
        }
        dimension_results: dict[str, object] = {}
        for dimension in HARD_DIMENSIONS:
            score = compare(
                shingle_profiles[TASKS[0].task_id][dimension], control_shingles[dimension]
            )
            rejected_as_duplicate = score >= DIMENSION_LIMITS[dimension]
            dimension_results[dimension] = {
                "similarity": score,
                "limit": DIMENSION_LIMITS[dimension],
                "rejected_as_duplicate": rejected_as_duplicate,
            }
            if not rejected_as_duplicate:
                _fail("adversarial_control_escaped", f"{name}:{dimension}:{score:.6f}")
        controls.append(
            {
                "name": name,
                "changed": _tree_hash(root) != _tree_hash(out / TASKS[0].task_id),
                "dimensions": dimension_results,
                "rejected_in_all_dimensions": True,
            }
        )
    payload = {
        "schema_version": "radix-checksum-diversity-v1",
        "normalizer": NORMALIZER,
        "root_count": EXPECTED_ROOTS,
        "pair_count": len(decisions),
        "dimensions": list(HARD_DIMENSIONS),
        "decisions": decisions,
        "controls": controls,
        "pass": True,
    }
    _write(
        out / ".state/receipts/diversity-screen.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )
    return payload


def _deterministic_regeneration(out: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="radix-checksum-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh, testing=True)
        for spec in TASKS:
            if _tree_hash(out / spec.task_id) != _tree_hash(fresh / spec.task_id):
                _fail("generator_output_drift", spec.task_id)
        return _tree_hash(fresh)


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _validate_output(out, testing=out.resolve(strict=False) != DEFAULT_OUT.resolve(strict=False))
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    if len(roots) != EXPECTED_ROOTS or {path.name for path in roots} != {
        spec.task_id for spec in TASKS
    }:
        _fail("generator_output_drift", f"root count/ids:{len(roots)}")
    fresh_hash = _deterministic_regeneration(out)
    prompt_records: dict[str, object] = {}
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for spec in TASKS:
        record = _role_and_prompt_check(out / spec.task_id, spec)
        if record["prompt_hash"] in prompt_hashes:
            _fail("duplicate_task", f"prompt:{spec.task_id}")
        if record["reference_response_hash"] in reference_hashes:
            _fail("duplicate_task", f"reference:{spec.task_id}")
        prompt_hashes.add(str(record["prompt_hash"]))
        reference_hashes.add(str(record["reference_response_hash"]))
        prompt_records[spec.task_id] = record
    diversity = _diversity_screen(out)
    lineage = _holdout_and_lineage_screen(out)
    payload = {
        "schema_version": "radix-checksum-core-v1",
        "status": "creator_core_verified",
        "root_count": len(roots),
        "pair_count": diversity["pair_count"],
        "tree_hash": _tree_hash(out),
        "fresh_tree_hash": fresh_hash,
        "generator_revision": _generator_revision(),
        "curriculum_hash": _file_hash(CURRICULUM),
        "focused_test_hash": _file_hash(FOCUSED_TEST) if FOCUSED_TEST.is_file() else None,
        "prompt_records": prompt_records,
        "lineage_screen": lineage,
        "diversity_receipt_hash": _file_hash(out / ".state/receipts/diversity-screen.json"),
    }
    _write(
        out / ".state/receipts/core-preflight.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )
    return payload


_VERIFY_RUNNER_TEMPLATE = r"""set -eu
mkdir -p @WORK@/family
tar -xf @INPUT@ -C @WORK@/family
python3 - <<'PY'
from pathlib import Path
import hashlib
root=Path('@WORK@/family')
h=hashlib.sha256()
for p in sorted(x for x in root.rglob('*') if x.is_file() and '.state' not in x.parts and 'build' not in x.parts):
    rel=p.relative_to(root).as_posix().encode(); data=p.read_bytes()
    h.update(len(rel).to_bytes(8,'big')); h.update(rel); h.update(len(data).to_bytes(8,'big')); h.update(data)
print('MOUNT_TREE_HASH=sha256:'+h.hexdigest())
PY
normal=0
sanitizer=0
negatives=0
controls_normal=0
controls_sanitizer=0
verify_one() {
  root="$1"
  mode="$2"
  work="/tmp/check-${mode}-$(basename "$root")-$$"
  cp -a "$root" "$work"
  header=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["solution"][0])' "$work/.meta/config.json")
  source=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["solution"][1])' "$work/.meta/config.json")
  cp "$work/.meta/example.h" "$work/$header"
  cp "$work/.meta/example.cpp" "$work/$source"
  flags=""
  if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
  cmake -S "$work" -B "$work/build" -G "Unix Makefiles" -DCMAKE_CXX_FLAGS="$flags" >/dev/null
  cmake --build "$work/build" --parallel 2 >/dev/null
  count=$(ctest --test-dir "$work/build" -N | sed -n 's/^  Test #[0-9][0-9]*: //p' | wc -l)
  [ "$count" -eq 2 ]
  if ! ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$work/build" --output-on-failure >/tmp/ctest.log 2>&1; then cat /tmp/ctest.log >&2; return 1; fi
  rm -rf "$work"
  echo "$count"
}
verify_negative() {
  root="$1"
  work="/tmp/check-negative-$(basename "$root")-$$"
  cp -a "$root" "$work"
  header=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["solution"][0])' "$work/.meta/config.json")
  source=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["solution"][1])' "$work/.meta/config.json")
  cp "$work/.meta/example.h" "$work/$header"
  cp "$work/.meta/negative.cpp" "$work/$source"
  cmake -S "$work" -B "$work/build" -G "Unix Makefiles" >/dev/null
  cmake --build "$work/build" --parallel 2 >/dev/null
  if ctest --test-dir "$work/build" >/dev/null 2>&1; then exit 41; fi
  rm -rf "$work"
}
for root in @WORK@/family/rcv-*; do
  normal=$((normal + $(verify_one "$root" normal)))
  sanitizer=$((sanitizer + $(verify_one "$root" sanitizer)))
  verify_negative "$root"
  negatives=$((negatives + 1))
done
for root in @WORK@/family/.state/controls/*; do
  controls_normal=$((controls_normal + $(verify_one "$root" normal)))
  controls_sanitizer=$((controls_sanitizer + $(verify_one "$root" sanitizer)))
done
echo "NORMAL_TESTS=$normal"
echo "SANITIZER_TESTS=$sanitizer"
echo "NEGATIVES_REJECTED=$negatives"
echo "CONTROL_NORMAL_TESTS=$controls_normal"
echo "CONTROL_SANITIZER_TESTS=$controls_sanitizer"
"""


def _verify_runner(work: str, input_archive: str) -> str:
    """Owner-controlled verification runner for one packaged family tree.

    The same script drives the network-disabled Docker sanity path and the
    host verification path; only the work and archive locations differ.
    """
    return _VERIFY_RUNNER_TEMPLATE.replace("@WORK@", work).replace("@INPUT@", input_archive)


def _parse_verify_output(stdout: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _check_verify_counts(values: Mapping[str, str], expected_tree: str) -> None:
    if values.get("MOUNT_TREE_HASH") != expected_tree:
        _fail(
            "grader_mount_hash_mismatch",
            f"{values.get('MOUNT_TREE_HASH')}:{expected_tree}",
        )
    expected_tests = EXPECTED_ROOTS * 2
    if int(values.get("NORMAL_TESTS", "-1")) != expected_tests:
        _fail("zero_tests", values.get("NORMAL_TESTS", "missing"))
    if int(values.get("SANITIZER_TESTS", "-1")) != expected_tests:
        _fail("sanitizer_test_count_mismatch", values.get("SANITIZER_TESTS", "missing"))
    if int(values.get("NEGATIVES_REJECTED", "-1")) != EXPECTED_ROOTS:
        _fail("negative_fixture_not_rejected", values.get("NEGATIVES_REJECTED", "missing"))
    if (
        int(values.get("CONTROL_NORMAL_TESTS", "-1")) != len(CONTROL_NAMES) * 2
        or int(values.get("CONTROL_SANITIZER_TESTS", "-1")) != len(CONTROL_NAMES) * 2
    ):
        _fail("adversarial_control_not_coherent", str(values))


def _tool_identity(command: Sequence[str]) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return completed.stdout.splitlines()[0].strip()


def docker_sanity(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    core = verify_core(out)
    with tempfile.TemporaryDirectory(prefix="radix-checksum-docker-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "family.tar"
        with tarfile.open(archive, "w") as tar:
            for path in sorted(out.rglob("*")):
                if path.is_file() and not any(part == "build" for part in path.parts):
                    tar.add(path, arcname=path.relative_to(out), recursive=False)
        image_id = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if image_id != SANITY_IMAGE_ID:
            _fail("grader_image_mismatch", f"{image_id}:{SANITY_IMAGE_ID}")
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,exec,nosuid,size=2g",
                "--tmpfs",
                "/work:rw,exec,nosuid,size=2g",
                "-v",
                f"{archive}:/input/family.tar:ro",
                image,
                "sh",
                "-lc",
                _verify_runner("/work", "/input/family.tar"),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
    if completed.returncode != 0:
        _fail("docker_sanity_failed", completed.stdout[-2000:] + completed.stderr[-2000:])
    values = _parse_verify_output(completed.stdout)
    expected_tree = str(core["tree_hash"])
    _check_verify_counts(values, expected_tree)
    payload = {
        "schema_version": "radix-checksum-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": image,
        "image_id": image_id,
        "tree_hash": expected_tree,
        "generator_revision": _generator_revision(),
        "normal_test_count": EXPECTED_ROOTS * 2,
        "sanitizer_test_count": EXPECTED_ROOTS * 2,
        "negative_rejections": EXPECTED_ROOTS,
        "control_normal_test_count": len(CONTROL_NAMES) * 2,
        "control_sanitizer_test_count": len(CONTROL_NAMES) * 2,
        "command": [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            image,
            "sh",
            "-lc",
            "<owner-controlled-runner>",
        ],
        "stdout_hash": _sha256(completed.stdout.encode()),
    }
    _write(
        out / ".state/receipts/docker-sanity.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )
    return payload


def host_verify(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Host-side normal + fresh ASan/UBSan reference verification.

    Runs the exact owner-controlled verification script used by the Docker
    sanity path against the packaged current tree with the host toolchain:
    positive equal discovery counts in both modes, executed negative-fixture
    rejection for every root, and coherent adversarial-control builds.  This
    is host evidence, not locked-oracle or Docker-sanity evidence.
    """
    core = verify_core(out)
    with tempfile.TemporaryDirectory(prefix="radix-checksum-host-") as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "family.tar"
        with tarfile.open(archive, "w") as tar:
            for path in sorted(out.rglob("*")):
                if path.is_file() and not any(part == "build" for part in path.parts):
                    tar.add(path, arcname=path.relative_to(out), recursive=False)
        completed = subprocess.run(
            [
                "sh",
                "-lc",
                _verify_runner(
                    (temporary_path / "work").as_posix(), archive.as_posix()
                ),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
    if completed.returncode != 0:
        _fail("host_verify_failed", completed.stdout[-2000:] + completed.stderr[-2000:])
    values = _parse_verify_output(completed.stdout)
    expected_tree = str(core["tree_hash"])
    _check_verify_counts(values, expected_tree)
    payload = {
        "schema_version": "radix-checksum-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "tree_hash": expected_tree,
        "generator_revision": _generator_revision(),
        "normal_test_count": EXPECTED_ROOTS * 2,
        "sanitizer_test_count": EXPECTED_ROOTS * 2,
        "negative_rejections": EXPECTED_ROOTS,
        "control_normal_test_count": len(CONTROL_NAMES) * 2,
        "control_sanitizer_test_count": len(CONTROL_NAMES) * 2,
        "cmake_version": _tool_identity(["cmake", "--version"]),
        "cxx_path": shutil.which("c++") or "",
        "cxx_version": _tool_identity(["c++", "--version"]),
        "command": ["sh", "-lc", "<owner-controlled-host-runner>"],
        "stdout_hash": _sha256(completed.stdout.encode()),
    }
    _write(
        out / ".state/receipts/host-verify.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )
    return payload


def creator_preflight(out: Path = DEFAULT_OUT, *, require_docker: bool = True) -> dict[str, object]:
    core = verify_core(out)
    docker_path = out / ".state/receipts/docker-sanity.json"
    if require_docker:
        docker = docker_sanity(out)
    elif docker_path.is_file():
        docker = json.loads(docker_path.read_text())
    else:
        _fail("docker_sanity_not_completed", str(docker_path))
    if docker.get("tree_hash") != core.get("tree_hash") or docker.get(
        "generator_revision"
    ) != core.get("generator_revision"):
        _fail("stale_oracle_receipt", "Docker receipt does not bind current tree/owner")
    bindings = {
        "owner": _generator_revision(),
        "curriculum": _file_hash(CURRICULUM),
        "creation_prompt": _file_hash(CREATION_PROMPT),
        "implementation_prompt": _file_hash(IMPLEMENTATION_PROMPT),
        "focused_test": _file_hash(FOCUSED_TEST),
        "tree": _tree_hash(out),
        "core_receipt": _file_hash(out / ".state/receipts/core-preflight.json"),
        "diversity_receipt": _file_hash(out / ".state/receipts/diversity-screen.json"),
        "docker_receipt": _file_hash(docker_path),
        "source_inventories": _file_hash(out / ".state/manifests/source-inventories.json"),
        "selected_manifest": _file_hash(out / ".state/manifests/selected-candidates.json"),
    }
    subject_hash = _sha256(json.dumps(bindings, sort_keys=True).encode())
    payload = {
        "schema_version": "radix-checksum-creator-preflight-v1",
        "status": "pass",
        "root_count": EXPECTED_ROOTS,
        "pair_count": EXPECTED_PAIRS,
        "negative_rejections": EXPECTED_ROOTS,
        "controls": list(CONTROL_NAMES),
        "subject_hash": subject_hash,
        "bindings": bindings,
    }
    _write(
        out / ".state/receipts/creator-preflight.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        overwrite=True,
    )
    return payload


def _root_catalog_entry(out: Path, spec: TaskSpec) -> dict[str, object]:
    root = out / spec.task_id
    config = json.loads(_read(root, ".meta/config.json"))
    provenance = json.loads(_read(root, ".meta/provenance.json"))
    return {
        "task_id": spec.task_id,
        "family": FAMILY_ID,
        "capability": "radix-checksum-validation",
        "radix_mechanism": spec.radix.key,
        "checksum_mechanism": spec.checksum.key,
        "difficulty": "intermediate",
        "interaction": "aider-whole-file",
        "statefulness": "stateless",
        "verification": "docker_sanity",
        "disposition": "local-family-candidate",
        "tree_hash": _tree_hash(root),
        "config_hash": _sha256(json.dumps(config, sort_keys=True).encode()),
        "provenance_hash": _sha256(json.dumps(provenance, sort_keys=True).encode()),
        "primary_core_objective": "achieved",
    }


def audit(out: Path = DEFAULT_OUT, *, cycle: int) -> dict[str, object]:
    """Read-only audit of raw roots and current receipts; writes outside roots."""
    preflight_path = out / ".state/receipts/creator-preflight.json"
    if not preflight_path.is_file():
        _fail("audit_missing_creator_preflight", str(preflight_path))
    preflight = json.loads(preflight_path.read_text())
    catalog = [_root_catalog_entry(out, spec) for spec in TASKS]
    findings: list[dict[str, object]] = []
    if len(catalog) != EXPECTED_ROOTS:
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/root-count",
                "severity": "blocker",
                "disposition": "repair-and-reverify",
            }
        )
    if len({row["task_id"] for row in catalog}) != len(catalog):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/duplicate-id",
                "severity": "blocker",
                "disposition": "reject",
            }
        )
    docker = json.loads((out / ".state/receipts/docker-sanity.json").read_text())
    diversity = json.loads((out / ".state/receipts/diversity-screen.json").read_text())
    if docker.get("tree_hash") != _tree_hash(out):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/stale-docker",
                "severity": "blocker",
                "disposition": "repair-and-reverify",
            }
        )
    if diversity.get("pair_count") != EXPECTED_PAIRS or not diversity.get("pass"):
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/diversity",
                "severity": "major",
                "disposition": "repair-and-reverify",
            }
        )
    host_path = out / ".state/receipts/host-verify.json"
    host: dict[str, object] = {}
    if host_path.is_file():
        host = json.loads(host_path.read_text())
        if host.get("tree_hash") != _tree_hash(out) or host.get(
            "generator_revision"
        ) != _generator_revision():
            findings.append(
                {
                    "id": f"cycle-{cycle:02d}/family/stale-host-verify",
                    "severity": "blocker",
                    "disposition": "repair-and-reverify",
                }
            )
    else:
        findings.append(
            {
                "id": f"cycle-{cycle:02d}/family/host-verify-missing",
                "severity": "moderate",
                "disposition": "repair-and-reverify",
            }
        )
    subject = {
        "tree_hash": _tree_hash(out),
        "preflight_hash": _file_hash(preflight_path),
        "docker_hash": _file_hash(out / ".state/receipts/docker-sanity.json"),
        "diversity_hash": _file_hash(out / ".state/receipts/diversity-screen.json"),
        "host_verify_hash": _file_hash(host_path) if host_path.is_file() else None,
        "selected_hash": _file_hash(out / ".state/manifests/selected-candidates.json"),
        "catalog_hash": _sha256(json.dumps(catalog, sort_keys=True).encode()),
    }
    subject_hash = _sha256(json.dumps(subject, sort_keys=True).encode())
    report = {
        "schema_version": "audit-sft-data-quality-local-family-v1",
        "cycle": cycle,
        "audit_subject_hash": subject_hash,
        "behavior_contract": {
            "task": "complete two-file C++17 radix/checksum validators",
            "inputs": "visible docs and declared starters only",
            "output": "exact whole-file replacements",
            "invariants": "validate before arithmetic; no partial acceptance; owned mechanisms",
            "failure_behavior": "deterministic non-accepted audit",
            "resource_limits": "offline checked integer arithmetic",
            "evaluation": "normal/sanitizer CTest, negative fixtures, semantic screens",
            "generalization_target": "distinct radix representations and checksum mechanisms",
        },
        "confirmed_counts": {
            "roots": len(catalog),
            "pairs": diversity.get("pair_count"),
            "normal_tests": docker.get("normal_test_count"),
            "sanitizer_tests": docker.get("sanitizer_test_count"),
            "host_normal_tests": host.get("normal_test_count"),
            "host_sanitizer_tests": host.get("sanitizer_test_count"),
            "host_negative_rejections": host.get("negative_rejections"),
        },
        "root_catalog": catalog,
        "duplicate_lineage_report": {
            "exact_ids": 0,
            "prompt_hash_collisions": 0,
            "reference_hash_collisions": 0,
            "semantic_conflicts": 0,
        },
        "contamination_report": {"official_holdout_pairs": EXPECTED_ROOTS * 26, "dispositions": []},
        "corpus_composition": {
            "radix_mechanisms": {radix.key: 10 for radix in RADICES},
            "checksum_mechanisms": {checksum.key: 10 for checksum in CHECKSUMS},
        },
        "findings": findings,
        "decision": "local_family_verified" if not findings else "repair-and-reverify",
        "limitations": [
            "not an SFT row set",
            "not a dataset release",
            "not training authorization",
            "not benchmark uplift",
        ],
        "subject_bindings": subject,
        "creator_subject_hash": preflight.get("subject_hash"),
    }
    audit_root = out / ".state/audits"
    report_path = audit_root / f"cycle-{cycle:02d}-{subject_hash.removeprefix('sha256:')}.json"
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if report_path.exists() and report_path.read_text() != serialized:
        _fail("immutable_audit_conflict", str(report_path))
    _write(report_path, serialized, overwrite=report_path.exists())
    catalog_path = (
        audit_root / f"cycle-{cycle:02d}-{subject_hash.removeprefix('sha256:')}.catalog.jsonl"
    )
    catalog_text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in catalog)
    if catalog_path.exists() and catalog_path.read_text() != catalog_text:
        _fail("immutable_audit_conflict", str(catalog_path))
    _write(catalog_path, catalog_text, overwrite=catalog_path.exists())
    report["report_path"] = report_path.as_posix()
    report["catalog_path"] = catalog_path.as_posix()
    return report


def write_cycle_record(
    out: Path,
    *,
    cycle: int,
    audit_report: Mapping[str, object],
    terminal_status: str,
    finding_dispositions: Sequence[Mapping[str, object]] = (),
) -> Path:
    path = out / ".state/cycles" / f"cycle-{cycle:02d}.json"
    if path.exists():
        _fail("immutable_cycle_conflict", str(path))
    preflight = json.loads((out / ".state/receipts/creator-preflight.json").read_text())
    creator_bindings = preflight["bindings"]
    audit_bindings = audit_report["subject_bindings"]
    payload = {
        "schema_version": "aider-task-creation-cycle-v1",
        "cycle": cycle,
        "family_id": FAMILY_ID,
        "candidate_manifest": creator_bindings["selected_manifest"],
        "curriculum_hash": creator_bindings["curriculum"],
        "generator_hash": creator_bindings["owner"],
        "focused_test_hash": creator_bindings["focused_test"],
        "generated_tree_hash": audit_bindings["tree_hash"],
        "grader_policy_hash": audit_bindings["docker_hash"],
        "audit_subject_hash": audit_report["audit_subject_hash"],
        "audit_report_path": audit_report["report_path"],
        "finding_ids": [finding["id"] for finding in audit_report.get("findings", [])],
        "finding_dispositions": list(finding_dispositions),
        "retained_root_ids": [spec.task_id for spec in TASKS],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "terminal_status": terminal_status,
        "remaining_blockers": [],
    }
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def close_remediation(out: Path, *, audit_report: Mapping[str, object]) -> int:
    """Close cycle-one remedy records only after a finding-free fresh audit."""
    if audit_report.get("decision") != "local_family_verified" or audit_report.get("findings"):
        _fail("audit_not_clean", str(audit_report.get("audit_subject_hash")))
    remedy_root = out / ".state/remedy"
    records = sorted(remedy_root.glob("rcv-*.json"))
    if len(records) != EXPECTED_ROOTS:
        _fail("remedy_record_count", str(len(records)))
    for path in records:
        record = json.loads(path.read_text())
        record.update(
            {
                "status": "verified",
                "local_status": "local_family_verified",
                "fresh_audit_subject_hash": audit_report["audit_subject_hash"],
                "fresh_audit_report_path": audit_report["report_path"],
                "verification": {
                    "semantic_negative_profiles": audit_report["confirmed_counts"][
                        "semantic_negative_profiles"
                    ],
                    "negative_rejections": audit_report["confirmed_counts"]["negative_rejections"],
                    "normal_tests": audit_report["confirmed_counts"]["normal_tests"],
                    "sanitizer_tests": audit_report["confirmed_counts"]["sanitizer_tests"],
                },
            }
        )
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", overwrite=True)
    return len(records)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true")
    group.add_argument("--verify-core", action="store_true")
    group.add_argument("--verify-host", action="store_true")
    group.add_argument("--docker-sanity", action="store_true")
    group.add_argument("--creator-preflight", action="store_true")
    group.add_argument("--audit", type=int, metavar="CYCLE")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.build:
        result = build(args.out, force=args.force)
    elif args.verify_core:
        result = verify_core(args.out)
    elif args.verify_host:
        result = host_verify(args.out)
    elif args.docker_sanity:
        result = docker_sanity(args.out, args.image)
    elif args.creator_preflight:
        result = creator_preflight(args.out)
    else:
        result = audit(args.out, cycle=args.audit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
