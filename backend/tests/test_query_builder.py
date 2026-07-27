import unittest
from app.services.query_builder import (
    build_profile_query,
    build_detail_query,
    _resolve_columns,
    FIELD_MAP,
    COLUMN_GROUPS,
    DETAIL_COLUMNS,
)


class BuildProfileQueryTests(unittest.TestCase):
    def test_empty_filters_returns_simple_query(self):
        sql, params = build_profile_query({})
        self.assertIn("WHERE", sql)
        self.assertIn("Status", sql)
        self.assertNotIn("AND", sql.split("WHERE")[1].strip())
        self.assertEqual(params[-1], 10)

    def test_gender_filter_adds_condition(self):
        sql, params = build_profile_query({"gender": "Female"})
        self.assertIn("LOWER(Gender) = LOWER(?)", sql)
        self.assertIn("Female", params)

    def test_city_filter_uses_like(self):
        sql, params = build_profile_query({"city": "Pune"})
        self.assertIn("LOWER(City) LIKE", sql)
        self.assertIn("%Pune%", params)

    def test_city_supersedes_dist_and_state(self):
        sql, params = build_profile_query({"city": "Mumbai", "dist": "Thane"})
        self.assertEqual(sql.count("LOWER(City) LIKE"), 1)
        self.assertEqual(sql.count("LOWER(Dist) LIKE"), 1)

    def test_age_range_adds_both_conditions(self):
        sql, params = build_profile_query({"age_min": 21, "age_max": 35})
        self.assertIn("CAST(Age AS SIGNED) >= ?", sql)
        self.assertIn("CAST(Age AS SIGNED) <= ?", sql)
        self.assertIn(21, params)
        self.assertIn(35, params)

    def test_education_and_occupation_use_like(self):
        sql, params = build_profile_query({"education": "engineer", "occupation": "software"})
        self.assertIn("LOWER(Education) LIKE", sql)
        self.assertIn("LOWER(Occupation) LIKE", sql)

    def test_subcaste_adds_like_on_caste(self):
        sql, params = build_profile_query({"subcaste": "kuli"})
        self.assertIn("LOWER(Caste) LIKE LOWER(?)", sql)
        self.assertIn("%kuli%", params)

    def test_custom_limit_applied(self):
        sql, params = build_profile_query({"gender": "Male"}, limit=5)
        self.assertEqual(params[-1], 5)

    def test_limit_passed_through(self):
        sql, params = build_profile_query({"gender": "Female"}, limit=999)
        self.assertEqual(params[-1], 999)

    def test_multiple_filters_all_combined(self):
        filters = {
            "gender": "Female", "caste": "Maratha", "city": "Pune",
            "age_min": 21, "age_max": 30, "religion": "Hindu",
            "marital_status": "Never Married",
        }
        sql, params = build_profile_query(filters)
        where_clause = sql.split("WHERE")[1].split("ORDER BY")[0]
        conditions = [c.strip() for c in where_clause.split("AND")]
        self.assertGreaterEqual(len(conditions), 7)
        self.assertIn("LOWER(Gender) = LOWER(?)", sql)

    def test_order_by_regdate_desc(self):
        sql, _ = build_profile_query({"gender": "Male"})
        self.assertIn("ORDER BY Regdate DESC", sql)

    def test_all_field_map_keys_generate_conditions(self):
        filters = {}
        for key, column in FIELD_MAP.items():
            if key in ("gothram",):
                continue
            filters[key] = "test"
        sql, _ = build_profile_query(filters)
        for key, column in FIELD_MAP.items():
            if key in ("city", "dist", "state", "subcaste", "education", "occupation",
                       "age_min", "age_max", "income_min", "income_max",
                       "height_min", "height_max", "gothram"):
                continue
            self.assertIn(f"LOWER({column}) = LOWER(?)", sql)


class BuildDetailQueryTests(unittest.TestCase):
    def test_by_matri_id(self):
        sql, params = build_detail_query(matri_id="MAT001")
        self.assertIn("MatriID = ?", sql)
        self.assertIn("MAT001", params)

    def test_by_name(self):
        sql, params = build_detail_query(name="Priya")
        self.assertIn("LOWER(Name) LIKE LOWER(?)", sql)
        self.assertIn("%Priya%", params)

    def test_by_both_matri_id_and_name(self):
        sql, params = build_detail_query(matri_id="M1", name="Test")
        self.assertIn("MatriID = ?", sql)
        self.assertIn("LOWER(Name) LIKE", sql)

    def test_default_fields_first_seven_columns(self):
        sql, _ = build_detail_query(matri_id="M1")
        for col in DETAIL_COLUMNS[:7]:
            self.assertIn(col, sql)

    def test_specific_field_group(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["education"])
        self.assertIn("Education", sql)
        self.assertIn("EducationDetails", sql)

    def test_multiple_field_groups(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["family", "income"])
        self.assertIn("Annualincome", sql)
        self.assertIn("Fathername", sql)
        self.assertIn("Mothersname", sql)

    def test_photo_group_adds_photo1(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["photo"])
        self.assertIn("Photo1", sql)

    def test_contact_group_adds_mobile(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["contact"])
        self.assertIn("Mobile", sql)

    def test_all_group_includes_everything(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["all"])
        for col in DETAIL_COLUMNS:
            self.assertIn(col, sql)
        self.assertIn("Photo1", sql)
        self.assertIn("Mobile", sql)

    def test_invalid_field_ignored(self):
        sql, _ = build_detail_query(matri_id="M1", fields=["education", "nonexistent"])
        self.assertIn("Education", sql)
        self.assertNotIn("nonexistent", sql)

    def test_limit_param(self):
        sql, params = build_detail_query(matri_id="M1", limit=5)
        self.assertEqual(params[-1], 5)

    def test_active_status_filter_always_present(self):
        sql, _ = build_detail_query(matri_id="M1")
        self.assertIn("LOWER(Status) = LOWER('Active')", sql)


class ResolveColumnsTests(unittest.TestCase):
    def test_none_fields_returns_first_seven(self):
        result = _resolve_columns(None)
        self.assertEqual(result, DETAIL_COLUMNS[:7])

    def test_empty_list_returns_first_seven(self):
        result = _resolve_columns([])
        self.assertEqual(result, DETAIL_COLUMNS[:7])

    def test_known_field_group(self):
        result = _resolve_columns(["manglik"])
        self.assertEqual(result, ["Manglik"])

    def test_field_map_key_works(self):
        result = _resolve_columns(["gotra"])
        self.assertEqual(result, ["Gothram"])

    def test_deduplicates_columns(self):
        result = _resolve_columns(["gotra", "gothram"])
        self.assertEqual(result, ["Gothram"])


class FieldMapConsistencyTests(unittest.TestCase):
    def test_column_groups_use_known_columns(self):
        detail_set = set(DETAIL_COLUMNS) | {"Photo1", "Mobile"}
        for group_name, cols in COLUMN_GROUPS.items():
            if group_name == "all":
                continue
            for col in cols:
                self.assertIn(col, detail_set, f"{col} from group {group_name} not in DETAIL_COLUMNS")

    def test_all_group_includes_all_detail_columns_plus_extras(self):
        all_cols = COLUMN_GROUPS["all"]
        for col in DETAIL_COLUMNS:
            self.assertIn(col, all_cols)
        self.assertIn("Photo1", all_cols)
        self.assertIn("Mobile", all_cols)


if __name__ == "__main__":
    unittest.main()
