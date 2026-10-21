from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import experiment_recorder as recorder


ROOT = Path(__file__).resolve().parents[4]


@unittest.skipUnless(shutil.which("git"), "Git is required for tracking checks")
class ExperimentGitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "fixture"
        self.repo.mkdir()
        self.empty_excludes = self.root / "empty-excludes"
        self.empty_excludes.write_bytes(b"")
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "--quiet")
        (self.repo / ".gitignore").write_bytes((ROOT / ".gitignore").read_bytes())

    def git(self, *arguments):
        return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.excludesFile=" + str(self.empty_excludes), "-C", str(self.repo), *arguments], env=self.environment, capture_output=True, text=True)

    def write(self, relative, payload=b"fixture\n"):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def test_all_report_categories_are_trackable(self):
        relatives = ["reports/requirements/content-preservation.json", "reports/sdlc/orchestration-state.json", "reports/architecture/design-gate.json", "reports/addr/implementation-handoff.json", "reports/loop-control/retry-ledger.json", "reports/unit-test/coverage.json", "reports/integration-test/integration-test-plan.json", "reports/experiments/RUN-001/events.sqlite3", "reports/experiments/RUN-001/metrics.json", "reports/experiments/RUN-001/artifacts/fixture.json", "reports/evaluation/RUN-001/acceptance-test/execution-evidence.json", "reports/evaluation/RUN-001/external-evaluation.zip"]
        for relative in relatives:
            self.write(relative)
            self.assertEqual(1, self.git("check-ignore", "--no-index", "--quiet", relative).returncode, relative)
        added = self.git("add", "--", "reports")
        self.assertEqual(0, added.returncode, added.stderr)
        self.assertEqual(set(relatives), set(self.git("ls-files").stdout.splitlines()))

    def test_python_caches_still_ignored(self):
        for relative in ("reports/unit-test/__pycache__/helper.pyc", "reports/evaluation/result.pyc", ".github/skills/evaluation/scripts/__pycache__/helper.pyc"):
            self.write(relative)
            self.assertEqual(0, self.git("check-ignore", "--no-index", "--quiet", relative).returncode)

    def test_report_append_and_git_index_do_not_change_source_fingerprint(self):
        self.write("app.py", b"application source\n")
        before = recorder.source_fingerprint(self.repo)
        self.write("reports/experiments/RUN-001/metrics.json", b'{"status":"MEASURED"}\n')
        self.assertEqual(0, self.git("add", "--", "reports").returncode)
        self.assertEqual(before, recorder.source_fingerprint(self.repo))
        self.write("reports/experiments/RUN-001/metrics.json", b'{"status":"INVALID"}\n')
        self.assertEqual(before, recorder.source_fingerprint(self.repo))

    def test_source_changes_still_invalidate_measurement(self):
        self.write("app.py", b"first source\n")
        before = recorder.source_fingerprint(self.repo)
        self.write("app.py", b"changed source\n")
        self.assertNotEqual(before, recorder.source_fingerprint(self.repo))

    def test_actual_journal_can_be_staged_without_changing_events(self):
        recorder.append(self.repo, "RUN-001", "start", "RUN_STARTED", {"condition_id": "fixture"})
        before = recorder.load_events(self.repo, "RUN-001")
        self.assertEqual(0, self.git("add", "--", "reports").returncode)
        self.assertEqual(before, recorder.load_events(self.repo, "RUN-001"))
        self.assertIn("reports/experiments/RUN-001/events.sqlite3", self.git("ls-files").stdout)

    def test_documentation_retains_external_acceptance_boundary(self):
        guide = (ROOT / "docs/ai-sdlc/experiment-git-workflow.md").read_text(encoding="utf-8")
        self.assertIn("開発中にリポジトリへ入れない", guide)
        self.assertIn("Gitブランチはアクセス権の隔離ではない", guide)
        self.assertIn("mainへマージしない", guide)
        self.assertIn("外部tests一式を自動でコピーする処理ではない", guide)


if __name__ == "__main__":
    unittest.main()
