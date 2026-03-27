import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print a standardized progress line for OpenClaw skill execution."
    )
    parser.add_argument("--current", type=int, required=True, help="Current stage number")
    parser.add_argument("--total", type=int, default=6, help="Total stage count (default: 6)")
    parser.add_argument("--stage", required=True, help="Stage name, e.g. preprocessing")
    parser.add_argument(
        "--status",
        required=True,
        choices=["START", "RUNNING", "DONE", "RETRY", "WARNING", "ERROR"],
        help="Progress status",
    )
    parser.add_argument("--detail", default="", help="Optional detail text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.current < 1 or args.total < 1 or args.current > args.total:
        print("ERROR: invalid current/total value", file=sys.stderr)
        return 1

    detail = f" | {args.detail}" if args.detail else ""
    print(f"[PROGRESS] {args.current}/{args.total} {args.stage} | {args.status}{detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
