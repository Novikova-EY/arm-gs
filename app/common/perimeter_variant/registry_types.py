# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PerimeterVariantDefinition:
    code: str
    label_suffix: str
    effective_from_year: int | None = None
    effective_to_year: int | None = None


@dataclass(frozen=True, slots=True)
class EntityPerimeterBinding:
    entity_kind: str
    entity_name_cf: str
    variants: tuple[PerimeterVariantDefinition, ...]
    label_prefix: str | None = None
    entity_name: str | None = None

    @property
    def display_label_prefix(self) -> str:
        return (self.label_prefix or self.entity_name or "").strip()

    def matches_name(self, name: str | None) -> bool:
        if not name or not str(name).strip():
            return False
        return str(name).strip().casefold() == self.entity_name_cf
