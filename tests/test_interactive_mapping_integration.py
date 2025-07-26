"""
Comprehensive Integration Tests for Interactive Camera Mapping

This test suite validates the complete interactive mapping workflow including:
- End-to-end drag-and-drop functionality
- Configuration save/load operations
- Coverage area calculations and visualization
- Performance with large numbers of cameras
- Error handling and recovery scenarios

Requirements tested:
- 1.1: Drag cameras to new positions on the map
- 2.1: Show visual coverage area around camera marker
- 3.1: Edit camera coverage parameters through interface
- 4.1: Test connectivity to all cameras and display their status
- 5.1: Provide option to save current configuration when user makes changes
"""

import asyncio
import json
import sqlite3
import tempfile
import os
import time
import unittest
from unittest.mock import Mock, patch, AsyncMock
import sys
import pytest

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from interactive_map_manager import InteractiveMapManager
from enhanced_camera_models import EnhancedCamera, MapConfiguration
from coverage_calculator import CoverageCalculator
from connectivity_monitor import ConnectivityMonitor
from map_configuration_manager import MapConfigurationManager
from error_handling import DatabaseTransactionManager, CoordinateValidator


class TestInteractiveMappingIntegration:
    """Integration tests for the complete interactive mapping system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        # Initialize database with test schema
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create cameras table
        cursor.execute("""
            CREATE TABLE cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                mac_address TEXT,
                latitude REAL,
                longitude REAL,
                coverage_radius REAL DEFAULT 50.0,
                field_of_view_angle REAL DEFAULT 360.0,
                coverage_direction REAL DEFAULT 0.0,
                has_memory_card BOOLEAN DEFAULT 0,
                memory_card_last_reset TEXT,
                dvr_id INTEGER,
                locational_group TEXT,
                date_installed TEXT
            )
        """)
        
        # Create DVRs table
        cursor.execute("""
            CREATE TABLE dvrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dvr_type TEXT,
                location TEXT,
                ip_address TEXT,
                mac_address TEXT,
                latitude REAL,
                longitude REAL,
                storage_capacity TEXT,
                date_installed TEXT
            )
        """)
        
        # Create map_configurations table
        cursor.execute("""
            CREATE TABLE map_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                configuration_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create action_log table
        cursor.execute("""
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
            (1, 'CAM-001', 'Main Entrance', '192.168.1.101', '00:1A:2B:3C:4D:01', 40.7128, -74.0060, 50.0, 360.0, 0.0),
            (2, 'CAM-002', 'Parking Lot', '192.168.1.102', '00:1A:2B:3C:4D:02', 40.7130, -74.0062, 75.0, 120.0, 45.0),
            (3, 'CAM-003', 'Side Door', '192.168.1.103', '00:1A:2B:3C:4D:03', 40.7126, -74.0058, 30.0, 90.0, 180.0),
        ]
        
        cursor.executemany("""
            INSERT INTO cameras (id, name, location, ip_address, mac_address, latitude, longitude, 
                               coverage_radius, field_of_view_angle, coverage_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_cameras)
        
        # Insert test DVR
        cursor.execute("""
            INSERT INTO dvrs (id, name, dvr_type, location, ip_address, mac_address, latitude, longitude)
            VALUES (1, 'DVR-001', '16-Channel', 'Server Room', '192.168.1.200', '00:1A:2B:3C:4D:10', 40.7129, -74.0061)
        """)
        
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_end_to_end_drag_drop_workflow(self, temp_db):
        """Test complete drag-and-drop workflow from start to finish."""
        # Initialize map manager
        map_manager = InteractiveMapManager(temp_db)
        
        # Test initial map creation
        map_html = await map_manager.create_enhanced_map()
        assert isinstance(map_html, str)
        assert len(map_html) > 0
        assert 'CAM-001' in map_html
        assert 'drag' in map_html.lower()
        
        # Test camera move operation
        original_camera_data = await map_manager.get_camera_coverage_data(1)
        assert original_camera_data is not None
        original_lat = original_camera_data['latitude']
        original_lon = original_camera_data['longitude']
        
        # Simulate drag operation
        new_lat = original_lat + 0.001
        new_lon = original_lon + 0.001
        
        move_result = await map_manager.handle_camera_move(1, new_lat, new_lon)
        
        # Verify successful move
        assert move_result['success'] is True
        assert 'coordinates updated' in move_result['message'].lower()
        assert move_result['coordinates']['lat'] == new_lat
        assert move_result['coordinates']['lon'] == new_lon
        
        # Verify database was updated
        updated_camera_data = await map_manager.get_camera_coverage_data(1)
        assert updated_camera_data['latitude'] == new_lat
        assert updated_camera_data['longitude'] == new_lon
        
        # Test error handling with invalid coordinates
        invalid_move_result = await map_manager.handle_camera_move(1, 91.0, 0.0)  # Invalid latitude
        assert invalid_move_result['success'] is False
        assert invalid_move_result['revert'] is True
    
    @pytest.mark.asyncio
    async def test_coverage_area_calculations_and_visualization(self, temp_db):
        """Test coverage area calculations for different camera types."""
        map_manager = InteractiveMapManager(temp_db)
        
        # Test circular coverage (360° field of view)
        circular_camera_data = await map_manager.get_camera_coverage_data(1)
        assert circular_camera_data is not None
        assert circular_camera_data['field_of_view_angle'] == 360.0
        
        circular_coords = circular_camera_data.get('coverage_coordinates')
        assert circular_coords is not None
        assert len(circular_coords) > 10  # Should have multiple points for circle
        
        # Test directional coverage (limited field of view)
        directional_camera_data = await map_manager.get_camera_coverage_data(2)
        assert directional_camera_data is not None
        assert directional_camera_data['field_of_view_angle'] == 120.0
        
        directional_coords = directional_camera_data.get('coverage_coordinates')
        assert directional_coords is not None
        assert len(directional_coords) > 3  # Should have points for sector
        
        # Test coverage parameter updates
        new_params = {
            'radius': 100.0,
            'angle': 180.0,
            'direction': 90.0
        }
        
        update_result = await map_manager.update_coverage_parameters(2, new_params)
        assert update_result['success'] is True
        
        # Verify parameters were updated
        updated_data = await map_manager.get_camera_coverage_data(2)
        assert updated_data['coverage_radius'] == 100.0
        assert updated_data['field_of_view_angle'] == 180.0
        assert updated_data['coverage_direction'] == 90.0
    
    @pytest.mark.asyncio
    async def test_configuration_save_load_workflow(self, temp_db):
        """Test complete configuration management workflow."""
        config_manager = MapConfigurationManager(temp_db)
        
        # Test saving current configuration
        save_result = await config_manager.save_configuration(
            "Test Configuration",
            "Test configuration for integration testing"
        )
        assert save_result.success is True
        config_id = save_result.configuration_id
        
        # Test listing configurations
        configs = await config_manager.list_configurations()
        assert len(configs) == 1
        assert configs[0].name == "Test Configuration"
        assert configs[0].camera_count == 3  # Should have 3 test cameras
        
        # Modify camera positions
        map_manager = InteractiveMapManager(temp_db)
        move_result = await map_manager.handle_camera_move(1, 40.7140, -74.0070)
        assert move_result['success'] is True
        
        # Test loading configuration (should restore original positions)
        load_result = await config_manager.load_configuration(config_id)
        assert load_result.success is True
        
        # Verify positions were restored
        restored_camera = await map_manager.get_camera_coverage_data(1)
        assert abs(restored_camera['latitude'] - 40.7128) < 0.0001
        assert abs(restored_camera['longitude'] - (-74.0060)) < 0.0001
    
    @pytest.mark.asyncio
    async def test_connectivity_monitoring_integration(self, temp_db):
        """Test connectivity monitoring integration with map display."""
        connectivity_monitor = ConnectivityMonitor(temp_db, cache_timeout=1)
        
        # Mock ping function to simulate different connectivity states
        with patch('src.connectivity_monitor.ping') as mock_ping:
            # Simulate mixed connectivity results
            mock_ping.side_effect = [0.05, None, 0.12]  # online, offline, online
            
            # Test batch connectivity testing
            devices = [
                {'id': 1, 'ip_address': '192.168.1.101', 'name': 'CAM-001', 'type': 'camera'},
                {'id': 2, 'ip_address': '192.168.1.102', 'name': 'CAM-002', 'type': 'camera'},
                {'id': 3, 'ip_address': '192.168.1.103', 'name': 'CAM-003', 'type': 'camera'},
            ]
            
            results = await connectivity_monitor.batch_connectivity_test(devices)
            
            # Verify results
            assert len(results) == 3
            assert results[1].is_online is True
            assert results[2].is_online is False
            assert results[3].is_online is True
            
            # Test status color coding
            assert connectivity_monitor.get_status_color(True) == 'green'
            assert connectivity_monitor.get_status_color(False) == 'red'
            assert connectivity_monitor.get_status_color(False, has_error=True) == 'orange'
            
            # Test coverage opacity based on connectivity
            assert connectivity_monitor.get_coverage_opacity(True) == 0.4
            assert connectivity_monitor.get_coverage_opacity(False) == 0.15
    
    @pytest.mark.asyncio
    async def test_performance_with_large_camera_count(self, temp_db):
        """Test system performance with a large number of cameras."""
        # Add many cameras to test performance
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Generate 100 test cameras
        large_camera_set = []
        for i in range(4, 104):  # IDs 4-103 (we already have 1-3)
            lat = 40.7128 + (i * 0.001)  # Spread cameras across area
            lon = -74.0060 + (i * 0.001)
            large_camera_set.append((
                i, f'CAM-{i:03d}', f'Location {i}', f'192.168.1.{100 + i}',
                f'00:1A:2B:3C:4D:{i:02X}', lat, lon, 50.0, 360.0, 0.0
            ))
        
        cursor.executemany("""
            INSERT INTO cameras (id, name, location, ip_address, mac_address, latitude, longitude,
                               coverage_radius, field_of_view_angle, coverage_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, large_camera_set)
        conn.commit()
        conn.close()
        
        # Test map generation performance
        map_manager = InteractiveMapManager(temp_db)
        
        start_time = time.time()
        map_html = await map_manager.create_enhanced_map()
        generation_time = time.time() - start_time
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert generation_time < 10.0  # 10 seconds max
        assert isinstance(map_html, str)
        assert len(map_html) > 0
        
        # Test batch operations performance
        connectivity_monitor = ConnectivityMonitor(temp_db, cache_timeout=1)
        
        # Create device list for all cameras
        devices = []
        for i in range(1, 104):
            devices.append({
                'id': i,
                'ip_address': f'192.168.1.{100 + i}',
                'name': f'CAM-{i:03d}',
                'type': 'camera'
            })
        
        # Mock ping to avoid actual network calls
        with patch('src.connectivity_monitor.ping', return_value=0.05):
            start_time = time.time()
            results = await connectivity_monitor.batch_connectivity_test(devices)
            batch_test_time = time.time() - start_time
            
            # Should complete batch testing within reasonable time
            assert batch_test_time < 30.0  # 30 seconds max for 103 cameras
            assert len(results) == 103
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, temp_db):
        """Test comprehensive error handling and recovery scenarios."""
        map_manager = InteractiveMapManager(temp_db)
        
        # Test invalid camera ID
        invalid_move_result = await map_manager.handle_camera_move(999, 40.7128, -74.0060)
        assert invalid_move_result['success'] is False
        assert 'not found' in invalid_move_result['message'].lower()
        
        # Test invalid coordinates
        invalid_coord_result = await map_manager.handle_camera_move(1, 91.0, 0.0)
        assert invalid_coord_result['success'] is False
        assert invalid_coord_result['revert'] is True
        
        # Test database transaction rollback
        transaction_manager = DatabaseTransactionManager(temp_db)
        
        # Test successful coordinate update
        success_result = await transaction_manager.update_camera_coordinates_atomic(1, 40.7130, -74.0062)
        assert success_result.success is True
        
        # Test failed coordinate update (invalid coordinates)
        fail_result = await transaction_manager.update_camera_coordinates_atomic(1, 91.0, 0.0)
        assert fail_result.success is False
        assert fail_result.error_category.value == 'validation'
        
        # Verify original coordinates were not changed
        camera_data = await map_manager.get_camera_coverage_data(1)
        assert abs(camera_data['latitude'] - 40.7130) < 0.0001  # Should still be the successful update
        
        # Test configuration error handling
        config_manager = MapConfigurationManager(temp_db)
        
        # Test saving configuration with empty name
        empty_name_result = await config_manager.save_configuration("")
        assert empty_name_result.success is False
        assert 'empty' in empty_name_result.message.lower()
        
        # Test loading non-existent configuration
        missing_config_result = await config_manager.load_configuration(999)
        assert missing_config_result.success is False
        assert 'not found' in missing_config_result.message.lower()
    
    def test_coordinate_validation_edge_cases(self):
        """Test coordinate validation with various edge cases."""
        validator = CoordinateValidator()
        
        # Test valid coordinates
        valid_result = validator.validate_coordinates(40.7128, -74.0060)
        assert valid_result[0] is True
        assert len(valid_result[1]) == 0
        
        # Test boundary coordinates
        north_pole = validator.validate_coordinates(90.0, 0.0)
        assert north_pole[0] is True
        
        south_pole = validator.validate_coordinates(-90.0, 0.0)
        assert south_pole[0] is True
        
        # Test invalid coordinates
        invalid_lat = validator.validate_coordinates(91.0, 0.0)
        assert invalid_lat[0] is False
        assert len(invalid_lat[1]) > 0
        
        invalid_lon = validator.validate_coordinates(0.0, 181.0)
        assert invalid_lon[0] is False
        assert len(invalid_lon[1]) > 0
        
        # Test None coordinates
        none_coords = validator.validate_coordinates(None, None)
        assert none_coords[0] is False
        assert len(none_coords[1]) == 2  # Both lat and lon errors
        
        # Test string coordinates
        string_coords = validator.validate_coordinates("40.7128", "-74.0060")
        assert string_coords[0] is True  # Should convert to float
        
        invalid_string = validator.validate_coordinates("invalid", "also_invalid")
        assert invalid_string[0] is False
        assert len(invalid_string[1]) == 2


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])