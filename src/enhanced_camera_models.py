"""
Enhanced Camera Data Models for Interactive Camera Mapping

This module provides comprehensive data models for cameras with coverage parameters,
map marker configurations, validation, and serialization capabilities.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from .coverage_calculator import CoverageCalculator


@dataclass
class EnhancedCamera:
    """Enhanced camera model with coverage parameters and map functionality."""
    id: int
    name: str
    location: str
    ip_address: str
    mac_address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coverage_radius: float = 50.0
    field_of_view_angle: float = 360.0
    coverage_direction: float = 0.0
    has_memory_card: bool = False
    memory_card_last_reset: Optional[str] = None
    dvr_id: Optional[int] = None
    locational_group: Optional[str] = None
    date_installed: Optional[str] = None
    custom_name: Optional[str] = None
    address: Optional[str] = None
    is_online: bool = False
    last_ping_time: Optional[datetime] = None
    
    def get_display_name(self) -> str:
        """Get display name (custom name or default based on camera name)."""
        if self.custom_name and self.custom_name.strip():
            return self.custom_name.strip()
        return self.name or f"Camera-{self.ip_address.replace('.', '-')}"
    
    def to_map_marker(self) -> Dict[str, Any]:
        """Convert to map marker configuration for Folium maps."""
        display_name = self.get_display_name()
        return {
            'id': self.id,
            'name': self.name,
            'display_name': display_name,
            'location': self.location,
            'ip_address': self.ip_address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_online': self.is_online,
            'marker_color': self._get_marker_color(),
            'marker_icon': self._get_marker_icon(),
            'popup_content': self._generate_popup_content(),
            'tooltip': f"📹 {display_name}",
            'coverage_radius': self.coverage_radius,
            'field_of_view_angle': self.field_of_view_angle,
            'coverage_direction': self.coverage_direction
        }
    
    def get_coverage_geometry(self) -> Optional[Dict[str, Any]]:
        """Get coverage area geometry for map display."""
        if not self.latitude or not self.longitude:
            return None
        
        camera_dict = {
            'id': self.id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'coverage_radius': self.coverage_radius,
            'field_of_view_angle': self.field_of_view_angle,
            'coverage_direction': self.coverage_direction
        }
        
        return CoverageCalculator.get_coverage_area_geojson(camera_dict)
    
    def get_coverage_coordinates(self) -> Optional[List[List[float]]]:
        """Get coverage area coordinates as a list of [lat, lon] pairs."""
        if not self.latitude or not self.longitude:
            return None
        
        try:
            if self.field_of_view_angle >= 360.0:
                return CoverageCalculator.calculate_circular_coverage(
                    self.latitude, self.longitude, self.coverage_radius
                )
            else:
                return CoverageCalculator.calculate_directional_coverage(
                    self.latitude, self.longitude, self.coverage_radius,
                    self.coverage_direction, self.field_of_view_angle
                )
        except ValueError:
            return None
    
    def _generate_popup_content(self) -> str:
        """Generate HTML popup content for map marker."""
        status_icon = "✅" if self.is_online else "❌"
        status_text = "Online" if self.is_online else "Offline"
        
        coverage_type = "Circular" if self.field_of_view_angle >= 360.0 else "Directional"
        display_name = self.get_display_name()
        
        popup_html = f"""
        <div style="width: 280px; font-family: Arial, sans-serif;">
            <h4 style="margin: 0 0 10px 0; color: #333;">📹 {display_name}</h4>
            <table style="width: 100%; font-size: 12px;">
        """
        
        # Show both custom name and original name if they differ
        if self.custom_name and self.custom_name.strip() and self.custom_name.strip() != self.name:
            popup_html += f"""
                <tr><td><strong>Original Name:</strong></td><td>{self.name}</td></tr>
            """
        
        popup_html += f"""
                <tr><td><strong>Location:</strong></td><td>{self.location}</td></tr>
                <tr><td><strong>IP Address:</strong></td><td>{self.ip_address}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{status_icon} {status_text}</td></tr>
                <tr><td><strong>Coverage Type:</strong></td><td>{coverage_type}</td></tr>
                <tr><td><strong>Coverage Radius:</strong></td><td>{self.coverage_radius}m</td></tr>
        """
        
        if self.field_of_view_angle < 360.0:
            popup_html += f"""
                <tr><td><strong>Field of View:</strong></td><td>{self.field_of_view_angle}°</td></tr>
                <tr><td><strong>Direction:</strong></td><td>{self.coverage_direction}°</td></tr>
            """
        
        popup_html += f"""
                <tr><td><strong>Memory Card:</strong></td><td>{'Yes' if self.has_memory_card else 'No'}</td></tr>
        """
        
        # Show address if available
        if self.address:
            popup_html += f"""
                <tr><td><strong>Address:</strong></td><td>{self.address}</td></tr>
            """
        
        popup_html += """
            </table>
        </div>
        """
        
        return popup_html
    
    def _get_marker_color(self) -> str:
        """Get marker color based on camera status."""
        return 'green' if self.is_online else 'red'
    
    def _get_marker_icon(self) -> str:
        """Get marker icon based on camera type."""
        return 'video-camera'
    
    def update_coordinates(self, latitude: float, longitude: float) -> bool:
        """Update camera coordinates with validation."""
        if self.validate_coordinates(latitude, longitude):
            self.latitude = latitude
            self.longitude = longitude
            return True
        return False
    
    def update_coverage_parameters(self, radius: float, angle: float, direction: float) -> bool:
        """Update coverage parameters with validation."""
        if self.validate_coverage_parameters(radius, angle, direction):
            self.coverage_radius = radius
            self.field_of_view_angle = angle
            self.coverage_direction = direction
            return True
        return False
    
    def update_connectivity_status(self, is_online: bool, ping_time: Optional[datetime] = None):
        """Update camera connectivity status."""
        self.is_online = is_online
        self.last_ping_time = ping_time or datetime.now()
    
    @staticmethod
    def validate_coordinates(latitude: Union[float, str, None], longitude: Union[float, str, None]) -> bool:
        """Validate latitude and longitude values."""
        try:
            if latitude is None or longitude is None:
                return True  # Allow None values
            
            lat = float(latitude)
            lon = float(longitude)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_coverage_parameters(coverage_radius: Union[float, str], 
                                   field_of_view_angle: Union[float, str], 
                                   coverage_direction: Union[float, str]) -> bool:
        """Validate camera coverage parameters."""
        try:
            radius = float(coverage_radius)
            angle = float(field_of_view_angle)
            direction = float(coverage_direction)
            
            # Validate coverage radius (1m to 10000m)
            if not (1.0 <= radius <= 10000.0):
                return False
            
            # Validate field of view angle (1 to 360 degrees)
            if not (1.0 <= angle <= 360.0):
                return False
            
            # Validate coverage direction (0 to 359.999 degrees)
            if not (0.0 <= direction < 360.0):
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_ip_address(ip_address: str) -> bool:
        """Validate IP address format."""
        import re
        pattern = r"^((\d{1,3})\.){3}(\d{1,3})$"
        if re.match(pattern, ip_address):
            parts = ip_address.split(".")
            return all(0 <= int(part) <= 255 for part in parts)
        return False
    
    @staticmethod
    def validate_mac_address(mac_address: str) -> bool:
        """Validate MAC address format."""
        import re
        pattern = r"^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$"
        return bool(re.match(pattern, mac_address))
    
    @staticmethod
    def validate_date(date_str: Optional[str]) -> bool:
        """Validate date format (YYYY-MM-DD)."""
        if not date_str:
            return True
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_custom_name(custom_name: Optional[str]) -> bool:
        """Validate custom name format and length."""
        if not custom_name:
            return True  # Custom name is optional
        
        # Check length (1-100 characters)
        if len(custom_name.strip()) < 1 or len(custom_name.strip()) > 100:
            return False
        
        # Check for invalid characters (basic validation)
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', custom_name.strip()):
            return False
        
        return True
    
    def validate_all_fields(self) -> Dict[str, bool]:
        """Validate all camera fields and return validation results."""
        return {
            'coordinates': self.validate_coordinates(self.latitude, self.longitude),
            'coverage_parameters': self.validate_coverage_parameters(
                self.coverage_radius, self.field_of_view_angle, self.coverage_direction
            ),
            'ip_address': self.validate_ip_address(self.ip_address),
            'mac_address': self.validate_mac_address(self.mac_address),
            'date_installed': self.validate_date(self.date_installed),
            'memory_card_reset': self.validate_date(self.memory_card_last_reset),
            'custom_name': self.validate_custom_name(self.custom_name)
        }
    
    def is_valid(self) -> bool:
        """Check if all camera fields are valid."""
        validation_results = self.validate_all_fields()
        return all(validation_results.values())
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors for this camera."""
        validation_results = self.validate_all_fields()
        errors = []
        
        if not validation_results['coordinates']:
            errors.append("Invalid coordinates (latitude must be -90 to 90, longitude must be -180 to 180)")
        
        if not validation_results['coverage_parameters']:
            errors.append("Invalid coverage parameters (radius: 1-10000m, angle: 1-360°, direction: 0-359°)")
        
        if not validation_results['ip_address']:
            errors.append("Invalid IP address format")
        
        if not validation_results['mac_address']:
            errors.append("Invalid MAC address format")
        
        if not validation_results['date_installed']:
            errors.append("Invalid installation date format (use YYYY-MM-DD)")
        
        if not validation_results['memory_card_reset']:
            errors.append("Invalid memory card reset date format (use YYYY-MM-DD)")
        
        if not validation_results['custom_name']:
            errors.append("Invalid custom name (1-100 characters, alphanumeric, spaces, hyphens, underscores, dots only)")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert camera to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if self.last_ping_time:
            data['last_ping_time'] = self.last_ping_time.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert camera to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedCamera':
        """Create EnhancedCamera from dictionary."""
        # Handle datetime conversion
        if 'last_ping_time' in data and data['last_ping_time']:
            if isinstance(data['last_ping_time'], str):
                data['last_ping_time'] = datetime.fromisoformat(data['last_ping_time'])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'EnhancedCamera':
        """Create EnhancedCamera from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'EnhancedCamera':
        """Create EnhancedCamera from database row tuple."""
        # Handle different row lengths for backward compatibility
        defaults = {
            'coverage_radius': 50.0,
            'field_of_view_angle': 360.0,
            'coverage_direction': 0.0
        }
        
        try:
            return cls(
                id=row[0],
                location=row[1],
                name=row[2],
                mac_address=row[3],
                ip_address=row[4],
                locational_group=row[5] if len(row) > 5 else None,
                date_installed=row[6] if len(row) > 6 else None,
                dvr_id=row[7] if len(row) > 7 else None,
                latitude=row[8] if len(row) > 8 else None,
                longitude=row[9] if len(row) > 9 else None,
                has_memory_card=bool(row[10]) if len(row) > 10 else False,
                memory_card_last_reset=row[11] if len(row) > 11 else None,
                coverage_radius=row[12] if len(row) > 12 else defaults['coverage_radius'],
                field_of_view_angle=row[13] if len(row) > 13 else defaults['field_of_view_angle'],
                coverage_direction=row[14] if len(row) > 14 else defaults['coverage_direction'],
                custom_name=row[15] if len(row) > 15 else None,
                address=row[16] if len(row) > 16 else None
            )
        except IndexError as e:
            raise ValueError(f"Invalid database row format: {e}")
    
    def to_db_tuple(self) -> tuple:
        """Convert camera to tuple for database insertion/update."""
        return (
            self.location,
            self.name,
            self.mac_address,
            self.ip_address,
            self.locational_group,
            self.date_installed,
            self.dvr_id,
            self.latitude,
            self.longitude,
            self.has_memory_card,
            self.memory_card_last_reset,
            self.coverage_radius,
            self.field_of_view_angle,
            self.coverage_direction,
            self.custom_name,
            self.address
        )
    
    def calculate_coverage_area_size(self) -> Optional[float]:
        """Calculate the coverage area size in square meters."""
        coordinates = self.get_coverage_coordinates()
        if not coordinates:
            return None
        
        return CoverageCalculator.calculate_coverage_area_size(coordinates)
    
    def find_overlaps_with(self, other_cameras: List['EnhancedCamera']) -> List[Dict[str, Any]]:
        """Find coverage overlaps with other cameras."""
        if not self.latitude or not self.longitude:
            return []
        
        cameras_data = [self.to_dict()]
        for camera in other_cameras:
            if camera.latitude and camera.longitude and camera.id != self.id:
                cameras_data.append(camera.to_dict())
        
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras_data)
        
        # Filter overlaps that involve this camera
        relevant_overlaps = []
        for overlap in overlaps:
            if overlap.camera1_id == self.id or overlap.camera2_id == self.id:
                relevant_overlaps.append({
                    'other_camera_id': overlap.camera2_id if overlap.camera1_id == self.id else overlap.camera1_id,
                    'distance': overlap.distance,
                    'overlap_distance': overlap.overlap_distance,
                    'overlap_percentage': overlap.overlap_percentage
                })
        
        return relevant_overlaps
    
    def __str__(self) -> str:
        """String representation of the camera."""
        status = "Online" if self.is_online else "Offline"
        coords = f"({self.latitude}, {self.longitude})" if self.latitude and self.longitude else "No coordinates"
        display_name = self.get_display_name()
        return f"Camera {self.id}: {display_name} at {self.location} [{status}] {coords}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the camera."""
        display_name = self.get_display_name()
        return (f"EnhancedCamera(id={self.id}, display_name='{display_name}', "
                f"location='{self.location}', ip='{self.ip_address}', "
                f"coords=({self.latitude}, {self.longitude}), "
                f"coverage={self.coverage_radius}m, online={self.is_online})")


