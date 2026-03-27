import difflib
import sys


SMALL_TEXT_THRESHOLD = 4000


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if left_char == right_char else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def ratio_to_diff_rate(ratio: float) -> float:
    return round((1.0 - ratio) * 100, 2)


def calculate_diff_rate(left: str, right: str) -> float:
    baseline = max(len(left), len(right), 1)

    # For short texts, keep the stricter character-level edit distance.
    if baseline <= SMALL_TEXT_THRESHOLD:
        return round(levenshtein_distance(left, right) / baseline * 100, 2)

    # For larger documents, prefer SequenceMatcher to avoid O(n*m) blowups.
    line_ratio = difflib.SequenceMatcher(None, left.splitlines(), right.splitlines()).ratio()
    char_ratio = difflib.SequenceMatcher(None, left, right).ratio()

    # Blend line and char similarity so structural edits weigh a bit more heavily.
    blended_ratio = line_ratio * 0.6 + char_ratio * 0.4
    return ratio_to_diff_rate(blended_ratio)


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python calc_diff.py <draft_v1> <draft_v2>", file=sys.stderr)
        return 1

    left = load_text(sys.argv[1])
    right = load_text(sys.argv[2])
    print(calculate_diff_rate(left, right))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
