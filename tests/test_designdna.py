"""Phase 11 — DesignDNA precedent memory.

The properties under test are the reviewed plan's four rules:
identity is the package digest (R1), acceptance has an author (R3),
retrieval is explainable (R4), archive and delete differ (R6).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import DesignDnaRow, DesignRow
from app.dna import (
    AcceptError,
    accept_design,
    archive_precedent,
    delete_precedent,
    get_precedent,
    list_precedents,
    precedent_block,
    search_precedents,
)


def _seed_design(session, *, material="basalt_slab", height_mm=740.0,
                 has_water=True, profile="public_plaza") -> str:
    design_id = str(uuid.uuid4())
    stored = {
        "schema": "assembly_design_record_v1",
        "request": {
            "seed": 7,
            "gate_profile_id": profile,
            "water": {"has_water": has_water},
        },
        "manifest": {
            "schema": "assembly_manifest_v1",
            "elements": [
                {"element_id": "b1", "primitive": "basin_round",
                 "material_id": material},
                {"element_id": "p1", "primitive": "plinth",
                 "material_id": material},
            ],
            "assembly_bbox_min_mm": [-1100, -1100, 0],
            "assembly_bbox_max_mm": [1100, 1100, height_mm],
            "total_mass_kg": 2400.0,
        },
        "artifacts": {"step_sha256": "a" * 64},
    }
    session.add(DesignRow(
        id=design_id, created_at=datetime.now(timezone.utc).isoformat(),
        spec_id=None, geometry_hash="a" * 64,
        parameter_json=json.dumps(stored), status="assembly_built",
        seed=7, spec_hash="s" * 64, build_ms=1.0, glb_path=None, step_path=None,
    ))
    session.flush()
    return design_id


def _accept(session, design_id, *, digest=None, overall="pass", note="clean plaza fountain",
            by="operator"):
    return accept_design(
        session, design_id=design_id, accepted_by=by, acceptance_note=note,
        content_digest=(uuid.uuid4().hex * 2) if digest is None else digest,
        validation_statuses={"structure_static_v1": overall},
        overall_status=overall, costing=None,
    )


@pytest.fixture()
def db_session(tmp_path):
    from app.db.database import Database

    db = Database(tmp_path / "dna.db")
    db.init_db()
    with db.get_session() as session:
        yield session


# --- acceptance invariants (R1, R3) ----------------------------------------

def test_accept_requires_author_note_and_package(db_session):
    design_id = _seed_design(db_session)
    with pytest.raises(AcceptError, match="accepted_by"):
        _accept(db_session, design_id, by="  ")
    with pytest.raises(AcceptError, match="acceptance_note"):
        _accept(db_session, design_id, note=" ")
    with pytest.raises(AcceptError, match="export package"):
        _accept(db_session, design_id, digest="")


def test_a_failing_design_cannot_become_precedent(db_session):
    design_id = _seed_design(db_session)
    with pytest.raises(AcceptError, match="failing design"):
        _accept(db_session, design_id, overall="fail")


def test_identical_deliverable_is_deduped_on_digest(db_session):
    design_id = _seed_design(db_session)
    digest = "d" * 64
    _accept(db_session, design_id, digest=digest)
    db_session.flush()
    with pytest.raises(AcceptError, match="already precedent"):
        _accept(db_session, design_id, digest=digest)


def test_same_geometry_different_material_is_two_precedents(db_session):
    """R1: content_digest separates what a geometry hash cannot."""
    basalt = _seed_design(db_session, material="basalt_slab")
    bronze = _seed_design(db_session, material="bronze_cast")
    _accept(db_session, basalt, digest="1" * 64)
    _accept(db_session, bronze, digest="2" * 64)
    db_session.flush()
    assert len(list_precedents(db_session)) == 2


def test_tags_are_measured_from_the_manifest(db_session):
    design_id = _seed_design(db_session, height_mm=2400.0)
    row = _accept(db_session, design_id, digest="3" * 64)
    db_session.flush()
    tags = json.loads(row.tags_json)
    assert tags["height_m"] == 2.4
    assert tags["footprint_m"] == 2.2
    assert tags["materials"] == ["basalt_slab"]
    assert set(tags["primitives"]) == {"basin_round", "plinth"}
    assert tags["has_water"] is True
    assert tags["gate_profile_id"] == "public_plaza"


# --- retrieval (R4) ---------------------------------------------------------

def test_search_returns_named_match_reasons(db_session):
    design_id = _seed_design(db_session, height_mm=2400.0)
    _accept(db_session, design_id, digest="4" * 64)
    db_session.flush()

    hits = search_precedents(
        db_session, material="basalt_slab", has_water=True, height_m=2.0,
    )
    assert len(hits) == 1
    reasons = hits[0]["match_reasons"]
    assert "material basalt_slab" in reasons
    assert "water design" in reasons
    assert any("height 2.4 m within" in r for r in reasons)


def test_search_is_an_and_filter_not_a_fuzzy_score(db_session):
    design_id = _seed_design(db_session, has_water=False)
    _accept(db_session, design_id, digest="5" * 64)
    db_session.flush()
    assert search_precedents(db_session, material="basalt_slab", has_water=True) == []
    assert len(search_precedents(db_session, material="basalt_slab", has_water=False)) == 1


def test_more_specific_matches_rank_first(db_session):
    a = _seed_design(db_session, has_water=True)
    b = _seed_design(db_session, has_water=False)
    _accept(db_session, a, digest="6" * 64, note="the water one")
    _accept(db_session, b, digest="7" * 64, note="the dry one")
    db_session.flush()
    hits = search_precedents(db_session, material="basalt_slab", has_water=True,
                             text="water")
    assert hits and len(hits[0]["match_reasons"]) == 3


# --- injection (R5) ---------------------------------------------------------

def test_precedent_block_is_quarantined_and_capped(db_session):
    ids = []
    for i in range(5):
        d = _seed_design(db_session)
        row = _accept(db_session, d, digest=str(i) * 64, note=f"precedent {i}")
        ids.append(row.id)
    db_session.flush()
    hits = search_precedents(db_session, material="basalt_slab", limit=10)
    block = precedent_block(hits)
    assert "BEGIN PRECEDENTS" in block and "END PRECEDENTS" in block
    assert "NOT requirements" in block
    assert "Never copy a dimension" in block
    # Capped at 3 — a session must not drown in memory.
    assert block.count("PRECEDENT ") == 3
    assert precedent_block([]) == ""


# --- archive vs delete (R6) -------------------------------------------------

def test_archive_hides_from_retrieval_but_stays_resolvable(db_session):
    design_id = _seed_design(db_session)
    row = _accept(db_session, design_id, digest="8" * 64)
    db_session.flush()
    archived = archive_precedent(db_session, row.id)
    assert archived["status"] == "archived"
    assert search_precedents(db_session, material="basalt_slab") == []
    assert list_precedents(db_session) == []
    # ...but the record is intact for old sessions that cite it.
    got = get_precedent(db_session, row.id, full=True)
    assert got["status"] == "archived"
    assert got["acceptance_note"] == "clean plaza fountain"
    assert got["record"]["manifest"]["schema"] == "assembly_manifest_v1"


def test_delete_leaves_a_tombstone_not_a_dangling_reference(db_session):
    design_id = _seed_design(db_session)
    row = _accept(db_session, design_id, digest="9" * 64)
    db_session.flush()
    deleted = delete_precedent(db_session, row.id)
    assert deleted["status"] == "deleted"
    got = get_precedent(db_session, row.id)
    assert got is not None, "the id must still resolve"
    assert got["status"] == "deleted"
    assert "deleted" in got["detail"]
    assert "acceptance_note" not in got
    # A deleted digest frees the slot: the same deliverable can be
    # re-accepted deliberately.
    _accept(db_session, design_id, digest="9" * 64)


def test_archived_precedent_cannot_be_double_deleted_confusingly(db_session):
    design_id = _seed_design(db_session)
    row = _accept(db_session, design_id, digest="b" * 64)
    db_session.flush()
    delete_precedent(db_session, row.id)
    assert archive_precedent(db_session, row.id) is None
