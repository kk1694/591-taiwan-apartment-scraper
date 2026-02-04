"""
591 Apartment Scraper - Extract Listing Details

Fetches individual listing pages and extracts structured data.
Optionally downloads listing images.
"""

import json
import os
import re
import time
import random
import requests
import urllib3
from pathlib import Path

# Disable SSL warnings - 591's certificate is missing Subject Key Identifier extension
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup
from typing import Optional
from config import (
    BASE_URL, DATA_DIR, IMAGES_DIR,
    USER_AGENTS, REQUEST_DELAY_SECONDS, MAX_RETRIES,
    NT_TO_EUR, calculate_total_monthly, estimate_utilities
)


def get_session() -> requests.Session:
    """Create a requests session with headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    })
    return session


def fetch_listing_page(session: requests.Session, listing_id: str) -> Optional[str]:
    """Fetch a listing page HTML with retries."""
    url = f"{BASE_URL}/{listing_id}"

    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=30, verify=False)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 404:
                print(f"  Listing {listing_id} not found (404)")
                return None
            else:
                print(f"  Attempt {attempt+1}: Status {response.status_code}")
        except requests.RequestException as e:
            print(f"  Attempt {attempt+1}: Error - {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(REQUEST_DELAY_SECONDS * (attempt + 1))

    return None


def parse_price(text: str) -> Optional[int]:
    """Extract price in NT$ from text."""
    if not text:
        return None
    match = re.search(r"[\d,]+", text.replace(",", ""))
    if match:
        try:
            return int(match.group().replace(",", ""))
        except ValueError:
            pass
    return None


def parse_size_ping(text: str) -> Optional[float]:
    """Extract size in ping from text."""
    if not text:
        return None
    match = re.search(r"([\d.]+)\s*坪", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def parse_floor(text: str) -> Optional[str]:
    """Parse floor info like '4F/5F' or '4樓/5樓'."""
    if not text:
        return None
    match = re.search(r"(\d+)\s*[F樓]?\s*/\s*(\d+)", text)
    if match:
        return f"{match.group(1)}F/{match.group(2)}F"
    match = re.search(r"(\d+)\s*[F樓]", text)
    if match:
        return f"{match.group(1)}F"
    return text.strip() if text.strip() else None


def parse_lease_term(text: str) -> Optional[int]:
    """Extract minimum lease term in months."""
    if not text:
        return None
    text = text.lower()
    if "一個月" in text or "1個月" in text or "月租" in text:
        return 1
    if "三個月" in text or "3個月" in text:
        return 3
    if "半年" in text or "六個月" in text or "6個月" in text:
        return 6
    if "一年" in text or "1年" in text or "12個月" in text:
        return 12
    if "兩年" in text or "二年" in text or "2年" in text or "24個月" in text:
        return 24
    match = re.search(r"(\d+)\s*[個]?月", text)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*年", text)
    if match:
        return int(match.group(1)) * 12
    return None


def extract_image_urls(html: str) -> list[str]:
    """Extract all listing photo URLs from page HTML."""
    urls = []
    seen_ids = set()

    pattern = r'https://img\d\.591\.com\.tw/house/\d{4}/\d{2}/\d{2}/(\d+)\.jpg(?:!\d+x[^"\']*)?'
    matches = re.finditer(pattern, html)

    for match in matches:
        img_id = match.group(1)
        if img_id not in seen_ids:
            seen_ids.add(img_id)
            base_url = match.group(0).split('!')[0]
            full_url = f"{base_url}!1000x.water2.jpg"
            urls.append(full_url)

    return urls[:20]


def extract_listing_details(html: str, listing_id: str) -> Optional[dict]:
    """Parse listing HTML and extract structured data."""
    result = {
        "id": listing_id,
        "url": f"{BASE_URL}/{listing_id}",
        "title": None,
        "title_zh": None,
        "district": None,
        "address": None,
        "address_zh": None,
        "size_ping": None,
        "size_sqm": None,
        "layout": None,
        "floor": None,
        "min_tenancy_months": None,
        "move_in_date": None,
        "deposit_months": None,
        "base_rent_nt": None,
        "management_fee_nt": None,
        "utilities_estimate_nt": None,
        "total_monthly_nt": None,
        "total_monthly_eur": None,
        "upfront_cost_nt": None,
        "upfront_cost_eur": None,
        "washing_machine": None,
        "ac": None,
        "balcony": None,
        "parking": None,
        "pets_allowed": None,
        "mrt_station": None,
        "mrt_distance_m": None,
        "building_age": None,
        "image_urls": [],
        "image_paths": [],
    }

    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text()

    # Extract price
    price_match = re.search(r'<strong[^>]*>(\d{1,3}(?:,\d{3})*)</strong>\s*元/月', html)
    if price_match:
        result["base_rent_nt"] = int(price_match.group(1).replace(",", ""))
    else:
        price_match = re.search(r'>(\d{1,3}(?:,\d{3})*)</strong>\s*元/月', html)
        if price_match:
            result["base_rent_nt"] = int(price_match.group(1).replace(",", ""))
        else:
            price_matches = re.findall(r'(\d{1,3}(?:,\d{3})+)\s*元/月', html)
            if price_matches:
                for p in price_matches:
                    val = int(p.replace(",", ""))
                    if val >= 10000:
                        result["base_rent_nt"] = val
                        break
            if not result["base_rent_nt"]:
                price_match = re.search(r'>(\d{5,6})<', html)
                if price_match:
                    result["base_rent_nt"] = int(price_match.group(1))

    # Extract size
    size_match = re.search(r'(\d+(?:\.\d+)?)\s*坪', full_text)
    if size_match:
        result["size_ping"] = float(size_match.group(1))

    # Extract layout
    layout_match = re.search(r'(\d+房\d*廳?\d*衛?\d*陽台?)', full_text)
    if layout_match:
        result["layout"] = layout_match.group(1)

    # Extract floor
    floor_match = re.search(r'(\d+)\s*[樓F]\s*/\s*(\d+)\s*[樓F]?', full_text)
    if floor_match:
        result["floor"] = f"{floor_match.group(1)}F/{floor_match.group(2)}F"

    # Extract district
    district_match = re.search(r'(大安區|中正區|信義區|松山區|中山區|內湖區|南港區|士林區|北投區|萬華區|文山區|大同區)', full_text)
    if district_match:
        district_map = {
            "大安區": "Da'an",
            "中正區": "Zhongzheng",
            "信義區": "Xinyi",
            "松山區": "Songshan",
            "中山區": "Zhongshan",
            "內湖區": "Neihu",
            "南港區": "Nangang",
            "士林區": "Shilin",
            "北投區": "Beitou",
            "萬華區": "Wanhua",
            "文山區": "Wenshan",
            "大同區": "Datong",
        }
        result["district"] = district_map.get(district_match.group(1), district_match.group(1))

    # Extract address
    addr_match = re.search(r'((?:大安區|中正區|信義區|松山區|中山區|內湖區|南港區|士林區|北投區|萬華區|文山區|大同區)[^\s,，]{5,50})', full_text)
    if addr_match:
        result["address_zh"] = addr_match.group(1)

    # Extract deposit
    if "押金二個月" in full_text or "押金兩個月" in full_text:
        result["deposit_months"] = 2
    elif "押金一個月" in full_text:
        result["deposit_months"] = 1
    elif "押金三個月" in full_text:
        result["deposit_months"] = 3
    else:
        deposit_match = re.search(r'押金\s*(\d+)\s*個?月', full_text)
        if deposit_match:
            result["deposit_months"] = int(deposit_match.group(1))

    # Extract lease term
    if "一年" in full_text:
        result["min_tenancy_months"] = 12
    elif "半年" in full_text or "六個月" in full_text:
        result["min_tenancy_months"] = 6
    elif "一個月" in full_text or "月租" in full_text:
        result["min_tenancy_months"] = 1
    elif "兩年" in full_text or "二年" in full_text:
        result["min_tenancy_months"] = 24
    else:
        lease_match = re.search(r'最短租期\s*(\d+)\s*[個]?月', full_text)
        if lease_match:
            result["min_tenancy_months"] = int(lease_match.group(1))

    # Extract management fee
    if "管理費無" in full_text or "管理費含" in full_text or "管理費已含" in full_text:
        result["management_fee_nt"] = 0
    else:
        mgmt_match = re.search(r'管理費[：:]\s*(\d{1,5})\s*元', full_text)
        if mgmt_match:
            result["management_fee_nt"] = int(mgmt_match.group(1))
        else:
            mgmt_match = re.search(r'管理費\s*(\d{3,5})', full_text)
            if mgmt_match:
                result["management_fee_nt"] = int(mgmt_match.group(1))

    # Extract amenities
    result["washing_machine"] = "洗衣機" in full_text
    result["ac"] = "冷氣" in full_text or "空調" in full_text
    result["balcony"] = "陽台" in full_text
    result["parking"] = "車位" in full_text or "停車" in full_text
    result["pets_allowed"] = "可養寵" in full_text or ("寵物" in full_text and "不可" not in full_text)

    # Extract MRT info
    mrt_match = re.search(r'([\u4e00-\u9fff]+(?:站|捷運站))[^\d]*(\d+)?(?:公尺|m)?', full_text)
    if mrt_match:
        station = mrt_match.group(1)
        distance = mrt_match.group(2)
        result["mrt_station"] = station
        if distance:
            result["mrt_distance_m"] = int(distance)

    # Extract images
    result["image_urls"] = extract_image_urls(html)

    # Calculate derived fields
    if result["size_ping"]:
        result["size_sqm"] = round(result["size_ping"] * 3.3, 1)

    if result["base_rent_nt"]:
        if result["size_sqm"]:
            result["utilities_estimate_nt"] = estimate_utilities(
                result["size_sqm"],
                has_ac=result["ac"] if result["ac"] is not None else True
            )

        costs = calculate_total_monthly(
            result["base_rent_nt"],
            result["management_fee_nt"],
            result["utilities_estimate_nt"],
            result["size_sqm"]
        )
        result.update(costs)

        deposit_months = result["deposit_months"] or 2
        result["upfront_cost_nt"] = result["base_rent_nt"] * deposit_months
        result["upfront_cost_eur"] = round(result["upfront_cost_nt"] * NT_TO_EUR, 2)

    return result


def download_images(listing: dict, max_images: int = 10) -> list[str]:
    """Download listing images to local directory."""
    listing_id = listing["id"]
    image_urls = listing.get("image_urls", [])[:max_images]

    if not image_urls:
        return []

    listing_dir = IMAGES_DIR / listing_id
    listing_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
        "Referer": f"{BASE_URL}/{listing_id}",
        "Origin": BASE_URL,
    })

    for i, url in enumerate(image_urls):
        try:
            response = session.get(url, timeout=30, verify=False)

            if response.status_code == 200:
                filepath = listing_dir / f"{i+1}.jpg"
                with open(filepath, "wb") as f:
                    f.write(response.content)
                downloaded.append(str(filepath))
                print(f"    Downloaded image {i+1}/{len(image_urls)}")
            else:
                print(f"    Failed to download image {i+1}: {response.status_code}")

        except Exception as e:
            print(f"    Error downloading image {i+1}: {e}")

        time.sleep(0.5)

    return downloaded


def load_listing_ids(filename: str = "listing_ids.json") -> list[str]:
    """Load listing IDs from JSON file."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        # Try all_districts file
        filepath = DATA_DIR / "all_districts_ids.json"
        if not filepath.exists():
            print(f"Error: No listing IDs file found. Run collect_ids.py first.")
            return []

    with open(filepath) as f:
        data = json.load(f)
        # Handle both single-district and all-districts format
        if "all_ids" in data:
            return data["all_ids"]
        return data.get("ids", [])


