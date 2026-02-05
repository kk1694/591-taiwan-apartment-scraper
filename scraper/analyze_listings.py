"""
591 Apartment Scraper - AI Analysis Module

Uses Claude to analyze listing images and descriptions.
Extracts: is_modern, has_elevator, is_flat, location, notes

All analysis is done by AI - no regex or keyword matching.
"""

import json
import time
from pathlib import Path
from config import DATA_DIR, IMAGES_DIR


def get_listing_images(listing_id: str, max_images: int = 5) -> list[Path]:
    """
    Get paths to downloaded images for a listing.

    Args:
        listing_id: The listing ID
        max_images: Maximum number of images to return

    Returns:
        List of Path objects to image files
    """
    listing_dir = IMAGES_DIR / listing_id
    if not listing_dir.exists():
        return []

    # Get image files sorted by name (1.jpg, 2.jpg, etc.)
    images = sorted(listing_dir.glob("*.jpg"))[:max_images]
    return images


def prepare_analysis_prompt(listing: dict) -> str:
    """
    Prepare a prompt for Claude to analyze a listing.

    Args:
        listing: Listing dictionary with metadata

    Returns:
        Formatted prompt string
    """
    prompt_parts = [
        "Analyze this Taiwan apartment listing for a foreign couple expecting a baby.",
        "",
        "Listing metadata:",
        f"- District: {listing.get('district', 'Unknown')}",
        f"- Size: {listing.get('size_ping', '?')} ping ({listing.get('size_sqm', '?')} sqm)",
        f"- Floor: {listing.get('floor', 'Unknown')}",
        f"- Layout: {listing.get('layout', 'Unknown')}",
        f"- Price: NT${listing.get('base_rent_nt', '?')}/month",
    ]

    # Add Chinese description if available
    if listing.get("description_zh"):
        prompt_parts.extend([
            "",
            "Chinese description:",
            listing["description_zh"],
        ])

    prompt_parts.extend([
        "",
        "Based on the images and description above, provide JSON with these fields:",
        "",
        "1. is_modern (Y/N/?): Modern fixtures, clean condition, updated appliances?",
        "2. has_elevator (Y/N/?): Does the building have an elevator? Look for clues in images/description.",
        "3. is_flat (Y/N/?): Is this a residential apartment? (not a store, garage, office, or commercial space)",
        "4. location (string or null): Any specific location info (road name, building name, nearby landmark)?",
        "5. notes (string): 2-3 sentences in English summarizing: condition, baby safety concerns",
        "   (balcony railings, stairs, sharp corners), natural light, cleanliness, any red flags.",
        "",
        "Respond ONLY with valid JSON, no other text:",
        '{"is_modern": "Y", "has_elevator": "Y", "is_flat": "Y", "location": "Xinyi Road Section 4", "notes": "..."}',
    ])

    return "\n".join(prompt_parts)


def load_listings(filename: str = "listings.json") -> list[dict]:
    """Load listings from JSON file."""
    filepath = DATA_DIR / filename

    if not filepath.exists():
        print(f"Error: {filepath} not found. Run extract_details.py first.")
        return []

    with open(filepath) as f:
        data = json.load(f)
        return data.get("listings", [])


def save_listings(listings: list[dict], filename: str = "listings.json") -> Path:
    """Save listings to JSON file with analysis results."""
    filepath = DATA_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(listings),
            "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "listings": listings
        }, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(listings)} listings to {filepath}")
    return filepath


def save_checkpoint(listings: list[dict], checkpoint_num: int) -> Path:
    """Save a checkpoint during analysis."""
    filepath = DATA_DIR / f"listings_checkpoint_{checkpoint_num}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(listings),
            "checkpoint": checkpoint_num,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "listings": listings
        }, f, indent=2, ensure_ascii=False)

    print(f"Checkpoint {checkpoint_num} saved to {filepath}")
    return filepath


