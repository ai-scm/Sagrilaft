#!/usr/bin/env python3
"""P20-only inert migration failure fixture; exits before importing Alembic."""

import json
import os
import re
import sys


def main() -> int:
    run_id = os.environ.get("P20_LAB_RUN_ID", "")
    if not re.fullmatch(r"p20-[a-f0-9]{12}", run_id):
        print("P20 fixture refused: invalid lab run id", file=sys.stderr)
        return 64

    # This fixture intentionally performs no database connection or DDL. Its
    # only effect is a structured log marker followed by a deterministic error.
    print(json.dumps({"event": "p20_migration_fault", "stage": "before_ddl",
                      "runId": run_id, "databaseTouched": False}), flush=True)
    return 42


if __name__ == "__main__":
    raise SystemExit(main())
