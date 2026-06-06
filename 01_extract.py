# -*- coding: utf-8 -*-
"""
01_extract.py

Stage 1: Extract text from PDFs via the Adobe PDF Services API.
Saves one .zip file per PDF (containing structuredData.json) in the output folder.
Already-extracted PDFs are skipped automatically.

Credentials are read from environment variables (or a .env file):
  ADOBE_CLIENT_ID
  ADOBE_CLIENT_SECRET

Usage:
  python 01_extract.py --pdf-folder /path/to/pdfs --zip-output /path/to/zips
  python 01_extract.py --pdf-folder /path/to/pdfs --zip-output /path/to/zips \\
      --client-id YOUR_ID --client-secret YOUR_SECRET
"""

import argparse
import logging
import os
from datetime import datetime
from io import BytesIO
import zipfile

from dotenv import load_dotenv

load_dotenv()

from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdfjobs.jobs.extract_pdf_job import ExtractPDFJob
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_element_type import ExtractElementType
from adobe.pdfservices.operation.pdfjobs.params.extract_pdf.extract_pdf_params import ExtractPDFParams
from adobe.pdfservices.operation.pdfjobs.result.extract_pdf_result import ExtractPDFResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class PDFExtractor:
    """Extract text from PDFs using Adobe PDF Services and save raw .zip outputs."""

    def __init__(self, pdf_folder: str, zip_output_folder: str,
                 client_id: str, client_secret: str):
        self.pdf_folder = pdf_folder
        self.zip_output_folder = zip_output_folder

        credentials = ServicePrincipalCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
        self.pdf_services = PDFServices(credentials=credentials)
        os.makedirs(self.zip_output_folder, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        existing_stems = self._existing_zip_stems()
        all_pdfs = sorted(f for f in os.listdir(self.pdf_folder) if f.lower().endswith(".pdf"))
        pending = [f for f in all_pdfs if os.path.splitext(f)[0] not in existing_stems]

        logging.info(
            f"PDFs found: {len(all_pdfs)}  |  already extracted: {len(all_pdfs) - len(pending)}"
            f"  |  to process: {len(pending)}"
        )

        for i, pdf_file in enumerate(pending, start=1):
            pdf_path = os.path.join(self.pdf_folder, pdf_file)
            logging.info(f"[{i}/{len(pending)}] {pdf_file}")
            try:
                self._extract_one(pdf_path)
            except Exception as exc:
                logging.error(f"Failed on {pdf_file}: {exc}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _existing_zip_stems(self) -> set:
        stems = set()
        for name in os.listdir(self.zip_output_folder):
            if name.lower().endswith(".zip") and "_extract_" in name:
                stems.add(name.split("_extract_")[0])
        return stems

    def _extract_one(self, pdf_path: str) -> None:
        with open(pdf_path, "rb") as fh:
            input_stream = fh.read()

        input_asset = self.pdf_services.upload(
            input_stream=input_stream,
            mime_type=PDFServicesMediaType.PDF,
        )

        params = ExtractPDFParams(elements_to_extract=[ExtractElementType.TEXT])
        job = ExtractPDFJob(input_asset=input_asset, extract_pdf_params=params)

        location = self.pdf_services.submit(job)
        response = self.pdf_services.get_job_result(location, ExtractPDFResult)

        result_asset: CloudAsset = response.get_result().get_resource()
        stream_asset: StreamAsset = self.pdf_services.get_content(result_asset)
        raw_bytes = stream_asset.get_input_stream()

        pdf_stem = os.path.splitext(os.path.basename(pdf_path))[0]
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        zip_name = f"{pdf_stem}_extract_{timestamp}.zip"
        zip_path = os.path.join(self.zip_output_folder, zip_name)

        with open(zip_path, "wb") as fh:
            fh.write(raw_bytes)
        logging.info(f"  Saved → {zip_path}")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs using Adobe PDF Services API (Stage 1)"
    )
    parser.add_argument("--pdf-folder", required=True,
                        help="Folder containing input PDF files")
    parser.add_argument("--zip-output", required=True,
                        help="Folder where extracted .zip files will be saved")
    parser.add_argument("--client-id", default=None,
                        help="Adobe client ID (overrides ADOBE_CLIENT_ID env var)")
    parser.add_argument("--client-secret", default=None,
                        help="Adobe client secret (overrides ADOBE_CLIENT_SECRET env var)")
    args = parser.parse_args()

    client_id = args.client_id or os.getenv("ADOBE_CLIENT_ID")
    client_secret = args.client_secret or os.getenv("ADOBE_CLIENT_SECRET")

    if not client_id or not client_secret:
        parser.error(
            "Adobe credentials are required.\n"
            "Set ADOBE_CLIENT_ID / ADOBE_CLIENT_SECRET in your environment (or .env file),\n"
            "or pass --client-id / --client-secret."
        )

    PDFExtractor(
        pdf_folder=args.pdf_folder,
        zip_output_folder=args.zip_output,
        client_id=client_id,
        client_secret=client_secret,
    ).run()


if __name__ == "__main__":
    main()
