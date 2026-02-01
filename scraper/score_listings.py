"""
591 Apartment Scraper - Score Listings

Calculates composite scores based on user preferences and exports results.
"""

import json
import argparse
from pathlib import Path
from config import DATA_DIR, load_config, get_scoring_weights
from mrt_data import calculate_commute_time
from output_handler import export_all


def calculate_score(listing: dict, weights: dict = None) -> float:
    """
    Calculate a composite score for a listing based on weighted factors.

    Args:
        listing: Listing dictionary with extracted data
        weights: Scoring weights (from config if not provided)

    Returns:
        Composite score (0-100 scale)
    """
    if weights is None:
        weights = get_scoring_weights()

    score = 0
    weights_total = 0

    # 1. Lease flexibility (shorter = better)
    tenancy = listing.get("min_tenancy_months", 12)
    if tenancy:
        if tenancy <= 1:
            lease_score = 100  # Month-to-month
        elif tenancy <= 3:
            lease_score = 90
        elif tenancy <= 6:
            lease_score = 70
        elif tenancy <= 12:
            lease_score = 40
        else:
            lease_score = 20  # 2+ years

        weight = weights.get("lease", 2)
        score += weight * lease_score
        weights_total += weight

    # 2. Commute time (shorter = better)
    commute_time = listing.get("commute_time_min")
    if commute_time:
        if commute_time <= 10:
            commute_score = 100
        elif commute_time <= 15:
            commute_score = 85
        elif commute_time <= 20:
            commute_score = 70
        elif commute_time <= 30:
            commute_score = 50
        elif commute_time <= 45:
            commute_score = 30
        else:
            commute_score = 10

        weight = weights.get("commute", 3)
        score += weight * commute_score
        weights_total += weight

    # 3. Price (lower = better, normalized to typical range)
    price = listing.get("base_rent_nt", 0)
    if price > 0:
        # Assume range NT$15,000 - NT$50,000
        # NT$15K = 100, NT$50K = 0
        price_score = max(0, min(100, 100 - (price - 15000) / 350))

        weight = weights.get("price", 1)
        score += weight * price_score
        weights_total += weight

    # 4. Size (larger = better, normalized)
    size = listing.get("size_sqm", 0)
    if size > 0:
        # Assume range 10-100 sqm
        # 10 sqm = 10, 50 sqm = 50, 100+ sqm = 100
        size_score = min(100, max(10, size))

        weight = weights.get("size", 1)
        score += weight * size_score
        weights_total += weight

    # 5. Amenities
    amenity_score = 0
    amenity_count = 0

    if listing.get("washing_machine"):
        amenity_score += 30  # High value
        amenity_count += 1

    if listing.get("balcony"):
        amenity_score += 25
        amenity_count += 1

    if listing.get("ac"):
        amenity_score += 20  # Expected, but still valuable
        amenity_count += 1

    if listing.get("pets_allowed"):
        amenity_score += 15
        amenity_count += 1

    if listing.get("parking"):
        amenity_score += 10
        amenity_count += 1

    if amenity_count > 0:
        # Normalize to 0-100
        amenity_score = min(100, amenity_score)

        weight = weights.get("amenities", 1)
        score += weight * amenity_score
        weights_total += weight

    # Calculate final score
    if weights_total > 0:
        final_score = score / weights_total
    else:
        final_score = 0

    return round(final_score, 1)


def enrich_with_commute(listing: dict) -> dict:
    """Add commute time data to a listing."""
    mrt_text = listing.get("mrt_station", "")
    if listing.get("mrt_distance_m"):
        mrt_text = f"{mrt_text} ({listing['mrt_distance_m']}m)"

    commute_data = calculate_commute_time(mrt_text)

    if commute_data:
        listing["commute_time_min"] = commute_data.get("commute_time_min")
        listing["transport_mode"] = commute_data.get("transport_mode")
        listing["commute_details"] = {
            "mrt": commute_data.get("mrt_details"),
            "bike": commute_data.get("bike_details"),
        }

    return listing


def score_all_listings(listings: list[dict]) -> list[dict]:
    """
    Score all listings and sort by score descending.

    Args:
        listings: List of listing dictionaries

    Returns:
        List of listings with scores added, sorted by score
    """
    weights = get_scoring_weights()

    for listing in listings:
        # Add commute time data
        enrich_with_commute(listing)

        # Calculate score
        listing["score"] = calculate_score(listing, weights)

    # Sort by score descending
    listings.sort(key=lambda x: x.get("score", 0), reverse=True)

    return listings


def load_listings(filename: str = "listings.json") -> list[dict]:
    """Load listings from JSON file."""
    filepath = DATA_DIR / filename

    if not filepath.exists():
        print(f"Error: {filepath} not found. Run extract_details.py first.")
        return []

    with open(filepath) as f:
        data = json.load(f)
        return data.get("listings", [])


def print_summary(listings: list[dict], top_n: int = 10):
    """Print a summary of top listings."""
    print(f"\n{'='*70}")
    print(f"  TOP {min(top_n, len(listings))} LISTINGS BY SCORE")
    print(f"{'='*70}\n")

    for i, listing in enumerate(listings[:top_n], 1):
        price = listing.get("base_rent_nt", 0)
        size = listing.get("size_ping", 0)
        score = listing.get("score", 0)
        district = listing.get("district", "?")
        commute = listing.get("commute_time_min", "?")
        tenancy = listing.get("min_tenancy_months", "?")

        print(f"{i:2}. Score: {score:5.1f} | NT${price:,} | {size} ping | {district}")
        print(f"    Commute: {commute} min | Min lease: {tenancy} mo")
        print(f"    {listing.get('url', '')}")
        print()


def main():
    """Score listings and export results."""
    parser = argparse.ArgumentParser(description="Score and export 591 listings")
    parser.add_argument("--input", type=str, default="listings.json",
                        help="Input listings file")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top listings to show")
    parser.add_argument("--no-export", action="store_true",
                        help="Don't export, just show summary")
    args = parser.parse_args()

    # Load listings
    listings = load_listings(args.input)
    if not listings:
        return

    print(f"Loaded {len(listings)} listings")

    # Score listings
    print("Calculating scores...")
    scored = score_all_listings(listings)

    # Print summary
    print_summary(scored, args.top)

    # Export
    if not args.no_export:
        print("\nExporting results...")
        results = export_all(scored)
        print("\nExport complete:")
        for fmt, path in results.items():
            print(f"  {fmt}: {path}")


if __name__ == "__main__":
    main()
