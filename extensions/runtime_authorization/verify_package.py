"""Public-byte integrity and bounded sensitive-content checks; not rights clearance."""
from pathlib import Path
import ast
import hashlib
import json
import re
import os

ROOT = Path(__file__).resolve().parent
ALLOWLIST = (
    "README.md", "LIMITATIONS_AND_PROVENANCE.md", "LICENSE_SCOPE.md",
    "shared/model_conditions.json", "shared/pap_0_5/POLICY.md",
    "studies/ex2/PROTOCOL.md", "studies/ex2/evidence.json", "studies/ex2/scenarios.json",
    "studies/ex2_r/PROTOCOL.md", "studies/ex2_r/evidence.json", "studies/ex2_r/scenarios.json",
    "reproduce.py", "analysis/reference.json", "verify_package.py", "run_tests.py",
    "tests/test_release.py",
    'mechanism/__init__.py',
    'mechanism/pap/__init__.py',
    'mechanism/pap/contracts.py',
    'mechanism/pap/serialization.py',
    'mechanism/pap/chain_validation.py',
    'mechanism/pap/evaluator.py',
    'mechanism/pap/execution/__init__.py',
    'mechanism/pap/execution/run.py',
    'mechanism/pap/execution/tools.py',
    'mechanism/fixtures.py',
    'mechanism/drivers.py',
    'mechanism/scoring.py',
    'mechanism/business_simulator.py',
    'mechanism/output_contract.py',
    'mechanism/fixtures.json',
    'mechanism/PROPOSED_MIT_NOTICE.md',
    'mechanism/offline_guard.py',
    'mechanism/recovery.py',
    'demonstrate.py',
    'tests/test_mechanism.py',
    'provenance/SOURCE_TRANSFORMATIONS.json',
 "provenance/PROJECTION_AND_SOURCE_MAP.json",
    "provenance/SHA256_MANIFEST.json", "docs/domain_adaptation.md",
)
FORBIDDEN_KEYS = {
    "api_key", "access_token", "refresh_token", "authorization", "authorization_header",
    "password", "passwd", "cookie", "cookies", "private_key", "client_secret", "credentials",
    "raw", "raw_provider_response", "_raw_provider_body", "_raw_response_text",
    "client_options", "endpoint", "provider_request_id", "request_hash", "request_id",
    "journal_root", "hostname", "username", "email", "signature", "token",
}
PATTERNS = {
    "google_credential": r"AI" + r"za[0-9A-Za-z_-]{35}",
    "provider_secret": r"s" + r"k-(?:ant-[A-Za-z0-9_-]{15,}|proj-[A-Za-z0-9_-]{15,}|[A-Za-z0-9]{32,})",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
    "cloud_access_key": r"(?:AKIA|ASIA)[A-Z0-9]{16}",
    "slack_token": r"xox[baprs]-[A-Za-z0-9-]{20,}",
    "google_oauth": r"ya29\.[A-Za-z0-9_-]{20,}",
    "stripe_secret": r"(?:sk|rk)_live_[A-Za-z0-9]{16,}",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "authentication_header": r"(?i)(?:bearer|basic)\s+[A-Za-z0-9_.+/=-]{16,}",
    "jwt": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "credential_assignment": r"(?i)(?:api[_-]?key|client[_-]?secret|password|access[_-]?token)\s*[:=]\s*[\"'][A-Za-z0-9_+/=-]{12,}[\"']",
    "private_path": r"(?i)[A-Z]:[/\\]Users[/\\]|" + "/" + r"home/[^/\s\"]+|" + "/" + r"Users/[^/\s\"]+",
    "private_run_identifier": r"EX2E1-(?:GEMINI|CLAUDE)-|EX2R-01-E\d+",
}
STDLIB_IMPORTS = {"argparse", "dataclasses", "enum", "types", "typing", "datetime", "threading", "mechanism", "pap", "contracts", "serialization", "chain_validation", "evaluator", "tools", "fixtures", "drivers", "scoring", "business_simulator", "output_contract", "recovery", "offline_guard", "pathlib", "decimal", "collections", "json", "ast", "hashlib", "re", "os", "sys", "unittest", "socket", "importlib", "copy", "tempfile", "contextlib", "io", "reproduce", "verify_package"}

