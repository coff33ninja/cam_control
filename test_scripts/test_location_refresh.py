#!/usr/bin/env python3
"""
Test script to verify location detection refresh functionality.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.interactive_map_manager import InteractiveMapManager
from src.location_detector import LocationDetector

async def test_location_refresh():
    """Test location detection refresh when script runs from different locations."""
    print("🧪 Testing location detection refresh functionality...")
    
    # Test 1: Clear location cache and force new detection
    print("\n1. Clearing location cache and forcing new detection...")
    detector = LocationDetector("camera_data.db")
    await detector.clear_location_cache()
    print("   ✅ Location cache cleared")
    
    # Test 2: Force new location detection
    print("\n2. Forcing new location detection...")
    location_result = await detector.detect_script_location()
    print(f"   Status: {'Success' if location_result.success else 'Failed'}")
    print(f"   Location: {location_result.address}")
    print(f"   Method: {location_result.detection_method}")
    print(f"   Confidence: {location_result.confidence_score:.1%}")
    
    # Test 3: Test map initialization with fresh location
    print("\n3. Testing map initialization with fresh location...")
    map_manager = InteractiveMapManager("camera_data.db")
    location_status = await map_manager.initialize_map_location()
    print(f"   Status: {location_status['status']}")
    print(f"   Location: {location_status['address']}")
    print(f"   Notification: {location_status['notification']}")
    
    # Test 4: Test location history
    print("\n4. Testing location history...")
    history = await detector.get_location_history(3)
    print(f"   Found {len(history)} location records:")
    for i, entry in enumerate(history, 1):
        current_marker = " (CURRENT)" if entry['is_current'] else ""
        print(f"   {i}. {entry['detected_at']}: {entry['address']} "
              f"({entry['detection_method']}, {entry['confidence_score']:.1%}){current_marker}")
    
    print("\n✅ Location detection refresh test completed!")

if __name__ == "__main__":
    asyncio.run(test_location_refresh())