"""
Demo script for AddressConverter functionality

This script demonstrates how to use the AddressConverter class for
geocoding addresses to coordinates and reverse geocoding.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from address_converter import AddressConverter


async def demo_address_conversion():
    """Demonstrate address conversion functionality"""
    print("=== Address Converter Demo ===\n")
    
    # Initialize converter
    converter = AddressConverter(cache_timeout=3600)
    
    # Test addresses
    test_addresses = [
        "Times Square, New York, NY",
        "Golden Gate Bridge, San Francisco, CA",
        "1600 Pennsylvania Avenue, Washington, DC",
        "Central Park, Manhattan, NY",
        "Invalid address 123"
    ]
    
    print("1. Testing individual address geocoding:")
    print("-" * 50)
    
    for address in test_addresses:
        print(f"\nGeocoding: {address}")
        result = await converter.address_to_coordinates(address)
        
        if result['success']:
            print(f"  ✓ Success: {result['latitude']:.6f}, {result['longitude']:.6f}")
            print(f"  Formatted: {result['formatted_address']}")
            print(f"  Confidence: {result.get('confidence', 'N/A')}")
            print(f"  Cached: {result.get('cached', False)}")
        else:
            print(f"  ✗ Failed: {result['error']}")
    
    print("\n" + "="*60)
    print("2. Testing batch geocoding:")
    print("-" * 50)
    
    batch_addresses = [
        "Empire State Building, New York",
        "Hollywood Sign, Los Angeles, CA",
        "Space Needle, Seattle, WA"
    ]
    
    print(f"Batch geocoding {len(batch_addresses)} addresses...")
    batch_results = await converter.batch_geocode_addresses(batch_addresses)
    
    for address, result in batch_results.items():
        if result['success']:
            print(f"  ✓ {address}: {result['latitude']:.6f}, {result['longitude']:.6f}")
        else:
            print(f"  ✗ {address}: {result['error']}")
    
    print("\n" + "="*60)
    print("3. Testing reverse geocoding:")
    print("-" * 50)
    
    test_coordinates = [
        (40.7589, -73.9851),  # Times Square
        (37.8199, -122.4783),  # Golden Gate Bridge
        (38.8977, -77.0365),   # White House
    ]
    
    for lat, lon in test_coordinates:
        print(f"\nReverse geocoding: {lat:.6f}, {lon:.6f}")
        result = await converter.coordinates_to_address(lat, lon)
        
        if result['success']:
            print(f"  ✓ Address: {result['address']}")
            print(f"  Cached: {result.get('cached', False)}")
        else:
            print(f"  ✗ Failed: {result['error']}")
    
    print("\n" + "="*60)
    print("4. Cache statistics:")
    print("-" * 50)
    
    stats = converter.get_cache_stats()
    print(f"Geocoding cache size: {stats['geocoding_cache_size']}")
    print(f"Reverse cache size: {stats['reverse_cache_size']}")
    print(f"Valid geocoding entries: {stats['valid_geocoding_entries']}")
    print(f"Valid reverse entries: {stats['valid_reverse_entries']}")
    print(f"Cache timeout: {stats['cache_timeout']} seconds")
    
    print("\n" + "="*60)
    print("5. Testing cache functionality:")
    print("-" * 50)
    
    # Test same address again to show caching
    print("Geocoding same address again (should be cached):")
    result = await converter.address_to_coordinates("Times Square, New York, NY")
    print(f"Cached: {result.get('cached', False)}")
    
    # Test cache cleanup
    print(f"\nBefore cleanup: {converter.get_cache_stats()['geocoding_cache_size']} entries")
    removed = converter.cleanup_expired_cache()
    print(f"Removed {removed} expired entries")
    print(f"After cleanup: {converter.get_cache_stats()['geocoding_cache_size']} entries")
    
    print("\n" + "="*60)
    print("6. Testing address validation:")
    print("-" * 50)
    
    validation_tests = [
        "123 Main Street, New York, NY",  # Valid
        "",  # Invalid - empty
        "A",  # Invalid - too short
        "123",  # Invalid - only numbers
        "!@#$%",  # Invalid - only special chars
        "   ",  # Invalid - only whitespace
        "Central Park, Manhattan",  # Valid
    ]
    
    for address in validation_tests:
        is_valid = converter.validate_address_format(address)
        status = "✓ Valid" if is_valid else "✗ Invalid"
        print(f"  {status}: '{address}'")
    
    print("\n" + "="*60)
    print("Demo completed!")


if __name__ == "__main__":
    asyncio.run(demo_address_conversion())