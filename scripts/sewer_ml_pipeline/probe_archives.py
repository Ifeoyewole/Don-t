import os
import urllib.request
import base64

password = os.environ.get("SEWER_PASSWORD", "").strip()
base_url = "https://sciencedata.dk/public/Large%20AAU%20files/Sewer_ML"

auth_header = "Basic " + base64.b64encode(f"operator:{password}".encode()).decode()

files = [
    "LICENSE.txt",
    "README.txt",
    "SewerML_Test.csv",
    "SewerML_Train.csv",
    "SewerML_Val.csv",
    "test00.zip",
    "test01.zip",
    "valid00.zip",
    "valid01.zip",
] + [f"train{i:02d}.zip" for i in range(14)]

print(f"{'Filename':<20} | {'Bytes':<15} | {'Size (GB)':<10}")
print("-" * 50)
total_bytes = 0
for fname in files:
    url = f"{base_url}/{fname}"
    req = urllib.request.Request(url, headers={"Authorization": auth_header}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            cl = int(resp.headers.get("Content-Length", 0))
            gb = cl / (1024 ** 3)
            total_bytes += cl
            print(f"{fname:<20} | {cl:<15} | {gb:<10.3f} GB")
    except Exception as e:
        print(f"{fname:<20} | ERROR: {e}")

print("-" * 50)
print(f"TOTAL REPOSITORY SIZE: {total_bytes / (1024 ** 3):.2f} GB ({total_bytes} bytes)")
