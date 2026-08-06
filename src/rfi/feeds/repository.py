"""SQLite authority for feed definitions, observations, tombstones, and runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rfi.feeds.contracts import FeedDefinition, FeedEntry, FeedError
from rfi.storage import RepositoryDatabase, StorageError
from rfi.storage.sqlite import canonical_json


class FeedRepository:
    """Keep feed configuration independent while linking only to public repository identities."""

    def __init__(self, state: Path) -> None:
        try:
            self._database = RepositoryDatabase.initialize(state)
        except StorageError as error:
            raise FeedError(str(error)) from error

    def create_revision(
        self,
        *,
        feed_id: str,
        display_name: str,
        feed_url: str,
        enabled: bool,
        notes: str,
        firm_ids: tuple[str, ...],
        format: str,
        created_at: str,
        lifecycle_status: str = "active",
        expected_revision_id: str | None = None,
    ) -> FeedDefinition:
        if not display_name.strip():
            raise FeedError("feed display name is required")
        if format not in {"rss", "atom"}:
            raise FeedError("validated feed format must be RSS or Atom")
        if lifecycle_status not in {"active", "retired"}:
            raise FeedError("feed lifecycle status is invalid")
        firm_ids = tuple(sorted(set(firm_ids)))
        with self._database.transaction() as connection:
            prior = connection.execute(
                "SELECT current_revision_id,lifecycle_status FROM feed_definitions WHERE feed_id=?",
                (feed_id,),
            ).fetchone()
            if prior is None:
                if expected_revision_id is not None:
                    raise FeedError("cannot update an unknown feed")
                revision_number, predecessor = 1, None
            else:
                if expected_revision_id != str(prior[0]):
                    raise FeedError("feed changed since the editor was opened")
                revision_number = int(connection.execute(
                    "SELECT revision_number FROM feed_revisions WHERE revision_id=?",
                    (str(prior[0]),),
                ).fetchone()[0]) + 1
                predecessor = str(prior[0])
            known = {
                str(row[0]) for row in connection.execute(
                    "SELECT firm_id FROM firms WHERE firm_id IN "
                    f"({','.join('?' for _ in firm_ids)})",
                    firm_ids,
                )
            } if firm_ids else set()
            if known != set(firm_ids):
                raise FeedError("one or more associated firms do not exist")
            stable = canonical_json({
                "feed_id": feed_id,
                "revision_number": revision_number,
                "display_name": display_name.strip(),
                "feed_url": feed_url,
                "enabled": bool(enabled),
                "notes": notes.strip(),
                "firm_ids": list(firm_ids),
                "format": format,
                "lifecycle_status": lifecycle_status,
                "created_at": created_at,
            })
            revision_id = "feedrev-" + hashlib.sha256(stable.encode()).hexdigest()[:24]
            value = FeedDefinition(
                feed_id, revision_id, revision_number, display_name.strip(), feed_url,
                bool(enabled), notes.strip(), firm_ids, format, lifecycle_status, created_at,
            )
            payload = canonical_json({"schema_version": 1, **value.to_dict()})
            if prior is None:
                connection.execute(
                    "INSERT INTO feed_definitions VALUES (?,?,?)",
                    (feed_id, revision_id, lifecycle_status),
                )
            connection.execute(
                "INSERT INTO feed_revisions VALUES (?,?,?,?,?,?)",
                (revision_id, feed_id, revision_number, predecessor, created_at, payload),
            )
            connection.executemany(
                "INSERT INTO feed_firm_associations VALUES (?,?)",
                ((revision_id, firm_id) for firm_id in firm_ids),
            )
            connection.execute(
                "UPDATE feed_definitions SET current_revision_id=?,lifecycle_status=? "
                "WHERE feed_id=?",
                (revision_id, lifecycle_status, feed_id),
            )
            self._database.advance_revision(connection)
        return value

    def get(self, feed_id: str, *, include_retired: bool = False) -> FeedDefinition:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT r.canonical_json,d.lifecycle_status FROM feed_definitions d "
                "JOIN feed_revisions r ON r.revision_id=d.current_revision_id WHERE d.feed_id=?",
                (feed_id,),
            ).fetchone()
        if row is None or (str(row[1]) == "retired" and not include_retired):
            raise FeedError(f"unknown feed: {feed_id}")
        return self._definition(row[0])

    def list(self, *, include_retired: bool = False) -> tuple[FeedDefinition, ...]:
        where = "" if include_retired else "WHERE d.lifecycle_status='active'"
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT r.canonical_json FROM feed_definitions d JOIN feed_revisions r "
                f"ON r.revision_id=d.current_revision_id {where} "
                "ORDER BY lower(json_extract(r.canonical_json,'$.display_name')),d.feed_id"
            ).fetchall()
        return tuple(self._definition(row[0]) for row in rows)

    def history(self, feed_id: str) -> tuple[FeedDefinition, ...]:
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT canonical_json FROM feed_revisions WHERE feed_id=? "
                "ORDER BY revision_number",
                (feed_id,),
            ).fetchall()
        return tuple(self._definition(row[0]) for row in rows)

    def select_for_firms(self, firm_ids: tuple[str, ...]) -> tuple[FeedDefinition, ...]:
        if not firm_ids:
            return ()
        placeholders = ",".join("?" for _ in firm_ids)
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT DISTINCT r.canonical_json FROM feed_definitions d "
                "JOIN feed_revisions r ON r.revision_id=d.current_revision_id "
                "JOIN feed_firm_associations a ON a.revision_id=r.revision_id "
                "WHERE d.lifecycle_status='active' "
                "AND json_extract(r.canonical_json,'$.enabled')=1 "
                f"AND a.firm_id IN ({placeholders}) ORDER BY d.feed_id",
                firm_ids,
            ).fetchall()
        return tuple(self._definition(row[0]) for row in rows)

    def observe_entry(
        self, feed: FeedDefinition, entry: FeedEntry, observed_at: str
    ) -> tuple[str, str, str]:
        material_hash = hashlib.sha256(canonical_json(entry.to_dict()).encode()).hexdigest()
        observation_id = "feedobs-" + hashlib.sha256(
            f"{feed.feed_id}\0{entry.entry_key}\0{material_hash}".encode()
        ).hexdigest()[:24]
        value = {
            "schema_version": 1,
            "observation_id": observation_id,
            "feed_id": feed.feed_id,
            "feed_revision_id": feed.revision_id,
            "feed_url": feed.feed_url,
            "entry": entry.to_dict(),
            "material_hash": material_hash,
            "observed_at": observed_at,
        }
        with self._database.transaction() as connection:
            current = connection.execute(
                "SELECT current_observation_id FROM feed_entry_state "
                "WHERE feed_id=? AND entry_key=?",
                (feed.feed_id, entry.entry_key),
            ).fetchone()
            if current is not None:
                existing = connection.execute(
                    "SELECT material_hash FROM feed_entry_observations WHERE observation_id=?",
                    (str(current[0]),),
                ).fetchone()
                if existing is not None and str(existing[0]) == material_hash:
                    return "unchanged", str(current[0]), material_hash
            disposition = "new" if current is None else "updated"
            connection.execute(
                "INSERT OR IGNORE INTO feed_entry_observations VALUES (?,?,?,?,?,?,?)",
                (observation_id, feed.feed_id, feed.revision_id, entry.entry_key,
                 material_hash, observed_at, canonical_json(value)),
            )
            connection.execute(
                "INSERT INTO feed_entry_state VALUES (?,?,?) ON CONFLICT(feed_id,entry_key) "
                "DO UPDATE SET current_observation_id=excluded.current_observation_id",
                (feed.feed_id, entry.entry_key, observation_id),
            )
            self._database.advance_revision(connection)
        return disposition, observation_id, material_hash

    def link_artifact(
        self, feed_id: str, entry_key: str, material_hash: str, artifact_id: str,
        attempt_id: str, linked_at: str,
    ) -> None:
        with self._database.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO feed_entry_artifacts VALUES (?,?,?,?,?,?)",
                (feed_id, entry_key, material_hash, artifact_id, attempt_id, linked_at),
            )
            row = connection.execute(
                "SELECT canonical_json FROM feed_tombstones WHERE feed_id=? AND entry_key=?",
                (feed_id, entry_key),
            ).fetchone()
            if row is not None:
                value = json.loads(str(row[0]))
                value["status"] = "fulfilled"
                value["artifact_id"] = artifact_id
                value["fulfilled_at"] = linked_at
                connection.execute(
                    "UPDATE feed_tombstones SET status='fulfilled',artifact_id=?,canonical_json=? "
                    "WHERE feed_id=? AND entry_key=?",
                    (artifact_id, canonical_json(value), feed_id, entry_key),
                )
            self._database.advance_revision(connection)

    def record_unavailable(
        self, feed: FeedDefinition, entry: FeedEntry, observed_at: str,
        category: str, reason: str, retryable: bool, run_id: str,
    ) -> dict[str, Any]:
        tombstone_id = "feedtomb-" + hashlib.sha256(
            f"{feed.feed_id}\0{entry.entry_key}".encode()
        ).hexdigest()[:24]
        attempt = {
            "attempted_at": observed_at, "run_id": run_id, "category": category,
            "reason": reason[:512], "retryable": retryable,
        }
        with self._database.transaction() as connection:
            prior = connection.execute(
                "SELECT canonical_json,first_observed_at,status FROM feed_tombstones "
                "WHERE feed_id=? AND entry_key=?", (feed.feed_id, entry.entry_key),
            ).fetchone()
            if prior is None:
                value = {
                    "schema_version": 1, "tombstone_id": tombstone_id,
                    "feed_id": feed.feed_id, "feed_url": feed.feed_url,
                    "entry": entry.to_dict(), "status": "unresolved", "artifact_id": None,
                    "first_observed_at": observed_at, "last_observed_at": observed_at,
                    "attempts": [attempt], "failure_category": category,
                    "diagnostic_reason": reason[:512], "retry_eligible": retryable,
                }
                connection.execute(
                    "INSERT INTO feed_tombstones VALUES (?,?,?,?,?,?,?,?)",
                    (tombstone_id, feed.feed_id, entry.entry_key, "unresolved", None,
                     observed_at, observed_at, canonical_json(value)),
                )
            else:
                value = json.loads(str(prior[0]))
                value["entry"] = entry.to_dict()
                value["feed_url"] = feed.feed_url
                value["last_observed_at"] = observed_at
                value["failure_category"] = category
                value["diagnostic_reason"] = reason[:512]
                value["retry_eligible"] = retryable
                value.setdefault("attempts", []).append(attempt)
                value["attempts"] = value["attempts"][-20:]
                if value.get("status") == "fulfilled":
                    return value
                connection.execute(
                    "UPDATE feed_tombstones SET last_observed_at=?,canonical_json=? "
                    "WHERE tombstone_id=?",
                    (observed_at, canonical_json(value), tombstone_id),
                )
            self._database.advance_revision(connection)
        return value

    def touch_tombstone_observation(
        self, feed_id: str, entry: FeedEntry, observed_at: str
    ) -> None:
        """Refresh observation evidence without inventing an acquisition attempt."""
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT tombstone_id,canonical_json FROM feed_tombstones "
                "WHERE feed_id=? AND entry_key=?", (feed_id, entry.entry_key),
            ).fetchone()
            if row is None:
                return
            value = json.loads(str(row[1]))
            value["entry"] = entry.to_dict()
            value["last_observed_at"] = observed_at
            connection.execute(
                "UPDATE feed_tombstones SET last_observed_at=?,canonical_json=? "
                "WHERE tombstone_id=?",
                (observed_at, canonical_json(value), str(row[0])),
            )
            self._database.advance_revision(connection)

    def tombstones(self, status: str | None = None) -> tuple[dict[str, Any], ...]:
        if status is not None and status not in {"unresolved", "fulfilled", "dismissed"}:
            raise FeedError("invalid tombstone status filter")
        where, values = ("WHERE status=?", (status,)) if status else ("", ())
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                f"SELECT canonical_json FROM feed_tombstones {where} "
                "ORDER BY last_observed_at DESC,tombstone_id DESC", values,
            ).fetchall()
        return tuple(json.loads(str(row[0])) for row in rows)

    def tombstone(self, tombstone_id: str) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM feed_tombstones WHERE tombstone_id=?",
                (tombstone_id,),
            ).fetchone()
        if row is None:
            raise FeedError(f"unknown unavailable entry: {tombstone_id}")
        return json.loads(str(row[0]))

    def set_tombstone_status(self, tombstone_id: str, status: str, at: str) -> dict[str, Any]:
        if status not in {"unresolved", "dismissed"}:
            raise FeedError("tombstone may only be dismissed or restored by this action")
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT canonical_json FROM feed_tombstones WHERE tombstone_id=?",
                (tombstone_id,),
            ).fetchone()
            if row is None:
                raise FeedError(f"unknown unavailable entry: {tombstone_id}")
            value = json.loads(str(row[0]))
            if value.get("status") == "fulfilled":
                raise FeedError("a fulfilled entry cannot be dismissed or restored")
            value["status"] = status
            value["status_changed_at"] = at
            connection.execute(
                "UPDATE feed_tombstones SET status=?,canonical_json=? WHERE tombstone_id=?",
                (status, canonical_json(value), tombstone_id),
            )
            self._database.advance_revision(connection)
        return value

    def record_fulfillment_attempt(
        self, tombstone_id: str, at: str, method: str, outcome: str, diagnostic: str
    ) -> dict[str, Any]:
        """Append bounded manual-candidate history without changing unresolved state."""
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT canonical_json FROM feed_tombstones WHERE tombstone_id=?",
                (tombstone_id,),
            ).fetchone()
            if row is None:
                raise FeedError(f"unknown unavailable entry: {tombstone_id}")
            value = json.loads(str(row[0]))
            value.setdefault("fulfillment_attempts", []).append({
                "attempted_at": at, "method": method, "outcome": outcome,
                "diagnostic": diagnostic[:512],
            })
            value["fulfillment_attempts"] = value["fulfillment_attempts"][-20:]
            connection.execute(
                "UPDATE feed_tombstones SET canonical_json=? WHERE tombstone_id=?",
                (canonical_json(value), tombstone_id),
            )
            self._database.advance_revision(connection)
        return value

    def create_run(self, value: dict[str, Any]) -> None:
        with self._database.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM feed_runs WHERE outcome='running' LIMIT 1"
            ).fetchone() is not None:
                raise FeedError("another feed poll is already running")
            connection.execute(
                "INSERT INTO feed_runs VALUES (?,?,?,?,?,?)",
                (value["run_id"], value["trigger"], value["requested_at"],
                 value.get("completed_at", ""), value["outcome"], canonical_json(value)),
            )
            self._database.advance_revision(connection)

    def recover_running_runs(self, recovered_at: str) -> tuple[str, ...]:
        """Cancel runs left active by the prior process without replacing their facts."""
        recovered: list[str] = []
        diagnostic = {
            "category": "startup_recovery",
            "message": (
                "The prior process ended while this feed run was active; "
                "startup recovery canceled the run."
            ),
        }
        with self._database.transaction() as connection:
            rows = connection.execute(
                "SELECT run_id,canonical_json FROM feed_runs "
                "WHERE outcome='running' ORDER BY requested_at,run_id"
            ).fetchall()
            for row in rows:
                run_id = str(row[0])
                try:
                    value = json.loads(str(row[1]))
                except json.JSONDecodeError as error:
                    raise FeedError(f"invalid feed run record: {run_id}") from error
                if not isinstance(value, dict) or value.get("run_id") != run_id:
                    raise FeedError(f"invalid feed run record: {run_id}")
                diagnostics = value.get("diagnostics", [])
                if not isinstance(diagnostics, list):
                    raise FeedError(f"invalid feed run diagnostics: {run_id}")
                value["diagnostics"] = [*diagnostics, diagnostic]
                value["outcome"] = "canceled"
                value["completed_at"] = recovered_at
                value["recovered_at"] = recovered_at
                value["termination_reason"] = "canceled during startup recovery"
                connection.execute(
                    "UPDATE feed_runs SET completed_at=?,outcome='canceled',canonical_json=? "
                    "WHERE run_id=? AND outcome='running'",
                    (recovered_at, canonical_json(value), run_id),
                )
                recovered.append(run_id)
            if recovered:
                self._database.advance_revision(connection)
        return tuple(recovered)

    def save_run(self, value: dict[str, Any]) -> None:
        with self._database.transaction() as connection:
            changed = connection.execute(
                "UPDATE feed_runs SET completed_at=?,outcome=?,canonical_json=? WHERE run_id=?",
                (value["completed_at"], value["outcome"], canonical_json(value), value["run_id"]),
            ).rowcount
            if changed != 1:
                raise FeedError("unknown feed run")
            old = connection.execute(
                "SELECT run_id FROM feed_runs ORDER BY requested_at DESC,run_id DESC "
                "LIMIT -1 OFFSET 100"
            ).fetchall()
            connection.executemany("DELETE FROM feed_runs WHERE run_id=?", old)
            self._database.advance_revision(connection)

    def run(self, run_id: str) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM feed_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise FeedError(f"unknown feed run: {run_id}")
        return json.loads(str(row[0]))

    def runs(self, limit: int = 25) -> tuple[dict[str, Any], ...]:
        limit = max(1, min(limit, 100))
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT canonical_json FROM feed_runs "
                "ORDER BY requested_at DESC,run_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return tuple(json.loads(str(row[0])) for row in rows)

    def export_items(self, limit: int = 200) -> tuple[dict[str, Any], ...]:
        limit = max(1, min(limit, 500))
        with self._database.connect(read_only=True) as connection:
            rows = connection.execute(
                "SELECT o.canonical_json,a.artifact_id,t.status,t.tombstone_id "
                "FROM feed_entry_state s JOIN feed_entry_observations o "
                "ON o.observation_id=s.current_observation_id "
                "LEFT JOIN feed_entry_artifacts a ON a.feed_id=o.feed_id "
                "AND a.entry_key=o.entry_key AND a.material_hash=o.material_hash "
                "LEFT JOIN feed_tombstones t ON t.feed_id=o.feed_id AND t.entry_key=o.entry_key "
                "ORDER BY o.observed_at DESC,o.observation_id DESC LIMIT ?", (limit,),
            ).fetchall()
        result = []
        for row in rows:
            value = json.loads(str(row[0]))
            value["artifact_id"] = str(row[1]) if row[1] is not None else None
            value["availability"] = "retained" if row[1] is not None else "unavailable"
            value["tombstone_status"] = str(row[2]) if row[2] is not None else None
            value["tombstone_id"] = str(row[3]) if row[3] is not None else None
            result.append(value)
        return tuple(result)

    @staticmethod
    def _definition(raw: object) -> FeedDefinition:
        value = json.loads(str(raw))
        return FeedDefinition(
            value["feed_id"], value["revision_id"], int(value["revision_number"]),
            value["display_name"], value["feed_url"], bool(value["enabled"]),
            value.get("notes", ""), tuple(value.get("firm_ids", ())), value["format"],
            value["lifecycle_status"], value["created_at"],
        )
