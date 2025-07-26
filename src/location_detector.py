#!/usr/bin/env python3
"""
Location Detection Service

This module provides location detection functionality for the interactive camera mapping system.
It includes IP geolocation, timezone-based location estimation, and location caching.
"""

import asyncio
import aiosqlite
import json
import time
import socket
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

# Third-party imports for location detection
try:
    import requests
    import pytz
    from timezonefinder import TimezoneFinder
except ImportError as e:
    print(f"Warning: Some location detection dependencies are missing: {e}")
    print("Install with: pip install requests pytz timezonefinder")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LocationResult:
    """Data class for location detection results."""
    latitude: float
    longitude: float
    address: Optional[str] = None
    detection_method: str = "unknown"
    confidence_score: float = 1.0
    error_message: Optional[str] = None
    success: bool = True

class LocationDetector:
    """
    Service for detecting script execution location using multiple methods.
    
    Provides IP geolocation, timezone-based estimation, and location caching
    with fallback mechanisms for robust location detection.
    """
    
    def __init__(self, db_path: str = "camera_data.db"):
        self.db_path = db_path
        self.default_location = (40.7128, -74.0060)  # New York City fallback
        self.cache_timeout = 3600  # 1 hour cache timeout
        self.location_cache = {}
        
        # IP geolocation service URLs (free tiers)
        self.geolocation_services = [
            {
                'name': 'ipapi',
                'url': 'http://ip-api.com/json/',
                'fields': ['lat', 'lon', 'city', 'regionName', 'country']
            },
            {
                'name': 'ipinfo',
                'url': 'https://ipinfo.io/json',
                'fields': ['loc', 'city', 'region', 'country']
            },
            {
                'name': 'ipgeolocation',
                'url': 'https://api.ipgeolocation.io/ipgeo?apiKey=free',
                'fields': ['latitude', 'longitude', 'city', 'state_prov', 'country_name']
            }
        ]
    
    async def detect_script_location(self) -> LocationResult:
        """
        Detect current location based on script execution environment.
        
        Uses multiple detection methods with fallback:
        1. IP geolocation (primary)
        2. System timezone estimation (fallback)
        3. Default location (last resort)
        
        Returns:
            LocationResult: Detected location with metadata
        """
        logger.info("🌍 Starting location detection...")
        
        # Try IP geolocation first
        ip_result = await self.get_ip_geolocation()
        if ip_result.success:
            logger.info(f"✅ Location detected via IP geolocation: {ip_result.address}")
            await self.store_detected_location(
                ip_result.latitude, 
                ip_result.longitude, 
                ip_result.address,
                ip_result.detection_method,
                ip_result.confidence_score
            )
            return ip_result
        
        # Fallback to timezone-based estimation
        logger.info("⚠️  IP geolocation failed, trying timezone-based estimation...")
        timezone_result = self.get_system_timezone_location()
        if timezone_result.success:
            logger.info(f"✅ Location estimated via timezone: {timezone_result.address}")
            await self.store_detected_location(
                timezone_result.latitude,
                timezone_result.longitude,
                timezone_result.address,
                timezone_result.detection_method,
                timezone_result.confidence_score
            )
            return timezone_result
        
        # Last resort: use default location
        logger.warning("⚠️  All location detection methods failed, using default location")
        default_result = LocationResult(
            latitude=self.default_location[0],
            longitude=self.default_location[1],
            address="New York, NY, USA (Default)",
            detection_method="default",
            confidence_score=0.1,
            error_message="All detection methods failed"
        )
        
        await self.store_detected_location(
            default_result.latitude,
            default_result.longitude,
            default_result.address,
            default_result.detection_method,
            default_result.confidence_score
        )
        
        return default_result
    
    async def get_ip_geolocation(self) -> LocationResult:
        """
        Get location based on public IP address using multiple services.
        
        Returns:
            LocationResult: Location data from IP geolocation service
        """
        # Check cache first
        cache_key = "ip_geolocation"
        if self._is_cache_valid(cache_key):
            logger.info("📋 Using cached IP geolocation result")
            return self.location_cache[cache_key]['result']
        
        for service in self.geolocation_services:
            try:
                logger.info(f"🌐 Trying IP geolocation service: {service['name']}")
                
                # Make HTTP request with timeout
                response = requests.get(
                    service['url'], 
                    timeout=10,
                    headers={'User-Agent': 'Camera-Mapping-System/1.0'}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Parse response based on service format
                result = self._parse_geolocation_response(data, service)
                if result.success:
                    # Cache successful result
                    self.location_cache[cache_key] = {
                        'result': result,
                        'timestamp': time.time()
                    }
                    return result
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ {service['name']} request failed: {e}")
                continue
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"❌ {service['name']} response parsing failed: {e}")
                continue
            except Exception as e:
                logger.warning(f"❌ {service['name']} unexpected error: {e}")
                continue
        
        return LocationResult(
            latitude=0.0,
            longitude=0.0,
            detection_method="ip_geolocation",
            confidence_score=0.0,
            error_message="All IP geolocation services failed",
            success=False
        )
    
    def _parse_geolocation_response(self, data: dict, service: dict) -> LocationResult:
        """Parse geolocation service response based on service format."""
        try:
            if service['name'] == 'ipapi':
                # ip-api.com format
                if data.get('status') != 'success':
                    raise ValueError(f"Service returned error: {data.get('message', 'Unknown error')}")
                
                return LocationResult(
                    latitude=float(data['lat']),
                    longitude=float(data['lon']),
                    address=f"{data.get('city', '')}, {data.get('regionName', '')}, {data.get('country', '')}".strip(', '),
                    detection_method=f"ip_geolocation_{service['name']}",
                    confidence_score=0.8
                )
            
            elif service['name'] == 'ipinfo':
                # ipinfo.io format
                if 'loc' not in data:
                    raise ValueError("Location data not found in response")
                
                lat, lon = data['loc'].split(',')
                address_parts = [data.get('city', ''), data.get('region', ''), data.get('country', '')]
                address = ', '.join(filter(None, address_parts))
                
                return LocationResult(
                    latitude=float(lat),
                    longitude=float(lon),
                    address=address,
                    detection_method=f"ip_geolocation_{service['name']}",
                    confidence_score=0.8
                )
            
            elif service['name'] == 'ipgeolocation':
                # ipgeolocation.io format
                if 'latitude' not in data or 'longitude' not in data:
                    raise ValueError("Latitude/longitude not found in response")
                
                address_parts = [
                    data.get('city', ''), 
                    data.get('state_prov', ''), 
                    data.get('country_name', '')
                ]
                address = ', '.join(filter(None, address_parts))
                
                return LocationResult(
                    latitude=float(data['latitude']),
                    longitude=float(data['longitude']),
                    address=address,
                    detection_method=f"ip_geolocation_{service['name']}",
                    confidence_score=0.8
                )
            
            else:
                raise ValueError(f"Unknown service format: {service['name']}")
                
        except (KeyError, ValueError, TypeError) as e:
            return LocationResult(
                latitude=0.0,
                longitude=0.0,
                detection_method=f"ip_geolocation_{service['name']}",
                confidence_score=0.0,
                error_message=f"Response parsing failed: {e}",
                success=False
            )
    
    def get_system_timezone_location(self) -> LocationResult:
        """
        Estimate location based on system timezone.
        
        Uses timezone information to provide approximate location coordinates.
        Less accurate than IP geolocation but works offline.
        
        Returns:
            LocationResult: Estimated location based on timezone
        """
        try:
            # Get system timezone
            local_tz = datetime.now(timezone.utc).astimezone().tzinfo
            timezone_name = str(local_tz)
            
            logger.info(f"🕐 Detected system timezone: {timezone_name}")
            
            # Common timezone to location mappings
            timezone_locations = {
                'EST': (40.7128, -74.0060, "Eastern US"),
                'CST': (41.8781, -87.6298, "Central US"), 
                'MST': (39.7392, -104.9903, "Mountain US"),
                'PST': (37.7749, -122.4194, "Pacific US"),
                'GMT': (51.5074, -0.1278, "London, UK"),
                'CET': (52.5200, 13.4050, "Central Europe"),
                'JST': (35.6762, 139.6503, "Tokyo, Japan"),
                'AEST': (-33.8688, 151.2093, "Sydney, Australia"),
            }
            
            # Try to match timezone abbreviation
            for tz_abbr, (lat, lon, location_name) in timezone_locations.items():
                if tz_abbr in timezone_name.upper():
                    return LocationResult(
                        latitude=lat,
                        longitude=lon,
                        address=f"{location_name} (Timezone Estimate)",
                        detection_method="timezone_estimation",
                        confidence_score=0.5
                    )
            
            # If no match found, try using pytz if available
            try:
                import pytz
                from timezonefinder import TimezoneFinder
                
                # Get more detailed timezone info
                tf = TimezoneFinder()
                
                # Use common timezone center points
                common_timezones = {
                    'America/New_York': (40.7128, -74.0060),
                    'America/Chicago': (41.8781, -87.6298),
                    'America/Denver': (39.7392, -104.9903),
                    'America/Los_Angeles': (34.0522, -118.2437),
                    'Europe/London': (51.5074, -0.1278),
                    'Europe/Berlin': (52.5200, 13.4050),
                    'Asia/Tokyo': (35.6762, 139.6503),
                    'Australia/Sydney': (-33.8688, 151.2093),
                }
                
                for tz_name, (lat, lon) in common_timezones.items():
                    if tz_name in timezone_name:
                        return LocationResult(
                            latitude=lat,
                            longitude=lon,
                            address=f"{tz_name.replace('_', ' ')} (Timezone Estimate)",
                            detection_method="timezone_estimation_detailed",
                            confidence_score=0.6
                        )
                        
            except ImportError:
                logger.info("📦 pytz/timezonefinder not available for detailed timezone detection")
            
            # Fallback to UTC if nothing else works
            return LocationResult(
                latitude=51.5074,  # London (GMT)
                longitude=-0.1278,
                address="London, UK (UTC Fallback)",
                detection_method="timezone_estimation_fallback",
                confidence_score=0.3
            )
            
        except Exception as e:
            logger.error(f"❌ Timezone location estimation failed: {e}")
            return LocationResult(
                latitude=0.0,
                longitude=0.0,
                detection_method="timezone_estimation",
                confidence_score=0.0,
                error_message=f"Timezone detection failed: {e}",
                success=False
            )
    
    async def store_detected_location(self, lat: float, lon: float, address: str = None, 
                                    detection_method: str = "unknown", 
                                    confidence_score: float = 1.0) -> Dict[str, any]:
        """
        Store detected location in database with validation.
        
        Args:
            lat: Latitude coordinate
            lon: Longitude coordinate  
            address: Human-readable address (optional)
            detection_method: Method used for detection
            confidence_score: Confidence in detection accuracy (0.0-1.0)
            
        Returns:
            Dict with operation status and location ID
        """
        # Validate coordinates
        if not self._validate_coordinates(lat, lon):
            error_msg = f"Invalid coordinates: lat={lat}, lon={lon}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'location_id': None
            }
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Mark all previous locations as not current
                await db.execute(
                    "UPDATE script_locations SET is_current = 0"
                )
                
                # Insert new location
                cursor = await db.execute("""
                    INSERT INTO script_locations 
                    (latitude, longitude, address, detection_method, confidence_score, is_current)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (lat, lon, address, detection_method, confidence_score))
                
                location_id = cursor.lastrowid
                await db.commit()
                
                logger.info(f"✅ Stored location: {lat}, {lon} ({detection_method})")
                
                return {
                    'success': True,
                    'location_id': location_id,
                    'latitude': lat,
                    'longitude': lon,
                    'address': address,
                    'detection_method': detection_method,
                    'confidence_score': confidence_score
                }
                
        except Exception as e:
            error_msg = f"Database error storing location: {e}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'location_id': None
            }
    
    async def get_current_location(self) -> Optional[Dict[str, any]]:
        """
        Get the current stored location from database.
        
        Returns:
            Dict with current location data or None if not found
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, latitude, longitude, address, detection_method, 
                           confidence_score, detected_at
                    FROM script_locations 
                    WHERE is_current = 1 
                    ORDER BY detected_at DESC 
                    LIMIT 1
                """)
                
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'latitude': row[1],
                        'longitude': row[2],
                        'address': row[3],
                        'detection_method': row[4],
                        'confidence_score': row[5],
                        'detected_at': row[6]
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting current location: {e}")
            return None
    
    async def get_location_history(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        Get location detection history.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of location records ordered by detection time
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, latitude, longitude, address, detection_method,
                           confidence_score, detected_at, is_current
                    FROM script_locations 
                    ORDER BY detected_at DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = await cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'latitude': row[1],
                        'longitude': row[2],
                        'address': row[3],
                        'detection_method': row[4],
                        'confidence_score': row[5],
                        'detected_at': row[6],
                        'is_current': bool(row[7])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"❌ Error getting location history: {e}")
            return []
    
    def _validate_coordinates(self, lat: float, lon: float) -> bool:
        """
        Validate latitude and longitude coordinates.
        
        Args:
            lat: Latitude value
            lon: Longitude value
            
        Returns:
            True if coordinates are valid, False otherwise
        """
        try:
            lat = float(lat)
            lon = float(lon)
            
            # Check latitude bounds (-90 to 90)
            if lat < -90 or lat > 90:
                return False
            
            # Check longitude bounds (-180 to 180)
            if lon < -180 or lon > 180:
                return False
            
            return True
            
        except (ValueError, TypeError):
            return False
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached result is still valid."""
        if cache_key not in self.location_cache:
            return False
        
        cache_entry = self.location_cache[cache_key]
        return (time.time() - cache_entry['timestamp']) < self.cache_timeout
    
    async def clear_location_cache(self) -> None:
        """Clear the location detection cache."""
        self.location_cache.clear()
        logger.info("🗑️  Location cache cleared")
    
    async def get_map_center_coordinates(self) -> Tuple[float, float]:
        """
        Get coordinates for map center based on current location.
        
        Returns:
            Tuple of (latitude, longitude) for map centering
        """
        current_location = await self.get_current_location()
        
        if current_location:
            return (current_location['latitude'], current_location['longitude'])
        
        # Fallback to detecting new location
        location_result = await self.detect_script_location()
        return (location_result.latitude, location_result.longitude)

# Utility functions for testing and debugging
async def test_location_detection(db_path: str = "camera_data.db") -> None:
    """Test location detection functionality."""
    print("🧪 Testing location detection...")
    
    detector = LocationDetector(db_path)
    
    # Test location detection
    result = await detector.detect_script_location()
    print(f"📍 Detected location: {result.latitude}, {result.longitude}")
    print(f"📍 Address: {result.address}")
    print(f"📍 Method: {result.detection_method}")
    print(f"📍 Confidence: {result.confidence_score}")
    
    # Test getting current location
    current = await detector.get_current_location()
    if current:
        print(f"💾 Current stored location: {current['address']}")
    
    # Test location history
    history = await detector.get_location_history(5)
    print(f"📚 Location history ({len(history)} entries):")
    for entry in history:
        print(f"  - {entry['detected_at']}: {entry['address']} ({entry['detection_method']})")

if __name__ == "__main__":
    # Run tests if script is executed directly
    asyncio.run(test_location_detection())