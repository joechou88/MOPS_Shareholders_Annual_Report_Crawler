## Python Scripts
#### 英文版-股東會年報(尚未適用永續揭露準則) (`download_shareholders_annual_reports.py`)
- **Retrieve all listed companies**

  Fetch all listed-company stock codes from [MOPS](https://mopsov.twse.com.tw/mops/web/t51sb01) for both the SII (上市) and OTC (上櫃). The Industry field is left blank to retrieve companies across all industries rather than the default Cement Industry, and the retrieved stock codes are saved to market-specific text files (`company_list_sii.txt` and `company_list_otc.txt`).
- **Download annual reports**

  Download the English-version Shareholders' Annual Reports from [MOPS](https://mopsov.twse.com.tw/mops/web/t57sb01_q5) for the target years and save them to market-specific directories (`./shareholders_annual_reports_sii` and `./shareholders_annual_reports_otc`). The script utilizes HTTP requests to bypass browser auto-download issues, natively supporting both .pdf and .zip file formats. For .zip downloads, it automatically extracts the internal PDF, standardizes the naming convention, and deletes the raw zip archive to maintain a clean directory.

- **Skip existing reports**

  Before each download, the script checks if the corresponding company-year report already exists locally. Furthermore, it scans the HTML page source to immediately identify companies that have not uploaded the target report, avoiding unnecessary element-waiting timeouts and significantly improving scraping efficiency.
- **Handle request limits**

  To prevent server bans, the script dynamically reacts to MOPS rate limits. It pauses for 10 seconds if a query-limit (查詢過量) is detected, and 60 seconds if a download-limit (下載過量) is encountered, before automatically retrying the request (up to a maximum of 3 retries per file).
- **Record failed downloads**

  Unexpected errors (e.g., HTTP errors or corrupt ZIP files) are safely skipped rather than crashing the crawler. All skipped cases, along with their specific error reasons, are exported to an Excel file (`failed_downloads_sii.xlsx` and `failed_downloads_otc.xlsx`) at the end of the run, allowing for easy tracking and future retries.