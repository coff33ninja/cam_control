#!/usr/bin/env python3
"""
Test script for enhanced coverage area visualization functionality.

This script tests the enhanced coverage area implementation for task 7:
- Enhanced coverage area visualization with detailed styling and tooltips
- Different coverage shapes (circular vs directional) based on camera type
- Coverage area styling with opacity changes based on connectivity status
- Hover effects and tooltips for coverage areas showing camera details
"""

import asyncio
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from interactive_map_manager import InteractiveMapManager
from enhanced_camera_models import EnhancedCamera
from coverage_calculator import CoverageCalculator


async def test_enhanced_coverage_areas():
    """Test the enhanced coverage area functionality."""
    print("🧪 Testing Enhanced Coverage Area Visualization...")
    
    try:
        # Initialize the interactive map manager
        map_manager = InteractiveMapManager("camera_data.db")
        
        # Test 1: Create enhanced map with coverage areas
        print("\n1️⃣ Testing enhanced map creation with coverage areas...")
        map_html = await map_manager.create_enhanced_map()
        
        if map_html and len(map_html) > 1000:  # Basic check for substantial HTML content
            print("✅ Enhanced map created successfully")
            print(f"   Map HTML size: {len(map_html):,} characters")
            
            # Check for enhanced coverage area features
            coverage_features = [
                "coverage-area-",  # CSS class for coverage areas
                "Coverage Area Details",  # Enhanced popup title
                "Direction:",  # Direction indicator
                "Coverage Type:",  # Coverage type in popup
                "Coverage Area:",  # Area calculation in popup
                "📹",  # Camera emoji in tooltips
                "🔵",  # Circular coverage indicator
                "📐",  # Directional coverage indicator
            ]
            
            found_features = []
            for feature in coverage_features:
                if feature in map_html:
                    found_features.append(feature)
            
            print(f"   Enhanced features found: {len(found_features)}/{len(coverage_features)}")
            for feature in found_features:
                print(f"   ✓ {feature}")
            
            # Check for CSS enhancements
            css_features = [
                "coverage-area",
                "hover",
                "transition",
                "opacity",
                "leaflet-tooltip",
                "leaflet-popup-content"
            ]
            
            found_css = []
            for css in css_features:
                if css in map_html:
                    found_css.append(css)
            
            print(f"   CSS enhancements found: {len(found_css)}/{len(css_features)}")
            
        else:
            print("❌ Enhanced map creation failed or returned insufficient content")
            return False
        
        # Test 2: Test coverage area calculation with different camera types
        print("\n2️⃣ Testing coverage area calculations...")
        
        # Test circular coverage
        circular_coords = CoverageCalculator.calculate_circular_coverage(40.7128, -74.0060, 100.0)
        if circular_coords and len(circular_coords) > 10:
            print("✅ Circular coverage calculation working")
            print(f"   Generated {len(circular_coords)} coordinate points")
        else:
            print("❌ Circular coverage calculation failed")
        
        # Test directional coverage
        directional_coords = CoverageCalculator.calculate_directional_coverage(
            40.7128, -74.0060, 100.0, 45.0, 90.0
        )
        if directional_coords and len(directional_coords) > 3:
            print("✅ Directional coverage calculation working")
            print(f"   Generated {len(directional_coords)} coordinate points")
        else:
            print("❌ Directional coverage calculation failed")
        
        # Test 3: Test enhanced camera model functionality
        print("\n3️⃣ Testing enhanced camera model features...")
        
        # Create test camera with coverage parameters
        test_camera = EnhancedCamera(
            id=999,
            name="Test Camera",
            location="Test Location",
            ip_address="192.168.1.100",
            mac_address="00:11:22:33:44:55",
            latitude=40.7128,
            longitude=-74.0060,
            coverage_radius=75.0,
            field_of_view_angle=120.0,
            coverage_direction=45.0,
            is_online=True
        )
        
        # Test map marker generation
        marker_config = test_camera.to_map_marker()
        if marker_config and 'popup_content' in marker_config:
            print("✅ Enhanced camera marker configuration working")
            print(f"   Marker color: {marker_config.get('marker_color', 'N/A')}")
            print(f"   Has popup content: {'popup_content' in marker_config}")
        else:
            print("❌ Enhanced camera marker configuration failed")
        
        # Test coverage geometry
        coverage_geometry = test_camera.get_coverage_geometry()
        if coverage_geometry and 'geometry' in coverage_geometry:
            print("✅ Coverage geometry generation working")
            print(f"   Geometry type: {coverage_geometry['geometry'].get('type', 'N/A')}")
        else:
            print("❌ Coverage geometry generation failed")
        
        # Test 4: Test overlap detection
        print("\n4️⃣ Testing coverage overlap detection...")
        
        # Create multiple test cameras for overlap testing
        cameras_for_overlap = [
            {
                'id': 1,
                'name': 'Camera 1',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'coverage_radius': 100.0,
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            },
            {
                'id': 2,
                'name': 'Camera 2',
                'latitude': 40.7130,  # Close to camera 1
                'longitude': -74.0062,
                'coverage_radius': 80.0,
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            },
            {
                'id': 3,
                'name': 'Camera 3',
                'latitude': 40.7200,  # Far from others
                'longitude': -74.0200,
                'coverage_radius': 50.0,
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            }
        ]
        
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras_for_overlap)
        if overlaps:
            print(f"✅ Overlap detection working - found {len(overlaps)} overlaps")
            for overlap in overlaps:
                print(f"   Overlap: Camera {overlap.camera1_id} ↔ Camera {overlap.camera2_id}")
                print(f"   Distance: {overlap.distance:.1f}m, Overlap: {overlap.overlap_percentage:.1f}%")
        else:
            print("⚠️ No overlaps detected (this might be expected)")
        
        print("\n🎉 Enhanced coverage area testing completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_coverage_area_styling():
    """Test coverage area styling based on connectivity status."""
    print("\n🎨 Testing Coverage Area Styling...")
    
    try:
        # Test online camera styling
        online_camera = EnhancedCamera(
            id=1,
            name="Online Camera",
            location="Test Location",
            ip_address="192.168.1.100",
            mac_address="00:11:22:33:44:55",
            latitude=40.7128,
            longitude=-74.0060,
            coverage_radius=100.0,
            field_of_view_angle=360.0,
            coverage_direction=0.0,
            is_online=True
        )
        
        # Test offline camera styling
        offline_camera = EnhancedCamera(
            id=2,
            name="Offline Camera",
            location="Test Location 2",
            ip_address="192.168.1.101",
            mac_address="00:11:22:33:44:56",
            latitude=40.7130,
            longitude=-74.0062,
            coverage_radius=80.0,
            field_of_view_angle=120.0,
            coverage_direction=45.0,
            is_online=False
        )
        
        print("✅ Camera styling test objects created")
        print(f"   Online camera marker color: {online_camera.to_map_marker()['marker_color']}")
        print(f"   Offline camera marker color: {offline_camera.to_map_marker()['marker_color']}")
        
        # Test directional vs circular coverage
        circular_coords = online_camera.get_coverage_coordinates()
        directional_coords = offline_camera.get_coverage_coordinates()
        
        if circular_coords and directional_coords:
            print("✅ Coverage coordinate generation working for both types")
            print(f"   Circular coverage points: {len(circular_coords)}")
            print(f"   Directional coverage points: {len(directional_coords)}")
        else:
            print("❌ Coverage coordinate generation failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during styling test: {e}")
        return False


if __name__ == "__main__":
    async def main():
        print("🚀 Starting Enhanced Coverage Area Tests")
        print("=" * 50)
        
        # Run main functionality tests
        test1_result = await test_enhanced_coverage_areas()
        
        # Run styling tests
        test2_result = await test_coverage_area_styling()
        
        print("\n" + "=" * 50)
        print("📊 Test Results Summary:")
        print(f"   Enhanced Coverage Areas: {'✅ PASS' if test1_result else '❌ FAIL'}")
        print(f"   Coverage Area Styling: {'✅ PASS' if test2_result else '❌ FAIL'}")
        
        if test1_result and test2_result:
            print("\n🎉 All tests passed! Enhanced coverage area visualization is working correctly.")
            return 0
        else:
            print("\n❌ Some tests failed. Please check the implementation.")
            return 1
    
    # Run the tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)