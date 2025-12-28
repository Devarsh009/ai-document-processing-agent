import requests
import os
import time
import concurrent.futures

# Configuration
API_URL = "http://127.0.0.1:8000/process"
TEST_FOLDER = "test_samples"

def upload_document(filename):
    file_path = os.path.join(TEST_FOLDER, filename)
    if not os.path.exists(file_path):
        return f"❌ File not found: {filename}"

    print(f"📤 Uploading {filename}...")
    try:
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "text/plain")}
            response = requests.post(API_URL, files=files)
            if response.status_code == 200:
                data = response.json()
                return f"✅ {filename} Queued! ID: {data['doc_id']}"
            else:
                return f"❌ {filename} Failed: {response.text}"
    except Exception as e:
        return f"❌ Error uploading {filename}: {str(e)}"

if __name__ == "__main__":
    # Create the folder if it doesn't exist
    if not os.path.exists(TEST_FOLDER):
        os.makedirs(TEST_FOLDER)
        print(f"⚠️ Created '{TEST_FOLDER}'. Please put your .txt files there and run again.")
    else:
        files = [f for f in os.listdir(TEST_FOLDER) if f.endswith(".txt")]
        
        if not files:
            print("⚠️ No .txt files found in 'test_samples' folder.")
        else:
            print(f"🚀 Starting Concurrent Test for {len(files)} documents...\n")
            
            # Use ThreadPool to simulate concurrent users
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                results = list(executor.map(upload_document, files))
            
            print("\n" + "\n".join(results))
            print("\nCheck your Celery terminal for processing logs!")