def prepare_listings(listings: list[dict]) -> list[dict]:
    """
    Prepare listings for AI analysis by initializing fields and checking for images.

    Args:
        listings: List of listing dictionaries

    Returns:
        List of listings with analysis fields initialized
    """
    with_images = 0
    with_description = 0

    for listing in listings:
        listing_id = listing.get("id", "unknown")

        # Check for images
        images = get_listing_images(listing_id)
        listing["_has_images"] = len(images) > 0
        listing["_image_count"] = len(images)
        if images:
            with_images += 1

        # Check for description
        if listing.get("description_zh"):
            with_description += 1

        # Initialize analysis fields if not present
        if "is_modern" not in listing:
            listing["is_modern"] = "?"
        if "has_elevator" not in listing:
            listing["has_elevator"] = "?"
        if "is_flat" not in listing:
            listing["is_flat"] = "?"
        if "location" not in listing:
            listing["location"] = None
        if "notes" not in listing:
            listing["notes"] = ""

    print(f"\nListings prepared:")
    print(f"  Total: {len(listings)}")
    print(f"  With images: {with_images}")
    print(f"  With description: {with_description}")

    return listings


def generate_analysis_tasks(listings: list[dict]) -> list[dict]:
    """
    Generate a list of tasks for Claude AI analysis.

    Each task contains:
    - listing_id
    - images (list of paths)
    - prompt (analysis prompt)
    - has_description (bool)

    Returns:
        List of task dictionaries
    """
    tasks = []

    for listing in listings:
        # Skip if already analyzed
        if (listing.get("is_modern") != "?" and
            listing.get("has_elevator") != "?" and
            listing.get("is_flat") != "?"):
            continue

        listing_id = listing.get("id")
        images = get_listing_images(listing_id, max_images=5)

        # Need either images or description for analysis
        has_images = len(images) > 0
        has_description = bool(listing.get("description_zh"))

        if not has_images and not has_description:
            continue

        tasks.append({
            "listing_id": listing_id,
            "images": [str(p) for p in images],
            "prompt": prepare_analysis_prompt(listing),
            "has_images": has_images,
            "has_description": has_description,
            "metadata": {
                "district": listing.get("district"),
                "price": listing.get("base_rent_nt"),
                "size_ping": listing.get("size_ping"),
                "floor": listing.get("floor"),
            }
        })

    return tasks


def apply_analysis_result(listing: dict, result: dict) -> dict:
    """
    Apply AI analysis result to a listing.

    Args:
        listing: Original listing dict
        result: AI analysis result with is_modern, has_elevator, is_flat, location, notes

    Returns:
        Updated listing dict
    """
    if "is_modern" in result:
        listing["is_modern"] = result["is_modern"]
    if "has_elevator" in result:
        listing["has_elevator"] = result["has_elevator"]
    if "is_flat" in result:
        listing["is_flat"] = result["is_flat"]
    if "location" in result:
        listing["location"] = result["location"]
    if "notes" in result:
        listing["notes"] = result["notes"]

    return listing


def print_analysis_summary(listings: list[dict]):
    """Print summary of analysis results."""
    total = len(listings)

    analyzed = sum(1 for l in listings if l.get("is_modern") != "?")
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

    if suitable:
        print("\nTop suitable listings:")
        for l in suitable[:5]:
            print(f"  - {l.get('id')}: NT${l.get('base_rent_nt', '?'):,} | {l.get('district')} | {l.get('size_ping')} ping")
            if l.get("notes"):
                print(f"    Notes: {l.get('notes')[:80]}...")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze 591 listings with AI")
    parser.add_argument("--input", type=str, default="listings.json", help="Input listings file")
    parser.add_argument("--output", type=str, default="listings.json", help="Output file")
    parser.add_argument("--generate-tasks", action="store_true", help="Generate task list for Claude analysis")
    args = parser.parse_args()

    # Load listings
    listings = load_listings(args.input)
    if not listings:
        exit(1)

    print(f"Loaded {len(listings)} listings")

    # Prepare listings (initialize fields, check for images)
    listings = prepare_listings(listings)

    if args.generate_tasks:
        # Generate tasks for Claude analysis
        tasks = generate_analysis_tasks(listings)

        tasks_file = DATA_DIR / "analysis_tasks.json"
        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)

        print(f"\nGenerated {len(tasks)} analysis tasks")
        print(f"Saved to: {tasks_file}")

    # Save prepared listings
    save_listings(listings, args.output)
    print_analysis_summary(listings)

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
To complete AI analysis with Claude:

1. For each listing, Claude should:
   - Read images from data/images/{listing_id}/
   - Read the description from listings.json
   - Analyze and determine: is_modern, has_elevator, is_flat, location, notes

2. Update listings.json with the analysis results

3. Run: python score_listings.py
""")
