"""The property inspection checklist: sections, items, fields and follow-ups.

`BL/inspection/inspection_checklist_config.json` is the single source of truth.
The frontend keeps a byte-identical copy (`frontend/src/inspection/inspectionChecklistConfig.json`,
checked by `tests/test_inspection_checklist_config.py`). Adding a section or an
item later is a config-only change: the server validates every field value
against this config, and the UI renders from it.

Field types:
    choice              one of `options[].value`
    year_or_unknown     an integer year (1900 .. next year) or "unknown"
    text_or_unknown     free text (at most 120 characters) or "unknown"
    date_or_unknown     an ISO date (YYYY-MM-DD) or "unknown"
    counter             an integer between `minimum_count` and `maximum_count`
    text                free text (at most 500 characters)

A field with `show_when: {field_key, equals}` is a follow-up question: it only
applies while that other field of the same item has that value.
"""

from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from typing import Any

INSPECTION_CHECKLIST_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "inspection_checklist_config.json")

ITEM_STATUS_NOT_CHECKED = "not_checked"
ITEM_STATUS_OK = "ok"
ITEM_STATUS_REPAIR = "repair"
ITEM_STATUS_REPLACE = "replace"
ALL_ITEM_STATUSES = (ITEM_STATUS_NOT_CHECKED, ITEM_STATUS_OK, ITEM_STATUS_REPAIR, ITEM_STATUS_REPLACE)

UNKNOWN_FIELD_VALUE = "unknown"
EARLIEST_ALLOWED_YEAR = 1900
MAXIMUM_TEXT_OR_UNKNOWN_LENGTH = 120
MAXIMUM_FREE_TEXT_FIELD_LENGTH = 500
SUPPORTED_FIELD_TYPES = {"choice", "year_or_unknown", "text_or_unknown", "date_or_unknown", "counter", "text"}


class InspectionFieldValueInvalid(ValueError):
    pass


@lru_cache(maxsize=1)
def load_inspection_checklist_config() -> dict:
    with open(INSPECTION_CHECKLIST_CONFIG_PATH, encoding="utf-8") as config_file:
        config = json.load(config_file)
    check_inspection_checklist_config_is_well_formed(config)
    return config


def check_inspection_checklist_config_is_well_formed(config: dict) -> None:
    """Raises ValueError when the config is inconsistent (run once at load)."""

    seen_item_keys: set[str] = set()
    for section in config["sections"]:
        if not section.get("key") or not section.get("label"):
            raise ValueError("every section needs a key and a label")
        for item in section["items"]:
            if item["key"] in seen_item_keys:
                raise ValueError(f"duplicate item key {item['key']!r}")
            seen_item_keys.add(item["key"])
            field_keys = [field["key"] for field in item["fields"]]
            if len(field_keys) != len(set(field_keys)):
                raise ValueError(f"duplicate field key in item {item['key']!r}")
            for field in item["fields"]:
                if field["type"] not in SUPPORTED_FIELD_TYPES:
                    raise ValueError(f"unsupported field type {field['type']!r}")
                if field["type"] == "choice" and not field.get("options"):
                    raise ValueError(f"choice field {field['key']!r} needs options")
                if field["type"] == "counter" and field["minimum_count"] > field["maximum_count"]:
                    raise ValueError(f"counter field {field['key']!r} has minimum above maximum")
                show_when = field.get("show_when")
                if show_when and show_when["field_key"] not in field_keys:
                    raise ValueError(f"follow-up {field['key']!r} refers to an unknown field")


def all_inspection_checklist_items() -> list[dict]:
    return [item for section in load_inspection_checklist_config()["sections"] for item in section["items"]]


def find_inspection_checklist_item(item_key: str) -> dict | None:
    return next((item for item in all_inspection_checklist_items() if item["key"] == item_key), None)


def critical_inspection_item_keys() -> list[str]:
    return [item["key"] for item in all_inspection_checklist_items() if item["is_critical"]]


def validate_single_field_value(field: dict, value: Any) -> Any:
    """The cleaned value for one field, or raises InspectionFieldValueInvalid."""

    field_type = field["type"]
    label = field["key"]
    if field_type == "choice":
        allowed_values = {option["value"] for option in field["options"]}
        if value not in allowed_values:
            raise InspectionFieldValueInvalid(f"{label} must be one of: {', '.join(sorted(allowed_values))}")
        return value
    if field_type == "year_or_unknown":
        if value == UNKNOWN_FIELD_VALUE:
            return value
        latest_allowed_year = date.today().year + 1
        if isinstance(value, bool) or not isinstance(value, int) or not EARLIEST_ALLOWED_YEAR <= value <= latest_allowed_year:
            raise InspectionFieldValueInvalid(f"{label} must be a year between {EARLIEST_ALLOWED_YEAR} and {latest_allowed_year}, or \"unknown\"")
        return value
    if field_type == "date_or_unknown":
        if value == UNKNOWN_FIELD_VALUE:
            return value
        try:
            parsed_date = date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
        except ValueError:
            parsed_date = None
        if parsed_date is None or parsed_date.year < EARLIEST_ALLOWED_YEAR or parsed_date > date.today():
            raise InspectionFieldValueInvalid(f"{label} must be a past date (YYYY-MM-DD) or \"unknown\"")
        return parsed_date.isoformat()
    if field_type == "counter":
        if isinstance(value, bool) or not isinstance(value, int) or not field["minimum_count"] <= value <= field["maximum_count"]:
            raise InspectionFieldValueInvalid(f"{label} must be a whole number between {field['minimum_count']} and {field['maximum_count']}")
        return value
    maximum_length = MAXIMUM_TEXT_OR_UNKNOWN_LENGTH if field_type == "text_or_unknown" else MAXIMUM_FREE_TEXT_FIELD_LENGTH
    if not isinstance(value, str):
        raise InspectionFieldValueInvalid(f"{label} must be text")
    cleaned_text = strip_control_characters(value).strip()
    if not cleaned_text or len(cleaned_text) > maximum_length:
        raise InspectionFieldValueInvalid(f"{label} must be between 1 and {maximum_length} characters")
    return cleaned_text


def validate_item_field_value_changes(item: dict, field_value_changes: dict[str, Any]) -> dict[str, Any]:
    """Validates a partial update of an item's fields. A `None` value clears that field."""

    fields_by_key = {field["key"]: field for field in item["fields"]}
    cleaned_changes: dict[str, Any] = {}
    for field_key, value in field_value_changes.items():
        field = fields_by_key.get(field_key)
        if field is None:
            raise InspectionFieldValueInvalid(f"{item['key']} has no field {field_key!r}")
        cleaned_changes[field_key] = None if value is None else validate_single_field_value(field, value)
    return cleaned_changes


def visible_field_values(item: dict, stored_field_values: dict[str, Any]) -> dict[str, Any]:
    """Only the values of fields that currently apply: a follow-up whose condition
    no longer holds (Septic changed back to City) is left out of summaries."""

    visible_values: dict[str, Any] = {}
    for field in item["fields"]:
        show_when = field.get("show_when")
        if show_when and stored_field_values.get(show_when["field_key"]) != show_when["equals"]:
            continue
        if field["key"] in stored_field_values:
            visible_values[field["key"]] = stored_field_values[field["key"]]
    return visible_values


def strip_control_characters(text: str) -> str:
    """Drops ASCII control characters except newline and tab."""

    return "".join(character for character in text if character in "\n\t" or ord(character) >= 32 and ord(character) != 127)
