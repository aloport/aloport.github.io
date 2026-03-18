"""
Download survey responses from Qualtrics for the dating conjoint fieldwork monitor.
Designed for GitHub Actions: reads API token from QUALTRICS_API_TOKEN env var.
Saves {country}_latest.csv to ../data/ relative to this script.
"""

import io
import os
import time
import zipfile

import requests

API_TOKEN = os.environ["QUALTRICS_API_TOKEN"]
DATA_CENTER = "fra1"
BASE_URL = f"https://{DATA_CENTER}.qualtrics.com/API/v3"
HEADERS = {
    "X-API-TOKEN": API_TOKEN,
    "Content-Type": "application/json",
}

SURVEYS = {
    "germany": "SV_eeWw88fMUn9ZcLY",
    "austria": "SV_eOS1muETsvUk0S2",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")


def download_survey(country, survey_id):
    print(f"\n[{country.upper()}] Downloading survey {survey_id}...")

    # Step 1: Create export
    url = f"{BASE_URL}/surveys/{survey_id}/export-responses"
    payload = {"format": "csv", "useLabels": True}
    r = requests.post(url, headers=HEADERS, json=payload)
    if r.status_code != 200:
        print(f"  FAILED to create export: {r.status_code} {r.text[:200]}")
        return None

    progress_id = r.json()["result"]["progressId"]
    print(f"  Export created: {progress_id}")

    # Step 2: Poll until complete
    check_url = f"{url}/{progress_id}"
    for attempt in range(60):
        time.sleep(2)
        r = requests.get(check_url, headers=HEADERS)
        if r.status_code != 200:
            print(f"  Poll error: {r.status_code}")
            continue
        result = r.json()["result"]
        pct = result["percentComplete"]
        if pct == 100:
            file_id = result["fileId"]
            print(f"  Export complete: {file_id}")
            break
        print(f"  Progress: {pct}%...")
    else:
        print("  TIMEOUT waiting for export")
        return None

    # Step 3: Download ZIP and extract CSV
    download_url = f"{url}/{file_id}/file"
    r = requests.get(download_url, headers=HEADERS)
    if r.status_code != 200:
        print(f"  FAILED to download: {r.status_code}")
        return None

    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv_names = [n for n in z.namelist() if n.endswith(".csv")]
    if not csv_names:
        print("  ERROR: No CSV found in ZIP")
        return None

    csv_data = z.read(csv_names[0])
    print(f"  Downloaded: {csv_names[0]} ({len(csv_data)} bytes)")

    latest_path = os.path.join(DATA_DIR, f"{country}_latest.csv")
    with open(latest_path, "wb") as f:
        f.write(csv_data)
    print(f"  Saved: {latest_path}")
    return latest_path


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    for country, survey_id in SURVEYS.items():
        csv_path = download_survey(country, survey_id)
        if csv_path:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                n = max(0, len(f.readlines()) - 3)
            print(f"  Responses: {n}")
        time.sleep(1)
    print("\nDone.")


if __name__ == "__main__":
    main()
