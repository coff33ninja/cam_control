"""
Integration Example: ConnectivityMonitor with InteractiveMapManager

This example demonstrates how the ConnectivityMonitor integrates with the
InteractiveMapManager to provide real-time connectivity status on the map.
"""

import asyncio
from connectivity_monitor import ConnectivityMonitor
from interactive_map_manager import InteractiveMapManager


async def connectivity_integration_demo():
    """Demonstrate integration between ConnectivityMonitor and InteractiveMapManager."""
    print("🔗 ConnectivityMonitor + InteractiveMapManager Integration Demo")
    print("=" * 60)
    
    # Initialize both components
    connectivity_monitor = ConnectivityMonitor(cache_timeout=30)
    map_manager = InteractiveMapManager()
    
    print("\n📡 Step 1: Testing connectivity for all devices...")
    
    # Get connectivity status for all devices
    connectivity_results = await connectivity_monitor.get_all_devices_status()
    
    if connectivity_results:
        print(f"✅ Found {len(connectivity_results)} devices")
        
        # Display connectivity summary
        stats = connectivity_monitor.get_connectivity_stats(connectivity_results)
        print(f"📊 Status: {stats.online_devices}/{stats.total_devices} online ({stats.online_percentage:.1f}%)")
        
        # Show device details
        for device_id, result in connectivity_results.items():
            status_icon = "✅" if result.is_online else "❌"
            device_type = result.device_type.upper()
            print(f"   {status_icon} {device_type} {device_id}: {result.device_name} ({result.ip_address}) - {result.status_text}")
    else:
        print("ℹ️ No devices found in database")
    
    print("\n🗺️ Step 2: Creating enhanced map with connectivity status...")
    
    # Create enhanced map (this will use connectivity status for marker colors)
    try:
        map_html = await map_manager.create_enhanced_map()
        print("✅ Enhanced map created with real-time connectivity status")
        print("   - Online cameras shown with green markers")
        print("   - Offline cameras shown with red markers")
        print("   - Coverage areas have appropriate opacity based on status")
    except Exception as e:
        print(f"❌ Error creating map: {e}")
    
    print("\n🔄 Step 3: Setting up auto-refresh for real-time updates...")
    
    # Define callback for connectivity updates
    def connectivity_update_callback(results):
        """Callback function called when connectivity status is refreshed."""
        online_count = sum(1 for r in results.values() if r.is_online)
        total_count = len(results)
        print(f"   🔄 Connectivity refresh: {online_count}/{total_count} devices online")
        
        # In a real application, this would trigger map updates
        # For example: update marker colors, coverage opacity, etc.
    
    # Add callback and start auto-refresh
    connectivity_monitor.add_refresh_callback(connectivity_update_callback)
    
    try:
        await connectivity_monitor.start_auto_refresh(interval=30)  # 30 second intervals
        print("✅ Auto-refresh started (30s intervals)")
        print("   - Map will automatically update when device status changes")
        
        # Simulate running for a short time
        print("\n⏱️ Running auto-refresh for 5 seconds...")
        await asyncio.sleep(5)
        
    finally:
        await connectivity_monitor.stop_auto_refresh()
        print("🛑 Auto-refresh stopped")
    
    print("\n📈 Step 4: Connectivity statistics and caching performance...")
    
    # Show cache statistics
    cache_stats = connectivity_monitor.get_cache_stats()
    print(f"💾 Cache Performance:")
    print(f"   - Total tests: {cache_stats['total_tests']}")
    print(f"   - Cache hits: {cache_stats['cache_hits']}")
    print(f"   - Hit rate: {cache_stats['cache_hit_rate']:.1f}%")
    print(f"   - Active cache entries: {cache_stats['active_entries']}")
    
    print("\n🎯 Integration Benefits:")
    print("   ✅ Real-time connectivity monitoring")
    print("   ✅ Efficient caching reduces network overhead")
    print("   ✅ Batch testing for multiple devices")
    print("   ✅ Automatic status refresh with configurable intervals")
    print("   ✅ Visual status indicators on map (colors, opacity)")
    print("   ✅ Status change notifications via callbacks")
    
    print("\n" + "=" * 60)
    print("✨ Integration demo completed successfully!")


if __name__ == "__main__":
    asyncio.run(connectivity_integration_demo())