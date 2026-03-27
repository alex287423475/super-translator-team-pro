import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_languages(config_path: Path) -> Tuple[str, str]:
    if not config_path.exists():
        return "en-US", "zh-CN"
    cfg = load_json(config_path)
    src = (cfg.get("source_language") or "en-US").strip()
    tgt = (cfg.get("target_language") or "zh-CN").strip()
    return src, tgt


def normalized_lang_prefix(lang: str) -> str:
    lang = (lang or "").strip().lower()
    if not lang:
        return ""
    return lang.split("-")[0]


def should_reverse(source_lang: str, target_lang: str) -> bool:
    src = normalized_lang_prefix(source_lang)
    tgt = normalized_lang_prefix(target_lang)
    # terminology.json is maintained as English -> Chinese pairs by default.
    return src.startswith("zh") and tgt.startswith("en")


def build_map(terms: List[dict], reverse: bool) -> Tuple[Dict[str, str], int, int, List[dict]]:
    mapping: Dict[str, str] = {}
    skipped = 0
    collisions = 0
    collision_examples: List[dict] = []
    for item in terms:
        source = (item.get("source") or "").strip()
        target = (item.get("target") or "").strip()
        if not source or not target:
            skipped += 1
            continue
        left, right = (target, source) if reverse else (source, target)
        if not left or not right:
            skipped += 1
            continue
        if left in mapping:
            if mapping[left] != right:
                collisions += 1
                if len(collision_examples) < 10:
                    collision_examples.append(
                        {"term": left, "kept": mapping[left], "dropped": right}
                    )
            # keep first mapping to make output deterministic
            continue
        mapping[left] = right
    return mapping, skipped, collisions, collision_examples


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare directional glossary map from references/terminology.json for current language direction."
    )
    parser.add_argument(
        "--terminology",
        default="references/terminology.json",
        help="Path to terminology JSON (default: references/terminology.json)",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config JSON for default source/target language (default: config.json)",
    )
    parser.add_argument(
        "--source-lang",
        default="",
        help="Source language override, e.g. en-US or zh-CN",
    )
    parser.add_argument(
        "--target-lang",
        default="",
        help="Target language override, e.g. zh-CN or en-US",
    )
    parser.add_argument(
        "--out",
        default="references/glossary.active.json",
        help="Output glossary map JSON path (default: references/glossary.active.json)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    terminology_path = Path(args.terminology)
    config_path = Path(args.config)
    out_path = Path(args.out)

    if not terminology_path.exists():
        print(f"ERROR: terminology file not found: {terminology_path}", file=sys.stderr)
        return 1

    cfg_source, cfg_target = read_languages(config_path)
    source_lang = (args.source_lang or cfg_source).strip()
    target_lang = (args.target_lang or cfg_target).strip()
    reverse = should_reverse(source_lang, target_lang)

    data = load_json(terminology_path)
    terms = data.get("terms") or []
    if not isinstance(terms, list):
        print("ERROR: terminology JSON must contain a list field named 'terms'", file=sys.stderr)
        return 1

    mapping, skipped_count, collision_count, collision_examples = build_map(terms, reverse=reverse)
    out = {
        "source_language": source_lang,
        "target_language": target_lang,
        "direction": f"{source_lang}->{target_lang}",
        "reversed_from_default_en_zh": reverse,
        "term_count": len(mapping),
        "collision_count": collision_count,
        "collision_examples": collision_examples,
        "map": mapping,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "direction": out["direction"],
                "reversed": reverse,
                "term_count": len(mapping),
                "skipped_count": skipped_count,
                "collision_count": collision_count,
                "collision_examples": collision_examples,
                "out": str(out_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
