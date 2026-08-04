import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

from app.services.indexing_service import (
    _fetch_all_active_profile_rows,
    fetch_all_active_profiles,
    reindex_all,
)


class FetchProfilesTests(unittest.TestCase):
    @patch("app.services.indexing_service.safe_query")
    def test_fetch_all_active_profile_rows(self, mock_safe_query):
        mock_safe_query.return_value = [{"MatriID": "M1"}, {"MatriID": "M2"}]
        result = _fetch_all_active_profile_rows()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["MatriID"], "M1")
        mock_safe_query.assert_called_once()
        self.assertIn("SELECT", mock_safe_query.call_args[0][0])
        self.assertIn("Active", mock_safe_query.call_args[0][0])

    @patch("app.services.indexing_service._fetch_all_active_profile_rows")
    def test_fetch_all_active_profiles(self, mock_fetch):
        mock_fetch.return_value = [{"MatriID": "M1"}]
        result = asyncio.run(fetch_all_active_profiles())
        self.assertEqual(len(result), 1)


class ReindexAllTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.indexing_service.safe_query")
    @patch("app.services.vector_service.get_client")
    @patch("app.services.db_query_service.add_photo_url")
    @patch("app.services.db_query_service.sanitize_rows")
    @patch("app.services.indexing_service.build_profile_document")
    @patch("app.services.indexing_service.embed_batch")
    @patch("app.services.indexing_service.upsert_batch")
    @patch("app.services.indexing_service.delete_collection")
    @patch("app.services.vector_service._ensure_collection")
    async def test_reindex_full_flow(
        self, mock_ensure, mock_delete, mock_upsert, mock_embed,
        mock_build_doc, mock_sanitize, mock_photo_url, mock_get_client, mock_safe_query,
    ):
        mock_safe_query.return_value = [{"MatriID": "M1", "Name": "Test"}]
        mock_sanitize.return_value = [{"MatriID": "M1", "Name": "Test"}]
        mock_build_doc.return_value = "Name: Test"
        mock_embed.return_value = [[0.1, 0.2]]

        mock_client = MagicMock()
        existing = MagicMock()
        existing.name = "profiles"
        mock_client.get_collections.return_value.collections = [existing]
        mock_get_client.return_value = mock_client

        await reindex_all()

        mock_delete.assert_called_once()
        mock_ensure.assert_called_once()
        mock_upsert.assert_called_once()

    @patch("app.services.indexing_service.safe_query")
    async def test_reindex_no_profiles(self, mock_safe_query):
        mock_safe_query.return_value = []
        result = await reindex_all()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
