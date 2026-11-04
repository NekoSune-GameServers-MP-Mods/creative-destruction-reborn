"""Dependency-aware image selection must not rebuild unrelated service images."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from select_docker_services import selected, SERVICES


class SelectImagesTests(unittest.TestCase):
    def test_dedicated_branch_only_owns_its_image(self):
        cases = {
            "server": "game-server", "account": "account-api",
            "staff": "staff", "cluster-api": "cluster-api",
            "cluster-agent": "cluster-agent",
        }
        for branch, target in cases.items():
            with self.subTest(branch=branch):
                self.assertEqual(selected(["Dockerfile", "reborn/server/accounts.py"],
                                          "push", branch), [target])

    def test_pr_and_main_rebuild_only_affected_images(self):
        for event, branch in (("pull_request", "account"), ("push", "main")):
            self.assertEqual(selected(["reborn/server/accounts.py"], event, branch), ["account-api"])
            self.assertEqual(selected(["reborn/server/offline_server.py"], event, branch), ["game-server"])
            self.assertEqual(selected(["reborn/server/staff_dashboard.py"], event, branch), ["staff"])
            self.assertEqual(selected(["reborn/server/cluster_api.py"], event, branch), ["cluster-api"])
            self.assertEqual(selected(["reborn/server/cluster_agent.py"], event, branch), ["cluster-agent"])
            self.assertEqual(selected(["reborn/server/player_profiles.py"], event, branch), ["account-api"])
            self.assertEqual(selected(["docs/README.md"], event, branch), [])

    def test_shared_build_changes_rebuild_all(self):
        for p in ("Dockerfile", ".dockerignore", ".github/workflows/docker-publish.yml",
                  "scripts/select_docker_services.py"):
            self.assertEqual(selected([p], "pull_request", "server"), list(SERVICES))

    def test_compose_dependencies(self):
        self.assertEqual(selected(["compose.yaml"], "push", "main"), ["game-server"])
        self.assertEqual(selected(["compose.cluster-control.yaml"], "push", "main"),
                         ["account-api", "cluster-api"])
        self.assertEqual(selected(["compose.vps.yaml"], "push", "main"),
                         ["game-server", "account-api", "staff"])

    def test_manual_override(self):
        self.assertEqual(selected([], "workflow_dispatch", "server", "account-api"), ["account-api"])
        self.assertEqual(selected([], "workflow_dispatch", "main", "all"), list(SERVICES))
        with self.assertRaises(ValueError):
            selected([], "workflow_dispatch", "main", "unrecognised")


if __name__ == "__main__":
    unittest.main()
