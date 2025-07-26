"""
Map Configuration Management System for Interactive Camera Mapping

This module provides comprehensive configuration management capabilities including
saving, loading, listing, and deleting map configurations with camera positions
and coverage settings.
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import aiosqlite

from .enhanced_camera_models import EnhancedCamera, MapConfiguration


@dataclass
class ConfigurationSummary:
    """Summary information about a map configuration."""
    id: int
    name: str
    description: str
    camera_count: int
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'camera_count': self.camera_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class ConfigurationOperation:
    """Result of a configuration operation."""
    success: bool
    message: str
    configuration_id: Optional[int] = None
    error_details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class MapConfigurationManager:
    """
    Manages map configurations for saving and loading camera layouts.
    
    Features:
    - Save current camera positions and coverage settings
    - Load saved configurations to restore camera layouts
    - List all available configurations with metadata
    - Delete configurations with proper cleanup
    - Validate configuration data integrity
    - Handle concurrent access safely
    """
    
    def __init__(self, db_name: str = "camera_data.db"):
        """
        Initialize the MapConfigurationManager.
        
        Args:
            db_name: Path to the SQLite database file
        """
        self.db_name = db_name
    
    async def save_configuration(self, name: str, description: str = "", 
                               camera_positions: Optional[Dict[int, Dict[str, float]]] = None) -> ConfigurationOperation:
        """
        Save current map configuration with camera positions and coverage settings.
        
        Args:
            name: User-defined name for the configuration
            description: Optional description of the configuration
            camera_positions: Optional specific camera positions to save. If None, saves current positions from database
            
        Returns:
            ConfigurationOperation with success status and details
            
        Requirements addressed:
        - 5.1: Provide option to save current configuration when user makes changes
        - 5.2: Store all camera positions and coverage settings with user-defined name
        """
        try:
            # Validate input
            if not name or not name.strip():
                return ConfigurationOperation(
                    success=False,
                    message="❌ Configuration name cannot be empty",
                    error_details="Name validation failed"
                )
            
            name = name.strip()
            
            # Check if configuration name already exists
            existing_config = await self._get_configuration_by_name(name)
            if existing_config:
                return ConfigurationOperation(
                    success=False,
                    message=f"❌ Configuration '{name}' already exists",
                    error_details="Duplicate name"
                )
            
            # Get current camera positions if not provided
            if camera_positions is None:
                camera_positions = await self._get_current_camera_positions()
            
            if not camera_positions:
                return ConfigurationOperation(
                    success=False,
                    message="❌ No camera positions found to save",
                    error_details="No cameras with coordinates"
                )
            
            # Create configuration object
            now = datetime.now()
            config = MapConfiguration(
                id=None,
                name=name,
                description=description,
                camera_positions=camera_positions,
                created_at=now,
                updated_at=now
            )
            
            # Validate configuration data
            if not config.validate():
                return ConfigurationOperation(
                    success=False,
                    message="❌ Invalid configuration data",
                    error_details="Configuration validation failed"
                )
            
            # Save to database
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    INSERT INTO map_configurations (name, description, configuration_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    config.name,
                    config.description,
                    config.to_json(),
                    config.created_at.isoformat(),
                    config.updated_at.isoformat()
                ))
                
                config_id = cursor.lastrowid
                await db.commit()
            
            # Log the save operation
            await self._log_configuration_operation('save', config_id, name)
            
            return ConfigurationOperation(
                success=True,
                message=f"✅ Configuration '{name}' saved successfully",
                configuration_id=config_id
            )
            
        except Exception as e:
            return ConfigurationOperation(
                success=False,
                message=f"❌ Error saving configuration: {str(e)}",
                error_details=str(e)
            )
    
    async def load_configuration(self, config_id: int) -> ConfigurationOperation:
        """
        Load and apply a saved configuration to restore camera positions.
        
        Args:
            config_id: ID of the configuration to load
            
        Returns:
            ConfigurationOperation with success status and details
            
        Requirements addressed:
        - 5.3: Restore all camera positions and coverage areas to saved state
        - 5.4: Display error message and maintain current state if loading fails
        """
        try:
            # Get configuration from database
            config = await self._get_configuration_by_id(config_id)
            if not config:
                return ConfigurationOperation(
                    success=False,
                    message=f"❌ Configuration {config_id} not found",
                    error_details="Configuration does not exist"
                )
            
            # Validate configuration data
            if not config.validate():
                return ConfigurationOperation(
                    success=False,
                    message=f"❌ Configuration '{config.name}' contains invalid data",
                    error_details="Configuration validation failed"
                )
            
            # Get current camera positions for potential rollback
            original_positions = await self._get_current_camera_positions()
            
            # Apply configuration to database
            applied_count = 0
            failed_cameras = []
            
            async with aiosqlite.connect(self.db_name) as db:
                for camera_id, position in config.camera_positions.items():
                    try:
                        # Update camera position and coverage parameters
                        await db.execute("""
                            UPDATE cameras 
                            SET latitude = ?, longitude = ?, coverage_radius = ?, 
                                field_of_view_angle = ?, coverage_direction = ?
                            WHERE id = ?
                        """, (
                            position['latitude'],
                            position['longitude'],
                            position['coverage_radius'],
                            position['field_of_view_angle'],
                            position['coverage_direction'],
                            camera_id
                        ))
                        
                        # Check if update was successful
                        if db.total_changes > 0:
                            applied_count += 1
                        else:
                            failed_cameras.append(camera_id)
                            
                    except Exception as e:
                        failed_cameras.append(camera_id)
                        print(f"Error updating camera {camera_id}: {e}")
                
                await db.commit()
            
            # Update configuration's last used timestamp
            await self._update_configuration_timestamp(config_id)
            
            # Log the load operation
            await self._log_configuration_operation('load', config_id, config.name)
            
            # Prepare result message
            if applied_count == len(config.camera_positions):
                message = f"✅ Configuration '{config.name}' loaded successfully ({applied_count} cameras updated)"
            elif applied_count > 0:
                message = f"⚠️ Configuration '{config.name}' partially loaded ({applied_count}/{len(config.camera_positions)} cameras updated)"
            else:
                message = f"❌ Failed to load configuration '{config.name}' (no cameras updated)"
            
            return ConfigurationOperation(
                success=applied_count > 0,
                message=message,
                configuration_id=config_id,
                error_details=f"Failed cameras: {failed_cameras}" if failed_cameras else None
            )
            
        except Exception as e:
            return ConfigurationOperation(
                success=False,
                message=f"❌ Error loading configuration: {str(e)}",
                error_details=str(e)
            )
    
    async def list_configurations(self) -> List[ConfigurationSummary]:
        """
        List all available configurations with metadata.
        
        Returns:
            List of ConfigurationSummary objects
        """
        try:
            configurations = []
            
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, description, configuration_data, created_at, updated_at
                    FROM map_configurations
                    ORDER BY updated_at DESC
                """)
                
                rows = await cursor.fetchall()
                
                for row in rows:
                    config_id, name, description, config_data, created_at, updated_at = row
                    
                    # Parse configuration data to get camera count
                    try:
                        data = json.loads(config_data)
                        camera_count = len(data.get('camera_positions', {}))
                    except:
                        camera_count = 0
                    
                    summary = ConfigurationSummary(
                        id=config_id,
                        name=name,
                        description=description or "",
                        camera_count=camera_count,
                        created_at=datetime.fromisoformat(created_at),
                        updated_at=datetime.fromisoformat(updated_at)
                    )
                    
                    configurations.append(summary)
            
            return configurations
            
        except Exception as e:
            print(f"Error listing configurations: {e}")
            return []
    
    async def delete_configuration(self, config_id: int) -> ConfigurationOperation:
        """
        Delete a configuration with proper cleanup.
        
        Args:
            config_id: ID of the configuration to delete
            
        Returns:
            ConfigurationOperation with success status and details
        """
        try:
            # Check if configuration exists
            config = await self._get_configuration_by_id(config_id)
            if not config:
                return ConfigurationOperation(
                    success=False,
                    message=f"❌ Configuration {config_id} not found",
                    error_details="Configuration does not exist"
                )
            
            # Delete from database
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("DELETE FROM map_configurations WHERE id = ?", (config_id,))
                
                if db.total_changes == 0:
                    return ConfigurationOperation(
                        success=False,
                        message=f"❌ Failed to delete configuration {config_id}",
                        error_details="No rows affected"
                    )
                
                await db.commit()
            
            # Log the delete operation
            await self._log_configuration_operation('delete', config_id, config.name)
            
            return ConfigurationOperation(
                success=True,
                message=f"✅ Configuration '{config.name}' deleted successfully",
                configuration_id=config_id
            )
            
        except Exception as e:
            return ConfigurationOperation(
                success=False,
                message=f"❌ Error deleting configuration: {str(e)}",
                error_details=str(e)
            )
    
    async def update_configuration(self, config_id: int, name: Optional[str] = None, 
                                 description: Optional[str] = None,
                                 camera_positions: Optional[Dict[int, Dict[str, float]]] = None) -> ConfigurationOperation:
        """
        Update an existing configuration.
        
        Args:
            config_id: ID of the configuration to update
            name: New name (optional)
            description: New description (optional)
            camera_positions: New camera positions (optional)
            
        Returns:
            ConfigurationOperation with success status and details
        """
        try:
            # Get existing configuration
            config = await self._get_configuration_by_id(config_id)
            if not config:
                return ConfigurationOperation(
                    success=False,
                    message=f"❌ Configuration {config_id} not found",
                    error_details="Configuration does not exist"
                )
            
            # Update fields if provided
            if name is not None:
                name = name.strip()
                if not name:
                    return ConfigurationOperation(
                        success=False,
                        message="❌ Configuration name cannot be empty",
                        error_details="Name validation failed"
                    )
                
                # Check for duplicate name (excluding current config)
                existing = await self._get_configuration_by_name(name)
                if existing and existing.id != config_id:
                    return ConfigurationOperation(
                        success=False,
                        message=f"❌ Configuration name '{name}' already exists",
                        error_details="Duplicate name"
                    )
                
                config.name = name
            
            if description is not None:
                config.description = description
            
            if camera_positions is not None:
                config.camera_positions = camera_positions
            
            # Update timestamp
            config.updated_at = datetime.now()
            
            # Validate updated configuration
            if not config.validate():
                return ConfigurationOperation(
                    success=False,
                    message="❌ Invalid configuration data",
                    error_details="Configuration validation failed"
                )
            
            # Save to database
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    UPDATE map_configurations 
                    SET name = ?, description = ?, configuration_data = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    config.name,
                    config.description,
                    config.to_json(),
                    config.updated_at.isoformat(),
                    config_id
                ))
                
                await db.commit()
            
            # Log the update operation
            await self._log_configuration_operation('update', config_id, config.name)
            
            return ConfigurationOperation(
                success=True,
                message=f"✅ Configuration '{config.name}' updated successfully",
                configuration_id=config_id
            )
            
        except Exception as e:
            return ConfigurationOperation(
                success=False,
                message=f"❌ Error updating configuration: {str(e)}",
                error_details=str(e)
            )
    
    async def get_configuration_details(self, config_id: int) -> Optional[MapConfiguration]:
        """
        Get detailed configuration information.
        
        Args:
            config_id: ID of the configuration
            
        Returns:
            MapConfiguration object or None if not found
        """
        return await self._get_configuration_by_id(config_id)
    
    async def export_configuration(self, config_id: int) -> Optional[str]:
        """
        Export configuration as JSON string.
        
        Args:
            config_id: ID of the configuration to export
            
        Returns:
            JSON string of the configuration or None if not found
        """
        config = await self._get_configuration_by_id(config_id)
        if config:
            return config.to_json()
        return None
    
    async def import_configuration(self, json_data: str, name: str, description: str = "") -> ConfigurationOperation:
        """
        Import configuration from JSON data.
        
        Args:
            json_data: JSON string containing configuration data
            name: Name for the imported configuration
            description: Description for the imported configuration
            
        Returns:
            ConfigurationOperation with success status and details
        """
        try:
            # Parse JSON data
            data = json.loads(json_data)
            
            # Extract camera positions
            camera_positions = data.get('camera_positions', {})
            if not camera_positions:
                return ConfigurationOperation(
                    success=False,
                    message="❌ No camera positions found in import data",
                    error_details="Invalid import data"
                )
            
            # Convert string keys to integers
            camera_positions = {int(k): v for k, v in camera_positions.items()}
            
            # Save as new configuration
            return await self.save_configuration(name, description, camera_positions)
            
        except json.JSONDecodeError as e:
            return ConfigurationOperation(
                success=False,
                message="❌ Invalid JSON data",
                error_details=str(e)
            )
        except Exception as e:
            return ConfigurationOperation(
                success=False,
                message=f"❌ Error importing configuration: {str(e)}",
                error_details=str(e)
            )
    
    async def get_configuration_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about configurations.
        
        Returns:
            Dictionary with configuration statistics
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # Total configurations
                cursor = await db.execute("SELECT COUNT(*) FROM map_configurations")
                total_configs = (await cursor.fetchone())[0]
                
                # Most recent configuration
                cursor = await db.execute("""
                    SELECT name, updated_at FROM map_configurations 
                    ORDER BY updated_at DESC LIMIT 1
                """)
                recent_result = await cursor.fetchone()
                most_recent = recent_result[0] if recent_result else None
                
                # Average camera count
                cursor = await db.execute("SELECT configuration_data FROM map_configurations")
                configs = await cursor.fetchall()
                
                total_cameras = 0
                for (config_data,) in configs:
                    try:
                        data = json.loads(config_data)
                        total_cameras += len(data.get('camera_positions', {}))
                    except:
                        pass
                
                avg_cameras = total_cameras / total_configs if total_configs > 0 else 0
                
                return {
                    'total_configurations': total_configs,
                    'total_camera_positions': total_cameras,
                    'average_cameras_per_config': round(avg_cameras, 1),
                    'most_recent_configuration': most_recent,
                    'last_updated': datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"Error getting configuration statistics: {e}")
            return {
                'total_configurations': 0,
                'total_camera_positions': 0,
                'average_cameras_per_config': 0,
                'most_recent_configuration': None,
                'last_updated': datetime.now().isoformat(),
                'error': str(e)
            }
    
    async def _get_current_camera_positions(self) -> Dict[int, Dict[str, float]]:
        """Get current camera positions and coverage settings from database."""
        positions = {}
        
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, latitude, longitude, coverage_radius, field_of_view_angle, coverage_direction
                    FROM cameras
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                """)
                
                rows = await cursor.fetchall()
                
                for row in rows:
                    camera_id, lat, lon, radius, angle, direction = row
                    positions[camera_id] = {
                        'latitude': lat,
                        'longitude': lon,
                        'coverage_radius': radius or 50.0,
                        'field_of_view_angle': angle or 360.0,
                        'coverage_direction': direction or 0.0
                    }
        
        except Exception as e:
            print(f"Error getting current camera positions: {e}")
        
        return positions
    
    async def _get_configuration_by_id(self, config_id: int) -> Optional[MapConfiguration]:
        """Get configuration by ID."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, description, configuration_data, created_at, updated_at
                    FROM map_configurations WHERE id = ?
                """, (config_id,))
                
                row = await cursor.fetchone()
                
                if row:
                    config_id, name, description, config_data, created_at, updated_at = row
                    return MapConfiguration.from_json(config_id, name, description, config_data)
        
        except Exception as e:
            print(f"Error getting configuration by ID: {e}")
        
        return None
    
    async def _get_configuration_by_name(self, name: str) -> Optional[MapConfiguration]:
        """Get configuration by name."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, description, configuration_data, created_at, updated_at
                    FROM map_configurations WHERE name = ?
                """, (name,))
                
                row = await cursor.fetchone()
                
                if row:
                    config_id, name, description, config_data, created_at, updated_at = row
                    return MapConfiguration.from_json(config_id, name, description, config_data)
        
        except Exception as e:
            print(f"Error getting configuration by name: {e}")
        
        return None
    
    async def _update_configuration_timestamp(self, config_id: int):
        """Update the timestamp of a configuration."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    UPDATE map_configurations SET updated_at = ? WHERE id = ?
                """, (datetime.now().isoformat(), config_id))
                await db.commit()
        except Exception as e:
            print(f"Error updating configuration timestamp: {e}")
    
    async def _log_configuration_operation(self, operation: str, config_id: int, config_name: str):
        """Log configuration operations to action log."""
        try:
            details = {
                'operation': operation,
                'configuration_id': config_id,
                'configuration_name': config_name,
                'timestamp': datetime.now().isoformat()
            }
            
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    INSERT INTO action_log (timestamp, action_type, table_name, record_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    f'configuration_{operation}',
                    'map_configurations',
                    config_id,
                    json.dumps(details)
                ))
                await db.commit()
        except Exception as e:
            print(f"Error logging configuration operation: {e}")


# Utility functions for working with map configurations
async def create_configuration_manager(db_name: str = "camera_data.db") -> MapConfigurationManager:
    """Create and initialize a MapConfigurationManager instance."""
    return MapConfigurationManager(db_name=db_name)


def format_configuration_summary(configs: List[ConfigurationSummary]) -> str:
    """Format configuration list as a readable summary."""
    if not configs:
        return "📋 No configurations found"
    
    summary = f"📋 Found {len(configs)} configuration(s):\n"
    
    for config in configs:
        age = datetime.now() - config.updated_at
        age_str = f"{age.days}d ago" if age.days > 0 else f"{age.seconds//3600}h ago"
        
        summary += f"  • {config.name} ({config.camera_count} cameras) - {age_str}\n"
        if config.description:
            summary += f"    {config.description}\n"
    
    return summary


def validate_configuration_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate configuration data structure.
    
    Args:
        data: Configuration data dictionary
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Check required fields
    if 'camera_positions' not in data:
        errors.append("Missing 'camera_positions' field")
        return False, errors
    
    camera_positions = data['camera_positions']
    
    if not isinstance(camera_positions, dict):
        errors.append("'camera_positions' must be a dictionary")
        return False, errors
    
    # Validate each camera position
    for camera_id, position in camera_positions.items():
        try:
            camera_id_int = int(camera_id)
        except ValueError:
            errors.append(f"Invalid camera ID: {camera_id}")
            continue
        
        if not isinstance(position, dict):
            errors.append(f"Camera {camera_id} position must be a dictionary")
            continue
        
        # Check required position fields
        required_fields = ['latitude', 'longitude', 'coverage_radius', 'field_of_view_angle', 'coverage_direction']
        for field in required_fields:
            if field not in position:
                errors.append(f"Camera {camera_id} missing field: {field}")
            else:
                try:
                    float(position[field])
                except (ValueError, TypeError):
                    errors.append(f"Camera {camera_id} invalid {field}: {position[field]}")
        
        # Validate coordinate ranges
        if 'latitude' in position:
            lat = position['latitude']
            if not isinstance(lat, (int, float)) or not (-90 <= lat <= 90):
                errors.append(f"Camera {camera_id} invalid latitude: {lat}")
        
        if 'longitude' in position:
            lon = position['longitude']
            if not isinstance(lon, (int, float)) or not (-180 <= lon <= 180):
                errors.append(f"Camera {camera_id} invalid longitude: {lon}")
    
    return len(errors) == 0, errors