import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

PLACEHOLDER_RE = re.compile(r"\{\{PH_[A-Z_0-9]+\}\}")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").lstrip("\ufeff")


def normalize_segment(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}#{1,6}\s+\S", line))


def _is_unordered_list(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}[-*+]\s+\S", line))


def _is_ordered_list(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}\d+\.\s+\S", line))


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def split_segments(text: str) -> List[str]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: List[str] = []
    paragraph: List[str] = []
    in_fence = False
    fence_lines: List[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            joined = normalize_segment(" ".join(part.strip() for part in paragraph if part.strip()))
            if joined:
                segments.append(joined)
            paragraph.clear()

    for line in lines:
        stripped = line.strip()

        if line.lstrip().startswith("```"):
            if not in_fence:
                flush_paragraph()
                in_fence = True
                fence_lines = [line]
            else:
                fence_lines.append(line)
                block = "\n".join(fence_lines).strip()
                if block:
                    segments.append(block)
                in_fence = False
                fence_lines = []
            continue

        if in_fence:
            fence_lines.append(line)
            continue

        if not stripped:
            flush_paragraph()
            continue

        if _is_heading(line) or _is_unordered_list(line) or _is_ordered_list(line) or _is_table_row(line):
            flush_paragraph()
            segments.append(normalize_segment(line))
            continue

        paragraph.append(line)

    flush_paragraph()
    if in_fence and fence_lines:
        block = "\n".join(fence_lines).strip()
        if block:
            segments.append(block)
    return [seg for seg in segments if seg]


def align_segments(source: List[str], target: List[str]) -> Tuple[List[Tuple[str, str]], List[str]]:
    warnings: List[str] = []
    if len(source) != len(target):
        warnings.append(
            f"segment count mismatch: source={len(source)} target={len(target)}; unmatched segments will be emitted with empty counterpart"
        )

    total = max(len(source), len(target))
    pairs: List[Tuple[str, str]] = []
    for idx in range(total):
        src = source[idx] if idx < len(source) else ""
        tgt = target[idx] if idx < len(target) else ""
        if not src and not tgt:
            continue
        pairs.append((src, tgt))
    return pairs, warnings


def build_stable_unit_ids(pairs: List[Tuple[str, str]]) -> List[str]:
    seen: Dict[str, int] = {}
    unit_ids: List[str] = []
    for idx, (src, _tgt) in enumerate(pairs, start=1):
        key_source = src if src else f"_empty_source_{idx}"
        base = hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:12]
        count = seen.get(base, 0) + 1
        seen[base] = count
        suffix = f"-{count}" if count > 1 else ""
        unit_ids.append(f"seg-{base}{suffix}")
    return unit_ids


def load_baseline_map(path: Path) -> Dict[str, Tuple[str, str]]:
    baseline: Dict[str, Tuple[str, str]] = {}
    if not path.exists():
        return baseline

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        source_key = None
        target_key = None
        for key in reader.fieldnames or []:
            if key.startswith("source_"):
                source_key = key
            if key.startswith("target_"):
                target_key = key
        if source_key is None or target_key is None:
            return baseline

        for row in reader:
            stable_id = (row.get("stable_id") or "").strip()
            if not stable_id:
                continue
            src = row.get(source_key, "") or ""
            tgt = row.get(target_key, "") or ""
            baseline[stable_id] = (src, tgt)
    return baseline


def classify_changes(
    unit_ids: List[str], pairs: List[Tuple[str, str]], baseline: Dict[str, Tuple[str, str]]
) -> List[str]:
    def canonical(value: str) -> str:
        return value.replace("\r\n", "\n").replace("\r", "\n").strip()

    statuses: List[str] = []
    for unit_id, pair in zip(unit_ids, pairs):
        old = baseline.get(unit_id)
        if old is None:
            statuses.append("new")
        elif canonical(old[0]) != canonical(pair[0]) or canonical(old[1]) != canonical(pair[1]):
            statuses.append("updated")
        else:
            statuses.append("unchanged")
    return statuses


def detect_removed_ids(unit_ids: List[str], baseline: Dict[str, Tuple[str, str]]) -> List[str]:
    current = set(unit_ids)
    removed = [stable_id for stable_id in baseline.keys() if stable_id not in current]
    removed.sort()
    return removed


