"""Configuration data container for AudioControl Hyperion APR-16."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class APR16Config:
    """Configuration options for the APR-16 device client."""

    identifier: str
    name: str
    address: str
    port: int
