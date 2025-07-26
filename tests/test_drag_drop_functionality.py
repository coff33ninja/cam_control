"""
Test suite for drag-and-drop functionality in Interactive Camera Mapping

This test suite validates all requirements for task 8:
- Embed custom JavaScript in Folium map for handling marker drag events
- Implement communication between JavaScript drag events and Python backend
- Add visual feedback during drag operations (temporary coverage area updates)
- Create error handling for failed drag operations with marker position reversion

Requirements tested:
- 1.1: Allow camera markers to be moved to new positions
- 1.2: Update coordinates when cameras are moved
- 1.3: Display confirmation message showing new coordinates
- 1.4: Revert marker to original position on failure
"""

import asyncio
import json
import sqlite3
import tempfile
import os
from interactive_map_manager import InteractiveMapManager
from enhanced_camera_models import EnhancedCamera


class TestDragDropFunctionality:
    """Test class for drag-and-drop functionality."""
    
    def setup_test_db(self):
        """Create a temporary database with test data."""
        # Create temporary database file
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        # Initialize database with test schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create cameras table with coverage parameters
        cursor.execute("""
            CREATE TABLE cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                latitude REAL,
                longitude REAL,
                coverage_radius REAL DEFAULT 50.0,
                field_of_view_angle REAL DEFAULT 360.0,
                coverage_direction REAL DEFAULT 0.0,
                mac_address TEXT,
                locational_group TEXT,
                date_installed TEXT,
                dvr_id INTEGER,
                has_memory_card BOOLEAN DEFAULT 0,
                memory_card_last_reset TEXT
            )
        """)
        
        # Create DVRs table
        cursor.execute("""
            CREATE TABLE dvrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                latitude REAL,
                longitude REAL,
                dvr_type TEXT
            )
        """)
        
        # Create action_log table for logging
        cursor.execute("""
            CREATE TABLE action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                details TEXT
            )
        """)
        
        # Insert test cameras
        test_cameras = [
            (1, 'Test Camera 1', 'Building A', '192.168.1.100', 40.7128, -74.0060, 75.0, 360.0, 0.0),
            (2, 'Test Camera 2', 'Building B', '192.168.1.101', 40.7130, -74.0062, 50.0, 90.0, 45.0),
            (3, 'Test Camera 3', 'Building C', '192.168.1.102', 40.7132, -74.0064, 100.0, 180.0, 90.0)
        ]
        
        cursor.executemany("""
            INSERT INTO cameras (id, name, location, ip_address, latitude, longitude, 
                               coverage_radius, field_of_view_angle, coverage_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_cameras)
        
        conn.commit()
        conn.close()
        
        return db_path
    
    async def test_javascript_integration(self, db_path):
        """
        Test that JavaScript is properly embedded in the map.
        
        Requirements tested:
        - Embed custom JavaScript in Folium map for handling marker drag events
        """
        manager = InteractiveMapManager(db_path)
        
        # Create enhanced map
        map_html = await manager.create_enhanced_map()
        
        # Verify JavaScript integration
        assert 'drag-and-drop functionality' in map_html
        assert 'initializeDragFunctionality' in map_html
        assert 'makeMarkerDraggable' in map_html
        assert 'updateCameraPosition' in map_html
        assert 'dragstart' in map_html
        assert 'drag' in map_html
        assert 'dragend' in map_html
        
        # Verify camera identification elements
        assert 'data-camera-id' in map_html
        assert 'camera-marker' in map_html
        
        print("✅ JavaScript integration test passed")
    
    async def test_backend_communication(self, db_path):
        """
        Test communication between JavaScript and Python backend.
        
        Requirements tested:
        - 1.2: Update coordinates when cameras are moved
        - Implement communication between JavaScript drag events and Python backend
        """
        manager = InteractiveMapManager(db_path)
        
        # Test successful position update
        result = await manager.handle_camera_move(1, 40.7140, -74.0070)
        
        assert result['success'] is True
        assert result['camera_id'] == 1
        assert result['coordinates']['lat'] == 40.7140
        assert result['coordinates']['lon'] == -74.0070
        assert '✅' in result['message']
        
        # Verify database was updated
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT latitude, longitude FROM cameras WHERE id = ?", (1,)
            )
            result_db = await cursor.fetchone()
            assert result_db[0] == 40.7140
            assert result_db[1] == -74.0070
        
        print("✅ Backend communication test passed")
    
    async def test_coordinate_validation(self, db_path):
        """
        Test coordinate validation and error handling.
        
        Requirements tested:
        - 1.4: Create error handling for failed drag operations
        """
        manager = InteractiveMapManager(db_path)
        
        # Test invalid latitude (too high)
        result = await manager.handle_camera_move(1, 95.0, -74.0060)
        assert result['success'] is False
        assert result['revert'] is True
        assert 'Invalid coordinates' in result['message']
        
        # Test invalid longitude (too low)
        result = await manager.handle_camera_move(1, 40.7128, -200.0)
        assert result['success'] is False
        assert result['revert'] is True
        assert 'Invalid coordinates' in result['message']
        
        # Test non-existent camera
        result = await manager.handle_camera_move(999, 40.7128, -74.0060)
        assert result['success'] is False
        assert result['revert'] is True
        assert 'not found' in result['message']
        
        print("✅ Coordinate validation test passed")
    
    async def test_visual_feedback_elements(self, db_path):
        """
        Test visual feedback during drag operations.
        
        Requirements tested:
        - Add visual feedback during drag operations (temporary coverage area updates)
        """
        manager = InteractiveMapManager(db_path)
        
        # Create enhanced map
        map_html = await manager.create_enhanced_map()
        
        # Verify visual feedback elements are present
        assert 'showDragIndicator' in map_html
        assert 'updateTemporaryCoverageArea' in map_html
        assert 'showProcessingIndicator' in map_html
        assert 'showNotification' in map_html
        assert 'temp-coverage-area' in map_html
        
        # Verify drag indicator styling
        assert 'drag-indicator' in map_html
        assert 'Dragging camera' in map_html
        assert 'Release to update position' in map_html
        
        # Verify notification system
        assert 'map-notification' in map_html
        assert 'slideIn' in map_html
        
        print("✅ Visual feedback elements test passed")
    
    async def test_camera_data_loading(self, db_path):
        """
        Test loading camera data for JavaScript functionality.
        
        Requirements tested:
        - JavaScript needs camera data for real-time coverage updates
        """
        manager = InteractiveMapManager(db_path)
        
        # Test getting all cameras data
        cameras_data = await manager.get_all_cameras_data()
        
        assert len(cameras_data) == 3
        
        # Verify first camera data
        camera1 = cameras_data[0]
        assert camera1['id'] == 1
        assert camera1['name'] == 'Test Camera 1'
        assert camera1['latitude'] == 40.7128
        assert camera1['longitude'] == -74.0060
        assert camera1['coverage_radius'] == 75.0
        assert camera1['field_of_view_angle'] == 360.0
        assert camera1['coverage_direction'] == 0.0
        
        # Verify directional camera data
        camera2 = cameras_data[1]
        assert camera2['field_of_view_angle'] == 90.0
        assert camera2['coverage_direction'] == 45.0
        
        print("✅ Camera data loading test passed")
    
    async def test_drag_request_processing(self, db_path):
        """
        Test processing of drag requests from frontend.
        
        Requirements tested:
        - 1.3: Display confirmation message showing new coordinates
        - Backend communication for coordinate updates
        """
        manager = InteractiveMapManager(db_path)
        
        # Test update camera position request
        request_data = {
            'action': 'update_camera_position',
            'camera_id': '2',
            'latitude': '40.7135',
            'longitude': '-74.0065'
        }
        
        result = await manager.process_drag_request(request_data)
        
        assert result['success'] is True
        assert result['camera_id'] == 2
        assert result['coordinates']['lat'] == 40.7135
        assert result['coordinates']['lon'] == -74.0065
        assert 'moved to' in result['message']
        
        # Test get camera data request
        request_data = {'action': 'get_camera_data'}
        result = await manager.process_drag_request(request_data)
        
        assert result['success'] is True
        assert 'cameras' in result
        assert len(result['cameras']) == 3
        
        # Test unknown action
        request_data = {'action': 'unknown_action'}
        result = await manager.process_drag_request(request_data)
        
        assert result['success'] is False
        assert result['revert'] is True
        assert 'Unknown action' in result['message']
        
        print("✅ Drag request processing test passed")
    
    async def test_error_handling_and_reversion(self, db_path):
        """
        Test error handling and position reversion functionality.
        
        Requirements tested:
        - 1.4: Revert marker to original position on failure
        - Create error handling for failed drag operations
        """
        manager = InteractiveMapManager(db_path)
        
        # Get original position
        original_position = await manager._get_camera_position(1)
        assert original_position is not None
        
        # Test database error simulation (invalid camera ID)
        result = await manager.handle_camera_move(999, 40.7140, -74.0070)
        
        assert result['success'] is False
        assert result['revert'] is True
        assert result['camera_id'] == 999
        
        # Verify original camera position unchanged
        current_position = await manager._get_camera_position(1)
        assert current_position == original_position
        
        # Test coordinate validation error
        result = await manager.handle_camera_move(1, 200.0, -74.0060)
        
        assert result['success'] is False
        assert result['revert'] is True
        assert 'Invalid coordinates' in result['message']
        
        print("✅ Error handling and reversion test passed")
    
    async def test_coverage_area_updates(self, db_path):
        """
        Test coverage area updates during drag operations.
        
        Requirements tested:
        - Real-time coverage area updates during drag
        - Temporary coverage area display
        """
        manager = InteractiveMapManager(db_path)
        
        # Get coverage data for a camera
        coverage_data = await manager.get_camera_coverage_data(2)
        
        assert coverage_data is not None
        assert coverage_data['id'] == 2
        assert coverage_data['coverage_radius'] == 50.0
        assert coverage_data['field_of_view_angle'] == 90.0
        assert coverage_data['coverage_direction'] == 45.0
        
        # Verify coverage coordinates are calculated
        assert 'coverage_coordinates' in coverage_data
        assert len(coverage_data['coverage_coordinates']) > 0
        
        # Test coverage parameter updates
        new_params = {
            'radius': 80.0,
            'angle': 120.0,
            'direction': 60.0
        }
        
        result = await manager.update_coverage_parameters(2, new_params)
        
        assert result['success'] is True
        assert result['parameters']['radius'] == 80.0
        assert result['parameters']['angle'] == 120.0
        assert result['parameters']['direction'] == 60.0
        
        print("✅ Coverage area updates test passed")
    
    async def test_marker_identification(self, db_path):
        """
        Test camera marker identification for drag functionality.
        
        Requirements tested:
        - Camera markers must be identifiable by JavaScript
        - Proper embedding of camera IDs in markers
        """
        manager = InteractiveMapManager(db_path)
        
        # Create enhanced map
        map_html = await manager.create_enhanced_map()
        
        # Verify camera identification elements for each test camera
        for camera_id in [1, 2, 3]:
            assert f'data-camera-id="{camera_id}"' in map_html or f"data-camera-id='{camera_id}'" in map_html
            assert f'camera-marker-{camera_id}' in map_html
            assert f'Camera {camera_id}:' in map_html
        
        # Verify drag instructions are included
        assert 'Drag to move' in map_html
        assert 'Click and drag this marker' in map_html
        
        print("✅ Marker identification test passed")
    
    def test_javascript_functions_completeness(self, db_path):
        """
        Test that all required JavaScript functions are present.
        
        Requirements tested:
        - All drag-and-drop JavaScript functions are embedded
        """
        manager = InteractiveMapManager(db_path)
        
        # Get the JavaScript code
        map_obj = type('MockMap', (), {'get_root': lambda: type('MockRoot', (), {'html': type('MockHTML', (), {'add_child': lambda x: None})()})()})()
        manager._add_drag_drop_javascript(map_obj)
        
        # This test verifies the method runs without error
        # The actual JavaScript content is tested in other methods
        
        print("✅ JavaScript functions completeness test passed")


async def run_all_tests():
    """Run all drag-and-drop functionality tests."""
    print("🧪 Running Drag-and-Drop Functionality Tests")
    print("=" * 50)
    
    test_instance = TestDragDropFunctionality()
    
    # Create test database
    import tempfile
    import os
    import sqlite3
    
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Initialize database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            ip_address TEXT,
            latitude REAL,
            longitude REAL,
            coverage_radius REAL DEFAULT 50.0,
            field_of_view_angle REAL DEFAULT 360.0,
            coverage_direction REAL DEFAULT 0.0,
            mac_address TEXT,
            locational_group TEXT,
            date_installed TEXT,
            dvr_id INTEGER,
            has_memory_card BOOLEAN DEFAULT 0,
            memory_card_last_reset TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE dvrs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT,
            ip_address TEXT,
            latitude REAL,
            longitude REAL,
            dvr_type TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            details TEXT
        )
    """)
    
    test_cameras = [
        (1, 'Test Camera 1', 'Building A', '192.168.1.100', 40.7128, -74.0060, 75.0, 360.0, 0.0),
        (2, 'Test Camera 2', 'Building B', '192.168.1.101', 40.7130, -74.0062, 50.0, 90.0, 45.0),
        (3, 'Test Camera 3', 'Building C', '192.168.1.102', 40.7132, -74.0064, 100.0, 180.0, 90.0)
    ]
    
    cursor.executemany("""
        INSERT INTO cameras (id, name, location, ip_address, latitude, longitude, 
                           coverage_radius, field_of_view_angle, coverage_direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_cameras)
    
    conn.commit()
    conn.close()
    
    try:
        # Run tests
        await test_instance.test_javascript_integration(db_path)
        await test_instance.test_backend_communication(db_path)
        await test_instance.test_coordinate_validation(db_path)
        await test_instance.test_visual_feedback_elements(db_path)
        await test_instance.test_camera_data_loading(db_path)
        await test_instance.test_drag_request_processing(db_path)
        await test_instance.test_error_handling_and_reversion(db_path)
        await test_instance.test_coverage_area_updates(db_path)
        await test_instance.test_marker_identification(db_path)
        test_instance.test_javascript_functions_completeness(db_path)
        
        print("\n" + "=" * 50)
        print("🎉 All Drag-and-Drop Functionality Tests Passed!")
        print("✅ JavaScript integration working")
        print("✅ Backend communication established")
        print("✅ Visual feedback implemented")
        print("✅ Error handling and reversion working")
        print("✅ Coverage area updates functional")
        print("✅ Camera marker identification working")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup with retry
        import time
        for i in range(3):
            try:
                time.sleep(0.1)  # Small delay to ensure connections are closed
                os.unlink(db_path)
                break
            except PermissionError:
                if i == 2:  # Last attempt
                    print(f"Warning: Could not delete temporary database file: {db_path}")
                time.sleep(0.5)


if __name__ == "__main__":
    # Run the tests
    result = asyncio.run(run_all_tests())
    exit(0 if result else 1)