@dataclass
class MapConfiguration:
    """Map configuration model for saving/loading camera layouts."""
    id: Optional[int]
    name: str
    description: str
    camera_positions: Dict[int, Dict[str, float]]  # camera_id -> {lat, lon, coverage params}
    created_at: datetime
    updated_at: datetime
    
    def to_json(self) -> str:
        """Serialize configuration to JSON."""
        return json.dumps({
            'name': self.name,
            'description': self.description,
            'camera_positions': self.camera_positions,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'camera_positions': self.camera_positions,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_json(cls, config_id: Optional[int], name: str, description: str, json_data: str) -> 'MapConfiguration':
        """Deserialize configuration from JSON."""
        data = json.loads(json_data)
        
        # Convert string keys to integers for camera_positions
        camera_positions = {}
        for key, value in data['camera_positions'].items():
            camera_positions[int(key)] = value
        
        return cls(
            id=config_id,
            name=name,
            description=description,
            camera_positions=camera_positions,
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MapConfiguration':
        """Create MapConfiguration from dictionary."""
        return cls(
            id=data.get('id'),
            name=data['name'],
            description=data['description'],
            camera_positions=data['camera_positions'],
            created_at=datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at'],
            updated_at=datetime.fromisoformat(data['updated_at']) if isinstance(data['updated_at'], str) else data['updated_at']
        )
    
    def apply_to_cameras(self, cameras: List[EnhancedCamera]) -> List[EnhancedCamera]:
        """Apply configuration to list of cameras."""
        updated_cameras = []
        for camera in cameras:
            if camera.id in self.camera_positions:
                pos = self.camera_positions[camera.id]
                camera.latitude = pos.get('latitude', camera.latitude)
                camera.longitude = pos.get('longitude', camera.longitude)
                camera.coverage_radius = pos.get('coverage_radius', camera.coverage_radius)
                camera.field_of_view_angle = pos.get('field_of_view_angle', camera.field_of_view_angle)
                camera.coverage_direction = pos.get('coverage_direction', camera.coverage_direction)
            updated_cameras.append(camera)
        return updated_cameras
    
    def add_camera_position(self, camera: EnhancedCamera):
        """Add or update camera position in configuration."""
        if camera.latitude is not None and camera.longitude is not None:
            self.camera_positions[camera.id] = {
                'latitude': camera.latitude,
                'longitude': camera.longitude,
                'coverage_radius': camera.coverage_radius,
                'field_of_view_angle': camera.field_of_view_angle,
                'coverage_direction': camera.coverage_direction
            }
            self.updated_at = datetime.now()
    
    def remove_camera_position(self, camera_id: int):
        """Remove camera position from configuration."""
        if camera_id in self.camera_positions:
            del self.camera_positions[camera_id]
            self.updated_at = datetime.now()
    
    def get_camera_count(self) -> int:
        """Get number of cameras in configuration."""
        return len(self.camera_positions)
    
    def validate(self) -> bool:
        """Validate configuration data."""
        if not self.name or not isinstance(self.name, str):
            return False
        
        if not isinstance(self.camera_positions, dict):
            return False
        
        # Validate each camera position
        for camera_id, position in self.camera_positions.items():
            if not isinstance(camera_id, int):
                return False
            
            required_keys = ['latitude', 'longitude', 'coverage_radius', 'field_of_view_angle', 'coverage_direction']
            if not all(key in position for key in required_keys):
                return False
            
            # Validate coordinate and coverage parameter ranges
            if not EnhancedCamera.validate_coordinates(position['latitude'], position['longitude']):
                return False
            
            if not EnhancedCamera.validate_coverage_parameters(
                position['coverage_radius'], 
                position['field_of_view_angle'], 
                position['coverage_direction']
            ):
                return False
        
        return True
    
    def __str__(self) -> str:
        """String representation of the configuration."""
        return f"MapConfiguration '{self.name}': {self.get_camera_count()} cameras"
    
    def __repr__(self) -> str:
        """Detailed string representation of the configuration."""
        return (f"MapConfiguration(id={self.id}, name='{self.name}', "
                f"cameras={self.get_camera_count()}, "
                f"created={self.created_at.strftime('%Y-%m-%d %H:%M')})")


# Utility functions for working with enhanced camera models
def create_camera_from_form_data(form_data: Dict[str, Any]) -> EnhancedCamera:
    """Create EnhancedCamera from form data with proper type conversion."""
    return EnhancedCamera(
        id=int(form_data.get('id', 0)),
        name=str(form_data.get('name', '')),
        location=str(form_data.get('location', '')),
        ip_address=str(form_data.get('ip_address', '')),
        mac_address=str(form_data.get('mac_address', '')),
        latitude=float(form_data['latitude']) if form_data.get('latitude') else None,
        longitude=float(form_data['longitude']) if form_data.get('longitude') else None,
        coverage_radius=float(form_data.get('coverage_radius', 50.0)),
        field_of_view_angle=float(form_data.get('field_of_view_angle', 360.0)),
        coverage_direction=float(form_data.get('coverage_direction', 0.0)),
        has_memory_card=bool(form_data.get('has_memory_card', False)),
        memory_card_last_reset=form_data.get('memory_card_last_reset'),
        dvr_id=int(form_data['dvr_id']) if form_data.get('dvr_id') else None,
        locational_group=form_data.get('locational_group'),
        date_installed=form_data.get('date_installed'),
        custom_name=form_data.get('custom_name'),
        address=form_data.get('address')
    )


def validate_camera_batch(cameras: List[EnhancedCamera]) -> Dict[str, Any]:
    """Validate a batch of cameras and return summary results."""
    total_cameras = len(cameras)
    valid_cameras = 0
    validation_errors = {}
    
    for camera in cameras:
        if camera.is_valid():
            valid_cameras += 1
        else:
            validation_errors[camera.id] = camera.get_validation_errors()
    
    return {
        'total_cameras': total_cameras,
        'valid_cameras': valid_cameras,
        'invalid_cameras': total_cameras - valid_cameras,
        'validation_errors': validation_errors,
        'success_rate': (valid_cameras / total_cameras) * 100 if total_cameras > 0 else 0
    }


def export_cameras_to_json(cameras: List[EnhancedCamera]) -> str:
    """Export list of cameras to JSON format."""
    camera_data = [camera.to_dict() for camera in cameras]
    return json.dumps(camera_data, indent=2)


def import_cameras_from_json(json_str: str) -> List[EnhancedCamera]:
    """Import cameras from JSON format."""
    camera_data = json.loads(json_str)
    return [EnhancedCamera.from_dict(data) for data in camera_data]