import unittest
from unittest.mock import patch, MagicMock
from unittest import IsolatedAsyncioTestCase
import numpy as np

from app.services.embedding_service import (
    build_profile_document,
    embed_text,
    embed_batch,
    get_embedding_dimension,
    get_embedding_model,
    unload_embedding_model,
)


class BuildProfileDocumentTests(unittest.TestCase):
    def test_basic_profile(self):
        doc = build_profile_document({
            "Name": "Priya", "Age": "28", "Gender": "Female",
            "Caste": "Maratha", "City": "Pune",
        })
        self.assertIn("Name: Priya", doc)
        self.assertIn("Age: 28", doc)
        self.assertIn("Gender: Female", doc)
        self.assertIn("Caste: Maratha", doc)

    def test_excludes_sensitive_fields(self):
        doc = build_profile_document({
            "Name": "Test", "Password": "secret", "Mobile": "1234567890",
            "Photo1": "photo.jpg", "PhotoURL": "url", "Status": "Active",
        })
        self.assertNotIn("Password", doc)
        self.assertNotIn("Mobile", doc)
        self.assertNotIn("Photo1", doc)
        self.assertNotIn("Status", doc)

    def test_excludes_empty_values(self):
        doc = build_profile_document({
            "Name": "Test", "Caste": "", "City": None,
        })
        self.assertNotIn("Caste:", doc)
        self.assertNotIn("City:", doc)

    def test_excludes_nophoto_jpg(self):
        doc = build_profile_document({
            "Name": "Test", "Photo1": "nophoto.jpg",
            "Hobbies": "Reading",
        })
        self.assertNotIn("Photo1", doc)
        self.assertIn("Hobbies", doc)

    def test_joins_with_dot_space(self):
        doc = build_profile_document({
            "Name": "Priya", "Caste": "Maratha",
        })
        self.assertIn(". ", doc)


class EmbedTextTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.embedding_service.get_embedding_model")
    async def test_embed_text_returns_float_list(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_get_model.return_value = mock_model

        result = await embed_text("test text")
        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_model.encode.assert_called_once_with("test text", normalize_embeddings=True)

    @patch("app.services.embedding_service.get_embedding_model")
    async def test_embed_text_with_custom_model(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.5])
        mock_get_model.return_value = mock_model

        result = await embed_text("hello", model_name="custom-model")
        mock_get_model.assert_called_once_with("custom-model")


class EmbedBatchTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.embedding_service.get_embedding_model")
    async def test_embed_batch_returns_list_of_lists(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([
            [0.1, 0.2], [0.3, 0.4],
        ])
        mock_get_model.return_value = mock_model

        result = await embed_batch(["text1", "text2"])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], [0.1, 0.2])
        self.assertEqual(result[1], [0.3, 0.4])

    @patch("app.services.embedding_service.get_embedding_model")
    async def test_empty_batch_returns_empty_list(self, mock_get_model):
        result = await embed_batch([])
        self.assertEqual(result, [])
        mock_get_model.assert_not_called()


class GetEmbeddingDimensionTests(unittest.TestCase):
    @patch("app.services.embedding_service.get_embedding_model")
    def test_dimension_from_model(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 1024
        mock_get_model.return_value = mock_model

        result = get_embedding_dimension()
        self.assertEqual(result, 1024)


class UnloadEmbeddingModelTests(unittest.TestCase):
    def tearDown(self):
        unload_embedding_model()

    @patch("app.services.embedding_service.SentenceTransformer", return_value=MagicMock())
    def test_unload_releases_model(self, ctor):
        model = get_embedding_model()
        self.assertIsNotNone(model)
        unload_embedding_model()
        # Next call must reload, i.e. the instance must be rebuilt.
        with patch("app.services.embedding_service.SentenceTransformer", return_value=MagicMock()) as ctor2:
            second = get_embedding_model()
        self.assertIsNot(second, model)
        ctor2.assert_called_once()

    @patch("app.services.embedding_service.SentenceTransformer")
    def test_unload_when_not_loaded_is_safe(self, _ctor):
        unload_embedding_model()  # must not raise


if __name__ == "__main__":
    unittest.main()
