#!/usr/bin/env python3
"""
591 Apartment Scraper - Interactive Setup Wizard

Run this script to configure your search preferences.
Creates a config.json file with your settings.
"""

import json
import sys
from pathlib import Path

# District information
DISTRICTS = {
    "Da'an": {"code": 7, "chinese": "大安區", "description": "Central, upscale, near tech hub"},
    "Zhongzheng": {"code": 8, "chinese": "中正區", "description": "Government area, historical"},
    "Xinyi": {"code": 3, "chinese": "信義區", "description": "Business district, Taipei 101"},
    "Songshan": {"code": 4, "chinese": "松山區", "description": "Residential, good transport"},
    "Zhongshan": {"code": 1, "chinese": "中山區", "description": "Commercial, nightlife"},
    "Neihu": {"code": 5, "chinese": "內湖區", "description": "Tech park, suburban feel"},
    "Nangang": {"code": 6, "chinese": "南港區", "description": "Emerging tech hub"},
    "Shilin": {"code": 10, "chinese": "士林區", "description": "Night market, residential"},
    "Beitou": {"code": 11, "chinese": "北投區", "description": "Hot springs, quieter"},
    "Wanhua": {"code": 9, "chinese": "萬華區", "description": "Historic, affordable"},
    "Wenshan": {"code": 2, "chinese": "文山區", "description": "Universities, green"},
    "Datong": {"code": 12, "chinese": "大同區", "description": "Traditional, affordable"},
}

# MRT stations for reference point selection
POPULAR_STATIONS = {
    "台北車站": {"coords": [25.0478, 121.5170], "english": "Taipei Main Station"},
    "忠孝復興": {"coords": [25.0416, 121.5439], "english": "Zhongxiao Fuxing"},
    "忠孝新生": {"coords": [25.0420, 121.5330], "english": "Zhongxiao Xinsheng"},
    "市政府": {"coords": [25.0408, 121.5670], "english": "City Hall"},
    "南京復興": {"coords": [25.0520, 121.5443], "english": "Nanjing Fuxing"},
    "大安": {"coords": [25.0332, 121.5435], "english": "Daan"},
    "松山": {"coords": [25.0497, 121.5779], "english": "Songshan"},
    "西門": {"coords": [25.0420, 121.5080], "english": "Ximen"},
    "古亭": {"coords": [25.0263, 121.5227], "english": "Guting"},
    "東門": {"coords": [25.0340, 121.5290], "english": "Dongmen"},
}


