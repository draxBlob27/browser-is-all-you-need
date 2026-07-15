"""Frozen pilot taxonomy and deterministic source classifications."""

from __future__ import annotations

from collections import Counter
from typing import Final

from .schema import Difficulty, PrimaryCategory, Split

CATEGORY_SLUGS: Final[dict[PrimaryCategory, tuple[str, ...]]] = {
    PrimaryCategory.ALGORITHMS: (
        "binary-search",
        "collatz-conjecture",
        "etl",
        "high-scores",
        "list-ops",
        "matching-brackets",
        "nucleotide-count",
        "prime-factors",
        "secret-handshake",
        "series",
        "sieve",
        "simple-linked-list",
        "sum-of-multiples",
        "two-bucket",
    ),
    PrimaryCategory.TEXT: (
        "acronym",
        "affine-cipher",
        "anagram",
        "atbash-cipher",
        "bob",
        "hamming",
        "isbn-verifier",
        "isogram",
        "pangram",
        "pig-latin",
        "protein-translation",
        "rail-fence-cipher",
        "run-length-encoding",
        "word-count",
    ),
    PrimaryCategory.NUMERICAL: (
        "armstrong-numbers",
        "binary",
        "difference-of-squares",
        "eliuds-eggs",
        "grains",
        "hexadecimal",
        "largest-series-product",
        "luhn",
        "nth-prime",
        "pascals-triangle",
        "raindrops",
        "resistor-color",
        "resistor-color-duo",
        "trinary",
    ),
    PrimaryCategory.TIME: (
        "election-day",
        "freelancer-rates",
        "interest-is-interesting",
        "leap",
        "twelve-days",
    ),
    PrimaryCategory.STATE: (
        "doctor-data",
        "ellens-alien-game",
        "hello-world",
        "lasagna",
        "lasagna-master",
        "last-will",
        "making-the-grade",
        "power-of-troy",
        "reverse-string",
        "rna-transcription",
        "robot-simulator",
        "speedywagon",
        "troll-the-trolls",
        "vehicle-purchase",
    ),
    PrimaryCategory.LOGIC: (
        "alphametics",
        "beer-song",
        "darts",
        "flower-field",
        "food-chain",
        "log-levels",
        "minesweeper",
        "pacman-rules",
        "roman-numerals",
        "rotational-cipher",
        "say",
        "scrabble-score",
        "triangle",
        "two-fer",
    ),
}

TIME_SPLITS: Final[dict[str, Split]] = {
    "leap": Split.TRAIN,
    "twelve-days": Split.TRAIN,
    "election-day": Split.VALIDATION,
    "freelancer-rates": Split.VALIDATION,
    "interest-is-interesting": Split.TEST,
}


def category_for(slug: str) -> PrimaryCategory:
    matches = [category for category, slugs in CATEGORY_SLUGS.items() if slug in slugs]
    if len(matches) != 1:
        raise ValueError(f"source slug must have exactly one primary category: {slug}")
    return matches[0]


def source_split(slug: str, category: PrimaryCategory) -> Split:
    if category is PrimaryCategory.TIME:
        return TIME_SPLITS[slug]
    index = CATEGORY_SLUGS[category].index(slug)
    if index < 11:
        return Split.TRAIN
    if category in {PrimaryCategory.ALGORITHMS, PrimaryCategory.NUMERICAL}:
        return Split.VALIDATION if index in {11, 12} else Split.TEST
    return Split.VALIDATION if index == 11 else Split.TEST


def source_difficulty(slug: str, category: PrimaryCategory) -> Difficulty:
    index = CATEGORY_SLUGS[category].index(slug)
    return (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD)[index % 3]


def source_tags(slug: str, category: PrimaryCategory, source_kind: str) -> list[str]:
    tags = {
        PrimaryCategory.ALGORITHMS: ["algorithms", "collections"],
        PrimaryCategory.TEXT: ["strings", "validation"],
        PrimaryCategory.NUMERICAL: ["boundaries", "numerical"],
        PrimaryCategory.TIME: ["dates", "validation"],
        PrimaryCategory.STATE: ["classes", "stateful-objects"],
        PrimaryCategory.LOGIC: ["control-flow", "games"],
    }[category]
    if source_kind == "concept":
        tags = [*tags, "multi-file"]
    if slug in {"simple-linked-list", "two-bucket", "robot-simulator"}:
        tags = [*tags, "stateful-objects"]
    return sorted(set(tags))


def validate_taxonomy_inventory(slugs: set[str]) -> None:
    expected = {slug for group in CATEGORY_SLUGS.values() for slug in group}
    if slugs != expected or len(expected) != 75:
        missing = sorted(expected - slugs)
        extra = sorted(slugs - expected)
        raise ValueError(f"taxonomy inventory mismatch; missing={missing}, extra={extra}")


def source_cell_counts(entries: list[dict]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = {}
    for category in PrimaryCategory:
        counter: Counter[str] = Counter()
        for entry in entries:
            if entry["primary_category"] == category.value and entry.get("enabled", True):
                counter[entry["intended_split"]] += 1
        counts[category.value] = dict(sorted(counter.items()))
    return counts
