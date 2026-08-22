"""DesignDNA — L8 precedent memory (Phase 11)."""

from app.dna.store import (
    AcceptError,
    accept_design,
    archive_precedent,
    delete_precedent,
    get_precedent,
    list_precedents,
    precedent_block,
    search_precedents,
)

__all__ = [
    "AcceptError",
    "accept_design",
    "archive_precedent",
    "delete_precedent",
    "get_precedent",
    "list_precedents",
    "precedent_block",
    "search_precedents",
]
