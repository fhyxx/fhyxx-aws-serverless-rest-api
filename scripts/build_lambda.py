"""Build a pinned, dependency-inclusive Python 3.12 Lambda zip artifact."""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "build" / "lambda-package"
ARTIFACT = ROOT / "dist" / "task_api.zip"


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(
            "Build the Lambda artifact with Python 3.12 to match the configured runtime."
        )
    if PACKAGE.exists() or ARTIFACT.exists():
        raise SystemExit(
            "Build output already exists; review and remove only generated build/dist "
            "output before rebuilding."
        )
    PACKAGE.mkdir(parents=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--target",
            str(PACKAGE),
            "-r",
            str(ROOT / "requirements-lambda.txt"),
        ],
        check=True,
    )
    shutil.copytree(ROOT / "src" / "task_api", PACKAGE / "task_api", dirs_exist_ok=True)
    with zipfile.ZipFile(
        ARTIFACT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for source in sorted(PACKAGE.rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts:
                archive.write(source, source.relative_to(PACKAGE).as_posix())
    print(f"Created {ARTIFACT.relative_to(ROOT)} ({ARTIFACT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
