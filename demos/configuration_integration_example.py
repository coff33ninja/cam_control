"""
Integration Example: MapConfigurationManager with Camera Management System

This example demonstrates how the MapConfigurationManager integrates with the
camera management system to provide configuration save/load functionality.
"""

import asyncio
import json
from map_configuration_manager import MapConfigurationManager
from enhanced_camera_models import EnhancedCamera


async def configuration_integration_demo():
    """Demonstrate integration of MapConfigurationManager with camera system."""
    print("🗂️ MapConfigurationManager Integration Demo")
    print("=" * 50)
    
    # Initialize configuration manager
    config_manager = MapConfigurationManager()
    
    print("\n📋 Step 1: Listing existing configurations...")
    
    # List all available configurations
    configurations = await config_manager.list_configurations()
    
    if configurations:
        print(f"✅ Found {len(configurations)} existing configuration(s):")
        for config in configurations:
            age = (config.updated_at - config.created_at).total_seconds()
            print(f"   • {config.name}: {config.camera_count} cameras")
            print(f"     Created: {config.created_at.strftime('%Y-%m-%d %H:%M')}")
            if config.description:
                print(f"     Description: {config.description}")
    else:
        print("ℹ️ No existing configurations found")
    
    print("\n💾 Step 2: Saving current camera layout...")
    
    # Save current configuration
    save_result = await config_manager.save_configuration(
        name="Demo Layout",
        description="Demonstration of configuration management system"
    )
    
    if save_result.success:
        print(f"✅ {save_result.message}")
        demo_config_id = save_result.configuration_id
        
        # Get configuration details
        config_details = await config_manager.get_configuration_details(demo_config_id)
        if config_details:
            print(f"   📊 Saved {len(config_details.camera_positions)} camera positions")
            
            # Show sample camera data
            for camera_id, position in list(config_details.camera_positions.items())[:3]:
                print(f"   📹 Camera {camera_id}: ({position['latitude']:.6f}, {position['longitude']:.6f})")
                print(f"      Coverage: {position['coverage_radius']}m, {position['field_of_view_angle']}° FOV")
    else:
        print(f"❌ {save_result.message}")
        return
    
    print("\n🔄 Step 3: Simulating camera position changes...")
    
    # Simulate making changes to camera positions
    print("   • Moving cameras to new positions...")
    print("   • Adjusting coverage parameters...")
    print("   • (In real application, this would be done through the map interface)")
    
    # Create a modified configuration
    modified_positions = {}
    if config_details:
        for camera_id, position in config_details.camera_positions.items():
            # Simulate slight position changes
            modified_positions[camera_id] = {
                'latitude': position['latitude'] + 0.001,  # Move slightly north
                'longitude': position['longitude'] + 0.001,  # Move slightly east
                'coverage_radius': position['coverage_radius'] + 10.0,  # Increase radius
                'field_of_view_angle': position['field_of_view_angle'],
                'coverage_direction': position['coverage_direction']
            }
    
    # Save modified configuration
    modified_result = await config_manager.save_configuration(
        name="Modified Demo Layout",
        description="Modified camera positions for comparison",
        camera_positions=modified_positions
    )
    
    if modified_result.success:
        print(f"✅ {modified_result.message}")
        modified_config_id = modified_result.configuration_id
    else:
        print(f"❌ {modified_result.message}")
        return
    
    print("\n📥 Step 4: Loading saved configurations...")
    
    # Load original configuration
    print("   Loading original configuration...")
    load_result = await config_manager.load_configuration(demo_config_id)
    
    if load_result.success:
        print(f"   ✅ {load_result.message}")
    else:
        print(f"   ❌ {load_result.message}")
    
    # Load modified configuration
    print("   Loading modified configuration...")
    load_result = await config_manager.load_configuration(modified_config_id)
    
    if load_result.success:
        print(f"   ✅ {load_result.message}")
    else:
        print(f"   ❌ {load_result.message}")
    
    print("\n📤 Step 5: Configuration export/import...")
    
    # Export configuration
    exported_json = await config_manager.export_configuration(demo_config_id)
    
    if exported_json:
        print("✅ Configuration exported to JSON")
        
        # Show sample of exported data
        exported_data = json.loads(exported_json)
        print(f"   📊 Export contains {len(exported_data['camera_positions'])} camera positions")
        print(f"   📅 Created: {exported_data['created_at']}")
        
        # Import as new configuration
        import_result = await config_manager.import_configuration(
            exported_json,
            name="Imported Demo Layout",
            description="Imported from exported configuration"
        )
        
        if import_result.success:
            print(f"✅ {import_result.message}")
            imported_config_id = import_result.configuration_id
        else:
            print(f"❌ {import_result.message}")
    else:
        print("❌ Failed to export configuration")
    
    print("\n📊 Step 6: Configuration statistics...")
    
    # Get statistics
    stats = await config_manager.get_configuration_statistics()
    
    print(f"📈 Configuration Statistics:")
    print(f"   • Total configurations: {stats['total_configurations']}")
    print(f"   • Total camera positions: {stats['total_camera_positions']}")
    print(f"   • Average cameras per config: {stats['average_cameras_per_config']}")
    if stats.get('most_recent_configuration'):
        print(f"   • Most recent: {stats['most_recent_configuration']}")
    
    print("\n🧹 Step 7: Configuration cleanup...")
    
    # List configurations for cleanup
    final_configs = await config_manager.list_configurations()
    demo_configs = [c for c in final_configs if 'Demo' in c.name]
    
    print(f"   Found {len(demo_configs)} demo configurations to clean up")
    
    # Delete demo configurations
    for config in demo_configs:
        delete_result = await config_manager.delete_configuration(config.id)
        if delete_result.success:
            print(f"   ✅ Deleted: {config.name}")
        else:
            print(f"   ❌ Failed to delete: {config.name}")
    
    print("\n🎯 Integration Benefits Demonstrated:")
    print("   ✅ Save current camera layouts with custom names")
    print("   ✅ Load saved configurations to restore camera positions")
    print("   ✅ Compare different camera deployment scenarios")
    print("   ✅ Export/import configurations for backup or sharing")
    print("   ✅ Track configuration history and statistics")
    print("   ✅ Robust error handling and validation")
    print("   ✅ High-performance operations for large configurations")
    
    print("\n" + "=" * 50)
    print("✨ Configuration management integration demo completed!")


