"""
Database Migration for DVR Management System

This module handles database schema updates for the enhanced DVR management system,
adding custom naming, address fields, and timestamp tracking.
"""

import aiosqlite
from datetime import datetime
from typing import Dict, Any


async def migrate_dvr_schema(db_path: str = "camera_data.db") -> Dict[str, Any]:
    """Migrate DVR table to include new columns for enhanced management."""
    try:
        async with aiosqlite.connect(db_path) as db:
            # Check current DVR table structure
            cursor = await db.execute("PRAGMA table_info(dvrs)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            migrations_applied = []
            
            # Add custom_name column if it doesn't exist
            if 'custom_name' not in column_names:
                await db.execute("ALTER TABLE dvrs ADD COLUMN custom_name TEXT")
                migrations_applied.append("Added custom_name column")
            
            # Add address column if it doesn't exist
            if 'address' not in column_names:
                await db.execute("ALTER TABLE dvrs ADD COLUMN address TEXT")
                migrations_applied.append("Added address column")
            
            # Add created_at column if it doesn't exist
            if 'created_at' not in column_names:
                await db.execute("ALTER TABLE dvrs ADD COLUMN created_at TEXT")
                migrations_applied.append("Added created_at column")
            
            # Add updated_at column if it doesn't exist
            if 'updated_at' not in column_names:
                await db.execute("ALTER TABLE dvrs ADD COLUMN updated_at TEXT")
                migrations_applied.append("Added updated_at column")
            
            # Update existing DVRs with default values for new columns
            if migrations_applied:
                now = datetime.now().isoformat()
                
                # Set custom_name to existing name for backward compatibility
                await db.execute("""
                    UPDATE dvrs SET custom_name = name 
                    WHERE custom_name IS NULL OR custom_name = ''
                """)
                
                # Set timestamps for existing records
                await db.execute("""
                    UPDATE dvrs SET created_at = ?, updated_at = ? 
                    WHERE created_at IS NULL OR updated_at IS NULL
                """, (now, now))
                
                migrations_applied.append("Updated existing DVR records with default values")
            
            await db.commit()
            
            return {
                'success': True,
                'message': f"DVR schema migration completed successfully",
                'migrations_applied': migrations_applied
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f"Error migrating DVR schema: {str(e)}",
            'migrations_applied': []
        }


async def migrate_camera_dvr_fields(db_path: str = "camera_data.db") -> Dict[str, Any]:
    """Migrate camera table to include custom_name and address fields."""
    try:
        async with aiosqlite.connect(db_path) as db:
            # Check current camera table structure
            cursor = await db.execute("PRAGMA table_info(cameras)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            migrations_applied = []
            
            # Add custom_name column to cameras if it doesn't exist
            if 'custom_name' not in column_names:
                await db.execute("ALTER TABLE cameras ADD COLUMN custom_name TEXT")
                migrations_applied.append("Added custom_name column to cameras")
            
            # Add address column to cameras if it doesn't exist
            if 'address' not in column_names:
                await db.execute("ALTER TABLE cameras ADD COLUMN address TEXT")
                migrations_applied.append("Added address column to cameras")
            
            await db.commit()
            
            return {
                'success': True,
                'message': f"Camera schema migration completed successfully",
                'migrations_applied': migrations_applied
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f"Error migrating camera schema: {str(e)}",
            'migrations_applied': []
        }


async def run_all_dvr_migrations(db_path: str = "camera_data.db") -> Dict[str, Any]:
    """Run all DVR-related database migrations."""
    try:
        results = []
        
        # Migrate DVR schema
        dvr_result = await migrate_dvr_schema(db_path)
        results.append(dvr_result)
        
        # Migrate camera schema for DVR-related fields
        camera_result = await migrate_camera_dvr_fields(db_path)
        results.append(camera_result)
        
        # Collect all migrations applied
        all_migrations = []
        success = True
        
        for result in results:
            if not result['success']:
                success = False
            all_migrations.extend(result['migrations_applied'])
        
        return {
            'success': success,
            'message': f"All DVR migrations completed. Applied {len(all_migrations)} migrations.",
            'migrations_applied': all_migrations,
            'detailed_results': results
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error running DVR migrations: {str(e)}",
            'migrations_applied': []
        }


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("Running DVR database migrations...")
        result = await run_all_dvr_migrations()
        
        if result['success']:
            print("✅ Migrations completed successfully!")
            for migration in result['migrations_applied']:
                print(f"  - {migration}")
        else:
            print("❌ Migration failed:")
            print(f"  {result['message']}")
    
    asyncio.run(main())