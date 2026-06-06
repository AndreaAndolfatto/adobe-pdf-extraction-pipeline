# -*- coding: utf-8 -*-
"""
02_merge.py

Stage 2: Merge all .zip files produced in Stage 1 into two JSON files:
  1) merged_output.json       — full structured elements per document
  2) text_only_output.json    — concatenated plain text + term count per document

Document names are derived from the zip filename by stripping the
"_extract_<timestamp>.zip" suffix that Stage 1 adds.

Usage:
  python 02_merge.py --zip-folder /path/to/zips --output-folder /path/to/output
"""

import argparse
import json
import logging
import os
import zipfile
from io import BytesIO

from utils import get_element_type

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class ZipMerger:
    """Merge Adobe-extracted .zip archives into consolidated JSON datasets."""

    def __init__(
        self,
        zip_folder: str,
        output_folder: str,
        output_filename: str = "merged_output.json",
        text_only_filename: str = "text_only_output.json",
    ):
        self.zip_folder = zip_folder
        self.output_folder = output_folder
        self.output_filename = output_filename
        self.text_only_filename = text_only_filename
        os.makedirs(output_folder, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        zip_files = sorted(
            f for f in os.listdir(self.zip_folder) if f.lower().endswith(".zip")
        )
        logging.info(f"Found {len(zip_files)} zip files in {self.zip_folder}")

        all_docs = []
        for zip_file in zip_files:
            doc = self._process_zip(zip_file)
            if doc is not None:
                all_docs.append(doc)

        # Write structured output
        out_path = os.path.join(self.output_folder, self.output_filename)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(all_docs, fh, indent=2, ensure_ascii=False)
        logging.info(f"Structured output  → {out_path}  ({len(all_docs)} documents)")

        # Write text-only output
        text_docs = []
        for doc in all_docs:
            texts = [e["text"] for e in doc.get("Elements", []) if e.get("text")]
            text = " ".join(texts)
            entry = {k: v for k, v in doc.items() if k != "Elements"}
            entry["Text"] = text
            entry["Term Count"] = len(text.split())
            text_docs.append(entry)

        text_path = os.path.join(self.output_folder, self.text_only_filename)
        with open(text_path, "w", encoding="utf-8") as fh:
            json.dump(text_docs, fh, indent=2, ensure_ascii=False)
        logging.info(f"Text-only output   → {text_path}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _process_zip(self, zip_file: str) -> dict:
        zip_path = os.path.join(self.zip_folder, zip_file)
        logging.info(f"Processing: {zip_file}")

        with open(zip_path, "rb") as fh:
            raw = fh.read()

        with zipfile.ZipFile(BytesIO(raw), "r") as zf:
            if "structuredData.json" not in zf.namelist():
                logging.warning(f"  No structuredData.json — skipping {zip_file}")
                return None
            with zf.open("structuredData.json") as fj:
                data = json.load(fj)

        # Derive document name from the zip filename
        base_name = zip_file
        if "_extract_" in base_name:
            base_name = base_name.split("_extract_")[0]
        else:
            base_name = os.path.splitext(base_name)[0]

        # Map elements
        elements = data.get("elements", [])
        mapped = []
        for elem in elements:
            if "Text" not in elem:
                continue
            mapped.append({
                "type": get_element_type(elem.get("Path", "")),
                "page": elem.get("Page"),
                "text": elem["Text"],
            })

        return {"File Name": base_name, "Elements": mapped}


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Adobe extraction zips into JSON datasets (Stage 2)"
    )
    parser.add_argument("--zip-folder", required=True,
                        help="Folder containing .zip files from Stage 1")
    parser.add_argument("--output-folder", required=True,
                        help="Folder for output JSON files")
    parser.add_argument("--output-filename", default="merged_output.json",
                        help="Filename for the structured output (default: merged_output.json)")
    parser.add_argument("--text-only-filename", default="text_only_output.json",
                        help="Filename for the text-only output (default: text_only_output.json)")
    args = parser.parse_args()

    ZipMerger(
        zip_folder=args.zip_folder,
        output_folder=args.output_folder,
        output_filename=args.output_filename,
        text_only_filename=args.text_only_filename,
    ).run()


if __name__ == "__main__":
    main()
