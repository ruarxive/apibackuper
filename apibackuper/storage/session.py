"""Non-destructive publication and generation naming for backup runs."""

import os
import re
import shutil
import uuid
from datetime import datetime, timezone

from .backends import build_storage_backend, publish_zip


class BackupSession:
    """Open a resumable working archive and publish complete full backups."""

    def __init__(self, project, mode, checkpoint):
        self.project = project
        self.mode = mode
        self.destination = project.storage_file
        self.staging = self.destination + ".partial"
        previous = self.destination + ".previous"
        if (
            project.storage_type == "filesystem"
            and os.path.exists(previous)
            and not os.path.exists(self.destination)
        ):
            os.replace(previous, self.destination)
        self.run_id = checkpoint.get("run_id") or (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex
            if mode == "update"
            else ""
        )
        if self.run_id and not re.fullmatch(r"[a-zA-Z0-9_-]+", self.run_id):
            raise ValueError("Invalid checkpoint run_id")
        self.prefix = f"runs/{self.run_id}/" if mode == "update" else ""
        if checkpoint:
            self.path = checkpoint.get("storage_file", self.destination)
            if self.path not in (self.destination, self.staging):
                raise ValueError("Checkpoint belongs to a different storage path")
            if (
                not os.path.exists(self.path)
                and checkpoint.get("status") == "publishing"
                and os.path.exists(self.destination)
            ):
                self.path = self.destination
            if not os.path.exists(self.path):
                raise FileNotFoundError(f"Checkpoint storage is missing: {self.path}")
            backend_mode = "continue"
        else:
            self.path = self.staging if mode == "full" else self.destination
            backend_mode = "full" if mode == "full" else "continue"
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.backend = build_storage_backend(project.storage_type, self.path, backend_mode)

    def name(self, page):
        return f"{self.prefix}page_{page}.json"

    def checkpoint(self, payload):
        self.backend.flush()
        self.project._save_checkpoint(
            dict(
                payload,
                mode=self.mode,
                run_id=self.run_id,
                storage_file=self.path,
                status="running",
            ),
            strict=True,
        )

    def publish(self):
        self.backend.close()
        if self.path == self.destination:
            return
        if self.project.storage_type == "zip":
            publish_zip(self.path, self.destination)
        elif self.project.storage_type != "filesystem":
            os.replace(self.path, self.destination)
        else:
            previous = self.destination + ".previous"
            if os.path.exists(previous):
                raise RuntimeError(f"A previous publication needs recovery: {previous}")
            had_previous = os.path.exists(self.destination)
            if had_previous:
                os.replace(self.destination, previous)
            try:
                os.replace(self.path, self.destination)
            except OSError:
                if had_previous:
                    os.replace(previous, self.destination)
                raise
            if had_previous:
                shutil.rmtree(previous)
        self.path = self.destination
