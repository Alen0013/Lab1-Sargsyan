"""Try three prohibited commits in an isolated repository with the real hooks."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    output = ROOT / "reports/LAB1"
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONUTF8"] = "1"
    env["PRE_COMMIT_COLOR"] = "never"
    transcript = []
    results = []
    with tempfile.TemporaryDirectory(prefix="lab1_negative_") as directory:
        sandbox = Path(directory)

        def run(*args, check=True):
            process = subprocess.run(
                args,
                cwd=sandbox,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            transcript.append("$ " + subprocess.list2cmdline(args))
            transcript.append(process.stdout + process.stderr)
            if check and process.returncode:
                raise RuntimeError(f"Setup command failed: {args[0]} (exit {process.returncode})")
            return process

        try:
            run("git", "init", "--quiet")
            run("git", "config", "user.name", "Lab1 negative control")
            run("git", "config", "user.email", "lab1@example.invalid")
            run("git", "config", "core.autocrlf", "false")
            for name in (".pre-commit-config.yaml", "check_staged.py", "pyproject.toml"):
                shutil.copyfile(ROOT / name, sandbox / name)
            run("git", "add", ".")
            run("git", "commit", "--quiet", "-m", "control baseline")
            run(sys.executable, "-m", "pre_commit", "install", "--install-hooks")
            baseline = run("git", "rev-parse", "HEAD").stdout.strip()
            cases = (
                ("style", "bad_style.py", b"import os\nx=1\n", "Python style"),
                ("secret", "fake_secret.txt", ("ghp_" + "A" * 36).encode(), "BLOCK_SECRET"),
                ("size", "too_large.bin", b"\x00" * (1024 * 1024 + 1), "BLOCK_SIZE"),
            )
            for label, filename, payload, marker in cases:
                transcript.append(f"\nCONTROL: {label}")
                (sandbox / filename).write_bytes(payload)
                run("git", "add", "--", filename)
                commit = run("git", "commit", "-m", f"prohibited {label} change", check=False)
                unchanged = run("git", "rev-parse", "HEAD").stdout.strip() == baseline
                combined = commit.stdout + commit.stderr
                detected = marker in combined
                if label == "style":
                    detected = detected and "F401" in combined
                passed = commit.returncode != 0 and unchanged and detected
                result = {
                    "case": label,
                    "exit_code": commit.returncode,
                    "head_unchanged": unchanged,
                    "expected_marker": marker,
                    "marker_found": detected,
                    "passed": passed,
                }
                results.append(result)
                transcript.append(json.dumps(result))
                run("git", "reset", "--quiet", "HEAD", "--", filename)
                (sandbox / filename).unlink()
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            transcript.append(f"CONTROL_ERROR: {exc}")
    success = len(results) == 3 and all(case["passed"] for case in results)
    summary = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "isolated_repository": True,
        "all_blocked": success,
        "controls": results,
    }
    transcript.append("RESULT: PASS" if success else "RESULT: FAIL")
    (output / "precommit_block.log").write_text("\n".join(transcript) + "\n", encoding="utf-8")
    (output / "precommit_controls.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copyfile(ROOT / ".pre-commit-config.yaml", output / "precommit_config.yaml")
    print(
        "Three actual commits blocked; HEAD unchanged." if success else "Negative controls failed."
    )
    print(output / "precommit_block.log")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
