"""JSON Schema validation for Analyst Mode documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    Draft202012Validator = None
    FormatChecker = None

HAS_JSONSCHEMA = Draft202012Validator is not None


def validate_analysis_document(payload: dict[str, Any], schema_path: Path) -> None:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema is required to validate analysis documents")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "root"
        raise ValueError(f"invalid analysis input at {location}: {errors[0].message}")
