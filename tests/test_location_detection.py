#!/usr/bin/env python3
"""
Unit Tests for Location Detection Service

This module tests the LocationDetector class with mocked geolocation services
to ensure reliable location detection functionality.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import tempfile
import os

# Import the module to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.location_detector import LocationDetector, LocationResult


class TestLocationDetector:
    """Test suite for LocationDetector class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        yield temp_file.name
        os.unlink(temp_file.name)
    
    @pytest.fixture
    def detector(self, temp_db):
        """Create a LocationDetector instance with temporary database."""
        return LocationDetector(temp_db)
    
    def test_init(self, detector):
        """Test LocationDetector initialization."""
        assert detector.db_path is not None
        assert detector.default_location == (40.7128, -74.0060)
        assert detector.cache_timeout == 3600
        assert len(detector.geolocation_services) > 0
    
    def test_validate_coordinates_valid(self, detector):
        """Test coordinate validation with valid coordinates."""
        assert detector._validate_coordinates(40.7128, -74.0060) == True
        assert detector._validate_coordinates(-90, -180) == True
        assert detector._validate_coordinates(90, 180) == True
        assert detector._validate_coordinates(0, 0) == True
    
    def test_validate_coordinates_invalid(self, detector):
        """Test coordinate validation with invalid coordinates."""
        assert detector._validate_coordinates(91, 0) == False
        assert detector._validate_coordinates(-91, 0) == False
        assert detector._validate_coordinates(0, 181) == False
        assert detector._validate_coordinates(0, -181) == False
        assert detector._validate_coordinates("invalid", 0) == False
        assert detector._validate_coordinates(0, "invalid") == False
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_success_ipapi(self, mock_get, detector):
        """Test successful IP geolocation using ip-api service."""
        # Mock successful response from ip-api
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'status': 'success',
            'lat': 40.7128,
            'lon': -74.0060,
            'city': 'New York',
            'regionName': 'New York',
            'country': 'United States'
        }
        mock_get.return_value = mock_response
        
        result = await detector.get_ip_geolocation()
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert 'New York' in result.address
        assert result.detection_method == 'ip_geolocation_ipapi'
        assert result.confidence_score == 0.8
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_success_ipinfo(self, mock_get, detector):
        """Test successful IP geolocation using ipinfo service."""
        # Mock failed first service, successful second service
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = Exception("Service unavailable")
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.json.return_value = {
            'loc': '40.7128,-74.0060',
            'city': 'New York',
            'region': 'NY',
            'country': 'US'
        }
        
        mock_get.side_effect = [mock_response_fail, mock_response_success]
        
        result = await detector.get_ip_geolocation()
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.detection_method == 'ip_geolocation_ipinfo'
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_ip_geolocation_all_services_fail(self, mock_get, detector):
        """Test IP geolocation when all services fail."""
        # Mock all services failing
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("Service unavailable")
        mock_get.return_value = mock_response
        
        result = await detector.get_ip_geolocation()
        
        assert result.success == False
        assert result.error_message == "All IP geolocation services failed"
        assert result.detection_method == "ip_geolocation"
    
    def test_system_timezone_location(self, detector):
        """Test system timezone-based location estimation."""
        result = detector.get_system_timezone_location()
        
        assert isinstance(result, LocationResult)
        assert result.latitude != 0 or result.longitude != 0  # Should have some location
        assert result.detection_method.startswith('timezone_estimation')
        assert result.confidence_score <= 0.8  # Timezone is less accurate
    
    @pytest.mark.asyncio
    async def test_detect_script_location_success(self, detector):
        """Test successful script location detection."""
        # Mock successful IP geolocation
        with patch.object(detector, 'get_ip_geolocation') as mock_ip:
            mock_ip.return_value = LocationResult(
                latitude=40.7128,
                longitude=-74.0060,
                address="New York, NY, USA",
                detection_method="ip_geolocation_ipapi",
                confidence_score=0.8,
                success=True
            )
            
            with patch.object(detector, 'store_detected_location') as mock_store:
                mock_store.return_value = {'success': True, 'location_id': 1}
                
                result = await detector.detect_script_location()
                
                assert result.success == True
                assert result.latitude == 40.7128
                assert result.longitude == -74.0060
                assert result.detection_method == "ip_geolocation_ipapi"
                mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_script_location_fallback_to_timezone(self, detector):
        """Test script location detection falling back to timezone."""
        # Mock failed IP geolocation
        with patch.object(detector, 'get_ip_geolocation') as mock_ip:
            mock_ip.return_value = LocationResult(
                latitude=0.0,
                longitude=0.0,
                detection_method="ip_geolocation",
                success=False,
                error_message="All services failed"
            )
            
            # Mock successful timezone detection
            with patch.object(detector, 'get_system_timezone_location') as mock_tz:
                mock_tz.return_value = LocationResult(
                    latitude=51.5074,
                    longitude=-0.1278,
                    address="London, UK (Timezone Estimate)",
                    detection_method="timezone_estimation",
                    confidence_score=0.5,
                    success=True
                )
                
                with patch.object(detector, 'store_detected_location') as mock_store:
                    mock_store.return_value = {'success': True, 'location_id': 1}
                    
                    result = await detector.detect_script_location()
                    
                    assert result.success == True
                    assert result.latitude == 51.5074
                    assert result.longitude == -0.1278
                    assert result.detection_method == "timezone_estimation"
    
    @pytest.mark.asyncio
    async def test_detect_script_location_default_fallback(self, detector):
        """Test script location detection falling back to default location."""
        # Mock both IP and timezone detection failing
        with patch.object(detector, 'get_ip_geolocation') as mock_ip:
            mock_ip.return_value = LocationResult(
                latitude=0.0,
                longitude=0.0,
                detection_method="ip_geolocation",
                success=False,
                error_message="All services failed"
            )
            
            with patch.object(detector, 'get_system_timezone_location') as mock_tz:
                mock_tz.return_value = LocationResult(
                    latitude=0.0,
                    longitude=0.0,
                    detection_method="timezone_estimation",
                    success=False,
                    error_message="Timezone detection failed"
                )
                
                with patch.object(detector, 'store_detected_location') as mock_store:
                    mock_store.return_value = {'success': True, 'location_id': 1}
                    
                    result = await detector.detect_script_location()
                    
                    assert result.latitude == 40.7128  # Default NYC
                    assert result.longitude == -74.0060
                    assert result.detection_method == "default"
                    assert result.error_message == "All detection methods failed"
    
    def test_parse_geolocation_response_ipapi(self, detector):
        """Test parsing ip-api response format."""
        service = {'name': 'ipapi'}
        data = {
            'status': 'success',
            'lat': 40.7128,
            'lon': -74.0060,
            'city': 'New York',
            'regionName': 'New York',
            'country': 'United States'
        }
        
        result = detector._parse_geolocation_response(data, service)
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert 'New York' in result.address
    
    def test_parse_geolocation_response_ipinfo(self, detector):
        """Test parsing ipinfo response format."""
        service = {'name': 'ipinfo'}
        data = {
            'loc': '40.7128,-74.0060',
            'city': 'New York',
            'region': 'NY',
            'country': 'US'
        }
        
        result = detector._parse_geolocation_response(data, service)
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert 'New York' in result.address
    
    def test_parse_geolocation_response_invalid(self, detector):
        """Test parsing invalid response format."""
        service = {'name': 'ipapi'}
        data = {'status': 'fail', 'message': 'Invalid query'}
        
        result = detector._parse_geolocation_response(data, service)
        
        assert result.success == False
        assert 'Invalid query' in result.error_message
    
    def test_cache_functionality(self, detector):
        """Test location detection caching."""
        # Test cache miss
        assert not detector._is_cache_valid('test_key')
        
        # Add to cache
        test_result = LocationResult(
            latitude=40.7128,
            longitude=-74.0060,
            success=True
        )
        detector.location_cache['test_key'] = {
            'result': test_result,
            'timestamp': time.time()
        }
        
        # Test cache hit
        assert detector._is_cache_valid('test_key')
        
        # Test cache expiry
        detector.location_cache['test_key']['timestamp'] = time.time() - 7200  # 2 hours ago
        assert not detector._is_cache_valid('test_key')
    
    @pytest.mark.asyncio
    async def test_clear_location_cache(self, detector):
        """Test clearing location cache."""
        # Add some cache entries
        detector.location_cache['test1'] = {'result': Mock(), 'timestamp': time.time()}
        detector.location_cache['test2'] = {'result': Mock(), 'timestamp': time.time()}
        
        assert len(detector.location_cache) == 2
        
        await detector.clear_location_cache()
        
        assert len(detector.location_cache) == 0


class TestLocationResult:
    """Test suite for LocationResult dataclass."""
    
    def test_location_result_creation(self):
        """Test LocationResult creation with all fields."""
        result = LocationResult(
            latitude=40.7128,
            longitude=-74.0060,
            address="New York, NY, USA",
            detection_method="ip_geolocation",
            confidence_score=0.8,
            error_message=None,
            success=True
        )
        
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.address == "New York, NY, USA"
        assert result.detection_method == "ip_geolocation"
        assert result.confidence_score == 0.8
        assert result.success == True
    
    def test_location_result_defaults(self):
        """Test LocationResult creation with default values."""
        result = LocationResult(
            latitude=40.7128,
            longitude=-74.0060
        )
        
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.address is None
        assert result.detection_method == "unknown"
        assert result.confidence_score == 1.0
        assert result.error_message is None
        assert result.success == True


if __name__ == '__main__':
    # Run tests if script is executed directly
    pytest.main([__file__, '-v'])