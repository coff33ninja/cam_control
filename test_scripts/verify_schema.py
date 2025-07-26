#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('camera_data.db')
cursor = conn.cursor()

print("=== CAMERAS TABLE ===")
cursor.execute("PRAGMA table_info(cameras)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} - {col[2]} {'(PK)' if col[5] else ''}")

print("\n=== DVRS TABLE ===")
cursor.execute("PRAGMA table_info(dvrs)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} - {col[2]} {'(PK)' if col[5] else ''}")

print("\n=== SCRIPT_LOCATIONS TABLE ===")
cursor.execute("PRAGMA table_info(script_locations)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} - {col[2]} {'(PK)' if col[5] else ''}")

print("\n=== SAMPLE DATA ===")
cursor.execute("SELECT COUNT(*) FROM cameras")
camera_count = cursor.fetchone()[0]
print(f"Cameras: {camera_count}")

cursor.execute("SELECT COUNT(*) FROM dvrs")
dvr_count = cursor.fetchone()[0]
print(f"DVRs: {dvr_count}")

cursor.execute("SELECT COUNT(*) FROM script_locations")
location_count = cursor.fetchone()[0]
print(f"Script locations: {location_count}")

if location_count > 0:
    cursor.execute("SELECT latitude, longitude, address, detection_method FROM script_locations LIMIT 1")
    location = cursor.fetchone()
    print(f"Sample location: {location[0]}, {location[1]} - {location[2]} ({location[3]})")

conn.close()