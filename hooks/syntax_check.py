import re
import sys
from typing import List


PLACEHOLDER_RE = re.compile(r"\{\{PH_[A-Z_0-9]+\}\}")
LINK_RE = re.compile(r"\[[^\]\n]+\]\([^)]+\)")


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def strip_fenced_code(text: str) -> str:
    return re.sub(r"(?ms)^```.*?^```[ \t]*\n?", "", text)


def has_unbalanced_inline_backticks(text: str) -> bool:
    stripped = strip_fenced_code(text)
    stripped = re.sub(r"``[^`]*``", "", stripped)
    count = len(re.findall(r"(?<!`)`(?!`)", stripped))
    return count % 2 != 0


def find_errors(text: str) -> List[str]:
    errors: List[str] = []

    fence_count = len(re.findall(r"(?m)^```", text))
    if fence_count % 2 != 0:
        errors.append("Unclosed code fence detected.")

    if has_unbalanced_inline_backticks(text):
        errors.append("Unbalanced inline backticks detected.")

    placeholders = sorted(set(PLACEHOLDER_RE.findall(text)))
    if placeholders:
        errors.append("Unrestored placeholders detected: " + ", ".join(placeholders))

    stripped = strip_fenced_code(text)
    open_links = stripped.count("](")
    closed_links = len(LINK_RE.findall(stripped))
    if open_links > closed_links:
        errors.append("Malformed Markdown links detected.")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python syntax_check.py <markdown_file>", file=sys.stderr)
        return 1

    text = load_text(sys.argv[1])
    errors = find_errors(text)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
