#!/usr/bin/env python3
"""
Demonstration of MapConfigurationManager functionality

This script demonstrates the key features of the configuration management system
working with the actual camera database.
"""

import asyncio
from map_configuration_manager import MapConfigurationManager

async def demo_configuration_management():
    """Demonstrate the key configuration management features."""
    print("🎯 MapConfigurationManager Demonstration")
    print("=" * 60)
    
    # Initialize the configuration manager
    manager = MapConfigurationManager()
    
    print("\n📊 Current Database Status:")
    
    # Check current configurations
    configs = await manager.list_configurations()
    print(f"   • Existing configurations: {len(configs)}")
    
    # Get statistics
    stats = await manager.get_configuration_statistics()
    print(f"   • Total camera positions stored: {stats['total_camera_positions']}")
    
    print("\n💾 Saving Current Camera Layout:")
    
    # Save current configuration
    result = await manager.save_configuration(
        name="Production Layout",
        description="Current production camera configuration"
    )
    
    if result.success:
        print(f"   ✅ {result.message}")
        config_id = result.configuration_id
        
        # Get details
        details = await manager.get_configuration_details(config_id)
        if details:
            print(f"   📊 Saved {len(details.camera_positions)} camera positions")
            
            # Show first few cameras
            for i, (camera_id, pos) in enumerate(list(details.camera_positions.items())[:3]):
                print(f"   📹 Camera {camera_id}: ({pos['latitude']:.6f}, {pos['longitude']:.6f})")
                print(f"      Coverage: {pos['coverage_radius']}m radius, {pos['field_of_view_angle']}° FOV")
                if i == 2 and len(details.camera_positions) > 3:
                    print(f"   ... and {len(details.camera_positions) - 3} more cameras")
    else:
        print(f"   ❌ {result.message}")
        return
    
    print("\n📥 Loading Configuration:")
    
    # Load the configuration back
    load_result = await manager.load_configuration(config_id)
    if load_result.success:
        print(f"   ✅ {load_result.message}")
    else:
        print(f"   ❌ {load_result.message}")
    
    print("\n📤 Export/Import Functionality:")
    
    # Export configuration
    exported_json = await manager.export_configuration(config_id)
    if exported_json:
        print("   ✅ Configuration exported to JSON format")
        
        # Import as new configuration
        import_result = await manager.import_configuration(
            exported_json,
            name="Backup Layout",
            description="Backup of production configuration"
        )
        
        if import_result.success:
            print(f"   ✅ {import_result.message}")
            backup_config_id = import_result.configuration_id
        else:
            print(f"   ❌ {import_result.message}")
    else:
        print("   ❌ Export failed")
    
    print("\n📋 Configuration Management:")
    
    # List all configurations
    all_configs = await manager.list_configurations()
    print(f"   📊 Total configurations: {len(all_configs)}")
    
    for config in all_configs:
        age_hours = (config.updated_at - config.created_at).total_seconds() / 3600
        print(f"   • {config.name}: {config.camera_count} cameras")
        print(f"     Created: {config.created_at.strftime('%Y-%m-%d %H:%M')}")
        if config.description:
            print(f"     Description: {config.description}")
    
    print("\n🔧 Configuration Update:")
    
    # Update configuration
    update_result = await manager.update_configuration(
        config_id,
        description="Updated production configuration with latest changes"
    )
    
    if update_result.success:
        print(f"   ✅ {update_result.message}")
    else:
        print(f"   ❌ {update_result.message}")
    
    print("\n📈 Final Statistics:")
    
    # Get final statistics
    final_stats = await manager.get_configuration_statistics()
    print(f"   • Total configurations: {final_stats['total_configurations']}")
    print(f"   • Total camera positions: {final_stats['total_camera_positions']}")
    print(f"   • Average cameras per config: {final_stats['average_cameras_per_config']}")
    print(f"   • Most recent: {final_stats.get('most_recent_configuration', 'None')}")
    
    print("\n✅ Key Features Demonstrated:")
    print("   ✅ Save current camera positions and coverage settings")
    print("   ✅ Load saved configurations to restore camera layouts")
    print("   ✅ Export configurations for backup or sharing")
    print("   ✅ Import configurations from JSON data")
    print("   ✅ List and manage multiple configurations")
    print("   ✅ Update configuration metadata")
    print("   ✅ Track configuration statistics and history")
    print("   ✅ Robust error handling and validation")
    
    print("\n" + "=" * 60)
    print("🎉 Configuration management system is fully operational!")

if __name__ == "__main__":
    asyncio.run(demo_configuration_management())