def count_code_fences(text: str) -> int:
    return len(re.findall(r"(?m)^```", text))


def looks_like_translatable_text(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def load_glossary_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}

    # Preferred format from prepare_glossary.py: {"map": {...}}
    direct_map = data.get("map")
    if isinstance(direct_map, dict):
        out: Dict[str, str] = {}
        for k, v in direct_map.items():
            key = str(k or "").strip()
            value = str(v or "").strip()
            if key and value:
                out[key] = value
        return out

    # Fallback format: {"terms":[{"source":"...","target":"..."}]}
    terms = data.get("terms")
    if isinstance(terms, list):
        out = {}
        for item in terms:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").strip()
            target = str(item.get("target") or "").strip()
            if source and target:
                out[source] = target
        return out
    return {}


def contains_term(text: str, term: str) -> bool:
    if not text or not term:
        return False
    # For Latin-like terms, prefer word-boundary matching.
    if re.search(r"[A-Za-z0-9]", term):
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return term in text


def build_qa_flags(
    unit_ids: List[str], pairs: List[Tuple[str, str]], glossary_map: Dict[str, str]
) -> List[Tuple[str, str, str, str, str, str]]:
    flags: List[Tuple[str, str, str, str, str, str]] = []
    for unit_id, (src, tgt) in zip(unit_ids, pairs):
        src_norm = normalize_segment(src)
        tgt_norm = normalize_segment(tgt)
        src_len = len(src_norm)
        tgt_len = len(tgt_norm)

        if src_norm and not tgt_norm:
            flags.append((unit_id, "missing_target", "error", "target segment is empty", src, tgt))

        if src_norm and tgt_norm and src_norm == tgt_norm and looks_like_translatable_text(src_norm):
            flags.append((unit_id, "unchanged_text", "warning", "source and target are identical", src, tgt))

        if PLACEHOLDER_RE.search(tgt_norm):
            flags.append((unit_id, "placeholder_leak", "error", "target still contains placeholder tokens", src, tgt))

        if tgt_len > 0 and src_len > 0:
            ratio = tgt_len / max(src_len, 1)
            if ratio < 0.2:
                flags.append(
                    (
                        unit_id,
                        "length_too_short",
                        "warning",
                        f"target/source length ratio is very small ({ratio:.2f})",
                        src,
                        tgt,
                    )
                )
            elif ratio > 5.0:
                flags.append(
                    (
                        unit_id,
                        "length_too_long",
                        "warning",
                        f"target/source length ratio is very large ({ratio:.2f})",
                        src,
                        tgt,
                    )
                )

        if count_code_fences(src_norm) % 2 != count_code_fences(tgt_norm) % 2:
            flags.append(
                (
                    unit_id,
                    "code_fence_mismatch",
                    "warning",
                    "source/target code fence parity differs",
                    src,
                    tgt,
                )
            )

        if glossary_map and src_norm and tgt_norm and not src_norm.startswith("```"):
            for source_term, target_term in glossary_map.items():
                if contains_term(src_norm, source_term) and not contains_term(tgt_norm, target_term):
                    flags.append(
                        (
                            unit_id,
                            "term_inconsistency",
                            "warning",
                            f"expected terminology '{source_term}' -> '{target_term}'",
                            src,
                            tgt,
                        )
                    )
    return flags


def select_records(
    unit_ids: List[str], pairs: List[Tuple[str, str]], statuses: List[str], only_changed: bool
) -> Tuple[List[str], List[Tuple[str, str]], List[str]]:
    if not only_changed:
        return unit_ids, pairs, statuses

    selected_ids: List[str] = []
    selected_pairs: List[Tuple[str, str]] = []
    selected_statuses: List[str] = []
    for unit_id, pair, status in zip(unit_ids, pairs, statuses):
        if status == "unchanged":
            continue
        selected_ids.append(unit_id)
        selected_pairs.append(pair)
        selected_statuses.append(status)
    return selected_ids, selected_pairs, selected_statuses