def print_header(text: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def get_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(prompt).strip()
    return value if value else default


def get_number(prompt: str, default: int = None, min_val: int = None, max_val: int = None) -> int:
    """Get numeric input with validation."""
    while True:
        value = get_input(prompt, str(default) if default else None)
        try:
            num = int(value)
            if min_val is not None and num < min_val:
                print(f"  Please enter a value >= {min_val}")
                continue
            if max_val is not None and num > max_val:
                print(f"  Please enter a value <= {max_val}")
                continue
            return num
        except (ValueError, TypeError):
            print("  Please enter a valid number")


def select_multiple(prompt: str, options: dict, default_keys: list = None) -> list:
    """Let user select multiple options from a dict."""
    print(f"\n{prompt}")
    keys = list(options.keys())

    for i, key in enumerate(keys, 1):
        item = options[key]
        if isinstance(item, dict) and "description" in item:
            print(f"  {i}. {key} - {item['description']}")
        else:
            print(f"  {i}. {key}")

    print("\nEnter numbers separated by commas (e.g., 1,3,5)")
    if default_keys:
        default_nums = [str(keys.index(k) + 1) for k in default_keys if k in keys]
        default_str = ",".join(default_nums)
    else:
        default_str = "1"

    while True:
        value = get_input("Your selection", default_str)
        try:
            indices = [int(x.strip()) - 1 for x in value.split(",")]
            selected = [keys[i] for i in indices if 0 <= i < len(keys)]
            if selected:
                return selected
            print("  Please select at least one option")
        except (ValueError, IndexError):
            print("  Please enter valid numbers separated by commas")


def select_one(prompt: str, options: dict, default_key: str = None) -> str:
    """Let user select one option from a dict."""
    print(f"\n{prompt}")
    keys = list(options.keys())

    for i, key in enumerate(keys, 1):
        item = options[key]
        if isinstance(item, dict) and "english" in item:
            print(f"  {i}. {key} ({item['english']})")
        elif isinstance(item, dict) and "description" in item:
            print(f"  {i}. {key} - {item['description']}")
        else:
            print(f"  {i}. {key}")

    default_num = str(keys.index(default_key) + 1) if default_key and default_key in keys else "1"

    while True:
        value = get_input("Your selection", default_num)
        try:
            idx = int(value.strip()) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
            print(f"  Please enter a number between 1 and {len(keys)}")
        except ValueError:
            print("  Please enter a valid number")


def setup_reference_location() -> dict:
    """Configure the reference location for commute calculations."""
    print_header("Step 1: Reference Location")

    print("Your reference location is used to calculate commute times.")
    print("This could be your workplace, school, or any important destination.")

    choice = select_one(
        "How would you like to set your reference location?",
        {
            "MRT Station": {"description": "Select from popular MRT stations"},
            "Custom Coordinates": {"description": "Enter latitude/longitude manually"},
        },
        "MRT Station"
    )

    if choice == "MRT Station":
        station = select_one(
            "Select your reference MRT station:",
            POPULAR_STATIONS,
            "台北車站"
        )
        station_info = POPULAR_STATIONS[station]
        return {
            "name": station_info["english"],
            "coords": station_info["coords"],
            "station": station
        }
    else:
        print("\nEnter coordinates (you can find these on Google Maps)")
        lat = float(get_input("Latitude", "25.0478"))
        lon = float(get_input("Longitude", "121.5170"))
        name = get_input("Location name", "My Reference Point")

        # Find nearest station for commute calculations
        nearest = min(
            POPULAR_STATIONS.items(),
            key=lambda x: abs(x[1]["coords"][0] - lat) + abs(x[1]["coords"][1] - lon)
        )

        return {
            "name": name,
            "coords": [lat, lon],
            "station": nearest[0]
        }


def setup_search_filters() -> dict:
    """Configure search filters."""
    print_header("Step 2: Search Criteria")

    # Districts
    districts = select_multiple(
        "Select district(s) to search (you can choose multiple):",
        DISTRICTS,
        ["Da'an"]
    )
    print(f"  Selected: {', '.join(districts)}")

    # Price range
    print("\nPrice range (NT$ per month):")
    price_min = get_number("Minimum price", 15000, min_val=5000)
    price_max = get_number("Maximum price", 50000, min_val=price_min)

    # Size
    print("\nMinimum apartment size:")
    area_min = get_number("Minimum size (ping, 1 ping = 3.3 sqm)", 10, min_val=1)

    return {
        "region": 1,  # Taipei
        "districts": districts,
        "price_min": price_min,
        "price_max": price_max,
        "area_min": area_min,
    }


def setup_scoring_weights() -> dict:
    """Configure scoring weights."""
    print_header("Step 3: Scoring Preferences")

    print("Rate the importance of each factor (1-5):")
    print("1 = Not important, 5 = Very important\n")

    weights = {}
    factors = [
        ("commute", "Commute time to reference location", 3),
        ("lease", "Lease flexibility (shorter = better)", 2),
        ("price", "Lower price", 1),
        ("size", "Larger size", 1),
        ("amenities", "Amenities (washing machine, balcony, etc.)", 1),
    ]

    for key, description, default in factors:
        weight = get_number(f"{description}", default, min_val=1, max_val=5)
        weights[key] = weight

    return weights


def setup_output() -> dict:
    """Configure output options."""
    print_header("Step 4: Output Format")

    print("Select output format(s):\n")

    output = {
        "json": True,  # Always enabled
        "csv": False,
        "google_sheets": False,
        "sheet_id": None
    }

    # JSON is always on
    print("  JSON output: Always enabled (data/listings.json)")

    # CSV option
    csv_choice = get_input("\nAlso export to CSV? (y/n)", "n")
    output["csv"] = csv_choice.lower() in ("y", "yes")

    # Google Sheets option
    sheets_choice = get_input("\nExport to Google Sheets? (y/n)", "n")
    if sheets_choice.lower() in ("y", "yes"):
        output["google_sheets"] = True
        print("\nTo use Google Sheets, you'll need to:")
        print("  1. Create a Google Cloud project")
        print("  2. Enable the Google Sheets API")
        print("  3. Create a service account and download credentials")
        print("  4. Place credentials.json in this directory")
        print("  5. Share your sheet with the service account email")
        print("\nSee README.md for detailed instructions.")

        sheet_id = get_input("\nGoogle Sheet ID (from URL)", "")
        if sheet_id:
            output["sheet_id"] = sheet_id

    return output


def main():
    """Run the setup wizard."""
    print("\n" + "="*60)
    print("       591 Taiwan Apartment Scraper - Setup Wizard")
    print("="*60)
    print("\nThis wizard will help you configure the scraper.")
    print("Press Enter to accept default values shown in [brackets].")

    config = {}

    # Step 1: Reference location
    config["reference_location"] = setup_reference_location()

    # Step 2: Search filters
    config["search_filters"] = setup_search_filters()

    # Step 3: Scoring weights
    config["scoring_weights"] = setup_scoring_weights()

    # Step 4: Output format
    config["output"] = setup_output()

    # Summary
    print_header("Configuration Summary")
    print(f"Reference location: {config['reference_location']['name']}")
    print(f"  Station: {config['reference_location']['station']}")
    print(f"  Coordinates: {config['reference_location']['coords']}")
    print(f"\nSearch filters:")
    print(f"  Districts: {', '.join(config['search_filters']['districts'])}")
    print(f"  Price: NT${config['search_filters']['price_min']:,} - {config['search_filters']['price_max']:,}")
    print(f"  Min size: {config['search_filters']['area_min']} ping")
    print(f"\nScoring weights:")
    for key, value in config["scoring_weights"].items():
        print(f"  {key}: {value}/5")
    print(f"\nOutput:")
    print(f"  JSON: Yes")
    print(f"  CSV: {'Yes' if config['output']['csv'] else 'No'}")
    print(f"  Google Sheets: {'Yes' if config['output']['google_sheets'] else 'No'}")

    # Confirm and save
    print("\n" + "-"*60)
    confirm = get_input("Save this configuration? (y/n)", "y")

    if confirm.lower() in ("y", "yes"):
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"\nConfiguration saved to {config_path}")
        print("\nNext steps:")
        print("  1. Run: python scraper/collect_ids.py")
        print("  2. Run: python scraper/extract_details.py")
        print("  3. Run: python scraper/score_listings.py")
    else:
        print("\nConfiguration not saved. Run setup.py again to start over.")
        sys.exit(0)


if __name__ == "__main__":
    main()
