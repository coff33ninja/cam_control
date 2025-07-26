"""
DVR Management System for Interactive Camera Mapping

This module provides comprehensive DVR data models and management functionality
including CRUD operations, location inheritance, and camera assignment management.
"""

import json
import aiosqlite
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Tuple
from .enhanced_camera_models import EnhancedCamera


@dataclass
class DVR:
    """DVR data model with custom naming and location fields."""
    id: int
    custom_name: str
    ip_address: str
    dvr_type: str = "Unknown"
    location: str = ""
    mac_address: str = ""
    storage_capacity: str = ""
    date_installed: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    is_online: bool = False
    last_ping_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_display_name(self) -> str:
        """Get display name (custom name or default based on IP)."""
        if self.custom_name and self.custom_name.strip():
            return self.custom_name.strip()
        return f"DVR-{self.ip_address.replace('.', '-')}"
    
    def to_map_marker(self) -> Dict[str, Any]:
        """Convert DVR to map marker configuration."""
        return {
            'id': self.id,
            'name': self.get_display_name(),
            'location': self.location,
            'ip_address': self.ip_address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'is_online': self.is_online,
            'marker_color': self._get_marker_color(),
            'marker_icon': self._get_marker_icon(),
            'popup_content': self._generate_popup_content(),
            'tooltip': f"📺 {self.get_display_name()}",
            'device_type': 'dvr'
        }
    
    def _generate_popup_content(self) -> str:
        """Generate HTML popup content for DVR map marker."""
        status_icon = "✅" if self.is_online else "❌"
        status_text = "Online" if self.is_online else "Offline"
        
        popup_html = f"""
        <div style="width: 280px; font-family: Arial, sans-serif;">
            <h4 style="margin: 0 0 10px 0; color: #333;">📺 {self.get_display_name()}</h4>
            <table style="width: 100%; font-size: 12px;">
                <tr><td><strong>Type:</strong></td><td>{self.dvr_type}</td></tr>
                <tr><td><strong>Location:</strong></td><td>{self.location}</td></tr>
                <tr><td><strong>IP Address:</strong></td><td>{self.ip_address}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{status_icon} {status_text}</td></tr>
                <tr><td><strong>Storage:</strong></td><td>{self.storage_capacity or 'Unknown'}</td></tr>
        """
        
        if self.address:
            popup_html += f"""
                <tr><td><strong>Address:</strong></td><td>{self.address}</td></tr>
            """
        
        if self.date_installed:
            popup_html += f"""
                <tr><td><strong>Installed:</strong></td><td>{self.date_installed}</td></tr>
            """
        
        popup_html += """
            </table>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                <button onclick="openDVRLocation({id})" style="background: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 11px;">📍 View Location</button>
            </div>
        </div>
        """.format(id=self.id)
        
        return popup_html
    
    def _get_marker_color(self) -> str:
        """Get marker color based on DVR status."""
        return 'green' if self.is_online else 'red'
    
    def _get_marker_icon(self) -> str:
        """Get marker icon for DVR."""
        return 'server'
    
    def update_coordinates(self, latitude: float, longitude: float) -> bool:
        """Update DVR coordinates with validation."""
        if self.validate_coordinates(latitude, longitude):
            self.latitude = latitude
            self.longitude = longitude
            self.updated_at = datetime.now()
            return True
        return False
    
    def update_connectivity_status(self, is_online: bool, ping_time: Optional[datetime] = None):
        """Update DVR connectivity status."""
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
    
    def validate_all_fields(self) -> Dict[str, bool]:
        """Validate all DVR fields and return validation results."""
        return {
            'coordinates': self.validate_coordinates(self.latitude, self.longitude),
            'ip_address': self.validate_ip_address(self.ip_address),
            'mac_address': self.validate_mac_address(self.mac_address) if self.mac_address else True,
            'date_installed': self.validate_date(self.date_installed)
        }
    
    def is_valid(self) -> bool:
        """Check if all DVR fields are valid."""
        validation_results = self.validate_all_fields()
        return all(validation_results.values())
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors for this DVR."""
        validation_results = self.validate_all_fields()
        errors = []
        
        if not validation_results['coordinates']:
            errors.append("Invalid coordinates (latitude must be -90 to 90, longitude must be -180 to 180)")
        
        if not validation_results['ip_address']:
            errors.append("Invalid IP address format")
        
        if not validation_results['mac_address']:
            errors.append("Invalid MAC address format")
        
        if not validation_results['date_installed']:
            errors.append("Invalid installation date format (use YYYY-MM-DD)")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert DVR to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime to string for JSON serialization
        if self.last_ping_time:
            data['last_ping_time'] = self.last_ping_time.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert DVR to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DVR':
        """Create DVR from dictionary."""
        # Handle datetime conversion
        for field in ['last_ping_time', 'created_at', 'updated_at']:
            if field in data and data[field]:
                if isinstance(data[field], str):
                    data[field] = datetime.fromisoformat(data[field])
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'DVR':
        """Create DVR from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'DVR':
        """Create DVR from database row tuple."""
        try:
            return cls(
                id=row[0],
                custom_name=row[2] if len(row) > 2 and row[2] else "",  # custom_name is now at index 2
                dvr_type=row[3] if len(row) > 3 else "Unknown",
                location=row[4] if len(row) > 4 else "",
                ip_address=row[5] if len(row) > 5 else "",
                mac_address=row[6] if len(row) > 6 else "",
                storage_capacity=row[7] if len(row) > 7 else "",
                date_installed=row[8] if len(row) > 8 else None,
                latitude=row[9] if len(row) > 9 else None,
                longitude=row[10] if len(row) > 10 else None,
                address=row[11] if len(row) > 11 else None,
                created_at=datetime.fromisoformat(row[12]) if len(row) > 12 and row[12] else datetime.now(),
                updated_at=datetime.fromisoformat(row[13]) if len(row) > 13 and row[13] else datetime.now()
            )
        except IndexError as e:
            raise ValueError(f"Invalid database row format: {e}")
    
    def to_db_tuple(self) -> tuple:
        """Convert DVR to tuple for database insertion/update."""
        return (
            self.custom_name,
            self.dvr_type,
            self.location,
            self.ip_address,
            self.mac_address,
            self.storage_capacity,
            self.date_installed,
            self.latitude,
            self.longitude,
            self.address,
            self.created_at.isoformat() if self.created_at else datetime.now().isoformat(),
            self.updated_at.isoformat() if self.updated_at else datetime.now().isoformat()
        )
    
    def __str__(self) -> str:
        """String representation of the DVR."""
        status = "Online" if self.is_online else "Offline"
        coords = f"({self.latitude}, {self.longitude})" if self.latitude and self.longitude else "No coordinates"
        return f"DVR {self.id}: {self.get_display_name()} at {self.location} [{status}] {coords}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the DVR."""
        return (f"DVR(id={self.id}, name='{self.get_display_name()}', "
                f"location='{self.location}', ip='{self.ip_address}', "
                f"coords=({self.latitude}, {self.longitude}), online={self.is_online})")


