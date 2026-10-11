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
