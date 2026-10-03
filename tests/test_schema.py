import json
from pathlib import Path
import unittest

from mlb_kaizen.validation.schema import HAS_JSONSCHEMA, validate_analysis_document


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema is not installed in this environment")
class SchemaTests(unittest.TestCase):
    def test_example_document_validates(self):
        root=Path(__file__).resolve().parents[1]
        payload=json.loads((root/"examples/analysis-input.manual.example.json").read_text())
        validate_analysis_document(payload, root/"docs/schemas/analysis-input.schema.json")

    def test_missing_league_average_is_rejected(self):
        root=Path(__file__).resolve().parents[1]
        payload=json.loads((root/"examples/analysis-input.manual.example.json").read_text())
        payload.pop("league_runs_per_team")
        with self.assertRaises(ValueError):
            validate_analysis_document(payload, root/"docs/schemas/analysis-input.schema.json")
