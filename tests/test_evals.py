from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "tests" / "evals" / "context-prompts.json"


class ForwardEvalCorpusTest(unittest.TestCase):
    def test_corpus_defines_required_workbuddy_cases(self) -> None:
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 3)
        self.assertEqual(payload["skill"], "govern-openspec-context")
        self.assertEqual(
            [case["id"] for case in payload["cases"]],
            [
                "new-project-initialization",
                "explicit-codex-override",
                "direct-fix",
                "compaction-recovery",
                "ambiguous-changes",
                "history-on-demand",
            ],
        )
        for case in payload["cases"]:
            self.assertIn("{skill_path}", case["prompt"])
            self.assertIn("{repo_path}", case["prompt"])
            self.assertGreaterEqual(len(case["expected"]), 4)

    def test_corpus_uses_workbuddy_invocation_and_forbids_handoffs(self) -> None:
        serialized = json.dumps(
            json.loads(EVALS.read_text(encoding="utf-8")), ensure_ascii=False
        )
        self.assertIn("/govern-openspec-context", serialized)
        self.assertNotIn("$govern-openspec-context", serialized)
        self.assertIn("no handoff", serialized.lower())


if __name__ == "__main__":
    unittest.main()
