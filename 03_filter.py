# -*- coding: utf-8 -*-
"""
03_filter.py

Stage 3: Filter the merged JSON produced in Stage 2.

Filtering options
-----------------
  --keywords / --keywords-file   Keep only elements containing any of the given keywords.
  --allowed-types                Keep only listed element types (e.g. paragraph heading).
  --min-words                    Minimum number of alphabetic tokens required.
  --require-alphabetic           Drop elements with no letters.
  --max-numeric-ratio            Drop elements whose token-numeric ratio exceeds this value.
  --context                      Include adaptive context window around keyword matches.
  --group-by-heading             Output sections grouped by heading rather than a flat list.
  --start-keyword / --end-keyword  Extract only the range between two heading keywords.

Output
------
Both a structured JSON (with element metadata) and a text-only JSON are written
unless you pass --no-text-only or --no-structured.

Usage:
  python 03_filter.py --input merged_output.json --output-folder ./filtered \\
      --keywords "word one" "word two" --min-words 10 --context
  python 03_filter.py --input merged_output.json --output-folder ./filtered \\
      --keywords-file examples/keywords_example.json --min-words 10 --context
"""

import argparse
import json
import os
from datetime import datetime

from utils import clean_text


class PDFFilter:
    """Apply configurable filters to a structured PDF extraction dataset."""

    def __init__(self, input_json_file: str):
        with open(input_json_file, "r", encoding="utf-8") as fh:
            self.docs = json.load(fh)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_all_element_types(self) -> list:
        types = set()
        for doc in self.docs:
            for elem in doc.get("Elements", []):
                if elem.get("type"):
                    types.add(elem["type"])
        return sorted(types)

    def generate_filename(self, folder: str, prefix: str, **params) -> str:
        parts = [prefix]
        if params.get("keywords"):
            kw_str = "_".join(params["keywords"][:3])
            parts.append(f"kw_{kw_str}")
        if params.get("min_words", 1) > 1:
            parts.append(f"minw_{params['min_words']}")
        if params.get("max_numeric_ratio", 1.0) < 1.0:
            parts.append(f"maxnum_{int(params['max_numeric_ratio'] * 100)}")
        if params.get("require_alphabetic"):
            parts.append("alpha")
        if params.get("context"):
            parts.append("context")
        if params.get("group_by_heading"):
            parts.append("grouped")
        if params.get("start_keyword") and params.get("end_keyword"):
            parts.append(f"range_{params['start_keyword'][:10]}_{params['end_keyword'][:10]}")
        parts.append(datetime.now().strftime("%d%m%Y"))
        return os.path.join(folder, "_".join(parts) + ".json")

    # ------------------------------------------------------------------
    # Core filter
    # ------------------------------------------------------------------

    def filter_documents(
        self,
        output_json_file: str = None,
        output_text_only_file: str = None,
        auto_generate_filenames: bool = False,
        output_folder: str = None,
        extract_between_headings: bool = False,
        start_keyword: str = None,
        end_keyword: str = None,
        min_words: int = 1,
        require_alphabetic: bool = False,
        allowed_types: list = None,
        keywords: list = None,
        case_insensitive: bool = True,
        group_by_heading: bool = False,
        max_numeric_ratio: float = 1.0,
        context: bool = True,
        context_base_window: int = 1,
        context_max_window: int = 5,
        context_min_words: int = 20,
        context_min_chars: int = 75,
        text_separator: str = " ",
        generate_both_outputs: bool = True,
    ) -> None:
        """Apply all filters and write results to disk."""

        if auto_generate_filenames:
            if not output_folder:
                raise ValueError("output_folder is required when auto_generate_filenames=True")
            params = dict(
                keywords=keywords, min_words=min_words,
                require_alphabetic=require_alphabetic,
                max_numeric_ratio=max_numeric_ratio,
                context=context, group_by_heading=group_by_heading,
                start_keyword=start_keyword, end_keyword=end_keyword,
            )
            if generate_both_outputs:
                output_json_file = output_json_file or self.generate_filename(
                    output_folder, "structured", **params
                )
                output_text_only_file = output_text_only_file or self.generate_filename(
                    output_folder, "text_only", **params
                )

        # ── inner helpers ──────────────────────────────────────────────

        def passes_basic_filters(text: str) -> bool:
            tokens = text.split()
            alpha_tokens = [t for t in tokens if any(c.isalpha() for c in t)]
            if len(alpha_tokens) < min_words:
                return False
            if require_alphabetic and not any(c.isalpha() for c in text):
                return False
            if max_numeric_ratio < 1.0 and tokens:
                numeric_count = sum(1 for t in tokens if t.isdigit())
                if numeric_count / len(tokens) > max_numeric_ratio:
                    return False
            return True

        def extract_range(elems: list) -> list:
            if not extract_between_headings or not start_keyword or not end_keyword:
                return elems
            start_kw = start_keyword.lower()
            end_kw = end_keyword.lower()
            result, recording = [], False
            for e in elems:
                if e.get("type") == "heading":
                    heading = e.get("text", "").lower()
                    if start_kw in heading:
                        recording = True
                    elif end_kw in heading and recording:
                        break
                if recording:
                    result.append(e)
            return result

        def filter_with_context(elems: list) -> list:
            norm_kw = (
                [kw.lower() for kw in keywords] if (keywords and case_insensitive) else keywords
            )

            # Step 1: type filter + text cleaning + basic filters
            pre = []
            for e in elems:
                if allowed_types is not None and e.get("type") not in allowed_types:
                    continue
                ec = e.copy()
                ec["text"] = clean_text(ec.get("text", ""))
                if not passes_basic_filters(ec["text"]):
                    continue
                pre.append(ec)

            # Step 2: keyword matching
            if not keywords:
                return pre

            matches = set()
            for i, e in enumerate(pre):
                txt = e["text"].lower() if case_insensitive else e["text"]
                if any(kw in txt for kw in norm_kw):
                    matches.add(i)

            if not context or not matches:
                result = []
                for i in sorted(matches):
                    ec = pre[i].copy()
                    ec.pop("type", None)
                    ec["match_type"] = "direct"
                    result.append(ec)
                return result

            # Adaptive context: expand window until finding a sufficiently long element
            n = len(pre)
            final, processed = [], set()

            for idx in sorted(matches):
                if idx in processed:
                    continue

                # context before
                ctx_before = []
                for w in range(context_base_window, context_max_window + 1):
                    window = list(range(max(0, idx - w), idx))
                    if any(
                        len(pre[i]["text"].split()) >= context_min_words
                        and len(pre[i]["text"]) >= context_min_chars
                        for i in window
                    ):
                        ctx_before = window
                        break
                    if idx - w <= 0:
                        break

                # context after
                ctx_after = []
                for w in range(context_base_window, context_max_window + 1):
                    window = list(range(idx + 1, min(idx + w + 1, n)))
                    if any(
                        len(pre[i]["text"].split()) >= context_min_words
                        and len(pre[i]["text"]) >= context_min_chars
                        for i in window
                    ):
                        ctx_after = window
                        break
                    if idx + w >= n - 1:
                        break

                if ctx_before:
                    final.append({
                        "text": " ".join(pre[i]["text"] for i in ctx_before),
                        "match_type": "context",
                    })
                    processed.update(ctx_before)

                ec = pre[idx].copy()
                ec.pop("type", None)
                ec["match_type"] = "direct"
                final.append(ec)
                processed.add(idx)

                if ctx_after:
                    final.append({
                        "text": " ".join(pre[i]["text"] for i in ctx_after),
                        "match_type": "context",
                    })
                    processed.update(ctx_after)

            return final

        def group_by_headings(elems: list) -> list:
            sections = []
            current = {"heading": "NO_HEADING", "page": None, "elements": []}
            for e in elems:
                if e.get("type") == "heading":
                    if current["elements"] or current["heading"] != "NO_HEADING":
                        sections.append(current)
                    current = {
                        "heading": e.get("text", "").strip(),
                        "page": e.get("page"),
                        "elements": [],
                    }
                else:
                    current["elements"].append(e)
            if current["elements"] or current["heading"] != "NO_HEADING":
                sections.append(current)
            return sections

        # ── main processing ───────────────────────────────────────────

        final_docs = []
        for doc in self.docs:
            elems = extract_range(doc.get("Elements", []))
            filtered = filter_with_context(elems)

            base = {
                "File Name": doc.get("File Name"),
                **{k: v for k, v in doc.items() if k not in ("File Name", "Elements")},
            }

            if group_by_heading:
                base["Sections"] = group_by_headings(filtered)
            else:
                base["Elements"] = filtered

            final_docs.append(base)

        if output_folder:
            os.makedirs(output_folder, exist_ok=True)

        if output_json_file:
            with open(output_json_file, "w", encoding="utf-8") as fh:
                json.dump(final_docs, fh, indent=2, ensure_ascii=False)
            print(f"[filter] Structured output → {output_json_file}")

        if output_text_only_file:
            text_docs = []
            for doc in final_docs:
                if "Sections" in doc:
                    texts = [
                        e.get("text", "")
                        for sec in doc["Sections"]
                        for e in sec["elements"]
                        if e.get("text")
                    ]
                else:
                    texts = [e.get("text", "") for e in doc.get("Elements", []) if e.get("text")]

                combined = text_separator.join(texts)
                entry = {k: v for k, v in doc.items() if k not in ("Elements", "Sections")}
                entry["Text"] = combined
                entry["Term Count"] = len(combined.split())
                text_docs.append(entry)

            with open(output_text_only_file, "w", encoding="utf-8") as fh:
                json.dump(text_docs, fh, indent=2, ensure_ascii=False)
            print(f"[filter] Text-only output  → {output_text_only_file}")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter a merged PDF extraction dataset (Stage 3)"
    )

    # I/O
    parser.add_argument("--input", required=True,
                        help="Path to merged_output.json from Stage 2")
    parser.add_argument("--output-folder", required=True,
                        help="Folder for filtered output files")
    parser.add_argument("--output-filename", default=None,
                        help="Custom structured output filename (auto-generated if omitted)")
    parser.add_argument("--text-only-filename", default=None,
                        help="Custom text-only output filename (auto-generated if omitted)")
    parser.add_argument("--no-text-only", action="store_true",
                        help="Skip writing the text-only output")
    parser.add_argument("--no-structured", action="store_true",
                        help="Skip writing the structured output")

    # Keyword options
    kw_group = parser.add_mutually_exclusive_group()
    kw_group.add_argument("--keywords", nargs="+", default=None,
                          help="Keywords to match (space-separated)")
    kw_group.add_argument("--keywords-file", default=None,
                          help="JSON file containing a list of keywords")

    # Filter options
    parser.add_argument("--allowed-types", nargs="+", default=None,
                        help="Element types to keep (e.g. paragraph heading title)")
    parser.add_argument("--min-words", type=int, default=1,
                        help="Minimum alphabetic tokens per element (default: 1)")
    parser.add_argument("--require-alphabetic", action="store_true",
                        help="Drop elements with no alphabetic characters")
    parser.add_argument("--max-numeric-ratio", type=float, default=1.0,
                        help="Max fraction of numeric tokens allowed (default: 1.0 = no limit)")
    parser.add_argument("--no-context", action="store_true",
                        help="Disable adaptive context window around keyword matches")
    parser.add_argument("--context-base-window", type=int, default=1,
                        help="Initial context window size in elements (default: 1)")
    parser.add_argument("--context-max-window", type=int, default=5,
                        help="Maximum context window size in elements (default: 5)")
    parser.add_argument("--context-min-words", type=int, default=20,
                        help="Min words for a context element to be considered sufficient (default: 20)")
    parser.add_argument("--context-min-chars", type=int, default=75,
                        help="Min characters for a context element to be considered sufficient (default: 75)")
    parser.add_argument("--text-separator", default=" ",
                        help="String used to join elements in the text-only output (default: space)")
    parser.add_argument("--group-by-heading", action="store_true",
                        help="Group elements into sections by heading")
    parser.add_argument("--case-sensitive", action="store_true",
                        help="Use case-sensitive keyword matching")

    # Range extraction
    parser.add_argument("--start-keyword", default=None,
                        help="Start extracting at the first heading containing this keyword")
    parser.add_argument("--end-keyword", default=None,
                        help="Stop extracting at the first heading containing this keyword")

    # Info
    parser.add_argument("--list-types", action="store_true",
                        help="Print all element types found in the input file and exit")

    args = parser.parse_args()

    pf = PDFFilter(args.input)

    if args.list_types:
        print("Element types found:", pf.get_all_element_types())
        return

    # Resolve keywords
    keywords = args.keywords
    if args.keywords_file:
        with open(args.keywords_file, "r", encoding="utf-8") as fh:
            keywords = json.load(fh)

    # Resolve output paths
    use_auto = args.output_filename is None and args.text_only_filename is None

    pf.filter_documents(
        output_json_file=args.output_filename if not args.no_structured else None,
        output_text_only_file=args.text_only_filename if not args.no_text_only else None,
        auto_generate_filenames=use_auto,
        output_folder=args.output_folder,
        extract_between_headings=bool(args.start_keyword and args.end_keyword),
        start_keyword=args.start_keyword,
        end_keyword=args.end_keyword,
        min_words=args.min_words,
        require_alphabetic=args.require_alphabetic,
        allowed_types=args.allowed_types,
        keywords=keywords,
        case_insensitive=not args.case_sensitive,
        group_by_heading=args.group_by_heading,
        max_numeric_ratio=args.max_numeric_ratio,
        context=not args.no_context,
        context_base_window=args.context_base_window,
        context_max_window=args.context_max_window,
        context_min_words=args.context_min_words,
        context_min_chars=args.context_min_chars,
        text_separator=args.text_separator,
        generate_both_outputs=not args.no_text_only and not args.no_structured,
    )


if __name__ == "__main__":
    main()
