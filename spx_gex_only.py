# spx_gex_only.py
# -*- coding: utf-8 -*-
import os, re, csv, time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

GFLOW_URL = os.getenv("GFLOW_URL", "https://gflows.up.railway.app")
DATA_DIR = Path("data"); DATA_DIR.mkdir(exist_ok=True)
GEX_CSV  = DATA_DIR / "spx_gex.csv"
NBSP = u"\xa0"

def parse_gflow_total_gamma(page_text: str):
    t = re.sub(r"\s+", " ", page_text.replace(NBSP, " "), flags=re.M)
    m = re.search(r"Total\s*Gamma[^$]*\$\s*([\-–—−]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?)", t, flags=re.I)
    if not m: return None, None
    raw = m.group(1).replace("−", "-")
    try:
        return float(raw.replace(",", "").replace(" ", "")), f"${raw}"
    except ValueError:
        return None, None

def write_row(path: Path, header: list, row: dict):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if new: w.writeheader()
        w.writerow(row)

def click_if_exists(page, selectors, timeout=2500):
    for sel in selectors:
        try:
            page.locator(sel).first.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False

def main():
    print("[INFO] starting GFLOWS")
    header = ["date","symbol","total_gamma","raw_label","source_url"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width":1280,"height":800}, ignore_https_errors=True)
        page = ctx.new_page()
        page.goto(GFLOW_URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(1500)

        # cookie banners (jeśli są)
        click_if_exists(page, ["#onetrust-accept-btn-handler","button:has-text('Accept')","button:has-text('Zgadzam')"], 2000)

        # wybór SPX + zakładka Gamma
        click_if_exists(page, [
            "a:has-text('S&P 500 INDEX (SPX)')",
            "button:has-text('S&P 500 INDEX (SPX)')",
            "text=/S&P 500 INDEX\\s*\\(SPX\\)/i"
        ], 3000)
        click_if_exists(page, ["button:has-text('Gamma')","[role=tab]:has-text('Gamma')","text=Gamma"], 3000)

        # poczekaj aż pojawi się tekst z Total Gamma
        try:
            page.wait_for_selector("text=/Total\\s*Gamma/i", timeout=8000)
        except Exception:
            page.wait_for_timeout(1000)

        body = page.inner_text("body")
        try:
            svg = page.eval_on_selector_all("svg text","els => els.map(e => e.textContent).join(' | ')")
        except Exception:
            svg = ""

        val, raw = parse_gflow_total_gamma((body or "") + " | " + (svg or ""))
        if val is None:
            raise RuntimeError("Nie znaleziono wartości 'Total Gamma'.")

        row = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "symbol": "SPX",
            "total_gamma": int(val),
            "raw_label": raw,
            "source_url": GFLOW_URL,
        }
        write_row(GEX_CSV, header, row)
        print(f"[GEX] SPX Total Gamma = {raw} (~{row['total_gamma']:,} USD)")

        ctx.close(); browser.close()

if __name__ == "__main__":
    main()
