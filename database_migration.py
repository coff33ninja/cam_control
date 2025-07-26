#!/usr/bin/env python3
"""
Database migration script for DVR support and location features

This script extends the database schema to support:
- DVR table with custom naming and location fields
- Extended cameras table with custom_name, dvr_id, and address columns
- Script locations table for storing detected execution locations
"""

import asyncio
import aiosqlite
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_NAME = "camera_data.db"

class DatabaseMigration:
    """Handles database schema migrations for DVR and location features."""
    
    def __init__(self, db_path: str = DB_NAME):
        self.db_path = db_path
    
    async def run_migrations(self) -> Dict[str, bool]:
        """Run all database migrations and return status."""
        print("🔧 Starting database migrations for DVR support and location features...")
        
        results = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign key constraints
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Run individual migrations
            results['cameras_table'] = await self._migrate_cameras_table(db)
            results['dvrs_table'] = await self._migrate_dvrs_table(db)
            results['script_locations_table'] = await self._create_script_locations_table(db)
            
            # Commit all changes
            await db.commit()
            
            # Verify migrations
            await self._verify_migrations(db)
        
        print("✅ Database migrations completed successfully!")
        return results
    
    async def _migrate_cameras_table(self, db: aiosqlite.Connection) -> bool:
        """Add missing columns to cameras table."""
        print("📋 Migrating cameras table...")
        
        try:
            # Get current table structure
            cursor = await db.execute("PRAGMA table_info(cameras)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add custom_name column if it doesn't exist
            if 'custom_name' not in column_names:
                print("  ➕ Adding custom_name column to cameras table...")
                await db.execute("ALTER TABLE cameras ADD COLUMN custom_name TEXT")
            else:
                print("  ✓ custom_name column already exists")
            
            # Add address column if it doesn't exist
            if 'address' not in column_names:
                print("  ➕ Adding address column to cameras table...")
                await db.execute("ALTER TABLE cameras ADD COLUMN address TEXT")
            else:
                print("  ✓ address column already exists")
            
            # Verify dvr_id column exists (should already exist based on earlier check)
            if 'dvr_id' not in column_names:
                print("  ➕ Adding dvr_id column to cameras table...")
                await db.execute("ALTER TABLE cameras ADD COLUMN dvr_id INTEGER REFERENCES dvrs(id)")
            else:
                print("  ✓ dvr_id column already exists")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error migrating cameras table: {e}")
            return False
    
    async def _migrate_dvrs_table(self, db: aiosqlite.Connection) -> bool:
        """Add missing columns to dvrs table or create if it doesn't exist."""
        print("📋 Migrating dvrs table...")
        
        try:
            # Check if dvrs table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dvrs'"
            )
            table_exists = await cursor.fetchone()
            
            if not table_exists:
                print("  ➕ Creating dvrs table...")
                await db.execute("""
                    CREATE TABLE dvrs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        custom_name TEXT,
                        dvr_type TEXT,
                        location TEXT,
                        ip_address TEXT NOT NULL,
                        mac_address TEXT,
                        storage_capacity TEXT,
                        date_installed TEXT,
                        latitude REAL,
                        longitude REAL,
                        address TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                return True
            
            # Get current table structure
            cursor = await db.execute("PRAGMA table_info(dvrs)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add custom_name column if it doesn't exist
            if 'custom_name' not in column_names:
                print("  ➕ Adding custom_name column to dvrs table...")
                await db.execute("ALTER TABLE dvrs ADD COLUMN custom_name TEXT")
            else:
                print("  ✓ custom_name column already exists")
            
            # Add address column if it doesn't exist
            if 'address' not in column_names:
                print("  ➕ Adding address column to dvrs table...")
                await db.execute("ALTER TABLE dvrs ADD COLUMN address TEXT")
            else:
                print("  ✓ address column already exists")
            
            # Add created_at column if it doesn't exist
            if 'created_at' not in column_names:
                print("  ➕ Adding created_at column to dvrs table...")
                await db.execute("ALTER TABLE dvrs ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'))")
            else:
                print("  ✓ created_at column already exists")
            
            # Add updated_at column if it doesn't exist
            if 'updated_at' not in column_names:
                print("  ➕ Adding updated_at column to dvrs table...")
                await db.execute("ALTER TABLE dvrs ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))")
            else:
                print("  ✓ updated_at column already exists")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error migrating dvrs table: {e}")
            return False
    
    async def _create_script_locations_table(self, db: aiosqlite.Connection) -> bool:
        """Create script_locations table for storing detected execution locations."""
        print("📋 Creating script_locations table...")
        
        try:
            # Check if table already exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='script_locations'"
            )
            table_exists = await cursor.fetchone()
            
            if table_exists:
                print("  ✓ script_locations table already exists")
                return True
            
            print("  ➕ Creating script_locations table...")
            await db.execute("""
                CREATE TABLE script_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    address TEXT,
                    detection_method TEXT,
                    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
                    is_current BOOLEAN DEFAULT 1,
                    confidence_score REAL DEFAULT 1.0,
                    CONSTRAINT valid_coordinates CHECK (
                        latitude >= -90 AND latitude <= 90 AND
                        longitude >= -180 AND longitude <= 180
                    )
                )
            """)
            
            # Create index for faster queries
            await db.execute("""
                CREATE INDEX idx_script_locations_current 
                ON script_locations(is_current, detected_at DESC)
            """)
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error creating script_locations table: {e}")
            return False
    
    async def _verify_migrations(self, db: aiosqlite.Connection) -> None:
        """Verify that all migrations were applied successfully."""
        print("🔍 Verifying database migrations...")
        
        # Check cameras table structure
        cursor = await db.execute("PRAGMA table_info(cameras)")
        cameras_columns = [col[1] for col in await cursor.fetchall()]
        required_cameras_columns = ['custom_name', 'address', 'dvr_id']
        
        for col in required_cameras_columns:
            if col in cameras_columns:
                print(f"  ✓ cameras.{col} exists")
            else:
                print(f"  ❌ cameras.{col} missing")
        
        # Check dvrs table structure
        cursor = await db.execute("PRAGMA table_info(dvrs)")
        dvrs_columns = [col[1] for col in await cursor.fetchall()]
        required_dvrs_columns = ['custom_name', 'address', 'created_at', 'updated_at']
        
        for col in required_dvrs_columns:
            if col in dvrs_columns:
                print(f"  ✓ dvrs.{col} exists")
            else:
                print(f"  ❌ dvrs.{col} missing")
        
        # Check script_locations table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='script_locations'"
        )
        if await cursor.fetchone():
            print("  ✓ script_locations table exists")
        else:
            print("  ❌ script_locations table missing")
        
        # Show final table count
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        print(f"  📊 Total tables in database: {len(tables)}")
        for table in tables:
            if table[0] != 'sqlite_sequence':
                print(f"    - {table[0]}")

# Migration utility functions
async def add_sample_script_location(db_path: str = DB_NAME) -> bool:
    """Add a sample script location for testing."""
    try:
        async with aiosqlite.connect(db_path) as db:
            # Add a sample location (New York City)
            await db.execute("""
                INSERT INTO script_locations 
                (latitude, longitude, address, detection_method, is_current, confidence_score)
                VALUES (40.7128, -74.0060, 'New York, NY, USA', 'default', 1, 0.5)
            """)
            await db.commit()
            print("✅ Added sample script location")
            return True
    except Exception as e:
        print(f"❌ Error adding sample script location: {e}")
        return False

async def update_existing_dvr_timestamps(db_path: str = DB_NAME) -> bool:
    """Update existing DVR records with timestamps if they don't have them."""
    try:
        async with aiosqlite.connect(db_path) as db:
            current_time = datetime.now().isoformat()
            
            # Update records where created_at or updated_at is NULL
            await db.execute("""
                UPDATE dvrs 
                SET created_at = ?, updated_at = ?
                WHERE created_at IS NULL OR updated_at IS NULL
            """, (current_time, current_time))
            
            rows_affected = db.total_changes
            await db.commit()
            
            if rows_affected > 0:
                print(f"✅ Updated timestamps for {rows_affected} DVR records")
            else:
                print("✓ All DVR records already have timestamps")
            
            return True
    except Exception as e:
        print(f"❌ Error updating DVR timestamps: {e}")
        return False

# Main migration function
async def run_database_migration() -> bool:
    """Run the complete database migration process."""
    migration = DatabaseMigration()
    
    try:
        # Run migrations
        results = await migration.run_migrations()
        
        # Add sample data if needed
        await add_sample_script_location()
        await update_existing_dvr_timestamps()
        
        # Check if all migrations succeeded
        all_successful = all(results.values())
        
        if all_successful:
            print("🎉 All database migrations completed successfully!")
        else:
            print("⚠️  Some migrations failed. Check the output above for details.")
        
        return all_successful
        
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_database_migration())
    exit(0 if success else 1)