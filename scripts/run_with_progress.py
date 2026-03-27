import argparse
import math
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import List, Optional, Tuple


def format_seconds(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes = total // 60
    remain = total % 60
    if minutes <= 0:
        return f"{remain}s"
    return f"{minutes}m{remain:02d}s"


def progress_line(current: int, total: int, stage: str, status: str, detail: str = "") -> str:
    suffix = f" | {detail}" if detail else ""
    return f"[PROGRESS] {current}/{total} {stage} | {status}{suffix}"


def enqueue_stream(stream, stream_name: str, queue: Queue) -> None:
    try:
        for line in iter(stream.readline, ""):
            queue.put((stream_name, line.rstrip("\r\n")))
    finally:
        queue.put((stream_name, None))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a command and emit live OpenClaw progress lines to stdout."
    )
    parser.add_argument("--current", type=int, required=True, help="Current stage number")
    parser.add_argument("--total", type=int, default=6, help="Total stage count")
    parser.add_argument("--stage", required=True, help="Stage name")
    parser.add_argument("--expected-sec", type=int, default=0, help="Expected seconds for ETA display")
    parser.add_argument(
        "--heartbeat-sec",
        type=int,
        default=20,
        help="Heartbeat interval in seconds for RUNNING messages (default: 20)",
    )
    parser.add_argument(
        "--warning-after-sec",
        type=int,
        default=120,
        help="Emit WARNING after this duration (default: 120)",
    )
    parser.add_argument(
        "--force-unbuffered",
        action="store_true",
        default=True,
        help="Force child process unbuffered output when possible (default: enabled)",
    )
    parser.add_argument(
        "--no-force-unbuffered",
        action="store_false",
        dest="force_unbuffered",
        help="Disable unbuffered forcing",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run, prefix with --")
    return parser


def prepare_unbuffered_command(cmd: List[str], enabled: bool) -> List[str]:
    if not enabled or not cmd:
        return cmd
    exe = Path(cmd[0]).name.lower()
    if exe in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
        if "-u" not in cmd[1:]:
            return [cmd[0], "-u", *cmd[1:]]
    return cmd


def main() -> int:
    args = build_parser().parse_args()
    cmd: List[str] = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("ERROR: missing command. Use: run_with_progress.py ... -- <cmd> [args...]", file=sys.stderr)
        return 1
    if args.current < 1 or args.total < 1 or args.current > args.total:
        print("ERROR: invalid current/total value", file=sys.stderr)
        return 1
    if args.heartbeat_sec <= 0:
        print("ERROR: heartbeat-sec must be > 0", file=sys.stderr)
        return 1

    cmd = prepare_unbuffered_command(cmd, args.force_unbuffered)
    start_detail = f"cmd={' '.join(cmd)}"
    if args.force_unbuffered:
        start_detail = f"{start_detail} unbuffered=1"
    print(progress_line(args.current, args.total, args.stage, "START", start_detail), flush=True)
    start_ts = time.time()
    next_heartbeat = start_ts + args.heartbeat_sec
    warning_emitted = False

    child_env = dict(os.environ)
    if args.force_unbuffered:
        child_env["PYTHONUNBUFFERED"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        cwd=str(Path.cwd()),
        env=child_env,
    )

    q: Queue[Tuple[str, Optional[str]]] = Queue()
    threads = [
        threading.Thread(target=enqueue_stream, args=(proc.stdout, "stdout", q), daemon=True),
        threading.Thread(target=enqueue_stream, args=(proc.stderr, "stderr", q), daemon=True),
    ]
    for t in threads:
        t.start()

    finished_streams = set()
    while True:
        now = time.time()
        elapsed = now - start_ts

        if now >= next_heartbeat:
            detail = f"elapsed={format_seconds(elapsed)}"
            if args.expected_sec > 0:
                eta = max(0, args.expected_sec - int(elapsed))
                pct = int(math.floor(min(1.0, elapsed / args.expected_sec) * 100))
                detail = f"{detail} eta={format_seconds(eta)} progress={pct}%"
            print(progress_line(args.current, args.total, args.stage, "RUNNING", detail), flush=True)
            next_heartbeat = now + args.heartbeat_sec

        if not warning_emitted and args.warning_after_sec > 0 and elapsed >= args.warning_after_sec:
            print(
                progress_line(
                    args.current,
                    args.total,
                    args.stage,
                    "WARNING",
                    f"stage_running_long elapsed={format_seconds(elapsed)}",
                ),
                flush=True,
            )
            warning_emitted = True

        try:
            stream_name, line = q.get(timeout=0.2)
            if line is None:
                finished_streams.add(stream_name)
            else:
                prefix = "STDERR" if stream_name == "stderr" else "STDOUT"
                print(f"[{prefix}] {line}", flush=True)
        except Empty:
            pass

        if proc.poll() is not None and len(finished_streams) >= 2:
            break

    code = proc.returncode
    total_elapsed = time.time() - start_ts
    if code == 0:
        print(
            progress_line(
                args.current,
                args.total,
                args.stage,
                "DONE",
                f"exit=0 elapsed={format_seconds(total_elapsed)}",
            ),
            flush=True,
        )
    else:
        print(
            progress_line(
                args.current,
                args.total,
                args.stage,
                "ERROR",
                f"exit={code} elapsed={format_seconds(total_elapsed)}",
            ),
            flush=True,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
