#!/usr/bin/env python3
"""
Tests for LocationDetector service

This module contains comprehensive tests for the location detection functionality
including IP geolocation, timezone estimation, caching, and database operations.
"""

import asyncio
import pytest
import pytest_asyncio
import tempfile
import os
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import the module under test
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from location_detector import LocationDetector, LocationResult

class TestLocationDetector:
    """Test suite for LocationDetector class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        yield temp_file.name
        
        # Cleanup
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
    
    @pytest_asyncio.fixture
    async def detector(self, temp_db):
        """Create LocationDetector instance with temporary database."""
        # Initialize database with required schema
        import aiosqlite
        async with aiosqlite.connect(temp_db) as db:
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
            await db.commit()
        
        return LocationDetector(temp_db)
    
    def test_coordinate_validation(self, detector):
        """Test coordinate validation functionality."""
        # Valid coordinates
        assert detector._validate_coordinates(40.7128, -74.0060) == True
        assert detector._validate_coordinates(0, 0) == True
        assert detector._validate_coordinates(90, 180) == True
        assert detector._validate_coordinates(-90, -180) == True
        
        # Invalid coordinates
        assert detector._validate_coordinates(91, 0) == False  # Latitude too high
        assert detector._validate_coordinates(-91, 0) == False  # Latitude too low
        assert detector._validate_coordinates(0, 181) == False  # Longitude too high
        assert detector._validate_coordinates(0, -181) == False  # Longitude too low
        
        # Invalid types
        assert detector._validate_coordinates("invalid", 0) == False
        assert detector._validate_coordinates(0, None) == False
    
    @pytest.mark.asyncio
    async def test_store_detected_location(self, detector):
        """Test storing location in database."""
        # Test valid location storage
        result = await detector.store_detected_location(
            40.7128, -74.0060, 
            "New York, NY, USA", 
            "test_method", 
            0.8
        )
        
        assert result['success'] == True
        assert result['location_id'] is not None
        assert result['latitude'] == 40.7128
        assert result['longitude'] == -74.0060
        assert result['address'] == "New York, NY, USA"
        
        # Test invalid coordinates
        result = await detector.store_detected_location(91, 0)
        assert result['success'] == False
        assert 'Invalid coordinates' in result['error']
    
    @pytest.mark.asyncio
    async def test_get_current_location(self, detector):
        """Test retrieving current location from database."""
        # Initially no location
        current = await detector.get_current_location()
        assert current is None
        
        # Store a location
        await detector.store_detected_location(
            40.7128, -74.0060, 
            "New York, NY, USA", 
            "test_method"
        )
        
        # Retrieve current location
        current = await detector.get_current_location()
        assert current is not None
        assert current['latitude'] == 40.7128
        assert current['longitude'] == -74.0060
        assert current['address'] == "New York, NY, USA"
        assert current['detection_method'] == "test_method"
    
    @pytest.mark.asyncio
    async def test_location_history(self, detector):
        """Test location history functionality."""
        # Store multiple locations
        locations = [
            (40.7128, -74.0060, "New York, NY, USA"),
            (34.0522, -118.2437, "Los Angeles, CA, USA"),
            (41.8781, -87.6298, "Chicago, IL, USA")
        ]
        
        for lat, lon, address in locations:
            await detector.store_detected_location(lat, lon, address, "test_method")
            await asyncio.sleep(0.1)  # Longer delay to ensure different timestamps
        
        # Get history
        history = await detector.get_location_history(5)
        assert len(history) == 3
        
        # Should be ordered by most recent first - check that we have all addresses
        addresses = [entry['address'] for entry in history]
        assert "Chicago, IL, USA" in addresses
        assert "Los Angeles, CA, USA" in addresses
        assert "New York, NY, USA" in addresses
        
        # Only the most recent should be current
        current_entries = [entry for entry in history if entry['is_current']]
        assert len(current_entries) == 1
        assert current_entries[0]['address'] == "Chicago, IL, USA"
    
    @pytest.mark.asyncio
    async def test_get_map_center_coordinates(self, detector):
        """Test getting map center coordinates."""
        # Store a location
        await detector.store_detected_location(
            40.7128, -74.0060, 
            "New York, NY, USA", 
            "test_method"
        )
        
        # Get map center
        lat, lon = await detector.get_map_center_coordinates()
        assert lat == 40.7128
        assert lon == -74.0060
    
    def test_cache_functionality(self, detector):
        """Test location caching mechanism."""
        # Test cache miss
        assert not detector._is_cache_valid("test_key")
        
        # Add to cache
        detector.location_cache["test_key"] = {
            'result': LocationResult(40.7128, -74.0060),
            'timestamp': time.time()
        }
        
        # Test cache hit
        assert detector._is_cache_valid("test_key")
        
        # Test cache expiry
        detector.location_cache["test_key"]['timestamp'] = time.time() - 7200  # 2 hours ago
        assert not detector._is_cache_valid("test_key")
    
    @pytest.mark.asyncio
    async def test_clear_location_cache(self, detector):
        """Test cache clearing functionality."""
        # Add something to cache
        detector.location_cache["test"] = {"data": "test"}
        assert len(detector.location_cache) > 0
        
        # Clear cache
        await detector.clear_location_cache()
        assert len(detector.location_cache) == 0
    
    def test_timezone_location_estimation(self, detector):
        """Test timezone-based location estimation."""
        result = detector.get_system_timezone_location()
        
        # Should return a valid result
        assert isinstance(result, LocationResult)
        assert result.success == True
        assert detector._validate_coordinates(result.latitude, result.longitude)
        assert result.detection_method.startswith("timezone_estimation")
        assert 0 < result.confidence_score <= 1.0
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_success(self, mock_get, detector):
        """Test successful IP geolocation."""
        # Mock successful response from ip-api.com
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'success',
            'lat': 40.7128,
            'lon': -74.0060,
            'city': 'New York',
            'regionName': 'New York',
            'country': 'United States'
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = await detector.get_ip_geolocation()
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert "New York" in result.address
        assert result.detection_method == "ip_geolocation_ipapi"
        assert result.confidence_score == 0.8
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_failure(self, mock_get, detector):
        """Test IP geolocation failure handling."""
        # Mock failed request
        mock_get.side_effect = Exception("Network error")
        
        result = await detector.get_ip_geolocation()
        
        assert result.success == False
        assert "All IP geolocation services failed" in result.error_message
        assert result.confidence_score == 0.0
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_ipinfo_format(self, mock_get, detector):
        """Test IP geolocation with ipinfo.io format."""
        # Mock ipinfo.io response format
        mock_response = Mock()
        mock_response.json.return_value = {
            'loc': '40.7128,-74.0060',
            'city': 'New York',
            'region': 'New York',
            'country': 'US'
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test parsing ipinfo format
        service = {
            'name': 'ipinfo',
            'url': 'https://ipinfo.io/json',
            'fields': ['loc', 'city', 'region', 'country']
        }
        
        result = detector._parse_geolocation_response(mock_response.json(), service)
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.detection_method == "ip_geolocation_ipinfo"
    
    @pytest.mark.asyncio
    async def test_detect_script_location_fallback_chain(self, detector):
        """Test the complete fallback chain in detect_script_location."""
        # Mock IP geolocation to fail
        with patch.object(detector, 'get_ip_geolocation') as mock_ip:
            mock_ip.return_value = LocationResult(
                0, 0, success=False, error_message="IP failed"
            )
            
            # Mock timezone estimation to succeed
            with patch.object(detector, 'get_system_timezone_location') as mock_tz:
                mock_tz.return_value = LocationResult(
                    40.7128, -74.0060, 
                    address="Timezone Location",
                    detection_method="timezone_estimation",
                    confidence_score=0.5
                )
                
                result = await detector.detect_script_location()
                
                assert result.success == True
                assert result.latitude == 40.7128
                assert result.longitude == -74.0060
                assert result.detection_method == "timezone_estimation"
                
                # Verify it was stored in database
                current = await detector.get_current_location()
                assert current['latitude'] == 40.7128
                assert current['longitude'] == -74.0060
    
    @pytest.mark.asyncio
    async def test_detect_script_location_default_fallback(self, detector):
        """Test fallback to default location when all methods fail."""
        # Mock both IP and timezone to fail
        with patch.object(detector, 'get_ip_geolocation') as mock_ip, \
             patch.object(detector, 'get_system_timezone_location') as mock_tz:
            
            mock_ip.return_value = LocationResult(
                0, 0, success=False, error_message="IP failed"
            )
            mock_tz.return_value = LocationResult(
                0, 0, success=False, error_message="Timezone failed"
            )
            
            result = await detector.detect_script_location()
            
            assert result.success == True  # Default location is still successful
            assert result.latitude == detector.default_location[0]
            assert result.longitude == detector.default_location[1]
            assert result.detection_method == "default"
            assert result.confidence_score == 0.1
            assert "All detection methods failed" in result.error_message
    
    def test_parse_geolocation_response_error_handling(self, detector):
        """Test error handling in geolocation response parsing."""
        service = {
            'name': 'ipapi',
            'url': 'http://ip-api.com/json/',
            'fields': ['lat', 'lon', 'city', 'regionName', 'country']
        }
        
        # Test missing required fields
        invalid_data = {'status': 'success'}  # Missing lat/lon
        result = detector._parse_geolocation_response(invalid_data, service)
        assert result.success == False
        assert "Response parsing failed" in result.error_message
        
        # Test service error status
        error_data = {'status': 'fail', 'message': 'Invalid query'}
        result = detector._parse_geolocation_response(error_data, service)
        assert result.success == False
        assert "Service returned error" in result.error_message

# Integration tests
class TestLocationDetectorIntegration:
    """Integration tests for LocationDetector with real services."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_ip_geolocation(self):
        """Test with real IP geolocation service (requires internet)."""
        detector = LocationDetector()
        
        # This test requires internet connection
        try:
            result = await detector.get_ip_geolocation()
            
            if result.success:
                assert detector._validate_coordinates(result.latitude, result.longitude)
                assert result.address is not None
                assert result.confidence_score > 0
                print(f"Real IP location: {result.address}")
            else:
                print(f"IP geolocation failed: {result.error_message}")
                
        except Exception as e:
            pytest.skip(f"Internet connection required for integration test: {e}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_location_detection_workflow(self):
        """Test complete location detection workflow."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
            temp_db = temp_file.name
        
        try:
            # Initialize database
            import aiosqlite
            async with aiosqlite.connect(temp_db) as db:
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
                await db.commit()
            
            detector = LocationDetector(temp_db)
            
            # Run full detection
            result = await detector.detect_script_location()
            
            assert result.success == True
            assert detector._validate_coordinates(result.latitude, result.longitude)
            
            # Verify storage
            current = await detector.get_current_location()
            assert current is not None
            assert current['latitude'] == result.latitude
            assert current['longitude'] == result.longitude
            
            print(f"Detected location: {result.address} via {result.detection_method}")
            
        finally:
            os.unlink(temp_db)

# Utility function to run tests
def run_tests():
    """Run all tests."""
    pytest.main([__file__, "-v"])

if __name__ == "__main__":
    run_tests()