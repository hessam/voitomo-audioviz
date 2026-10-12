"""Offline deploy checks against throwaway git repos; never touches a server."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "scripts" / "deploy.sh"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True,
                          capture_output=True, text=True).stdout.strip()


class TestDeployScript(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.origin = tmp / "origin"
        self.deploy_dir = tmp / "deploy"
        self.origin.mkdir()
        git(self.origin, "init", "-q", "-b", "main")
        (self.origin / ".gitignore").write_text(".env\n.deployed_sha\n")
        (self.origin / "app.txt").write_text("v1\n")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-q", "-m", "v1")
        self.sha_a = git(self.origin, "rev-parse", "HEAD")
        (self.origin / "app.txt").write_text("v2\n")
        git(self.origin, "commit", "-qam", "v2")
        self.sha_b = git(self.origin, "rev-parse", "HEAD")
        git(tmp, "clone", "-q", str(self.origin), str(self.deploy_dir))
        git(self.deploy_dir, "checkout", "-q", "--detach", self.sha_a)
        (self.deploy_dir / ".env").write_text("SECRET=keep-me\n")

    def run_deploy(self, sha, health="true"):
        env = {
            **os.environ,
            "DEPLOY_DIR": str(self.deploy_dir),
            "RESTART_CMD": "true",
            "HEALTH_CMD": health,
            "HEALTH_WAIT": "0",
        }
        return subprocess.run(["bash", str(DEPLOY), sha], env=env,
                              capture_output=True, text=True)

    def test_deploys_commit_and_records_sha(self):
        result = self.run_deploy(self.sha_b)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.deploy_dir, "rev-parse", "HEAD"), self.sha_b)
        self.assertEqual((self.deploy_dir / ".deployed_sha").read_text().strip(), self.sha_b)

    def test_keeps_ignored_env_file(self):
        self.run_deploy(self.sha_b)
        self.assertEqual((self.deploy_dir / ".env").read_text(), "SECRET=keep-me\n")

    def test_refuses_drift_in_tracked_files(self):
        (self.deploy_dir / "app.txt").write_text("hand edit\n")
        result = self.run_deploy(self.sha_b)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(self.deploy_dir, "rev-parse", "HEAD"), self.sha_a)

    def test_refuses_commit_not_on_main(self):
        git(self.origin, "checkout", "-q", "-b", "side", self.sha_a)
        (self.origin / "side.txt").write_text("x\n")
        git(self.origin, "add", "-A")
        git(self.origin, "commit", "-qm", "side")
        side = git(self.origin, "rev-parse", "HEAD")
        git(self.origin, "checkout", "-q", "main")
        git(self.deploy_dir, "fetch", "-q", str(self.origin), "side")
        result = self.run_deploy(side)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not on origin/main", result.stderr)

    def test_failed_health_check_rolls_back(self):
        # Health passes only while HEAD is sha_a, so deploying sha_b must fail.
        health = f'test "$(git rev-parse HEAD)" = "{self.sha_a}"'
        result = self.run_deploy(self.sha_b, health=health)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rolled back", result.stderr)
        self.assertEqual(git(self.deploy_dir, "rev-parse", "HEAD"), self.sha_a)
        self.assertFalse((self.deploy_dir / ".deployed_sha").exists())


if __name__ == "__main__":
    unittest.main()
