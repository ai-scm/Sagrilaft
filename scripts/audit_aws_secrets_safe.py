#!/usr/bin/env python3
"""Safe AWS Secrets Manager inventory.

This script intentionally never prints raw secret values. It reports metadata,
JSON keys, emptiness, length, and a short SHA-256 fingerprint per field.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
from datetime import datetime
from typing import Any


SENSITIVE_HINTS = (
    "password",
    "secret",
    "token",
    "key",
    "credential",
    "client_id",
    "username",
)


def run_aws(args: list[str]) -> Any:
    result = subprocess.run(
        ["aws", *args, "--output", "json"],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def classify_secret(name: str, fields: list[str]) -> str:
    text = f"{name} {' '.join(fields)}".lower()
    if "db" in text or "database" in text:
        return "credenciales de base de datos"
    if "zoho" in text:
        return "OAuth/API de tercero + webhook"
    if "smtp" in text:
        return "credenciales SMTP/SES"
    if "keycloak" in text:
        return "credenciales administrativas IdP"
    if "app_secret" in text or "secret_key" in text:
        return "clave criptografica de aplicacion"
    if any(hint in text for hint in SENSITIVE_HINTS):
        return "secreto sensible"
    return "secreto sin clasificacion automatica"


def parse_value(value: str | bytes, is_binary: bool = False) -> tuple[str, Any]:
    if is_binary:
        return "binary", {"bytes": len(value)}
    assert isinstance(value, str)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return "string", value
    if isinstance(parsed, dict):
        return "json", parsed
    return "json-non-object", parsed


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True) if not isinstance(value, str) else value
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def summarize_field(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": True, "empty": True, "type": "null", "length": 0, "sha256_12": None}
    if isinstance(value, str):
        return {
            "present": True,
            "empty": value == "",
            "type": "string",
            "length": len(value),
            "sha256_12": fingerprint(value) if value else None,
        }
    return {
        "present": True,
        "empty": value in ({}, []),
        "type": type(value).__name__,
        "length": len(value) if hasattr(value, "__len__") else None,
        "sha256_12": fingerprint(value),
    }


def fmt_date(value: str | None) -> str:
    if not value:
        return ""
    # AWS CLI JSON dates are already ISO-like; keep them readable and stable.
    try:
        return datetime.fromisoformat(value).isoformat(sep=" ", timespec="seconds")
    except ValueError:
        return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--prefix", default="")
    args = parser.parse_args()

    listed = run_aws([
        "secretsmanager",
        "list-secrets",
        "--region",
        args.region,
        "--include-planned-deletion",
    ])

    rows: list[dict[str, Any]] = []
    for item in listed.get("SecretList", []):
        name = item["Name"]
        if args.prefix and not name.startswith(args.prefix):
            continue

        value_response = run_aws([
            "secretsmanager",
            "get-secret-value",
            "--region",
            args.region,
            "--secret-id",
            name,
        ])

        if "SecretBinary" in value_response:
            raw_binary = base64.b64decode(value_response["SecretBinary"])
            value_type, parsed = parse_value(raw_binary, is_binary=True)
        else:
            value_type, parsed = parse_value(value_response.get("SecretString", ""))

        if isinstance(parsed, dict):
            fields = sorted(parsed.keys())
            field_summary = {key: summarize_field(parsed[key]) for key in fields}
            empty_fields = [key for key, meta in field_summary.items() if meta["empty"]]
        else:
            fields = ["<value>"]
            field_summary = {"<value>": summarize_field(parsed)}
            empty_fields = ["<value>"] if field_summary["<value>"]["empty"] else []

        rows.append({
            "name": name,
            "arn": item.get("ARN", ""),
            "type": classify_secret(name, fields),
            "created": fmt_date(str(item.get("CreatedDate", ""))),
            "last_changed": fmt_date(str(item.get("LastChangedDate", ""))),
            "last_accessed": fmt_date(str(item.get("LastAccessedDate", ""))),
            "value_type": value_type,
            "fields": fields,
            "empty_fields": empty_fields,
            "field_summary": field_summary,
            "version_stages": item.get("SecretVersionsToStages", {}),
        })

    print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
