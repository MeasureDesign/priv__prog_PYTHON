
import csv
import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Vstupní soubor
SITEMAP_LIST_FILE = r"/Users/johanarucka/Desktop/Measure Design/Python - kontrola parametrů/sitemap_list.txt"
OUTPUT_FILE = r"/Users/johanarucka/Desktop/Measure Design/Python - kontrola parametrů/Final/results_all.csv"

def extract_urls_from_multiple_sitemaps(list_path):
    all_urls = set()
    with open(list_path, "r", encoding="utf-8") as f:
        sitemap_urls = [line.strip() for line in f if line.strip()]
    for sitemap_url in sitemap_urls:
        try:
            response = requests.get(sitemap_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")
                loc_urls = [loc.text.strip() for loc in soup.find_all("loc")]
                xhtml_links = [link.get("href") for link in soup.find_all("xhtml:link") if link.get("href")]
                all_urls.update(loc_urls + xhtml_links)
        except Exception as e:
            print(f"Chyba při načítání {sitemap_url}: {e}")
    return sorted(all_urls)

def extract_page_params(item):
    page_data = item.get("page") or item
    return {
        "page_segment": page_data.get("segment", ""),
        "page_category": page_data.get("category", page_data.get("pageCategory", "")),
        "page_topic": page_data.get("topic", page_data.get("pageTopic", "")),
        "page_environment": page_data.get("environment", ""),
        "page_country": page_data.get("country", ""),
        "page_language": page_data.get("language", ""),
        "page_name": page_data.get("name", ""),
        "page_hostname": page_data.get("hostname", ""),
        "page_clean_path": page_data.get("clean_page_path", page_data.get("cleanPagePath", "")),
        "page_full_url": page_data.get("full_url", page_data.get("fullUrl", "")),
        "page_params": page_data.get("params", ""),
    }

def analyze_url(context, url):
    page = context.new_page()
    result = {
        "url": url,
        "http_status": "",
        "has_dataLayer": False,
        "has_pageView": False,
        "page_segment": "",
        "page_category": "",
        "page_topic": "",
        "page_environment": "",
        "page_country": "",
        "page_language": "",
        "page_name": "",
        "page_hostname": "",
        "page_clean_path": "",
        "page_full_url": "",
        "page_params": "",
        "error": ""
    }

    try:
        response = page.goto(url, timeout=20000)
        if response:
            result["http_status"] = response.status
        else:
            result["http_status"] = "no response"

        # Polling až 10s na pageView
        page_view_item = None
        for _ in range(10):
            logs = page.evaluate("() => window.dataLayer || []")
            if logs:
                result["has_dataLayer"] = True
                for item in logs:
                    if isinstance(item, dict) and item.get("event") == "pageView":
                        page_view_item = item
                        break
                if page_view_item:
                    break
            time.sleep(1)

        if page_view_item:
            result["has_pageView"] = True
            params = extract_page_params(page_view_item)
            result.update(params)
        else:
            if result["has_dataLayer"]:
                result["error"] = "missing pageView"
            else:
                result["error"] = "dataLayer missing"

    except Exception as e:
        result["error"] = str(e)
        result["http_status"] = "error"
    finally:
        page.close()

    return result

def main():
    urls = extract_urls_from_multiple_sitemaps(SITEMAP_LIST_FILE)
    results = []
    start_time = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Spouštím kontrolu v {start_time}. Celkem URL: {len(urls)}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        try:
            for idx, url in enumerate(urls, 1):
                print(f"[{idx}/{len(urls)}] Kontroluji: {url}")
                result = analyze_url(context, url)
                results.append(result)

                # průběžné ukládání výsledků
                keys = results[0].keys()
                with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)

                print(f"Uloženo {idx} výsledků.")

        except KeyboardInterrupt:
            print("\nSkript byl přerušen uživatelem. Ukládám dosavadní výsledky...")
            if results:
                keys = results[0].keys()
                with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(results)
            print(f"Hotovo. Uloženo {len(results)} výsledků.")
        finally:
            browser.close()
            end_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Skript ukončen v {end_time}. Celkem uloženo: {len(results)} záznamů.")

if __name__ == "__main__":
    main()
