## Python Scripts
#### 英文版-股東會年報 (`download_shareholders_annual_reports.py`)
- **Retrieve all listed companies**

  Fetch all listed-company stock codes from [MOPS](https://mopsov.twse.com.tw/mops/web/t51sb01) for both the SII (上市) and OTC (上櫃). The Industry field is left blank to retrieve companies across all industries rather than the default Cement Industry, and the retrieved stock codes are saved to market-specific text files (`company_list_sii.txt` and `company_list_otc.txt`).
- **Retry failed downloads**

  Displays a prompt in the terminal: `"Retry failed companies only (excluding 'NoReportFound')? (y/n): "`. Entering `y` allows you to retry only the specific company-year pairs that failed in previous runs, reading target lists directly from the exported Excel files. 
  
  **Note:** If you haven't performed a full run yet, you must enter `n`.
- **Download annual reports**

  Download the English-version Shareholders' Annual Reports from [MOPS](https://mopsov.twse.com.tw/mops/web/t57sb01_q5) for the target years and save them to market-specific directories (`./shareholders_annual_reports_sii` and `./shareholders_annual_reports_otc`). The script utilizes HTTP requests to bypass browser auto-download issues, natively supporting .doc, .docx, .pdf and .zip file formats. For .zip downloads, it automatically extracts the internal file, standardizes the naming convention, and deletes the raw zip archive to maintain a clean directory.

- **Skip existing reports and missing files (NoReportFound)**

  Before each download, the script checks if the corresponding company-year report already exists locally. Furthermore, it scans the HTML page source to immediately identify companies that have not uploaded the target report, avoiding unnecessary element-waiting timeouts and significantly improving scraping efficiency.
- **Handle request limits**

  To prevent server bans, the script dynamically reacts to MOPS rate limits. It pauses for 10 seconds if a query-limit (查詢過量) is detected, and 60 seconds if a download-limit (下載過量) is encountered, before automatically retrying the request (up to a maximum of 3 retries per file).
- **Record failed downloads**

  Unexpected errors (e.g., HTTP errors or corrupt ZIP files) are safely skipped rather than crashing the crawler. All skipped cases, along with their specific error reasons, are exported to an Excel file (`failed_downloads_sii.xlsx` and `failed_downloads_otc.xlsx`) at the end of the run, allowing for easy tracking and future retries.

## Error & Troubleshooting

When a file fails to download, the script records a specific error code in the `failed_downloads_<market>.xlsx` file. Here is what each error means and how the script handles it:

| Error | Description | Script Behavior |
| :--- | :--- | :--- |
| `NoReportFound` | The company has not uploaded the target report for the specified year. | The script safely skips this without retrying and retains the record to avoid redundant checks in future runs. |
| `OutOfQueryLimit` / `OutOfDownloadLimit` | The IP was temporarily throttled by the MOPS server. | The script pauses automatically (10s for query limit, 60s for download limit) and then retries up to 3 times per file. |
| `DownloadLinkNotFound` | The script submitted the request form but couldn't locate a valid `.pdf`, `.zip`, or `.docx` URL in the server's response (possible malformed page). | The script sleeps for 5 seconds, resets the browser, and retries up to 3 times per file. |
| `WebDriverException` | Chrome crashed (often due to out-of-memory issues over time) or was manually closed by the user. | The script sleeps for 5 seconds, automatically respawns a fresh Chrome driver, and retries up to 3 times per file. |
| `BadZipFile` / `NoValidFileInZip` | The downloaded ZIP file was corrupt, or it contained no recognizable document formats. | The script deletes the corrupted file and skips to the next company without retrying. |
| `HTTP_xxx` (e.g., `HTTP_404`, `HTTP_500`) | Standard HTTP connection error or server-side crash. | The script sleeps for 5 seconds, resets the session, and retries up to 3 times per file. |
| `MaxRetriesExceeded` | The script attempted to download the file 3 times, but all attempts failed due to recurring network or server errors. | The script logs the final failure and moves to the next file. |
