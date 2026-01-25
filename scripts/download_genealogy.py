#!/usr/bin/env python3
"""
Download Shanghai genealogy PDF from Wikimedia Commons and convert to page images.
This is the proper way to get the content - download the original, convert locally.
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path

# Configuration
OUTPUT_DIR = Path("sources")
PDF_PATH = OUTPUT_DIR / "genealogy.pdf"
PDF_URL = "https://upload.wikimedia.org/wikipedia/commons/6/68/Shanghai_%E5%8B%BE%E7%94%AC%E9%AE%91%E6%B0%8F%E5%AE%97%E8%AD%9C.pdf"
USER_AGENT = "FamilyGenealogyDownloader/1.0 (personal genealogy research)"


def format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    else:
        return f"{num_bytes / (1024 * 1024):.1f} MB"


def download_pdf():
    """Download the PDF file with progress indicator."""
    if PDF_PATH.exists() and PDF_PATH.stat().st_size > 80_000_000:
        print(f"PDF already downloaded: {format_bytes(PDF_PATH.stat().st_size)}")
        return True

    print(f"Downloading PDF from Wikimedia Commons...")
    print(f"URL: {PDF_URL}")
    print(f"Expected size: ~87.6 MB")
    print()

    request = urllib.request.Request(PDF_URL, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192

            with open(PDF_PATH, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Progress bar
                    if total_size > 0:
                        progress = downloaded / total_size
                        bar_width = 40
                        filled = int(bar_width * progress)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        sys.stdout.write(f"\r[{bar}] {format_bytes(downloaded)} / {format_bytes(total_size)} ({progress*100:.1f}%)")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write(f"\rDownloaded: {format_bytes(downloaded)}")
                        sys.stdout.flush()

        print()
        print(f"Downloaded: {format_bytes(PDF_PATH.stat().st_size)}")
        return True

    except Exception as e:
        print(f"\nError downloading PDF: {e}")
        if PDF_PATH.exists():
            PDF_PATH.unlink()
        return False


def check_tools():
    """Check for available PDF conversion tools."""
    # Check for pdftoppm (from poppler-utils)
    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
        return "pdftoppm"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check for ImageMagick convert
    try:
        result = subprocess.run(["convert", "-version"], capture_output=True, check=True)
        return "convert"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check for sips (macOS built-in, but doesn't handle PDF pages well)
    return None


def convert_with_pdftoppm():
    """Convert PDF to images using pdftoppm (fastest and best quality)."""
    print("Converting PDF to JPEG images using pdftoppm...")
    print("This may take a few minutes...")
    print()

    # pdftoppm outputs to sources/page-001.jpg, page-002.jpg, etc.
    result = subprocess.run([
        "pdftoppm",
        "-jpeg",
        "-r", "150",  # 150 DPI - good balance of quality and file size
        str(PDF_PATH),
        str(OUTPUT_DIR / "page")
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    # Rename files from page-001.jpg to page1.jpg
    print("Renaming files...")
    for f in OUTPUT_DIR.glob("page-*.jpg"):
        # Extract number from page-001.jpg
        num = int(f.stem.split("-")[1])
        new_name = OUTPUT_DIR / f"page{num}.jpg"
        f.rename(new_name)

    return True


def convert_with_imagemagick():
    """Convert PDF to images using ImageMagick (slower but widely available)."""
    print("Converting PDF to JPEG images using ImageMagick...")
    print("This may take a while (ImageMagick is slower than pdftoppm)...")
    print()

    result = subprocess.run([
        "convert",
        "-density", "150",
        str(PDF_PATH),
        "-quality", "85",
        str(OUTPUT_DIR / "page%d.jpg")
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False

    # ImageMagick uses 0-indexing, rename to 1-indexed
    for f in sorted(OUTPUT_DIR.glob("page*.jpg")):
        num = int(f.stem.replace("page", ""))
        new_name = OUTPUT_DIR / f"page{num + 1}.jpg"
        if f != new_name:
            f.rename(new_name)

    return True


def main():
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Check if pages already exist
    existing_pages = list(OUTPUT_DIR.glob("page*.jpg"))
    if len(existing_pages) >= 1040:
        print(f"Already have {len(existing_pages)} page images.")
        total_size = sum(f.stat().st_size for f in existing_pages)
        print(f"Total size: {format_bytes(total_size)}")
        return

    print("Shanghai Family Genealogy Downloader")
    print("=" * 50)
    print()

    # Step 1: Download PDF
    if not download_pdf():
        return

    print()

    # Step 2: Check for conversion tools
    tool = check_tools()
    if tool is None:
        print("No PDF conversion tool found!")
        print()
        print("Please install one of these:")
        print("  macOS:   brew install poppler")
        print("  Ubuntu:  sudo apt install poppler-utils")
        print()
        print("The PDF has been saved to:")
        print(f"  {PDF_PATH.absolute()}")
        print()
        print("You can manually convert with:")
        print(f"  pdftoppm -jpeg -r 150 {PDF_PATH} sources/page")
        return

    # Step 3: Convert PDF to images
    if tool == "pdftoppm":
        success = convert_with_pdftoppm()
    else:
        success = convert_with_imagemagick()

    if not success:
        print("Conversion failed!")
        return

    # Step 4: Report results
    pages = list(OUTPUT_DIR.glob("page*.jpg"))
    total_size = sum(f.stat().st_size for f in pages)

    print()
    print("=" * 50)
    print(f"Done! Created {len(pages)} page images")
    print(f"Total size: {format_bytes(total_size)}")
    print(f"Location: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    main()
