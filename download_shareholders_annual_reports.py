import os
import pandas as pd
import time
import random
import requests
import re
import zipfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

def get_all_company_ids(driver, market_type='sii'):
    driver.get("https://mopsov.twse.com.tw/mops/web/t51sb01")

    # Locate the market type dropdown and select 'sii' or 'otc'
    typek_dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//select[@name='TYPEK']"))
    )
    Select(typek_dropdown).select_by_value(market_type)

    time.sleep(2)

    # Locate the industry dropdown and select the first blank option to search all industires
    industry_dropdown = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//select[@name='code']"))
    )
    Select(industry_dropdown).select_by_index(0)
    
    # Click the search button
    search_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//input[@type='button' and contains(@value, '查詢')]"))
    )
    search_btn.click()
    
    # Wait for the results table to load
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='table01']//tr[@class='even' or @class='odd']/td[1]"))
    )
    
    # Extract IDs from the first column of the table
    elements = driver.find_elements(By.XPATH, "//div[@id='table01']//tr[@class='even' or @class='odd']/td[1]")
    
    # Clean and filter numerical IDs
    return [el.text.strip() for el in elements if el.text.strip().isdigit()]

def setup_driver():
    """Initialize Chrome with memory-saving flags to prevent crashes."""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    # Stop waiting for images and external scripts to load
    options.page_load_strategy = 'eager'
    options.add_argument("--blink-settings=imagesEnabled=false")

    # Anti-bot detection flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return webdriver.Chrome(options=options)

def setup_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Referer": "https://doc.twse.com.tw/server-java/t57sb01",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
    })
    return s

# --- Settings ---
years = [112, 113, 114, 115]
markets = ['sii', 'otc']
# ----------------

retry_mode = input("Retry failed companies only (excluding 'NoReportFound')? (y/n): ").strip().lower() == 'y'

