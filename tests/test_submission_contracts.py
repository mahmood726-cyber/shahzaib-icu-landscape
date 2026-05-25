import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "e156-submission" / "config.json"


class SubmissionContracts(unittest.TestCase):
    def test_submission_config_uses_repo_relative_root(self) -> None:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["path"], "..")
        resolved_root = (CONFIG_PATH.parent / payload["path"]).resolve()
        self.assertEqual(resolved_root, REPO_ROOT.resolve())

    def test_reviewer_docs_do_not_reference_machine_local_repo_paths(self) -> None:
        doc_paths = [
            REPO_ROOT / "F1000_Submission_Checklist_RealReview.md",
            REPO_ROOT / "F1000_Software_Tool_Article.md",
            REPO_ROOT / "F1000_Reviewer_Rerun_Manifest.md",
        ]

        for path in doc_paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(r"C:\Models\shahzaib-icu-landscape", text)
            self.assertNotIn(r"C:\HTML apps\reviewer Report.txt", text)


if __name__ == "__main__":
    unittest.main()
