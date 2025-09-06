#!/usr/bin/env python3
"""
Google Drive Shared Drive watcher -> Telegram notifier

Features:
- Watches one or more Shared Drive folder IDs for newly created files or folders
- Uses Drive v3 changes().list with includeItemsFromAllDrives/supportsAllDrives
- Computes relative path from watched folder to the new item
- Sends formatted Telegram messages to TWO chat IDs (comma-separated)
- Persists Drive page tokens in SQLite to avoid duplicates on restart
- OAuth Installed App flow using credentials.json -> token.json
- Config via .env, supports --dry-run
- Logs to console and rotating file

Usage:
  python main.py [--dry-run]

Environment (.env):
  TELEGRAM_BOT_TOKEN=
  TELEGRAM_CHAT_IDS=-1001234567890,-1009876543210
  WATCH_FOLDER_IDS=folderIdA,folderIdB
  POLL_INTERVAL_SECONDS=30
  ANNOUNCE_UPDATES=true
  GOOGLE_CREDENTIALS_PATH=credentials.json
  GOOGLE_TOKEN_PATH=token.json
  SQLITE_DB_PATH=drive_watcher.db
  LOG_DIR=logs
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple
import html

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Drive scopes: metadata and changes feed. Readonly is sufficient.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


# ----------------------------
# Dataclasses and configuration
# ----------------------------


@dataclass
class Config:
    telegram_bot_token: str
    telegram_chat_ids: List[str]
    watch_folder_ids: List[str]
    poll_interval_seconds: int
    announce_updates: bool
    google_credentials_path: str
    google_token_path: str
    sqlite_db_path: str
    log_dir: str


def parse_bool(value: str, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> Config:
    load_dotenv()

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_ids_raw = os.getenv("TELEGRAM_CHAT_IDS", "").strip()
    watch_folder_ids_raw = os.getenv("WATCH_FOLDER_IDS", "").strip()
    poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))
    announce_updates = parse_bool(os.getenv("ANNOUNCE_UPDATES", "true"), True)
    google_credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json").strip()
    google_token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json").strip()
    sqlite_db_path = os.getenv("SQLITE_DB_PATH", "drive_watcher.db").strip()
    log_dir = os.getenv("LOG_DIR", "logs").strip()

    telegram_chat_ids = [cid.strip() for cid in telegram_chat_ids_raw.split(",") if cid.strip()]
    watch_folder_ids = [fid.strip() for fid in watch_folder_ids_raw.split(",") if fid.strip()]

    if not telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN missing in environment")
    if len(telegram_chat_ids) < 2:
        raise SystemExit("TELEGRAM_CHAT_IDS must contain two comma-separated chat IDs")
    if not watch_folder_ids:
        raise SystemExit("WATCH_FOLDER_IDS must contain at least one folder ID")

    return Config(
        telegram_bot_token=telegram_bot_token,
        telegram_chat_ids=telegram_chat_ids,
        watch_folder_ids=watch_folder_ids,
        poll_interval_seconds=poll_interval_seconds,
        announce_updates=announce_updates,
        google_credentials_path=google_credentials_path,
        google_token_path=google_token_path,
        sqlite_db_path=sqlite_db_path,
        log_dir=log_dir,
    )


# ---------------
# Logging utility
# ---------------


def setup_logging(log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "drive_watcher.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


# ----------------------
# SQLite state utilities
# ----------------------


class State:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )

    def get(self, key: str) -> Optional[str]:
        cur = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# -------------------------
# Google Drive API handling
# -------------------------


def authenticate_drive(credentials_path: str, token_path: str):
    creds: Optional[Credentials] = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(HttpError),
)
def drive_get_start_page_token(service) -> str:
    resp = service.changes().getStartPageToken(supportsAllDrives=True).execute()
    return resp["startPageToken"]


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(HttpError),
)
def drive_list_changes(service, page_token: str) -> dict:
    fields = (
        "changes(changeType,removed,fileId,kind,time,"
        "file(id,name,parents,mimeType,trashed,createdTime,driveId)),"
        "newStartPageToken,nextPageToken"
    )
    return (
        service
        .changes()
        .list(
            pageToken=page_token,
            pageSize=1000,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields=fields,
            spaces="drive",
        )
        .execute()
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type(HttpError),
)
def drive_files_get(service, file_id: str) -> dict:
    fields = "id,name,parents,mimeType,trashed,driveId"
    return (
        service.files()
        .get(fileId=file_id, supportsAllDrives=True, fields=fields)
        .execute()
    )


# -----------------------------------
# Path resolution and creation filter
# -----------------------------------


class PathResolver:
    def __init__(self, service, watched_folder_ids: List[str]) -> None:
        self.service = service
        self.watched_folder_ids = set(watched_folder_ids)
        self.cache: Dict[str, dict] = {}

    def fetch(self, file_id: str) -> Optional[dict]:
        if file_id in self.cache:
            return self.cache[file_id]
        try:
            meta = drive_files_get(self.service, file_id)
            self.cache[file_id] = meta
            return meta
        except HttpError as e:
            logging.warning("Failed to fetch metadata for %s: %s", file_id, e)
            return None

    def compute_relative_path(self, file_meta: dict) -> Optional[Tuple[str, List[str]]]:
        """
        Returns (watched_root_id, components) where components is [ ... , item_name ]
        relative to the watched root. None if outside watched roots or on error.
        """
        # Guard against trashed or missing parents
        if not file_meta or file_meta.get("trashed"):
            return None

        item_id = file_meta.get("id")
        item_name = file_meta.get("name") or item_id
        parents = file_meta.get("parents") or []

        # If the item itself is a watched root, relative path is empty
        if item_id in self.watched_folder_ids:
            return (item_id, [])

        if not parents:
            return None

        # Follow the first parent; in modern Drive there is only one parent
        parent_id = parents[0]
        path_components = [item_name]

        while parent_id:
            if parent_id in self.watched_folder_ids:
                # Found a watched root. Relative path excludes the root itself.
                path_components.reverse()
                return (parent_id, path_components)

            parent_meta = self.fetch(parent_id)
            if not parent_meta:
                return None
            if parent_meta.get("trashed"):
                return None
            path_components.append(parent_meta.get("name") or parent_id)
            next_parents = parent_meta.get("parents") or []
            if not next_parents:
                break
            parent_id = next_parents[0]

        return None


def is_folder(file_meta: dict) -> bool:
    return file_meta.get("mimeType") == "application/vnd.google-apps.folder"


def format_path(components: List[str]) -> str:
    return "/".join(components)


# ----------------------
# Telegram notifications
# ----------------------


def telegram_send_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Telegram send failed ({resp.status_code}): {resp.text}")


def notify_telegram(bot_token: str, chat_ids: List[str], text: str, dry_run: bool) -> None:
    for cid in chat_ids:
        if dry_run:
            logging.info("[DRY-RUN] Would send to %s: %s", cid, text)
        else:
            try:
                telegram_send_message(bot_token, cid, text)
                logging.info("Sent to %s", cid)
            except Exception as e:
                logging.error("Telegram send to %s failed: %s", cid, e)


# --------------------
# Core polling routine
# --------------------


def ensure_initial_tokens(state: State, service) -> None:
    page_token = state.get("page_token")
    if page_token:
        return

    # Set the checkpoint to NOW so we only receive changes that happen after now
    init_time = datetime.now(timezone.utc)
    start_page_token = drive_get_start_page_token(service)
    state.set("page_token", start_page_token)
    state.set("start_page_token", start_page_token)
    state.set("init_start_time_iso", init_time.isoformat())
    logging.info("Initialized startPageToken=%s at %s", start_page_token, init_time.isoformat())


def parse_rfc3339(ts: str) -> datetime:
    # Drive returns RFC3339 with Z
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def build_message(file_meta: dict, rel_path: str, change_time_iso: str) -> str:
    created_iso = file_meta.get("createdTime")
    created_dt = parse_rfc3339(created_iso) if created_iso else None
    created_str = created_dt.strftime("%Y-%m-%d %H:%M UTC") if created_dt else "Unknown"
    kind_emoji = "📁" if is_folder(file_meta) else "📄"
    kind_word = "folder" if is_folder(file_meta) else "file"
    name = file_meta.get("name") or file_meta.get("id")
    # HTML escape dynamic content for Telegram parse_mode=HTML
    name = html.escape(name)
    rel_path = html.escape(rel_path)
    lines = [
        f"{kind_emoji} <b>New {kind_word}</b>",
        f"<b>Name:</b> {name}",
        f"<b>Path:</b> {rel_path}",
        f"<b>Created:</b> {created_str}",
    ]
    # Include the change time in a subtle way
    if change_time_iso:
        try:
            ch_dt = parse_rfc3339(change_time_iso)
            lines.append(f"<b>Detected:</b> {ch_dt.strftime('%Y-%m-%d %H:%M UTC')}")
        except Exception:
            pass
    return "\n".join(lines)


def poll_changes_loop(config: Config, dry_run: bool) -> None:
    service = authenticate_drive(config.google_credentials_path, config.google_token_path)
    state = State(config.sqlite_db_path)
    try:
        ensure_initial_tokens(state, service)
        path_resolver = PathResolver(service, config.watch_folder_ids)

        # Cache init start time for creation filter
        init_start_time_iso = state.get("init_start_time_iso")
        if not init_start_time_iso:
            # Fallback to now if somehow missing
            init_start_time_iso = datetime.now(timezone.utc).isoformat()
            state.set("init_start_time_iso", init_start_time_iso)
        init_start_time = parse_rfc3339(init_start_time_iso)

        logging.info(
            "Watching %d folder(s); polling every %ds; dry_run=%s; announce_updates=%s",
            len(config.watch_folder_ids),
            config.poll_interval_seconds,
            dry_run,
            config.announce_updates,
        )

        while True:
            page_token = state.get("page_token")
            if not page_token:
                # If missing (e.g., DB cleared), reinitialize
                ensure_initial_tokens(state, service)
                page_token = state.get("page_token")

            try:
                response = drive_list_changes(service, page_token)
            except HttpError as e:
                logging.error("Drive changes.list failed: %s", e)
                time.sleep(config.poll_interval_seconds)
                continue

            changes = response.get("changes", [])
            next_page_token = response.get("nextPageToken")
            new_start_page_token = response.get("newStartPageToken")

            if changes:
                logging.info("Fetched %d change(s)", len(changes))
            else:
                logging.debug("No changes in this cycle")

            for change in changes:
                if change.get("removed"):
                    continue
                file_meta = change.get("file")
                if not file_meta:
                    continue
                if file_meta.get("trashed"):
                    continue

                # Creation filter: only consider items whose createdTime is after init_start_time
                created_iso = file_meta.get("createdTime")
                if not created_iso:
                    continue
                try:
                    created_dt = parse_rfc3339(created_iso)
                except Exception:
                    continue

                if created_dt < (init_start_time):
                    # Not a new creation since the watcher started
                    continue

                # Compute relative path under any watched root
                comp = path_resolver.compute_relative_path(file_meta)
                if not comp:
                    continue
                _, components = comp
                rel_path = format_path(components)

                # Build and send Telegram message
                if config.announce_updates:
                    msg = build_message(file_meta, rel_path, change.get("time"))
                    notify_telegram(config.telegram_bot_token, config.telegram_chat_ids, msg, dry_run)
                else:
                    logging.info("New item (announce disabled): %s", rel_path)

            # Advance page token
            if next_page_token:
                state.set("page_token", next_page_token)
            elif new_start_page_token:
                # When no more pages, update to the newStartPageToken for future polls
                state.set("page_token", new_start_page_token)
                state.set("start_page_token", new_start_page_token)
            else:
                # Keep the current token if API returned neither
                pass

            time.sleep(config.poll_interval_seconds)
    finally:
        state.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive -> Telegram watcher")
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending")
    args = parser.parse_args()

    config = load_config()
    setup_logging(config.log_dir)
    logging.info("Starting Drive watcher")
    try:
        poll_changes_loop(config, dry_run=args.dry_run)
    except KeyboardInterrupt:
        logging.info("Stopping by user request")


if __name__ == "__main__":
    main()