class DVRManager:
    """DVR management system with CRUD operations and location inheritance."""
    
    def __init__(self, db_path: str = "camera_data.db"):
        """Initialize DVR manager with database connection."""
        self.db_path = db_path
    
    async def create_dvr(self, custom_name: str, ip_address: str, dvr_type: str = "Unknown",
                        location: str = "", mac_address: str = "", storage_capacity: str = "",
                        date_installed: str = None, address: str = None, 
                        latitude: float = None, longitude: float = None) -> Dict[str, Any]:
        """Create new DVR with location information."""
        try:
            # Validate required fields
            if not custom_name or not ip_address:
                return {
                    'success': False,
                    'message': "Custom name and IP address are required",
                    'dvr_id': None
                }
            
            # Validate IP address format
            if not DVR.validate_ip_address(ip_address):
                return {
                    'success': False,
                    'message': "Invalid IP address format",
                    'dvr_id': None
                }
            
            # Validate MAC address if provided
            if mac_address and not DVR.validate_mac_address(mac_address):
                return {
                    'success': False,
                    'message': "Invalid MAC address format",
                    'dvr_id': None
                }
            
            # Validate coordinates if provided
            if not DVR.validate_coordinates(latitude, longitude):
                return {
                    'success': False,
                    'message': "Invalid latitude/longitude values",
                    'dvr_id': None
                }
            
            # Validate date if provided
            if not DVR.validate_date(date_installed):
                return {
                    'success': False,
                    'message': "Invalid date format (use YYYY-MM-DD)",
                    'dvr_id': None
                }
            
            async with aiosqlite.connect(self.db_path) as db:
                # Check for duplicate IP address
                cursor = await db.execute(
                    "SELECT id FROM dvrs WHERE ip_address = ?", 
                    (ip_address,)
                )
                if await cursor.fetchone():
                    return {
                        'success': False,
                        'message': "IP address already exists",
                        'dvr_id': None
                    }
                
                # Check for duplicate MAC address if provided
                if mac_address:
                    cursor = await db.execute(
                        "SELECT id FROM dvrs WHERE mac_address = ?", 
                        (mac_address,)
                    )
                    if await cursor.fetchone():
                        return {
                            'success': False,
                            'message': "MAC address already exists",
                            'dvr_id': None
                        }
                
                # Insert new DVR
                now = datetime.now().isoformat()
                # Use custom_name as name if provided, otherwise generate from IP
                dvr_name = custom_name if custom_name else f"DVR-{ip_address.replace('.', '-')}"
                
                cursor = await db.execute("""
                    INSERT INTO dvrs (name, custom_name, dvr_type, location, ip_address, mac_address, 
                                    storage_capacity, date_installed, latitude, longitude, address,
                                    created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    dvr_name, custom_name, dvr_type, location, ip_address, mac_address,
                    storage_capacity, date_installed, latitude, longitude, address,
                    now, now
                ))
                
                dvr_id = cursor.lastrowid
                await db.commit()
                
                return {
                    'success': True,
                    'message': f"DVR '{custom_name}' created successfully",
                    'dvr_id': dvr_id
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error creating DVR: {str(e)}",
                'dvr_id': None
            }
    
    async def get_dvr(self, dvr_id: int) -> Optional[DVR]:
        """Get DVR by ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, name, custom_name, dvr_type, location, ip_address, mac_address,
                           storage_capacity, date_installed, latitude, longitude, address,
                           created_at, updated_at
                    FROM dvrs WHERE id = ?
                """, (dvr_id,))
                
                row = await cursor.fetchone()
                if row:
                    return DVR.from_db_row(row)
                return None
                
        except Exception as e:
            print(f"Error getting DVR {dvr_id}: {e}")
            return None
    
    async def get_all_dvrs(self) -> List[DVR]:
        """Get all DVRs from database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, name, custom_name, dvr_type, location, ip_address, mac_address,
                           storage_capacity, date_installed, latitude, longitude, address,
                           created_at, updated_at
                    FROM dvrs ORDER BY COALESCE(NULLIF(custom_name, ''), name)
                """)
                
                rows = await cursor.fetchall()
                return [DVR.from_db_row(row) for row in rows]
                
        except Exception as e:
            print(f"Error getting all DVRs: {e}")
            return []
    
    async def update_dvr(self, dvr_id: int, **kwargs) -> Dict[str, Any]:
        """Update DVR with provided fields."""
        try:
            dvr = await self.get_dvr(dvr_id)
            if not dvr:
                return {
                    'success': False,
                    'message': f"DVR with ID {dvr_id} not found"
                }
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(dvr, field):
                    setattr(dvr, field, value)
            
            dvr.updated_at = datetime.now()
            
            # Validate updated DVR
            if not dvr.is_valid():
                errors = dvr.get_validation_errors()
                return {
                    'success': False,
                    'message': f"Validation errors: {', '.join(errors)}"
                }
            
            async with aiosqlite.connect(self.db_path) as db:
                # Update name field to match custom_name if provided
                dvr_name = dvr.custom_name if dvr.custom_name else f"DVR-{dvr.ip_address.replace('.', '-')}"
                
                await db.execute("""
                    UPDATE dvrs SET name = ?, custom_name = ?, dvr_type = ?, location = ?, ip_address = ?,
                                  mac_address = ?, storage_capacity = ?, date_installed = ?,
                                  latitude = ?, longitude = ?, address = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    dvr_name, dvr.custom_name, dvr.dvr_type, dvr.location, dvr.ip_address,
                    dvr.mac_address, dvr.storage_capacity, dvr.date_installed,
                    dvr.latitude, dvr.longitude, dvr.address, 
                    dvr.updated_at.isoformat(), dvr_id
                ))
                await db.commit()
            
            return {
                'success': True,
                'message': f"DVR '{dvr.get_display_name()}' updated successfully"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error updating DVR: {str(e)}"
            }    
 
    async def update_dvr_location(self, dvr_id: int, latitude: float, longitude: float, 
                                 address: str = None) -> Dict[str, Any]:
        """Update DVR location and propagate to assigned cameras."""
        try:
            # Validate coordinates
            if not DVR.validate_coordinates(latitude, longitude):
                return {
                    'success': False,
                    'message': "Invalid latitude/longitude values"
                }
            
            async with aiosqlite.connect(self.db_path) as db:
                # Update DVR location
                await db.execute("""
                    UPDATE dvrs SET latitude = ?, longitude = ?, address = ?, updated_at = ?
                    WHERE id = ?
                """, (latitude, longitude, address, datetime.now().isoformat(), dvr_id))
                
                await db.commit()
                
                # Get DVR details for response
                dvr = await self.get_dvr(dvr_id)
                if not dvr:
                    return {
                        'success': False,
                        'message': f"DVR with ID {dvr_id} not found"
                    }
                
                return {
                    'success': True,
                    'message': f"DVR '{dvr.get_display_name()}' location updated successfully",
                    'dvr': dvr.to_dict()
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error updating DVR location: {str(e)}"
            }
    
    async def delete_dvr(self, dvr_id: int) -> Dict[str, Any]:
        """Delete DVR and handle camera assignments."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get DVR details before deletion
                dvr = await self.get_dvr(dvr_id)
                if not dvr:
                    return {
                        'success': False,
                        'message': f"DVR with ID {dvr_id} not found"
                    }
                
                # Check for assigned cameras
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM cameras WHERE dvr_id = ?", 
                    (dvr_id,)
                )
                camera_count = (await cursor.fetchone())[0]
                
                if camera_count > 0:
                    # Unassign cameras from DVR
                    await db.execute(
                        "UPDATE cameras SET dvr_id = NULL WHERE dvr_id = ?", 
                        (dvr_id,)
                    )
                
                # Delete DVR
                await db.execute("DELETE FROM dvrs WHERE id = ?", (dvr_id,))
                await db.commit()
                
                message = f"DVR '{dvr.get_display_name()}' deleted successfully"
                if camera_count > 0:
                    message += f" ({camera_count} cameras unassigned)"
                
                return {
                    'success': True,
                    'message': message,
                    'cameras_unassigned': camera_count
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error deleting DVR: {str(e)}"
            }
    
    async def assign_camera_to_dvr(self, camera_id: int, dvr_id: int, 
                                  inherit_location: bool = True) -> Dict[str, Any]:
        """Assign camera to DVR with optional location inheritance."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Verify DVR exists
                dvr = await self.get_dvr(dvr_id)
                if not dvr:
                    return {
                        'success': False,
                        'message': f"DVR with ID {dvr_id} not found"
                    }
                
                # Get camera details
                cursor = await db.execute("""
                    SELECT id, name, latitude, longitude FROM cameras WHERE id = ?
                """, (camera_id,))
                camera_row = await cursor.fetchone()
                
                if not camera_row:
                    return {
                        'success': False,
                        'message': f"Camera with ID {camera_id} not found"
                    }
                
                camera_name = camera_row[1]
                camera_lat = camera_row[2]
                camera_lon = camera_row[3]
                
                # Assign camera to DVR
                await db.execute(
                    "UPDATE cameras SET dvr_id = ? WHERE id = ?", 
                    (dvr_id, camera_id)
                )
                
                # Handle location inheritance
                location_inherited = False
                if inherit_location and dvr.latitude and dvr.longitude:
                    # Only inherit if camera has no location or user explicitly wants to inherit
                    if not camera_lat or not camera_lon:
                        await db.execute("""
                            UPDATE cameras SET latitude = ?, longitude = ? WHERE id = ?
                        """, (dvr.latitude, dvr.longitude, camera_id))
                        location_inherited = True
                
                await db.commit()
                
                message = f"Camera '{camera_name}' assigned to DVR '{dvr.get_display_name()}'"
                if location_inherited:
                    message += " (location inherited from DVR)"
                
                return {
                    'success': True,
                    'message': message,
                    'location_inherited': location_inherited
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error assigning camera to DVR: {str(e)}"
            }
    
    async def unassign_camera_from_dvr(self, camera_id: int) -> Dict[str, Any]:
        """Unassign camera from its DVR."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get camera details
                cursor = await db.execute("""
                    SELECT c.name, d.custom_name as dvr_name 
                    FROM cameras c 
                    LEFT JOIN dvrs d ON c.dvr_id = d.id 
                    WHERE c.id = ?
                """, (camera_id,))
                
                row = await cursor.fetchone()
                if not row:
                    return {
                        'success': False,
                        'message': f"Camera with ID {camera_id} not found"
                    }
                
                camera_name = row[0]
                dvr_name = row[1]
                
                if not dvr_name:
                    return {
                        'success': False,
                        'message': f"Camera '{camera_name}' is not assigned to any DVR"
                    }
                
                # Unassign camera
                await db.execute(
                    "UPDATE cameras SET dvr_id = NULL WHERE id = ?", 
                    (camera_id,)
                )
                await db.commit()
                
                return {
                    'success': True,
                    'message': f"Camera '{camera_name}' unassigned from DVR '{dvr_name}'"
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error unassigning camera from DVR: {str(e)}"
            }
    
    async def propagate_dvr_location_to_cameras(self, dvr_id: int, 
                                              force_update: bool = False) -> Dict[str, Any]:
        """Update all cameras assigned to DVR with DVR's location."""
        try:
            dvr = await self.get_dvr(dvr_id)
            if not dvr:
                return {
                    'success': False,
                    'message': f"DVR with ID {dvr_id} not found"
                }
            
            if not dvr.latitude or not dvr.longitude:
                return {
                    'success': False,
                    'message': f"DVR '{dvr.get_display_name()}' has no location coordinates"
                }
            
            async with aiosqlite.connect(self.db_path) as db:
                # Get cameras assigned to this DVR
                if force_update:
                    # Update all cameras assigned to this DVR
                    cursor = await db.execute("""
                        SELECT id, name FROM cameras WHERE dvr_id = ?
                    """, (dvr_id,))
                else:
                    # Only update cameras without coordinates
                    cursor = await db.execute("""
                        SELECT id, name FROM cameras 
                        WHERE dvr_id = ? AND (latitude IS NULL OR longitude IS NULL)
                    """, (dvr_id,))
                
                cameras_to_update = await cursor.fetchall()
                
                if not cameras_to_update:
                    message = "No cameras need location updates" if not force_update else "No cameras assigned to this DVR"
                    return {
                        'success': True,
                        'message': message,
                        'cameras_updated': 0
                    }
                
                # Update camera locations
                camera_ids = [camera[0] for camera in cameras_to_update]
                placeholders = ','.join(['?' for _ in camera_ids])
                
                await db.execute(f"""
                    UPDATE cameras SET latitude = ?, longitude = ? 
                    WHERE id IN ({placeholders})
                """, [dvr.latitude, dvr.longitude] + camera_ids)
                
                await db.commit()
                
                camera_names = [camera[1] for camera in cameras_to_update]
                return {
                    'success': True,
                    'message': f"Updated location for {len(cameras_to_update)} cameras: {', '.join(camera_names)}",
                    'cameras_updated': len(cameras_to_update),
                    'updated_cameras': camera_names
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f"Error propagating DVR location: {str(e)}"
            }
    
    async def get_dvr_with_cameras(self, dvr_id: int) -> Optional[Dict[str, Any]]:
        """Get DVR details with all assigned cameras."""
        try:
            dvr = await self.get_dvr(dvr_id)
            if not dvr:
                return None
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, name, location, ip_address, latitude, longitude,
                           coverage_radius, field_of_view_angle, coverage_direction
                    FROM cameras WHERE dvr_id = ?
                    ORDER BY name
                """, (dvr_id,))
                
                camera_rows = await cursor.fetchall()
                cameras = []
                
                for row in camera_rows:
                    cameras.append({
                        'id': row[0],
                        'name': row[1],
                        'location': row[2],
                        'ip_address': row[3],
                        'latitude': row[4],
                        'longitude': row[5],
                        'coverage_radius': row[6],
                        'field_of_view_angle': row[7],
                        'coverage_direction': row[8]
                    })
                
                return {
                    'dvr': dvr.to_dict(),
                    'cameras': cameras,
                    'camera_count': len(cameras)
                }
                
        except Exception as e:
            print(f"Error getting DVR with cameras: {e}")
            return None
    
    async def search_dvrs(self, search_term: str) -> List[DVR]:
        """Search DVRs by name, location, or IP address."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, custom_name, dvr_type, location, ip_address, mac_address,
                           storage_capacity, date_installed, latitude, longitude, address,
                           created_at, updated_at
                    FROM dvrs 
                    WHERE custom_name LIKE ? OR location LIKE ? OR ip_address LIKE ?
                    ORDER BY custom_name
                """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
                
                rows = await cursor.fetchall()
                return [DVR.from_db_row(row) for row in rows]
                
        except Exception as e:
            print(f"Error searching DVRs: {e}")
            return []
    
    async def get_dvrs_for_map(self) -> List[Dict[str, Any]]:
        """Get DVRs formatted for map display."""
        try:
            dvrs = await self.get_all_dvrs()
            return [dvr.to_map_marker() for dvr in dvrs if dvr.latitude and dvr.longitude]
        except Exception as e:
            print(f"Error getting DVRs for map: {e}")
            return []
    
    async def bulk_update_dvr_locations(self, location_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk update DVR locations."""
        try:
            updated_count = 0
            errors = []
            
            async with aiosqlite.connect(self.db_path) as db:
                for update in location_updates:
                    try:
                        dvr_id = update['dvr_id']
                        latitude = update['latitude']
                        longitude = update['longitude']
                        address = update.get('address')
                        
                        if not DVR.validate_coordinates(latitude, longitude):
                            errors.append(f"DVR {dvr_id}: Invalid coordinates")
                            continue
                        
                        await db.execute("""
                            UPDATE dvrs SET latitude = ?, longitude = ?, address = ?, updated_at = ?
                            WHERE id = ?
                        """, (latitude, longitude, address, datetime.now().isoformat(), dvr_id))
                        
                        updated_count += 1
                        
                    except Exception as e:
                        errors.append(f"DVR {update.get('dvr_id', 'unknown')}: {str(e)}")
                
                await db.commit()
            
            return {
                'success': True,
                'message': f"Updated {updated_count} DVR locations",
                'updated_count': updated_count,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error in bulk update: {str(e)}"
            }
    
    async def get_cameras_by_dvr(self, dvr_id: int) -> List[EnhancedCamera]:
        """Get all cameras assigned to a specific DVR."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, location, name, mac_address, ip_address, locational_group,
                           date_installed, dvr_id, latitude, longitude, has_memory_card,
                           memory_card_last_reset, coverage_radius, field_of_view_angle,
                           coverage_direction
                    FROM cameras WHERE dvr_id = ?
                    ORDER BY name
                """, (dvr_id,))
                
                rows = await cursor.fetchall()
                return [EnhancedCamera.from_db_row(row) for row in rows]
                
        except Exception as e:
            print(f"Error getting cameras by DVR: {e}")
            return []
    
    async def validate_dvr_camera_assignments(self) -> Dict[str, Any]:
        """Validate all DVR-camera assignments and report issues."""
        try:
            issues = []
            
            async with aiosqlite.connect(self.db_path) as db:
                # Check for cameras assigned to non-existent DVRs
                cursor = await db.execute("""
                    SELECT c.id, c.name, c.dvr_id 
                    FROM cameras c 
                    LEFT JOIN dvrs d ON c.dvr_id = d.id 
                    WHERE c.dvr_id IS NOT NULL AND d.id IS NULL
                """)
                
                orphaned_cameras = await cursor.fetchall()
                for camera in orphaned_cameras:
                    issues.append({
                        'type': 'orphaned_camera',
                        'camera_id': camera[0],
                        'camera_name': camera[1],
                        'dvr_id': camera[2],
                        'message': f"Camera '{camera[1]}' assigned to non-existent DVR {camera[2]}"
                    })
                
                # Check for DVRs without location that have cameras
                cursor = await db.execute("""
                    SELECT d.id, d.custom_name, COUNT(c.id) as camera_count
                    FROM dvrs d
                    LEFT JOIN cameras c ON d.id = c.dvr_id
                    WHERE (d.latitude IS NULL OR d.longitude IS NULL) AND c.id IS NOT NULL
                    GROUP BY d.id, d.custom_name
                """)
                
                dvrs_without_location = await cursor.fetchall()
                for dvr in dvrs_without_location:
                    issues.append({
                        'type': 'dvr_no_location',
                        'dvr_id': dvr[0],
                        'dvr_name': dvr[1],
                        'camera_count': dvr[2],
                        'message': f"DVR '{dvr[1]}' has {dvr[2]} cameras but no location coordinates"
                    })
            
            return {
                'success': True,
                'issues_found': len(issues),
                'issues': issues
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error validating assignments: {str(e)}"
            }


