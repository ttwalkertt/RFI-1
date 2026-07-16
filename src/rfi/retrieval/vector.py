"""Dependency-free deterministic vector candidate generation for the bounded POC."""

from __future__ import annotations

import hashlib
import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> tuple[str, ...]:
    """Normalize search tokens without claiming semantic interpretation."""
    return tuple(_TOKEN.findall(text.lower()))


class HashingVectorizer:
    """Replaceable signed feature-hashing vectorizer with no external model state."""

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 16:
            raise ValueError("vector dimensions must be at least 16")
        self.dimensions = dimensions

    @property
    def name(self) -> str:
        """Return the persisted implementation identity."""
        return f"rfi-hashing-vector-v1-{self.dimensions}"

    def vector(self, text: str) -> tuple[float, ...]:
        """Map normalized tokens into a stable unit vector."""
        values = [0.0] * self.dimensions
        for token in tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            values[bucket] += sign
        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude:
            values = [value / magnitude for value in values]
        return tuple(values)


class CharacterNgramVectorizer:
    """Independent character-trigram hashing candidate implementation."""

    def __init__(self, dimensions: int = 192) -> None:
        if dimensions < 16:
            raise ValueError("vector dimensions must be at least 16")
        self.dimensions = dimensions

    @property
    def name(self) -> str:
        """Return the distinct persisted implementation identity."""
        return f"rfi-character-ngram-vector-v1-{self.dimensions}"

    def vector(self, text: str) -> tuple[float, ...]:
        """Map normalized character trigrams into an unsigned stable unit vector."""
        normalized = " ".join(tokens(text))
        grams = (
            tuple(normalized[index:index + 3] for index in range(len(normalized) - 2))
            if len(normalized) >= 3
            else (normalized,)
        )
        values = [0.0] * self.dimensions
        for gram in grams:
            digest = hashlib.sha256(gram.encode()).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            values[bucket] += 1.0
        magnitude = math.sqrt(sum(value * value for value in values))
        if magnitude:
            values = [value / magnitude for value in values]
        return tuple(values)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Return cosine for vectors already normalized by the implementation."""
    if len(left) != len(right):
        raise ValueError("vector dimensions differ")
    return sum(a * b for a, b in zip(left, right, strict=True))
