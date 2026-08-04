"""P8: unit tests for the deterministic zero-LLM DB formatting helpers that
the CF-5/CF-6 routes rely on but had no direct coverage.

Covers db_query_service: add_photo_url, format_filter_summary,
format_no_matches_notice, format_profile_results_markdown; and matri_service's
_photo_url.
"""
import unittest

from app.config import settings
from app.services.db_query_service import (
    add_photo_url,
    format_filter_summary,
    format_no_matches_notice,
    format_profile_results_markdown,
)
from app.services.matri_service import _photo_url

BASE = settings.PHOTO_BASE_URL.rstrip("/")


class PhotoUrlTests(unittest.TestCase):
    def test_builds_url_from_config_base(self):
        row = {"Photo1": "uploads/photo1.jpg"}
        add_photo_url(row)
        self.assertEqual(row["PhotoURL"], f"{BASE}/uploads/photo1.jpg")

    def test_strips_leading_slash(self):
        row = {"Photo1": "/2023_07_11_01_31_0431.jpg"}
        add_photo_url(row)
        self.assertEqual(row["PhotoURL"], f"{BASE}/2023_07_11_01_31_0431.jpg")

    def test_nophoto_becomes_empty(self):
        row = {"Photo1": "nophoto.jpg"}
        add_photo_url(row)
        self.assertEqual(row["PhotoURL"], "")

    def test_missing_photo_becomes_empty(self):
        row = {"Name": "A"}
        add_photo_url(row)
        self.assertEqual(row["PhotoURL"], "")

    def test_matri_photo_url_ignores_nophoto(self):
        self.assertEqual(_photo_url("nophoto.jpg"), "")
        self.assertEqual(_photo_url(""), "")
        self.assertEqual(_photo_url("photos/a.jpg"), f"{BASE}/photos/a.jpg")


class FilterSummaryTests(unittest.TestCase):
    def test_age_range_and_gender(self):
        text = format_filter_summary({"age_min": "21", "age_max": "28", "gender": "Female"})
        self.assertIn("वय 21 - 28 वर्षे", text)
        self.assertIn("मुलगी", text)

    def test_male_gender_word(self):
        self.assertIn("मुलगा", format_filter_summary({"gender": "Male"}))

    def test_marathi_filter_labels(self):
        text = format_filter_summary({
            "marital_status": "Unmarried",
            "religion": "Hindu",
            "caste": "Brahmin",
            "manglik": "No",
            "complexion": "Fair",
            "city": "Pune",
            "occupation": "Engineer",
        })
        self.assertIn("वैवाहिक स्थिती: कधीही लग्न न केलेले", text)
        self.assertIn("धर्म: Hindu", text)
        self.assertIn("जात: Brahmin", text)
        self.assertIn("मांगलिक: अमांगलिक", text)
        self.assertIn("रंग/वर्ण: गोरा", text)
        self.assertIn("स्थान: Pune", text)
        self.assertIn("व्यवसाय: Engineer", text)

    def test_empty_filters_returns_empty(self):
        self.assertEqual(format_filter_summary({}), "")


class NoMatchesNoticeTests(unittest.TestCase):
    def test_includes_filter_summary_and_advice(self):
        text = format_no_matches_notice({"city": "Pune", "gender": "Female"})
        self.assertIn("सध्या या निकषांना जुळणारी प्रोफाइल सापडली नाही:", text)
        self.assertIn("स्थान: Pune", text)
        self.assertIn("सल्ला:", text)
        self.assertIn("सैल निकषांनी पर्याय दाखव", text)

    def test_no_filters_still_offers_advice(self):
        text = format_no_matches_notice({})
        self.assertIn("सध्या या निकषांना जुळणारी प्रोफाइल सापडली नाही.", text)
        self.assertIn("सल्ला:", text)


class ProfileResultsMarkdownTests(unittest.TestCase):
    def test_empty_rows_returns_empty_string(self):
        self.assertEqual(format_profile_results_markdown({}, {"rows": [], "row_count": 0}), "")

    def test_count_header_with_context(self):
        text = format_profile_results_markdown(
            {"city": "Pune", "gender": "Female"},
            {"rows": [{"Name": "A"}], "row_count": 1},
        )
        self.assertIn("येथे Pune मधील मुलींची 1 प्रोफाइल आहेत:", text)

    def test_photo_card_and_details(self):
        text = format_profile_results_markdown(
            {},
            {"rows": [{"Name": "Anita", "Age": "27", "Gender": "Female", "City": "Pune",
                       "Caste": "Maratha", "Religion": "Hindu", "Occupation": "Engineer",
                       "Education": "BE", "PhotoURL": f"{BASE}/a.jpg"}]},
        )
        self.assertIn(f"![Anita]({BASE}/a.jpg)", text)
        self.assertIn("27, Female, Pune", text)
        self.assertIn("Maratha, Hindu, Engineer, BE", text)

    def test_no_photo_uses_placeholder_url(self):
        text = format_profile_results_markdown(
            {},
            {"rows": [{"Name": "Anita", "Age": "27", "PhotoURL": ""}]},
        )
        self.assertIn(f"![Anita]({BASE}/nophoto.jpg) 27", text)


if __name__ == "__main__":
    unittest.main()
