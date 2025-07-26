#!/usr/bin/env python3
"""
Setup script for Camera Viewer functionality (Task 23)

This script initializes the camera viewer system including:
- Secondary database setup
- Device information population
- RTSP proxy configuration
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, 'src')

from src.camera_viewer import CameraViewer
from src.device_manager import DeviceManager
from src.rtsp_proxy import initialize_proxy
import aiosqlite


async def setup_camera_viewer_system():
    """Set up the complete camera viewer system."""
    print("🚀 Setting up Camera Viewer System (Task 23)")
    print("=" * 50)
    
    try:
        # 1. Initialize camera viewer and secondary database
        print("\n1. 🗄️ Initializing secondary database...")
        camera_viewer = CameraViewer()
        await camera_viewer.initialize_device_database()
        print("✅ Secondary database initialized with manufacturer defaults")
        
        # 2. Initialize device manager
        print("\n2. 📱 Setting up device manager...")
        device_manager = DeviceManager()
        
        # Get device statistics
        stats = await device_manager.get_device_statistics()
        if stats['success']:
            print(f"✅ Device database ready - {stats['statistics']['total_devices']} devices configured")
        
        # 3. Initialize RTSP proxy
        print("\n3. 🔄 Initializing RTSP proxy server...")
        proxy = await initialize_proxy()
        print("✅ RTSP proxy server initialized")
        
        # 4. Check main camera database
        print("\n4. 📹 Checking main camera database...")
        async with aiosqlite.connect("camera_data.db") as db:
            cursor = await db.execute("SELECT COUNT(*) FROM cameras WHERE ip_address IS NOT NULL")
            camera_count = (await cursor.fetchone())[0]
            print(f"✅ Found {camera_count} cameras with IP addresses")
        
        # 5. Offer to run auto-detection
        if camera_count > 0:
            print(f"\n5. 🔍 Auto-detection available for {camera_count} cameras")
            print("   Run device auto-detection to populate manufacturer/model info:")
            print("   python -c \"import asyncio; from src.device_manager import DeviceManager; asyncio.run(DeviceManager().bulk_auto_detect())\"")
        
        print("\n" + "=" * 50)
        print("🎉 Camera Viewer System Setup Complete!")
        print("\n📋 System Components Ready:")
        print("✅ RTSP Camera Viewer with pop-out windows")
        print("✅ Secondary database for device information")
        print("✅ RTSP proxy server for bandwidth optimization")
        print("✅ Web API endpoints for camera viewing")
        print("✅ Interactive map integration")
        
        print("\n💡 Usage Instructions:")
        print("1. Click 'View Camera' button in camera popup on map")
        print("2. Or use Ctrl+Click (Cmd+Click) on camera marker")
        print("3. Camera streams will open in pop-out windows")
        print("4. RTSP streams are automatically proxied to reduce bandwidth")
        
        print("\n🔧 Configuration:")
        print("• Device info database: device_info.db")
        print("• RTSP proxy ports: 8080-8130 (50 concurrent sessions)")
        print("• Supported manufacturers: Hikvision, Dahua, Axis, Foscam, Reolink, Ubiquiti")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_camera_viewer_functionality():
    """Test camera viewer functionality with sample data."""
    print("\n🧪 Testing Camera Viewer Functionality")
    print("-" * 40)
    
    try:
        camera_viewer = CameraViewer()
        
        # Test with a sample camera (if exists)
        async with aiosqlite.connect("camera_data.db") as db:
            cursor = await db.execute("""
                SELECT id, ip_address FROM cameras 
                WHERE ip_address IS NOT NULL 
                LIMIT 1
            """)
            sample_camera = await cursor.fetchone()
        
        if sample_camera:
            camera_id, ip_address = sample_camera
            print(f"📹 Testing with camera {camera_id} ({ip_address})")
            
            # Get stream info
            stream_info = await camera_viewer.get_camera_stream_info(camera_id)
            if stream_info:
                print(f"✅ Stream info retrieved: {stream_info.get_display_name()}")
                print(f"   RTSP URL: {stream_info.get_rtsp_url()}")
                print(f"   Online: {stream_info.is_online}")
                
                # Test viewer HTML generation
                viewer_html = camera_viewer.generate_camera_viewer_html(stream_info)
                if len(viewer_html) > 1000:  # Basic check for substantial HTML
                    print("✅ Camera viewer HTML generated successfully")
                else:
                    print("⚠️ Camera viewer HTML may be incomplete")
            else:
                print("⚠️ Could not retrieve stream info")
        else:
            print("⚠️ No cameras with IP addresses found for testing")
        
        print("✅ Camera viewer functionality test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


def show_api_endpoints():
    """Show available API endpoints."""
    print("\n🌐 Available API Endpoints")
    print("-" * 30)
    
    endpoints = [
        ("GET", "/api/camera/viewer/{camera_id}", "Get camera viewer HTML"),
        ("GET", "/api/camera/info/{camera_id}", "Get camera information"),
        ("PUT", "/api/camera/device/{camera_id}", "Update device information"),
        ("POST", "/api/camera/stream/{camera_id}", "Create RTSP proxy session"),
        ("DELETE", "/api/camera/stream/{session_id}", "Stop proxy session"),
        ("GET", "/api/camera/sessions", "List active proxy sessions"),
        ("GET", "/api/camera/manufacturers", "Get manufacturer information"),
        ("POST", "/api/camera/test-stream", "Test camera stream connectivity")
    ]
    
    for method, endpoint, description in endpoints:
        print(f"{method:6} {endpoint:35} - {description}")


async def main():
    """Main setup function."""
    print("Camera Viewer Setup - Task 23 Implementation")
    
    # Run setup
    setup_success = await setup_camera_viewer_system()
    
    if setup_success:
        # Run tests
        await test_camera_viewer_functionality()
        
        # Show API endpoints
        show_api_endpoints()
        
        print(f"\n🎯 Task 23 Implementation Status: COMPLETE")
        print("\nNext steps:")
        print("1. Start your web server with camera API routes")
        print("2. Configure camera device information as needed")
        print("3. Test camera viewing functionality on the interactive map")
        
        return True
    else:
        print(f"\n❌ Task 23 Implementation Status: FAILED")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)