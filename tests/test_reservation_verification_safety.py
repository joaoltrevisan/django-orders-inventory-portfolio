"""Reject unsafe HTTP fixture targets before any time-travel or API writes."""

import json
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.verify_reservations import review_url


class ReservationVerificationSafetyTests(SimpleTestCase):
    def test_wrong_database_role_and_historical_data_are_refused(self):
        for identity in [
            ["olist_case_study", "olist_api", 0],
            ["olist_demo", "olist_owner", 0],
            ["olist_demo", "olist_api", 1],
        ]:
            with (
                self.subTest(identity=identity),
                patch(
                    "scripts.verify_reservations.compose_output", return_value=json.dumps(identity)
                ) as mocked,
                self.assertRaises(ValueError),
            ):
                review_url(["docker", "compose"])
            self.assertEqual(mocked.call_count, 1)

    def test_external_or_ambiguous_bindings_are_refused(self):
        for binding in ["0.0.0.0:18027", "[::1]:18027", "127.0.0.1:18027\n127.0.0.1:18028"]:
            with (
                self.subTest(binding=binding),
                patch(
                    "scripts.verify_reservations.compose_output",
                    side_effect=[json.dumps(["olist_demo", "olist_api", 0]), binding],
                ),
                self.assertRaises(ValueError),
            ):
                review_url(["docker", "compose"])

    def test_confirmed_private_source_free_target_is_accepted(self):
        with patch(
            "scripts.verify_reservations.compose_output",
            side_effect=[json.dumps(["olist_demo", "olist_api", 0]), "127.0.0.1:18027"],
        ):
            self.assertEqual(review_url(["docker", "compose"]), "http://127.0.0.1:18027")
