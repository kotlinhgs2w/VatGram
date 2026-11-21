#!/usr/bin/env python3
"""Safely import the supplied Yougram ZIP into a local VatGram checkout.

Run from the root of a cloned https://github.com/kotlinhgs2w/VatGram.
This script does not commit or push anything.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath

SKIP_NAMES = {".DS_Store", "Thumbs.db", "yougram.jks", "valgram.jks", "local.properties"}
SKIP_PARTS = {"__MACOSX", ".git", ".gradle", "build", ".cxx", ".externalNativeBuild"}
PRESERVE_ROOT_FILES = {"README.md", ".gitignore", "IMPORT_STATUS.md"}


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe ZIP path: {name}")
    return path


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    result, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        print(f"NOTICE: could not automatically update {label}; inspect it manually.")
        return text
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Yougram sources into ValGram.")
    parser.add_argument("zip_file", help="Path to Yougram.zip")
    parser.add_argument("--dry-run", action="store_true", help="List files without copying.")
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    archive = Path(args.zip_file).expanduser().resolve()
    if not (repo / ".git").exists():
        sys.exit("ERROR: run from the root of your cloned VatGram Git repository.")
    if not archive.is_file():
        sys.exit(f"ERROR: ZIP not found: {archive}")

    try:
        with zipfile.ZipFile(archive) as zf:
            files = [n for n in zf.namelist() if n and not n.endswith("/")]
            roots = {PurePosixPath(n).parts[0] for n in files if PurePosixPath(n).parts}
            if len(roots) != 1:
                raise ValueError("ZIP must contain exactly one top-level project directory.")
            prefix = next(iter(roots)) + "/"
            plan = []
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename[len(prefix):] if info.filename.startswith(prefix) else info.filename
                rel = safe_member_path(name)
                if not rel.parts or any(p in SKIP_PARTS for p in rel.parts) or rel.name in SKIP_NAMES:
                    continue
                if len(rel.parts) == 1 and rel.name in PRESERVE_ROOT_FILES:
                    if rel.name == "README.md":
                        rel = PurePosixPath("UPSTREAM_README.md")
                    else:
                        continue
                dest = repo.joinpath(*rel.parts)
                try:
                    dest.resolve().relative_to(repo)
                except ValueError:
                    raise ValueError(f"ZIP path escapes repository: {info.filename}")
                plan.append((info, dest))

            print(f"Files to import: {len(plan)}")
            print("Excluded: signing keys, local.properties, Git metadata and build/cache folders.")
            if args.dry_run:
                for _, dest in plan:
                    print(dest.relative_to(repo))
                return 0

            collisions = [dest for _, dest in plan if dest.exists()]
            if collisions:
                print("ERROR: destination files already exist; no files were copied:")
                for path in collisions[:30]:
                    print("  " + str(path.relative_to(repo)))
                print("Use a clean VatGram checkout or back up/move the conflicting files.")
                return 2

            for info, dest in plan:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, dest.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except (zipfile.BadZipFile, ValueError) as exc:
        sys.exit(f"ERROR: {exc}")

    settings = repo / "settings.gradle.kts"
    if settings.exists():
        value = settings.read_text(encoding="utf-8-sig")
        value = value.replace('rootProject.name = "Yougram"', 'rootProject.name = "ValGram"')
        settings.write_text(value, encoding="utf-8")

    app_gradle = repo / "app" / "build.gradle.kts"
    if app_gradle.exists():
        value = app_gradle.read_text(encoding="utf-8-sig")
        value = value.replace('applicationId = "app.yougram"', 'applicationId = "app.valgram"')
        app_gradle.write_text(value, encoding="utf-8")

    strings = repo / "app" / "src" / "main" / "res" / "values" / "strings.xml"
    if strings.exists():
        value = strings.read_text(encoding="utf-8-sig")
        value = value.replace('<string name="app_name">Yougram</string>', '<string name="app_name">ValGram</string>')
        strings.write_text(value, encoding="utf-8")

    print("\nImport completed. Review the changes before committing.")
    print("Kotlin namespace remains app.yougram to preserve source imports.")
    print("No signing key or local.properties was copied.")
    print("\nNext: install JDK 17, Android SDK 36, NDK and CMake 3.22.1.")
    print("If Gradle is installed: gradle wrapper --gradle-version 8.14.4")
    print("Build debug APK: ./gradlew assembleDebug (Windows: gradlew.bat assembleDebug)")
    print("APK: app/build/outputs/apk/debug/app-debug.apk")
    print("Configure your own Telegram API credentials in local.properties if required.")
    print("Inspect git diff, then commit and push manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
