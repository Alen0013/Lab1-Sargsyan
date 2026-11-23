"""Check bytes in the Git index before a commit, without displaying secrets."""

import ast
import json
import re
import subprocess
from pathlib import PurePosixPath

import yaml

MAX_BYTES = 1024 * 1024
SECRETS = (
    rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    rb"(?im)^\s*(?:API_KEY|ACCESS_TOKEN|SECRET_KEY|PASSWORD)\s*[:=]\s*[\"']?[A-Za-z0-9_+/=.-]{20,}",
)


def check_blob(name: str, payload: bytes) -> list[str]:
    failures = []
    if len(payload) > MAX_BYTES:
        failures.append(f"BLOCK_SIZE {name}: {len(payload)} > {MAX_BYTES} bytes")
    if any(re.search(pattern, payload) for pattern in SECRETS):
        failures.append(f"BLOCK_SECRET {name}: credential pattern detected; value redacted")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return failures
    if re.search(r"(?m)^(?:<{7} |={7}$|>{7} )", text):
        failures.append(f"BLOCK_CONFLICT {name}: unresolved merge marker")
    suffix = PurePosixPath(name).suffix.lower()
    try:
        if suffix == ".py":
            ast.parse(text, filename=name)
        elif suffix == ".json":
            json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            yaml.safe_load(text)
    except (SyntaxError, ValueError, yaml.YAMLError):
        failures.append(f"BLOCK_SYNTAX {name}: invalid {suffix} syntax")
    return failures


def main() -> int:
    try:
        names = subprocess.check_output(["git", "ls-files", "--cached", "-z"]).split(b"\0")
        failures = []
        for raw_name in filter(None, names):
            name = raw_name.decode("utf-8", errors="surrogateescape")
            payload = subprocess.check_output(["git", "show", f":{name}"], stderr=subprocess.PIPE)
            failures.extend(check_blob(name, payload))
    except (OSError, subprocess.CalledProcessError):
        print("CHECK_FAILED: cannot read Git index")
        return 2
    print("\n".join(failures) if failures else "PASS: staged secrets, size and syntax checks")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
