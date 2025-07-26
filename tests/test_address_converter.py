"""
Tests for AddressConverter class

This module contains comprehensive tests for the address conversion service,
including geocoding, caching, validation, and batch processing functionality.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from src.address_converter import AddressConverter, GeocodeResult, CacheEntry


class TestAddressConverter:
    """Test cases for AddressConverter class"""
    
    @pytest.fixture
    def converter(self):
        """Create AddressConverter instance for testing"""
        return AddressConverter(cache_timeout=60)
    
    @pytest.fixture
    def mock_geocoder(self):
        """Create mock geocoder for testing"""
        mock = Mock()
        mock.geocode = Mock()
        mock.reverse = Mock()
        return mock
    
    def test_init(self):
        """Test AddressConverter initialization"""
        converter = AddressConverter(cache_timeout=3600)
        assert converter.cache_timeout == 3600
        assert isinstance(converter.geocoding_cache, dict)
        assert isinstance(converter.reverse_cache, dict)
        assert len(converter.geocoding_cache) == 0
        assert len(converter.reverse_cache) == 0
    
    def test_validate_address_format_valid(self, converter):
        """Test address format validation with valid addresses"""
        valid_addresses = [
            "123 Main Street, New York, NY",
            "1600 Pennsylvania Avenue, Washington, DC",
            "Times Square, New York",
            "Central Park, Manhattan",
            "Golden Gate Bridge, San Francisco, CA"
        ]
        
        for address in valid_addresses:
            assert converter.validate_address_format(address) == True
    
    def test_validate_address_format_invalid(self, converter):
        """Test address format validation with invalid addresses"""
        invalid_addresses = [
            "",  # Empty string
            None,  # None value
            "   ",  # Only whitespace
            "123",  # Only numbers
            "A",  # Single letter
            "!@#$%",  # Only special characters
            "ab",  # Too short
        ]
        
        for address in invalid_addresses:
            assert converter.validate_address_format(address) == False
    
    def test_normalize_address(self, converter):
        """Test address normalization"""
        test_cases = [
            ("123 Main Street", "123 main street"),
            ("  123   Main   Street  ", "123 main street"),
            ("123 Main St., New York", "123 main st new york"),
            ("123 Main St. Suite 100", "123 main st suite 100"),
            ("UPPER CASE ADDRESS", "upper case address"),
        ]
        
        for input_addr, expected in test_cases:
            result = converter._normalize_address(input_addr)
            assert result == expected
    
    def test_get_cache_key(self, converter):
        """Test cache key generation"""
        address = "123 Main Street, New York"
        key = converter._get_cache_key(address)
        assert key == "123 main street new york"
        
        # Same address should generate same key
        key2 = converter._get_cache_key("  123   Main   Street,   New York  ")
        assert key == key2
    
    def test_get_reverse_cache_key(self, converter):
        """Test reverse geocoding cache key generation"""
        lat, lon = 40.7128, -74.0060
        key = converter._get_reverse_cache_key(lat, lon)
        assert key == "40.712800,-74.006000"
        
        # Test rounding
        key2 = converter._get_reverse_cache_key(40.7128001, -74.0060001)
        assert key2 == "40.712800,-74.006000"
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_invalid_format(self, converter):
        """Test address to coordinates with invalid format"""
        result = await converter.address_to_coordinates("")
        assert result['success'] == False
        assert result['error'] == 'Invalid address format'
        assert result['latitude'] is None
        assert result['longitude'] is None
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_fallback(self, converter):
        """Test address to coordinates with fallback geocoding"""
        # Force fallback mode
        converter.geopy_available = False
        converter.geocoder = None
        
        result = await converter.address_to_coordinates("123 Main Street")
        assert result['success'] == True
        assert result['latitude'] == 40.7128
        assert result['longitude'] == -74.0060
        assert 'Fallback location' in result['formatted_address']
        assert result['confidence'] == 0.1
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_with_geopy(self, converter):
        """Test address to coordinates with geopy"""
        # Setup mock
        mock_location = Mock()
        mock_location.latitude = 40.7589
        mock_location.longitude = -73.9851
        mock_location.address = "Times Square, Manhattan, NY, USA"
        
        mock_geocoder = Mock()
        mock_geocoder.geocode.return_value = mock_location
        
        # Force geopy mode
        converter.geopy_available = True
        converter.geocoder = mock_geocoder
        
        result = await converter.address_to_coordinates("Times Square, New York")
        
        assert result['success'] == True
        assert result['latitude'] == 40.7589
        assert result['longitude'] == -73.9851
        assert result['formatted_address'] == "Times Square, Manhattan, NY, USA"
        assert result['confidence'] == 1.0
    
    @pytest.mark.asyncio
    async def test_address_to_coordinates_caching(self, converter):
        """Test address to coordinates caching"""
        # Force fallback mode for consistent results
        converter.geopy_available = False
        converter.geocoder = None
        
        address = "123 Test Street"
        
        # First call
        result1 = await converter.address_to_coordinates(address)
        assert result1['success'] == True
        assert result1['cached'] == False
        
        # Second call should be cached
        result2 = await converter.address_to_coordinates(address)
        assert result2['success'] == True
        assert result2['cached'] == True
        assert result2['latitude'] == result1['latitude']
        assert result2['longitude'] == result1['longitude']
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_invalid(self, converter):
        """Test coordinates to address with invalid coordinates"""
        # Invalid latitude
        result = await converter.coordinates_to_address(91.0, 0.0)
        assert result['success'] == False
        assert result['error'] == 'Invalid coordinates'
        
        # Invalid longitude
        result = await converter.coordinates_to_address(0.0, 181.0)
        assert result['success'] == False
        assert result['error'] == 'Invalid coordinates'
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_fallback(self, converter):
        """Test coordinates to address with fallback"""
        # Force fallback mode
        converter.geopy_available = False
        converter.geocoder = None
        
        result = await converter.coordinates_to_address(40.7128, -74.0060)
        assert result['success'] == True
        assert 'Fallback address' in result['address']
        assert '40.7128' in result['address']
        assert '-74.0060' in result['address']
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_with_geopy(self, converter):
        """Test coordinates to address with geopy"""
        # Setup mock
        mock_location = Mock()
        mock_location.address = "Times Square, Manhattan, NY, USA"
        
        mock_geocoder = Mock()
        mock_geocoder.reverse.return_value = mock_location
        
        # Force geopy mode
        converter.geopy_available = True
        converter.geocoder = mock_geocoder
        
        result = await converter.coordinates_to_address(40.7589, -73.9851)
        
        assert result['success'] == True
        assert result['address'] == "Times Square, Manhattan, NY, USA"
    
    @pytest.mark.asyncio
    async def test_coordinates_to_address_caching(self, converter):
        """Test coordinates to address caching"""
        # Force fallback mode for consistent results
        converter.geopy_available = False
        converter.geocoder = None
        
        lat, lon = 40.7128, -74.0060
        
        # First call
        result1 = await converter.coordinates_to_address(lat, lon)
        assert result1['success'] == True
        assert result1['cached'] == False
        
        # Second call should be cached
        result2 = await converter.coordinates_to_address(lat, lon)
        assert result2['success'] == True
        assert result2['cached'] == True
        assert result2['address'] == result1['address']
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses_empty(self, converter):
        """Test batch geocoding with empty list"""
        result = await converter.batch_geocode_addresses([])
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses(self, converter):
        """Test batch geocoding functionality"""
        # Force fallback mode for consistent results
        converter.geopy_available = False
        converter.geocoder = None
        
        addresses = [
            "123 Main Street",
            "456 Oak Avenue",
            "789 Pine Road"
        ]
        
        results = await converter.batch_geocode_addresses(addresses)
        
        assert len(results) == 3
        for address in addresses:
            assert address in results
            assert results[address]['success'] == True
            assert results[address]['latitude'] is not None
            assert results[address]['longitude'] is not None
    
    @pytest.mark.asyncio
    async def test_batch_geocode_addresses_with_invalid(self, converter):
        """Test batch geocoding with some invalid addresses"""
        addresses = [
            "123 Main Street",  # Valid
            "",  # Invalid
            "456 Oak Avenue",  # Valid
            None,  # Invalid
            "   ",  # Invalid
        ]
        
        results = await converter.batch_geocode_addresses(addresses)
        
        # Should only process valid addresses
        assert len(results) == 2
        assert "123 Main Street" in results
        assert "456 Oak Avenue" in results
    
    def test_clear_cache(self, converter):
        """Test cache clearing"""
        # Add some cache entries
        converter.geocoding_cache["test"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=time.time()
        )
        converter.reverse_cache["test"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=time.time()
        )
        
        assert len(converter.geocoding_cache) == 1
        assert len(converter.reverse_cache) == 1
        
        converter.clear_cache()
        
        assert len(converter.geocoding_cache) == 0
        assert len(converter.reverse_cache) == 0
    
    def test_get_cache_stats(self, converter):
        """Test cache statistics"""
        # Add some cache entries
        current_time = time.time()
        
        # Valid entry
        converter.geocoding_cache["valid"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time
        )
        
        # Expired entry
        converter.geocoding_cache["expired"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time - 3700  # Older than 1 hour
        )
        
        converter.reverse_cache["valid"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time
        )
        
        stats = converter.get_cache_stats()
        
        assert stats['geocoding_cache_size'] == 2
        assert stats['reverse_cache_size'] == 1
        assert stats['valid_geocoding_entries'] == 1  # Only one non-expired
        assert stats['valid_reverse_entries'] == 1
        assert stats['cache_timeout'] == converter.cache_timeout
    
    def test_cleanup_expired_cache(self, converter):
        """Test expired cache cleanup"""
        current_time = time.time()
        
        # Add valid and expired entries
        converter.geocoding_cache["valid"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time
        )
        
        converter.geocoding_cache["expired1"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time - 3700
        )
        
        converter.reverse_cache["expired2"] = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time - 3700
        )
        
        assert len(converter.geocoding_cache) == 2
        assert len(converter.reverse_cache) == 1
        
        removed_count = converter.cleanup_expired_cache()
        
        assert removed_count == 2
        assert len(converter.geocoding_cache) == 1
        assert len(converter.reverse_cache) == 0
        assert "valid" in converter.geocoding_cache
    
    def test_cache_entry_expiration(self):
        """Test CacheEntry expiration logic"""
        current_time = time.time()
        
        # Fresh entry
        fresh_entry = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time
        )
        assert not fresh_entry.is_expired(3600)
        
        # Expired entry
        expired_entry = CacheEntry(
            result=GeocodeResult(success=True),
            timestamp=current_time - 3700
        )
        assert expired_entry.is_expired(3600)
    
    def test_geocode_result_dataclass(self):
        """Test GeocodeResult dataclass"""
        # Success result
        success_result = GeocodeResult(
            success=True,
            latitude=40.7128,
            longitude=-74.0060,
            formatted_address="New York, NY, USA",
            confidence=1.0
        )
        
        assert success_result.success == True
        assert success_result.latitude == 40.7128
        assert success_result.longitude == -74.0060
        assert success_result.formatted_address == "New York, NY, USA"
        assert success_result.confidence == 1.0
        assert success_result.error_message is None
        
        # Error result
        error_result = GeocodeResult(
            success=False,
            error_message="Service unavailable"
        )
        
        assert error_result.success == False
        assert error_result.error_message == "Service unavailable"
        assert error_result.latitude is None
        assert error_result.longitude is None


if __name__ == "__main__":
    pytest.main([__file__])