import json
import os
import re
import sys
from typing import List


DEFAULT_CHUNK_SIZE = 5000


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def split_sections(text: str) -> List[str]:
    parts = re.split(r"(?m)^##\s+", text)
    if len(parts) <= 1:
        return [text]

    sections: List[str] = []
    first = parts[0].strip()
    if first:
        sections.append(first)

    for part in parts[1:]:
        cleaned = part.strip()
        if not cleaned:
            continue
        lines = cleaned.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:])
        sections.append(f"## {title}\n{body}".strip())

    return sections or [text]


def merge_sections(sections: List[str], chunk_size: int) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for section in sections:
        projected = current_len + len(section) + (2 if current else 0)
        if current and projected > chunk_size:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if len(section) > chunk_size:
            paragraphs = [p for p in section.split("\n\n") if p.strip()]
            for paragraph in paragraphs:
                projected = current_len + len(paragraph) + (2 if current else 0)
                if current and projected > chunk_size:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0

                if len(paragraph) > chunk_size:
                    if current:
                        chunks.append("\n\n".join(current))
                        current = []
                        current_len = 0
                    for start in range(0, len(paragraph), chunk_size):
                        chunks.append(paragraph[start : start + chunk_size])
                else:
                    current.append(paragraph)
                    current_len += len(paragraph) + (2 if current_len else 0)
            continue

        current.append(section)
        current_len += len(section) + (2 if current_len else 0)

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [""]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python splitter.py <input_file> [output_dir] [chunk_size]", file=sys.stderr)
        return 1

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(input_file), "chunks")
    try:
        chunk_size = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_CHUNK_SIZE
    except ValueError:
        print("ERROR: chunk_size must be an integer", file=sys.stderr)
        return 1
    if chunk_size <= 0:
        print("ERROR: chunk_size must be > 0", file=sys.stderr)
        return 1

    text = load_text(input_file)
    sections = split_sections(text)
    chunks = merge_sections(sections, chunk_size)

    os.makedirs(output_dir, exist_ok=True)
    chunk_files: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_path = os.path.join(output_dir, f"chunk_{index:03d}.md")
        with open(chunk_path, "w", encoding="utf-8") as handle:
            handle.write(chunk)
        chunk_files.append(chunk_path)

    manifest = {
        "source_file": os.path.abspath(input_file),
        "chunk_size": chunk_size,
        "chunk_count": len(chunk_files),
        "chunks": chunk_files,
    }
    manifest_path = os.path.join(output_dir, "chunks_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
