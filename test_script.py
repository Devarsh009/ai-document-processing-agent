import concurrent.futures
import os
import time
import requests

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{BASE_URL}/v1/documents"
STATUS_URL = f"{BASE_URL}/v1/documents"
TEST_FOLDER = "test_samples"


def upload_document(filename: str):
    file_path = os.path.join(TEST_FOLDER, filename)
    if not os.path.exists(file_path):
        return f"[ERROR] File not found: {filename}"

    print(f"[UPLOAD] Uploading {filename}...")
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "text/plain")}
            response = requests.post(API_URL, files=files, timeout=10)
            if response.status_code in (200, 202):
                data = response.json()
                doc_id = data.get("id") or data.get("doc_id")
                return f"[QUEUED] {filename} -> ID: {doc_id} (Status: {STATUS_URL}/{doc_id})"
            else:
                return f"[FAILED] {filename} (HTTP {response.status_code}): {response.text}"
    except Exception as e:
        return f"[ERROR] Failed uploading {filename}: {str(e)}"


def poll_status(doc_id: str, max_retries: int = 5, delay_sec: float = 2.0):
    for _ in range(max_retries):
        try:
            resp = requests.get(f"{STATUS_URL}/{doc_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status in ("succeeded", "needs_review", "failed"):
                    return data
            time.sleep(delay_sec)
        except Exception:
            pass
    return None


if __name__ == "__main__":
    if not os.path.exists(TEST_FOLDER):
        os.makedirs(TEST_FOLDER)
        print(f"[INFO] Created '{TEST_FOLDER}'. Please add sample files and rerun.")
    else:
        files = [f for f in os.listdir(TEST_FOLDER) if f.endswith(".txt")]

        if not files:
            print("[INFO] No sample files found in 'test_samples' folder.")
        else:
            print(f"[START] Starting upload test for {len(files)} documents...\n")

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(upload_document, files))

            print("\n" + "\n".join(results))
            print(f"\n[INFO] Poll document status via: GET {STATUS_URL}/<doc_id>")
            print("Check Celery worker logs for asynchronous processing progress.")