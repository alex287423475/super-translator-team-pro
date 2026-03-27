import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_TERMINOLOGY = "references/terminology.json"
ECOMMERCE_TERMINOLOGY = "references/terminology.ecommerce.json"

ECOMMERCE_STRONG_KEYWORDS = [
    "amazon",
    "temu",
    "shopee",
    "lazada",
    "aliexpress",
    "shopify",
    "etsy",
    "ebay",
    "listing",
    "sku",
    "fba",
    "fbm",
    "dropshipping",
    "cross-border e-commerce",
    "跨境电商",
    "商品标题",
    "卖点",
    "店铺",
    "物流单号",
    "退货政策",
    "清关",
]

ECOMMERCE_WEAK_KEYWORDS = [
    "product title",
    "bullet points",
    "product description",
    "variant",
    "inventory",
    "restock",
    "minimum order quantity",
    "lead time",
    "fulfillment",
    "overseas warehouse",
    "shipping fee",
    "delivery time",
    "tracking number",
    "hs code",
    "incoterms",
    "refund",
    "exchange",
    "after-sales service",
    "warranty",
    "brand registry",
    "storefront",
    "conversion rate",
    "click-through rate",
    "gmv",
    "aov",
    "coupon",
    "limited-time offer",
    "畅销款",
    "变体",
    "库存",
    "补货",
    "履约",
    "海外仓",
    "运费",
    "配送时效",
    "知识产权",
    "品牌备案",
    "转化率",
    "点击率",
    "客单价",
    "成交总额",
    "优惠券",
    "限时优惠",
]


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


def detect_domain_from_text(input_file: Path) -> Tuple[str, int, List[str]]:
    if not input_file.exists():
        return "default", 0, []

    text = input_file.read_text(encoding="utf-8-sig", errors="replace").lower()
    score = 0
    matches: List[str] = []

    for kw in ECOMMERCE_STRONG_KEYWORDS:
        if kw in text:
            score += 2
            matches.append(kw)
    for kw in ECOMMERCE_WEAK_KEYWORDS:
        if kw in text:
            score += 1
            matches.append(kw)

    if score >= 3:
        return "ecommerce", score, matches[:20]
    return "default", score, matches[:20]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare directional glossary map from references/terminology.json for current language direction."
    )
    parser.add_argument(
        "--terminology",
        default="",
        help="Path to terminology JSON. If omitted, selected by --domain or defaults.",
    )
    parser.add_argument(
        "--domain",
        choices=["default", "ecommerce", "auto"],
        default="default",
        help="Glossary domain. 'auto' uses --input-file keyword routing (default: default).",
    )
    parser.add_argument(
        "--input-file",
        default="",
        help="Optional source markdown/text file used by --domain auto for keyword routing.",
    )
    parser.add_argument(
        "--default-terminology",
        default=DEFAULT_TERMINOLOGY,
        help=f"Default-domain terminology path (default: {DEFAULT_TERMINOLOGY})",
    )
    parser.add_argument(
        "--ecommerce-terminology",
        default=ECOMMERCE_TERMINOLOGY,
        help=f"Ecommerce-domain terminology path (default: {ECOMMERCE_TERMINOLOGY})",
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
    default_terminology_path = Path(args.default_terminology)
    ecommerce_terminology_path = Path(args.ecommerce_terminology)
    input_path = Path(args.input_file) if args.input_file else Path()
    auto_score = 0
    auto_matches: List[str] = []

    selected_domain = args.domain
    if selected_domain == "auto":
        if not args.input_file:
            print(
                "WARNING: --domain auto used without --input-file, fallback to default domain",
                file=sys.stderr,
            )
            selected_domain = "default"
        else:
            selected_domain, auto_score, auto_matches = detect_domain_from_text(input_path)

    if args.terminology:
        terminology_path = Path(args.terminology)
    elif selected_domain == "ecommerce":
        terminology_path = ecommerce_terminology_path
    else:
        terminology_path = default_terminology_path

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
                "selected_domain": selected_domain,
                "terminology": str(terminology_path),
                "auto_score": auto_score,
                "auto_matches": auto_matches,
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
