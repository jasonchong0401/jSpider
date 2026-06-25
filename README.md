# jSpider 🕷️

Web scraper for [Investing.com](https://www.investing.com/) commodity data, using Playwright + stealth plugins to bypass bot detection.

## Features

- Scrape real-time commodity prices from Investing.com
- Category filtering: energy, metals, agriculture, or all
- Stealth mode with browser fingerprint randomization
- Auto-wait for Cloudflare challenge resolution
- Output as JSON and CSV

## Quick Start

```bash
# Install dependencies
pip install playwright playwright-stealth
playwright install chromium

# Scrape all commodities
python scrape_commodities.py

# Scrape only metals
python scrape_commodities.py --metals

# Scrape only energy
python scrape_commodities.py --energy

# Scrape only agriculture
python scrape_commodities.py --agriculture

# Show browser window (for debugging)
python scrape_commodities.py --visible

# Custom output file
python scrape_commodities.py --output my_data.csv
```

## Requirements

- Python 3.8+
- Playwright Chromium browser
- **Must run from a residential/office IP** (Investing.com blocks datacenter IPs)

## Output

Data is saved to the `output/` directory in both JSON and CSV formats.

### Data Fields

| Field      | Description        |
|------------|--------------------|
| name       | Commodity name     |
| last       | Last price         |
| high       | Daily high         |
| low        | Daily low          |
| change     | Price change       |
| change_pct | Change percentage  |
| time       | Last update time   |

## License

MIT
