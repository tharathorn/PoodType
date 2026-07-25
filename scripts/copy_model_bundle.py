"""Copy a Faster Whisper snapshot into a self-contained release directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

REQUIRED_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")


def sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def copy_model(source: Path, destination: Path, model_name: str) -> dict:
    missing = [name for name in REQUIRED_FILES if not (source / name).is_file()]
    if missing:
        raise RuntimeError(f"Incomplete model snapshot; missing: {', '.join(missing)}")

    destination.mkdir(parents=True, exist_ok=True)
    manifest_files: dict[str, dict[str, int | str]] = {}
    for name in REQUIRED_FILES:
        src = source / name
        dst = destination / name
        # copy2 follows Hugging Face snapshot symlinks and creates real files.
        shutil.copy2(src, dst, follow_symlinks=True)
        manifest_files[name] = {
            "bytes": dst.stat().st_size,
            "sha256": sha256(dst),
        }

    manifest = {
        "format": 1,
        "model": model_name,
        "source": "Systran/faster-whisper-medium",
        "files": manifest_files,
    }
    (destination / "poodtype-model-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--model", default="medium")
    args = parser.parse_args()
    manifest = copy_model(
        args.source.resolve(),
        args.destination.resolve(),
        args.model,
    )
    total = sum(item["bytes"] for item in manifest["files"].values())
    print(f"Bundled {args.model} model: {total:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
