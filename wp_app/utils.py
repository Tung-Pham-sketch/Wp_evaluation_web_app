from __future__ import annotations

import re
from typing import Any

from .matching import parse_mhr


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def column_map(headers: list[Any] | tuple[Any, ...]) -> dict[str, int]:
    return {
        normalize(value): index
        for index, value in enumerate(headers)
        if value not in (None, "")
    }


def mhr_hours(value: Any) -> float | None:
    return parse_mhr(value)
