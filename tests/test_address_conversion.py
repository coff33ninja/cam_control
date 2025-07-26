#!/usr/bin/env python3
"""
Unit Tests for Address Conversion Service

This module tests the AddressConverter class including geocoding functionality,
caching behavior, and batch processing capabilities.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import os

# Import the module to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.address_converter import AddressConverter, GeocodeResult, CacheEntry


class TestAddressConverter:
    """Test suite for AddressConverter class."""
    
    @pytest.fixture
    def converter(self):
        """Create an AddressConverter instance for testing."""
        return AddressConverter(cache_timeout=300)  # 5 minutes for testing
    
    def test_init(self, converter):
        """Test AddressConverter initialization."""
        assert converter.cache_timeout == 300
        assert isinstance(converter.geocoding_cache, dict)
        assert isinstance(converter.reverse_cache, dict)
        assert len(converter.geocoding_cache) == 0
        assert len(converter.reverse_cache) == 0
    
    def test_validate_address_format_valid(self, converter):
        """Test address format validation with valid addresses."""
        valid_addresses = [
            "123 Main Street, New York, NY 10001",
            "1600 Pennsylvania Avenue, Washington, DC",
            "Times Square, New York",
            "Central Park, Manhattan, NY",
            "Golden Gate Bridge, San Francisco, CA"
        ]
        
        for address in valid_addresses:
            assert converter.validate_address_format(address) == True
    
    def test_validate_address_format_invalid(self, converter):
        """Test address format validation with invalid addresses."""
        invalid_addresses = [
            "",  # Empty string
            "   ",  # Only whitespace
            "123",  # Too short
            "!@#$%",  # Only special characters
            "12345",  # Only numbers
            "a",  # Single character
            None,  # None value
            123,  # Non-string type
        ]
        
        for address in invalid_addresses:
            assert converter.validate_address_format(address) == False
    
    def test_normalize_address(self, converter):
        """Test address normalization."""
        test_cases = [
            ("123 Main Street, New York, NY", "123 main street new york ny"),
            ("  TIMES   SQUARE  ", "times square"),
            ("Central.Park,Manhattan", "central park manhattan"),
            ("Golden Gate Bridge", "golden gate bridge"),
        ]
        
        for input_addr, expected in test_cases:
            result = converter._normalize_address(input_addr)
            assert result == expected
    
    def test_get_cache_key(self, converter):
        """Test cache key generation."""
        address = "123 Main Street, New York, NY"
        expected = "123 main street new york ny"
        
        result = converter._get_cache_key(address)
        assert result == expected
    
    def test_get_reverse_cache_key(self, converter):
        """Test reverse geocoding cache key generation."""
        lat, lon = 40.712800, -74.006000
        expected = "40.712800,-74.006000"
        
        result = converter._get_reverse_cache_key(lat, lon)
        assert result == expected
    
    @patch('src.address_converter.requests.get')
    @pytest.mark.asyncio
    async def test_address_to_coordinates_success(self, mock_get, converter):
        """Test successful address to coordinates conversion."""
        # Mock successful geocoding response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'lat': 40.7128,
            'lon': -74.0060,
            'city': 'New York',
            'regionName': 'New York',
            'country': 'United States'
        }
        mock_get.return_value = mock_response
        
        # Mock geopy availability
        with patch.object(converter, 'geopy_available', True):
            with patch.object(converter, 'geocoder') as mock_geocoder:
                mock_location = Mock()
                mock_location.latitude = 40.7128
                mock_location.longitude = -74.0060
                mock_location.address = "New York, NY, USA"
                mock_geocoder.geocode.return_value = mock_location
                
                result = await converter.address_to_coordinates("New York, NY")
                
                assert result['success'] == True
                assert result['latitude'] == 40.7128
                assert result['longitude'] == -74.0060
                assert result['formatted_address'] == "New York, NY, USA"
                assert result['cached'] == False
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_cached(self, converter):
        """Test cached address to coordinates conversion."""
        address = "New York, NY"
        cache_key = converter._get_cache_key(address)
        
        # Add to cache
        cached_result = GeocodeResult(
            success=True,
            latitude=40.7128,
            longitude=-74.0060,
            formatted_address="New York, NY, USA",
            confidence=1.0
        )
        converter.geocoding_cache[cache_key] = CacheEntry(
            result=cached_result,
            timestamp=time.time()
        )
        
        result = await converter.address_to_coordinates(address)
        
        assert result['success'] == True
        assert result['latitude'] == 40.7128
        assert result['longitude'] == -74.0060
        assert result['cached'] == True
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_invalid_format(self, converter):
        """Test address to coordinates with invalid format."""
        result = await converter.address_to_coordinates("")
        
        assert result['success'] == False
        assert result['error'] == 'Invalid address format'
        assert result['latitude'] is None
        assert result['longitude'] is None
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_fallback(self, converter):
        """Test address to coordinates with fallback implementation."""
        # Mock geopy not available
        with patch.object(converter, 'geopy_available', False):
            result = await converter.address_to_coordinates("New York, NY")
            
            assert result['success'] == True
            assert result['latitude'] == 40.7128  # Fallback coordinates
            assert result['longitude'] == -74.0060
            assert 'Fallback location' in result['formatted_address']
            assert result['confidence'] == 0.1
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_success(self, converter):
        """Test successful coordinates to address conversion."""
        with patch.object(converter, 'geopy_available', True):
            with patch.object(converter, 'geocoder') as mock_geocoder:
                mock_location = Mock()
                mock_location.address = "New York, NY, USA"
                mock_geocoder.reverse.return_value = mock_location
                
                result = await converter.coordinates_to_address(40.7128, -74.0060)
                
                assert result['success'] == True
                assert result['address'] == "New York, NY, USA"
                assert result['cached'] == False
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_invalid_coordinates(self, converter):
        """Test coordinates to address with invalid coordinates."""
        result = await converter.coordinates_to_address(91, 0)  # Invalid latitude
        
        assert result['success'] == False
        assert result['error'] == 'Invalid coordinates'
        assert result['address'] is None
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_cached(self, converter):
        """Test cached coordinates to address conversion."""
        lat, lon = 40.7128, -74.0060
        cache_key = converter._get_reverse_cache_key(lat, lon)
        
        # Add to cache
        cached_result = GeocodeResult(
            success=True,
            formatted_address="New York, NY, USA"
        )
        converter.reverse_cache[cache_key] = CacheEntry(
            result=cached_result,
            timestamp=time.time()
        )
        
        result = await converter.coordinates_to_address(lat, lon)
        
        assert result['success'] == True
        assert result['address'] == "New York, NY, USA"
        assert result['cached'] == True
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_fallback(self, converter):
        """Test coordinates to address with fallback implementation."""
        with patch.object(converter, 'geopy_available', False):
            result = await converter.coordinates_to_address(40.7128, -74.0060)
            
            assert result['success'] == True
            assert 'Fallback address' in result['address']
            assert result['cached'] == False
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses(self, converter):
        """Test batch geocoding of multiple addresses."""
        addresses = [
            "New York, NY",
            "Los Angeles, CA",
            "Chicago, IL"
        ]
        
        # Mock successful geocoding for all addresses
        with patch.object(converter, 'address_to_coordinates') as mock_geocode:
            mock_geocode.side_effect = [
                {'success': True, 'latitude': 40.7128, 'longitude': -74.0060},
                {'success': True, 'latitude': 34.0522, 'longitude': -118.2437},
                {'success': True, 'latitude': 41.8781, 'longitude': -87.6298}
            ]
            
            results = await converter.batch_geocode_addresses(addresses)
            
            assert len(results) == 3
            assert all(addr in results for addr in addresses)
            assert all(results[addr]['success'] for addr in addresses)
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses_empty(self, converter):
        """Test batch geocoding with empty address list."""
        result = await converter.batch_geocode_addresses([])
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses_with_errors(self, converter):
        """Test batch geocoding with some addresses failing."""
        addresses = ["Valid Address", ""]
        
        with patch.object(converter, 'address_to_coordinates') as mock_geocode:
            mock_geocode.side_effect = [
                {'success': True, 'latitude': 40.7128, 'longitude': -74.0060},
                {'success': False, 'error': 'Invalid address format'}
            ]
            
            results = await converter.batch_geocode_addresses(addresses)
            
            assert len(results) == 1  # Empty address should be filtered out
            assert "Valid Address" in results
            assert results["Valid Address"]['success'] == True
    
    def test_clear_cache(self, converter):
        """Test clearing geocoding cache."""
        # Add some cache entries
        converter.geocoding_cache['test1'] = CacheEntry(Mock(), time.time())
        converter.reverse_cache['test2'] = CacheEntry(Mock(), time.time())
        
        assert len(converter.geocoding_cache) == 1
        assert len(converter.reverse_cache) == 1
        
        converter.clear_cache()
        
        assert len(converter.geocoding_cache) == 0
        assert len(converter.reverse_cache) == 0
    
    def test_get_cache_stats(self, converter):
        """Test getting cache statistics."""
        # Add some cache entries
        current_time = time.time()
        converter.geocoding_cache['valid1'] = CacheEntry(Mock(), current_time)
        converter.geocoding_cache['expired1'] = CacheEntry(Mock(), current_time - 7200)  # 2 hours ago
        converter.reverse_cache['valid2'] = CacheEntry(Mock(), current_time)
        
        stats = converter.get_cache_stats()
        
        assert stats['geocoding_cache_size'] == 2
        assert stats['reverse_cache_size'] == 1
        assert stats['valid_geocoding_entries'] == 1  # Only one valid entry
        assert stats['valid_reverse_entries'] == 1
        assert stats['cache_timeout'] == 300
    
    def test_cleanup_expired_cache(self, converter):
        """Test cleaning up expired cache entries."""
        current_time = time.time()
        
        # Add valid and expired entries
        converter.geocoding_cache['valid'] = CacheEntry(Mock(), current_time)
        converter.geocoding_cache['expired'] = CacheEntry(Mock(), current_time - 7200)
        converter.reverse_cache['expired2'] = CacheEntry(Mock(), current_time - 7200)
        
        removed_count = converter.cleanup_expired_cache()
        
        assert removed_count == 2  # Two expired entries removed
        assert len(converter.geocoding_cache) == 1  # Only valid entry remains
        assert len(converter.reverse_cache) == 0
        assert 'valid' in converter.geocoding_cache


class TestGeocodeResult:
    """Test suite for GeocodeResult dataclass."""
    
    def test_geocode_result_creation(self):
        """Test GeocodeResult creation with all fields."""
        result = GeocodeResult(
            success=True,
            latitude=40.7128,
            longitude=-74.0060,
            formatted_address="New York, NY, USA",
            error_message=None,
            confidence=0.8
        )
        
        assert result.success == True
        assert result.latitude == 40.7128
        assert result.longitude == -74.0060
        assert result.formatted_address == "New York, NY, USA"
        assert result.confidence == 0.8
    
    def test_geocode_result_defaults(self):
        """Test GeocodeResult creation with default values."""
        result = GeocodeResult(success=True)
        
        assert result.success == True
        assert result.latitude is None
        assert result.longitude is None
        assert result.formatted_address is None
        assert result.error_message is None
        assert result.confidence is None


class TestCacheEntry:
    """Test suite for CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation."""
        result = GeocodeResult(success=True)
        timestamp = time.time()
        
        entry = CacheEntry(result=result, timestamp=timestamp)
        
        assert entry.result == result
        assert entry.timestamp == timestamp
    
    def test_cache_entry_is_expired(self):
        """Test cache entry expiration checking."""
        result = GeocodeResult(success=True)
        
        # Fresh entry
        fresh_entry = CacheEntry(result=result, timestamp=time.time())
        assert not fresh_entry.is_expired(3600)  # 1 hour timeout
        
        # Expired entry
        expired_entry = CacheEntry(result=result, timestamp=time.time() - 7200)  # 2 hours ago
        assert expired_entry.is_expired(3600)  # 1 hour timeout


if __name__ == '__main__':
    # Run tests if script is executed directly
    pytest.main([__file__, '-v'])