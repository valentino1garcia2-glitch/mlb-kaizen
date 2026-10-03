import json
import logging
import unittest

from mlb_kaizen.observability.logging import (
    JsonFormatter,
    SensitiveFieldError,
    _reject_sensitive_names,
    configure_logging,
    log_event,
)


class LoggingTests(unittest.TestCase):
    def test_log_event_emits_one_json_object_with_whitelisted_fields(self) -> None:
        logger = logging.getLogger("mlb_kaizen.test.http")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.Handler()
        handler.setFormatter(JsonFormatter())
        records: list[str] = []
        handler.emit = lambda record: records.append(handler.format(record))  # type: ignore[method-assign]
        logger.addHandler(handler)

        log_event(
            logger,
            "provider request failed on attempt 1/3",
            level=logging.WARNING,
            operation="http_get_json",
            source="https://statsapi.mlb.com/api/v1/schedule",
        )

        self.assertEqual(len(records), 1)
        payload = json.loads(records[0])
        self.assertEqual(payload["level"], "WARNING")
        self.assertEqual(payload["module"], "mlb_kaizen.test.http")
        self.assertEqual(payload["operation"], "http_get_json")
        self.assertEqual(payload["source"], "https://statsapi.mlb.com/api/v1/schedule")
        self.assertEqual(payload["message"], "provider request failed on attempt 1/3")
        self.assertIn("timestamp", payload)
        self.assertNotIn("game_id", payload)

    def test_log_event_omits_unset_fields_rather_than_null(self) -> None:
        logger = logging.getLogger("mlb_kaizen.test.minimal")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        handler = logging.Handler()
        handler.setFormatter(JsonFormatter())
        records: list[str] = []
        handler.emit = lambda record: records.append(handler.format(record))  # type: ignore[method-assign]
        logger.addHandler(handler)

        log_event(logger, "schema initialised", operation="init_db")

        payload = json.loads(records[0])
        self.assertEqual(payload["operation"], "init_db")
        self.assertNotIn("source", payload)
        self.assertNotIn("game_id", payload)
        self.assertNotIn("model_version", payload)
        self.assertNotIn("feature_version", payload)

    def test_log_event_signature_rejects_arbitrary_keyword_fields(self) -> None:
        logger = logging.getLogger("mlb_kaizen.test.secrets")

        # The keyword-only signature is the primary guarantee: there is no
        # **kwargs path that could smuggle a field like api_key into a log line.
        with self.assertRaises(TypeError):
            log_event(logger, "would-be leak", api_key="do-not-log-this")  # type: ignore[call-arg]

    def test_reject_sensitive_names_guards_future_kwargs_style_calls(self) -> None:
        # If log_event is ever loosened to accept **kwargs, this internal guard
        # is what must still catch a credential-shaped field name.
        with self.assertRaises(SensitiveFieldError):
            _reject_sensitive_names(("api_key",))
        with self.assertRaises(SensitiveFieldError):
            _reject_sensitive_names(("auth_token",))
        _reject_sensitive_names(("operation", "source", "game_id"))  # does not raise

    def test_configure_logging_is_idempotent(self) -> None:
        configure_logging()
        configure_logging()
        root = logging.getLogger()
        json_handlers = [h for h in root.handlers if isinstance(h.formatter, JsonFormatter)]
        self.assertEqual(len(json_handlers), 1)


if __name__ == "__main__":
    unittest.main()
