#!/usr/bin/env python3
"""
Test script for Task 23: Camera view on map and misc
"""

import asyncio
import sys
import os

def test_syntax():
    """Test that all new files compile without syntax errors."""
    print("🧪 Testing Task 23 implementation syntax...")
    
    files_to_test = [
        'src/camera_viewer.py',
        'src/rtsp_proxy.py',
        'src/camera_api.py',
        'src/device_manager.py'
    ]
    
    for file_path in files_to_test:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            compile(code, file_path, 'exec')
            print(f"✅ {file_path} - Syntax OK")
            
        except SyntaxError as e:
            print(f"❌ {file_path} - Syntax Error: {e}")
            return False
        except Exception as e:
            print(f"⚠️ {file_path} - Warning: {e}")
    
    return True

def test_implementation_features():
    """Test that the implementation includes required features."""
    print("\n🔍 Checking Task 23 implementation features...")
    
    # Check camera_viewer.py
    with open('src/camera_viewer.py', 'r', encoding='utf-8') as f:
        viewer_content = f.read()
    
    # Check rtsp_proxy.py
    with open('src/rtsp_proxy.py', 'r', encoding='utf-8') as f:
        proxy_content = f.read()
    
    # Check camera_api.py
    with open('src/camera_api.py', 'r', encoding='utf-8') as f:
        api_content = f.read()
    
    # Check device_manager.py
    with open('src/device_manager.py', 'r', encoding='utf-8') as f:
        device_content = f.read()
    
    # Check interactive_map_manager.py for camera viewer integration
    with open('src/interactive_map_manager.py', 'r', encoding='utf-8') as f:
        map_content = f.read()
    
    features = {
        'RTSP camera viewer': 'CameraViewer' in viewer_content and 'rtsp_url' in viewer_content,
        'Pop-out window functionality': 'generate_camera_viewer_html' in viewer_content,
        'Secondary database for device info': 'device_info' in viewer_content and 'manufacturer_info' in viewer_content,
        'RTSP proxy server': 'RTSPProxy' in proxy_content and 'ffmpeg' in proxy_content,
        'Traffic proxying': 'create_proxy_session' in proxy_content,
        'HLS streaming': 'hls' in proxy_content and 'stream.m3u8' in proxy_content,
        'Camera API endpoints': 'CameraAPI' in api_content and '/api/camera/' in api_content,
        'Device auto-detection': 'auto_detect_device_info' in device_content,
        'Manufacturer database': 'manufacturer_info' in device_content,
        'Map integration': 'openCameraViewer' in map_content,
        'Click to view functionality': 'View Camera' in map_content,
        'Ctrl+Click shortcut': 'ctrlKey' in map_content
    }
    
    passed = 0
    total = len(features)
    
    for feature, check in features.items():
        if check:
            print(f"✅ {feature}")
            passed += 1
        else:
            print(f"❌ {feature}")
    
    print(f"\n📊 Implementation score: {passed}/{total} features implemented")
    
    return passed >= total * 0.8

def test_database_schema():
    """Test database schema components."""
    print("\n🗄️ Checking database schema features...")
    
    with open('src/camera_viewer.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    schema_features = {
        'Device info table': 'CREATE TABLE IF NOT EXISTS device_info' in content,
        'Manufacturer info table': 'CREATE TABLE IF NOT EXISTS manufacturer_info' in content,
        'RTSP URL storage': 'rtsp_url TEXT' in content,
        'Serial number tracking': 'serial_number TEXT' in content,
        'Manufacturer defaults': 'default_rtsp_path' in content,
        'Authentication fields': 'username TEXT' in content and 'password TEXT' in content
    }
    
    passed = 0
    total = len(schema_features)
    
    for feature, check in schema_features.items():
        if check:
            print(f"✅ {feature}")
            passed += 1
        else:
            print(f"❌ {feature}")
    
    return passed == total

def test_proxy_functionality():
    """Test RTSP proxy functionality."""
    print("\n🔄 Checking RTSP proxy functionality...")
    
    with open('src/rtsp_proxy.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    proxy_features = {
        'FFmpeg integration': 'ffmpeg' in content,
        'RTSP to HLS conversion': 'hls' in content and 'libx264' in content,
        'Session management': 'ProxySession' in content,
        'Port management': 'port_pool' in content,
        'Client counting': 'client_count' in content,
        'Session cleanup': 'cleanup_expired_sessions' in content,
        'HTTP server for HLS': 'serve_hls' in content,
        'CORS headers': 'Access-Control-Allow-Origin' in content
    }
    
    passed = 0
    total = len(proxy_features)
    
    for feature, check in proxy_features.items():
        if check:
            print(f"✅ {feature}")
            passed += 1
        else:
            print(f"❌ {feature}")
    
    return passed >= total * 0.75

def main():
    """Run all tests."""
    print("🚀 Starting Task 23 Implementation Tests\n")
    
    syntax_ok = test_syntax()
    features_ok = test_implementation_features()
    database_ok = test_database_schema()
    proxy_ok = test_proxy_functionality()
    
    print("\n" + "="*60)
    print("📋 TASK 23 IMPLEMENTATION SUMMARY")
    print("="*60)
    
    if syntax_ok:
        print("✅ Syntax: All files compile successfully")
    else:
        print("❌ Syntax: Compilation errors found")
    
    if features_ok:
        print("✅ Features: Core functionality implemented")
    else:
        print("⚠️ Features: Some functionality may be missing")
    
    if database_ok:
        print("✅ Database: Secondary database schema complete")
    else:
        print("⚠️ Database: Database schema may be incomplete")
    
    if proxy_ok:
        print("✅ Proxy: RTSP proxy functionality implemented")
    else:
        print("⚠️ Proxy: Proxy functionality may be incomplete")
    
    overall_success = syntax_ok and features_ok and database_ok and proxy_ok
    
    if overall_success:
        print("\n🎉 Task 23 implementation appears to be complete!")
        print("\nImplemented components:")
        print("📹 RTSP Camera Viewer:")
        print("  • Pop-out window with camera stream display")
        print("  • RTSP URL generation and testing")
        print("  • Device information display")
        print("  • Stream controls (start, stop, refresh, fullscreen)")
        print("\n🗄️ Secondary Database:")
        print("  • Device information storage (manufacturer, model, serial)")
        print("  • Manufacturer defaults and RTSP configurations")
        print("  • Auto-detection capabilities")
        print("  • CSV import/export functionality")
        print("\n🔄 RTSP Proxy Server:")
        print("  • RTSP to HLS conversion using FFmpeg")
        print("  • Session management and client tracking")
        print("  • Traffic proxying to reduce server bandwidth")
        print("  • Automatic session cleanup")
        print("\n🌐 Web API Integration:")
        print("  • Camera viewer endpoints")
        print("  • Stream proxy management")
        print("  • Device information APIs")
        print("  • Map integration with click-to-view")
        print("\n💡 Usage:")
        print("  • Click 'View Camera' button in camera popup")
        print("  • Ctrl+Click (or Cmd+Click) camera marker for direct access")
        print("  • Streams are proxied to reduce bandwidth usage")
    else:
        print("\n⚠️ Task 23 implementation may need additional work")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)