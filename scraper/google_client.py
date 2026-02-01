"""
591 Apartment Scraper - Google Sheets Client

Template for Google Sheets authentication.
Set up a service account to use this.

Setup instructions:
1. Go to Google Cloud Console (console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the Google Sheets API
4. Create a service account (IAM & Admin > Service Accounts)
5. Create and download a JSON key for the service account
6. Save the key as 'credentials.json' in this directory
7. Share your Google Sheet with the service account email
"""

import os
from pathlib import Path

# Credentials file location
CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service():
    """
    Get an authenticated Google Sheets service.

    Returns:
        googleapiclient.discovery.Resource: Sheets API service

    Raises:
        FileNotFoundError: If credentials.json is not found
        ImportError: If google-api-python-client is not installed
    """
    # Check for required packages
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API packages not installed. Run:\n"
            "pip install google-api-python-client google-auth"
        )

    # Check for credentials file
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {CREDENTIALS_FILE}\n"
            "See the docstring in this file for setup instructions."
        )

    # Authenticate
    credentials = service_account.Credentials.from_service_account_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES
    )

    # Build and return service
    service = build("sheets", "v4", credentials=credentials)
    return service.spreadsheets()


def test_connection(sheet_id: str = None):
    """
    Test the Google Sheets connection.

    Args:
        sheet_id: Optional Sheet ID to test access
    """
    try:
        service = get_sheets_service()
        print("Successfully authenticated with Google Sheets API")

        if sheet_id:
            # Try to read the sheet
            result = service.get(spreadsheetId=sheet_id).execute()
            title = result.get("properties", {}).get("title", "Unknown")
            print(f"Successfully accessed sheet: {title}")
            return True

    except FileNotFoundError as e:
        print(f"Setup required: {e}")
        return False
    except ImportError as e:
        print(f"Missing packages: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    print("Testing Google Sheets connection...\n")

    sheet_id = sys.argv[1] if len(sys.argv) > 1 else None
    success = test_connection(sheet_id)

    if success:
        print("\nGoogle Sheets is ready to use!")
    else:
        print("\nGoogle Sheets setup incomplete. See instructions above.")
