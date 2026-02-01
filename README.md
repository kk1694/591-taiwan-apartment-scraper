# 591 Taiwan Apartment Scraper

A configurable tool for scraping and scoring apartment listings from [591.com.tw](https://rent.591.com.tw), Taiwan's primary rental portal.

## What it does

1. **Collects listing IDs** from 591.com.tw based on your search criteria
2. **Extracts detailed information** from each listing (price, size, amenities, MRT access)
3. **Calculates commute times** to your reference location (MRT or bike)
4. **Scores listings** based on your weighted preferences
5. **Exports results** to JSON, CSV, or Google Sheets

## Requirements

- Python 3.10+
- Playwright (for browser automation)
- Internet connection

## Quick start

```bash
# Clone the repository
git clone https://github.com/yourusername/591-taiwan-apartment-scraper.git
cd 591-taiwan-apartment-scraper

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Run interactive setup
python setup.py

# Collect listing IDs
python scraper/collect_ids.py

# Extract listing details
python scraper/extract_details.py

# Score and export results
python scraper/score_listings.py
```

## Configuration

Run `python setup.py` to interactively configure:

- **Reference location**: Where you want to calculate commute times to (MRT station or coordinates)
- **Search criteria**: Districts, price range, minimum size
- **Scoring weights**: How important each factor is (1-5 scale)
  - Commute time
  - Lease flexibility (shorter = better)
  - Price
  - Size
  - Amenities
- **Output format**: JSON (default), CSV, Google Sheets

Configuration is saved to `config.json`. See `examples/config.example.json` for reference.

## Usage

### Step 1: Collect listing IDs

```bash
# Collect from configured districts
python scraper/collect_ids.py

# Show browser window (for debugging)
python scraper/collect_ids.py --visible

# Collect from all configured districts
python scraper/collect_ids.py --all-districts

# Collect from specific district
python scraper/collect_ids.py --district "Zhongshan"
```

### Step 2: Extract listing details

```bash
# Extract all listings
python scraper/extract_details.py

# Limit to first N listings (for testing)
python scraper/extract_details.py --limit 10

# Also download images
python scraper/extract_details.py --images
```

### Step 3: Score and export

```bash
# Score listings and export to configured formats
python scraper/score_listings.py

# Show top 20 listings
python scraper/score_listings.py --top 20

# Just show summary, don't export
python scraper/score_listings.py --no-export
```

## Output

Results are saved to:

- `output/listings.json` - Full listing data with scores
- `output/listings.csv` - Spreadsheet-friendly format (if enabled)
- Google Sheets (if configured)

## Running with Claude Code

This scraper works well with [Claude Code](https://claude.ai/claude-code). Claude can:

1. Run the setup wizard interactively
2. Execute the scraping steps
3. Help you understand and filter results
4. Adjust scoring weights based on your feedback

Example conversation:

```
> Run the apartment scraper setup

> Collect listings from Da'an and Xinyi districts

> Show me the top 10 apartments under NT$30,000

> Which apartments have washing machines and are close to MRT?
```

## Google Sheets setup (optional)

To export results to Google Sheets:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the Google Sheets API
4. Create a service account (IAM & Admin > Service Accounts)
5. Create and download a JSON key for the service account
6. Save the key as `credentials.json` in the project root
7. Share your target Google Sheet with the service account email

The service account email looks like: `your-service-account@your-project.iam.gserviceaccount.com`

## Scoring algorithm

The composite score (0-100) is calculated as a weighted average of:

| Factor | Description | Scoring |
|--------|-------------|---------|
| Commute | Time to reference location | ≤10 min = 100, ≤20 min = 70, ≤30 min = 50 |
| Lease | Minimum tenancy period | Month-to-month = 100, 6 mo = 70, 1 yr = 40 |
| Price | Monthly rent | NT$15K = 100, NT$50K = 0 |
| Size | Apartment size | 10 sqm = 10, 100 sqm = 100 |
| Amenities | Washing machine, balcony, AC, etc. | Sum of amenity values |

Adjust weights in `config.json` or re-run `setup.py`.

## Data extracted

For each listing:

- Basic: ID, URL, district, address
- Size: Ping, square meters, layout (rooms/bathrooms)
- Cost: Base rent, management fee, utilities estimate, total monthly
- Lease: Minimum tenancy, deposit months
- Amenities: Washing machine, AC, balcony, parking, pets allowed
- Location: MRT station, distance to station, commute time

## Limitations

- **Rate limiting**: The scraper adds delays between requests to be respectful. Scraping all of Taipei takes time.
- **Site changes**: 591.com.tw may change their page structure, which could break extraction.
- **Language**: Listing data is in Chinese; the scraper extracts but doesn't translate most fields.
- **Images**: Downloaded but not automatically analyzed. You could add vision API integration.

## Project structure

```
591-taiwan-apartment-scraper/
├── README.md
├── setup.py                 # Interactive configuration wizard
├── config.json              # Your preferences (generated by setup)
├── requirements.txt
├── .gitignore
├── scraper/
│   ├── config.py            # Configuration loading
│   ├── collect_ids.py       # Step 1: Collect listing IDs
│   ├── extract_details.py   # Step 2: Extract listing details
│   ├── mrt_data.py          # MRT station data and commute calculations
│   ├── score_listings.py    # Step 3: Score and export
│   ├── output_handler.py    # Export to JSON/CSV/Sheets
│   └── google_client.py     # Google Sheets authentication
├── data/                    # Scraped data (not committed)
├── output/                  # Export files (not committed)
└── examples/
    └── config.example.json  # Example configuration
```

## License

MIT License - feel free to use and modify.

## Acknowledgments

- [591.com.tw](https://rent.591.com.tw) for being Taiwan's go-to rental platform
- [Playwright](https://playwright.dev) for reliable browser automation