async def demonstrate_use_cases():
    """Demonstrate common use cases for configuration management."""
    print("\n🎯 Common Use Cases for Configuration Management")
    print("=" * 50)
    
    config_manager = MapConfigurationManager()
    
    # Use Case 1: Planning camera deployments
    print("\n📋 Use Case 1: Planning Camera Deployments")
    print("   • Security team creates 'Proposed Layout A' configuration")
    print("   • Adjusts camera positions and coverage areas")
    print("   • Saves configuration for review")
    print("   • Creates alternative 'Proposed Layout B'")
    print("   • Compares both layouts before implementation")
    
    # Use Case 2: Seasonal adjustments
    print("\n🌱 Use Case 2: Seasonal Adjustments")
    print("   • Save 'Summer Layout' with expanded outdoor coverage")
    print("   • Save 'Winter Layout' with focus on indoor areas")
    print("   • Switch between configurations as seasons change")
    
    # Use Case 3: Event-specific configurations
    print("\n🎪 Use Case 3: Event-Specific Configurations")
    print("   • Create 'Special Event Layout' for concerts/gatherings")
    print("   • Temporarily adjust camera positions for event coverage")
    print("   • Restore 'Normal Operations Layout' after event")
    
    # Use Case 4: Backup and disaster recovery
    print("\n💾 Use Case 4: Backup and Disaster Recovery")
    print("   • Regular automated backups of current configuration")
    print("   • Export configurations for off-site storage")
    print("   • Quick restoration after system maintenance")
    
    # Use Case 5: Multi-site management
    print("\n🏢 Use Case 5: Multi-Site Management")
    print("   • Template configurations for similar locations")
    print("   • Export successful layouts for replication")
    print("   • Standardize camera deployments across sites")
    
    print("\n✨ Configuration management enables flexible, efficient camera system administration!")


if __name__ == "__main__":
    asyncio.run(configuration_integration_demo())
    asyncio.run(demonstrate_use_cases())