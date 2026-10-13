"""Configuração por variável de ambiente. Ver .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DSN = "postgresql://vaster:vaster@localhost:5432/vaster"


@dataclass(frozen=True)
class Config:
    dsn: str
    tcgdex_base: str
    lang_pt: str
    lang_en: str
    concurrency: int
    timeout: float
    pokeapi_base: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            dsn=os.environ.get("VASTER_DB_DSN", DEFAULT_DSN),
            tcgdex_base=os.environ.get("TCGDEX_BASE", "https://api.tcgdex.net/v2").rstrip("/"),
            # 'pt', não 'pt-br'. Ver docs/achados-tcgdex.md.
            lang_pt=os.environ.get("TCGDEX_LANG_PT", "pt"),
            lang_en=os.environ.get("TCGDEX_LANG_EN", "en"),
            concurrency=int(os.environ.get("TCGDEX_CONCURRENCY", "6")),
            timeout=float(os.environ.get("TCGDEX_TIMEOUT", "30")),
            pokeapi_base=os.environ.get("POKEAPI_BASE", "https://pokeapi.co/api/v2").rstrip("/"),
        )
