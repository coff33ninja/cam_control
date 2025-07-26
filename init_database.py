#!/usr/bin/env python3
"""
Database initialization script for MapConfigurationManager

This script ensures the database has all required tables and columns
for the configuration management system.
"""

import asyncio
import aiosqlite

DB_NAME = "camera_data.db"

async def init_database():
    """Initialize database with all required tables and columns."""
    print("🔧 Initializing database for configuration management...")
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Create map_configurations table if it doesn't exist
        print("📋 Creating map_configurations table...")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS map_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                configuration_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Check if coverage columns exist in cameras table
        print("🔍 Checking cameras table structure...")
        cursor = await db.execute("PRAGMA table_info(cameras)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add coverage columns if they don't exist
        if 'coverage_radius' not in column_names:
            print("➕ Adding coverage_radius column...")
            await db.execute("ALTER TABLE cameras ADD COLUMN coverage_radius REAL DEFAULT 50.0")
        
        if 'field_of_view_angle' not in column_names:
            print("➕ Adding field_of_view_angle column...")
            await db.execute("ALTER TABLE cameras ADD COLUMN field_of_view_angle REAL DEFAULT 360.0")
        
        if 'coverage_direction' not in column_names:
            print("➕ Adding coverage_direction column...")
            await db.execute("ALTER TABLE cameras ADD COLUMN coverage_direction REAL DEFAULT 0.0")
        
        await db.commit()
        
        # Verify the changes
        print("✅ Verifying database structure...")
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        print(f"   Tables: {[table[0] for table in tables]}")
        
        cursor = await db.execute("PRAGMA table_info(cameras)")
        columns = await cursor.fetchall()
        coverage_columns = [col[1] for col in columns if 'coverage' in col[1] or 'field_of_view' in col[1]]
        print(f"   Coverage columns: {coverage_columns}")
        
        # Check if we have any cameras to work with
        cursor = await db.execute("SELECT COUNT(*) FROM cameras")
        camera_count = (await cursor.fetchone())[0]
        print(f"   Current cameras in database: {camera_count}")
        
        if camera_count == 0:
            print("ℹ️  No cameras found. Adding sample cameras for testing...")
            await add_sample_cameras(db)
        
        print("✅ Database initialization completed!")

async def add_sample_cameras(db):
    """Add sample cameras for testing configuration management."""
    sample_cameras = [
        ("Main Entrance", "Camera 1", "00:11:22:33:44:55", "192.168.1.101", "Main Building", "2024-01-15", None, 40.7128, -74.0060, True, None, 75.0, 360.0, 0.0),
        ("Parking Lot", "Camera 2", "00:11:22:33:44:56", "192.168.1.102", "Parking", "2024-01-16", None, 40.7130, -74.0058, False, None, 100.0, 120.0, 45.0),
        ("Back Exit", "Camera 3", "00:11:22:33:44:57", "192.168.1.103", "Main Building", "2024-01-17", None, 40.7126, -74.0062, True, None, 60.0, 90.0, 180.0),
        ("Side Entrance", "Camera 4", "00:11:22:33:44:58", "192.168.1.104", "Main Building", "2024-01-18", None, 40.7132, -74.0056, False, None, 80.0, 180.0, 270.0),
        ("Reception Area", "Camera 5", "00:11:22:33:44:59", "192.168.1.105", "Interior", "2024-01-19", None, 40.7129, -74.0059, True, None, 50.0, 360.0, 0.0)
    ]
    
    for camera_data in sample_cameras:
        await db.execute("""
            INSERT INTO cameras (
                location, name, mac_address, ip_address, locational_group, 
                date_installed, dvr_id, latitude, longitude, has_memory_card, 
                memory_card_last_reset, coverage_radius, field_of_view_angle, coverage_direction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, camera_data)
    
    await db.commit()
    print(f"   ✅ Added {len(sample_cameras)} sample cameras")

if __name__ == "__main__":
    asyncio.run(init_database())