def files(root):
    for base, dirs, names in os.walk(root, followlinks=False):
        base = Path(base)
        if base == root and ".git" in dirs:
            dirs.remove(".git")
        for d in dirs:
            p = base / d
            if p.is_symlink() or p.is_junction():
                raise ValueError("Linked directory")
        for name in names:
            p = base / name
            if p.is_symlink():
                raise ValueError("Linked file")
            yield p

def structured_findings(value, file, path="$", synthetic_fixture=False):
    result = []
    if isinstance(value, dict):
        for k, v in value.items():
            test_request = (synthetic_fixture and k == "request_id" and isinstance(v, str) and
                            re.fullmatch(r"EX2-S(?:01|06|07|08)-R[12]", v) is not None)
            if k.lower() in FORBIDDEN_KEYS and not test_request:
                result.append({"file":file, "location":path, "category":"excluded_structured_field"})
            result.extend(structured_findings(v, file, path + "." + k, synthetic_fixture))
    elif isinstance(value, list):
        for i,v in enumerate(value):
            result.extend(structured_findings(v, file, path + "[" + str(i) + "]", synthetic_fixture))
    return result

def scan_text(text, file):
    return [{"file":file, "category":name} for name, pattern in PATTERNS.items() if re.search(pattern, text)]

def sensitive_review(root=ROOT, check_imports=True):
    findings = []
    seen = []
    for p in sorted(files(root)):
        name = p.relative_to(root).as_posix()
        seen.append(name)
        if p.name.startswith(".env") or p.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".pyc", ".zip", ".sqlite", ".db", ".env"} or p.name in {"credentials.sh", "id_rsa", "id_ed25519"}:
            findings.append({"file":name, "category":"excluded_file_type"})
        text = p.read_text(encoding="utf-8-sig")
        findings.extend(scan_text(text, name))
        if p.suffix == ".json":
            data = json.loads(text)
            synthetic = name in {"mechanism/fixtures.json", "extensions/runtime_authorization/mechanism/fixtures.json"} and isinstance(data, dict) and data.get("test_only") is True and set(data) == {"test_only", "protocol"}
            findings.extend(structured_findings(data, name, synthetic_fixture=synthetic))
        if check_imports and p.suffix == ".py":
            for node in ast.walk(ast.parse(text)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if isinstance(node, ast.ImportFrom) and node.level and node.module is None:
                    names = [a.name for a in node.names]
                if any(n.split(".")[0] not in STDLIB_IMPORTS for n in names):
                    findings.append({"file":name, "category":"unapproved_import"})
    return {"files_reviewed":len(seen), "findings":findings, "scope":"Bounded patterns, recursive JSON keys, file and import checks; manual/rights review still required."}

def verify(root=ROOT):
    actual = {p.relative_to(root).as_posix() for p in files(root)}
    if actual != set(ALLOWLIST):
        raise ValueError("Explicit file allowlist mismatch")
    manifest = json.loads((root / "provenance/SHA256_MANIFEST.json").read_text(encoding="utf-8"))
    expected = actual - {"provenance/SHA256_MANIFEST.json"}
    if set(manifest["files"]) != expected:
        raise ValueError("Manifest coverage mismatch")
    for name in expected:
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest["files"][name]:
            raise ValueError("Public bytes changed: " + name)
    scan = sensitive_review(root)
    if scan["findings"]:
        raise ValueError("Sensitive-content/import review requires resolution")
    return {"status":"PASS", "files":len(actual), "scan":scan, "authentication":"Public bytes only; not private-source authentication or legal clearance."}

if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
