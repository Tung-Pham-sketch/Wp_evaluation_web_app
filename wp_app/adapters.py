# =============================================================================
# adapters.py – REGISTRY: TALLY SHEET FORMAT -> PARSER (+ STRUCTURE READER)
# -----------------------------------------------------------------------------
# AdapterDefinition(name, customer_codes, parser, structure_inspector)
# ADAPTERS            the registered formats: VietJet, Lufthansa.
#                     A new customer layout = write a parser + add one line here;
#                     it then appears automatically in the upload form.
# adapter_for_customer(customer)   default format of a customer code
#                     (raises ValueError if unknown) – used by the fork's seed.
# adapter_for_upload(customer, tally_format)   format chosen on the step-1
#                     form; falls back to adapter_for_customer() if empty.
# parse_tally(name, path)           run the parser of a format.
# inspect_tally_structure(name, path)  block structure (Lufthansa only).
# tally_format_names()              formats offered in the upload dropdown.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .parsers import inspect_lufthansa_structure, parse_lufthansa, parse_vietjet


Parser = Callable[[Path], list[dict[str, Any]]]
Inspector = Callable[[Path], dict[str, Any]]


@dataclass(frozen=True)
class AdapterDefinition:
    name: str
    customer_codes: tuple[str, ...]
    parser: Parser
    structure_inspector: Inspector | None = None


ADAPTERS = (
    AdapterDefinition("VietJet", ("VA-VJ",), parse_vietjet),
    AdapterDefinition("Lufthansa", ("DLH",), parse_lufthansa, inspect_lufthansa_structure),
)

ADAPTERS_BY_NAME = {adapter.name: adapter for adapter in ADAPTERS}
ADAPTERS_BY_CUSTOMER = {
    customer: adapter
    for adapter in ADAPTERS
    for customer in adapter.customer_codes
}


def adapter_for_customer(customer: str) -> str:
    adapter = ADAPTERS_BY_CUSTOMER.get(customer.strip().upper())
    if not adapter:
        raise ValueError(f"Chưa hỗ trợ parser cho khách hàng: {customer}")
    return adapter.name


def parse_tally(adapter_name: str, path: Path) -> list[dict[str, Any]]:
    adapter = ADAPTERS_BY_NAME.get(adapter_name)
    if not adapter:
        raise ValueError(f"Không tìm thấy adapter: {adapter_name}")
    return adapter.parser(path)


def inspect_tally_structure(adapter_name: str, path: Path) -> dict[str, Any] | None:
    adapter = ADAPTERS_BY_NAME.get(adapter_name)
    if not adapter:
        raise ValueError(f"Không tìm thấy adapter: {adapter_name}")
    return adapter.structure_inspector(path) if adapter.structure_inspector else None


# --- Merged: Tally format chosen on the upload form -------------------------
def tally_format_names() -> list[str]:
    """Layouts offered in the upload form (one per registered adapter)."""
    return [adapter.name for adapter in ADAPTERS]


def adapter_for_upload(customer: str, tally_format: str | None = None) -> str:
    """Adapter chosen by the user on the upload form; falls back to the customer mapping."""
    if tally_format:
        if tally_format not in ADAPTERS_BY_NAME:
            raise ValueError(f"Mẫu Tally Sheet không hợp lệ: {tally_format}")
        return tally_format
    return adapter_for_customer(customer)
