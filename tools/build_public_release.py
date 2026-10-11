"""Build a local, explicit-allowlist FieldFix source release; never publish it.

Only Python's standard library is used. The existing output directory is
reused only if every file is listed in its previous manifest and unchanged.
Run a fresh-start test in a separate copy, not in this build directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

VERSION = "0.10"
PACKAGE = f"FieldFix-v{VERSION}-source"
ZIP_TIME = (2026, 10, 11, 0, 0, 0)
MANIFEST = "RELEASE_MANIFEST.json"

# Explicit names are intentional. Never replace these with a recursive glob of
# the working project, even when .gitignore appears to exclude private files.
REQUIRED = (
    ".env.example",
    "app/analysis_engine.py",
    "app/case_ai.py",
    "app/case_report.py",
    "app/demo_session.py",
    "app/localization.py",
    "app/paypal.py",
    "app/recovery.py",
    "app/research_replay.py",
    "app/server.py",
    "app/train_triage_model.py",
    "app/triage_model.py",
    "app/workflow.py",
    "app/models/triage-model-v1.json",
    "app/static/app.js",
    "app/static/flow-view.js",
    "app/static/i18n.js",
    "app/static/index.html",
    "app/static/research.css",
    "app/static/research.js",
    "app/static/styles.css",
    "app/tests/test_ai_http.py",
    "app/tests/test_ai_workflow.py",
    "app/tests/test_analysis.py",
    "app/tests/test_authorization.py",
    "app/tests/test_case_ai.py",
    "app/tests/test_case_report.py",
    "app/tests/test_demo_http.py",
    "app/tests/test_demo_session.py",
    "app/tests/test_evidence_history.py",
    "app/tests/test_flow_view.cjs",
    "app/tests/test_legacy_payment_verification.py",
    "app/tests/test_localization.py",
    "app/tests/test_payment_review.py",
    "app/tests/test_recovery.py",
    "app/tests/test_triage_model.py",
    "app/tests/test_workflow.py",
    "docs/triage-model-card-v1.json",
    "docs/triage-model-card-v1.txt",
    "tools/build_public_release.py",
)
MULTILINGUAL = (
    "app/locale_extra.py",
    "app/tests/test_i18n.cjs",
    "app/tests/test_multilingual.py",
)
TEMPLATES = (
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY.md",
    ".gitignore", "start-demo.cmd", "start-sandbox.cmd",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def within(path: Path, root: Path) -> Path:
    result = path.resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("A release path escaped its expected root.")
    return result


def load_sources(root: Path, require_multilingual: bool) -> tuple[dict[str, bytes], list[str]]:
    entries = {name: root / name for name in REQUIRED}
    missing_optional = []
    for name in MULTILINGUAL:
        if (root / name).is_file():
            entries[name] = root / name
        else:
            missing_optional.append(name)
    if require_multilingual and missing_optional:
        raise ValueError("Multilingual release files are missing: " + ", ".join(missing_optional))
    for name in TEMPLATES:
        candidate = root / "public-release" / name
        # A previously built public package can regenerate itself without the
        # owner's separate release-template directory.
        entries[name] = candidate if candidate.is_file() else root / name
    payload = {}
    for name, path in entries.items():
        within(path, root)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or linked allowlist source: " + name)
        payload[name] = path.read_bytes()
    if require_multilingual:
        locale_source = payload["app/static/i18n.js"].decode("utf-8-sig")
        for locale in ("en", "zh-CN", "es", "fr", "pt"):
            quoted = r"[\"']" + re.escape(locale) + r"[\"']"
            named_key = r"(?<![\w])" + re.escape(locale) + r"\s*:"
            if re.search(quoted + "|" + named_key, locale_source) is None:
                raise ValueError("Required UI locale is not declared: " + locale)
    return payload, missing_optional


def scan(payload: dict[str, bytes]) -> list[dict[str, str]]:
    """Return file/rule names only; never echo matched sensitive content."""
    findings = []
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    home_markers = set()
    if home:
        home_markers = {home.lower(), home.replace("\\", "/").lower(), home.replace("\\", "\\\\").lower()}
    env_values = [os.environ.get(name, "") for name in (
        "PAYPAL_SANDBOX_CLIENT_ID", "PAYPAL_SANDBOX_CLIENT_SECRET")]
    secret_values = [value for value in env_values if len(value) >= 12]
    patterns = {
        "nonempty_paypal_env_assignment": re.compile(
            r"(?m)^[ \t]*PAYPAL_SANDBOX_(?:CLIENT_ID|CLIENT_SECRET)[ \t]*=[ \t]*[^\s#]+"),
        "credential_literal": re.compile(
            r"(?i)\b(?:api_key|client_secret|access_token|refresh_token)\b[\"']?[ \t]*[:=][ \t]*[\"']([A-Za-z0-9_./+\-]{32,})[\"']"),
        "private_key_block": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    for name, data in payload.items():
        content = data.decode("utf-8-sig")
        lower = content.lower()
        if any(marker and marker in lower for marker in home_markers):
            findings.append({"file": name, "rule": "current_user_home_path"})
        if any(value in content for value in secret_values):
            findings.append({"file": name, "rule": "current_payment_credential"})
        for rule, pattern in patterns.items():
            if pattern.search(content):
                findings.append({"file": name, "rule": rule})
    return findings


def verify_existing_output(directory: Path, new_files: set[str]) -> None:
    """Never overwrite a modified, untracked or runtime-filled release copy."""
    if not directory.exists():
        return
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Release directory must be an ordinary directory.")
    manifest_path = directory / MANIFEST
    if not manifest_path.is_file():
        raise ValueError("Existing release directory has no manifest; choose a new --output-dir.")
    old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_hashes = {entry["path"]: entry["sha256"] for entry in old_manifest["files"]}
    actual = set()
    for path in directory.rglob("*"):
        within(path, directory)
        if path.is_symlink():
            raise ValueError("Linked content in existing release; choose a new --output-dir.")
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(old_hashes) | {MANIFEST}:
        raise ValueError("Existing release contains missing or extra files; choose a new --output-dir.")
    if not set(old_hashes).issubset(new_files):
        raise ValueError("Allowlist removed an old file; choose a new --output-dir to avoid stale output.")
    for name, expected in old_hashes.items():
        if digest(within(directory / name, directory).read_bytes()) != expected:
            raise ValueError("Existing release was modified; choose a new --output-dir.")


def build(root: Path, output: Path, require_multilingual: bool, check_only: bool) -> dict:
    root = root.resolve()
    output = within(output, root)
    if output == root:
        raise ValueError("Output must be a dedicated subdirectory.")
    payload, missing_optional = load_sources(root, require_multilingual)
    findings = scan(payload)
    if findings:
        # Values are deliberately never included in this error.
        raise ValueError("Release scan blocked packaging: " + json.dumps(findings))
    manifest = {
        "schema": "fieldfix-public-source-v1",
        "version": VERSION,
        "package": PACKAGE,
        "selection": "explicit file allowlist",
        "publication_status": "local preparation only; not uploaded or submitted",
        "missing_optional_multilingual_files": missing_optional,
        "scan": {"status": "passed", "findings": 0, "scope": "allowlisted UTF-8 files; best effort, human review still needed"},
        "excluded_categories": ["credentials", "runtime databases", "personal reports", "contacts", "private research inputs and inference tools", "transaction records", "screenshots"],
        "files": [{"path": name, "bytes": len(data), "sha256": digest(data)} for name, data in sorted(payload.items())],
    }
    result = {"status": "checked" if check_only else "built", "version": VERSION,
              "source_files": len(payload), "missing_optional_multilingual_files": missing_optional,
              "scan_findings": 0}
    if check_only:
        return result
    destination = within(output / PACKAGE, root)
    verify_existing_output(destination, set(payload))
    destination.mkdir(parents=True, exist_ok=True)
    all_files = dict(payload)
    all_files[MANIFEST] = json_bytes(manifest)
    for name, data in sorted(all_files.items()):
        path = within(destination / name, destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    archive = within(output / (PACKAGE + ".zip"), root)
    if archive.is_symlink():
        raise ValueError("Archive target must not be a link.")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in sorted(all_files.items()):
            entry = zipfile.ZipInfo(PACKAGE + "/" + name, date_time=ZIP_TIME)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive) as package:
        if package.testzip() is not None:
            raise ValueError("Archive integrity check failed.")
        if set(package.namelist()) != {PACKAGE + "/" + name for name in all_files}:
            raise ValueError("Archive entries differ from the allowlist.")
        for name, expected in all_files.items():
            if package.read(PACKAGE + "/" + name) != expected:
                raise ValueError("Archive content mismatch: " + name)
    result.update({"archive": str(archive), "directory": str(destination),
                   "archive_bytes": archive.stat().st_size, "archive_sha256": digest(archive.read_bytes()),
                   "manifest": str(destination / MANIFEST), "archive_integrity": "passed"})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, help="Dedicated output directory within source root; default: releases")
    parser.add_argument("--require-multilingual", action="store_true", default=True,
                        help="Require all three multilingual source/test files and five locale declarations (always enabled)")
    parser.add_argument("--check-only", action="store_true", help="Check selection and scan without writing a package")
    args = parser.parse_args()
    output = args.output_dir or args.source_root / "releases"
    if not output.is_absolute():
        output = args.source_root / output
    try:
        result = build(args.source_root, output, args.require_multilingual, args.check_only)
    except (ValueError, OSError, KeyError, UnicodeError) as exc:
        parser.exit(1, "Build failed: " + str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