def extract_all_listings(
    listing_ids: list[str] = None,
    download_images_flag: bool = False,
    limit: int = None
) -> list[dict]:
    """
    Extract details for all listings.

    Args:
        listing_ids: List of IDs to process. If None, loads from file.
        download_images_flag: Whether to download images.
        limit: Max number of listings to process (for testing).
    """
    if listing_ids is None:
        listing_ids = load_listing_ids()

    if not listing_ids:
        return []

    if limit:
        listing_ids = listing_ids[:limit]

    print(f"Processing {len(listing_ids)} listings...")
    session = get_session()
    results = []

    for i, listing_id in enumerate(listing_ids):
        print(f"\n[{i+1}/{len(listing_ids)}] Listing {listing_id}")

        html = fetch_listing_page(session, listing_id)
        if not html:
            continue

        listing = extract_listing_details(html, listing_id)
        if not listing:
            continue

        if download_images_flag and listing.get("image_urls"):
            print(f"  Downloading {len(listing['image_urls'])} images...")
            listing["image_paths"] = download_images(listing)

        price = listing.get("base_rent_nt", "?")
        size = listing.get("size_ping", "?")
        total_eur = listing.get("total_monthly_eur", "?")
        print(f"  Price: NT${price}, Size: {size} ping, Total: EUR {total_eur}/mo")

        results.append(listing)

        if i < len(listing_ids) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    return results


def save_listings(listings: list[dict], filename: str = "listings.json") -> Path:
    """Save listings to JSON file."""
    filepath = DATA_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(listings),
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "listings": listings
        }, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(listings)} listings to {filepath}")
    return filepath


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract 591 listing details")
    parser.add_argument("--limit", type=int, help="Max listings to process")
    parser.add_argument("--images", action="store_true", help="Download images")
    parser.add_argument("--ids", nargs="+", help="Specific listing IDs to process")
    parser.add_argument("--input", type=str, help="Input IDs file (default: listing_ids.json)")
    parser.add_argument("--output", type=str, default="listings.json", help="Output filename")
    args = parser.parse_args()

    listing_ids = args.ids if args.ids else None
    if not listing_ids and args.input:
        listing_ids = load_listing_ids(args.input)

    listings = extract_all_listings(
        listing_ids=listing_ids,
        download_images_flag=args.images,
        limit=args.limit
    )

    if listings:
        save_listings(listings, args.output)
