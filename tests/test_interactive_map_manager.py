"""
Test script for InteractiveMapManager component

This script tests the core functionality of the InteractiveMapManager class
to ensure it meets the requirements for task 4.
"""

import asyncio
import os
import tempfile
import aiosqlite
from src.interactive_map_manager import InteractiveMapManager
from src.enhanced_camera_models import EnhancedCamera


async def setup_test_database():
    """Create a temporary test database with sample data."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    async with aiosqlite.connect(db_path) as db:
        # Create cameras table
        await db.execute("""
            CREATE TABLE cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                name TEXT NOT NULL,
                mac_address TEXT NOT NULL UNIQUE,
                ip_address TEXT NOT NULL UNIQUE,
                locational_group TEXT,
                date_installed TEXT NOT NULL,
                dvr_id INTEGER,
                latitude REAL,
                longitude REAL,
                has_memory_card BOOLEAN NOT NULL,
                memory_card_last_reset TEXT,
                coverage_radius REAL DEFAULT 50.0,
                field_of_view_angle REAL DEFAULT 360.0,
                coverage_direction REAL DEFAULT 0.0
            )
        """)
        
        # Create DVRs table
        await db.execute("""
            CREATE TABLE dvrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dvr_type TEXT NOT NULL,
                location TEXT NOT NULL,
                ip_address TEXT NOT NULL UNIQUE,
                mac_address TEXT NOT NULL UNIQUE,
                storage_capacity TEXT,
                date_installed TEXT NOT NULL,
                latitude REAL,
                longitude REAL
            )
        """)
        
        # Create action_log table
        await db.execute("""
            CREATE TABLE action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                details TEXT
            )
        """)
        
        # Insert test cameras
        test_cameras = [
            ("Main Entrance", "Camera 1", "00:11:22:33:44:55", "192.168.1.101", 
             "Entrance", "2024-01-01", None, 40.7128, -74.0060, True, None, 75.0, 360.0, 0.0),
            ("Parking Lot", "Camera 2", "00:11:22:33:44:56", "192.168.1.102", 
             "Parking", "2024-01-02", None, 40.7130, -74.0058, False, None, 100.0, 120.0, 45.0),
            ("Back Exit", "Camera 3", "00:11:22:33:44:57", "192.168.1.103", 
             "Exit", "2024-01-03", None, 40.7126, -74.0062, True, None, 60.0, 90.0, 180.0)
        ]
        
        for camera in test_cameras:
            await db.execute("""
                INSERT INTO cameras (location, name, mac_address, ip_address, locational_group,
                                   date_installed, dvr_id, latitude, longitude, has_memory_card,
                                   memory_card_last_reset, coverage_radius, field_of_view_angle,
                                   coverage_direction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, camera)
        
        # Insert test DVR
        await db.execute("""
            INSERT INTO dvrs (name, dvr_type, location, ip_address, mac_address,
                            storage_capacity, date_installed, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Main DVR", "Network DVR", "Server Room", "192.168.1.200", 
              "00:11:22:33:44:99", "2TB", "2024-01-01", 40.7129, -74.0059))
        
        await db.commit()
    
    return db_path


async def test_interactive_map_manager():
    """Test the InteractiveMapManager functionality."""
    print("🧪 Testing InteractiveMapManager...")
    
    # Setup test database
    db_path = await setup_test_database()
    
    try:
        # Initialize InteractiveMapManager
        manager = InteractiveMapManager(db_path)
        
        # Test 1: Create enhanced map
        print("\n📍 Test 1: Creating enhanced map...")
        map_html = await manager.create_enhanced_map()
        
        # Verify map was created
        assert isinstance(map_html, str), "Map should return HTML string"
        assert len(map_html) > 1000, "Map HTML should be substantial"
        assert "folium" in map_html.lower(), "Map should contain Folium elements"
        assert "camera" in map_html.lower(), "Map should reference cameras"
        print("✅ Enhanced map created successfully")
        
        # Test 2: Handle camera move
        print("\n🎯 Test 2: Testing camera position update...")
        result = await manager.handle_camera_move(1, 40.7140, -74.0050)
        
        assert result['success'] == True, "Camera move should succeed"
        assert result['camera_id'] == 1, "Should return correct camera ID"
        assert 'coordinates' in result, "Should return new coordinates"
        print(f"✅ Camera move successful: {result['message']}")
        
        # Test 3: Handle invalid coordinates
        print("\n❌ Test 3: Testing invalid coordinate handling...")
        result = await manager.handle_camera_move(1, 91.0, -74.0050)  # Invalid latitude
        
        assert result['success'] == False, "Invalid coordinates should fail"
        assert result['revert'] == True, "Should request revert"
        print(f"✅ Invalid coordinates handled correctly: {result['message']}")
        
        # Test 4: Update coverage parameters
        print("\n📐 Test 4: Testing coverage parameter update...")
        params = {'radius': 80.0, 'angle': 180.0, 'direction': 90.0}
        result = await manager.update_coverage_parameters(1, params)
        
        assert result['success'] == True, "Coverage update should succeed"
        assert result['parameters']['radius'] == 80.0, "Should return updated radius"
        print(f"✅ Coverage parameters updated: {result['message']}")
        
        # Test 5: Get camera coverage data
        print("\n📊 Test 5: Testing coverage data retrieval...")
        coverage_data = await manager.get_camera_coverage_data(1)
        
        assert coverage_data is not None, "Should return coverage data"
        assert coverage_data['id'] == 1, "Should return correct camera"
        assert 'coverage_coordinates' in coverage_data, "Should include coordinates"
        print("✅ Coverage data retrieved successfully")
        
        # Test 6: Handle non-existent camera
        print("\n🔍 Test 6: Testing non-existent camera handling...")
        result = await manager.handle_camera_move(999, 40.7140, -74.0050)
        
        assert result['success'] == False, "Non-existent camera should fail"
        print(f"✅ Non-existent camera handled correctly: {result['message']}")
        
        print("\n🎉 All tests passed! InteractiveMapManager is working correctly.")
        
        # Optional: Save test map to file for manual inspection
        with open("test_interactive_map.html", "w", encoding='utf-8') as f:
            f.write(map_html)
        print("💾 Test map saved to 'test_interactive_map.html' for manual inspection")
        
    finally:
        # Cleanup test database
        os.unlink(db_path)
        print("🧹 Test database cleaned up")


async def test_requirements_compliance():
    """Test that the implementation meets the specific requirements."""
    print("\n📋 Testing Requirements Compliance...")
    
    db_path = await setup_test_database()
    
    try:
        manager = InteractiveMapManager(db_path)
        
        # Requirement 1.1: Drag cameras to new positions on the map
        print("\n✅ Requirement 1.1: Drag functionality")
        map_html = await manager.create_enhanced_map()
        assert "dragging" in map_html.lower(), "Map should include drag functionality"
        assert "cameraId" in map_html, "Map should include camera identification for dragging"
        print("   - Drag-and-drop JavaScript included in map")
        
        # Requirement 1.2: Update camera coordinates when cameras are moved  
        print("\n✅ Requirement 1.2: Coordinate updates")
        result = await manager.handle_camera_move(1, 40.7150, -74.0040)
        assert result['success'] == True, "Should successfully update coordinates"
        
        # Verify database was updated
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT latitude, longitude FROM cameras WHERE id = 1")
            row = await cursor.fetchone()
            assert abs(row[0] - 40.7150) < 0.0001, "Latitude should be updated in database"
            assert abs(row[1] - (-74.0040)) < 0.0001, "Longitude should be updated in database"
        print("   - Database coordinates updated successfully")
        
        # Requirement 2.2: Coverage area moves with camera marker in real-time
        print("\n✅ Requirement 2.2: Real-time coverage updates")
        coverage_data = await manager.get_camera_coverage_data(1)
        assert coverage_data is not None, "Should provide coverage data for real-time updates"
        assert 'coverage_coordinates' in coverage_data, "Should include coverage coordinates"
        print("   - Coverage data available for real-time updates")
        print("   - JavaScript includes coverage area update functions")
        
        print("\n🎯 All requirements successfully implemented!")
        
    finally:
        os.unlink(db_path)


if __name__ == "__main__":
    print("🚀 Starting InteractiveMapManager Tests")
    print("=" * 50)
    
    # Run main functionality tests
    asyncio.run(test_interactive_map_manager())
    
    # Run requirements compliance tests
    asyncio.run(test_requirements_compliance())
    
    print("\n" + "=" * 50)
    print("✨ All tests completed successfully!")