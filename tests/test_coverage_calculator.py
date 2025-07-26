"""
Unit tests for the Coverage Calculation Engine

This module contains comprehensive tests for coverage area calculations,
overlap detection, and geometric accuracy validation.
"""

import unittest
import math
from coverage_calculator import CoverageCalculator, CoverageArea, CoverageOverlap


class TestCoverageCalculator(unittest.TestCase):
    """Test cases for the CoverageCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_lat = 40.7128  # NYC latitude
        self.test_lon = -74.0060  # NYC longitude
        self.test_radius = 100.0  # 100 meters
        
        self.sample_camera = {
            'id': 1,
            'name': 'Test Camera',
            'latitude': self.test_lat,
            'longitude': self.test_lon,
            'coverage_radius': self.test_radius,
            'field_of_view_angle': 360.0,
            'coverage_direction': 0.0
        }
    
    def test_circular_coverage_basic(self):
        """Test basic circular coverage calculation."""
        coordinates = CoverageCalculator.calculate_circular_coverage(
            self.test_lat, self.test_lon, self.test_radius
        )
        
        # Should return a list of coordinate pairs
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 0)
        
        # Each coordinate should be a [lat, lon] pair
        for coord in coordinates:
            self.assertIsInstance(coord, list)
            self.assertEqual(len(coord), 2)
            self.assertIsInstance(coord[0], float)  # latitude
            self.assertIsInstance(coord[1], float)  # longitude
        
        # First and last coordinates should be the same (closed polygon)
        self.assertAlmostEqual(coordinates[0][0], coordinates[-1][0], places=6)
        self.assertAlmostEqual(coordinates[0][1], coordinates[-1][1], places=6)
    
    def test_circular_coverage_precision(self):
        """Test circular coverage with different precision levels."""
        # Test with different precision values
        for precision in [8, 16, 36, 72]:
            coordinates = CoverageCalculator.calculate_circular_coverage(
                self.test_lat, self.test_lon, self.test_radius, precision
            )
            
            # Should have precision + 1 points (to close the polygon)
            self.assertEqual(len(coordinates), precision + 1)
    
    def test_circular_coverage_radius_accuracy(self):
        """Test that circular coverage radius is approximately correct."""
        coordinates = CoverageCalculator.calculate_circular_coverage(
            self.test_lat, self.test_lon, self.test_radius, 36
        )
        
        # Calculate distance from center to each point
        center_lat, center_lon = self.test_lat, self.test_lon
        
        for coord in coordinates[:-1]:  # Exclude last point (duplicate of first)
            distance = CoverageCalculator._haversine_distance(
                center_lat, center_lon, coord[0], coord[1]
            )
            
            # Distance should be approximately equal to radius (within 1% tolerance)
            self.assertAlmostEqual(distance, self.test_radius, delta=self.test_radius * 0.01)
    
    def test_directional_coverage_basic(self):
        """Test basic directional coverage calculation."""
        direction = 90.0  # East
        angle = 60.0     # 60-degree field of view
        
        coordinates = CoverageCalculator.calculate_directional_coverage(
            self.test_lat, self.test_lon, self.test_radius, direction, angle
        )
        
        # Should return a list of coordinate pairs
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 2)  # At least camera position + arc points
        
        # First and last coordinates should be the camera position
        self.assertAlmostEqual(coordinates[0][0], self.test_lat, places=6)
        self.assertAlmostEqual(coordinates[0][1], self.test_lon, places=6)
        self.assertAlmostEqual(coordinates[-1][0], self.test_lat, places=6)
        self.assertAlmostEqual(coordinates[-1][1], self.test_lon, places=6)
    
    def test_directional_coverage_angles(self):
        """Test directional coverage with various angles."""
        direction = 0.0  # North
        
        for angle in [30.0, 60.0, 90.0, 180.0, 270.0]:
            coordinates = CoverageCalculator.calculate_directional_coverage(
                self.test_lat, self.test_lon, self.test_radius, direction, angle
            )
            
            # Should have appropriate number of points based on angle
            expected_points = max(int(angle), 1) + 2  # arc points + 2 camera positions
            self.assertGreaterEqual(len(coordinates), 3)
    
    def test_directional_coverage_directions(self):
        """Test directional coverage with different directions."""
        angle = 90.0  # 90-degree field of view
        
        for direction in [0.0, 90.0, 180.0, 270.0]:
            coordinates = CoverageCalculator.calculate_directional_coverage(
                self.test_lat, self.test_lon, self.test_radius, direction, angle
            )
            
            self.assertIsInstance(coordinates, list)
            self.assertGreater(len(coordinates), 2)
    
    def test_haversine_distance_accuracy(self):
        """Test Haversine distance calculation accuracy."""
        # Test known distances
        lat1, lon1 = 40.7128, -74.0060  # NYC
        lat2, lon2 = 40.7589, -73.9851  # Times Square (approximately 5.5 km)
        
        distance = CoverageCalculator._haversine_distance(lat1, lon1, lat2, lon2)
        
        # Should be approximately 5.5 km (within 10% tolerance)
        expected_distance = 5500  # meters
        self.assertAlmostEqual(distance, expected_distance, delta=expected_distance * 0.1)
    
    def test_haversine_distance_zero(self):
        """Test Haversine distance for same point."""
        distance = CoverageCalculator._haversine_distance(
            self.test_lat, self.test_lon, self.test_lat, self.test_lon
        )
        self.assertAlmostEqual(distance, 0.0, places=6)
    
    def test_coverage_overlaps_detection(self):
        """Test overlap detection between cameras."""
        # Create two cameras with overlapping coverage
        camera1 = {
            'id': 1,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'coverage_radius': 100.0
        }
        
        camera2 = {
            'id': 2,
            'latitude': 40.7138,  # Slightly north
            'longitude': -74.0050,  # Slightly east
            'coverage_radius': 100.0
        }
        
        cameras = [camera1, camera2]
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras)
        
        # Should detect one overlap
        self.assertEqual(len(overlaps), 1)
        
        overlap = overlaps[0]
        self.assertIsInstance(overlap, CoverageOverlap)
        self.assertEqual(overlap.camera1_id, 1)
        self.assertEqual(overlap.camera2_id, 2)
        self.assertGreater(overlap.overlap_distance, 0)
        self.assertGreater(overlap.overlap_percentage, 0)
    
    def test_coverage_no_overlaps(self):
        """Test no overlap detection for distant cameras."""
        # Create two cameras with no overlapping coverage
        camera1 = {
            'id': 1,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'coverage_radius': 50.0
        }
        
        camera2 = {
            'id': 2,
            'latitude': 40.8128,  # 1 degree north (much farther)
            'longitude': -74.0060,
            'coverage_radius': 50.0
        }
        
        cameras = [camera1, camera2]
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras)
        
        # Should detect no overlaps
        self.assertEqual(len(overlaps), 0)
    
    def test_multiple_camera_overlaps(self):
        """Test overlap detection with multiple cameras."""
        # Create three cameras in a triangle formation with overlaps
        cameras = [
            {
                'id': 1,
                'latitude': 40.7128,
                'longitude': -74.0060,
                'coverage_radius': 150.0
            },
            {
                'id': 2,
                'latitude': 40.7138,
                'longitude': -74.0050,
                'coverage_radius': 150.0
            },
            {
                'id': 3,
                'latitude': 40.7118,
                'longitude': -74.0050,
                'coverage_radius': 150.0
            }
        ]
        
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras)
        
        # Should detect 3 overlaps (each pair)
        self.assertEqual(len(overlaps), 3)
        
        # Check that all camera pairs are represented
        camera_pairs = {(o.camera1_id, o.camera2_id) for o in overlaps}
        expected_pairs = {(1, 2), (1, 3), (2, 3)}
        self.assertEqual(camera_pairs, expected_pairs)
    
    def test_geojson_generation_circular(self):
        """Test GeoJSON generation for circular coverage."""
        geojson = CoverageCalculator.get_coverage_area_geojson(self.sample_camera)
        
        self.assertIsNotNone(geojson)
        self.assertEqual(geojson['type'], 'Feature')
        self.assertIn('properties', geojson)
        self.assertIn('geometry', geojson)
        
        # Check properties
        props = geojson['properties']
        self.assertEqual(props['camera_id'], 1)
        self.assertEqual(props['camera_name'], 'Test Camera')
        self.assertEqual(props['coverage_radius'], self.test_radius)
        self.assertEqual(props['area_type'], 'circular')
        
        # Check geometry
        geometry = geojson['geometry']
        self.assertEqual(geometry['type'], 'Polygon')
        self.assertIn('coordinates', geometry)
        self.assertIsInstance(geometry['coordinates'][0], list)
    
    def test_geojson_generation_directional(self):
        """Test GeoJSON generation for directional coverage."""
        directional_camera = self.sample_camera.copy()
        directional_camera['field_of_view_angle'] = 90.0
        directional_camera['coverage_direction'] = 45.0
        
        geojson = CoverageCalculator.get_coverage_area_geojson(directional_camera)
        
        self.assertIsNotNone(geojson)
        self.assertEqual(geojson['type'], 'Feature')
        
        # Check properties
        props = geojson['properties']
        self.assertEqual(props['area_type'], 'directional')
        self.assertEqual(props['field_of_view'], 90.0)
        self.assertEqual(props['direction'], 45.0)
    
    def test_geojson_invalid_camera(self):
        """Test GeoJSON generation with invalid camera data."""
        invalid_camera = {
            'id': 1,
            'name': 'Invalid Camera',
            'latitude': None,
            'longitude': None
        }
        
        geojson = CoverageCalculator.get_coverage_area_geojson(invalid_camera)
        self.assertIsNone(geojson)
    
    def test_coverage_area_creation(self):
        """Test CoverageArea object creation."""
        coverage_area = CoverageCalculator.create_coverage_area(self.sample_camera)
        
        self.assertIsNotNone(coverage_area)
        self.assertIsInstance(coverage_area, CoverageArea)
        self.assertEqual(coverage_area.camera_id, 1)
        self.assertEqual(coverage_area.center_lat, self.test_lat)
        self.assertEqual(coverage_area.center_lon, self.test_lon)
        self.assertEqual(coverage_area.radius, self.test_radius)
        self.assertEqual(coverage_area.area_type, 'circular')
        self.assertIsInstance(coverage_area.coordinates, list)
    
    def test_coverage_area_size_calculation(self):
        """Test coverage area size calculation."""
        # Create a simple square for testing
        square_coords = [
            [40.7128, -74.0060],
            [40.7138, -74.0060],
            [40.7138, -74.0050],
            [40.7128, -74.0050],
            [40.7128, -74.0060]  # Close the polygon
        ]
        
        area = CoverageCalculator.calculate_coverage_area_size(square_coords)
        
        # Should return a positive area
        self.assertGreater(area, 0)
        self.assertIsInstance(area, float)
    
    def test_coordinate_validation(self):
        """Test coordinate validation."""
        # Valid coordinates
        self.assertTrue(CoverageCalculator._validate_coordinates(40.7128, -74.0060))
        self.assertTrue(CoverageCalculator._validate_coordinates(0, 0))
        self.assertTrue(CoverageCalculator._validate_coordinates(90, 180))
        self.assertTrue(CoverageCalculator._validate_coordinates(-90, -180))
        
        # Invalid coordinates
        self.assertFalse(CoverageCalculator._validate_coordinates(91, 0))  # Lat > 90
        self.assertFalse(CoverageCalculator._validate_coordinates(-91, 0))  # Lat < -90
        self.assertFalse(CoverageCalculator._validate_coordinates(0, 181))  # Lon > 180
        self.assertFalse(CoverageCalculator._validate_coordinates(0, -181))  # Lon < -180
        self.assertFalse(CoverageCalculator._validate_coordinates('invalid', 0))
        self.assertFalse(CoverageCalculator._validate_coordinates(0, 'invalid'))
    
    def test_error_handling_invalid_radius(self):
        """Test error handling for invalid radius values."""
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_circular_coverage(
                self.test_lat, self.test_lon, -10.0
            )
        
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_circular_coverage(
                self.test_lat, self.test_lon, 0.0
            )
    
    def test_error_handling_invalid_coordinates(self):
        """Test error handling for invalid coordinates."""
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_circular_coverage(
                91.0, self.test_lon, self.test_radius
            )
        
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_directional_coverage(
                self.test_lat, 181.0, self.test_radius, 0.0, 90.0
            )
    
    def test_error_handling_invalid_angles(self):
        """Test error handling for invalid angle values."""
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_directional_coverage(
                self.test_lat, self.test_lon, self.test_radius, 0.0, 0.0
            )
        
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_directional_coverage(
                self.test_lat, self.test_lon, self.test_radius, 0.0, 361.0
            )
        
        with self.assertRaises(ValueError):
            CoverageCalculator.calculate_directional_coverage(
                self.test_lat, self.test_lon, self.test_radius, 360.0, 90.0
            )
    
    def test_edge_case_small_radius(self):
        """Test coverage calculation with very small radius."""
        small_radius = 1.0  # 1 meter
        coordinates = CoverageCalculator.calculate_circular_coverage(
            self.test_lat, self.test_lon, small_radius
        )
        
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 0)
    
    def test_edge_case_large_radius(self):
        """Test coverage calculation with large radius."""
        large_radius = 10000.0  # 10 km
        coordinates = CoverageCalculator.calculate_circular_coverage(
            self.test_lat, self.test_lon, large_radius
        )
        
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 0)
    
    def test_edge_case_narrow_field_of_view(self):
        """Test directional coverage with very narrow field of view."""
        narrow_angle = 1.0  # 1 degree
        coordinates = CoverageCalculator.calculate_directional_coverage(
            self.test_lat, self.test_lon, self.test_radius, 0.0, narrow_angle
        )
        
        self.assertIsInstance(coordinates, list)
        self.assertGreaterEqual(len(coordinates), 3)  # Camera + at least 2 arc points
    
    def test_edge_case_wide_field_of_view(self):
        """Test directional coverage with wide field of view."""
        wide_angle = 359.0  # Almost full circle
        coordinates = CoverageCalculator.calculate_directional_coverage(
            self.test_lat, self.test_lon, self.test_radius, 0.0, wide_angle
        )
        
        self.assertIsInstance(coordinates, list)
        self.assertGreater(len(coordinates), 300)  # Should have many points


class TestCoverageAreaDataClass(unittest.TestCase):
    """Test cases for the CoverageArea data class."""
    
    def test_coverage_area_creation(self):
        """Test CoverageArea object creation and attributes."""
        coordinates = [[40.7128, -74.0060], [40.7138, -74.0050], [40.7128, -74.0060]]
        
        coverage_area = CoverageArea(
            camera_id=1,
            center_lat=40.7128,
            center_lon=-74.0060,
            radius=100.0,
            field_of_view=360.0,
            direction=0.0,
            coordinates=coordinates,
            area_type='circular'
        )
        
        self.assertEqual(coverage_area.camera_id, 1)
        self.assertEqual(coverage_area.center_lat, 40.7128)
        self.assertEqual(coverage_area.center_lon, -74.0060)
        self.assertEqual(coverage_area.radius, 100.0)
        self.assertEqual(coverage_area.field_of_view, 360.0)
        self.assertEqual(coverage_area.direction, 0.0)
        self.assertEqual(coverage_area.coordinates, coordinates)
        self.assertEqual(coverage_area.area_type, 'circular')


class TestCoverageOverlapDataClass(unittest.TestCase):
    """Test cases for the CoverageOverlap data class."""
    
    def test_coverage_overlap_creation(self):
        """Test CoverageOverlap object creation and attributes."""
        overlap = CoverageOverlap(
            camera1_id=1,
            camera2_id=2,
            distance=150.0,
            overlap_distance=50.0,
            overlap_percentage=25.0
        )
        
        self.assertEqual(overlap.camera1_id, 1)
        self.assertEqual(overlap.camera2_id, 2)
        self.assertEqual(overlap.distance, 150.0)
        self.assertEqual(overlap.overlap_distance, 50.0)
        self.assertEqual(overlap.overlap_percentage, 25.0)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)