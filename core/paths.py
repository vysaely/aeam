"""
Locates AEAM's data directory (~/.local/share/aeam; AERAM's aeram/ before the 2026-11-06 rename).
"""

import sqlite3
from pathlib import Path


def _has_accounts(base_dir: Path) -> bool:
    """True when base_dir/manager.db exists and contains at least one account (read-only check)."""
    db_path = base_dir / "manager.db"
    if not db_path.is_file():
        return False
    try:
        conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, timeout=1.0)
        try:
            return conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone() is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def default_base_dir() -> Path:
    share = Path.home() / ".local" / "share"
    aeam_dir = share / "aeam"
    # Installs from before the renames keep their accounts in ~/.local/share/aeram (AERAM,
    # until 2026-11-06) or ~/.local/share/ram-linux; install.sh moves aeram/ to aeam/.
    legacy = (share / "aeram", share / "ram-linux")
    # Prefer whichever directory actually holds accounts: an empty aeam/ directory (created by
    # a repair step or a first launch) must not hide an existing legacy vault.
    for candidate in (aeam_dir, *legacy):
        if _has_accounts(candidate):
            return candidate
    for candidate in (aeam_dir, *legacy):
        if candidate.exists():
            return candidate
    return aeam_dir
