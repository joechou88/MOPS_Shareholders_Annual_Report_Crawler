import os
import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC

def get_all_company_ids(driver):
    """Fetch all listed company IDs from MOPS."""
    driver.get("https://mopsov.twse.com.tw/mops/web/t51sb01")

    # Locate the industry dropdown and select the first blank option to search all industires
    industry_dropdown = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "code")))
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

# --- Settings ---
years = [112, 113, 114, 115]
save_dir = "shareholders_annual_reports"
# ----------------

os.makedirs(save_dir, exist_ok=True)
driver = webdriver.Chrome()

print("Fetching company list...")
companies = get_all_company_ids(driver)
print(f"Found {len(companies)} companies")
with open("company_list.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(companies))
print("Company list saved to company_list.txt")

print("Starting download process...")
failed_downloads = []

for cid in companies:
    for year in years:
        # Navigate directly to the target list page
        url = f"https://doc.twse.com.tw/server-java/t57sb01?co_id={cid}&year={year}&colorchg=1&step=1&mtype=F"
        while True:
            driver.get(url)

            if "查詢過量" in driver.page_source or "下載過量" in driver.page_source:
                print(f"Rate limited for {cid} ({year}). Pausing for 10 seconds...")
                time.sleep(10)
                continue
            
            break
            
        try:
            # Locate the row containing "英文版-股東會年報" (English Annual Report) and click the <a> tag
            xpath = "//td[contains(text(), '英文版-股東會年報')]/parent::tr//a"
            link = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))

            # Check if file exists before crawling
            expected_filename = link.text.strip()
            file_path = os.path.join(save_dir, expected_filename)
            
            if os.path.exists(file_path):
                print(f"Already exists, skipping: {expected_filename}")
                time.sleep(1)
                continue

            link.click()
        
            # Switch to the newly opened popup window
            WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(2))
            driver.switch_to.window(driver.window_handles[1])
            
            # Wait for the actual PDF link to load
            pdf_element = WebDriverWait(driver, 5).until(
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
            
        except Exception:
            print(f"Skipped: Company {cid}, Year {year} (Report not found, timeout, or rate-limited)")            
            failed_downloads.append(f"{cid} - {year}")

            # Error handling: ensure we return to the main window if something fails
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                
        time.sleep(random.uniform(5, 10)) # Delay to prevent server overload

driver.quit()
print("All download completed.")

if failed_downloads:
    print("\n--- Failed Downloads Summary ---")
    for item in failed_downloads:
        print(item)
