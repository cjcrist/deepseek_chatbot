"""User-selectable explanation depth for chat responses (service-layer type)."""

from enum import StrEnum


class ExplanationLevel(StrEnum):
    """How deeply the model should explain answers."""

    BEGINNER = "beginner"
    MODERATE = "moderate"
    EXPERT = "expert"
