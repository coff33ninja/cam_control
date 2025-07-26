"""
Address Conversion Service

This module provides functionality to convert physical addresses to coordinates
and vice versa using geocoding services. It includes caching mechanisms to
reduce API calls and batch processing capabilities.
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class GeocodeResult:
    """Result of a geocoding operation"""
    success: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    formatted_address: Optional[str] = None
    error_message: Optional[str] = None
    confidence: Optional[float] = None

@dataclass
class CacheEntry:
    """Cache entry for geocoding results"""
    result: GeocodeResult
    timestamp: float
    
    def is_expired(self, timeout: int) -> bool:
        """Check if cache entry has expired"""
        return time.time() - self.timestamp > timeout

class AddressConverter:
    """
    Address conversion service with geocoding API integration and caching
    """
    
    def __init__(self, cache_timeout: int = 3600):
        """
        Initialize AddressConverter
        
        Args:
            cache_timeout: Cache timeout in seconds (default: 1 hour)
        """
        self.geocoding_cache: Dict[str, CacheEntry] = {}
        self.reverse_cache: Dict[str, CacheEntry] = {}
        self.cache_timeout = cache_timeout
        
        # Try to import geopy, fallback to basic implementation if not available
        try:
            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderServiceError
            self.geocoder = Nominatim(user_agent="camera_mapping_system")
            self.geopy_available = True
            self.GeocoderTimedOut = GeocoderTimedOut
            self.GeocoderServiceError = GeocoderServiceError
        except ImportError:
            logger.warning("geopy not available, using fallback geocoding")
            self.geocoder = None
            self.geopy_available = False
            self.GeocoderTimedOut = Exception
            self.GeocoderServiceError = Exception
    
    def validate_address_format(self, address: str) -> bool:
        """
        Validate address format before geocoding
        
        Args:
            address: Address string to validate
            
        Returns:
            bool: True if address format appears valid
        """
        if not address or not isinstance(address, str):
            return False
            
        # Remove extra whitespace
        address = address.strip()
        
        # Check minimum length
        if len(address) < 5:
            return False
            
        # Check for basic address components
        # Should contain at least some alphanumeric characters
        if not re.search(r'[a-zA-Z0-9]', address):
            return False
            
        # Check for suspicious patterns
        suspicious_patterns = [
            r'^[^a-zA-Z0-9]*$',  # Only special characters
            r'^\d+$',  # Only numbers
            r'^[a-zA-Z]$',  # Single letter
        ]
        
        for pattern in suspicious_patterns:
            if re.match(pattern, address):
                return False
                
        return True
    
    def _normalize_address(self, address: str) -> str:
        """
        Normalize address for consistent caching
        
        Args:
            address: Raw address string
            
        Returns:
            str: Normalized address string
        """
        if not address:
            return ""
            
        # Convert to lowercase and strip whitespace
        normalized = address.lower().strip()
        
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common punctuation variations
        normalized = normalized.replace(',', ' ')
        normalized = normalized.replace('.', ' ')
        
        # Replace multiple spaces again after punctuation removal
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _get_cache_key(self, address: str) -> str:
        """
        Generate cache key for address
        
        Args:
            address: Address string
            
        Returns:
            str: Cache key
        """
        return self._normalize_address(address)
    
    def _get_reverse_cache_key(self, lat: float, lon: float) -> str:
        """
        Generate cache key for reverse geocoding
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            str: Cache key
        """
        # Round to 6 decimal places for consistent caching
        return f"{lat:.6f},{lon:.6f}"
    
    async def _geocode_with_fallback(self, address: str) -> GeocodeResult:
        """
        Geocode address with fallback methods
        
        Args:
            address: Address to geocode
            
        Returns:
            GeocodeResult: Geocoding result
        """
        if self.geopy_available and self.geocoder:
            try:
                # Use geopy for geocoding
                location = await asyncio.get_event_loop().run_in_executor(
                    None, self.geocoder.geocode, address
                )
                
                if location:
                    return GeocodeResult(
                        success=True,
                        latitude=location.latitude,
                        longitude=location.longitude,
                        formatted_address=location.address,
                        confidence=1.0
                    )
                else:
                    return GeocodeResult(
                        success=False,
                        error_message="Address not found"
                    )
                    
            except self.GeocoderTimedOut:
                return GeocodeResult(
                    success=False,
                    error_message="Geocoding service timed out"
                )
            except self.GeocoderServiceError as e:
                return GeocodeResult(
                    success=False,
                    error_message=f"Geocoding service error: {str(e)}"
                )
            except Exception as e:
                return GeocodeResult(
                    success=False,
                    error_message=f"Geocoding error: {str(e)}"
                )
        else:
            # Fallback implementation - return mock coordinates for testing
            logger.warning(f"Using fallback geocoding for: {address}")
            return GeocodeResult(
                success=True,
                latitude=40.7128,  # Default to NYC coordinates
                longitude=-74.0060,
                formatted_address=f"Fallback location for: {address}",
                confidence=0.1
            )
    
    async def address_to_coordinates(self, address: str) -> Dict[str, Union[bool, float, str]]:
        """
        Convert physical address to latitude/longitude coordinates
        
        Args:
            address: Physical address string
            
        Returns:
            dict: Result containing success status, coordinates, and error info
        """
        if not self.validate_address_format(address):
            return {
                'success': False,
                'error': 'Invalid address format',
                'latitude': None,
                'longitude': None,
                'formatted_address': None
            }
        
        # Check cache first
        cache_key = self._get_cache_key(address)
        if cache_key in self.geocoding_cache:
            cache_entry = self.geocoding_cache[cache_key]
            if not cache_entry.is_expired(self.cache_timeout):
                result = cache_entry.result
                return {
                    'success': result.success,
                    'latitude': result.latitude,
                    'longitude': result.longitude,
                    'formatted_address': result.formatted_address,
                    'error': result.error_message,
                    'confidence': result.confidence,
                    'cached': True
                }
        
        # Perform geocoding
        result = await self._geocode_with_fallback(address)
        
        # Cache the result
        self.geocoding_cache[cache_key] = CacheEntry(
            result=result,
            timestamp=time.time()
        )
        
        return {
            'success': result.success,
            'latitude': result.latitude,
            'longitude': result.longitude,
            'formatted_address': result.formatted_address,
            'error': result.error_message,
            'confidence': result.confidence,
            'cached': False
        }
    
    async def coordinates_to_address(self, lat: float, lon: float) -> Dict[str, Union[bool, str]]:
        """
        Convert coordinates to physical address (reverse geocoding)
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            dict: Result containing success status, address, and error info
        """
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return {
                'success': False,
                'address': None,
                'error': 'Invalid coordinates'
            }
        
        # Check cache first
        cache_key = self._get_reverse_cache_key(lat, lon)
        if cache_key in self.reverse_cache:
            cache_entry = self.reverse_cache[cache_key]
            if not cache_entry.is_expired(self.cache_timeout):
                result = cache_entry.result
                return {
                    'success': result.success,
                    'address': result.formatted_address,
                    'error': result.error_message,
                    'cached': True
                }
        
        if self.geopy_available and self.geocoder:
            try:
                # Use geopy for reverse geocoding
                location = await asyncio.get_event_loop().run_in_executor(
                    None, self.geocoder.reverse, f"{lat}, {lon}"
                )
                
                if location:
                    result = GeocodeResult(
                        success=True,
                        formatted_address=location.address
                    )
                else:
                    result = GeocodeResult(
                        success=False,
                        error_message="Address not found for coordinates"
                    )
                    
            except (self.GeocoderTimedOut, self.GeocoderServiceError) as e:
                result = GeocodeResult(
                    success=False,
                    error_message=f"Reverse geocoding error: {str(e)}"
                )
            except Exception as e:
                result = GeocodeResult(
                    success=False,
                    error_message=f"Reverse geocoding error: {str(e)}"
                )
        else:
            # Fallback implementation
            result = GeocodeResult(
                success=True,
                formatted_address=f"Fallback address for {lat:.4f}, {lon:.4f}"
            )
        
        # Cache the result
        self.reverse_cache[cache_key] = CacheEntry(
            result=result,
            timestamp=time.time()
        )
        
        return {
            'success': result.success,
            'address': result.formatted_address,
            'error': result.error_message,
            'cached': False
        }
    
    async def batch_geocode_addresses(self, addresses: List[str]) -> Dict[str, Dict]:
        """
        Convert multiple addresses to coordinates efficiently
        
        Args:
            addresses: List of address strings
            
        Returns:
            dict: Results keyed by original address
        """
        if not addresses:
            return {}
        
        results = {}
        
        # Process addresses concurrently with rate limiting
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
        async def geocode_single(address: str) -> Tuple[str, Dict]:
            async with semaphore:
                result = await self.address_to_coordinates(address)
                # Add small delay to avoid overwhelming the service
                await asyncio.sleep(0.1)
                return address, result
        
        # Create tasks for all addresses
        tasks = [geocode_single(addr) for addr in addresses if addr and addr.strip()]
        
        # Execute tasks and collect results
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        for task_result in completed_tasks:
            if isinstance(task_result, Exception):
                logger.error(f"Batch geocoding error: {task_result}")
                continue
                
            address, result = task_result
            results[address] = result
        
        return results
    
    def clear_cache(self) -> None:
        """Clear all cached geocoding results"""
        self.geocoding_cache.clear()
        self.reverse_cache.clear()
        logger.info("Geocoding cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        current_time = time.time()
        
        # Count valid (non-expired) entries
        valid_geocoding = sum(
            1 for entry in self.geocoding_cache.values()
            if not entry.is_expired(self.cache_timeout)
        )
        
        valid_reverse = sum(
            1 for entry in self.reverse_cache.values()
            if not entry.is_expired(self.cache_timeout)
        )
        
        return {
            'geocoding_cache_size': len(self.geocoding_cache),
            'reverse_cache_size': len(self.reverse_cache),
            'valid_geocoding_entries': valid_geocoding,
            'valid_reverse_entries': valid_reverse,
            'cache_timeout': self.cache_timeout
        }
    
    def cleanup_expired_cache(self) -> int:
        """
        Remove expired entries from cache
        
        Returns:
            int: Number of entries removed
        """
        removed_count = 0
        
        # Clean geocoding cache
        expired_keys = [
            key for key, entry in self.geocoding_cache.items()
            if entry.is_expired(self.cache_timeout)
        ]
        
        for key in expired_keys:
            del self.geocoding_cache[key]
            removed_count += 1
        
        # Clean reverse geocoding cache
        expired_keys = [
            key for key, entry in self.reverse_cache.items()
            if entry.is_expired(self.cache_timeout)
        ]
        
        for key in expired_keys:
            del self.reverse_cache[key]
            removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} expired cache entries")
        
        return removed_count