def write_xliff(
    pairs: List[Tuple[str, str]],
    unit_ids: List[str],
    out_path: Path,
    source_lang: str,
    target_lang: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write('<xliff version="1.2">\n')
        handle.write(
            f'  <file original="super-translator-team-pro" source-language="{html.escape(source_lang)}" target-language="{html.escape(target_lang)}" datatype="plaintext">\n'
        )
        handle.write("    <body>\n")
        for unit_id, (src, tgt) in zip(unit_ids, pairs):
            handle.write(f'      <trans-unit id="{html.escape(unit_id)}" xml:space="preserve">\n')
            handle.write(f"        <source>{html.escape(src)}</source>\n")
            handle.write(f"        <target>{html.escape(tgt)}</target>\n")
            handle.write("      </trans-unit>\n")
        handle.write("    </body>\n")
        handle.write("  </file>\n")
        handle.write("</xliff>\n")


def write_tmx(
    pairs: List[Tuple[str, str]],
    unit_ids: List[str],
    out_path: Path,
    source_lang: str,
    target_lang: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    root = ET.Element("tmx", version="1.4")
    ET.SubElement(
        root,
        "header",
        {
            "creationtool": "super-translator-team-pro",
            "creationtoolversion": "5.0",
            "segtype": "paragraph",
            "adminlang": "en-us",
            "srclang": source_lang,
            "datatype": "PlainText",
            "creationdate": now,
        },
    )
    body = ET.SubElement(root, "body")
    for unit_id, (src, tgt) in zip(unit_ids, pairs):
        tu = ET.SubElement(body, "tu", {"tuid": unit_id})
        tuv_src = ET.SubElement(tu, "tuv", {"{http://www.w3.org/XML/1998/namespace}lang": source_lang})
        seg_src = ET.SubElement(tuv_src, "seg")
        seg_src.text = src

        tuv_tgt = ET.SubElement(tu, "tuv", {"{http://www.w3.org/XML/1998/namespace}lang": target_lang})
        seg_tgt = ET.SubElement(tuv_tgt, "seg")
        seg_tgt.text = tgt

    tree = ET.ElementTree(root)
    ET.register_namespace("xml", "http://www.w3.org/XML/1998/namespace")
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)


def write_segment_map_csv(
    pairs: List[Tuple[str, str]],
    unit_ids: List[str],
    statuses: List[str],
    out_path: Path,
    source_lang: str,
    target_lang: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stable_id", f"source_{source_lang}", f"target_{target_lang}", "change_type"])
        for unit_id, (src, tgt), status in zip(unit_ids, pairs, statuses):
            writer.writerow([unit_id, src, tgt, status])


def write_removed_map_csv(
    removed_ids: List[str],
    baseline: Dict[str, Tuple[str, str]],
    out_path: Path,
    source_lang: str,
    target_lang: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stable_id", f"source_{source_lang}", f"target_{target_lang}", "change_type"])
        for stable_id in removed_ids:
            src, tgt = baseline.get(stable_id, ("", ""))
            writer.writerow([stable_id, src, tgt, "removed"])


def write_qa_flags_csv(
    flags: List[Tuple[str, str, str, str, str, str]],
    out_path: Path,
    source_lang: str,
    target_lang: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "stable_id",
                "flag_type",
                "severity",
                "message",
                f"source_{source_lang}",
                f"target_{target_lang}",
            ]
        )
        for row in flags:
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export bilingual source/target text into Trados-friendly XLIFF and TMX."
    )
    parser.add_argument("source_file", help="Path to source text (e.g. Draft_v1.md)")
    parser.add_argument("target_file", help="Path to translated text (e.g. Final_Output.md)")
    parser.add_argument("--source-lang", default="en-US", help="Source language code, default: en-US")
    parser.add_argument("--target-lang", default="zh-CN", help="Target language code, default: zh-CN")
    parser.add_argument("--xliff-out", default="trados/segments.xliff", help="Output XLIFF path")
    parser.add_argument("--tmx-out", default="trados/memory.tmx", help="Output TMX path")
    parser.add_argument(
        "--csv-out",
        default="trados/segment_map.csv",
        help="Output CSV mapping path (stable_id, source, target)",
    )
    parser.add_argument(
        "--baseline-csv",
        default="",
        help="Optional previous segment_map.csv for incremental comparison",
    )
    parser.add_argument(
        "--only-changed",
        action="store_true",
        help="When baseline is provided, export only segments marked new/updated",
    )
    parser.add_argument(
        "--removed-csv-out",
        default="trados/removed_segments.csv",
        help="Output CSV path for baseline segments that were removed",
    )
    parser.add_argument(
        "--qa-csv-out",
        default="trados/qa_flags.csv",
        help="Output CSV path for QA flags (missing/unchanged/suspicious segments)",
    )
    parser.add_argument(
        "--fail-on-severity",
        choices=["none", "warning", "error"],
        default="none",
        help="Quality gate threshold. Default none (report only, never block).",
    )
    parser.add_argument(
        "--glossary-json",
        default="references/glossary.active.json",
        help="Optional glossary json for terminology consistency QA (default: references/glossary.active.json)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_file = Path(args.source_file)
    target_file = Path(args.target_file)

    if not source_file.exists():
        print(f"ERROR: source file not found: {source_file}", file=sys.stderr)
        return 1
    if not target_file.exists():
        print(f"ERROR: target file not found: {target_file}", file=sys.stderr)
        return 1

    source_segments = split_segments(load_text(source_file))
    target_segments = split_segments(load_text(target_file))
    pairs, warnings = align_segments(source_segments, target_segments)
    if not pairs:
        print("ERROR: no segments to export", file=sys.stderr)
        return 1

    unit_ids = build_stable_unit_ids(pairs)
    baseline = load_baseline_map(Path(args.baseline_csv)) if args.baseline_csv else {}
    statuses = classify_changes(unit_ids, pairs, baseline)
    removed_ids = detect_removed_ids(unit_ids, baseline) if baseline else []
    selected_ids, selected_pairs, selected_statuses = select_records(
        unit_ids, pairs, statuses, args.only_changed and bool(baseline)
    )
    if args.only_changed and not baseline:
        warnings.append("only-changed requested without valid baseline; exporting all segments")

    xliff_path = Path(args.xliff_out)
    tmx_path = Path(args.tmx_out)
    csv_path = Path(args.csv_out)
    removed_csv_path = Path(args.removed_csv_out)
    qa_csv_path = Path(args.qa_csv_out)
    glossary_path = Path(args.glossary_json)
    write_xliff(selected_pairs, selected_ids, xliff_path, args.source_lang, args.target_lang)
    write_tmx(selected_pairs, selected_ids, tmx_path, args.source_lang, args.target_lang)
    write_segment_map_csv(
        selected_pairs, selected_ids, selected_statuses, csv_path, args.source_lang, args.target_lang
    )
    if baseline:
        write_removed_map_csv(removed_ids, baseline, removed_csv_path, args.source_lang, args.target_lang)
    glossary_map = load_glossary_map(glossary_path)
    if args.glossary_json and not glossary_map:
        warnings.append(
            f"glossary map unavailable or empty: {glossary_path}; terminology consistency check skipped"
        )
    qa_flags = build_qa_flags(selected_ids, selected_pairs, glossary_map)
    write_qa_flags_csv(qa_flags, qa_csv_path, args.source_lang, args.target_lang)

    changed_count = sum(1 for status in statuses if status != "unchanged")

    summary = {
        "pairs": len(selected_pairs),
        "source_segments": len(source_segments),
        "target_segments": len(target_segments),
        "changed_pairs": changed_count,
        "removed_pairs": len(removed_ids),
        "stable_ids": True,
        "incremental": bool(baseline),
        "xliff": str(xliff_path),
        "tmx": str(tmx_path),
        "csv": str(csv_path),
        "removed_csv": str(removed_csv_path) if baseline else "",
        "qa_csv": str(qa_csv_path),
        "qa_flags": len(qa_flags),
        "glossary_terms": len(glossary_map),
        "fail_on_severity": args.fail_on_severity,
    }
    print(json.dumps(summary, ensure_ascii=False))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    # Default behavior is report-only and never blocks.
    if args.fail_on_severity != "none":
        severity_rank = {"warning": 1, "error": 2}
        threshold = severity_rank[args.fail_on_severity]
        max_found = 0
        for _unit_id, _flag_type, severity, _message, _src, _tgt in qa_flags:
            max_found = max(max_found, severity_rank.get(severity, 0))
        if max_found >= threshold:
            print(
                f"ERROR: quality gate failed (threshold={args.fail_on_severity}, max_found={'error' if max_found == 2 else 'warning'})",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
