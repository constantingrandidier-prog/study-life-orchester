"""Tests for custom pause insertion, block splitting into 1h intervals, and persistence in daily rhythm."""

import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.services.daily_rhythm_service import generate_daily_science_rhythm
from app.db.repository import save_rhythm_action, get_rhythm_actions_for_date, restore_rhythm_action

client = TestClient(app)


def test_generate_daily_science_rhythm_with_split_blocks():
    target = date(2027, 6, 1)
    
    # Simulate a split of block_morning_reps (e.g. 180m into 2x 50m parts + 10m pause + 60m rest)
    split_payload = {
        "sub_blocks": [
            {
                "id": "block_morning_reps_p1",
                "duration_minutes": 50,
                "title": "Block 1: Morgen-Repetitionen (Teil 1)",
                "subtitle": "50 Min. Fokus-Intervall",
                "focus_type": "active_recall",
                "color": "#58a6ff",
                "is_break": False,
                "parent_id": "block_morning_reps",
            },
            {
                "id": "block_morning_reps_brk1",
                "duration_minutes": 10,
                "title": "Pause (nach Teil 1)",
                "subtitle": "10 Min. Erholung",
                "focus_type": "pause",
                "color": "#3fb950",
                "is_break": True,
                "parent_id": "block_morning_reps",
            },
            {
                "id": "block_morning_reps_p2",
                "duration_minutes": 60,
                "title": "Block 1: Morgen-Repetitionen (Teil 2)",
                "subtitle": "60 Min. Fokus-Intervall",
                "focus_type": "active_recall",
                "color": "#58a6ff",
                "is_break": False,
                "parent_id": "block_morning_reps",
            }
        ]
    }

    res = generate_daily_science_rhythm(
        target_date=target,
        cards_due_today=120,
        start_time_str="08:30",
        split_blocks={"block_morning_reps": split_payload},
    )

    block_ids = [b["id"] for b in res["blocks"]]
    assert "block_morning_reps" not in block_ids
    assert "block_morning_reps_p1" in block_ids
    assert "block_morning_reps_brk1" in block_ids
    assert "block_morning_reps_p2" in block_ids

    # Check times
    p1 = next(b for b in res["blocks"] if b["id"] == "block_morning_reps_p1")
    brk1 = next(b for b in res["blocks"] if b["id"] == "block_morning_reps_brk1")
    p2 = next(b for b in res["blocks"] if b["id"] == "block_morning_reps_p2")

    assert p1["start_time"] == "08:30"
    assert p1["end_time"] == "09:20"
    assert brk1["start_time"] == "09:20"
    assert brk1["end_time"] == "09:30"
    assert p2["start_time"] == "09:30"
    assert p2["end_time"] == "10:30"


def test_generate_daily_science_rhythm_with_inserted_pause():
    target = date(2027, 6, 2)
    custom_pause = {
        "id": "pause_custom_test",
        "duration_minutes": 20,
        "title": "Pause: Frische Luft",
        "is_break": True,
        "color": "#3fb950",
    }

    res = generate_daily_science_rhythm(
        target_date=target,
        start_time_str="08:30",
        inserted_blocks=[custom_pause],
    )

    block_ids = [b["id"] for b in res["blocks"]]
    assert "pause_custom_test" in block_ids
    found_pause = next(b for b in res["blocks"] if b["id"] == "pause_custom_test")
    assert found_pause["duration_minutes"] == 20
    assert found_pause["is_break"] is True


def test_rhythm_actions_repo_and_api_split_and_insert():
    test_date = "2027-06-03"

    # Save a split action
    save_rhythm_action(
        source_date=test_date,
        block_id="block_morning_reps",
        action="split",
        block_payload={"sub_blocks": [{"id": "sub1", "duration_minutes": 45}]},
    )

    # Save an inserted pause
    save_rhythm_action(
        source_date=test_date,
        block_id="pause_adhoc_1",
        action="insert",
        block_payload={"id": "pause_adhoc_1", "duration_minutes": 15, "title": "Kaffeepause", "is_break": True},
    )

    actions = get_rhythm_actions_for_date(test_date)
    assert "block_morning_reps" in actions["split_blocks"]
    assert any(b["id"] == "pause_adhoc_1" for b in actions["inserted_blocks"])

    # Test via API
    resp = client.get(f"/api/v1/schedule/rhythm-actions?target_date={test_date}")
    assert resp.status_code == 200
    data = resp.json()
    assert "block_morning_reps" in data["split_blocks"]
    assert any(b["id"] == "pause_adhoc_1" for b in data["inserted_blocks"])

    # Clean up
    restore_rhythm_action(test_date)
    actions_after = get_rhythm_actions_for_date(test_date)
    assert "block_morning_reps" not in actions_after["split_blocks"]
    assert len(actions_after["inserted_blocks"]) == 0


def test_rhythm_action_block_interruption_preserves_block_and_shifts_schedule():
    test_date = "2027-06-04"

    # Save an interruption for a study block
    save_rhythm_action(
        source_date=test_date,
        block_id="block_morning_reps",
        action="interrupt",
        block_payload={"interruptions": [{"id": "pause_1", "start_time": "10:30", "duration_minutes": 15, "title": "Pause"}]},
    )

    actions = get_rhythm_actions_for_date(test_date)
    assert "block_morning_reps" in actions["interrupted_blocks"]
    assert actions["interrupted_blocks"]["block_morning_reps"][0]["duration_minutes"] == 15

    # Check via daily rhythm endpoint
    resp = client.get(f"/api/v1/schedule/daily-rhythm?target_date={test_date}&start_time=08:30")
    assert resp.status_code == 200
    data = resp.json()

    # Block was NOT replaced - it still exists with original ID!
    reps_block = next(b for b in data["blocks"] if b["id"] == "block_morning_reps")
    assert reps_block is not None
    assert "interruptions" in reps_block
    assert len(reps_block["interruptions"]) == 1
    assert reps_block["interruptions"][0]["duration_minutes"] == 15

    # Clean up
    restore_rhythm_action(test_date)
    actions_after = get_rhythm_actions_for_date(test_date)
    assert "block_morning_reps" not in actions_after.get("interrupted_blocks", {})