for market in markets:
    save_dir = f"shareholders_annual_reports_{market}"
    list_file = f"company_list_{market}.txt"
    failed_file = f"failed_downloads_{market}.xlsx"

    os.makedirs(save_dir, exist_ok=True)
    skipped_records_df = pd.DataFrame()

    if retry_mode and os.path.exists(failed_file):
        print(f"\n[{market.upper()}] Loading target (company, year) pairs from {failed_file}...")
        df = pd.read_excel(failed_file)
        skipped_records_df = df[df['error_reason'] == 'NoReportFound']
        df = df[df['error_reason'] != 'NoReportFound']
        df['company_id'] = df['company_id'].astype(str)
        target_tasks = df.groupby('company_id')['year'].apply(list).to_dict()
        companies = list(target_tasks.keys())
    else: 
        print(f"\n[{market.upper()}] Fetching company list...")
        driver = setup_driver()
        companies = get_all_company_ids(driver, market)

        target_tasks = {cid: years for cid in companies}

        with open(list_file, "w", encoding="utf-8") as f:
            f.write("\n".join(companies))
        print(f"[{market.upper()}] Company list saved to {list_file}")
        driver.quit()

    print(f"[{market.upper()}] Starting download process...")
    failed_downloads = []
    existing_files = set(
        f for f in os.listdir(save_dir) 
        if f.lower().endswith(('.pdf', '.doc', '.docx'))
    )
    driver = None  # The browser is only launched when there are missing files to download.

    for cid in companies:
        for year in target_tasks[cid]:
            pattern = f"{year+1910}_{cid}"
            already_downloaded = any(pattern in f for f in existing_files)
            
            if already_downloaded:
                print(f"Already exists locally, skipping request: {cid} ({year})")
                continue

            # Navigate directly to the target list page
            url = f"https://doc.twse.com.tw/server-java/t57sb01?co_id={cid}&year={year}&colorchg=1&step=1&mtype=F"

            retry_download = True
            retry_count = 0
            max_retries = 3
            last_error = None

            while retry_download and retry_count < max_retries:
                if driver is None:
                    driver = setup_driver()
                    req_session = setup_session()

                try:
                    driver.get(url)
                    page_src = driver.page_source

                    if "查詢過量" in driver.page_source:
                        retry_count += 1
                        last_error = "OutOfQueryLimit"
                        print(f"Rate limited [查詢過量] for {cid} ({year}). Pausing for 10 seconds...")
                        time.sleep(10)
                        continue

                    if "英文版-股東會年報" not in driver.page_source:
                        last_error = "NoReportFound"
                        print(f"Target report not found for {cid} ({year}), logging and skipping.")
                        break

                    # Locate the row containing "英文版-股東會年報" (English Annual Report) and click the <a> tag
                    xpath = "//td[contains(text(), '英文版-股東會年報')]/parent::tr//a"
                    link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))

                    # Check if file exists before crawling
                    expected_filename = link.text.strip()
                    file_path = os.path.join(save_dir, expected_filename)
                    
                    if os.path.exists(file_path):
                        print(f"Already exists, skipping: {expected_filename}")
                        retry_download = False
                        break
                    
                    file_url = link.get_attribute('href')

                    if file_url.startswith('javascript:'):
                        print(f"Downloading: {expected_filename} (via form submission)...")
                        dl_url = "https://doc.twse.com.tw/server-java/t57sb01"
                        payload = {
                            "colorchg": "1",
                            "step": "9",
                            "kind": "F",
                            "co_id": cid,
                            "filename": expected_filename,
                            "DEBUG": "",
                            "SKEY1": "",
                            "SKEY2": "",
                            "YEAR": "",
                            "MDATE": "",
                            "TYPE": ""
                        }
                        res = req_session.post(dl_url, data=payload, timeout=20)

                        if b"<html" in res.content[:500].lower():
                            matches = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                            real_path = next((m for m in matches if any(ext in m.lower() for ext in ['.pdf', '.zip', '.doc', '.docx'])), None)
                            
                            if real_path:
                                real_url = "https://doc.twse.com.tw" + real_path if not real_path.startswith('http') else real_path
                                res = req_session.get(real_url, timeout=30) 
                            else:
                                raise Exception("DownloadLinkNotFound")

                    else:
                        if not file_url.startswith('http'):
                            file_url = "https://doc.twse.com.tw" + file_url
                            
                        print(f"Downloading: {expected_filename}...")
                        res = req_session.get(file_url, timeout=20)
                        
                    if res.status_code == 200:

                        if b"\xe4\xb8\x8b\xe8\xbc\x89\xe9\x81\x8e\xe9\x87\x8f" in res.content:
                            retry_count += 1
                            limit_reason = "OutOfDownloadLimit"
                            print(f"Rate limited [下載過量] for {cid} ({year}). Pausing for 60 seconds...")
                            time.sleep(60)
                            continue
                        
                        with open(file_path, 'wb') as f:
                            f.write(res.content)

                        if expected_filename.lower().endswith('.zip'):
                            print(f"  -> Handle .zip and rename .pdf inside it...")
                            try:
                                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                    target_files = [
                                        name for name in zip_ref.namelist() 
                                        if name.lower().endswith(('.pdf', '.docx', '.doc'))
                                    ]
                                    
                                    if target_files:
                                        target_filename = target_files[0]
                                        file_data = zip_ref.read(target_filename)
                                        
                                        base_name = os.path.splitext(expected_filename)[0]
                                        ext = os.path.splitext(target_filename)[1] 
                                        new_file_name = f"{base_name}{ext}"
                                        new_file_path = os.path.join(save_dir, new_file_name)
                                        
                                        with open(new_file_path, 'wb') as f_out:
                                            f_out.write(file_data)
                                            
                                        print(f"  -> Extracted and saved as: {new_file_name}")
                                    else:
                                        last_error = "NoValidFileInZip"
                                        print(f"  -> No valid PDF/Word file found inside {expected_filename}")
                                        os.remove(file_path)
                                        break

                                os.remove(file_path)
                                
                            except zipfile.BadZipFile:
                                last_error = "BadZipFile"
                                print(f"  -> Downloaded file is not a valid .zip file.")
                                if os.path.exists(file_path): os.remove(file_path)
                                break

                        retry_download = False
                        print(f"  -> .pdf saved successfully.")

                    else:
                        raise Exception(f"HTTP_{res.status_code}")

                except Exception as e:
                    custom_errors = ["OutOfQueryLimit", "OutOfDownloadLimit", "DownloadLinkNotFound", "MaxRetriesExceeded"]
                    err_reason = str(e) if str(e) in custom_errors else type(e).__name__
                    last_error = err_reason
                    retry_count += 1
                    
                    print(f"Error for {cid} ({year}): {err_reason}. Resetting and retrying ({retry_count}/{max_retries})...")

                    if driver is not None:
                        try: driver.quit()
                        except: pass
                        driver = None
                        req_session = None

                    print(f"Unexpected error occurred for {cid} ({year}). Pausing for 5 seconds...")
                    time.sleep(5)

            if retry_download:
                err_reason = last_error or "MaxRetriesExceeded"
                print(f"Skipped: Company {cid}, Year {year} (Final Error: {err_reason})")
                
                # Check if it wasn't already logged by the Zip exceptions
                if not any(f[0] == cid and f[1] == year for f in failed_downloads):
                    failed_downloads.append([cid, year, err_reason])
                
                if driver is not None:
                    try: driver.quit()
                    except: pass
                    driver = None
                    req_session = None
                    
            time.sleep(random.uniform(5, 10)) # Delay to prevent server overload

    if driver is not None:
        driver.quit()

    final_failures_df = pd.DataFrame(failed_downloads, columns=["company_id", "year", "error_reason"])
    if not skipped_records_df.empty:
        final_failures_df = pd.concat([skipped_records_df, final_failures_df], ignore_index=True)

    if not final_failures_df.empty:
        final_failures_df.to_excel(failed_file, index=False)        
        print(f"[{market.upper()}] Failed downloads exported to '{failed_file}' for future retry.")

    print(f"[{market.upper()}] All downloads completed.")
