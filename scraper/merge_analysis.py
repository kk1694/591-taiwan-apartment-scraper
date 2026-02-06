#!/usr/bin/env python3
"""
Merge Claude analysis results back into listings.json
"""

import json
import time
from pathlib import Path
from config import DATA_DIR

RESULTS_DIR = DATA_DIR / "analysis_results"
LISTINGS_FILE = DATA_DIR / "listings.json"


def load_listings() -> list[dict]:
    """Load listings from JSON file."""
    if not LISTINGS_FILE.exists():
        print(f"Error: {LISTINGS_FILE} not found")
        return []

    with open(LISTINGS_FILE) as f:
        data = json.load(f)
        return data.get("listings", [])


def save_listings(listings: list[dict]):
    """Save listings back to JSON file."""
    with open(LISTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(listings),
            "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "listings": listings
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(listings)} listings to {LISTINGS_FILE}")


def load_analysis_result(listing_id: str) -> dict | None:
    """Load analysis result for a listing."""
    result_file = RESULTS_DIR / f"{listing_id}.json"

    if not result_file.exists():
        return None

    try:
        with open(result_file) as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"  Warning: Could not parse {result_file}")
        return None


def merge_results():
    """Merge all analysis results into listings.json."""
    listings = load_listings()
    if not listings:
        return

    print(f"Loaded {len(listings)} listings")

    merged = 0
    skipped = 0

    for listing in listings:
        listing_id = listing.get("id")
        if not listing_id:
            continue

        # Skip if already has analysis
        if listing.get("is_modern") not in (None, "?"):
            skipped += 1
            continue

        result = load_analysis_result(listing_id)
        if not result:
            continue

        # Merge fields
        for field in ["is_modern", "has_elevator", "is_flat", "location", "notes"]:
            if field in result:
                listing[field] = result[field]

        merged += 1

    print(f"Merged: {merged}")
    print(f"Skipped (already analyzed): {skipped}")
    print(f"Pending: {len(listings) - merged - skipped}")

    save_listings(listings)

    # Print summary
    print_summary(listings)


def print_summary(listings: list[dict]):
    """Print analysis summary."""
    total = len(listings)
    analyzed = sum(1 for l in listings if l.get("is_modern") not in (None, "?"))
    modern_y = sum(1 for l in listings if l.get("is_modern") == "Y")
    modern_n = sum(1 for l in listings if l.get("is_modern") == "N")
    flat_y = sum(1 for l in listings if l.get("is_flat") == "Y")
    flat_n = sum(1 for l in listings if l.get("is_flat") == "N")
    elevator_y = sum(1 for l in listings if l.get("has_elevator") == "Y")
    elevator_n = sum(1 for l in listings if l.get("has_elevator") == "N")

    print(f"\n{'='*50}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*50}")
    print(f"Total listings: {total}")
    print(f"Analyzed: {analyzed}")
    print(f"Pending: {total - analyzed}")
    print()
    print(f"Modern: {modern_y} Y / {modern_n} N / {total - modern_y - modern_n} ?")
    print(f"Is flat: {flat_y} Y / {flat_n} N / {total - flat_y - flat_n} ?")
    print(f"Has elevator: {elevator_y} Y / {elevator_n} N / {total - elevator_y - elevator_n} ?")

    # Show suitable properties
    suitable = [l for l in listings
                if l.get("is_modern") == "Y"
                and l.get("is_flat") == "Y"]
    print(f"\nSuitable (modern + flat): {len(suitable)}")


if __name__ == "__main__":
    merge_results()
