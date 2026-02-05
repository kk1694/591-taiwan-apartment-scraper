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


def scroll_and_collect(page: Page, max_pages: int = 100) -> list[str]:
    """Collect listing IDs by clicking through pagination pages."""
    all_ids = set()
    page_num = 1

    while page_num <= max_pages:
        # Extract IDs from current page
        current_ids = extract_listing_ids(page)
        all_ids.update(current_ids)
        print(f"Page {page_num}: Found {len(current_ids)} IDs, {len(all_ids)} total unique")

        if len(current_ids) == 0:
            print("No listings found on page, stopping.")
            break

        # Find next page button: <span class="navigator"><a>下一頁</a></span>
        # When disabled: <span class="disabled navigator">
        # Must select the one with "下一頁" (next) not "上一頁" (previous)
        next_link = page.query_selector(".paginator-container span.navigator:not(.disabled) a:has-text('下一頁')")

        if not next_link:
            print(f"Reached last page ({page_num} pages total).")
            break

        try:
            next_link.click()
            page_num += 1
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            print(f"Error clicking next page: {e}")
            break

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


def collect_all_taipei(headless: bool = True) -> dict:
    """
    Collect listing IDs from ALL 12 Taipei districts.
    Ignores config.json district settings - always scrapes all districts.

    Returns:
        Dict mapping district names to lists of IDs
    """
    from config import DISTRICT_CODES

    all_results = {}

    for district_name, district_code in DISTRICT_CODES.items():
        print(f"\n{'='*50}")
        print(f"Collecting: {district_name} (code: {district_code})")
        print(f"{'='*50}")

        ids = collect_listing_ids(headless=headless, district_code=district_code)
        all_results[district_name] = ids

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
    parser.add_argument("--all-taipei", action="store_true", help="Collect from ALL 12 Taipei districts (ignores config)")
    parser.add_argument("--district", type=str, help="Specific district to search (e.g., 'Da'an')")
    args = parser.parse_args()

    headless = not args.visible

    if args.all_taipei:
        results = collect_all_taipei(headless=headless)
        if results:
            save_all_districts(results)
    elif args.all_districts:
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
