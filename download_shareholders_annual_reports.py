import os
import pandas as pd
import time
import random
import requests
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

    # Anti-bot detection flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return webdriver.Chrome(options=options)

# --- Settings ---
years = [112, 113, 114, 115]
markets = ['sii', 'otc']
# ----------------

for market in markets:
    save_dir = f"shareholders_annual_reports_{market}"
    list_file = f"company_list_{market}.txt"
    failed_file = f"failed_downloads_{market}.xlsx"

    os.makedirs(save_dir, exist_ok=True)

    print(f"\n[{market.upper()}] Fetching company list...")
    driver = setup_driver()
    companies = get_all_company_ids(driver, market)
    
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
        for year in years:
            pattern = f"{year+1910}_{cid}"
            already_downloaded = any(pattern in f for f in existing_files)
            
            if already_downloaded:
                print(f"Already exists locally, skipping request: {cid} ({year})")
                continue

            if driver is None:
                driver = setup_driver()

            # Navigate directly to the target list page
            url = f"https://doc.twse.com.tw/server-java/t57sb01?co_id={cid}&year={year}&colorchg=1&step=1&mtype=F"

            try:
                retry_download = True
                retry_count = 0
                max_retries = 3

                while retry_download and retry_count < max_retries:
                    driver.get(url)
                    page_src = driver.page_source

                    if "查詢過量" in driver.page_source:
                        retry_count += 1
                        print(f"Rate limited [查詢過量] for {cid} ({year}). Pausing for 10 seconds...")
                        time.sleep(10)
                        continue

                    if "英文版-股東會年報" not in driver.page_source:
                        print(f"Target report not found for {cid} ({year}), logging and skipping.")
                        failed_downloads.append([cid, year, "NoReportFound"])
                        retry_download = False
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

                    link.click()
                
                    # Switch to the newly opened popup window
                    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                    driver.switch_to.window(driver.window_handles[1])

                    if "下載過量" in driver.page_source:
                            retry_count += 1
                            print(f"Rate limited [下載過量] for {cid} ({year}). Pausing for 60 seconds...")
                            time.sleep(60)
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            continue
                    
                    # Wait for the actual PDF link to load
                    pdf_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '.pdf')]"))
                    )
                    
                    pdf_url = pdf_element.get_attribute('href')
                    pdf_name = pdf_element.text
                    
                    if not pdf_url.startswith('http'):
                        pdf_url = "https://doc.twse.com.tw" + pdf_url
                        
                    print(f"Downloading: {pdf_name}...")
                    
                    # Download the PDF directly via requests to bypass browser PDF viewer
                    res = requests.get(pdf_url, timeout=10)
                    if res.status_code == 200:
                        with open(os.path.join(save_dir, pdf_name), 'wb') as f:
                            f.write(res.content)
                        print(f"  -> Saved successfully.")
                    
                    # Close the popup window and switch back to the main window
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                    retry_download = False

                if retry_count >= max_retries:
                    raise Exception("MaxRetriesExceeded")

            except Exception as e:
                print(f"Skipped: Company {cid}, Year {year} (Error: {type(e).__name__})")            
                failed_downloads.append([cid, year, type(e).__name__])

                if driver is not None:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None

                print(f"Unexpected error occurred for {cid} ({year}). Pausing for 30 seconds...")
                time.sleep(30)
                    
            time.sleep(random.uniform(5, 10)) # Delay to prevent server overload

    if driver is not None:
        driver.quit()

    if failed_downloads:
        df = pd.DataFrame(failed_downloads, columns=["company_id", "year", "error_reason"])
        df.to_excel(failed_file, index=False)        
        print(f"[{market.upper()}] Failed downloads exported to '{failed_file}' for future retry.")

    print(f"[{market.upper()}] All downloads completed.")
