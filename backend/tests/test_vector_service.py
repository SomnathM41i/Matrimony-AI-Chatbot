import unittest
from unittest.mock import patch, MagicMock, call

from app.services.vector_service import (
    hash_id,
    _ensure_collection,
    upsert_batch,
    search_with_filters,
    delete_collection,
    COLLECTION_NAME,
    PAYLOAD_INDEXED_FIELDS,
)


class HashIdTests(unittest.TestCase):
    def test_hash_id_returns_positive_int(self):
        result = hash_id("MAT001")
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)
        self.assertLess(result, 2**63 - 1)

    def test_same_id_has_same_hash(self):
        self.assertEqual(hash_id("MAT001"), hash_id("MAT001"))

    def test_different_ids_have_different_hashes(self):
        self.assertNotEqual(hash_id("MAT001"), hash_id("MAT002"))

    def test_empty_string_hashes(self):
        result = hash_id("")
        self.assertIsInstance(result, int)


class EnsureCollectionTests(unittest.TestCase):
    @patch("app.services.vector_service.QdrantClient")
    def test_skips_if_exists(self, mock_client_class):
        mock_client = MagicMock()
        existing = MagicMock()
        existing.name = COLLECTION_NAME
        mock_client.get_collections.return_value.collections = [existing]
        _ensure_collection(mock_client)
        mock_client.create_collection.assert_not_called()

    @patch("app.services.vector_service.QdrantClient")
    def test_creates_if_not_exists(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get_collections.return_value.collections = []

        _ensure_collection(mock_client)

        mock_client.create_collection.assert_called_once()
        call_args = mock_client.create_collection.call_args
        self.assertEqual(call_args[1]["collection_name"], COLLECTION_NAME)

    @patch("app.services.vector_service.QdrantClient")
    def test_creates_payload_indexes(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get_collections.return_value.collections = []

        _ensure_collection(mock_client)

        expected_keyword_fields = PAYLOAD_INDEXED_FIELDS
        for field in expected_keyword_fields:
            mock_client.create_payload_index.assert_any_call(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_type=unittest.mock.ANY,
            )
        mock_client.create_payload_index.assert_any_call(
            collection_name=COLLECTION_NAME,
            field_name="Age",
            field_type=unittest.mock.ANY,
        )


class UpsertBatchTests(unittest.TestCase):
    @patch("app.services.vector_service.get_client")
    def test_empty_profiles_does_nothing(self, mock_get_client):
        upsert_batch([])
        mock_get_client.assert_not_called()

    @patch("app.services.vector_service.get_client")
    def test_upserts_profiles(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        profiles = [
            {"MatriID": "M1", "_vector": [0.1, 0.2], "Name": "A", "Age": 25},
            {"MatriID": "M2", "_vector": [0.3, 0.4], "Name": "B", "Age": 30},
        ]
        upsert_batch(profiles)

        mock_client.upsert.assert_called_once()
        points = mock_client.upsert.call_args[1]["points"]
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].payload["MatriID"], "M1")
        self.assertEqual(points[1].payload["MatriID"], "M2")

    @patch("app.services.vector_service.get_client")
    def test_retries_on_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.upsert.side_effect = [Exception("fail"), None]
        mock_get_client.return_value = mock_client

        profiles = [{"MatriID": "M1", "_vector": [0.1], "Name": "A"}]
        upsert_batch(profiles)

        self.assertEqual(mock_client.upsert.call_count, 2)

    @patch("app.services.vector_service.get_client")
    def test_gives_up_after_max_retries(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.upsert.side_effect = Exception("always fail")
        mock_get_client.return_value = mock_client

        profiles = [{"MatriID": "M1", "_vector": [0.1], "Name": "A"}]
        with self.assertRaises(Exception):
            upsert_batch(profiles)

        self.assertEqual(mock_client.upsert.call_count, 3)

    @patch("app.services.vector_service.get_client")
    def test_removes_private_keys_from_payload(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        profiles = [{"MatriID": "M1", "_vector": [0.1], "_internal": "secret", "Name": "A"}]
        upsert_batch(profiles)

        point = mock_client.upsert.call_args[1]["points"][0]
        self.assertNotIn("_vector", point.payload)
        self.assertNotIn("_internal", point.payload)
        self.assertIn("Name", point.payload)


class SearchWithFiltersTests(unittest.TestCase):
    @patch("app.services.vector_service.get_client")
    def test_search_no_filters(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = search_with_filters([0.1, 0.2])
        self.assertEqual(result, [])
        mock_client.query_points.assert_called_once()

    @patch("app.services.vector_service.get_client")
    def test_gender_filter_applied(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        search_with_filters([0.1], filters={"gender": "Female"})
        call_kwargs = mock_client.query_points.call_args[1]
        qfilter = call_kwargs["query_filter"]
        self.assertIsNotNone(qfilter)
        self.assertEqual(len(qfilter.must), 1)

    @patch("app.services.vector_service.get_client")
    def test_age_range_filter(self, mock_get_client):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.points = []
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        search_with_filters([0.1], filters={"age_min": 21, "age_max": 35})
        call_kwargs = mock_client.query_points.call_args[1]
        qfilter = call_kwargs["query_filter"]
        self.assertEqual(len(qfilter.must), 2)

    @patch("app.services.vector_service.get_client")
    def test_score_threshold_filters_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.score = 0.3
        mock_result.payload = {"Name": "Low Score"}
        mock_response = MagicMock()
        mock_response.points = [mock_result]
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = search_with_filters([0.1])
        self.assertEqual(result, [])

    @patch("app.services.vector_service.get_client")
    def test_high_score_results_returned(self, mock_get_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.score = 0.8
        mock_result.payload = {"Name": "High Score"}
        mock_response = MagicMock()
        mock_response.points = [mock_result]
        mock_client.query_points.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = search_with_filters([0.1])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Name"], "High Score")


class DeleteCollectionTests(unittest.TestCase):
    @patch("app.services.vector_service.get_client")
    def test_delete_collection_called(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        delete_collection()
        mock_client.delete_collection.assert_called_once_with(COLLECTION_NAME)


if __name__ == "__main__":
    unittest.main()
