# Lodgix Universal Scraper

A universal Python scraper designed to extract property addresses and/or
coordinates from vacation rental websites built on the **Lodgix
platform**.

This scraper is built to work across multiple Lodgix-powered websites by
automatically detecting API endpoints, parsing embedded JSON (JSON-LD,
inline JS), or falling back to HTML parsing when necessary.

------------------------------------------------------------------------

## Features

-   Automatically detects Lodgix API calls and uses them when available\
-   Falls back to parsing embedded JSON or HTML if API is not present\
-   Extracts **Full Address** and/or **Latitude/Longitude**\
-   Works for **multiple Lodgix-powered sites** without custom coding
    per site\
-   Outputs results in:
    -   JSON (per-site file)
    -   CSV (analysis log with notes and approach used)

------------------------------------------------------------------------

## Requirements

-   Python **3.9+**
-   Install dependencies:

``` bash
pip install requests beautifulsoup4
```

------------------------------------------------------------------------

## Usage

### Scrape a single site

``` bash
python lodgix_universal_scraper.py --url https://examplelodgixsite.com
```

### Scrape multiple sites from a list

Prepare a text file (`sites.txt`) with one URL per line:

    https://lodgixsite1.com
    https://lodgixsite2.com
    https://lodgixsite3.com

Run:

``` bash
python lodgix_universal_scraper.py --list sites.txt
```

### Output

-   Results will be stored in the `out/` directory by default:
    -   `out/json/` → per-site JSON results\
    -   `out/analysis.csv` → CSV log containing site, timestamp,
        approach, success/failure, address/coordinates, and notes

Example CSV row:

``` csv
SourceUrl,Timestamp,Approach,Success,FullAddress,Latitude,Longitude,Notes
https://examplelodgixsite.com,2025-09-11T12:00:00,json-ld,True,"123 Main St, Miami, FL 33101",25.7617,-80.1918,
```

------------------------------------------------------------------------

## Options

  Argument            Description
  ------------------- -------------------------------------------------------
  `--url` / `-u`      Scrape a single URL
  `--list` / `-l`     Path to file with multiple URLs (one per line)
  `--outdir` / `-o`   Output directory (default: `out`)
  `--csv`             Custom path for CSV log (default: `out/analysis.csv`)
  `--json`            Save per-site JSON results (enabled by default)
  `--timeout`         HTTP request timeout (default: 20s)

------------------------------------------------------------------------

## Example Run

``` bash
python lodgix_universal_scraper.py --list sites.txt --outdir results
```

Output:

    Processed 3 sites. CSV log: results/analysis.csv
    Sample results:
    {"SourceUrl":"https://lodgixsite1.com","Timestamp":"2025-09-11T02:00:00","Approach":"json-ld","Success":true,"FullAddress":"123 Main St, Miami, FL 33101","Latitude":25.7617,"Longitude":-80.1918,"Notes":null}

------------------------------------------------------------------------

## Deliverables for Client

-   **`lodgix_universal_scraper.py`** → Main scraper script\
-   **`README.md`** → This file (setup + usage instructions)\
-   **`analysis.csv`**
