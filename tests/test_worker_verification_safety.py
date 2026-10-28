"""Refuse existing or populated targets before preparing a worker fixture."""

from django.test import SimpleTestCase

from scripts.verify_expiry_worker import validate_target


class WorkerVerificationSafetyTests(SimpleTestCase):
    def test_wrong_database_role_history_or_seed_shape_is_refused(self):
        baseline = ["olist_demo", "olist_api", 0, 4, 5, 3, 10]
        for index, replacement in [
            (0, "olist_case_study"),
            (1, "olist_owner"),
            (2, 1),
            (3, 5),
            (4, 6),
            (5, 4),
            (6, 11),
        ]:
            candidate = baseline.copy()
            candidate[index] = replacement
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_target(candidate, "")

    def test_existing_worker_container_is_never_taken_over(self):
        with self.assertRaises(ValueError):
            validate_target(["olist_demo", "olist_api", 0, 4, 5, 3, 10], "existing-container-id")

    def test_fresh_source_free_fixture_target_is_accepted(self):
        validate_target(["olist_demo", "olist_api", 0, 4, 5, 3, 10], "")
