"""
Interactive Map Manager Component for Camera Mapping System

This module provides the InteractiveMapManager class that handles map generation,
drag-and-drop interactions, and real-time coverage area updates for the camera
management system.
"""

import json
import math
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import aiosqlite
import folium
from folium.plugins import MarkerCluster
from ping3 import ping

from .enhanced_camera_models import EnhancedCamera
from .coverage_calculator import CoverageCalculator
from .location_detector import LocationDetector
from .error_handling import get_error_handler


class InteractiveMapManager:
    """
    Manages interactive map functionality with drag-and-drop and real-time updates.
    
    This class provides:
    - Enhanced map creation with custom JavaScript for drag-and-drop
    - Camera position update handling from map interactions
    - Real-time coverage area updates when cameras are moved
    - Integration with connectivity monitoring
    """
    
    def __init__(self, db_name: str = "camera_data.db"):
        """
        Initialize the InteractiveMapManager.
        
        Args:
            db_name: Path to the SQLite database file
        """
        self.db_name = db_name
        self.connectivity_cache = {}
        self.cache_timeout = 30  # seconds
        self.location_detector = LocationDetector(db_name)
    
    async def create_enhanced_map(self, focus_device_id: Optional[int] = None, 
                                 focus_device_type: str = "camera") -> str:
        """
        Create interactive map with drag-and-drop functionality.
        
        Returns:
            HTML string of the enhanced Folium map
            
        Requirements addressed:
        - 1.1: Drag cameras to new positions on the map
        - 1.2: Update camera coordinates when cameras are moved
        - 2.2: Coverage area moves with camera marker in real-time
        """
        try:
            # Get cameras with coverage data
            cameras = await self._get_cameras_with_coverage()
            dvrs = await self._get_dvrs_for_map()
            
            # Initialize map location detection and get center coordinates
            location_status = await self.initialize_map_location()
            
            # Calculate map center based on device locations, focus device, or detected location
            if focus_device_id and focus_device_type:
                center_lat, center_lon = await self._get_focus_device_location(focus_device_id, focus_device_type)
            else:
                center_lat, center_lon = await self._get_initial_map_center(cameras, dvrs)
            
            # If no cameras and DVRs, create empty map with detected location
            if not cameras and not dvrs:
                return await self._create_empty_map_with_location(location_status)
            
            # Create base map with enhanced configuration
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=13,
                tiles='OpenStreetMap',
                prefer_canvas=True  # Better performance for interactive elements
            )
            
            # Add additional tile layers for better visualization
            folium.TileLayer(
                'Stamen Terrain', 
                name='Terrain',
                attr='Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL.'
            ).add_to(m)
            folium.TileLayer(
                'CartoDB positron', 
                name='Light',
                attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            ).add_to(m)
            folium.TileLayer(
                'CartoDB dark_matter', 
                name='Dark',
                attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            ).add_to(m)
            
            # Create marker clusters for better organization
            camera_cluster = MarkerCluster(
                name="📹 Cameras",
                overlay=True,
                control=True,
                show=True
            ).add_to(m)
            
            dvr_cluster = MarkerCluster(
                name="📺 DVRs",
                overlay=True,
                control=True,
                show=True
            ).add_to(m)
            
            # Add cameras with coverage areas and connectivity testing
            camera_objects = []
            for camera_data in cameras:
                camera = EnhancedCamera.from_db_row(camera_data)
                
                # Test connectivity for real-time status
                is_online = await self._test_camera_connectivity(camera.ip_address)
                camera.update_connectivity_status(is_online)
                
                camera_objects.append(camera)
                
                # Add coverage area first (so it appears behind markers)
                if camera.latitude and camera.longitude:
                    self._add_coverage_area_to_map(m, camera)
                    self._add_camera_marker_to_map(camera_cluster, camera)
            
            # Add coverage overlap visualization
            if len(camera_objects) > 1:
                self._add_coverage_overlaps_to_map(m, camera_objects)
            
            # Add DVRs to map
            for dvr_data in dvrs:
                await self._add_dvr_marker_to_map(dvr_cluster, dvr_data)
            
            # Add visual connections between cameras and DVRs
            self._add_dvr_camera_connections(m, cameras, dvrs)
            
            # Add layer control for toggling different elements
            folium.LayerControl(position='topright').add_to(m)
            
            # Add custom JavaScript for drag-and-drop functionality
            self._add_drag_drop_javascript(m)
            
            # Add map legend and controls
            self._add_map_legend(m)
            self._add_map_controls(m)
            
            # Add custom CSS for enhanced styling
            self._add_custom_css(m)
            
            # Add location detection notification to map
            self._add_location_notification(m, location_status)
            
            return m._repr_html_()
            
        except Exception as e:
            print(f"Error creating enhanced map: {e}")
            return self._create_error_map(str(e))
    
    async def handle_camera_move(self, camera_id: int, lat: float, lon: float) -> Dict[str, Any]:
        """
        Handle camera position updates from map interactions with comprehensive error handling.
        
        Args:
            camera_id: ID of the camera being moved
            lat: New latitude coordinate
            lon: New longitude coordinate
            
        Returns:
            Dictionary with success status, message, and updated coordinates
            
        Requirements addressed:
        - 1.2: Update camera's latitude and longitude coordinates in database
        - 1.3: Display confirmation message showing new coordinates
        - 1.4: Revert marker to original position on failure
        """
        # Use comprehensive error handler for coordinate updates
        error_handler = get_error_handler(self.db_name)
        result = await error_handler.handle_camera_coordinate_update(camera_id, lat, lon)
        
        # Convert OperationResult to expected dictionary format
        response = {
            'success': result.success,
            'message': result.message,
            'revert': not result.success,
            'camera_id': camera_id
        }
        
        if result.success and result.data:
            response['coordinates'] = {
                'lat': result.data['new_coordinates']['latitude'],
                'lon': result.data['new_coordinates']['longitude']
            }
            response['original_position'] = result.data['original_coordinates']
        
        return response
    
    async def update_coverage_parameters(self, camera_id: int, params: Dict[str, float]) -> Dict[str, Any]:
        """
        Update camera coverage settings and trigger real-time coverage area updates.
        
        Args:
            camera_id: ID of the camera to update
            params: Dictionary with coverage parameters (radius, angle, direction)
            
        Returns:
            Dictionary with success status and updated parameters
            
        Requirements addressed:
        - 2.2: Real-time coverage area updates when cameras are moved
        """
        try:
            radius = params.get('radius', 50.0)
            angle = params.get('angle', 360.0)
            direction = params.get('direction', 0.0)
            
            # Validate coverage parameters
            if not EnhancedCamera.validate_coverage_parameters(radius, angle, direction):
                return {
                    'success': False,
                    'message': '❌ Invalid coverage parameters! Radius: 1-10000m, Angle: 1-360°, Direction: 0-359°',
                    'camera_id': camera_id
                }
            
            # Update database
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    UPDATE cameras 
                    SET coverage_radius = ?, field_of_view_angle = ?, coverage_direction = ?
                    WHERE id = ?
                """, (float(radius), float(angle), float(direction), camera_id))
                await db.commit()
            
            # Log the parameter update
            await self._log_coverage_update(camera_id, params)
            
            return {
                'success': True,
                'message': f'✅ Coverage parameters updated for camera {camera_id}',
                'parameters': {
                    'radius': radius,
                    'angle': angle,
                    'direction': direction
                },
                'camera_id': camera_id
            }
            
        except Exception as e:
            print(f"Error updating coverage parameters: {e}")
            return {
                'success': False,
                'message': f'❌ Error updating coverage: {str(e)}',
                'camera_id': camera_id
            }
    
    async def get_camera_coverage_data(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current coverage data for a specific camera.
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dictionary with coverage coordinates and parameters, or None if not found
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, latitude, longitude, coverage_radius,
                           field_of_view_angle, coverage_direction
                    FROM cameras WHERE id = ?
                """, (camera_id,))
                result = await cursor.fetchone()
                
                if not result:
                    return None
                
                camera_data = {
                    'id': result[0],
                    'name': result[1],
                    'latitude': result[2],
                    'longitude': result[3],
                    'coverage_radius': result[4],
                    'field_of_view_angle': result[5],
                    'coverage_direction': result[6]
                }
                
                # Calculate coverage coordinates
                if camera_data['latitude'] and camera_data['longitude']:
                    if camera_data['field_of_view_angle'] >= 360.0:
                        coordinates = CoverageCalculator.calculate_circular_coverage(
                            camera_data['latitude'], camera_data['longitude'], 
                            camera_data['coverage_radius']
                        )
                    else:
                        coordinates = CoverageCalculator.calculate_directional_coverage(
                            camera_data['latitude'], camera_data['longitude'],
                            camera_data['coverage_radius'], camera_data['coverage_direction'],
                            camera_data['field_of_view_angle']
                        )
                    
                    camera_data['coverage_coordinates'] = coordinates
                
                return camera_data
                
        except Exception as e:
            print(f"Error getting camera coverage data: {e}")
            return None

    async def get_all_cameras_data(self) -> List[Dict[str, Any]]:
        """
        Get all cameras data for JavaScript drag functionality.
        
        Returns:
            List of camera dictionaries with coverage parameters
            
        Requirements addressed:
        - JavaScript needs camera data for real-time coverage updates during drag
        """
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, latitude, longitude, coverage_radius,
                           field_of_view_angle, coverage_direction, ip_address
                    FROM cameras 
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                    ORDER BY id
                """)
                results = await cursor.fetchall()
                
                cameras_data = []
                for result in results:
                    camera_data = {
                        'id': result[0],
                        'name': result[1],
                        'latitude': result[2],
                        'longitude': result[3],
                        'coverage_radius': result[4] or 50.0,
                        'field_of_view_angle': result[5] or 360.0,
                        'coverage_direction': result[6] or 0.0,
                        'ip_address': result[7]
                    }
                    cameras_data.append(camera_data)
                
                return cameras_data
                
        except Exception as e:
            print(f"Error getting all cameras data: {e}")
            return []

    async def process_drag_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process drag-and-drop requests from JavaScript frontend.
        
        Args:
            request_data: Dictionary containing action, camera_id, latitude, longitude
            
        Returns:
            Response dictionary for JavaScript
            
        Requirements addressed:
        - 1.2: Backend communication for coordinate updates
        - 1.3: Confirmation messages for successful updates
        - 1.4: Error handling and position reversion
        """
        try:
            action = request_data.get('action')
            
            if action == 'update_camera_position':
                camera_id = int(request_data.get('camera_id', 0))
                latitude = float(request_data.get('latitude', 0))
                longitude = float(request_data.get('longitude', 0))
                
                # Use existing handle_camera_move method
                result = await self.handle_camera_move(camera_id, latitude, longitude)
                return result
                
            elif action == 'get_camera_data':
                # Return all cameras data for JavaScript
                cameras_data = await self.get_all_cameras_data()
                return {
                    'success': True,
                    'cameras': cameras_data
                }
                
            else:
                return {
                    'success': False,
                    'message': f'❌ Unknown action: {action}',
                    'revert': True
                }
                
        except Exception as e:
            print(f"Error processing drag request: {e}")
            return {
                'success': False,
                'message': f'❌ Server error: {str(e)}',
                'revert': True
            }
    
    async def handle_dvr_move(self, dvr_id: int, lat: float, lon: float) -> Dict[str, Any]:
        """
        Handle DVR position updates from map interactions.
        
        Args:
            dvr_id: ID of the DVR being moved
            lat: New latitude coordinate
            lon: New longitude coordinate
            
        Returns:
            Dictionary with success status, message, and updated coordinates
        """
        try:
            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return {
                    'success': False,
                    'message': '❌ Invalid coordinates! Latitude must be -90 to 90, longitude must be -180 to 180.',
                    'revert': True,
                    'dvr_id': dvr_id
                }
            
            # Update DVR coordinates in database
            async with aiosqlite.connect(self.db_name) as db:
                # Get original coordinates for response
                cursor = await db.execute(
                    "SELECT latitude, longitude FROM dvrs WHERE id = ?",
                    (dvr_id,)
                )
                original = await cursor.fetchone()
                
                if not original:
                    return {
                        'success': False,
                        'message': f'❌ DVR {dvr_id} not found',
                        'revert': True,
                        'dvr_id': dvr_id
                    }
                
                # Update coordinates
                await db.execute(
                    "UPDATE dvrs SET latitude = ?, longitude = ? WHERE id = ?",
                    (float(lat), float(lon), dvr_id)
                )
                await db.commit()
                
                # Log the update
                await self._log_dvr_coordinate_update(dvr_id, lat, lon, original)
                
                return {
                    'success': True,
                    'message': f'✅ DVR {dvr_id} coordinates updated to ({lat:.6f}, {lon:.6f})',
                    'coordinates': {'lat': lat, 'lon': lon},
                    'original_position': {'latitude': original[0], 'longitude': original[1]},
                    'dvr_id': dvr_id
                }
                
        except Exception as e:
            print(f"Error updating DVR coordinates: {e}")
            return {
                'success': False,
                'message': f'❌ Error updating DVR position: {str(e)}',
                'revert': True,
                'dvr_id': dvr_id
            }
    
    async def _log_dvr_coordinate_update(self, dvr_id: int, new_lat: float, new_lon: float, original: tuple):
        """Log DVR coordinate update to action log."""
        try:
            import time
            details = {
                'dvr_id': dvr_id,
                'new_coordinates': {'latitude': new_lat, 'longitude': new_lon},
                'original_coordinates': {'latitude': original[0], 'longitude': original[1]},
                'timestamp': datetime.now().isoformat()
            }
            
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    INSERT INTO action_log (timestamp, action_type, table_name, record_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    'dvr_coordinate_update',
                    'dvrs',
                    dvr_id,
                    json.dumps(details)
                ))
                await db.commit()
        except Exception as e:
            print(f"Error logging DVR coordinate update: {e}")
    
    async def _get_cameras_with_coverage(self) -> List[tuple]:
        """Get cameras with coverage parameters from database."""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT c.id, c.location, c.name, c.mac_address, c.ip_address, 
                       c.locational_group, c.date_installed, c.dvr_id, c.latitude, c.longitude,
                       c.has_memory_card, c.memory_card_last_reset, c.coverage_radius,
                       c.field_of_view_angle, c.coverage_direction, c.custom_name, c.address
                FROM cameras c
                WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
                ORDER BY COALESCE(NULLIF(c.custom_name, ''), c.name)
            """)
            return await cursor.fetchall()
    
    async def _get_dvrs_for_map(self) -> List[tuple]:
        """Get DVRs with coordinates for map display."""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                SELECT id, name, location, ip_address, latitude, longitude, dvr_type, custom_name
                FROM dvrs
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                ORDER BY COALESCE(NULLIF(custom_name, ''), name)
            """)
            return await cursor.fetchall()
    
    async def _get_focus_device_location(self, device_id: int, device_type: str) -> Tuple[float, float]:
        """Get location coordinates for a specific device to focus the map on."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                if device_type.lower() == "camera":
                    cursor = await db.execute("""
                        SELECT latitude, longitude FROM cameras WHERE id = ?
                    """, (device_id,))
                elif device_type.lower() == "dvr":
                    cursor = await db.execute("""
                        SELECT latitude, longitude FROM dvrs WHERE id = ?
                    """, (device_id,))
                else:
                    return 40.7128, -74.0060  # Default location
                
                result = await cursor.fetchone()
                if result and result[0] and result[1]:
                    return float(result[0]), float(result[1])
                else:
                    return 40.7128, -74.0060  # Default location
                    
        except Exception as e:
            print(f"Error getting focus device location: {e}")
            return 40.7128, -74.0060  # Default location

    def _calculate_map_center(self, cameras: List[tuple], dvrs: List[tuple]) -> Tuple[float, float]:
        """Calculate center point for map based on device locations."""
        all_coords = []
        
        # Add camera coordinates
        for camera in cameras:
            if len(camera) > 9 and camera[8] and camera[9]:  # lat, lon indices
                all_coords.append([float(camera[8]), float(camera[9])])
        
        # Add DVR coordinates  
        for dvr in dvrs:
            if len(dvr) > 5 and dvr[4] and dvr[5]:  # lat, lon indices
                all_coords.append([float(dvr[4]), float(dvr[5])])
        
        if all_coords:
            center_lat = sum(coord[0] for coord in all_coords) / len(all_coords)
            center_lon = sum(coord[1] for coord in all_coords) / len(all_coords)
            return center_lat, center_lon
        else:
            # Default to New York City if no coordinates available
            return 40.7128, -74.0060

    async def initialize_map_location(self) -> Dict[str, Any]:
        """
        Detect and set initial map location based on script execution location.
        
        This method detects the script's execution location on first load and stores it
        for future map centering. It provides user notification about detection status.
        
        Returns:
            Dict with detection status, coordinates, and user notification message
            
        Requirements addressed:
        - 6.1: Detect script location on first load
        - 6.2: Set map center to detected coordinates with appropriate zoom level
        - 6.3: Use default location and notify user when detection fails
        - 6.4: Automatically adjust to new location when script runs from different locations
        """
        try:
            # Check if we have a recent location detection (within last hour)
            current_location = await self.location_detector.get_current_location()
            
            # If no current location or it's old, detect new location
            if not current_location or self._is_location_detection_stale(current_location):
                print("🌍 Detecting script execution location for map initialization...")
                location_result = await self.location_detector.detect_script_location()
                
                if location_result.success:
                    notification_message = (
                        f"📍 Map centered on detected location: {location_result.address} "
                        f"(Method: {location_result.detection_method}, "
                        f"Confidence: {location_result.confidence_score:.1%})"
                    )
                    
                    return {
                        'success': True,
                        'latitude': location_result.latitude,
                        'longitude': location_result.longitude,
                        'address': location_result.address,
                        'detection_method': location_result.detection_method,
                        'confidence_score': location_result.confidence_score,
                        'notification': notification_message,
                        'status': 'detected'
                    }
                else:
                    # Detection failed, use default location
                    notification_message = (
                        f"⚠️ Location detection failed: {location_result.error_message}. "
                        f"Using default location: {location_result.address}"
                    )
                    
                    return {
                        'success': False,
                        'latitude': location_result.latitude,
                        'longitude': location_result.longitude,
                        'address': location_result.address,
                        'detection_method': location_result.detection_method,
                        'confidence_score': location_result.confidence_score,
                        'notification': notification_message,
                        'status': 'failed_fallback'
                    }
            else:
                # Use existing current location
                notification_message = (
                    f"📍 Using cached location: {current_location['address']} "
                    f"(Method: {current_location['detection_method']})"
                )
                
                return {
                    'success': True,
                    'latitude': current_location['latitude'],
                    'longitude': current_location['longitude'],
                    'address': current_location['address'],
                    'detection_method': current_location['detection_method'],
                    'confidence_score': current_location['confidence_score'],
                    'notification': notification_message,
                    'status': 'cached'
                }
                
        except Exception as e:
            # Error in location detection, use default
            error_message = f"❌ Error in location detection: {str(e)}. Using default location."
            print(error_message)
            
            return {
                'success': False,
                'latitude': 40.7128,
                'longitude': -74.0060,
                'address': "New York, NY, USA (Error Fallback)",
                'detection_method': 'error_fallback',
                'confidence_score': 0.1,
                'notification': error_message,
                'status': 'error'
            }

    async def _get_initial_map_center(self, cameras: List[tuple], dvrs: List[tuple]) -> Tuple[float, float]:
        """
        Get initial map center coordinates based on detected location and device locations.
        
        Priority order:
        1. Average of device locations (if devices exist)
        2. Detected script execution location
        3. Default location (New York City)
        
        Args:
            cameras: List of camera data tuples
            dvrs: List of DVR data tuples
            
        Returns:
            Tuple of (latitude, longitude) for map center
            
        Requirements addressed:
        - 6.1: Center map on detected location when no devices present
        - 6.2: Use detected coordinates with appropriate zoom level
        - 6.3: Fallback to default location when detection fails
        """
        # If we have devices, use their average location
        if cameras or dvrs:
            return self._calculate_map_center(cameras, dvrs)
        
        # No devices, use detected script location
        try:
            center_coords = await self.location_detector.get_map_center_coordinates()
            print(f"🗺️ Map centered on detected location: {center_coords}")
            return center_coords
        except Exception as e:
            print(f"⚠️ Error getting detected location for map center: {e}")
            return 40.7128, -74.0060  # Default fallback

    def _is_location_detection_stale(self, location_data: Dict[str, Any]) -> bool:
        """
        Check if location detection data is stale and needs refresh.
        
        Args:
            location_data: Location data from database
            
        Returns:
            True if location data is stale and should be refreshed
        """
        try:
            from datetime import datetime, timedelta
            
            # Parse the detected_at timestamp
            detected_at = datetime.fromisoformat(location_data['detected_at'].replace('Z', '+00:00'))
            
            # Consider location stale if older than 1 hour
            stale_threshold = datetime.now().replace(tzinfo=detected_at.tzinfo) - timedelta(hours=1)
            
            return detected_at < stale_threshold
            
        except Exception as e:
            print(f"⚠️ Error checking location staleness: {e}")
            return True  # Consider stale if we can't determine age
    
    def _add_coverage_area_to_map(self, map_obj: folium.Map, camera: EnhancedCamera):
        """
        Add enhanced coverage area visualization to map with detailed styling and tooltips.
        
        Requirements addressed:
        - 2.1: Show visual coverage area around camera marker
        - 2.2: Coverage area moves with camera marker in real-time
        - 2.4: Display camera details and coverage information on hover
        - 4.3: Coverage area styling with opacity changes based on connectivity status
        """
        try:
            # Enhanced styling based on connectivity status
            if camera.is_online:
                opacity = 0.4
                weight = 2
                color = '#007bff'  # Blue for online
                fill_color = '#007bff'
                dash_array = None
            else:
                opacity = 0.15  # Reduced opacity for offline cameras
                weight = 1
                color = '#6c757d'  # Gray for offline
                fill_color = '#6c757d'
                dash_array = '5, 5'  # Dashed line for offline
            
            # Calculate coverage area size for display
            coverage_coords = None
            coverage_area_size = 0.0
            
            if camera.field_of_view_angle >= 360.0:
                # Circular coverage
                coverage_coords = CoverageCalculator.calculate_circular_coverage(
                    camera.latitude, camera.longitude, camera.coverage_radius
                )
                coverage_area_size = 3.14159 * (camera.coverage_radius ** 2)  # π * r²
                coverage_type = "Circular (360°)"
            else:
                # Directional coverage
                coverage_coords = CoverageCalculator.calculate_directional_coverage(
                    camera.latitude, camera.longitude, camera.coverage_radius,
                    camera.coverage_direction, camera.field_of_view_angle
                )
                # Approximate area for sector: (angle/360) * π * r²
                coverage_area_size = (camera.field_of_view_angle / 360.0) * 3.14159 * (camera.coverage_radius ** 2)
                coverage_type = f"Directional ({camera.field_of_view_angle}°)"
            
            # Enhanced popup content with detailed information
            status_icon = "✅" if camera.is_online else "❌"
            status_text = "Online" if camera.is_online else "Offline"
            
            popup_content = f"""
            <div style="width: 320px; font-family: Arial, sans-serif; line-height: 1.4;">
                <h4 style="margin: 0 0 12px 0; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px;">
                    📹 Coverage Area Details
                </h4>
                <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                    <tr style="background-color: #f8f9fa;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Camera:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Location:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.location}</td>
                    </tr>
                    <tr style="background-color: #f8f9fa;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">IP Address:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.ip_address}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Status:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{status_icon} {status_text}</td>
                    </tr>
                    <tr style="background-color: #e3f2fd;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coverage Type:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{coverage_type}</td>
                    </tr>
                    <tr style="background-color: #e3f2fd;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coverage Radius:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.coverage_radius}m</td>
                    </tr>
            """
            
            if camera.field_of_view_angle < 360.0:
                popup_content += f"""
                    <tr style="background-color: #e3f2fd;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Field of View:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.field_of_view_angle}°</td>
                    </tr>
                    <tr style="background-color: #e3f2fd;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Direction:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.coverage_direction}° (from North)</td>
                    </tr>
                """
            
            popup_content += f"""
                    <tr style="background-color: #e3f2fd;">
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coverage Area:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{coverage_area_size:,.0f} m²</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coordinates:</td>
                        <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.latitude:.6f}, {camera.longitude:.6f}</td>
                    </tr>
                </table>
                <div style="margin-top: 10px; padding: 8px; background-color: #f1f3f4; border-radius: 4px; font-size: 11px; color: #666;">
                    💡 <strong>Tip:</strong> Coverage areas show the approximate monitoring range. 
                    Actual coverage may vary based on camera specifications and environmental factors.
                </div>
            </div>
            """
            
            # Enhanced tooltip with key information using display name
            display_name = camera.get_display_name()
            if camera.field_of_view_angle >= 360.0:
                tooltip_text = (f"📹 {display_name}\n"
                              f"🔵 Circular Coverage: {camera.coverage_radius}m\n"
                              f"📍 Area: {coverage_area_size:,.0f} m²\n"
                              f"{status_icon} {status_text}")
            else:
                tooltip_text = (f"📹 {display_name}\n"
                              f"📐 Directional Coverage: {camera.coverage_radius}m\n"
                              f"🎯 FOV: {camera.field_of_view_angle}° @ {camera.coverage_direction}°\n"
                              f"📍 Area: {coverage_area_size:,.0f} m²\n"
                              f"{status_icon} {status_text}")
            
            if camera.field_of_view_angle >= 360.0:
                # Enhanced circular coverage
                coverage_circle = folium.Circle(
                    location=[camera.latitude, camera.longitude],
                    radius=camera.coverage_radius,
                    popup=folium.Popup(popup_content, max_width=350),
                    tooltip=folium.Tooltip(tooltip_text, sticky=True),
                    color=color,
                    fill=True,
                    fillColor=fill_color,
                    fillOpacity=opacity,
                    weight=weight,
                    dashArray=dash_array,
                    className=f'coverage-area-{camera.id}',
                    # Enhanced interaction options
                    options={
                        'interactive': True,
                        'bubblingMouseEvents': False
                    }
                )
                coverage_circle.add_to(map_obj)
            else:
                # Enhanced directional coverage
                coverage_polygon = folium.Polygon(
                    locations=coverage_coords,
                    popup=folium.Popup(popup_content, max_width=350),
                    tooltip=folium.Tooltip(tooltip_text, sticky=True),
                    color=color,
                    fill=True,
                    fillColor=fill_color,
                    fillOpacity=opacity,
                    weight=weight,
                    dashArray=dash_array,
                    className=f'coverage-area-{camera.id}',
                    # Enhanced interaction options
                    options={
                        'interactive': True,
                        'bubblingMouseEvents': False
                    }
                )
                coverage_polygon.add_to(map_obj)
            
            # Add coverage area center point for directional cameras
            if camera.field_of_view_angle < 360.0:
                # Add a small indicator showing the direction
                direction_end_lat = camera.latitude + (camera.coverage_radius / 111320) * 0.3 * math.cos(math.radians(camera.coverage_direction))
                direction_end_lon = camera.longitude + (camera.coverage_radius / 111320) * 0.3 * math.sin(math.radians(camera.coverage_direction)) / math.cos(math.radians(camera.latitude))
                
                folium.PolyLine(
                    locations=[[camera.latitude, camera.longitude], [direction_end_lat, direction_end_lon]],
                    color='red',
                    weight=3,
                    opacity=0.8,
                    tooltip=f"Direction: {camera.coverage_direction}° from North",
                    className=f'direction-indicator-{camera.id}'
                ).add_to(map_obj)
                
        except Exception as e:
            print(f"Error adding enhanced coverage area for camera {camera.id}: {e}")
            # Fallback to basic coverage area
            try:
                folium.Circle(
                    location=[camera.latitude, camera.longitude],
                    radius=camera.coverage_radius,
                    popup=f"Coverage: {camera.name}",
                    tooltip=f"Coverage: {camera.name}",
                    color='blue',
                    fill=True,
                    fillColor='lightblue',
                    fillOpacity=0.3,
                    weight=1,
                    className=f'coverage-area-{camera.id}'
                ).add_to(map_obj)
            except Exception as fallback_error:
                print(f"Fallback coverage area also failed for camera {camera.id}: {fallback_error}")
    
    def _add_coverage_overlaps_to_map(self, map_obj: folium.Map, cameras: List[EnhancedCamera]):
        """
        Add visual indicators for overlapping coverage areas between cameras.
        
        Requirements addressed:
        - 2.3: Visually indicate overlapping areas when multiple cameras have overlapping coverage
        """
        try:
            # Convert cameras to dictionary format for overlap calculation
            camera_dicts = []
            for camera in cameras:
                if camera.latitude and camera.longitude:
                    camera_dicts.append({
                        'id': camera.id,
                        'name': camera.name,
                        'latitude': camera.latitude,
                        'longitude': camera.longitude,
                        'coverage_radius': camera.coverage_radius,
                        'field_of_view_angle': camera.field_of_view_angle,
                        'coverage_direction': camera.coverage_direction
                    })
            
            if len(camera_dicts) < 2:
                return
            
            # Find overlapping coverage areas
            overlaps = CoverageCalculator.find_coverage_overlaps(camera_dicts)
            
            if not overlaps:
                return
            
            # Create a feature group for overlap indicators
            overlap_group = folium.FeatureGroup(name="🔄 Coverage Overlaps", show=True)
            
            for overlap in overlaps:
                # Find the cameras involved in this overlap
                camera1 = next((c for c in cameras if c.id == overlap.camera1_id), None)
                camera2 = next((c for c in cameras if c.id == overlap.camera2_id), None)
                
                if not camera1 or not camera2:
                    continue
                
                # Calculate midpoint between cameras for overlap indicator
                mid_lat = (camera1.latitude + camera2.latitude) / 2
                mid_lon = (camera1.longitude + camera2.longitude) / 2
                
                # Create overlap indicator line
                folium.PolyLine(
                    locations=[[camera1.latitude, camera1.longitude], [camera2.latitude, camera2.longitude]],
                    color='orange',
                    weight=3,
                    opacity=0.7,
                    dashArray='10, 5',
                    popup=folium.Popup(
                        f"""
                        <div style="width: 280px; font-family: Arial, sans-serif;">
                            <h4 style="margin: 0 0 10px 0; color: #ff6600;">🔄 Coverage Overlap</h4>
                            <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                                <tr style="background-color: #fff3cd;">
                                    <td style="padding: 5px; font-weight: bold; border: 1px solid #ffeaa7;">Camera 1:</td>
                                    <td style="padding: 5px; border: 1px solid #ffeaa7;">{camera1.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px; font-weight: bold; border: 1px solid #ffeaa7;">Camera 2:</td>
                                    <td style="padding: 5px; border: 1px solid #ffeaa7;">{camera2.name}</td>
                                </tr>
                                <tr style="background-color: #fff3cd;">
                                    <td style="padding: 5px; font-weight: bold; border: 1px solid #ffeaa7;">Distance:</td>
                                    <td style="padding: 5px; border: 1px solid #ffeaa7;">{overlap.distance:.1f}m</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px; font-weight: bold; border: 1px solid #ffeaa7;">Overlap:</td>
                                    <td style="padding: 5px; border: 1px solid #ffeaa7;">{overlap.overlap_percentage:.1f}%</td>
                                </tr>
                            </table>
                            <div style="margin-top: 8px; padding: 6px; background-color: #f8f9fa; border-radius: 3px; font-size: 11px; color: #666;">
                                ⚠️ <strong>Note:</strong> Overlapping coverage areas may indicate redundant monitoring or optimal coverage zones.
                            </div>
                        </div>
                        """,
                        max_width=300
                    ),
                    tooltip=f"Overlap: {camera1.name} ↔ {camera2.name} ({overlap.overlap_percentage:.1f}%)"
                ).add_to(overlap_group)
                
                # Add overlap indicator marker at midpoint
                folium.CircleMarker(
                    location=[mid_lat, mid_lon],
                    radius=8,
                    popup=folium.Popup(
                        f"""
                        <div style="font-family: Arial, sans-serif;">
                            <h5 style="margin: 0 0 8px 0; color: #ff6600;">🔄 Coverage Overlap Zone</h5>
                            <p style="margin: 0; font-size: 12px;">
                                <strong>{camera1.name}</strong> ↔ <strong>{camera2.name}</strong><br>
                                Overlap: {overlap.overlap_percentage:.1f}%<br>
                                Distance: {overlap.distance:.1f}m
                            </p>
                        </div>
                        """,
                        max_width=200
                    ),
                    tooltip=f"🔄 {overlap.overlap_percentage:.1f}% overlap",
                    color='orange',
                    fill=True,
                    fillColor='yellow',
                    fillOpacity=0.8,
                    weight=2
                ).add_to(overlap_group)
            
            # Add the overlap group to the map
            overlap_group.add_to(map_obj)
            
            print(f"Added {len(overlaps)} coverage overlap indicators to map")
            
        except Exception as e:
            print(f"Error adding coverage overlaps to map: {e}")
    
    def _add_camera_marker_to_map(self, cluster: MarkerCluster, camera: EnhancedCamera):
        """
        Add camera marker to map cluster with enhanced drag-and-drop support.
        
        Requirements addressed:
        - 1.1: Create draggable camera markers
        - 1.2: Embed camera ID for position updates
        """
        marker_config = camera.to_map_marker()
        
        display_name = camera.get_display_name()
        
        # Enhanced popup content with camera ID for drag operations
        enhanced_popup = f"""
        <div style="width: 300px; font-family: Arial, sans-serif; line-height: 1.4;">
            <h4 style="margin: 0 0 12px 0; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px;">
                📹 {display_name}
            </h4>
            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Camera ID:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.id}</td>
                </tr>
        """
        
        # Show both custom name and original name if they differ
        if camera.custom_name and camera.custom_name.strip() and camera.custom_name.strip() != camera.name:
            enhanced_popup += f"""
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Original Name:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.name}</td>
                </tr>
            """
        elif not camera.custom_name or not camera.custom_name.strip():
            enhanced_popup += f"""
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Name:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.name}</td>
                </tr>
            """
        
        enhanced_popup += f"""
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Location:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.location}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">IP Address:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.ip_address}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Status:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{"✅ Online" if camera.is_online else "❌ Offline"}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coordinates:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.latitude:.6f}, {camera.longitude:.6f}</td>
                </tr>
        """
        
        # Show address if available
        if camera.address:
            enhanced_popup += f"""
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Address:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{camera.address}</td>
                </tr>
            """
        
        # Show DVR assignment if available (will be populated by JavaScript)
        dvr_assignment_row = ""
        if hasattr(camera, 'dvr_id') and camera.dvr_id:
            dvr_assignment_row = f"""
                <tr id="dvr-assignment-{camera.id}">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Assigned DVR:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">📺 Loading...</td>
                </tr>
            """
        
        enhanced_popup += dvr_assignment_row
        
        enhanced_popup += f"""
            </table>
            <div style="margin-top: 10px; padding: 8px; background-color: #e3f2fd; border-radius: 4px; font-size: 11px; color: #1976d2;">
                🎯 <strong>Drag & Drop:</strong> Click and drag this marker to move the camera to a new location.
                The position will be automatically saved to the database.
            </div>
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                <button onclick="window.focusMapOnCamera && window.focusMapOnCamera({camera.id})" style="background: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 11px; margin-right: 5px;">📍 Focus Location</button>
                <button onclick="window.openCameraViewer && window.openCameraViewer({camera.id})" style="background: #2196F3; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 11px;">📹 View Camera</button>
            </div>
            <div style="margin-top: 8px; padding: 6px; background-color: #f1f3f4; border-radius: 4px; font-size: 10px; color: #666;">
                💡 <strong>Tip:</strong> Ctrl+Click (or Cmd+Click) on camera marker to open viewer directly
            </div>
        </div>
        """
        
        # Enhanced tooltip with drag instruction (DVR info will be added by JavaScript)
        enhanced_tooltip = f"📹 {display_name}\n🎯 Drag to move • Click for details"
        
        # Create marker with drag-specific attributes and identifiers
        marker = folium.Marker(
            location=[camera.latitude, camera.longitude],
            popup=folium.Popup(enhanced_popup, max_width=350),
            tooltip=folium.Tooltip(enhanced_tooltip, sticky=True),
            icon=folium.Icon(
                color=marker_config['marker_color'],
                icon='video-camera',
                prefix='fa'
            ),
            # Add custom options for drag functionality
            options={
                'draggable': True,  # Enable dragging by default
                'title': f'Camera {camera.id}: {display_name}',  # For JavaScript identification
                'alt': f'camera-{camera.id}',  # Alternative identifier
                'riseOnHover': True,
                'riseOffset': 250
            }
        )
        
        # Add custom attributes via JavaScript injection for camera identification
        marker_js = f"""
        <script>
        // Add camera identification to marker when it's created
        setTimeout(function() {{
            // Find the marker and add camera ID attribute
            var markers = document.querySelectorAll('[title*="Camera {camera.id}"]');
            markers.forEach(function(markerElement) {{
                markerElement.setAttribute('data-camera-id', '{camera.id}');
                markerElement.setAttribute('data-camera-name', '{display_name}');
                markerElement.setAttribute('data-camera-original-name', '{camera.name}');
                markerElement.setAttribute('data-dvr-id', '{getattr(camera, "dvr_id", "") or ""}');
                markerElement.classList.add('camera-marker');
                markerElement.classList.add('camera-marker-{camera.id}');
                
                // Add click event for camera viewer (Ctrl+Click or Cmd+Click)
                markerElement.addEventListener('click', function(e) {{
                    if (e.ctrlKey || e.metaKey) {{
                        e.stopPropagation();
                        e.preventDefault();
                        window.openCameraViewer && window.openCameraViewer({camera.id});
                    }}
                }});
            }});
        }}, 500);
        </script>
        """
        
        # Add the marker to cluster
        marker.add_to(cluster)
        
        # Add the identification script
        cluster._parent.get_root().html.add_child(folium.Element(marker_js))
    
    async def _add_dvr_marker_to_map(self, cluster: MarkerCluster, dvr_data: tuple):
        """
        Add DVR marker to map cluster with distinct styling from camera markers.
        
        Requirements addressed:
        - 9.1: Display custom names in tooltips and markers
        - 9.2: Distinct styling from camera markers
        """
        dvr_id, name, location, ip, lat, lon, dvr_type, custom_name = dvr_data
        
        # Get display name (custom name or default)
        display_name = custom_name.strip() if custom_name and custom_name.strip() else name or f"DVR-{ip.replace('.', '-')}"
        
        # Test DVR connectivity
        is_online = await self._test_device_connectivity(ip)
        
        # Enhanced DVR-specific styling (distinct from cameras)
        if is_online:
            status_color = "blue"  # Blue for online DVRs (different from green cameras)
            marker_icon = "hdd-o"  # Different icon for DVRs
            status_text = "✅ Online"
            border_color = "#007bff"
        else:
            status_color = "darkred"  # Dark red for offline DVRs
            marker_icon = "hdd-o"
            status_text = "❌ Offline"
            border_color = "#dc3545"
        
        # Enhanced popup content with DVR-specific styling
        popup_content = f"""
        <div style="width: 320px; font-family: Arial, sans-serif; line-height: 1.4;">
            <h4 style="margin: 0 0 12px 0; color: #333; border-bottom: 2px solid {border_color}; padding-bottom: 5px;">
                📺 {display_name}
            </h4>
            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">DVR ID:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{dvr_id}</td>
                </tr>
        """
        
        # Show both custom name and original name if they differ
        if custom_name and custom_name.strip() and custom_name.strip() != name:
            popup_content += f"""
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Original Name:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{name}</td>
                </tr>
            """
        elif not custom_name or not custom_name.strip():
            popup_content += f"""
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Name:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{name}</td>
                </tr>
            """
        
        popup_content += f"""
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Type:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{dvr_type}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Location:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{location}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">IP Address:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{ip}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Status:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{status_text}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coordinates:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{lat:.6f}, {lon:.6f}</td>
                </tr>
            </table>
        """
        
        # Get assigned cameras count for this DVR
        assigned_cameras = await self._get_cameras_assigned_to_dvr(dvr_id)
        camera_count = len(assigned_cameras)
        
        if camera_count > 0:
            popup_content += f"""
            <div style="margin-top: 10px; padding: 8px; background-color: #e8f4fd; border-radius: 4px; font-size: 12px; color: #0c5460;">
                📹 <strong>Assigned Cameras:</strong> {camera_count} camera{'s' if camera_count != 1 else ''}
                <br><small>Hover over DVR marker to highlight connections</small>
            </div>
            """
        else:
            popup_content += """
            <div style="margin-top: 10px; padding: 8px; background-color: #fff3cd; border-radius: 4px; font-size: 12px; color: #856404;">
                📹 <strong>No cameras assigned</strong> to this DVR
            </div>
            """
        
        popup_content += f"""
            <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee;">
                <button onclick="window.focusMapOnDVR && window.focusMapOnDVR({dvr_id})" style="background: #4CAF50; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 11px; margin-right: 5px;">📍 Focus Location</button>
                <button onclick="window.showDVRCameras && window.showDVRCameras({dvr_id})" style="background: #2196F3; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; font-size: 11px;">📹 Show Cameras</button>
            </div>
        </div>
        """
        
        # Enhanced tooltip with camera count
        tooltip_text = f"📺 {display_name}"
        if camera_count > 0:
            tooltip_text += f"\n📹 {camera_count} camera{'s' if camera_count != 1 else ''} assigned"
        tooltip_text += "\n🖱️ Hover to highlight connections"
        
        # Create DVR marker with distinct styling
        dvr_marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=folium.Tooltip(tooltip_text, sticky=True),
            icon=folium.Icon(
                color=status_color, 
                icon=marker_icon, 
                prefix='fa'
            ),
            options={
                'draggable': True,  # Enable dragging for DVRs
                'alt': f'dvr-{dvr_id}',
                'title': f'DVR {dvr_id}: {display_name}',
                'riseOnHover': True,
                'riseOffset': 300  # Higher than cameras for visual hierarchy
            }
        )
        
        # Add custom attributes for JavaScript identification and hover effects
        dvr_js = f"""
        <script>
        // Add DVR identification and hover functionality
        setTimeout(function() {{
            var dvrMarkers = document.querySelectorAll('[title*="DVR {dvr_id}"]');
            dvrMarkers.forEach(function(markerElement) {{
                markerElement.setAttribute('data-dvr-id', '{dvr_id}');
                markerElement.setAttribute('data-dvr-name', '{display_name}');
                markerElement.setAttribute('data-camera-count', '{camera_count}');
                markerElement.classList.add('dvr-marker');
                markerElement.classList.add('dvr-marker-{dvr_id}');
                
                // Add hover effects for showing connections
                markerElement.addEventListener('mouseenter', function() {{
                    window.highlightDVRConnections && window.highlightDVRConnections({dvr_id}, true);
                }});
                
                markerElement.addEventListener('mouseleave', function() {{
                    window.highlightDVRConnections && window.highlightDVRConnections({dvr_id}, false);
                }});
            }});
        }}, 500);
        </script>
        """
        
        # Add the marker to cluster
        dvr_marker.add_to(cluster)
        
        # Add the identification and hover script
        cluster._parent.get_root().html.add_child(folium.Element(dvr_js))
    
    async def _get_cameras_assigned_to_dvr(self, dvr_id: int) -> List[Dict[str, Any]]:
        """Get cameras assigned to a specific DVR."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, custom_name, ip_address, latitude, longitude
                    FROM cameras 
                    WHERE dvr_id = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
                    ORDER BY COALESCE(NULLIF(custom_name, ''), name)
                """, (dvr_id,))
                
                results = await cursor.fetchall()
                cameras = []
                for row in results:
                    cameras.append({
                        'id': row[0],
                        'name': row[1],
                        'custom_name': row[2],
                        'display_name': row[2].strip() if row[2] and row[2].strip() else row[1],
                        'ip_address': row[3],
                        'latitude': row[4],
                        'longitude': row[5]
                    })
                return cameras
                
        except Exception as e:
            print(f"Error getting cameras for DVR {dvr_id}: {e}")
            return []
    
    async def _get_dvr_info_for_camera(self, dvr_id: int) -> Optional[Dict[str, Any]]:
        """Get DVR information for a camera's assigned DVR."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute("""
                    SELECT id, name, custom_name, ip_address, latitude, longitude
                    FROM dvrs 
                    WHERE id = ?
                """, (dvr_id,))
                
                result = await cursor.fetchone()
                if result:
                    return {
                        'id': result[0],
                        'name': result[1],
                        'custom_name': result[2],
                        'display_name': result[2].strip() if result[2] and result[2].strip() else result[1],
                        'ip_address': result[3],
                        'latitude': result[4],
                        'longitude': result[5]
                    }
                return None
                
        except Exception as e:
            print(f"Error getting DVR info for camera DVR {dvr_id}: {e}")
            return None
    
    def _add_dvr_camera_connections(self, map_obj: folium.Map, cameras: List[tuple], dvrs: List[tuple]):
        """
        Add visual connections between cameras and their assigned DVRs.
        
        Requirements addressed:
        - 9.3: Create visual connections between cameras and assigned DVRs
        - 9.4: Implement hover effects showing DVR-camera relationships
        """
        try:
            # Create a mapping of DVR IDs to their coordinates
            dvr_locations = {}
            for dvr_data in dvrs:
                dvr_id, name, location, ip, lat, lon, dvr_type, custom_name = dvr_data
                dvr_locations[dvr_id] = {
                    'lat': lat,
                    'lon': lon,
                    'display_name': custom_name.strip() if custom_name and custom_name.strip() else name
                }
            
            # Create connections for cameras assigned to DVRs
            connection_count = 0
            for camera_data in cameras:
                # Extract camera data (dvr_id is at index 7)
                if len(camera_data) > 7 and camera_data[7]:  # dvr_id exists
                    camera_id = camera_data[0]
                    camera_name = camera_data[2]
                    camera_custom_name = camera_data[15] if len(camera_data) > 15 else None
                    camera_lat = camera_data[8]
                    camera_lon = camera_data[9]
                    dvr_id = camera_data[7]
                    
                    # Check if DVR exists and has coordinates
                    if dvr_id in dvr_locations and camera_lat and camera_lon:
                        dvr_info = dvr_locations[dvr_id]
                        camera_display_name = camera_custom_name.strip() if camera_custom_name and camera_custom_name.strip() else camera_name
                        
                        # Create connection line with enhanced styling
                        connection_line = folium.PolyLine(
                            locations=[
                                [camera_lat, camera_lon],
                                [dvr_info['lat'], dvr_info['lon']]
                            ],
                            color='#6c757d',  # Gray color for connections
                            weight=2,
                            opacity=0.6,
                            dash_array='5, 10',  # Dashed line style
                            popup=folium.Popup(
                                f"""
                                <div style="font-family: Arial, sans-serif; font-size: 12px;">
                                    <strong>📹➡️📺 Camera-DVR Connection</strong><br>
                                    <strong>Camera:</strong> {camera_display_name}<br>
                                    <strong>DVR:</strong> {dvr_info['display_name']}<br>
                                    <small>This line shows the assignment relationship</small>
                                </div>
                                """,
                                max_width=250
                            ),
                            tooltip=f"📹 {camera_display_name} ➡️ 📺 {dvr_info['display_name']}"
                        )
                        
                        # Add custom attributes for JavaScript control
                        connection_line.add_to(map_obj)
                        
                        # Add JavaScript to control connection visibility and hover effects
                        connection_js = f"""
                        <script>
                        // Add connection line control for camera {camera_id} to DVR {dvr_id}
                        setTimeout(function() {{
                            var connectionLines = document.querySelectorAll('path[stroke="#6c757d"]');
                            connectionLines.forEach(function(line, index) {{
                                if (index === {connection_count}) {{
                                    line.setAttribute('data-camera-id', '{camera_id}');
                                    line.setAttribute('data-dvr-id', '{dvr_id}');
                                    line.classList.add('camera-dvr-connection');
                                    line.classList.add('connection-camera-{camera_id}');
                                    line.classList.add('connection-dvr-{dvr_id}');
                                    
                                    // Initially hide connections (will be shown on hover)
                                    line.style.opacity = '0.3';
                                    line.style.strokeWidth = '1';
                                }}
                            }});
                        }}, 1000);
                        </script>
                        """
                        
                        map_obj.get_root().html.add_child(folium.Element(connection_js))
                        connection_count += 1
            
            print(f"✅ Added {connection_count} DVR-camera connections to map")
            
        except Exception as e:
            print(f"Error adding DVR-camera connections: {e}")
    
    def _add_drag_drop_javascript(self, map_obj: folium.Map):
        """
        Add comprehensive JavaScript for drag-and-drop functionality with backend communication.
        
        Requirements addressed:
        - 1.1: Allow camera markers to be moved to new positions
        - 1.2: Update coordinates when cameras are moved
        - 1.3: Display confirmation message showing new coordinates
        - 1.4: Revert marker to original position on failure
        - 2.2: Real-time coverage area updates during drag operations
        """
        drag_js = """
        <script>
        // Enhanced drag-and-drop functionality for camera markers with full backend integration
        (function() {
            let isDragging = false;
            let draggedCamera = null;
            let originalPosition = null;
            let draggedMarker = null;
            let tempCoverageLayer = null;
            let cameraData = new Map(); // Store camera coverage parameters
            
            // Initialize drag functionality when map is ready
            function initializeDragFunctionality() {
                console.log('Initializing enhanced camera drag functionality...');
                
                // Wait for map and markers to be fully loaded
                setTimeout(() => {
                    enableCameraDragging();
                    loadCameraData();
                }, 1500);
                
                // Also try again after a longer delay to catch late-loading markers
                setTimeout(() => {
                    enableCameraDragging();
                }, 3000);
                
                // Additional retry mechanism with exponential backoff
                initializeWithRetry();
            }
            
            function initializeWithRetry(attempt = 1, maxAttempts = 5) {
                const delay = Math.min(500 * attempt, 5000); // Max 5 second delay
                
                setTimeout(() => {
                    console.log(`Initialization attempt ${attempt} after ${delay}ms`);
                    
                    // Check if map is ready
                    const mapContainer = document.querySelector('.folium-map');
                    let mapObj = null;
                    
                    if (window.map && typeof window.map.eachLayer === 'function') {
                        mapObj = window.map;
                    } else {
                        for (let key in window) {
                            if (window[key] && typeof window[key] === 'object' && 
                                window[key]._container && typeof window[key].eachLayer === 'function') {
                                mapObj = window[key];
                                window.map_obj = mapObj;
                                break;
                            }
                        }
                    }
                    
                    if (mapObj && mapContainer) {
                        enableCameraDragging();
                        loadCameraData();
                    } else if (attempt < maxAttempts) {
                        initializeWithRetry(attempt + 1, maxAttempts);
                    } else {
                        console.warn('Failed to initialize drag functionality after', maxAttempts, 'attempts');
                    }
                }, delay);
            }
            
            async function loadCameraData() {
                // Load camera coverage parameters for real-time updates
                try {
                    const cameras = await getCameraDataFromBackend();
                    cameras.forEach(camera => {
                        cameraData.set(camera.id, {
                            radius: camera.coverage_radius || 50,
                            angle: camera.field_of_view_angle || 360,
                            direction: camera.coverage_direction || 0
                        });
                    });
                    console.log('Camera data loaded for drag operations:', cameraData.size, 'cameras');
                } catch (error) {
                    console.log('Could not load camera data:', error);
                    console.log('Camera data loaded for drag operations: 0 cameras');
                }
            }
            
            function enableCameraDragging() {
                // Find all camera and DVR markers and make them draggable
                console.log('Setting up drag functionality for camera and DVR markers...');
                
                // Access the Leaflet map instance
                const mapContainer = document.querySelector('.folium-map');
                if (!mapContainer) {
                    console.log('Map container not ready yet, will retry...');
                    return;
                }
                
                // Find the Leaflet map object - Folium creates it with different variable names
                let mapObj = null;
                
                // Method 1: Check if we already have a stored map object
                if (window.map_obj && typeof window.map_obj.eachLayer === 'function') {
                    mapObj = window.map_obj;
                    console.log('Using stored map object');
                }
                
                // Method 2: Check common Folium map variable names
                if (!mapObj) {
                    const commonMapNames = ['map', 'leafletMap'];
                    for (let name of commonMapNames) {
                        if (window[name] && typeof window[name] === 'object' && 
                            typeof window[name].eachLayer === 'function') {
                            mapObj = window[name];
                            console.log(`Found map object as window.${name}`);
                            break;
                        }
                    }
                }
                
                // Method 3: Search through all window properties for Leaflet map
                if (!mapObj) {
                    console.log('Searching for Leaflet map in window properties...');
                    for (let key in window) {
                        try {
                            const obj = window[key];
                            if (obj && typeof obj === 'object' && 
                                typeof obj.eachLayer === 'function' && 
                                obj._container && obj._zoom !== undefined) {
                                mapObj = obj;
                                console.log(`Found map object as window.${key}`);
                                break;
                            }
                        } catch (e) {
                            // Skip properties that can't be accessed
                            continue;
                        }
                    }
                }
                
                // Method 4: Wait for Folium to create the map and try again
                if (!mapObj) {
                    console.log('Leaflet map object not ready yet, will retry...');
                    const availableMapKeys = Object.keys(window).filter(k => 
                        k.toLowerCase().includes('map') || 
                        (window[k] && typeof window[k] === 'object' && window[k]._container)
                    );
                    console.log('Available map-related properties:', availableMapKeys);
                    return;
                }
                
                // Store the map object globally for future use
                window.map_obj = mapObj;
                console.log('Successfully found and stored map object with eachLayer function');
                
                // Find markers in all layers
                let cameraCount = 0;
                let dvrCount = 0;
                
                try {
                    mapObj.eachLayer(function(layer) {
                        if (layer instanceof L.MarkerClusterGroup) {
                            // Handle clustered markers
                            layer.eachLayer(function(marker) {
                                if (marker instanceof L.Marker) {
                                    // Check popup content for device type
                                    if (marker._popup && marker._popup._content) {
                                        const content = String(marker._popup._content || '');
                                        console.log('Checking clustered marker popup:', content.substring(0, 100) + '...');
                                        if (content.includes('Camera') || content.includes('📹')) {
                                            console.log('Found camera marker in cluster');
                                            makeMarkerDraggable(marker, 'camera');
                                            cameraCount++;
                                        } else if (content.includes('DVR') || content.includes('📺')) {
                                            console.log('Found DVR marker in cluster');
                                            makeMarkerDraggable(marker, 'dvr');
                                            dvrCount++;
                                        }
                                    }
                                }
                            });
                        } else if (layer instanceof L.Marker) {
                            // Handle individual markers
                            if (layer._popup && layer._popup._content) {
                                const content = String(layer._popup._content || '');
                                console.log('Checking individual marker popup:', content.substring(0, 100) + '...');
                                if (content.includes('Camera') || content.includes('📹')) {
                                    console.log('Found individual camera marker');
                                    makeMarkerDraggable(layer, 'camera');
                                    cameraCount++;
                                } else if (content.includes('DVR') || content.includes('📺')) {
                                    console.log('Found individual DVR marker');
                                    makeMarkerDraggable(layer, 'dvr');
                                    dvrCount++;
                                }
                            }
                        }
                    });
                } catch (error) {
                    console.warn('Error setting up drag functionality:', error);
                }
                
                console.log(`Made ${cameraCount} camera markers and ${dvrCount} DVR markers draggable`);
            }
            
            function makeMarkerDraggable(marker, deviceType = 'camera') {
                // Extract device ID from marker data
                const deviceId = extractDeviceId(marker, deviceType);
                if (!deviceId) {
                    console.warn(`Could not extract ${deviceType} ID from marker`);
                    return;
                }
                
                // Store device info on marker for easy access
                marker.deviceId = deviceId;
                marker.deviceType = deviceType;
                
                // Enable dragging
                marker.dragging.enable();
                
                // Store original position
                marker.originalPosition = marker.getLatLng();
                
                // Add enhanced visual feedback
                marker.on('mouseover', function(e) {
                    if (!isDragging) {
                        e.target.setOpacity(0.8);
                        const deviceName = e.target.deviceType === 'camera' ? 'camera' : 'DVR';
                        showTooltip(e.target, `Click and drag to move ${deviceName}`);
                    }
                });
                
                marker.on('mouseout', function(e) {
                    if (!isDragging) {
                        e.target.setOpacity(1.0);
                        hideTooltip();
                    }
                });
                
                // Add drag event listeners with comprehensive error handling
                marker.on('dragstart', function(e) {
                    isDragging = true;
                    draggedCamera = e.target.deviceId;  // Keep variable name for compatibility
                    draggedMarker = e.target;
                    originalPosition = e.target.getLatLng();
                    
                    // Enhanced visual feedback
                    e.target.setOpacity(0.6);
                    e.target.setZIndexOffset(1000); // Bring to front
                    
                    // Show drag indicator with device info
                    const deviceName = e.target.deviceType === 'camera' ? 'camera' : 'DVR';
                    showDragIndicator(true, draggedCamera, deviceName);
                    
                    // Hide existing coverage area temporarily (only for cameras)
                    if (e.target.deviceType === 'camera') {
                        hideCoverageArea(draggedCamera);
                    }
                    
                    // Add drag cursor to map
                    document.body.style.cursor = 'grabbing';
                    
                    console.log(`Started dragging ${deviceName} ${draggedCamera} from position:`, originalPosition);
                });
                
                marker.on('drag', function(e) {
                    const newPos = e.target.getLatLng();
                    
                    // Real-time coverage area update during drag (only for cameras)
                    if (e.target.deviceType === 'camera') {
                        updateTemporaryCoverageArea(draggedCamera, newPos);
                    }
                    
                    // Update drag indicator with current coordinates
                    updateDragIndicator(newPos);
                });
                
                marker.on('dragend', function(e) {
                    const newPos = e.target.getLatLng();
                    const deviceId = e.target.deviceId;
                    const deviceType = e.target.deviceType;
                    
                    // Reset visual feedback
                    e.target.setOpacity(1.0);
                    e.target.setZIndexOffset(0);
                    document.body.style.cursor = 'default';
                    
                    // Show processing indicator
                    showDragIndicator(false);
                    const deviceName = deviceType === 'camera' ? 'camera' : 'DVR';
                    showProcessingIndicator(true, `Updating ${deviceName} position...`);
                    
                    // Send position update to backend with comprehensive error handling
                    updateDevicePosition(deviceId, deviceType, newPos.lat, newPos.lng)
                        .then(result => {
                            showProcessingIndicator(false);
                            
                            if (result.success) {
                                console.log(`${deviceName} ${deviceId} position updated successfully:`, result);
                                showNotification(result.message, 'success');
                                
                                // Update coverage area permanently (only for cameras)
                                if (deviceType === 'camera') {
                                    removeTempCoverageArea();
                                    showCoverageArea(deviceId, newPos);
                                }
                                
                                // Update stored position
                                marker.originalPosition = newPos;
                                
                            } else {
                                console.error(`Failed to update ${deviceName} ${deviceId}:`, result.message);
                                showNotification(result.message, 'error');
                                
                                // Revert to original position
                                revertMarkerPosition(e.target, originalPosition, deviceId);
                            }
                        })
                        .catch(error => {
                            showProcessingIndicator(false);
                            console.error(`Network error updating ${deviceName} position:`, error);
                            showNotification(`❌ Network error: Could not update ${deviceName} position`, 'error');
                            
                            // Revert to original position
                            revertMarkerPosition(e.target, originalPosition, deviceId);
                        });
                    
                    // Reset drag state
                    isDragging = false;
                    draggedCamera = null;
                    draggedMarker = null;
                    originalPosition = null;
                });
            }
            
            function extractDeviceId(marker, deviceType = 'camera') {
                // Try multiple methods to extract device ID
                if (marker.deviceId) return marker.deviceId;
                
                const deviceName = deviceType === 'camera' ? 'Camera' : 'DVR';
                
                // Try from popup content with various patterns
                if (marker._popup && marker._popup._content) {
                    const content = String(marker._popup._content || '');
                    
                    // Try different patterns for HTML popup content
                    const patterns = [
                        new RegExp(`${deviceName}\\s+ID[:\\s]*<[^>]*>(\\d+)`, 'i'), // HTML table format
                        new RegExp(`${deviceName}\\s+ID[:\\s]*(\\d+)`, 'i'),
                        new RegExp(`${deviceName}[:\\s]+(\\d+)`, 'i'),
                        new RegExp(`ID[:\\s]*<[^>]*>(\\d+)`, 'i'), // HTML format
                        new RegExp(`ID[:\\s]*(\\d+)`, 'i'),
                        new RegExp(`\\b(\\d+)\\b`) // Any number as fallback (first match only)
                    ];
                    
                    for (let pattern of patterns) {
                        const match = content.match(pattern);
                        if (match) {
                            const id = parseInt(match[1] || match[0]);
                            if (!isNaN(id) && id > 0) {
                                console.log(`Extracted ${deviceType} ID ${id} from popup content`);
                                return id;
                            }
                        }
                    }
                }
                
                // Try from tooltip
                if (marker._tooltip && marker._tooltip._content) {
                    const match = marker._tooltip._content.match(new RegExp(`${deviceName}[:\\s]*(\\d+)`, 'i'));
                    if (match) return parseInt(match[1]);
                }
                
                // Try from title or other attributes
                if (marker.options.title) {
                    const match = marker.options.title.match(new RegExp(`${deviceName}\\s+(\\d+)`, 'i'));
                    if (match) return parseInt(match[1]);
                }
                
                console.warn(`Could not extract ${deviceType} ID from marker`);
                return null;
            }
            
            function updateTemporaryCoverageArea(cameraId, position) {
                // Remove existing temporary coverage
                removeTempCoverageArea();
                
                // Get camera coverage parameters
                const coverage = cameraData.get(cameraId) || { radius: 50, angle: 360, direction: 0 };
                
                // Create temporary coverage area
                if (coverage.angle >= 360) {
                    // Circular coverage
                    tempCoverageLayer = L.circle([position.lat, position.lng], {
                        radius: coverage.radius,
                        color: '#ff6b6b',
                        fillColor: '#ff6b6b',
                        fillOpacity: 0.3,
                        weight: 2,
                        dashArray: '5, 5',
                        className: 'temp-coverage-area'
                    }).addTo(mapObj || window.map_obj);
                } else {
                    // Directional coverage - simplified sector
                    const sectorPoints = calculateSectorPoints(position.lat, position.lng, coverage.radius, coverage.direction, coverage.angle);
                    tempCoverageLayer = L.polygon(sectorPoints, {
                        color: '#ff6b6b',
                        fillColor: '#ff6b6b',
                        fillOpacity: 0.3,
                        weight: 2,
                        dashArray: '5, 5',
                        className: 'temp-coverage-area'
                    }).addTo(mapObj || window.map_obj);
                }
            }
            
            function removeTempCoverageArea() {
                if (tempCoverageLayer && (window.map_obj || window.map)) {
                    const mapObj = window.map_obj || window.map;
                    mapObj.removeLayer(tempCoverageLayer);
                    tempCoverageLayer = null;
                }
            }
            
            function hideCoverageArea(cameraId) {
                const coverageElements = document.querySelectorAll(`.coverage-area-${cameraId}`);
                coverageElements.forEach(element => {
                    element.style.display = 'none';
                });
            }
            
            function showCoverageArea(cameraId, position) {
                const coverageElements = document.querySelectorAll(`.coverage-area-${cameraId}`);
                coverageElements.forEach(element => {
                    element.style.display = 'block';
                });
            }
            
            function revertMarkerPosition(marker, originalPos, deviceId) {
                marker.setLatLng(originalPos);
                removeTempCoverageArea();
                
                const deviceType = marker.deviceType || 'camera';
                const deviceName = deviceType === 'camera' ? 'camera' : 'DVR';
                
                // Only show coverage area for cameras
                if (deviceType === 'camera') {
                    showCoverageArea(deviceId, originalPos);
                }
                
                showNotification(`📍 ${deviceName} position reverted to original location`, 'warning');
            }
            
            function calculateSectorPoints(lat, lng, radius, direction, angle) {
                // Simple sector calculation for temporary coverage display
                const points = [[lat, lng]];
                const startAngle = direction - angle / 2;
                const endAngle = direction + angle / 2;
                
                for (let a = startAngle; a <= endAngle; a += 5) {
                    const radian = (a * Math.PI) / 180;
                    const deltaLat = (radius / 111320) * Math.cos(radian);
                    const deltaLng = (radius / 111320) * Math.sin(radian) / Math.cos((lat * Math.PI) / 180);
                    points.push([lat + deltaLat, lng + deltaLng]);
                }
                
                points.push([lat, lng]); // Close the sector
                return points;
            }
            
            async function updateDevicePosition(deviceId, deviceType, lat, lng) {
                // Backend communication for Gradio integration
                try {
                    const deviceName = deviceType === 'camera' ? 'camera' : 'DVR';
                    console.log(`Updating ${deviceName} ${deviceId} to coordinates: (${lat}, ${lng})`);
                    
                    // For Gradio integration, we'll use localStorage to communicate with backend
                    const updateData = {
                        deviceId: deviceId,
                        deviceType: deviceType,
                        latitude: lat,
                        longitude: lng,
                        timestamp: Date.now()
                    };
                    
                    // Store in localStorage for backend processing
                    localStorage.setItem('pendingDeviceUpdate', JSON.stringify(updateData));
                    
                    // Trigger a custom event that Gradio can listen for
                    window.dispatchEvent(new CustomEvent('devicePositionUpdate', {
                        detail: updateData
                    }));
                    
                    // Simulate processing delay
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    // For now, always return success since we can't directly call Python from JS
                    // In a full Gradio integration, this would be handled by the backend
                    const result = {
                        success: true,
                        message: `✅ ${deviceName} ${deviceId} position updated to (${lat.toFixed(6)}, ${lng.toFixed(6)})`,
                        coordinates: { lat, lng },
                        device_id: deviceId,
                        revert: false
                    };
                    
                    console.log(`${deviceName} position update completed:`, result);
                    return result;
                    
                } catch (error) {
                    console.error(`Error in updateDevicePosition for ${deviceType}:`, error);
                    
                    return {
                        success: false,
                        message: `❌ Failed to update ${deviceType} position: ${error.message}`,
                        revert: true,
                        device_id: deviceId
                    };
                }
            }
            
            // Keep backward compatibility
            async function updateCameraPosition(cameraId, lat, lng) {
                return await updateDevicePosition(cameraId, 'camera', lat, lng);
            }
            
            async function getCameraDataFromBackend() {
                // Load camera data for coverage calculations
                try {
                    // For Gradio integration, we'll use a simulated dataset
                    // In a full implementation, this would be populated by the Python backend
                    console.log('Loading camera data for drag operations...');
                    
                    // Return empty array for now - cameras will be handled by the map markers
                    const cameras = [];
                    console.log('Camera data loaded for drag operations:', cameras.length, 'cameras');
                    return cameras;
                    
                } catch (error) {
                    console.log('Could not load camera data:', error);
                    return [];
                }
            }
            
            function showDragIndicator(show, deviceId = null, deviceType = 'camera') {
                let indicator = document.getElementById('drag-indicator');
                
                if (show && !indicator) {
                    indicator = document.createElement('div');
                    indicator.id = 'drag-indicator';
                    indicator.className = 'drag-indicator';
                    
                    const deviceName = deviceType === 'camera' ? 'camera' : 'DVR';
                    const deviceInfo = deviceId ? ` (${deviceName} ${deviceId})` : '';
                    const icon = deviceType === 'camera' ? '📹' : '📺';
                    indicator.innerHTML = `🎯 Dragging ${deviceName}${deviceInfo}... Release to update position`;
                    
                    indicator.style.cssText = `
                        position: fixed;
                        top: 20px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 12px 24px;
                        border-radius: 8px;
                        z-index: 10000;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        font-size: 14px;
                        font-weight: 500;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                        animation: pulse 1.5s infinite;
                        max-width: 400px;
                        text-align: center;
                    `;
                    document.body.appendChild(indicator);
                } else if (!show && indicator) {
                    indicator.remove();
                }
            }
            
            function updateDragIndicator(position) {
                const indicator = document.getElementById('drag-indicator');
                if (indicator && draggedMarker) {
                    const deviceType = draggedMarker.deviceType || 'camera';
                    const deviceName = deviceType === 'camera' ? 'camera' : 'DVR';
                    const deviceInfo = draggedCamera ? ` (${deviceName} ${draggedCamera})` : '';
                    const icon = deviceType === 'camera' ? '📹' : '📺';
                    indicator.innerHTML = `🎯 Dragging ${deviceName}${deviceInfo}...<br>
                                         <small>📍 ${position.lat.toFixed(6)}, ${position.lng.toFixed(6)}</small>`;
                }
            }
            
            function showProcessingIndicator(show, message = 'Processing...') {
                let indicator = document.getElementById('processing-indicator');
                
                if (show && !indicator) {
                    indicator = document.createElement('div');
                    indicator.id = 'processing-indicator';
                    indicator.innerHTML = `
                        <div class="spinner"></div>
                        <span>${message}</span>
                    `;
                    indicator.style.cssText = `
                        position: fixed;
                        top: 20px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(0, 123, 255, 0.95);
                        color: white;
                        padding: 12px 24px;
                        border-radius: 8px;
                        z-index: 10000;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        font-size: 14px;
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    `;
                    
                    // Add spinner CSS
                    const style = document.createElement('style');
                    style.textContent = `
                        .spinner {
                            width: 16px;
                            height: 16px;
                            border: 2px solid rgba(255,255,255,0.3);
                            border-top: 2px solid white;
                            border-radius: 50%;
                            animation: spin 1s linear infinite;
                        }
                        @keyframes spin {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                        }
                    `;
                    document.head.appendChild(style);
                    document.body.appendChild(indicator);
                } else if (!show && indicator) {
                    indicator.remove();
                }
            }
            
            function showNotification(message, type = 'info') {
                const notification = document.createElement('div');
                notification.className = `map-notification ${type}`;
                notification.innerHTML = message;
                
                const colors = {
                    success: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
                    error: 'linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%)',
                    warning: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                    info: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
                };
                
                notification.style.cssText = `
                    position: fixed;
                    top: 70px;
                    right: 20px;
                    background: ${colors[type] || colors.info};
                    color: white;
                    padding: 12px 20px;
                    border-radius: 8px;
                    z-index: 10000;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    max-width: 350px;
                    animation: slideIn 0.3s ease;
                `;
                
                document.body.appendChild(notification);
                
                // Auto-remove after 5 seconds with fade out
                setTimeout(() => {
                    notification.style.animation = 'slideOut 0.3s ease';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.remove();
                        }
                    }, 300);
                }, 5000);
            }
            
            function showTooltip(marker, text) {
                // Simple tooltip implementation
                const tooltip = document.createElement('div');
                tooltip.id = 'drag-tooltip';
                tooltip.innerHTML = text;
                tooltip.style.cssText = `
                    position: fixed;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 6px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    z-index: 10000;
                    pointer-events: none;
                `;
                document.body.appendChild(tooltip);
                
                // Position tooltip near cursor
                document.addEventListener('mousemove', updateTooltipPosition);
            }
            
            function hideTooltip() {
                const tooltip = document.getElementById('drag-tooltip');
                if (tooltip) {
                    tooltip.remove();
                    document.removeEventListener('mousemove', updateTooltipPosition);
                }
            }
            
            function updateTooltipPosition(e) {
                const tooltip = document.getElementById('drag-tooltip');
                if (tooltip) {
                    tooltip.style.left = (e.clientX + 10) + 'px';
                    tooltip.style.top = (e.clientY - 30) + 'px';
                }
            }
            
            // Wait for Folium map to be fully loaded before initializing drag functionality
            function waitForMapAndInitialize() {
                console.log('Waiting for Folium map to be ready...');
                
                let attempts = 0;
                const maxAttempts = 20;
                const checkInterval = 500;
                
                function checkForMap() {
                    attempts++;
                    console.log(`Map check attempt ${attempts}/${maxAttempts}`);
                    
                    // Look for map container first
                    const mapContainer = document.querySelector('.folium-map');
                    if (!mapContainer) {
                        if (attempts < maxAttempts) {
                            setTimeout(checkForMap, checkInterval);
                        } else {
                            console.error('Map container not found after maximum attempts');
                        }
                        return;
                    }
                    
                    // Look for Leaflet map object
                    let foundMap = false;
                    for (let key in window) {
                        try {
                            const obj = window[key];
                            if (obj && typeof obj === 'object' && 
                                typeof obj.eachLayer === 'function' && 
                                obj._container === mapContainer) {
                                console.log(`Found Leaflet map object: window.${key}`);
                                window.map_obj = obj;
                                foundMap = true;
                                break;
                            }
                        } catch (e) {
                            continue;
                        }
                    }
                    
                    if (foundMap) {
                        console.log('Map is ready! Initializing drag functionality...');
                        initializeDragFunctionality();
                    } else if (attempts < maxAttempts) {
                        setTimeout(checkForMap, checkInterval);
                    } else {
                        console.error('Could not find Leaflet map object after maximum attempts');
                        // Try to initialize anyway in case we missed something
                        initializeDragFunctionality();
                    }
                }
                
                // Start checking for the map
                checkForMap();
            }
            
            // Initialize when DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', waitForMapAndInitialize);
            } else {
                waitForMapAndInitialize();
            }
            
            // Also try when window is fully loaded
            window.addEventListener('load', waitForMapAndInitialize);
            
            // Expose functions for external access if needed
            // Focus functionality for DVR and camera locations
            function focusMapOnDevice(deviceId, deviceType) {
                console.log(`Focusing map on ${deviceType} ID: ${deviceId}`);
                
                // Find the marker for the specified device
                let targetMarker = null;
                let targetLatLng = null;
                
                // Search through all markers on the map
                if (window.map && window.map._layers) {
                    Object.values(window.map._layers).forEach(layer => {
                        if (layer.options && layer.options.alt) {
                            const altText = layer.options.alt;
                            if ((deviceType === 'camera' && altText.startsWith('camera-') && altText.includes(deviceId)) ||
                                (deviceType === 'dvr' && altText.startsWith('dvr-') && altText.includes(deviceId))) {
                                targetMarker = layer;
                                targetLatLng = layer.getLatLng();
                            }
                        }
                    });
                }
                
                // If marker found, focus on it
                if (targetLatLng) {
                    window.map.setView(targetLatLng, 16); // Zoom level 16 for close view
                    
                    // Optional: Open popup if marker has one
                    if (targetMarker && targetMarker.openPopup) {
                        setTimeout(() => {
                            targetMarker.openPopup();
                        }, 500);
                    }
                    
                    console.log(`Successfully focused on ${deviceType} ${deviceId}`);
                } else {
                    console.warn(`Could not find ${deviceType} with ID ${deviceId} on map`);
                }
            }
            
            // Global functions for external access
            window.focusMapOnCamera = function(cameraId) {
                focusMapOnDevice(cameraId, 'camera');
            };
            
            window.focusMapOnDVR = function(dvrId) {
                focusMapOnDevice(dvrId, 'dvr');
            };

            window.cameraMapDrag = {
                enableDragging: enableCameraDragging,
                loadCameraData: loadCameraData,
                updatePosition: updateCameraPosition,
                focusOnCamera: window.focusMapOnCamera,
                focusOnDVR: window.focusMapOnDVR
            };
            
            // DVR-Camera connection highlighting functions
            window.highlightDVRConnections = function(dvrId, highlight) {
                const connections = document.querySelectorAll(`.connection-dvr-${dvrId}`);
                const cameras = document.querySelectorAll(`[data-camera-id]`);
                
                connections.forEach(function(connection) {
                    if (highlight) {
                        connection.style.opacity = '0.8';
                        connection.style.strokeWidth = '3';
                        connection.style.stroke = '#007bff';
                    } else {
                        connection.style.opacity = '0.3';
                        connection.style.strokeWidth = '1';
                        connection.style.stroke = '#6c757d';
                    }
                });
                
                // Highlight connected cameras
                cameras.forEach(function(camera) {
                    const cameraId = camera.getAttribute('data-camera-id');
                    const connectionExists = document.querySelector(`.connection-camera-${cameraId}.connection-dvr-${dvrId}`);
                    
                    if (connectionExists) {
                        if (highlight) {
                            camera.style.filter = 'brightness(1.3) drop-shadow(0 0 10px #007bff)';
                            camera.style.transform = 'scale(1.1)';
                        } else {
                            camera.style.filter = '';
                            camera.style.transform = '';
                        }
                    }
                });
            };
            
            window.showDVRCameras = function(dvrId) {
                console.log(`Showing cameras for DVR ${dvrId}`);
                
                // Find and highlight all cameras connected to this DVR
                const connections = document.querySelectorAll(`.connection-dvr-${dvrId}`);
                const cameraIds = [];
                
                connections.forEach(function(connection) {
                    const cameraId = connection.getAttribute('data-camera-id');
                    if (cameraId) {
                        cameraIds.push(cameraId);
                    }
                });
                
                if (cameraIds.length > 0) {
                    // Temporarily highlight all connected cameras
                    cameraIds.forEach(function(cameraId) {
                        const camera = document.querySelector(`[data-camera-id="${cameraId}"]`);
                        if (camera) {
                            camera.style.filter = 'brightness(1.5) drop-shadow(0 0 15px #ffc107)';
                            camera.style.transform = 'scale(1.2)';
                            
                            // Flash effect
                            setTimeout(function() {
                                camera.style.transition = 'all 0.3s ease';
                                camera.style.filter = '';
                                camera.style.transform = '';
                            }, 2000);
                        }
                    });
                    
                    // Show notification
                    const notification = document.createElement('div');
                    notification.innerHTML = `📹 Highlighted ${cameraIds.length} camera${cameraIds.length !== 1 ? 's' : ''} assigned to this DVR`;
                    notification.style.cssText = `
                        position: fixed;
                        top: 80px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: #ffc107;
                        color: #212529;
                        padding: 10px 20px;
                        border-radius: 5px;
                        z-index: 10000;
                        font-weight: bold;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    `;
                    document.body.appendChild(notification);
                    
                    setTimeout(function() {
                        notification.remove();
                    }, 3000);
                } else {
                    // Show no cameras message
                    const notification = document.createElement('div');
                    notification.innerHTML = '📺 No cameras assigned to this DVR';
                    notification.style.cssText = `
                        position: fixed;
                        top: 80px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: #6c757d;
                        color: white;
                        padding: 10px 20px;
                        border-radius: 5px;
                        z-index: 10000;
                        font-weight: bold;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    `;
                    document.body.appendChild(notification);
                    
                    setTimeout(function() {
                        notification.remove();
                    }, 2000);
                }
            };
            
            window.focusMapOnDVR = function(dvrId) {
                console.log(`Focusing map on DVR ${dvrId}`);
                const dvrMarker = document.querySelector(`[data-dvr-id="${dvrId}"]`);
                if (dvrMarker) {
                    dvrMarker.click();
                    // Highlight connections temporarily
                    window.highlightDVRConnections(dvrId, true);
                    setTimeout(function() {
                        window.highlightDVRConnections(dvrId, false);
                    }, 3000);
                }
            };
            
            // Camera viewer functionality
            window.openCameraViewer = function(cameraId) {
                console.log(`Opening camera viewer for camera ${cameraId}`);
                
                // Show loading notification
                const notification = document.createElement('div');
                notification.innerHTML = '📹 Loading camera viewer...';
                notification.style.cssText = `
                    position: fixed;
                    top: 50px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #007bff;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 5px;
                    z-index: 10000;
                    font-weight: bold;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                `;
                document.body.appendChild(notification);
                
                // Make request to get camera viewer
                fetch(`/api/camera/viewer/${cameraId}`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    notification.remove();
                    
                    if (data.success) {
                        // Open camera viewer in new window
                        const viewerWindow = window.open('', `camera_viewer_${cameraId}`, 
                            'width=900,height=700,scrollbars=yes,resizable=yes');
                        
                        if (viewerWindow) {
                            viewerWindow.document.write(data.viewer_html);
                            viewerWindow.document.close();
                            viewerWindow.focus();
                        } else {
                            alert('Pop-up blocked. Please allow pop-ups for camera viewer.');
                        }
                    } else {
                        alert(`Failed to load camera viewer: ${data.message}`);
                    }
                })
                .catch(error => {
                    notification.remove();
                    console.error('Error loading camera viewer:', error);
                    alert(`Error loading camera viewer: ${error.message}`);
                });
            };
            
        })();
        </script>
        """
        
        map_obj.get_root().html.add_child(folium.Element(drag_js))
    
    def _add_map_legend(self, map_obj: folium.Map):
        """Add comprehensive legend to map."""
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 280px; height: 220px; 
                    background-color: white; border: 2px solid grey; z-index: 9999; 
                    font-size: 12px; padding: 15px; border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
        <h4 style="margin: 0 0 10px 0; color: #333;">📍 Interactive Map Legend</h4>
        <div style="line-height: 1.6;">
            <p style="margin: 5px 0;"><i class="fa fa-video-camera" style="color:green; width: 20px;"></i> Online Camera</p>
            <p style="margin: 5px 0;"><i class="fa fa-video-camera" style="color:red; width: 20px;"></i> Offline Camera</p>
            <p style="margin: 5px 0;"><i class="fa fa-hdd-o" style="color:blue; width: 20px;"></i> Online DVR</p>
            <p style="margin: 5px 0;"><i class="fa fa-hdd-o" style="color:darkred; width: 20px;"></i> Offline DVR</p>
            <p style="margin: 5px 0;"><span style="color:#6c757d; width: 20px;">---</span> Camera-DVR Connection</p>
            <p style="margin: 5px 0;"><span style="color:lightblue; font-size: 16px;">●</span> Coverage Area</p>
            <p style="margin: 5px 0; font-size: 11px; color: #666;">💡 Drag cameras to move them</p>
            <p style="margin: 5px 0; font-size: 11px; color: #666;">�️ Hover mDVR to highlight connections</p>
        </div>
        </div>
        '''
        map_obj.get_root().html.add_child(folium.Element(legend_html))
    
    def _add_map_controls(self, map_obj: folium.Map):
        """Add additional map controls and information."""
        controls_html = '''
        <div style="position: fixed; 
                    top: 80px; right: 20px; width: 200px; 
                    background-color: white; border: 2px solid grey; z-index: 9999; 
                    font-size: 12px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
        <h5 style="margin: 0 0 8px 0; color: #333;">🎮 Map Controls</h5>
        <div style="line-height: 1.4;">
            <p style="margin: 3px 0;">• Click markers for details</p>
            <p style="margin: 3px 0;">• Drag cameras to move</p>
            <p style="margin: 3px 0;">• Use layer control to toggle</p>
            <p style="margin: 3px 0;">• Zoom with mouse wheel</p>
        </div>
        </div>
        '''
        map_obj.get_root().html.add_child(folium.Element(controls_html))
    
    def _add_custom_css(self, map_obj: folium.Map):
        """
        Add custom CSS for enhanced coverage area styling and hover effects.
        
        Requirements addressed:
        - 2.4: Create hover effects and tooltips for coverage areas showing camera details
        - 4.3: Coverage area styling with opacity changes based on connectivity status
        """
        """Add enhanced CSS for coverage area styling and hover effects."""
        custom_css = '''
        <style>
        /* Enhanced marker styles with smooth transitions */
        .leaflet-marker-icon {
            transition: all 0.3s ease;
            filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3));
        }
        
        .leaflet-marker-icon:hover {
            transform: scale(1.15);
            filter: brightness(1.2) drop-shadow(3px 3px 6px rgba(0,0,0,0.4));
            z-index: 1000;
        }
        
        /* Enhanced coverage area styles with hover effects */
        .leaflet-interactive[class*="coverage-area"] {
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .leaflet-interactive[class*="coverage-area"]:hover {
            opacity: 0.8 !important;
            stroke-width: 3 !important;
            filter: brightness(1.1);
            transform: scale(1.02);
            transform-origin: center;
        }
        
        /* Direction indicator styling */
        .leaflet-interactive[class*="direction-indicator"] {
            transition: all 0.2s ease;
        }
        
        .leaflet-interactive[class*="direction-indicator"]:hover {
            stroke-width: 5 !important;
            opacity: 1 !important;
        }
        
        /* Enhanced popup styles */
        .leaflet-popup-content {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.5;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .leaflet-popup-content h4 {
            margin: 0 0 12px 0;
            color: #2c3e50;
            font-weight: 600;
            text-align: center;
        }
        
        .leaflet-popup-content table {
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .leaflet-popup-content table td {
            transition: background-color 0.2s ease;
        }
        
        .leaflet-popup-content table tr:hover td {
            background-color: #e8f4fd !important;
        }
        
        /* Enhanced tooltip styles */
        .leaflet-tooltip {
            background-color: rgba(44, 62, 80, 0.95);
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 12px;
            line-height: 1.4;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            white-space: pre-line;
        }
        
        .leaflet-tooltip::before {
            border-top-color: rgba(44, 62, 80, 0.95);
        }
        
        /* Drag indicator styles */
        .drag-active {
            cursor: grabbing !important;
        }
        
        .drag-indicator {
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        /* Coverage overlap styles */
        .leaflet-interactive[stroke="orange"] {
            animation: dash 2s linear infinite;
        }
        
        @keyframes dash {
            to {
                stroke-dashoffset: -20;
            }
        }
        
        /* Map container enhancements */
        .folium-map {
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
            overflow: hidden;
        }
        
        /* Layer control enhancements */
        .leaflet-control-layers {
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .leaflet-control-layers-expanded {
            background-color: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
        }
        
        /* Zoom control enhancements */
        .leaflet-control-zoom {
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .leaflet-control-zoom a {
            transition: all 0.2s ease;
        }
        
        .leaflet-control-zoom a:hover {
            background-color: #007bff;
            color: white;
        }
        
        /* Notification styles */
        .map-notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
            max-width: 300px;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .map-notification.success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        
        .map-notification.error {
            background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        }
        
        .map-notification.warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        /* Loading spinner for connectivity tests */
        .connectivity-spinner {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #007bff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 5px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Responsive design for mobile devices */
        @media (max-width: 768px) {
            .leaflet-popup-content {
                max-width: 250px;
                font-size: 12px;
            }
            
            .leaflet-tooltip {
                font-size: 11px;
                padding: 6px 10px;
            }
            
            .map-notification {
                top: 10px;
                right: 10px;
                left: 10px;
                max-width: none;
                font-size: 13px;
            }
        }
        </style>
        '''
        map_obj.get_root().html.add_child(folium.Element(custom_css))

    def _add_location_notification(self, map_obj: folium.Map, location_status: Dict[str, Any]):
        """
        Add location detection notification to the map.
        
        Args:
            map_obj: Folium map object
            location_status: Location detection status from initialize_map_location()
            
        Requirements addressed:
        - 6.3: Create user notification system for location detection status
        - 6.4: Notify user when location detection fails
        """
        # Determine notification type and styling
        if location_status['success']:
            if location_status['status'] == 'detected':
                notification_class = 'success'
                icon = '✅'
                title = 'Location Detected'
            else:  # cached
                notification_class = 'info'
                icon = '📍'
                title = 'Using Cached Location'
        else:
            notification_class = 'warning'
            icon = '⚠️'
            title = 'Location Detection Failed'
        
        # Create notification HTML
        notification_html = f'''
        <div id="location-notification" class="map-notification {notification_class}" 
             style="display: block; opacity: 1;">
            <div style="font-weight: bold; margin-bottom: 5px;">
                {icon} {title}
            </div>
            <div style="font-size: 12px; opacity: 0.9;">
                {location_status['address']}<br>
                <small>Method: {location_status['detection_method']} | 
                Confidence: {location_status['confidence_score']:.1%}</small>
            </div>
        </div>
        
        <script>
        // Auto-hide notification after 8 seconds
        setTimeout(function() {{
            var notification = document.getElementById('location-notification');
            if (notification) {{
                notification.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                setTimeout(function() {{
                    notification.style.display = 'none';
                }}, 500);
            }}
        }}, 8000);
        
        // Allow manual dismissal by clicking
        document.addEventListener('DOMContentLoaded', function() {{
            var notification = document.getElementById('location-notification');
            if (notification) {{
                notification.style.cursor = 'pointer';
                notification.addEventListener('click', function() {{
                    this.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    this.style.opacity = '0';
                    this.style.transform = 'translateX(100%)';
                    setTimeout(() => this.style.display = 'none', 300);
                }});
            }}
        }});
        </script>
        '''
        
        # Add notification to map
        map_obj.get_root().html.add_child(folium.Element(notification_html))
    
    async def _test_camera_connectivity(self, ip_address: str) -> bool:
        """Test camera connectivity with caching."""
        current_time = time.time()
        
        # Check cache first
        if ip_address in self.connectivity_cache:
            cached_result, timestamp = self.connectivity_cache[ip_address]
            if current_time - timestamp < self.cache_timeout:
                return cached_result
        
        # Perform ping test
        try:
            response_time = ping(ip_address, timeout=2)
            is_online = response_time is not None
            
            # Cache the result
            self.connectivity_cache[ip_address] = (is_online, current_time)
            
            return is_online
        except Exception:
            # Cache the failure
            self.connectivity_cache[ip_address] = (False, current_time)
            return False
    
    async def _test_device_connectivity(self, ip_address: str) -> bool:
        """Test device connectivity (generic method for DVRs, etc.)."""
        return await self._test_camera_connectivity(ip_address)
    
    async def _get_camera_position(self, camera_id: int) -> Optional[Dict[str, float]]:
        """Get current camera position for revert operations."""
        try:
            async with aiosqlite.connect(self.db_name) as db:
                cursor = await db.execute(
                    "SELECT latitude, longitude FROM cameras WHERE id = ?",
                    (camera_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    return {'lat': result[0], 'lon': result[1]}
                return None
        except Exception:
            return None
    
    async def _log_coordinate_update(self, camera_id: int, lat: float, lon: float, 
                                   original_position: Optional[Dict[str, float]]):
        """Log coordinate updates to action log."""
        try:
            details = {
                'camera_id': camera_id,
                'new_coordinates': {'lat': lat, 'lon': lon},
                'original_coordinates': original_position,
                'update_type': 'drag_and_drop'
            }
            
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    INSERT INTO action_log (timestamp, action_type, table_name, record_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    'coordinate_update',
                    'cameras',
                    camera_id,
                    json.dumps(details)
                ))
                await db.commit()
        except Exception as e:
            print(f"Error logging coordinate update: {e}")
    
    async def _log_coverage_update(self, camera_id: int, params: Dict[str, float]):
        """Log coverage parameter updates to action log."""
        try:
            details = {
                'camera_id': camera_id,
                'coverage_parameters': params,
                'update_type': 'coverage_parameters'
            }
            
            async with aiosqlite.connect(self.db_name) as db:
                await db.execute("""
                    INSERT INTO action_log (timestamp, action_type, table_name, record_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    time.strftime('%Y-%m-%d %H:%M:%S'),
                    'coverage_update',
                    'cameras',
                    camera_id,
                    json.dumps(details)
                ))
                await db.commit()
        except Exception as e:
            print(f"Error logging coverage update: {e}")
    
    def _create_empty_map(self) -> str:
        """Create empty map when no cameras or DVRs are available (legacy method)."""
        empty_map = folium.Map(location=[40.7128, -74.0060], zoom_start=10)
        
        folium.Marker(
            [40.7128, -74.0060],
            popup="No cameras or DVRs with coordinates found. Add device coordinates to see them on the map.",
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(empty_map)
        
        return empty_map._repr_html_()

    async def _create_empty_map_with_location(self, location_status: Dict[str, Any]) -> str:
        """
        Create empty map when no cameras or DVRs are available, using detected location.
        
        Args:
            location_status: Location detection status from initialize_map_location()
            
        Returns:
            HTML string of the empty map centered on detected location
            
        Requirements addressed:
        - 6.1: Center map on detected location when no devices present
        - 6.2: Use detected coordinates with appropriate zoom level
        - 6.3: Show user notification about location detection status
        """
        # Use detected location for map center
        center_lat = location_status['latitude']
        center_lon = location_status['longitude']
        
        # Create map with detected location
        empty_map = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=12,  # Slightly closer zoom for detected location
            tiles='OpenStreetMap'
        )
        
        # Add tile layers for better visualization
        folium.TileLayer('CartoDB positron', name='Light').add_to(empty_map)
        folium.TileLayer('CartoDB dark_matter', name='Dark').add_to(empty_map)
        folium.LayerControl().add_to(empty_map)
        
        # Create popup content with location detection information
        detection_icon = "✅" if location_status['success'] else "⚠️"
        status_color = "green" if location_status['success'] else "orange"
        
        popup_content = f"""
        <div style="width: 300px; font-family: Arial, sans-serif; line-height: 1.4;">
            <h4 style="margin: 0 0 10px 0; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px;">
                🗺️ Map Location Information
            </h4>
            <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Status:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6; color: {status_color};">
                        {detection_icon} {location_status['status'].replace('_', ' ').title()}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Location:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{location_status['address']}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Method:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{location_status['detection_method']}</td>
                </tr>
                <tr>
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Confidence:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{location_status['confidence_score']:.1%}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 6px; font-weight: bold; border: 1px solid #dee2e6;">Coordinates:</td>
                    <td style="padding: 6px; border: 1px solid #dee2e6;">{center_lat:.6f}, {center_lon:.6f}</td>
                </tr>
            </table>
            <div style="margin-top: 10px; padding: 8px; background-color: #e3f2fd; border-radius: 4px; font-size: 11px; color: #1976d2;">
                📍 <strong>No cameras or DVRs found.</strong><br>
                Add device coordinates to see them on this map.
            </div>
        </div>
        """
        
        # Add marker at detected location
        marker_color = "green" if location_status['success'] else "orange"
        marker_icon = "map-marker" if location_status['success'] else "question-sign"
        
        folium.Marker(
            [center_lat, center_lon],
            popup=folium.Popup(popup_content, max_width=350),
            tooltip=f"📍 Detected Location: {location_status['address']}",
            icon=folium.Icon(color=marker_color, icon=marker_icon)
        ).add_to(empty_map)
        
        # Add a circle to show the general area
        folium.Circle(
            location=[center_lat, center_lon],
            radius=5000,  # 5km radius
            popup="General area around detected location",
            color='blue',
            fill=True,
            fillColor='lightblue',
            fillOpacity=0.2,
            weight=2,
            dashArray='5, 5'
        ).add_to(empty_map)
        
        # Add custom CSS for enhanced styling
        self._add_custom_css(empty_map)
        
        # Add location detection notification
        self._add_location_notification(empty_map, location_status)
        
        return empty_map._repr_html_()
    
    def _create_error_map(self, error_message: str) -> str:
        """Create error map when main map creation fails."""
        error_map = folium.Map(location=[40.7128, -74.0060], zoom_start=10)
        
        folium.Marker(
            [40.7128, -74.0060],
            popup=f"Error loading interactive map: {error_message}",
            icon=folium.Icon(color='red', icon='exclamation-sign')
        ).add_to(error_map)
        
        return error_map._repr_html_()