"""
591 Apartment Scraper - Output Handler

Exports listings to JSON, CSV, and Google Sheets.
"""

import json
import csv
import time
from pathlib import Path
from typing import Optional
from config import OUTPUT_DIR, load_config, NT_TO_EUR


def export_json(listings: list[dict], filename: str = "listings.json") -> Path:
    """
    Export listings to JSON file.

    Args:
        listings: List of listing dictionaries
        filename: Output filename

    Returns:
        Path to the created file
    """
    filepath = OUTPUT_DIR / filename

    output = {
        "count": len(listings),
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "listings": listings
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Exported {len(listings)} listings to {filepath}")
    return filepath


def export_csv(listings: list[dict], filename: str = "listings.csv") -> Path:
    """
    Export listings to CSV file.

    Args:
        listings: List of listing dictionaries
        filename: Output filename

    Returns:
        Path to the created file
    """
    filepath = OUTPUT_DIR / filename

    # Define columns
    columns = [
        "id", "url", "district", "size_ping", "size_sqm", "layout", "floor",
        "min_tenancy_months", "deposit_months",
        "base_rent_nt", "base_rent_eur", "total_monthly_nt", "total_monthly_eur",
        "upfront_cost_nt", "upfront_cost_eur",
        "washing_machine", "ac", "balcony", "parking", "pets_allowed",
        "mrt_station", "mrt_distance_m",
        "commute_time_min", "transport_mode",
        "score",
        "is_modern", "has_elevator", "is_flat", "location", "notes",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for listing in listings:
            # Add calculated fields
            row = listing.copy()
            row["base_rent_eur"] = round(listing.get("base_rent_nt", 0) * NT_TO_EUR, 2)
            row["washing_machine"] = "Y" if listing.get("washing_machine") else "N"
            row["ac"] = "Y" if listing.get("ac") else "N"
            row["balcony"] = "Y" if listing.get("balcony") else "N"
            row["parking"] = "Y" if listing.get("parking") else "N"
            row["pets_allowed"] = "Y" if listing.get("pets_allowed") else "N"
            # AI analysis fields - keep as-is (Y/N/? or text)
            row["is_modern"] = listing.get("is_modern", "?")
            row["has_elevator"] = listing.get("has_elevator", "?")
            row["is_flat"] = listing.get("is_flat", "?")
            row["location"] = listing.get("location", "")
            row["notes"] = listing.get("notes", "")
            writer.writerow(row)

    print(f"Exported {len(listings)} listings to {filepath}")
    return filepath


def export_sheets(
    listings: list[dict],
    sheet_id: str = None,
    tab_name: str = None
) -> Optional[str]:
    """
    Export listings to Google Sheets.

    Args:
        listings: List of listing dictionaries
        sheet_id: Google Sheet ID (from URL). If None, uses config.
        tab_name: Tab/sheet name. If None, generates one.

    Returns:
        URL to the sheet, or None if failed
    """
    config = load_config()

    if not sheet_id:
        sheet_id = config["output"].get("sheet_id")

    if not sheet_id:
        print("Error: No Google Sheet ID configured.")
        print("Run setup.py and provide a Sheet ID, or pass sheet_id parameter.")
        return None

    if not tab_name:
        tab_name = f"listings-{time.strftime('%Y-%m-%d')}"

    # Try to import Google client
    try:
        from google_client import get_sheets_service
        service = get_sheets_service()
    except ImportError:
        print("Error: google_client.py not found or not configured.")
        print("See README.md for Google Sheets setup instructions.")
        return None
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None

    # Prepare headers and rows
    headers = [
        "URL", "District", "Size (ping)", "Size (sqm)", "Layout", "Floor",
        "Min Tenancy", "Deposit (mo)",
        "Base Rent (NT$)", "Base Rent (EUR)", "Utilities Est", "Total Monthly (NT$)", "Total Monthly (EUR)",
        "Upfront (NT$)", "Upfront (EUR)",
        "Washer", "AC", "Balcony", "Parking", "Pets",
        "MRT Station", "Dist to Station (m)", "Commute Time (min)", "Transport Mode",
        "Score", "Notes"
    ]

    rows = [headers]

    for listing in listings:
        row = [
            listing.get("url", ""),
            listing.get("district", ""),
            listing.get("size_ping", ""),
            listing.get("size_sqm", ""),
            listing.get("layout", ""),
            listing.get("floor", ""),
            listing.get("min_tenancy_months", ""),
            listing.get("deposit_months", ""),
            listing.get("base_rent_nt", ""),
            round(listing.get("base_rent_nt", 0) * NT_TO_EUR, 2),
            listing.get("utilities_estimate_nt", ""),
            listing.get("total_monthly_nt", ""),
            listing.get("total_monthly_eur", ""),
            listing.get("upfront_cost_nt", ""),
            listing.get("upfront_cost_eur", ""),
            "Y" if listing.get("washing_machine") else "N",
            "Y" if listing.get("ac") else "N",
            "Y" if listing.get("balcony") else "N",
            "Y" if listing.get("parking") else "N",
            "Y" if listing.get("pets_allowed") else "N",
            listing.get("mrt_station", ""),
            listing.get("mrt_distance_m", ""),
            listing.get("commute_time_min", ""),
            listing.get("transport_mode", ""),
            listing.get("score", ""),
            "",  # Notes (for user to fill in)
        ]
        rows.append(row)

    try:
        # Try to create new tab
        try:
            request = {
                "requests": [{
                    "addSheet": {
                        "properties": {"title": tab_name}
                    }
                }]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body=request
            ).execute()
            print(f"Created new tab: {tab_name}")
        except Exception:
            # Tab may already exist
            pass

        # Write data
        body = {"values": rows}
        result = service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab_name}'!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()

        print(f"Updated {result.get('updatedCells', 0)} cells in Google Sheets")
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        print(f"Sheet URL: {sheet_url}")
        return sheet_url

    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
        return None


def export_all(listings: list[dict]) -> dict:
    """
    Export listings to all configured formats.

    Returns:
        Dict with paths/URLs for each format
    """
    config = load_config()
    output_config = config.get("output", {})
    results = {}

    # JSON (always)
    results["json"] = str(export_json(listings))

    # CSV (if configured)
    if output_config.get("csv"):
        results["csv"] = str(export_csv(listings))

    # Google Sheets (if configured)
    if output_config.get("google_sheets"):
        sheet_url = export_sheets(listings)
        if sheet_url:
            results["google_sheets"] = sheet_url

    return results


if __name__ == "__main__":
    # Test with sample data
    sample_listings = [
        {
            "id": "12345678",
            "url": "https://rent.591.com.tw/12345678",
            "district": "Da'an",
            "size_ping": 15,
            "size_sqm": 49.5,
            "layout": "2房1廳1衛",
            "floor": "4F/5F",
            "min_tenancy_months": 12,
            "deposit_months": 2,
            "base_rent_nt": 25000,
            "total_monthly_nt": 28500,
            "total_monthly_eur": 769.50,
            "upfront_cost_nt": 50000,
            "upfront_cost_eur": 1350.00,
            "washing_machine": True,
            "ac": True,
            "balcony": True,
            "parking": False,
            "pets_allowed": False,
            "mrt_station": "大安站",
            "mrt_distance_m": 200,
            "commute_time_min": 15.5,
            "transport_mode": "MRT",
            "score": 72.5,
        }
    ]

    print("Testing export functions...\n")
    export_json(sample_listings, "test_export.json")
    export_csv(sample_listings, "test_export.csv")
    print("\nTest exports created in output/ directory")
