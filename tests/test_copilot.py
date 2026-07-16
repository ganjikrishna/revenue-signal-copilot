import json
import unittest
from pathlib import Path

from copilot import analyze, parse_lead, score_lead


ROOT = Path(__file__).parents[1]


class CopilotTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "demo" / "lead.json").read_text(encoding="utf-8"))

    def test_demo_lead_is_high_priority(self):
        score, reasons = score_lead(parse_lead(self.data))
        self.assertEqual(score, 73)
        self.assertEqual(len(reasons), 5)

    def test_demo_analysis_is_deterministic_without_ai(self):
        result = analyze(self.data)
        self.assertEqual(result["mode"], "demo")
        self.assertIn("Peachtree Fitness Group", result["brief"])
        self.assertEqual(result["company"], "Peachtree Fitness Group")
        self.assertTrue(result["requires_human_review"])

    def test_invalid_numbers_are_rejected(self):
        self.data["employee_count"] = -1
        with self.assertRaises(ValueError):
            parse_lead(self.data)

    def test_input_text_is_length_limited(self):
        self.data["company"] = "x" * 500
        self.assertEqual(len(parse_lead(self.data).company), 120)


if __name__ == "__main__":
    unittest.main()
