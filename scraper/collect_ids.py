"""
591 Apartment Scraper - Collect Listing IDs

Uses Playwright to navigate the 591 search page and extract listing IDs.
Handles JavaScript rendering and pagination.
"""

import json
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from config import get_search_filters, BASE_URL, DATA_DIR


def build_search_url(district_code: int = None) -> str:
    """Build 591 search URL with filters from config."""
    filters = get_search_filters()

    # Use provided district or first from config
    section = district_code if district_code else filters["section"]

    params = [
        f"region={filters['region']}",
        f"section={section}",
        f"price={filters['price_min']}_{filters['price_max']}",
        f"area={filters['area_min']}_",
        "kind=0",  # Apartments only (not rooms/shared)
    ]
    return f"{BASE_URL}/list?{'&'.join(params)}"


def extract_listing_ids(page: Page) -> list[str]:
    """Extract all listing IDs from the current page state."""
    ids = set()

    # Method 1: Look for listing links in the format /XXXXXXXX
    links = page.query_selector_all("a[href*='rent.591.com.tw/']")
    for link in links:
        href = link.get_attribute("href") or ""
        match = re.search(r"/(\d{7,8})(?:\?|$|#)", href)
        if match:
            ids.add(match.group(1))

    # Method 2: Look for data attributes on listing cards
    cards = page.query_selector_all("[data-id]")
    for card in cards:
        data_id = card.get_attribute("data-id")
        if data_id and data_id.isdigit():
            ids.add(data_id)

    # Method 3: Look for listing IDs in onclick handlers or other attributes
    all_elements = page.query_selector_all("[onclick*='house'], [data-houseid]")
    for el in all_elements:
        onclick = el.get_attribute("onclick") or ""
        houseid = el.get_attribute("data-houseid") or ""
        for text in [onclick, houseid]:
            match = re.search(r"(\d{7,8})", text)
            if match:
                ids.add(match.group(1))

    return list(ids)


def scroll_and_collect(page: Page, max_scrolls: int = 50) -> list[str]:
    """
    Scroll through the page to load all listings and collect IDs.

    591 uses either pagination or infinite scroll depending on the view.
    """
    all_ids = set()
    last_count = 0
    no_change_count = 0

    for i in range(max_scrolls):
        # Extract IDs from current state
        current_ids = extract_listing_ids(page)
        all_ids.update(current_ids)

        print(f"Scroll {i+1}: Found {len(current_ids)} IDs on page, {len(all_ids)} total unique")

        # Check if we're still finding new listings
        if len(all_ids) == last_count:
            no_change_count += 1
            if no_change_count >= 3:
                print("No new listings found after 3 scrolls, stopping.")
                break
        else:
            no_change_count = 0
            last_count = len(all_ids)

        # Try to load more content
        # Method 1: Click "Load more" or pagination button if exists
        load_more = page.query_selector("button:has-text('更多'), .load-more, .pagination a.next")
        if load_more and load_more.is_visible():
            try:
                load_more.click()
                time.sleep(2)
                continue
            except Exception:
                pass

        # Method 2: Scroll to bottom for infinite scroll
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)

        # Method 3: Check for pagination and click next page
        next_page = page.query_selector(".pageNext, a[rel='next'], .pagination .next:not(.disabled)")
        if next_page and next_page.is_visible():
            try:
                next_page.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle")
            except Exception:
                pass

    return list(all_ids)


def collect_listing_ids(headless: bool = True, district_code: int = None) -> list[str]:
    """
    Main function to collect all listing IDs for configured districts.

    Args:
        headless: Run browser in headless mode
        district_code: Optional specific district code to search

    Returns:
        List of listing IDs
    """
    search_url = build_search_url(district_code)
    print(f"Searching: {search_url}")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Navigate to search page with timeout handling
        print("Loading search page...")
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)  # Let JS fully render
        except Exception as e:
            print(f"Error loading page: {e}")
            browser.close()
            return []

        # Handle any cookie/privacy popups
        try:
            cookie_btn = page.query_selector("button:has-text('同意'), button:has-text('接受')")
            if cookie_btn and cookie_btn.is_visible():
                cookie_btn.click()
                time.sleep(1)
        except Exception:
            pass

        # Get total count if displayed
        total_text = page.query_selector(".total, .count, [class*='total']")
        if total_text:
            print(f"Page shows: {total_text.inner_text()}")

        # Collect IDs by scrolling/paginating
        listing_ids = scroll_and_collect(page)

        browser.close()

    print(f"\nCollected {len(listing_ids)} unique listing IDs")
    return listing_ids


def collect_all_districts(headless: bool = True) -> dict:
    """
    Collect listing IDs for all configured districts.

    Returns:
        Dict mapping district names to lists of IDs
    """
    from config import load_config, DISTRICT_CODES

    config = load_config()
    districts = config["search_filters"].get("districts", ["Da'an"])

    all_results = {}

    for district in districts:
        if district not in DISTRICT_CODES:
            print(f"Warning: Unknown district '{district}', skipping")
            continue

        print(f"\n{'='*50}")
        print(f"Collecting listings for {district} district")
        print(f"{'='*50}")

        district_code = DISTRICT_CODES[district]
        ids = collect_listing_ids(headless=headless, district_code=district_code)
        all_results[district] = ids

        # Rate limit between districts
        time.sleep(3)

    return all_results


def save_listing_ids(ids: list[str], filename: str = "listing_ids.json") -> Path:
    """Save listing IDs to JSON file."""
    from config import get_search_filters

    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump({
            "count": len(ids),
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "filters": get_search_filters(),
            "ids": ids
        }, f, indent=2)
    print(f"Saved to {filepath}")
    return filepath


def save_all_districts(results: dict) -> Path:
    """Save all district results to JSON file."""
    from config import get_search_filters

    filepath = DATA_DIR / "all_districts_ids.json"

    # Flatten all IDs
    all_ids = []
    for ids in results.values():
        all_ids.extend(ids)
    unique_ids = list(set(all_ids))

    with open(filepath, "w") as f:
        json.dump({
            "count": len(unique_ids),
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "filters": get_search_filters(),
            "by_district": {d: {"count": len(ids), "ids": ids} for d, ids in results.items()},
            "all_ids": unique_ids
        }, f, indent=2)
    print(f"\nSaved all districts to {filepath}")
    print(f"Total unique listings: {len(unique_ids)}")
    return filepath


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Collect 591 listing IDs")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--all-districts", action="store_true", help="Collect from all configured districts")
    parser.add_argument("--district", type=str, help="Specific district to search (e.g., 'Da'an')")
    args = parser.parse_args()

    headless = not args.visible

    if args.all_districts:
        results = collect_all_districts(headless=headless)
        if results:
            save_all_districts(results)
    else:
        from config import DISTRICT_CODES
        district_code = None
        if args.district and args.district in DISTRICT_CODES:
            district_code = DISTRICT_CODES[args.district]

        ids = collect_listing_ids(headless=headless, district_code=district_code)
        if ids:
            save_listing_ids(ids)
        else:
            print("No listings found. Check search filters or page structure.")