# Utility functions for DVR management
async def create_dvr_from_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create DVR from form data with proper validation."""
    dvr_manager = DVRManager()
    
    return await dvr_manager.create_dvr(
        custom_name=form_data.get('custom_name', ''),
        ip_address=form_data.get('ip_address', ''),
        dvr_type=form_data.get('dvr_type', 'Unknown'),
        location=form_data.get('location', ''),
        mac_address=form_data.get('mac_address', ''),
        storage_capacity=form_data.get('storage_capacity', ''),
        date_installed=form_data.get('date_installed'),
        address=form_data.get('address'),
        latitude=float(form_data['latitude']) if form_data.get('latitude') else None,
        longitude=float(form_data['longitude']) if form_data.get('longitude') else None
    )


async def get_dvr_dropdown_choices() -> List[Tuple[str, int]]:
    """Get DVR choices for dropdown menus."""
    try:
        dvr_manager = DVRManager()
        dvrs = await dvr_manager.get_all_dvrs()
        
        choices = [("No DVR", None)]
        for dvr in dvrs:
            display_name = f"{dvr.get_display_name()} ({dvr.ip_address})"
            choices.append((display_name, dvr.id))
        
        return choices
        
    except Exception as e:
        print(f"Error getting DVR choices: {e}")
        return [("No DVR", None)]


def generate_dvr_location_click_script() -> str:
    """Generate JavaScript for DVR location click functionality."""
    return """
    <script>
    function openDVRLocation(dvrId) {
        // This function will be called when user clicks on DVR location button
        // It can be integrated with the main map interface to focus on DVR location
        console.log('Opening DVR location for ID:', dvrId);
        
        // Example: Focus map on DVR location
        if (window.focusMapOnDVR) {
            window.focusMapOnDVR(dvrId);
        } else {
            // Fallback: show alert with DVR ID
            alert('DVR Location - ID: ' + dvrId + '\\nThis feature will focus the map on the DVR location.');
        }
    }
    
    function openCameraLocation(cameraId) {
        // This function will be called when user clicks on camera location button
        console.log('Opening camera location for ID:', cameraId);
        
        // Example: Focus map on camera location
        if (window.focusMapOnCamera) {
            window.focusMapOnCamera(cameraId);
        } else {
            // Fallback: show alert with camera ID
            alert('Camera Location - ID: ' + cameraId + '\\nThis feature will focus the map on the camera location.');
        }
    }
    </script>
    """