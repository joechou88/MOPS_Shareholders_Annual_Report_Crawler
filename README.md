## Python Scripts
#### 英文版-股東會年報(尚未適用永續揭露準則) (`download_shareholders_annual_reports.py`)
- **Retrieve all listed companies**

  Fetch all listed-company stock codes from [MOPS](https://mopsov.twse.com.tw/mops/web/t51sb01). The Industry field should be left blank to retrieve companies across all industries rather than the default Cement Industry.
- **Download annual reports**

  Download the English-version Shareholders' Annual Reports from [MOPS](https://mopsov.twse.com.tw/mops/web/t57sb01_q5) for the target years and save them to `./shareholders_annual_reports`.

- **Skip existing reports**

  Before each download, check whether the corresponding company-year report already exists in `./shareholders_annual_reports`. If it has already been downloaded, skip it to avoid unnecessary requests and save time.
- **Handle request limits**

  If MOPS returns a query-limit or download-limit response, wait 10 seconds before sending the same request again to reduce the risk of excessive requests and skipped companies.
- **Record failed downloads**

  Unexpected errors for a company-year are skipped rather than stopping the crawler. Failed cases are recorded in the `failed_downloads` list and printed at the end, allowing them to be manually downloaded if necessary.