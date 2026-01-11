"""Test the exact query that's failing."""
from backend.storage import SensorEventWriter, MEASUREMENT_NAME

client = SensorEventWriter()
client.connect()

# The exact asset_id we know exists
test_id = "debug-c504d041"

# Build exact same query as query_latest_events
query = f'''
from(bucket: "{client.config.bucket}")
    |> range(start: -30d)
    |> filter(fn: (r) => r._measurement == "{MEASUREMENT_NAME}")
    |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    |> filter(fn: (r) => r.asset_id == "{test_id}")
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: 10)
'''

print("Query:")
print(query)
print()

tables = client._client.query_api().query(query, org=client.config.org)
print(f"Tables: {len(tables)}")

for t in tables:
    print(f"  Records: {len(t.records)}")
    for r in t.records:
        print(f"    asset_id={r.values.get('asset_id')}")

client.disconnect()
