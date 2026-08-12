from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "tests" / "evals" / "context-prompts.json"


class ForwardEvalCorpusTest(unittest.TestCase):
    def test_corpus_defines_all_required_fresh_session_cases(self) -> None:
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["skill"], "govern-openspec-context")
        self.assertEqual(
            [case["id"] for case in payload["cases"]],
            [
                "new-project-initialization",
                "direct-fix",
                "compaction-recovery",
                "new-session-recovery",
                "ambiguous-changes",
                "history-on-demand",
            ],
        )
        for case in payload["cases"]:
            self.assertIn("{skill_path}", case["prompt"])
            self.assertIn("{repo_path}", case["prompt"])
            self.assertGreaterEqual(len(case["expected"]), 4)

    def test_corpus_explicitly_forbids_handoff_behavior(self) -> None:
        serialized = json.dumps(payload := json.loads(EVALS.read_text(encoding="utf-8")))
        self.assertIn("no handoff", serialized.lower())
        self.assertNotIn("one writer", serialized.lower())
        self.assertEqual(len(payload["cases"]), 6)


if __name__ == "__main__":
    unittest.main()
