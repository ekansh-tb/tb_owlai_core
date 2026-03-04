import frappe
from frappe.tests import IntegrationTestCase


class TestEntityResolver(IntegrationTestCase):
    def test_empty_input(self):
        from tb_owlai_core.intelligence.entity_resolver import resolve_entities
        result = resolve_entities("")
        self.assertEqual(result, [])

    def test_none_input(self):
        from tb_owlai_core.intelligence.entity_resolver import resolve_entities
        result = resolve_entities(None)
        self.assertEqual(result, [])

    def test_noise_only_input(self):
        from tb_owlai_core.intelligence.entity_resolver import resolve_entities
        result = resolve_entities("show the balance")
        # After removing noise words, no candidates should remain
        self.assertIsInstance(result, list)

    def test_special_characters_sanitized(self):
        from tb_owlai_core.intelligence.entity_resolver import resolve_entities
        result = resolve_entities("'; DROP TABLE tabCustomer; --")
        self.assertIsInstance(result, list)

    def test_extract_candidates(self):
        from tb_owlai_core.intelligence.entity_resolver import _extract_candidates
        candidates = _extract_candidates("Ram Kumar balance")
        self.assertIn("Ram", candidates)
        self.assertIn("Kumar", candidates)
        self.assertIn("Ram Kumar", candidates)
        # "balance" should be filtered as noise
        self.assertNotIn("balance", candidates)

    def test_calculate_score_exact(self):
        from tb_owlai_core.intelligence.entity_resolver import _calculate_score
        score = _calculate_score("Ram Kumar", "Ram Kumar", "Ram Kumar")
        self.assertEqual(score, 1.0)

    def test_calculate_score_starts_with(self):
        from tb_owlai_core.intelligence.entity_resolver import _calculate_score
        score = _calculate_score("Ram", "Ram Kumar", "Ram Kumar")
        self.assertEqual(score, 0.7)

    def test_calculate_score_contains(self):
        from tb_owlai_core.intelligence.entity_resolver import _calculate_score
        score = _calculate_score("Kumar", "Ram Kumar", "Ram Kumar")
        self.assertEqual(score, 0.5)

    def test_entity_context_string(self):
        from tb_owlai_core.intelligence.entity_resolver import get_entity_context_string
        result = get_entity_context_string("nonexistent_entity_xyz_12345")
        self.assertIsInstance(result, str)

    def test_sanitize_input(self):
        from tb_owlai_core.intelligence.entity_resolver import _sanitize_input
        result = _sanitize_input("test'; DROP TABLE --")
        self.assertNotIn("'", result)
        self.assertNotIn(";", result)
