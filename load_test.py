import requests
import time
import json
import random

BASE_URL = "http://127.0.0.1:8000"
RECORD_COUNT = 1000

cities = ["Ankara", "Istanbul", "Izmir", "Bursa", "Antalya"]
professions = ["Engineer", "Statistician", "Designer", "Student", "Musician"]

print(f"Generating {RECORD_COUNT} records and sending to API. Please wait...")

start_time = time.time()

for i in range(1, RECORD_COUNT + 1):
    key = f"user:{i}"

    mock_data = {
        "id": i,
        "name": f"User_{i}",
        "age": random.randint(18, 65),
        "city": random.choice(cities),
        "profession": random.choice(professions),
        "score": round(random.uniform(10.0, 99.9), 2),
    }

    payload = {"value": json.dumps(mock_data)}

    response = requests.put(f"{BASE_URL}/keys/{key}", json=payload)

    if response.status_code != 200:
        print(f"Error: Could not write {key}. Status code: {response.status_code}")

end_time = time.time()
elapsed_time = end_time - start_time

print(f"\n--- LOAD TEST RESULTS ---")
print(f"Total records written: {RECORD_COUNT}")
print(f"Total time elapsed: {elapsed_time:.2f} seconds")
print(f"Write Throughput: {RECORD_COUNT / elapsed_time:.2f} req/sec")

# Random read verification
test_id = random.randint(1, RECORD_COUNT)
test_key = f"user:{test_id}"

print(f"\nVerification: Reading {test_key} from memory (O(1))...")
read_start = time.time()
get_response = requests.get(f"{BASE_URL}/keys/{test_key}")
read_end = time.time()

if get_response.status_code == 200:
    retrieved_data = get_response.json()
    print(f"Retrieved Value: {retrieved_data['value']}")
    print(f"Read latency: {(read_end - read_start) * 1000:.2f} ms")
else:
    print(f"Read error! Status code: {get_response.status_code}")
