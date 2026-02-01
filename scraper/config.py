"""
591 Apartment Scraper - Configuration

Loads user preferences from config.json, falling back to defaults.
"""

import json
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = DATA_DIR / "images"
CONFIG_FILE = BASE_DIR / "config.json"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 591 URLs
BASE_URL = "https://rent.591.com.tw"
SEARCH_URL = f"{BASE_URL}/list"

# Exchange rate (update as needed)
NT_TO_EUR = 0.027

# Utilities estimation (monthly, NT$)
UTILITIES_BASE_NT = 2000  # Water, internet, basic gas
ELECTRICITY_PER_SQM_NT = 70  # AC-heavy summer estimate

# Rate limiting
REQUEST_DELAY_SECONDS = 2
MAX_RETRIES = 3

# User agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# District codes for 591.com.tw (Taipei)
DISTRICT_CODES = {
    "Da'an": 7,
    "Zhongzheng": 8,
    "Xinyi": 3,
    "Songshan": 4,
    "Zhongshan": 1,
    "Neihu": 5,
    "Nangang": 6,
    "Shilin": 10,
    "Beitou": 11,
    "Wanhua": 9,
    "Wenshan": 2,
    "Datong": 12,
}

# Default configuration
DEFAULT_CONFIG = {
    "reference_location": {
        "name": "Taipei Main Station",
        "coords": [25.0478, 121.5170],
        "station": "台北車站"
    },
    "search_filters": {
        "region": 1,  # Taipei
        "districts": ["Da'an"],
        "price_min": 15000,
        "price_max": 50000,
        "area_min": 10,  # ping
    },
    "scoring_weights": {
        "commute": 3,
        "lease": 2,
        "price": 1,
        "size": 1,
        "amenities": 1
    },
    "output": {
        "json": True,
        "csv": False,
        "google_sheets": False,
        "sheet_id": None
    }
}


def load_config() -> dict:
    """Load configuration from config.json, using defaults for missing values."""
    config = DEFAULT_CONFIG.copy()

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)

            # Deep merge user config into defaults
            for key, value in user_config.items():
                if isinstance(value, dict) and key in config:
                    config[key].update(value)
                else:
                    config[key] = value

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load config.json: {e}")
            print("Using default configuration.")
    else:
        print("No config.json found. Run 'python setup.py' to configure.")
        print("Using default configuration.")

    return config


def save_config(config: dict) -> None:
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {CONFIG_FILE}")


def get_search_filters() -> dict:
    """Get search filters from config, formatted for 591 URL."""
    config = load_config()
    filters = config["search_filters"]

    # Convert district names to codes
    district_codes = []
    for district in filters.get("districts", ["Da'an"]):
        if district in DISTRICT_CODES:
            district_codes.append(DISTRICT_CODES[district])

    return {
        "region": filters.get("region", 1),
        "section": district_codes[0] if district_codes else 7,  # Primary district
        "sections": district_codes,  # All districts
        "price_min": filters.get("price_min", 15000),
        "price_max": filters.get("price_max", 50000),
        "area_min": filters.get("area_min", 10),
    }


def get_reference_coords() -> tuple:
    """Get reference location coordinates from config."""
    config = load_config()
    coords = config["reference_location"]["coords"]
    return tuple(coords)


def get_scoring_weights() -> dict:
    """Get scoring weights from config."""
    config = load_config()
    return config["scoring_weights"]


def estimate_utilities(size_sqm: float, has_ac: bool = True) -> int:
    """
    Estimate monthly utilities based on apartment size.

    Args:
        size_sqm: Apartment size in square meters
        has_ac: Whether apartment has AC (affects electricity estimate)

    Returns:
        Estimated monthly utilities in NT$
    """
    electricity = size_sqm * ELECTRICITY_PER_SQM_NT if has_ac else size_sqm * 30
    return int(UTILITIES_BASE_NT + electricity)


def calculate_total_monthly(
    base_rent: int,
    management_fee: int = None,
    utilities: int = None,
    size_sqm: float = None
) -> dict:
    """
    Calculate total monthly cost breakdown.

    Returns dict with NT$ and EUR values.
    """
    mgmt = management_fee if management_fee is not None else 0
    utils = utilities if utilities is not None else (
        estimate_utilities(size_sqm) if size_sqm else 0
    )

    total_nt = base_rent + mgmt + utils

    return {
        "base_rent_nt": base_rent,
        "management_fee_nt": mgmt,
        "utilities_nt": utils,
        "total_monthly_nt": total_nt,
        "total_monthly_eur": round(total_nt * NT_TO_EUR, 2),
    }
