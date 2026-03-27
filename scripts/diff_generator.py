import difflib
import html
import os
import sys


def load_lines(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readlines()


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: python diff_generator.py <draft_v1> <draft_v2> <output_html>", file=sys.stderr)
        return 1

    before_path, after_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    before_lines = load_lines(before_path)
    after_lines = load_lines(after_path)

    rendered = difflib.HtmlDiff(wrapcolumn=100).make_file(
        before_lines,
        after_lines,
        fromdesc=html.escape(os.path.basename(before_path)),
        todesc=html.escape(os.path.basename(after_path)),
        context=True,
        numlines=3,
    )

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(rendered)

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
