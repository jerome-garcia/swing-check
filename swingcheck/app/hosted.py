"""Hosted mode: SwingCheck on a public server, shared by strangers.

Run locally the app has one user and none of this applies. Hosted (`swingcheck
--hosted`), every visitor is kept apart without accounts or a database:

- The first visit gets a random owner key in a cookie. Each new swing records a
  hash of it in its own swing.json, and every swing route checks it, answering
  "not found" for anyone else's swing.
- The key doubles as a private link (`/#/claim/<key>`, a URL fragment, so it never
  reaches the server's or a proxy's logs) to open the same swings on another device.
- Each owner keeps at most `max_swings`, and swings are deleted `keep_days` after
  they were uploaded. Uploads are capped in size and clip length.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from swingcheck.app.jobs import JobManager
    from swingcheck.app.store import Store

log = logging.getLogger(__name__)

OWNER_COOKIE = "swingcheck_owner"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")  # secrets.token_urlsafe(32)
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # the swings expire long before; the key can stay
SWEEP_EVERY_S = 30 * 60


def new_key() -> str:
    return secrets.token_urlsafe(32)


def valid_key(key: str | None) -> bool:
    return bool(key and KEY_PATTERN.match(key))


def owner_of(key: str) -> str:
    """What a swing stores: a hash, so the swing folders never hold anyone's key."""
    return hashlib.sha256(key.encode()).hexdigest()


def expires_at(created: str, keep_days: float) -> datetime | None:
    try:
        return datetime.fromisoformat(created) + timedelta(days=keep_days)
    except (TypeError, ValueError):
        return None


def sweep(store: Store, jobs: JobManager, keep_days: float, now: datetime | None = None,
          before_delete: Callable[[str], None] = lambda swing_id: None) -> list[str]:
    """Delete every swing older than `keep_days` (skipping one that's being processed).
    `before_delete(id)` runs first, e.g. to close the swing's open video."""
    now = now or datetime.now()
    deleted = []
    for folder in list(store.root.iterdir()):
        if not folder.is_dir():
            continue
        try:
            meta = store.meta(folder.name)
        except KeyError:
            continue
        end = expires_at(meta.created, keep_days)
        if end is None or end > now or jobs.active_for(meta.id):
            continue
        try:
            before_delete(meta.id)
            store.delete(meta.id)
            deleted.append(meta.id)
        except OSError:
            log.exception("Couldn't delete expired swing %s", meta.id)
    return deleted


def start_sweeper(store: Store, jobs: JobManager, keep_days: float,
                  before_delete: Callable[[str], None] = lambda swing_id: None) -> None:
    """Sweep now, then every half hour, on a background thread."""
    def loop() -> None:
        while True:
            try:
                sweep(store, jobs, keep_days, before_delete=before_delete)
            except Exception:  # noqa: BLE001 - keep sweeping
                log.exception("Expired-swing sweep failed")
            time.sleep(SWEEP_EVERY_S)

    threading.Thread(target=loop, name="swingcheck-sweeper", daemon=True).start()
