import argparse
import math
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print standardized RUNNING progress line with ETA."
    )
    parser.add_argument("--current", type=int, required=True, help="Current stage number")
    parser.add_argument("--total", type=int, default=6, help="Total stage count")
    parser.add_argument("--stage", required=True, help="Stage name")
    parser.add_argument("--elapsed-sec", type=int, required=True, help="Elapsed seconds")
    parser.add_argument("--expected-sec", type=int, required=True, help="Expected total seconds")
    return parser


def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes = seconds // 60
    remain = seconds % 60
    if minutes <= 0:
        return f"{remain}s"
    return f"{minutes}m{remain:02d}s"


def main() -> int:
    args = build_parser().parse_args()
    if args.current < 1 or args.total < 1 or args.current > args.total:
        print("ERROR: invalid current/total value", file=sys.stderr)
        return 1
    if args.elapsed_sec < 0 or args.expected_sec <= 0:
        print("ERROR: elapsed-sec must be >= 0 and expected-sec must be > 0", file=sys.stderr)
        return 1

    progress = min(1.0, args.elapsed_sec / args.expected_sec)
    progress_pct = int(math.floor(progress * 100))
    remaining = max(0, args.expected_sec - args.elapsed_sec)
    detail = (
        f"elapsed={format_seconds(args.elapsed_sec)} "
        f"eta={format_seconds(remaining)} "
        f"progress={progress_pct}%"
    )
    print(f"[PROGRESS] {args.current}/{args.total} {args.stage} | RUNNING | {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
