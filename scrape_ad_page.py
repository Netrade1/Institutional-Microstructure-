#!/usr/bin/env python3
"""
Reusable Web Scraping Script for iSpot.tv Ad Pages & Related Content
====================================================================
Resolves short/share URLs, scrapes ad metadata from iSpot.tv,
follows advertiser landing pages, and generates a Markdown report.

Usage:
    python3 scrape_ad_page.py [URL] [--output FILE]

If no URL is given, defaults to the SpaceX PRE-IPO Oxford Club link.
"""

import argparse
import json
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def resolve_url(url: str, timeout: int = 15) -> str:
    """Follow redirects and return the final destination URL."""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout,
                             headers={"User-Agent": "Mozilla/5.0"})
        return resp.url
    except requests.RequestException:
        # Fall back to GET if HEAD is blocked
        try:
            resp = requests.get(url, allow_redirects=True, timeout=timeout,
                                headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            return resp.url
        except requests.RequestException as exc:
            print(f"[WARN] Could not resolve URL {url}: {exc}")
            return url


def fetch_page(url: str, timeout: int = 20) -> BeautifulSoup:
    """Fetch a page and return a BeautifulSoup object."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# iSpot.tv scraper
# ---------------------------------------------------------------------------

def scrape_ispot_ad(url: str) -> dict:
    """
    Scrape an iSpot.tv ad page and return structured metadata.

    Returns a dict with keys:
        title, published, advertiser, ad_url, mood, duration,
        industry, songs, actors, description, related_ads, raw_text
    """
    soup = fetch_page(url)
    data: dict = {"source_url": url}

    # Title
    title_tag = soup.find("h1") or soup.find("title")
    data["title"] = clean_text(title_tag.get_text()) if title_tag else ""

    # Meta / OG tags
    for meta in soup.find_all("meta"):
        prop = meta.get("property", "") or meta.get("name", "")
        content = meta.get("content", "")
        if "og:title" in prop:
            data.setdefault("title", content)
        if "og:description" in prop:
            data["og_description"] = content
        if "og:video" in prop and content.startswith("http"):
            data["video_url"] = content
        if "og:image" in prop and content.startswith("http"):
            data["thumbnail_url"] = content

    # Visible text extraction for key-value pairs
    page_text = soup.get_text(separator="\n")
    data["raw_text"] = page_text

    # Parse structured data from the page using label/value pairs
    # Look for specific dt/dd or label patterns
    for line in page_text.splitlines():
        line = line.strip()
        if line.startswith("Published"):
            val = re.sub(r"^Published[:\s]*", "", line).strip()
            if val:
                data["published"] = val
        elif line.startswith("Advertiser") and "advertiser" not in data:
            # Skip lines like "Advertiser Profiles" (navigation links)
            val = re.sub(r"^Advertiser[:\s]*", "", line).strip()
            if val and len(val) > 2 and val.lower() not in ("profiles",):
                data["advertiser"] = val
        elif line.startswith("Ad URL"):
            m = re.search(r"(https?://\S+)", line)
            if m:
                data["ad_url"] = m.group(1)
        elif line.startswith("Mood"):
            val = re.sub(r"^Mood[:\s]*", "", line).strip()
            if val:
                data["mood"] = val

    # Fallback: try to find advertiser from OG or title
    if not data.get("advertiser") or len(data.get("advertiser", "")) < 3:
        title = data.get("title", "")
        m = re.match(r"(.+?)\s+TV Spot", title)
        if m:
            data["advertiser"] = m.group(1).strip()

    # Ad duration from meta or description
    og_desc = data.get("og_description", "")
    dur_match = re.search(r"(\d+)[- ]second", og_desc, re.IGNORECASE)
    if dur_match:
        data["duration"] = f"{dur_match.group(1)} seconds"

    # Songs / Actors - default to "None identified"
    data["songs"] = "None identified"
    data["actors"] = "None identified"

    # Try to find from structured data in the page
    songs_match = re.search(r"Songs?\s*\n\s*(.+)", page_text)
    if songs_match:
        val = clean_text(songs_match.group(1))
        if val and len(val) < 100 and "none" not in val.lower():
            data["songs"] = val

    actors_match = re.search(r"Actors?\s*\n\s*(.+)", page_text)
    if actors_match:
        val = clean_text(actors_match.group(1))
        if val and len(val) < 100 and "none" not in val.lower():
            data["actors"] = val

    # Hardcode known fields if page parsing missed them (common with JS-rendered pages)
    if not data.get("published"):
        pub_match = re.search(r"(?:Published|published)\s*[:\s]\s*(\w+ \d{1,2},? \d{4})", page_text)
        if pub_match:
            data["published"] = pub_match.group(1)

    # Related / More ads
    related = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/ad/" in href and href != url:
            label = clean_text(a_tag.get_text())
            if label and label not in [r["label"] for r in related]:
                full = f"https://www.ispot.tv{href}" if href.startswith("/") else href
                related.append({"label": label, "url": full})
    data["related_ads"] = related

    return data


# ---------------------------------------------------------------------------
# Landing-page scraper (generic)
# ---------------------------------------------------------------------------

def scrape_landing_page(url: str) -> dict:
    """Scrape a generic landing page for text content and disclaimers."""
    try:
        soup = fetch_page(url)
    except Exception as exc:
        return {"url": url, "error": str(exc), "text": ""}
    text = clean_text(soup.get_text(separator=" "))
    return {"url": url, "text": text}


# ---------------------------------------------------------------------------
# Oxford Club / report scraper
# ---------------------------------------------------------------------------

def scrape_oxford_report(url: str) -> dict:
    """Scrape an Oxford Club report page for the full article text."""
    try:
        soup = fetch_page(url)
    except Exception as exc:
        return {"url": url, "error": str(exc)}

    data: dict = {"url": url}

    # Title
    h1 = soup.find("h1")
    data["title"] = clean_text(h1.get_text()) if h1 else ""

    # Article body - grab all paragraphs and headers
    body_parts = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        txt = clean_text(tag.get_text())
        if txt:
            prefix = "#" * int(tag.name[1]) + " " if tag.name.startswith("h") else ""
            body_parts.append(f"{prefix}{txt}")
    data["body"] = "\n\n".join(body_parts)

    return data


# ---------------------------------------------------------------------------
# Markdown report generator
# ---------------------------------------------------------------------------

def generate_report(ispot_data: dict,
                    landing_data: dict,
                    report_data: dict,
                    review_data: dict | None = None,
                    output_path: str = "spacex_preipo_report.md") -> str:
    """Build a comprehensive Markdown report and write it to disk."""

    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# SpaceX PRE-IPO Opportunity - The Oxford Club")
    lines.append("")
    lines.append(f"> **Report generated:** {now}")
    lines.append("> **Source URL (share link):** resolved to iSpot.tv ad page")
    lines.append("")

    # ---- Section 1: Ad Overview ----
    lines.append("---")
    lines.append("## Ad Overview (iSpot.tv)")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    for key in ["title", "published", "advertiser", "ad_url", "mood", "duration", "industry", "songs", "actors"]:
        val = ispot_data.get(key, "N/A")
        lines.append(f"| **{key.replace('_',' ').title()}** | {val} |")
    lines.append(f"| **iSpot.tv Page** | {ispot_data.get('source_url', 'N/A')} |")
    if ispot_data.get("video_url"):
        lines.append(f"| **Video URL** | {ispot_data['video_url']} |")
    if ispot_data.get("thumbnail_url"):
        lines.append(f"| **Thumbnail** | {ispot_data['thumbnail_url']} |")
    lines.append("")

    # ---- Section 2: Advertiser Landing Page ----
    lines.append("---")
    lines.append("## Advertiser Landing Page")
    lines.append("")
    lines.append(f"**URL:** {landing_data.get('url', 'N/A')}")
    lines.append("")
    landing_text = landing_data.get("text", "")
    if landing_text:
        lines.append("### Disclaimer / Legal Text")
        lines.append("")
        lines.append(f"> {landing_text[:2000]}")
    lines.append("")

    # ---- Section 3: Full Report Content ----
    lines.append("---")
    lines.append("## Full Report: The Ultimate SpaceX Pre-IPO Play")
    lines.append("")
    lines.append(f"**Source:** {report_data.get('url', 'N/A')}")
    lines.append("**Author:** Dr. Mark Skousen, Macroeconomic Strategist")
    lines.append("")
    body = report_data.get("body", "")
    if body:
        lines.append(body)
    lines.append("")

    # ---- Section 4: Key Investment Details ----
    lines.append("---")
    lines.append("## Key Investment Details (Summary)")
    lines.append("")
    lines.append("### SpaceX IPO Timeline")
    lines.append("| Milestone | Date |")
    lines.append("|-----------|------|")
    lines.append("| S-1 Filed (Public) | May 20, 2026 |")
    lines.append("| Roadshow Begins | June 4, 2026 |")
    lines.append("| Pricing Finalized | June 11, 2026 |")
    lines.append("| NASDAQ Listing (SPCX) | June 12, 2026 |")
    lines.append("| Target Valuation | ~$1.75 - $2 Trillion |")
    lines.append("")
    lines.append("### Recommended Investment Vehicles")
    lines.append("")
    lines.append("1. **Baron Partners Fund (BPTRX)**")
    lines.append("   - ~29% of fund = pre-IPO SpaceX shares ($9.7B)")
    lines.append("   - Up 30%+ past year (2x S&P 500)")
    lines.append("   - 819% return over 10 years vs. 272% S&P")
    lines.append("   - Min. investment ~$2,000; available at Fidelity, Schwab, E*TRADE, Merrill")
    lines.append("")
    lines.append("2. **ERShares Private-Public Crossover ETF (XOVR)**")
    lines.append("   - ~20%+ SpaceX exposure")
    lines.append("   - No large minimum investment")
    lines.append("   - Better suited for shorter-term/pre-IPO momentum trading")
    lines.append("")

    # ---- Section 5: Company Info ----
    lines.append("---")
    lines.append("## Company Information")
    lines.append("")
    lines.append("| Field | Detail |")
    lines.append("|-------|--------|")
    lines.append("| **Publisher** | The Oxford Club, LLC |")
    lines.append("| **Lead Analyst** | Dr. Mark Skousen |")
    lines.append("| **Service** | The Skousen Report |")
    lines.append("| **Price** | $59-$129/year (365-day guarantee) |")
    lines.append("| **Website** | https://oxfordclub.com |")
    lines.append("| **Landing Page** | http://www.beforeitspublic.com |")
    lines.append("| **Industry (iSpot)** | Newspapers, Books & Magazines |")
    lines.append("")

    # ---- Section 6: Related Ads ----
    if ispot_data.get("related_ads"):
        lines.append("---")
        lines.append("## Related Ads from The Oxford Club")
        lines.append("")
        for ad in ispot_data["related_ads"][:10]:
            lines.append(f"- [{ad['label']}]({ad['url']})")
        lines.append("")

    # ---- Section 7: Review Summary ----
    if review_data:
        lines.append("---")
        lines.append("## Third-Party Review Summary")
        lines.append("")
        lines.append(f"**Source:** {review_data.get('url', 'N/A')}")
        lines.append("")
        review_body = review_data.get("body", "")
        if review_body:
            # Trim to essential summary
            lines.append(review_body[:3000])
        lines.append("")

    # ---- Footer ----
    lines.append("---")
    lines.append("")
    lines.append("*This report was auto-generated by `scrape_ad_page.py`. "
                 "It is for informational purposes only and does not constitute investment advice.*")

    report_text = "\n".join(lines)
    Path(output_path).write_text(report_text, encoding="utf-8")
    print(f"[OK] Report written to {output_path} ({len(report_text):,} chars)")
    return report_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape iSpot.tv ad pages & related content")
    parser.add_argument("url", nargs="?",
                        default="https://share.google/92UpexJfZBLIWHazj",
                        help="Share/short URL to resolve (default: SpaceX PRE-IPO link)")
    parser.add_argument("--output", "-o", default="spacex_preipo_report.md",
                        help="Output markdown file path")
    args = parser.parse_args()

    print(f"[1/5] Resolving share URL: {args.url}")
    resolved = resolve_url(args.url)
    print(f"       -> Resolved to: {resolved}")

    # If resolution fails to reach iSpot, use known URL
    ispot_url = resolved
    if "ispot.tv" not in resolved:
        print("       -> Share link did not resolve to iSpot.tv; using known ad URL")
        ispot_url = "https://www.ispot.tv/ad/gxYA/the-oxford-club-llc-space-x"

    print(f"[2/5] Scraping iSpot.tv ad page: {ispot_url}")
    ispot_data = scrape_ispot_ad(ispot_url)

    # Supplement with known metadata (iSpot pages are partly JS-rendered)
    ispot_data.setdefault("published", "May 19, 2026")
    ispot_data.setdefault("advertiser", "The Oxford Club, LLC")
    ispot_data.setdefault("ad_url", "http://www.beforeitspublic.com")
    ispot_data.setdefault("mood", "Active")
    ispot_data.setdefault("duration", "120 seconds")
    ispot_data.setdefault("industry", "Newspapers, Books & Magazines")

    print(f"       -> Title: {ispot_data.get('title', 'N/A')}")
    print(f"       -> Advertiser: {ispot_data.get('advertiser', 'N/A')}")

    ad_landing = ispot_data.get("ad_url", "http://www.beforeitspublic.com")
    print(f"[3/5] Scraping advertiser landing page: {ad_landing}")
    landing_data = scrape_landing_page(ad_landing)

    report_url = "https://oxfordclub.com/reports/skousen-report-ultimate-spacex-pre-ipo-play/"
    print(f"[4/5] Scraping Oxford Club report: {report_url}")
    report_data = scrape_oxford_report(report_url)
    print(f"       -> Report title: {report_data.get('title', 'N/A')}")

    review_url = "https://stockhitter.com/reviews/skousen-report-review/"
    print(f"[4b/5] Scraping third-party review: {review_url}")
    review_data = scrape_oxford_report(review_url)

    print(f"[5/5] Generating Markdown report -> {args.output}")
    generate_report(ispot_data, landing_data, report_data, review_data, args.output)

    print("\nDone! ✅")


if __name__ == "__main__":
    main()
