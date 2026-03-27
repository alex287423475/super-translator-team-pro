import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(cmd, cwd=None):
    result = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


def assert_ok(condition, message):
    if not condition:
        raise AssertionError(message)

def parse_json_line(output: str):
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise AssertionError(f"No JSON summary found in output:\n{output}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        source = tmp / "input.md"
        source.write_text(
            "# Demo\n\nUse `foo()` here.\n\n```python\nprint('hi')\n```\n\n<span>label</span>\n",
            encoding="utf-8",
        )

        code, out, err = run([sys.executable, str(ROOT / "scripts" / "placeholder.py"), str(source)])
        assert_ok(code == 0, f"placeholder.py failed:\n{err}")
        assert_ok("{{PH_INLINE_" in out, "placeholder.py did not protect inline code")
        mapping_path = tmp / "input.mapping.json"
        assert_ok(mapping_path.exists(), "placeholder.py did not create mapping file")

        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "progress_line.py"),
                "--current",
                "1",
                "--total",
                "6",
                "--stage",
                "preprocessing",
                "--status",
                "START",
                "--detail",
                "placeholder + splitter",
            ]
        )
        assert_ok(code == 0, f"progress_line.py failed:\n{err}")
        assert_ok(out.strip().startswith("[PROGRESS] 1/6 preprocessing | START"), "progress line format invalid")

        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "progress_eta.py"),
                "--current",
                "2",
                "--total",
                "6",
                "--stage",
                "draft_translation",
                "--elapsed-sec",
                "40",
                "--expected-sec",
                "120",
            ]
        )
        assert_ok(code == 0, f"progress_eta.py failed:\n{err}")
        assert_ok("eta=1m20s" in out, "progress_eta.py ETA output invalid")

        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_with_progress.py"),
                "--current",
                "1",
                "--total",
                "6",
                "--stage",
                "preprocessing",
                "--heartbeat-sec",
                "1",
                "--expected-sec",
                "2",
                "--",
                sys.executable,
                "-c",
                "import time; print('phase-a'); time.sleep(1.2); print('phase-b')",
            ]
        )
        assert_ok(code == 0, f"run_with_progress.py failed:\nstdout:\n{out}\nstderr:\n{err}")
        assert_ok("[PROGRESS] 1/6 preprocessing | START" in out, "run_with_progress missing START")
        assert_ok("[PROGRESS] 1/6 preprocessing | RUNNING" in out, "run_with_progress missing RUNNING")
        assert_ok("[PROGRESS] 1/6 preprocessing | DONE" in out, "run_with_progress missing DONE")
        assert_ok("unbuffered=1" in out, "run_with_progress should report unbuffered mode")
        assert_ok("[STDOUT] phase-a" in out and "[STDOUT] phase-b" in out, "run_with_progress missing child output")

        draft_v1 = tmp / "Draft_v1.md"
        draft_v2 = tmp / "Draft_v2.md"
        draft_v1.write_text(
            "# Title\n\n- item one\n- item two\n\n| col1 | col2 |\n| --- | --- |\n| a | b |\n\n```python\nprint('x')\n```\n\nHello world\n",
            encoding="utf-8",
        )
        draft_v2.write_text(
            "# 标题\n\n- 条目一\n- 条目二\n\n| 列1 | 列2 |\n| --- | --- |\n| 甲 | 乙 |\n\n```python\nprint('x')\n```\n\n你好世界\n",
            encoding="utf-8",
        )

        code, out, err = run(
            [sys.executable, str(ROOT / "hooks" / "calc_diff.py"), str(draft_v1), str(draft_v2)]
        )
        assert_ok(code == 0, f"calc_diff.py failed:\n{err}")
        float(out.strip())

        diff_html = tmp / "diff.html"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "diff_generator.py"),
                str(draft_v1),
                str(draft_v2),
                str(diff_html),
            ]
        )
        assert_ok(code == 0, f"diff_generator.py failed:\n{err}")
        assert_ok(diff_html.exists(), "diff_generator.py did not create output html")

        with mapping_path.open("r", encoding="utf-8") as handle:
            mapping = json.load(handle)
        inline_placeholder = next(
            (key for key, value in mapping.items() if value == "`foo()`"),
            None,
        )
        assert_ok(inline_placeholder is not None, "mapping file missing inline code placeholder")

        processed = tmp / "Draft_v2_with_placeholder.md"
        processed.write_text(f"Result {inline_placeholder}\n", encoding="utf-8")
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "format_fix.py"),
                str(processed),
                str(mapping_path),
            ]
        )
        assert_ok(code == 0, f"format_fix.py failed:\nstdout:\n{out}\nstderr:\n{err}")
        assert_ok("`foo()`" in out, "format_fix.py did not restore placeholder content")

        final_md = tmp / "Final_Temp.md"
        final_md.write_text(out, encoding="utf-8")
        code, out, err = run(
            [sys.executable, str(ROOT / "hooks" / "syntax_check.py"), str(final_md)]
        )
        assert_ok(code == 0, f"syntax_check.py failed:\n{err}")
        assert_ok(out.strip() == "OK", "syntax_check.py did not return OK")

        manifest_dir = tmp / "chunks"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "splitter.py"),
                str(source),
                str(manifest_dir),
                "40",
            ]
        )
        assert_ok(code == 0, f"splitter.py failed:\n{err}")
        manifest = json.loads(out)
        assert_ok(manifest["chunk_count"] >= 1, "splitter.py returned empty chunk manifest")

        terminology = tmp / "terminology.json"
        terminology.write_text(
            json.dumps(
                {
                    "meta": {"description": "test glossary"},
                    "terms": [
                        {"source": "API", "target": "API"},
                        {"source": "Endpoint", "target": "端点"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        test_config = tmp / "config.json"
        test_config.write_text(
            json.dumps({"source_language": "en-US", "target_language": "zh-CN"}, ensure_ascii=False),
            encoding="utf-8",
        )
        glossary_forward = tmp / "glossary.forward.json"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_glossary.py"),
                "--terminology",
                str(terminology),
                "--config",
                str(test_config),
                "--out",
                str(glossary_forward),
            ]
        )
        assert_ok(code == 0, f"prepare_glossary.py forward failed:\nstdout:\n{out}\nstderr:\n{err}")
        gf_summary = parse_json_line(out)
        assert_ok(gf_summary["collision_count"] == 0, "forward glossary should have no collisions")
        gf = json.loads(glossary_forward.read_text(encoding="utf-8"))
        assert_ok(gf["map"].get("Endpoint") == "端点", "forward glossary direction invalid")

        glossary_reverse = tmp / "glossary.reverse.json"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_glossary.py"),
                "--terminology",
                str(terminology),
                "--source-lang",
                "zh-CN",
                "--target-lang",
                "en-US",
                "--out",
                str(glossary_reverse),
            ]
        )
        assert_ok(code == 0, f"prepare_glossary.py reverse failed:\nstdout:\n{out}\nstderr:\n{err}")
        gr_summary = parse_json_line(out)
        assert_ok(gr_summary["collision_count"] == 0, "reverse glossary should have no collisions in test data")
        gr = json.loads(glossary_reverse.read_text(encoding="utf-8"))
        assert_ok(gr["map"].get("端点") == "Endpoint", "reverse glossary direction invalid")

        # Auto domain routing scenario: ecommerce-like input should select ecommerce terminology.
        auto_input = tmp / "auto_ecom.md"
        auto_input.write_text(
            "Amazon listing with SKU variants, shipping fee, return policy and storefront updates.\n",
            encoding="utf-8",
        )
        glossary_auto = tmp / "glossary.auto.json"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "prepare_glossary.py"),
                "--domain",
                "auto",
                "--input-file",
                str(auto_input),
                "--default-terminology",
                str(terminology),
                "--ecommerce-terminology",
                str(ROOT / "references" / "terminology.ecommerce.json"),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--out",
                str(glossary_auto),
            ]
        )
        assert_ok(code == 0, f"prepare_glossary.py auto domain failed:\nstdout:\n{out}\nstderr:\n{err}")
        ga_summary = parse_json_line(out)
        assert_ok(ga_summary["selected_domain"] == "ecommerce", "auto domain routing should select ecommerce")
        ga = json.loads(glossary_auto.read_text(encoding="utf-8"))
        assert_ok(ga["map"].get("SKU") == "SKU", "auto domain glossary should contain ecommerce terms")

        xliff_path = tmp / "trados" / "segments.xliff"
        tmx_path = tmp / "trados" / "memory.tmx"
        csv_path = tmp / "trados" / "segment_map.csv"
        qa_csv = tmp / "trados" / "qa_flags.csv"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "trados_export.py"),
                str(draft_v1),
                str(draft_v2),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--xliff-out",
                str(xliff_path),
                "--tmx-out",
                str(tmx_path),
                "--csv-out",
                str(csv_path),
                "--qa-csv-out",
                str(qa_csv),
            ]
        )
        assert_ok(code == 0, f"trados_export.py failed:\nstdout:\n{out}\nstderr:\n{err}")
        summary0 = parse_json_line(out)
        assert_ok(xliff_path.exists(), "trados_export.py did not create XLIFF")
        assert_ok(tmx_path.exists(), "trados_export.py did not create TMX")
        assert_ok(csv_path.exists(), "trados_export.py did not create CSV map")
        assert_ok(qa_csv.exists(), "trados_export.py did not create QA CSV")
        xliff_content = xliff_path.read_text(encoding="utf-8")
        tmx_content = tmx_path.read_text(encoding="utf-8")
        csv_content = csv_path.read_text(encoding="utf-8")
        qa_csv_content = qa_csv.read_text(encoding="utf-8")
        assert_ok("<xliff" in xliff_content, "XLIFF content invalid")
        assert_ok("<tmx" in tmx_content, "TMX content invalid")
        assert_ok("```python" in xliff_content, "code fence block was not preserved in XLIFF")
        assert_ok("| col1 | col2 |" in xliff_content, "table row was not preserved in XLIFF")
        assert_ok('trans-unit id="seg-' in xliff_content, "stable trans-unit id missing in XLIFF")
        assert_ok('tuid="seg-' in tmx_content, "stable tuid missing in TMX")
        assert_ok("stable_id,source_en-US,target_zh-CN,change_type" in csv_content, "CSV header invalid")
        assert_ok(
            "stable_id,flag_type,severity,message,source_en-US,target_zh-CN" in qa_csv_content,
            "QA CSV header invalid",
        )
        assert_ok(summary0["qa_flags"] >= 0, "QA summary field missing")

        baseline_csv = tmp / "trados" / "segment_map.prev.csv"
        baseline_csv.write_text(csv_content, encoding="utf-8")
        draft_v2_incremental = tmp / "Draft_v2_incremental.md"
        draft_v2_incremental.write_text(
            "# 标题\n\n- 条目一\n- 条目二\n\n| 列1 | 列2 |\n| --- | --- |\n| 甲 | 乙 |\n\n```python\nprint('x')\n```\n\n你好世界（更新）\n",
            encoding="utf-8",
        )
        delta_xliff = tmp / "trados" / "segments.delta.xliff"
        delta_tmx = tmp / "trados" / "memory.delta.tmx"
        delta_csv = tmp / "trados" / "segment_map.delta.csv"
        removed_csv = tmp / "trados" / "removed_segments.csv"
        delta_qa_csv = tmp / "trados" / "qa_flags.delta.csv"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "trados_export.py"),
                str(draft_v1),
                str(draft_v2_incremental),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--baseline-csv",
                str(baseline_csv),
                "--only-changed",
                "--xliff-out",
                str(delta_xliff),
                "--tmx-out",
                str(delta_tmx),
                "--csv-out",
                str(delta_csv),
                "--removed-csv-out",
                str(removed_csv),
                "--qa-csv-out",
                str(delta_qa_csv),
            ]
        )
        assert_ok(code == 0, f"incremental trados_export failed:\nstdout:\n{out}\nstderr:\n{err}")
        summary = parse_json_line(out)
        assert_ok(summary["pairs"] == 1, "incremental export should only emit one changed segment")
        assert_ok(summary["removed_pairs"] == 0, "incremental export should not report removed segments here")
        delta_csv_content = delta_csv.read_text(encoding="utf-8")
        assert_ok("updated" in delta_csv_content, "incremental CSV should contain updated status")
        assert_ok(removed_csv.exists(), "removed CSV should be generated in incremental mode")
        removed_csv_content = removed_csv.read_text(encoding="utf-8")
        assert_ok("change_type" in removed_csv_content, "removed CSV header invalid")

        # Removed segment scenario: source version removed the final paragraph.
        draft_v1_removed = tmp / "Draft_v1_removed.md"
        draft_v1_removed.write_text(
            "# Title\n\n- item one\n- item two\n\n| col1 | col2 |\n| --- | --- |\n| a | b |\n\n```python\nprint('x')\n```\n",
            encoding="utf-8",
        )
        draft_v2_removed = tmp / "Draft_v2_removed.md"
        draft_v2_removed.write_text(
            "# 标题\n\n- 条目一\n- 条目二\n\n| 列1 | 列2 |\n| --- | --- |\n| 甲 | 乙 |\n\n```python\nprint('x')\n```\n",
            encoding="utf-8",
        )
        delta2_csv = tmp / "trados" / "segment_map.delta2.csv"
        removed2_csv = tmp / "trados" / "removed_segments2.csv"
        qa2_csv = tmp / "trados" / "qa_flags2.csv"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "trados_export.py"),
                str(draft_v1_removed),
                str(draft_v2_removed),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--baseline-csv",
                str(baseline_csv),
                "--only-changed",
                "--csv-out",
                str(delta2_csv),
                "--xliff-out",
                str(tmp / "trados" / "segments.delta2.xliff"),
                "--tmx-out",
                str(tmp / "trados" / "memory.delta2.tmx"),
                "--removed-csv-out",
                str(removed2_csv),
                "--qa-csv-out",
                str(qa2_csv),
            ]
        )
        assert_ok(code == 0, f"removed scenario export failed:\nstdout:\n{out}\nstderr:\n{err}")
        summary2 = parse_json_line(out)
        assert_ok(summary2["removed_pairs"] >= 1, "removed segments should be reported")
        removed2_content = removed2_csv.read_text(encoding="utf-8")
        assert_ok("removed" in removed2_content, "removed CSV should contain removed status")

        # QA flag scenario: empty target should be reported as missing_target.
        draft_v2_qa = tmp / "Draft_v2_qa.md"
        draft_v2_qa.write_text(
            "# 标题\n\n- 条目一\n- 条目二\n\n| 列1 | 列2 |\n| --- | --- |\n| 甲 | 乙 |\n\n```python\nprint('x')\n```\n\n\n",
            encoding="utf-8",
        )
        qa3_csv = tmp / "trados" / "qa_flags3.csv"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "trados_export.py"),
                str(draft_v1),
                str(draft_v2_qa),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--qa-csv-out",
                str(qa3_csv),
                "--csv-out",
                str(tmp / "trados" / "segment_map3.csv"),
                "--xliff-out",
                str(tmp / "trados" / "segments3.xliff"),
                "--tmx-out",
                str(tmp / "trados" / "memory3.tmx"),
            ]
        )
        assert_ok(code == 0, f"QA scenario export failed:\nstdout:\n{out}\nstderr:\n{err}")
        qa3_content = qa3_csv.read_text(encoding="utf-8")
        assert_ok("missing_target" in qa3_content, "QA CSV should include missing_target flag")

        # Terminology QA scenario: source term exists but target misses glossary target.
        term_source = tmp / "Term_Source.md"
        term_target = tmp / "Term_Target.md"
        term_source.write_text("Use Endpoint and API in this request.\n", encoding="utf-8")
        term_target.write_text("请在这个请求中使用终端和 API。\n", encoding="utf-8")
        term_glossary = tmp / "glossary.active.json"
        term_glossary.write_text(
            json.dumps(
                {
                    "source_language": "en-US",
                    "target_language": "zh-CN",
                    "map": {"Endpoint": "端点", "API": "API"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        qa4_csv = tmp / "trados" / "qa_flags4.csv"
        code, out, err = run(
            [
                sys.executable,
                str(ROOT / "scripts" / "trados_export.py"),
                str(term_source),
                str(term_target),
                "--source-lang",
                "en-US",
                "--target-lang",
                "zh-CN",
                "--glossary-json",
                str(term_glossary),
                "--qa-csv-out",
                str(qa4_csv),
                "--csv-out",
                str(tmp / "trados" / "segment_map4.csv"),
                "--xliff-out",
                str(tmp / "trados" / "segments4.xliff"),
                "--tmx-out",
                str(tmp / "trados" / "memory4.tmx"),
            ]
        )
        assert_ok(code == 0, f"terminology QA export failed:\nstdout:\n{out}\nstderr:\n{err}")
        qa4_content = qa4_csv.read_text(encoding="utf-8")
        assert_ok("term_inconsistency" in qa4_content, "QA CSV should include term_inconsistency flag")

    print("SELF_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
