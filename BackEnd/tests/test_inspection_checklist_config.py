"""The inspection checklist config and its field validation (unit, no HTTP)."""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from BL.inspection.common.inspection_checklist_config import (
    INSPECTION_CHECKLIST_CONFIG_PATH,
    InspectionFieldValueInvalid,
    check_inspection_checklist_config_is_well_formed,
    critical_inspection_item_keys,
    find_inspection_checklist_item,
    load_inspection_checklist_config,
    strip_control_characters,
    validate_item_field_value_changes,
    visible_field_values,
)
from BL.inspection.common.inspection_photo_google_drive import (
    build_drive_request_body,
    drive_request_signature,
    inspection_drive_folder_name,
)
from BL.inspection.inspectionPhotos import is_jpeg

FRONTEND_CONFIG_COPY_PATH = (
    pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "inspection" / "inspectionChecklistConfig.json"
)


def test_frontend_copy_of_the_config_is_byte_identical():
    assert FRONTEND_CONFIG_COPY_PATH.read_bytes() == pathlib.Path(INSPECTION_CHECKLIST_CONFIG_PATH).read_bytes(), (
        "run: cp BackEnd/BL/inspection/inspection_checklist_config.json frontend/src/inspection/inspectionChecklistConfig.json"
    )


def test_config_is_well_formed_and_lists_the_expected_critical_items():
    config = load_inspection_checklist_config()
    assert [section["key"] for section in config["sections"]] == ["structure_and_exterior", "utilities_and_mechanicals"]
    assert critical_inspection_item_keys() == ["roof", "foundation", "hvac", "electrical", "plumbing", "water_heater", "sewer", "water_supply"]


def test_config_check_rejects_a_follow_up_pointing_at_an_unknown_field():
    broken_config = {
        "sections": [
            {"key": "s", "label": "S", "items": [{"key": "i", "fields": [{"key": "f", "type": "text", "show_when": {"field_key": "nope", "equals": "x"}}]}]}
        ]
    }
    with pytest.raises(ValueError):
        check_inspection_checklist_config_is_well_formed(broken_config)


def test_choice_field_accepts_only_its_options():
    roof = find_inspection_checklist_item("roof")
    assert validate_item_field_value_changes(roof, {"roof_type": "metal"}) == {"roof_type": "metal"}
    with pytest.raises(InspectionFieldValueInvalid):
        validate_item_field_value_changes(roof, {"roof_type": "straw"})


def test_year_or_unknown_field_accepts_a_year_in_range_or_unknown():
    hvac = find_inspection_checklist_item("hvac")
    assert validate_item_field_value_changes(hvac, {"hvac_manufacture_year": 2015}) == {"hvac_manufacture_year": 2015}
    assert validate_item_field_value_changes(hvac, {"hvac_manufacture_year": "unknown"}) == {"hvac_manufacture_year": "unknown"}
    for invalid_year in (1850, date.today().year + 2, "2015", True, 2015.5):
        with pytest.raises(InspectionFieldValueInvalid):
            validate_item_field_value_changes(hvac, {"hvac_manufacture_year": invalid_year})


def test_window_counter_is_bounded():
    windows = find_inspection_checklist_item("windows")
    assert validate_item_field_value_changes(windows, {"windows_needing_replacement_count": 0}) == {"windows_needing_replacement_count": 0}
    for invalid_count in (-1, 100, "3"):
        with pytest.raises(InspectionFieldValueInvalid):
            validate_item_field_value_changes(windows, {"windows_needing_replacement_count": invalid_count})


def test_septic_pump_date_must_be_a_past_date_or_unknown():
    sewer = find_inspection_checklist_item("sewer")
    assert validate_item_field_value_changes(sewer, {"septic_last_pump_date": "2024-03-01"}) == {"septic_last_pump_date": "2024-03-01"}
    assert validate_item_field_value_changes(sewer, {"septic_last_pump_date": "unknown"}) == {"septic_last_pump_date": "unknown"}
    for invalid_date in ("2999-01-01", "03/01/2024", "2024-13-01"):
        with pytest.raises(InspectionFieldValueInvalid):
            validate_item_field_value_changes(sewer, {"septic_last_pump_date": invalid_date})


def test_unknown_field_key_is_rejected_and_null_clears():
    sewer = find_inspection_checklist_item("sewer")
    with pytest.raises(InspectionFieldValueInvalid):
        validate_item_field_value_changes(sewer, {"pool_type": "salt"})
    assert validate_item_field_value_changes(sewer, {"sewer_type": None}) == {"sewer_type": None}


def test_text_or_unknown_strips_control_characters_and_is_bounded():
    electrical = find_inspection_checklist_item("electrical")
    assert validate_item_field_value_changes(electrical, {"electrical_panel_brand": "  Square\x00 D  "}) == {"electrical_panel_brand": "Square D"}
    with pytest.raises(InspectionFieldValueInvalid):
        validate_item_field_value_changes(electrical, {"electrical_panel_brand": "x" * 121})


def test_follow_up_values_are_hidden_once_their_condition_no_longer_holds():
    sewer = find_inspection_checklist_item("sewer")
    assert visible_field_values(sewer, {"sewer_type": "septic", "septic_last_pump_date": "2024-03-01"}) == {
        "sewer_type": "septic",
        "septic_last_pump_date": "2024-03-01",
    }
    assert visible_field_values(sewer, {"sewer_type": "city", "septic_last_pump_date": "2024-03-01"}) == {"sewer_type": "city"}


def test_strip_control_characters_keeps_newlines_and_tabs():
    assert strip_control_characters("a\x07b\nc\td\x7f") == "ab\nc\td"


def test_jpeg_check_needs_start_and_end_markers():
    assert is_jpeg(b"\xff\xd8\xff\xe0abc\xff\xd9")
    assert not is_jpeg(b"\x89PNG\r\n\x1a\n")
    assert not is_jpeg(b"\xff\xd8\xff\xe0<html>")


def test_drive_request_signature_matches_the_apps_script_message_format():
    import hashlib
    import hmac

    body = build_drive_request_body(action="save", secret="s3cret", timestamp=1700000000, subject="folder/roof 1.jpg", image=b"jpeg")
    image_sha256 = hashlib.sha256(b"jpeg").hexdigest()
    expected_signature = hmac.new(b"s3cret", f"1700000000\nsave\nfolder/roof 1.jpg\n{image_sha256}".encode(), hashlib.sha256).hexdigest()
    assert body["signature"] == expected_signature == drive_request_signature("s3cret", 1700000000, "save", "folder/roof 1.jpg", image_sha256)
    assert body["image_sha256"] == image_sha256


def test_drive_folder_name_is_readable_safe_and_bounded():
    folder_name = inspection_drive_folder_name("2026-10-28", "12 Palm Ave/../x <Tampa>", "3f2a9c1e-0000-4000-8000-000000000000")
    assert folder_name == "2026-10-28 12 Palm Ave .. x Tampa (3f2a9c1e)"
    assert "/" not in folder_name
    assert len(inspection_drive_folder_name("2026-10-28", "x" * 500, "3f2a9c1e")) <= 120
