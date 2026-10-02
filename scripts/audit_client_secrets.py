"""
scripts/audit_client_secrets.py - Client Secret Leak Audit

Verifies that no server secrets, private credentials, or backend API keys
have leaked into frontend source files or production client bundles.

Usage:
    python scripts/audit_client_secrets.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_SRC = PROJECT_ROOT / "frontend" / "src"
FRONTEND_OUTPUT = PROJECT_ROOT / "frontend" / ".output" / "public"

FORBIDDEN_KEYWORD_PATTERNS = [
    re.compile(r"JWT_SECRET\s*=", re.IGNORECASE),
    re.compile(r"TELEGRAM_BOT_TOKEN\s*=", re.IGNORECASE),
    re.compile(r"TELEGRAM_WEBHOOK_SECRET\s*=", re.IGNORECASE),
    re.compile(r"CLOUDINARY_API_SECRET\s*=", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"ci-only-test-secret-that-is-never-used-in-production"),
    re.compile(r"your-super-secret-key-change-in-production"),
]

SUSPICIOUS_TOKEN_PATTERNS = [
    re.compile(r"""['"][0-9]{8,10}:[a-zA-Z0-9_-]{35}['"]"""),  # Telegram bot token format
    re.compile(r"""['"]AIza[0-9A-Za-z-_]{35}['"]"""),          # Google API Key format
]


def audit_file(filepath: Path) -> list[str]:
    violations: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        violations.append(f"Failed to read {filepath}: {exc}")
        return violations

    for pattern in FORBIDDEN_KEYWORD_PATTERNS:
        match = pattern.search(content)
        if match:
            violations.append(f"Forbidden secret pattern '{pattern.pattern}' detected in {filepath}")

    for pattern in SUSPICIOUS_TOKEN_PATTERNS:
        match = pattern.search(content)
        if match:
            violations.append(f"Suspicious live token format detected in {filepath}: {match.group(0)[:12]}...")

    return violations


def run_audit() -> int:
    print("[Secret Audit] Starting client secret leak audit...")
    violations: list[str] = []

    # 1. Audit Frontend Source
    if not FRONTEND_SRC.exists():
        print(f"[Error] Frontend source directory not found: {FRONTEND_SRC}")
        return 1

    src_files = [p for p in FRONTEND_SRC.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx", ".js", ".jsx", ".json", ".css"}]
    print(f"[Secret Audit] Auditing {len(src_files)} frontend source files in {FRONTEND_SRC}...")
    for file_path in src_files:
        violations.extend(audit_file(file_path))

    # 2. Audit Client Production Output (if built)
    if FRONTEND_OUTPUT.exists():
        bundle_files = [p for p in FRONTEND_OUTPUT.rglob("*") if p.is_file() and p.suffix in {".js", ".json", ".html"}]
        print(f"[Secret Audit] Auditing {len(bundle_files)} production client bundle files in {FRONTEND_OUTPUT}...")
        for file_path in bundle_files:
            violations.extend(audit_file(file_path))
    else:
        print("[Secret Audit] Client output directory not found yet (skipped production bundle audit).")

    if violations:
        print("\n[Audit FAILED] Secret leaks or forbidden patterns detected:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("\n[Audit PASSED] Zero client secret leaks detected. All frontend files verified.")
    return 0


if __name__ == "__main__":
    sys.exit(run_audit())
