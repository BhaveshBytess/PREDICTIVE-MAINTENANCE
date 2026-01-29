import os
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# --- HARDCODED CREDENTIALS FOR DEBUGGING ---
# We are bypassing .env to ensure no loading errors
URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
TOKEN = "kg2i8MqhVqYcS0JjNV7W7RYuV92cadByrIK14XAIMlL7izJxMRRKNMxUqGH-OStxSRo5EhYkkRlcMh7JKlPkmw=="
ORG = "67c4314d97304c09"
BUCKET = "sensor_data"

print(f"--- DIAGNOSTIC START ---")
print(f"Targeting Org: {ORG}")
print(f"Targeting Bucket: {BUCKET}")

try:
    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)

    # 1. Test Health
    health = client.health()
    print(f"Health Status: {health.status}")

    # 2. Test Write (The moment of truth)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    point = Point("debug_test").field("value", 1.0)

    print("Attempting write...")
    write_api.write(bucket=BUCKET, org=ORG, record=point)
    print("✅ SUCCESS! Write completed without error.")

except Exception as e:
    print("❌ FAILURE! Here is the exact error:")
    print(e)
finally:
    print("--- DIAGNOSTIC END ---")
