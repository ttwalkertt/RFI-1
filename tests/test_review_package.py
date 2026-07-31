from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.review_package import build_package, resolve_identity, verify_package


class ReviewPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "review@example.invalid")
        self.git("config", "user.name", "Review Test")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "base.txt")
        self.git("commit", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-b", "topic")
        (self.root / "implementation.txt").write_text(
            "committed implementation\n", encoding="utf-8"
        )
        (self.root / "implementation with spaces.txt").write_text(
            "space-safe implementation\n", encoding="utf-8"
        )
        self.git("add", "implementation.txt", "implementation with spaces.txt")
        self.git("commit", "-m", "implementation")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.source = self.root / "review.md"
        self.source.write_text("review\n", encoding="utf-8")
        self.git("add", "review.md")
        self.git("commit", "--amend", "--no-edit")
        self.head = self.git("rev-parse", "HEAD").strip()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], cwd=self.root, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True,
        ).stdout

    def build(self, suffix: str = "one") -> tuple[Path, Path]:
        package = self.root.parent / f"package-{suffix}"
        archive = self.root.parent / f"package-{suffix}.zip"
        build_package(
            root=self.root, task_id="TASK-TEST", package=package, zip_path=archive,
            copied_members=[("review.md", self.source)], base_ref="main",
            generated_at="2026-01-01T00:00:00+00:00",
        )
        return package, archive

    def test_clean_committed_range_records_identity_patch_files_stats_and_status(self) -> None:
        package, archive = self.build()
        metadata = json.loads((package / "repository/review-metadata.json").read_text())
        changed = json.loads((package / "repository/changed-files.json").read_text())["files"]
        numstat = json.loads((package / "repository/diff-numstat.json").read_text())["files"]
        self.assertEqual(metadata["reviewed_base"], self.base)
        self.assertEqual(metadata["reviewed_head"], self.head)
        self.assertEqual(metadata["review_range"], f"{self.base}..{self.head}")
        self.assertEqual(metadata["git_status"], "clean")
        self.assertIn("implementation.txt", changed)
        self.assertIn("implementation with spaces.txt", changed)
        self.assertTrue((package / "repository/complete.patch").read_text())
        self.assertEqual(sorted(item["path"] for item in numstat), changed)
        self.assertEqual(verify_package(archive)["result"], "PASS")

    def test_upstream_divergence_is_recorded(self) -> None:
        self.git("remote", "add", "origin", str(self.root))
        self.git("fetch", "origin", "main")
        self.git("branch", "--set-upstream-to", "origin/main")
        identity = resolve_identity(self.root, base_ref="main")
        self.assertEqual(identity.upstream, "origin/main")
        self.assertEqual(identity.upstream_ahead, 1)
        self.assertEqual(identity.upstream_behind, 0)

    def test_dirty_tree_requires_explicit_intent(self) -> None:
        (self.root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "clean working tree"):
            resolve_identity(self.root, base_ref="main")
        identity = resolve_identity(self.root, base_ref="main", allow_dirty=True)
        self.assertEqual(identity.git_status, "dirty")

    def test_repeated_generation_is_deterministic_and_removes_stale_staging(self) -> None:
        first, first_zip = self.build("repeat")
        first_bytes = first_zip.read_bytes()
        (first / "stale.txt").write_text("must disappear\n", encoding="utf-8")
        _, second_zip = self.build("repeat")
        self.assertFalse((first / "stale.txt").exists())
        self.assertEqual(first_bytes, second_zip.read_bytes())

    def test_verification_detects_corrupted_member(self) -> None:
        _, archive = self.build("corrupt")
        rewritten = self.root.parent / "corrupted.zip"
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(rewritten, "w") as target:
            for name in source.namelist():
                value = source.read(name)
                if name.endswith("repository/complete.patch"):
                    value += b"corruption"
                target.writestr(name, value)
        with self.assertRaisesRegex(ValueError, "hash or size mismatch"):
            verify_package(rewritten)

    def test_verification_detects_patch_inventory_mismatch_even_with_updated_hash(self) -> None:
        package, _ = self.build("mismatch")
        (package / "repository/changed-files.json").write_text('{"files": []}\n')
        manifest_path = package / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        value = (package / "repository/changed-files.json").read_bytes()
        import hashlib
        manifest["members"]["repository/changed-files.json"] = {
            "sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        archive = self.root.parent / "mismatch-rewritten.zip"
        with zipfile.ZipFile(archive, "w") as target:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    target.write(path, f"TASK-TEST/{path.relative_to(package).as_posix()}")
        with self.assertRaisesRegex(ValueError, "patch and changed-file"):
            verify_package(archive)


if __name__ == "__main__":
    unittest.main()
