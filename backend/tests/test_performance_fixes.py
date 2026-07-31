"""Regression tests for the performance and stability fixes.

Covers the verified defects only:
  - vector-search fallback crashed with NameError: name 'db' is not defined
  - embedding model could be loaded more than once
  - schema context was re-rendered on every LLM call
"""
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import app.services.schema_discovery as schema_discovery


class VectorFallbackNoticeTests(unittest.IsolatedAsyncioTestCase):
    """The zero-result branch of the vector fallback must not raise."""

    async def test_format_notice_safe_accepts_the_five_arguments_used_by_callers(self):
        from app.services.db_query_service import _format_notice_safe

        with patch(
            "app.services.llm_service.format_db_notice",
            new=AsyncMock(return_value={"content": "translated notice"}),
        ):
            result = await _format_notice_safe(
                "show me profiles", "No matching profiles found.",
                [], MagicMock(), "No matching profiles found.",
            )
        self.assertEqual(result, "translated notice")

    async def test_notice_falls_back_to_plain_text_when_llm_fails(self):
        from app.services.db_query_service import _format_notice_safe

        with patch(
            "app.services.llm_service.format_db_notice",
            new=AsyncMock(side_effect=RuntimeError("provider down")),
        ):
            result = await _format_notice_safe(
                "show me profiles", "No matching profiles found.",
                [], MagicMock(), "fallback text",
            )
        self.assertEqual(result, "fallback text")

    def test_chat_service_methods_never_read_an_undefined_db_name(self):
        """Guards the exact bug: a bare `db` read inside a ChatService method.

        Inside ChatService the session is `self.db`. A bare `db` load raises
        NameError at runtime, which only surfaced in the rarely-hit
        zero-vector-result branch of the vector search fallback.
        `__init__(self, db)` legitimately binds `db` as a parameter, so only
        methods that do not declare it are checked.
        """
        import ast
        import inspect
        import textwrap
        import app.services.chat_service as chat_service

        source = textwrap.dedent(inspect.getsource(chat_service.ChatService))
        class_node = ast.parse(source).body[0]

        offenders = []
        for method in class_node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            bound = {a.arg for a in method.args.args + method.args.kwonlyargs}
            for node in ast.walk(method):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    bound.add(node.id)
            if "db" in bound:
                continue
            for node in ast.walk(method):
                if isinstance(node, ast.Name) and node.id == "db" and isinstance(node.ctx, ast.Load):
                    offenders.append(f"{method.name}() line {node.lineno}")

        self.assertEqual(offenders, [], f"bare `db` read in {offenders}; use self.db")


class EmbeddingSingletonTests(unittest.TestCase):
    def setUp(self):
        import app.services.embedding_service as embedding_service
        self.mod = embedding_service
        self.mod._model_instance = None
        self.mod._model_name = None

    def tearDown(self):
        self.mod._model_instance = None
        self.mod._model_name = None

    def test_model_is_constructed_only_once_across_threads(self):
        construction_count = []

        def _slow_construct(name):
            construction_count.append(name)
            # Widen the race window that the lock has to close.
            threading.Event().wait(0.05)
            return MagicMock()

        with patch.object(self.mod, "SentenceTransformer", side_effect=_slow_construct):
            results = []
            threads = [
                threading.Thread(target=lambda: results.append(self.mod.get_embedding_model()))
                for _ in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(len(construction_count), 1, "model was constructed more than once")
        self.assertEqual(len(set(id(r) for r in results)), 1, "callers got different instances")

    def test_default_model_matches_configured_model(self):
        """Callers that pass settings.EMBEDDING_MODEL and callers that rely on the
        default must resolve to the same cache key, otherwise the singleton
        evicts and reloads the model on alternating calls."""
        from app.config import settings
        self.assertEqual(self.mod.DEFAULT_MODEL, settings.EMBEDDING_MODEL)

    def test_configured_and_default_calls_share_one_instance(self):
        from app.config import settings

        with patch.object(self.mod, "SentenceTransformer", return_value=MagicMock()) as ctor:
            a = self.mod.get_embedding_model()
            b = self.mod.get_embedding_model(settings.EMBEDDING_MODEL)
        self.assertIs(a, b)
        self.assertEqual(ctor.call_count, 1)

    def test_warmup_swallows_load_errors(self):
        with patch.object(self.mod, "SentenceTransformer", side_effect=RuntimeError("no model")):
            self.mod.warmup_embedding_model()  # must not raise


class SchemaContextCacheTests(unittest.TestCase):
    SCHEMA = {
        "tables": {"register": [{"name": "MatriID"}, {"name": "Name"}, {"name": "City"}]},
        "lookup_values": {"caste": ["Maratha"]},
        "distinct_values": {
            "Caste": ["Maratha"], "City": ["Pune"], "Religion": ["Hindu"],
            "Education": ["BE"], "Occupation": ["Engineer"],
        },
    }

    def setUp(self):
        schema_discovery._schema_cache = dict(self.SCHEMA)
        schema_discovery._schema_context_cache = None

    def tearDown(self):
        schema_discovery._schema_cache = None
        schema_discovery._schema_context_cache = None

    def test_cached_output_is_identical_to_uncached_build(self):
        self.assertEqual(
            schema_discovery.build_schema_context(),
            schema_discovery._build_schema_context(),
        )

    def test_context_is_built_only_once(self):
        with patch.object(
            schema_discovery, "_build_schema_context", return_value="ctx"
        ) as build:
            for _ in range(5):
                schema_discovery.build_schema_context()
        self.assertEqual(build.call_count, 1)

    def test_refresh_cache_invalidates_rendered_context(self):
        schema_discovery.build_schema_context()
        self.assertIsNotNone(schema_discovery._schema_context_cache)

        with patch.object(schema_discovery, "_sync_fetch_all", return_value=dict(self.SCHEMA)):
            schema_discovery.refresh_cache()

        self.assertIsNone(
            schema_discovery._schema_context_cache,
            "stale rendered context survived a schema refresh",
        )


if __name__ == "__main__":
    unittest.main()
