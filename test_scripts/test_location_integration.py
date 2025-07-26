#!/usr/bin/env python3
"""
Test script for location detection integration with map initialization.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.interactive_map_manager import InteractiveMapManager
from src.location_detector import LocationDetector

async def test_location_integration():
    """Test the location detection integration with map initialization."""
    print("🧪 Testing location detection integration with map initialization...")
    
    # Test 1: Location detection initialization
    print("\n1. Testing location detection initialization...")
    map_manager = InteractiveMapManager("camera_data.db")
    
    location_status = await map_manager.initialize_map_location()
    print(f"   Status: {location_status['status']}")
    print(f"   Success: {location_status['success']}")
    print(f"   Location: {location_status['address']}")
    print(f"   Coordinates: {location_status['latitude']}, {location_status['longitude']}")
    print(f"   Method: {location_status['detection_method']}")
    print(f"   Confidence: {location_status['confidence_score']:.1%}")
    print(f"   Notification: {location_status['notification']}")
    
    # Test 2: Map center calculation with location detection
    print("\n2. Testing map center calculation with location detection...")
    cameras = []  # Empty cameras list to test location detection fallback
    dvrs = []     # Empty DVRs list to test location detection fallback
    
    center_lat, center_lon = await map_manager._get_initial_map_center(cameras, dvrs)
    print(f"   Map center: {center_lat}, {center_lon}")
    
    # Test 3: Empty map creation with location detection
    print("\n3. Testing empty map creation with location detection...")
    empty_map_html = await map_manager._create_empty_map_with_location(location_status)
    print(f"   Empty map HTML length: {len(empty_map_html)} characters")
    print(f"   Contains location notification: {'location-notification' in empty_map_html}")
    
    # Test 4: Enhanced map creation with location detection
    print("\n4. Testing enhanced map creation with location detection...")
    try:
        enhanced_map_html = await map_manager.create_enhanced_map()
        print(f"   Enhanced map HTML length: {len(enhanced_map_html)} characters")
        print(f"   Contains location notification: {'location-notification' in enhanced_map_html}")
        print("   ✅ Enhanced map creation successful")
    except Exception as e:
        print(f"   ❌ Enhanced map creation failed: {e}")
    
    # Test 5: Location staleness check
    print("\n5. Testing location staleness check...")
    current_location = await map_manager.location_detector.get_current_location()
    if current_location:
        is_stale = map_manager._is_location_detection_stale(current_location)
        print(f"   Current location is stale: {is_stale}")
        print(f"   Location detected at: {current_location['detected_at']}")
    else:
        print("   No current location found in database")
    
    print("\n✅ Location detection integration test completed!")

if __name__ == "__main__":
    asyncio.run(test_location_integration())