from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "tests" / "evals" / "context-prompts.json"


class ContextEvalDefinitionTest(unittest.TestCase):
    def test_fixed_context_eval_suite_is_complete(self) -> None:
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill"], "govern-openspec-context")
        self.assertEqual(
            [case["id"] for case in payload["cases"]],
            [
                "new-project-initialization",
                "simple-fix",
                "cross-session-resume",
                "parallel-changes",
                "implementation-deviates-from-spec",
            ],
        )
        self.assertGreaterEqual(len(payload["criteria"]), 5)
        for case in payload["cases"]:
            self.assertTrue(case["prompt"].strip())
            self.assertGreaterEqual(len(case["expected"]), 3)


if __name__ == "__main__":
    unittest.main()
