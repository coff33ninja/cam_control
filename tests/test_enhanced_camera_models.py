"""
Unit tests for Enhanced Camera Data Models

This module contains comprehensive tests for the enhanced camera models,
including validation, serialization, and map functionality.
"""

import unittest
import json
from datetime import datetime
from enhanced_camera_models import (
    EnhancedCamera, MapConfiguration, 
    create_camera_from_form_data, validate_camera_batch,
    export_cameras_to_json, import_cameras_from_json
)


class TestEnhancedCamera(unittest.TestCase):
    """Test cases for the EnhancedCamera class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_camera = EnhancedCamera(
            id=1,
            name="Test Camera",
            location="Test Location",
            ip_address="192.168.1.100",
            mac_address="00:11:22:33:44:55",
            latitude=40.7128,
            longitude=-74.0060,
            coverage_radius=100.0,
            field_of_view_angle=360.0,
            coverage_direction=0.0,
            has_memory_card=True,
            date_installed="2024-01-15"
        )
    
    def test_camera_creation(self):
        """Test basic camera creation."""
        camera = self.sample_camera
        
        self.assertEqual(camera.id, 1)
        self.assertEqual(camera.name, "Test Camera")
        self.assertEqual(camera.location, "Test Location")
        self.assertEqual(camera.ip_address, "192.168.1.100")
        self.assertEqual(camera.mac_address, "00:11:22:33:44:55")
        self.assertEqual(camera.latitude, 40.7128)
        self.assertEqual(camera.longitude, -74.0060)
        self.assertEqual(camera.coverage_radius, 100.0)
        self.assertEqual(camera.field_of_view_angle, 360.0)
        self.assertEqual(camera.coverage_direction, 0.0)
        self.assertTrue(camera.has_memory_card)
        self.assertFalse(camera.is_online)
    
    def test_to_map_marker(self):
        """Test conversion to map marker configuration."""
        marker = self.sample_camera.to_map_marker()
        
        self.assertIsInstance(marker, dict)
        self.assertEqual(marker['id'], 1)
        self.assertEqual(marker['name'], "Test Camera")
        self.assertEqual(marker['location'], "Test Location")
        self.assertEqual(marker['ip_address'], "192.168.1.100")
        self.assertEqual(marker['latitude'], 40.7128)
        self.assertEqual(marker['longitude'], -74.0060)
        self.assertEqual(marker['marker_color'], 'red')  # Offline by default
        self.assertEqual(marker['marker_icon'], 'video-camera')
        self.assertIn('popup_content', marker)
        self.assertIn('tooltip', marker)
        self.assertEqual(marker['coverage_radius'], 100.0)
    
    def test_get_coverage_geometry(self):
        """Test coverage geometry generation."""
        geometry = self.sample_camera.get_coverage_geometry()
        
        self.assertIsNotNone(geometry)
        self.assertEqual(geometry['type'], 'Feature')
        self.assertIn('properties', geometry)
        self.assertIn('geometry', geometry)
        
        props = geometry['properties']
        self.assertEqual(props['camera_id'], 1)
        self.assertEqual(props['camera_name'], "Test Camera")
        self.assertEqual(props['coverage_radius'], 100.0)
        self.assertEqual(props['area_type'], 'circular')
    
    def test_get_coverage_coordinates(self):
        """Test coverage coordinates calculation."""
        coordinates = self.sample_camera.get_coverage_coordinates()
        
        self.assertIsNotNone(coordinates)
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 0)
        
        # Each coordinate should be [lat, lon]
        for coord in coordinates:
            self.assertIsInstance(coord, list)
            self.assertEqual(len(coord), 2)
            self.assertIsInstance(coord[0], float)
            self.assertIsInstance(coord[1], float)
    
    def test_get_coverage_coordinates_no_location(self):
        """Test coverage coordinates with no location."""
        camera = EnhancedCamera(
            id=1, name="Test", location="Test", 
            ip_address="192.168.1.1", mac_address="00:11:22:33:44:55"
        )
        
        coordinates = camera.get_coverage_coordinates()
        self.assertIsNone(coordinates)
    
    def test_directional_coverage(self):
        """Test directional coverage area."""
        camera = self.sample_camera
        camera.field_of_view_angle = 90.0
        camera.coverage_direction = 45.0
        
        coordinates = camera.get_coverage_coordinates()
        geometry = camera.get_coverage_geometry()
        
        self.assertIsNotNone(coordinates)
        self.assertIsNotNone(geometry)
        self.assertEqual(geometry['properties']['area_type'], 'directional')
        self.assertEqual(geometry['properties']['field_of_view'], 90.0)
        self.assertEqual(geometry['properties']['direction'], 45.0)
    
    def test_update_coordinates(self):
        """Test coordinate updates with validation."""
        camera = self.sample_camera
        
        # Valid coordinates
        self.assertTrue(camera.update_coordinates(41.0, -75.0))
        self.assertEqual(camera.latitude, 41.0)
        self.assertEqual(camera.longitude, -75.0)
        
        # Invalid coordinates
        self.assertFalse(camera.update_coordinates(91.0, -75.0))  # Invalid latitude
        self.assertEqual(camera.latitude, 41.0)  # Should remain unchanged
        
        self.assertFalse(camera.update_coordinates(41.0, 181.0))  # Invalid longitude
        self.assertEqual(camera.longitude, -75.0)  # Should remain unchanged
    
    def test_update_coverage_parameters(self):
        """Test coverage parameter updates with validation."""
        camera = self.sample_camera
        
        # Valid parameters
        self.assertTrue(camera.update_coverage_parameters(150.0, 180.0, 90.0))
        self.assertEqual(camera.coverage_radius, 150.0)
        self.assertEqual(camera.field_of_view_angle, 180.0)
        self.assertEqual(camera.coverage_direction, 90.0)
        
        # Invalid radius
        self.assertFalse(camera.update_coverage_parameters(0.5, 180.0, 90.0))
        self.assertEqual(camera.coverage_radius, 150.0)  # Should remain unchanged
        
        # Invalid angle
        self.assertFalse(camera.update_coverage_parameters(150.0, 361.0, 90.0))
        self.assertEqual(camera.field_of_view_angle, 180.0)  # Should remain unchanged
        
        # Invalid direction
        self.assertFalse(camera.update_coverage_parameters(150.0, 180.0, 360.0))
        self.assertEqual(camera.coverage_direction, 90.0)  # Should remain unchanged
    
    def test_update_connectivity_status(self):
        """Test connectivity status updates."""
        camera = self.sample_camera
        test_time = datetime.now()
        
        camera.update_connectivity_status(True, test_time)
        self.assertTrue(camera.is_online)
        self.assertEqual(camera.last_ping_time, test_time)
        
        camera.update_connectivity_status(False)
        self.assertFalse(camera.is_online)
        self.assertIsNotNone(camera.last_ping_time)
    
    def test_coordinate_validation(self):
        """Test coordinate validation."""
        # Valid coordinates
        self.assertTrue(EnhancedCamera.validate_coordinates(40.7128, -74.0060))
        self.assertTrue(EnhancedCamera.validate_coordinates(0, 0))
        self.assertTrue(EnhancedCamera.validate_coordinates(90, 180))
        self.assertTrue(EnhancedCamera.validate_coordinates(-90, -180))
        self.assertTrue(EnhancedCamera.validate_coordinates(None, None))
        
        # Invalid coordinates
        self.assertFalse(EnhancedCamera.validate_coordinates(91, 0))
        self.assertFalse(EnhancedCamera.validate_coordinates(-91, 0))
        self.assertFalse(EnhancedCamera.validate_coordinates(0, 181))
        self.assertFalse(EnhancedCamera.validate_coordinates(0, -181))
        self.assertFalse(EnhancedCamera.validate_coordinates('invalid', 0))
        self.assertFalse(EnhancedCamera.validate_coordinates(0, 'invalid'))
    
    def test_coverage_parameter_validation(self):
        """Test coverage parameter validation."""
        # Valid parameters
        self.assertTrue(EnhancedCamera.validate_coverage_parameters(50.0, 360.0, 0.0))
        self.assertTrue(EnhancedCamera.validate_coverage_parameters(1.0, 1.0, 359.9))
        self.assertTrue(EnhancedCamera.validate_coverage_parameters(10000.0, 360.0, 180.0))
        
        # Invalid radius
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(0.5, 360.0, 0.0))
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(10001.0, 360.0, 0.0))
        
        # Invalid angle
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(50.0, 0.5, 0.0))
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(50.0, 361.0, 0.0))
        
        # Invalid direction
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(50.0, 360.0, -1.0))
        self.assertFalse(EnhancedCamera.validate_coverage_parameters(50.0, 360.0, 360.0))
        
        # String inputs (should convert)
        self.assertTrue(EnhancedCamera.validate_coverage_parameters("50.0", "360.0", "0.0"))
        self.assertFalse(EnhancedCamera.validate_coverage_parameters("invalid", "360.0", "0.0"))
    
    def test_ip_address_validation(self):
        """Test IP address validation."""
        # Valid IP addresses
        self.assertTrue(EnhancedCamera.validate_ip_address("192.168.1.1"))
        self.assertTrue(EnhancedCamera.validate_ip_address("10.0.0.1"))
        self.assertTrue(EnhancedCamera.validate_ip_address("255.255.255.255"))
        self.assertTrue(EnhancedCamera.validate_ip_address("0.0.0.0"))
        
        # Invalid IP addresses
        self.assertFalse(EnhancedCamera.validate_ip_address("256.1.1.1"))
        self.assertFalse(EnhancedCamera.validate_ip_address("192.168.1"))
        self.assertFalse(EnhancedCamera.validate_ip_address("192.168.1.1.1"))
        self.assertFalse(EnhancedCamera.validate_ip_address("invalid"))
        self.assertFalse(EnhancedCamera.validate_ip_address(""))
    
    def test_mac_address_validation(self):
        """Test MAC address validation."""
        # Valid MAC addresses
        self.assertTrue(EnhancedCamera.validate_mac_address("00:11:22:33:44:55"))
        self.assertTrue(EnhancedCamera.validate_mac_address("AA:BB:CC:DD:EE:FF"))
        self.assertTrue(EnhancedCamera.validate_mac_address("aa:bb:cc:dd:ee:ff"))
        
        # Invalid MAC addresses
        self.assertFalse(EnhancedCamera.validate_mac_address("00:11:22:33:44"))
        self.assertFalse(EnhancedCamera.validate_mac_address("00-11-22-33-44-55"))
        self.assertFalse(EnhancedCamera.validate_mac_address("GG:11:22:33:44:55"))
        self.assertFalse(EnhancedCamera.validate_mac_address("invalid"))
        self.assertFalse(EnhancedCamera.validate_mac_address(""))
    
    def test_date_validation(self):
        """Test date validation."""
        # Valid dates
        self.assertTrue(EnhancedCamera.validate_date("2024-01-15"))
        self.assertTrue(EnhancedCamera.validate_date("2023-12-31"))
        self.assertTrue(EnhancedCamera.validate_date(None))
        self.assertTrue(EnhancedCamera.validate_date(""))
        
        # Invalid dates
        self.assertFalse(EnhancedCamera.validate_date("2024-13-01"))
        self.assertFalse(EnhancedCamera.validate_date("2024-01-32"))
        self.assertFalse(EnhancedCamera.validate_date("invalid"))
        self.assertFalse(EnhancedCamera.validate_date("01-15-2024"))
    
    def test_validate_all_fields(self):
        """Test comprehensive field validation."""
        camera = self.sample_camera
        validation_results = camera.validate_all_fields()
        
        self.assertIsInstance(validation_results, dict)
        expected_keys = [
            'coordinates', 'coverage_parameters', 'ip_address', 
            'mac_address', 'date_installed', 'memory_card_reset'
        ]
        
        for key in expected_keys:
            self.assertIn(key, validation_results)
            self.assertIsInstance(validation_results[key], bool)
    
    def test_is_valid(self):
        """Test overall camera validation."""
        camera = self.sample_camera
        self.assertTrue(camera.is_valid())
        
        # Make camera invalid
        camera.ip_address = "invalid_ip"
        self.assertFalse(camera.is_valid())
    
    def test_get_validation_errors(self):
        """Test validation error reporting."""
        camera = self.sample_camera
        camera.ip_address = "invalid_ip"
        camera.coverage_radius = 0.5  # Invalid radius
        
        errors = camera.get_validation_errors()
        self.assertIsInstance(errors, list)
        self.assertGreater(len(errors), 0)
        
        # Check that IP and coverage errors are reported
        error_text = " ".join(errors)
        self.assertIn("IP address", error_text)
        self.assertIn("coverage parameters", error_text)
    
    def test_serialization_to_dict(self):
        """Test conversion to dictionary."""
        camera = self.sample_camera
        camera.last_ping_time = datetime.now()
        
        data = camera.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], "Test Camera")
        self.assertIn('last_ping_time', data)
        self.assertIsInstance(data['last_ping_time'], str)  # Should be ISO format
    
    def test_serialization_to_json(self):
        """Test JSON serialization."""
        camera = self.sample_camera
        json_str = camera.to_json()
        
        self.assertIsInstance(json_str, str)
        
        # Should be valid JSON
        data = json.loads(json_str)
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], "Test Camera")
    
    def test_deserialization_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'id': 2,
            'name': 'Test Camera 2',
            'location': 'Test Location 2',
            'ip_address': '192.168.1.101',
            'mac_address': '00:11:22:33:44:56',
            'latitude': 41.0,
            'longitude': -75.0,
            'coverage_radius': 75.0,
            'field_of_view_angle': 180.0,
            'coverage_direction': 90.0,
            'has_memory_card': False,
            'last_ping_time': '2024-01-15T10:30:00'
        }
        
        camera = EnhancedCamera.from_dict(data)
        
        self.assertEqual(camera.id, 2)
        self.assertEqual(camera.name, 'Test Camera 2')
        self.assertEqual(camera.latitude, 41.0)
        self.assertEqual(camera.coverage_radius, 75.0)
        self.assertIsInstance(camera.last_ping_time, datetime)
    
    def test_deserialization_from_json(self):
        """Test creation from JSON."""
        json_str = '''
        {
            "id": 3,
            "name": "Test Camera 3",
            "location": "Test Location 3",
            "ip_address": "192.168.1.102",
            "mac_address": "00:11:22:33:44:57",
            "latitude": 42.0,
            "longitude": -76.0,
            "coverage_radius": 125.0,
            "field_of_view_angle": 270.0,
            "coverage_direction": 180.0,
            "has_memory_card": true
        }
        '''
        
        camera = EnhancedCamera.from_json(json_str)
        
        self.assertEqual(camera.id, 3)
        self.assertEqual(camera.name, 'Test Camera 3')
        self.assertEqual(camera.latitude, 42.0)
        self.assertEqual(camera.coverage_radius, 125.0)
        self.assertTrue(camera.has_memory_card)
    
    def test_from_db_row(self):
        """Test creation from database row."""
        # Test with full row
        full_row = (
            1, 'Test Location', 'Test Camera', '00:11:22:33:44:55', '192.168.1.100',
            'Group A', '2024-01-15', 1, 40.7128, -74.0060, True, '2024-01-10',
            100.0, 360.0, 0.0
        )
        
        camera = EnhancedCamera.from_db_row(full_row)
        
        self.assertEqual(camera.id, 1)
        self.assertEqual(camera.name, 'Test Camera')
        self.assertEqual(camera.location, 'Test Location')
        self.assertEqual(camera.coverage_radius, 100.0)
        
        # Test with minimal row (backward compatibility)
        minimal_row = (1, 'Test Location', 'Test Camera', '00:11:22:33:44:55', '192.168.1.100')
        
        camera = EnhancedCamera.from_db_row(minimal_row)
        
        self.assertEqual(camera.id, 1)
        self.assertEqual(camera.coverage_radius, 50.0)  # Default value
        self.assertEqual(camera.field_of_view_angle, 360.0)  # Default value
    
    def test_to_db_tuple(self):
        """Test conversion to database tuple."""
        camera = self.sample_camera
        db_tuple = camera.to_db_tuple()
        
        self.assertIsInstance(db_tuple, tuple)
        self.assertEqual(len(db_tuple), 14)  # Expected number of fields
        self.assertEqual(db_tuple[0], 'Test Location')  # location
        self.assertEqual(db_tuple[1], 'Test Camera')    # name
        self.assertEqual(db_tuple[11], 100.0)           # coverage_radius
    
    def test_calculate_coverage_area_size(self):
        """Test coverage area size calculation."""
        camera = self.sample_camera
        area_size = camera.calculate_coverage_area_size()
        
        self.assertIsNotNone(area_size)
        self.assertIsInstance(area_size, float)
        self.assertGreater(area_size, 0)
        
        # Camera without coordinates should return None
        camera.latitude = None
        camera.longitude = None
        area_size = camera.calculate_coverage_area_size()
        self.assertIsNone(area_size)
    
    def test_find_overlaps_with(self):
        """Test finding overlaps with other cameras."""
        camera1 = self.sample_camera
        
        camera2 = EnhancedCamera(
            id=2, name="Camera 2", location="Location 2",
            ip_address="192.168.1.101", mac_address="00:11:22:33:44:56",
            latitude=40.7138, longitude=-74.0050,  # Close to camera1
            coverage_radius=100.0
        )
        
        camera3 = EnhancedCamera(
            id=3, name="Camera 3", location="Location 3",
            ip_address="192.168.1.102", mac_address="00:11:22:33:44:57",
            latitude=41.0, longitude=-75.0,  # Far from camera1
            coverage_radius=50.0
        )
        
        overlaps = camera1.find_overlaps_with([camera2, camera3])
        
        self.assertIsInstance(overlaps, list)
        # Should find overlap with camera2 but not camera3
        self.assertGreater(len(overlaps), 0)
        
        # Check overlap structure
        if overlaps:
            overlap = overlaps[0]
            self.assertIn('other_camera_id', overlap)
            self.assertIn('distance', overlap)
            self.assertIn('overlap_distance', overlap)
            self.assertIn('overlap_percentage', overlap)
    
    def test_string_representations(self):
        """Test string representations."""
        camera = self.sample_camera
        
        str_repr = str(camera)
        self.assertIn("Test Camera", str_repr)
        self.assertIn("Test Location", str_repr)
        self.assertIn("Offline", str_repr)
        
        repr_str = repr(camera)
        self.assertIn("EnhancedCamera", repr_str)
        self.assertIn("id=1", repr_str)
        self.assertIn("name='Test Camera'", repr_str)


class TestMapConfiguration(unittest.TestCase):
    """Test cases for the MapConfiguration class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.camera_positions = {
            1: {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'coverage_radius': 100.0,
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            },
            2: {
                'latitude': 40.7138,
                'longitude': -74.0050,
                'coverage_radius': 75.0,
                'field_of_view_angle': 180.0,
                'coverage_direction': 90.0
            }
        }
        
        self.config = MapConfiguration(
            id=1,
            name="Test Configuration",
            description="Test configuration for unit tests",
            camera_positions=self.camera_positions,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            updated_at=datetime(2024, 1, 15, 11, 0, 0)
        )
    
    def test_configuration_creation(self):
        """Test basic configuration creation."""
        config = self.config
        
        self.assertEqual(config.id, 1)
        self.assertEqual(config.name, "Test Configuration")
        self.assertEqual(config.description, "Test configuration for unit tests")
        self.assertEqual(len(config.camera_positions), 2)
        self.assertIn(1, config.camera_positions)
        self.assertIn(2, config.camera_positions)
    
    def test_to_json(self):
        """Test JSON serialization."""
        json_str = self.config.to_json()
        
        self.assertIsInstance(json_str, str)
        
        # Should be valid JSON
        data = json.loads(json_str)
        self.assertEqual(data['name'], "Test Configuration")
        self.assertIn('camera_positions', data)
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        data = self.config.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], "Test Configuration")
        self.assertIn('camera_positions', data)
        self.assertIsInstance(data['created_at'], str)  # Should be ISO format
    
    def test_from_json(self):
        """Test creation from JSON."""
        json_data = '''
        {
            "camera_positions": {
                "1": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "coverage_radius": 100.0,
                    "field_of_view_angle": 360.0,
                    "coverage_direction": 0.0
                }
            },
            "created_at": "2024-01-15T10:30:00",
            "updated_at": "2024-01-15T11:00:00"
        }
        '''
        
        config = MapConfiguration.from_json(
            config_id=2,
            name="From JSON Config",
            description="Created from JSON",
            json_data=json_data
        )
        
        self.assertEqual(config.id, 2)
        self.assertEqual(config.name, "From JSON Config")
        self.assertIn('1', config.camera_positions)
        self.assertIsInstance(config.created_at, datetime)
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            'id': 3,
            'name': 'From Dict Config',
            'description': 'Created from dictionary',
            'camera_positions': self.camera_positions,
            'created_at': '2024-01-15T10:30:00',
            'updated_at': '2024-01-15T11:00:00'
        }
        
        config = MapConfiguration.from_dict(data)
        
        self.assertEqual(config.id, 3)
        self.assertEqual(config.name, 'From Dict Config')
        self.assertEqual(len(config.camera_positions), 2)
        self.assertIsInstance(config.created_at, datetime)
    
    def test_apply_to_cameras(self):
        """Test applying configuration to cameras."""
        camera1 = EnhancedCamera(
            id=1, name="Camera 1", location="Location 1",
            ip_address="192.168.1.100", mac_address="00:11:22:33:44:55",
            latitude=0.0, longitude=0.0  # Different from config
        )
        
        camera2 = EnhancedCamera(
            id=2, name="Camera 2", location="Location 2",
            ip_address="192.168.1.101", mac_address="00:11:22:33:44:56",
            latitude=0.0, longitude=0.0  # Different from config
        )
        
        cameras = [camera1, camera2]
        updated_cameras = self.config.apply_to_cameras(cameras)
        
        self.assertEqual(len(updated_cameras), 2)
        
        # Check that positions were applied
        updated_camera1 = updated_cameras[0]
        self.assertEqual(updated_camera1.latitude, 40.7128)
        self.assertEqual(updated_camera1.longitude, -74.0060)
        self.assertEqual(updated_camera1.coverage_radius, 100.0)
        
        updated_camera2 = updated_cameras[1]
        self.assertEqual(updated_camera2.latitude, 40.7138)
        self.assertEqual(updated_camera2.longitude, -74.0050)
        self.assertEqual(updated_camera2.field_of_view_angle, 180.0)
    
    def test_add_camera_position(self):
        """Test adding camera position to configuration."""
        camera = EnhancedCamera(
            id=3, name="Camera 3", location="Location 3",
            ip_address="192.168.1.102", mac_address="00:11:22:33:44:57",
            latitude=41.0, longitude=-75.0,
            coverage_radius=150.0, field_of_view_angle=270.0, coverage_direction=180.0
        )
        
        original_count = self.config.get_camera_count()
        original_updated_at = self.config.updated_at
        
        self.config.add_camera_position(camera)
        
        self.assertEqual(self.config.get_camera_count(), original_count + 1)
        self.assertIn(3, self.config.camera_positions)
        self.assertGreater(self.config.updated_at, original_updated_at)
        
        # Check position data
        position = self.config.camera_positions[3]
        self.assertEqual(position['latitude'], 41.0)
        self.assertEqual(position['longitude'], -75.0)
        self.assertEqual(position['coverage_radius'], 150.0)
    
    def test_remove_camera_position(self):
        """Test removing camera position from configuration."""
        original_count = self.config.get_camera_count()
        original_updated_at = self.config.updated_at
        
        self.config.remove_camera_position(1)
        
        self.assertEqual(self.config.get_camera_count(), original_count - 1)
        self.assertNotIn(1, self.config.camera_positions)
        self.assertGreater(self.config.updated_at, original_updated_at)
        
        # Removing non-existent camera should not cause error
        self.config.remove_camera_position(999)
        self.assertEqual(self.config.get_camera_count(), original_count - 1)
    
    def test_get_camera_count(self):
        """Test camera count calculation."""
        count = self.config.get_camera_count()
        self.assertEqual(count, 2)
        
        # Empty configuration
        empty_config = MapConfiguration(
            id=None, name="Empty", description="Empty config",
            camera_positions={}, created_at=datetime.now(), updated_at=datetime.now()
        )
        self.assertEqual(empty_config.get_camera_count(), 0)
    
    def test_validate(self):
        """Test configuration validation."""
        # Valid configuration
        self.assertTrue(self.config.validate())
        
        # Invalid name
        invalid_config = MapConfiguration(
            id=None, name="", description="Invalid config",
            camera_positions=self.camera_positions,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        self.assertFalse(invalid_config.validate())
        
        # Invalid camera positions
        invalid_positions = {
            1: {
                'latitude': 91.0,  # Invalid latitude
                'longitude': -74.0060,
                'coverage_radius': 100.0,
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            }
        }
        
        invalid_config.name = "Valid Name"
        invalid_config.camera_positions = invalid_positions
        self.assertFalse(invalid_config.validate())
    
    def test_string_representations(self):
        """Test string representations."""
        str_repr = str(self.config)
        self.assertIn("Test Configuration", str_repr)
        self.assertIn("2 cameras", str_repr)
        
        repr_str = repr(self.config)
        self.assertIn("MapConfiguration", repr_str)
        self.assertIn("id=1", repr_str)
        self.assertIn("cameras=2", repr_str)


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions."""
    
    def test_create_camera_from_form_data(self):
        """Test camera creation from form data."""
        form_data = {
            'id': '1',
            'name': 'Form Camera',
            'location': 'Form Location',
            'ip_address': '192.168.1.100',
            'mac_address': '00:11:22:33:44:55',
            'latitude': '40.7128',
            'longitude': '-74.0060',
            'coverage_radius': '100.0',
            'field_of_view_angle': '360.0',
            'coverage_direction': '0.0',
            'has_memory_card': True,
            'date_installed': '2024-01-15'
        }
        
        camera = create_camera_from_form_data(form_data)
        
        self.assertIsInstance(camera, EnhancedCamera)
        self.assertEqual(camera.id, 1)
        self.assertEqual(camera.name, 'Form Camera')
        self.assertEqual(camera.latitude, 40.7128)
        self.assertEqual(camera.coverage_radius, 100.0)
        self.assertTrue(camera.has_memory_card)
    
    def test_validate_camera_batch(self):
        """Test batch camera validation."""
        valid_camera = EnhancedCamera(
            id=1, name="Valid Camera", location="Location",
            ip_address="192.168.1.100", mac_address="00:11:22:33:44:55"
        )
        
        invalid_camera = EnhancedCamera(
            id=2, name="Invalid Camera", location="Location",
            ip_address="invalid_ip", mac_address="invalid_mac"
        )
        
        cameras = [valid_camera, invalid_camera]
        results = validate_camera_batch(cameras)
        
        self.assertEqual(results['total_cameras'], 2)
        self.assertEqual(results['valid_cameras'], 1)
        self.assertEqual(results['invalid_cameras'], 1)
        self.assertEqual(results['success_rate'], 50.0)
        self.assertIn(2, results['validation_errors'])
    
    def test_export_import_cameras_json(self):
        """Test JSON export and import of cameras."""
        cameras = [
            EnhancedCamera(
                id=1, name="Camera 1", location="Location 1",
                ip_address="192.168.1.100", mac_address="00:11:22:33:44:55",
                latitude=40.7128, longitude=-74.0060
            ),
            EnhancedCamera(
                id=2, name="Camera 2", location="Location 2",
                ip_address="192.168.1.101", mac_address="00:11:22:33:44:56",
                latitude=40.7138, longitude=-74.0050
            )
        ]
        
        # Export to JSON
        json_str = export_cameras_to_json(cameras)
        self.assertIsInstance(json_str, str)
        
        # Should be valid JSON
        data = json.loads(json_str)
        self.assertEqual(len(data), 2)
        
        # Import from JSON
        imported_cameras = import_cameras_from_json(json_str)
        self.assertEqual(len(imported_cameras), 2)
        
        # Check that data is preserved
        self.assertEqual(imported_cameras[0].id, 1)
        self.assertEqual(imported_cameras[0].name, "Camera 1")
        self.assertEqual(imported_cameras[1].id, 2)
        self.assertEqual(imported_cameras[1].name, "Camera 2")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)