"""Reset one learner/channel onboarding marker for a repeatable demo."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from src.bootstrap.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset Story 4 state for exactly one learner and channel."
    )
    parser.add_argument("--author-id", required=True)
    parser.add_argument("--channel-id", required=True)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    settings = Settings.load(project_root)
    database_path = settings.resolve_path(
        project_root,
        settings.onboarding_state_db_path,
    )
    if not database_path.exists():
        print("No onboarding state database exists yet; nothing to reset.")
        return

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM learner_first_questions
            WHERE author_id = ? AND channel_id = ?
            """,
            (args.author_id, args.channel_id),
        )
    print(f"Reset {cursor.rowcount} onboarding marker(s).")


if __name__ == "__main__":
    main()
