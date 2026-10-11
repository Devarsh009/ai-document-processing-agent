import concurrent.futures
import os
import time
import requests

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{BASE_URL}/process"
STATUS_URL = f"{BASE_URL}/status"
TEST_FOLDER = "test_samples"


def upload_document(filename: str):
    file_path = os.path.join(TEST_FOLDER, filename)
    if not os.path.exists(file_path):
        return f"❌ File not found: {filename}"

    print(f"📤 Uploading {filename}...")
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "text/plain")}
            response = requests.post(API_URL, files=files, timeout=10)
            if response.status_code == 200:
                data = response.json()
                doc_id = data.get("doc_id")
                return f"✅ {filename} Queued! Doc ID: {doc_id} -> Check: {STATUS_URL}/{doc_id}"
            else:
                return f"❌ {filename} Failed (HTTP {response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ Error uploading {filename}: {str(e)}"


def poll_status(doc_id: str, max_retries: int = 5, delay_sec: float = 2.0):
    for _ in range(max_retries):
        try:
            resp = requests.get(f"{STATUS_URL}/{doc_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status in ("completed", "failed"):
                    return data
            time.sleep(delay_sec)
        except Exception:
            pass
    return None


if __name__ == "__main__":
    if not os.path.exists(TEST_FOLDER):
        os.makedirs(TEST_FOLDER)
        print(f"⚠️ Created '{TEST_FOLDER}'. Please add sample .txt files and rerun.")
    else:
        files = [f for f in os.listdir(TEST_FOLDER) if f.endswith(".txt")]

        if not files:
            print("⚠️ No .txt files found in 'test_samples' folder.")
        else:
            print(f"🚀 Starting concurrent upload test for {len(files)} documents...\n")

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(upload_document, files))

            print("\n" + "\n".join(results))
            print("\n💡 You can poll status using: GET http://127.0.0.1:8000/status/<doc_id>")
            print("Check your Celery worker logs for live processing output!")