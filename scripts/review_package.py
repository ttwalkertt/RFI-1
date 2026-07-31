#!/usr/bin/env python3
"""Commit-aware review-package assembly and independent verification."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

FORMAT_VERSION = 2
REQUIRED_MEMBERS = {
    "manifest.json",
    "repository/changed-files.json",
    "repository/complete.patch",
    "repository/diff-numstat.json",
    "repository/diff-stat.txt",
    "repository/git-status.txt",
    "repository/review-metadata.json",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def _default_base_ref(root: Path) -> str:
    symbolic_result = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], cwd=root,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    symbolic = symbolic_result.stdout.strip() if symbolic_result.returncode == 0 else ""
    if symbolic:
        return symbolic.removeprefix("refs/remotes/")
    for candidate in ("origin/main", "origin/master", "main", "master"):
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", candidate], cwd=root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if result.returncode == 0:
            return candidate
    raise RuntimeError("could not determine review base; pass --base explicitly")


@dataclass(frozen=True)
class ReviewIdentity:
    reviewed_base: str
    reviewed_head: str
    merge_base: str
    review_range: str
    base_ref: str
    branch: str
    git_status: str
    upstream: str | None
    upstream_ahead: int | None
    upstream_behind: int | None


def resolve_identity(
    root: Path, *, base_ref: str | None = None, allow_dirty: bool = False
) -> ReviewIdentity:
    """Resolve immutable implementation identity separately from generation state."""
    root = root.resolve()
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status and not allow_dirty:
        raise RuntimeError(
            "review package generation requires a clean working tree; "
            "commit or remove changes, or pass explicit dirty-tree intent"
        )
    base_ref = base_ref or _default_base_ref(root)
    head = _git(root, "rev-parse", "HEAD").strip()
    base = _git(root, "rev-parse", base_ref).strip()
    merge_base = _git(root, "merge-base", base, head).strip()
    branch = _git(root, "branch", "--show-current").strip()
    upstream_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    ahead = behind = None
    if upstream:
        counts = _git(root, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        behind, ahead = (int(item) for item in counts.split())
    return ReviewIdentity(
        reviewed_base=merge_base,
        reviewed_head=head,
        merge_base=merge_base,
        review_range=f"{merge_base}..{head}",
        base_ref=base_ref,
        branch=branch,
        git_status="dirty" if status else "clean",
        upstream=upstream,
        upstream_ahead=ahead,
        upstream_behind=behind,
    )


def committed_evidence(
    root: Path, identity: ReviewIdentity
) -> tuple[str, list[str], str, list[dict[str, str]]]:
    """Return patch, changed paths, and statistics from the committed review range."""
    review_range = identity.review_range
    patch = _git(
        root, "-c", "core.quotePath=false", "diff", "--binary", "--no-renames",
        review_range,
    )
    changed = sorted(
        item for item in _git(
            root, "-c", "core.quotePath=false", "diff", "--name-only", "--no-renames",
            review_range,
        ).splitlines() if item
    )
    stat = _git(root, "-c", "core.quotePath=false", "diff", "--stat", "--no-renames", review_range)
    numstat = []
    for line in _git(
        root, "-c", "core.quotePath=false", "diff", "--numstat", "--no-renames", review_range
    ).splitlines():
        added, deleted, path = line.split("\t", 2)
        numstat.append({"path": path, "added": added, "deleted": deleted})
    if changed and not patch:
        raise RuntimeError("committed review range is non-empty but implementation patch is empty")
    return patch, changed, stat, numstat


def patch_files(patch: str) -> list[str]:
    """Extract committed file paths from a no-renames Git binary patch."""
    files: list[str] = []
    current: tuple[str, str] | None = None
    deleted = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current[0] if deleted else current[1])
            paths = line.removeprefix("diff --git ")
            current = None
            offset = 0
            while True:
                separator = paths.find(" b/", offset)
                if separator < 0:
                    break
                first = paths[:separator]
                second = paths[separator + 1:]
                if first.startswith("a/") and second.startswith("b/"):
                    current = (first[2:], second[2:])
                    if current[0] == current[1]:
                        break
                offset = separator + 3
            if current is None or current[0] != current[1]:
                raise ValueError(f"unsupported patch header: {line}")
            deleted = False
        elif line.startswith("deleted file mode "):
            deleted = True
    if current:
        files.append(current[0] if deleted else current[1])
    return sorted(files)


def write_text(package: Path, relative: str, content: str) -> None:
    target = package / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def build_package(
    *, root: Path, task_id: str, package: Path, zip_path: Path,
    copied_members: Sequence[tuple[str, Path]], base_ref: str | None = None,
    allow_dirty: bool = False, generated_at: str | None = None,
) -> dict[str, object]:
    """Rebuild and verify a commit-aware package from finalized source artifacts."""
    identity = resolve_identity(root, base_ref=base_ref, allow_dirty=allow_dirty)
    patch, changed, stat, numstat = committed_evidence(root, identity)
    shutil.rmtree(package, ignore_errors=True)
    package.mkdir(parents=True)
    zip_path.unlink(missing_ok=True)
    for relative, source in copied_members:
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    metadata = {
        **asdict(identity),
        "generated_at_utc": generated_at or datetime.now(UTC).isoformat(),
    }
    write_text(
        package, "repository/review-metadata.json",
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
    )
    write_text(
        package, "repository/git-status.txt",
        f"branch: {identity.branch}\nstatus: {identity.git_status}\n",
    )
    write_text(package, "repository/complete.patch", patch)
    write_text(
        package, "repository/changed-files.json",
        json.dumps({"files": changed}, indent=2) + "\n",
    )
    write_text(package, "repository/diff-stat.txt", stat)
    write_text(
        package, "repository/diff-numstat.json",
        json.dumps({"files": numstat}, indent=2) + "\n",
    )
    members = sorted(
        path.relative_to(package).as_posix()
        for path in package.rglob("*") if path.is_file()
    )
    manifest = {
        "format_version": FORMAT_VERSION,
        "task_id": task_id,
        "package_identity": {
            "reviewed_base": identity.reviewed_base,
            "reviewed_head": identity.reviewed_head,
            "merge_base": identity.merge_base,
            "review_range": identity.review_range,
        },
        "members": {
            member: {
                "sha256": sha256(package / member),
                "bytes": (package / member).stat().st_size,
            }
            for member in members
        },
    }
    write_text(package, "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    f"{task_id}/{path.relative_to(package).as_posix()}",
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    verify_package(zip_path, expected_task_id=task_id)
    return manifest


def verify_package(zip_path: Path, *, expected_task_id: str | None = None) -> dict[str, object]:
    """Independently validate an existing package without regenerating it."""
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"ZIP member failed CRC verification: {bad}")
        names = archive.namelist()
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise ValueError("package must contain exactly one task root")
        task_id = roots.pop()
        if expected_task_id and task_id != expected_task_id:
            raise ValueError(
                f"package identity mismatch: expected {expected_task_id}, found {task_id}"
            )
        manifest_name = f"{task_id}/manifest.json"
        if manifest_name not in names:
            raise ValueError("manifest.json is missing")
        manifest = json.loads(archive.read(manifest_name))
        if manifest.get("format_version") != FORMAT_VERSION or manifest.get("task_id") != task_id:
            raise ValueError("package format or identity is invalid")
        members = manifest.get("members", {})
        actual = {name.removeprefix(f"{task_id}/") for name in names if name != manifest_name}
        if actual != set(members) or not REQUIRED_MEMBERS.issubset(actual | {"manifest.json"}):
            raise ValueError("manifest completeness or required-member verification failed")
        for relative, record in members.items():
            value = archive.read(f"{task_id}/{relative}")
            if sha256_bytes(value) != record["sha256"] or len(value) != record["bytes"]:
                raise ValueError(f"member hash or size mismatch: {relative}")
        metadata = json.loads(archive.read(f"{task_id}/repository/review-metadata.json"))
        identity = manifest["package_identity"]
        for key in ("reviewed_base", "reviewed_head", "merge_base", "review_range"):
            if metadata.get(key) != identity.get(key):
                raise ValueError(f"review-range metadata mismatch: {key}")
        if identity["review_range"] != f"{identity['reviewed_base']}..{identity['reviewed_head']}":
            raise ValueError("resolved review range is inconsistent")
        patch = archive.read(f"{task_id}/repository/complete.patch").decode()
        changed = json.loads(archive.read(f"{task_id}/repository/changed-files.json"))["files"]
        numstat = json.loads(archive.read(f"{task_id}/repository/diff-numstat.json"))["files"]
        if patch_files(patch) != sorted(changed):
            raise ValueError("implementation patch and changed-file inventory differ")
        if sorted(item["path"] for item in numstat) != sorted(changed):
            raise ValueError("diff statistics and changed-file inventory differ")
        if changed and not patch:
            raise ValueError("non-empty comparison has an empty implementation patch")
    return {
        "task_id": task_id,
        "format_version": FORMAT_VERSION,
        "members_verified": len(members),
        "result": "PASS",
    }
