"""
Coverage Calculation Engine for Interactive Camera Mapping

This module provides comprehensive coverage area calculations for security cameras,
including circular and directional coverage areas, overlap detection, and geometric
calculations for map visualization.
"""

import math
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class CoverageArea:
    """Represents a camera coverage area with geometric properties."""
    camera_id: int
    center_lat: float
    center_lon: float
    radius: float
    field_of_view: float
    direction: float
    coordinates: List[List[float]]
    area_type: str  # 'circular' or 'directional'


@dataclass
class CoverageOverlap:
    """Represents an overlap between two camera coverage areas."""
    camera1_id: int
    camera2_id: int
    distance: float
    overlap_distance: float
    overlap_percentage: float


class CoverageCalculator:
    """
    Calculate camera coverage areas and overlaps with high precision.
    
    This class provides methods for:
    - Calculating circular coverage areas for omnidirectional cameras
    - Calculating directional coverage areas for focused cameras
    - Detecting overlaps between multiple camera coverage areas
    - Converting coverage areas to various formats (GeoJSON, coordinates)
    """
    
    # Earth's radius in meters (WGS84 ellipsoid)
    EARTH_RADIUS = 6378137.0
    
    @staticmethod
    def calculate_circular_coverage(lat: float, lon: float, radius: float, 
                                  precision: int = 36) -> List[List[float]]:
        """
        Calculate circular coverage area coordinates.
        
        Args:
            lat: Camera latitude in decimal degrees
            lon: Camera longitude in decimal degrees
            radius: Coverage radius in meters
            precision: Number of points to generate (default: 36, every 10 degrees)
            
        Returns:
            List of [latitude, longitude] coordinate pairs forming a circle
            
        Raises:
            ValueError: If coordinates are invalid or radius is non-positive
        """
        if not CoverageCalculator._validate_coordinates(lat, lon):
            raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")
        
        if radius <= 0:
            raise ValueError(f"Radius must be positive: {radius}")
        
        # Convert radius from meters to degrees
        radius_deg = radius / CoverageCalculator.EARTH_RADIUS * (180 / math.pi)
        
        # Generate circle points
        points = []
        angle_step = 360 / precision
        
        for i in range(precision + 1):  # +1 to close the polygon
            angle = math.radians(i * angle_step)
            
            # Calculate point coordinates using spherical geometry
            point_lat = lat + radius_deg * math.cos(angle)
            
            # Adjust longitude for latitude compression
            lat_rad = math.radians(lat)
            point_lon = lon + (radius_deg * math.sin(angle)) / math.cos(lat_rad)
            
            points.append([point_lat, point_lon])
        
        return points
    
    @staticmethod
    def calculate_directional_coverage(lat: float, lon: float, radius: float,
                                     direction: float, angle: float,
                                     precision: int = 1) -> List[List[float]]:
        """
        Calculate sector-based coverage area for directional cameras.
        
        Args:
            lat: Camera latitude in decimal degrees
            lon: Camera longitude in decimal degrees
            radius: Coverage radius in meters
            direction: Direction camera is facing in degrees (0 = North, 90 = East)
            angle: Field of view angle in degrees
            precision: Angle precision in degrees (default: 1 degree steps)
            
        Returns:
            List of [latitude, longitude] coordinate pairs forming a sector
            
        Raises:
            ValueError: If parameters are invalid
        """
        if not CoverageCalculator._validate_coordinates(lat, lon):
            raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")
        
        if radius <= 0:
            raise ValueError(f"Radius must be positive: {radius}")
        
        if not 0 < angle <= 360:
            raise ValueError(f"Angle must be between 0 and 360: {angle}")
        
        if not 0 <= direction < 360:
            raise ValueError(f"Direction must be between 0 and 360: {direction}")
        
        # Convert radius from meters to degrees
        radius_deg = radius / CoverageCalculator.EARTH_RADIUS * (180 / math.pi)
        
        # Convert direction to radians and adjust for map orientation
        # (0° = North, 90° = East, 180° = South, 270° = West)
        direction_rad = math.radians(direction)
        half_angle_rad = math.radians(angle / 2)
        
        # Start with camera position at the center
        points = [[lat, lon]]
        
        # Calculate start and end angles for the sector
        start_angle = direction_rad - half_angle_rad
        end_angle = direction_rad + half_angle_rad
        
        # Generate points along the arc
        num_points = max(int(angle / precision), 1)
        angle_step = (end_angle - start_angle) / num_points
        
        for i in range(num_points + 1):
            current_angle = start_angle + (i * angle_step)
            
            # Calculate point coordinates
            point_lat = lat + radius_deg * math.cos(current_angle)
            
            # Adjust longitude for latitude compression
            lat_rad = math.radians(lat)
            point_lon = lon + (radius_deg * math.sin(current_angle)) / math.cos(lat_rad)
            
            points.append([point_lat, point_lon])
        
        # Close the sector back to camera position
        points.append([lat, lon])
        
        return points
    
    @staticmethod
    def find_coverage_overlaps(cameras: List[Dict[str, Any]]) -> List[CoverageOverlap]:
        """
        Identify overlapping coverage areas between cameras.
        
        Args:
            cameras: List of camera dictionaries with required keys:
                    - id, latitude, longitude, coverage_radius
                    - Optional: field_of_view_angle, coverage_direction
                    
        Returns:
            List of CoverageOverlap objects describing overlapping areas
        """
        overlaps = []
        
        for i, camera1 in enumerate(cameras):
            for j, camera2 in enumerate(cameras[i+1:], i+1):
                overlap = CoverageCalculator._calculate_camera_overlap(camera1, camera2)
                if overlap:
                    overlaps.append(overlap)
        
        return overlaps
    
    @staticmethod
    def _calculate_camera_overlap(camera1: Dict[str, Any], 
                                camera2: Dict[str, Any]) -> Optional[CoverageOverlap]:
        """Calculate overlap between two specific cameras."""
        # Extract coordinates and coverage parameters
        lat1 = camera1.get('latitude')
        lon1 = camera1.get('longitude')
        lat2 = camera2.get('latitude')
        lon2 = camera2.get('longitude')
        
        if not all([lat1, lon1, lat2, lon2]):
            return None
        
        # Calculate distance between cameras using Haversine formula
        distance = CoverageCalculator._haversine_distance(lat1, lon1, lat2, lon2)
        
        # Get coverage radii
        radius1 = camera1.get('coverage_radius', 50.0)
        radius2 = camera2.get('coverage_radius', 50.0)
        
        # Check if coverage areas overlap
        if distance < (radius1 + radius2):
            overlap_distance = (radius1 + radius2) - distance
            
            # Calculate overlap percentage (approximate)
            # This is a simplified calculation - actual overlap area would be more complex
            max_possible_overlap = min(radius1, radius2) * 2
            overlap_percentage = min((overlap_distance / max_possible_overlap) * 100, 100)
            
            return CoverageOverlap(
                camera1_id=camera1.get('id'),
                camera2_id=camera2.get('id'),
                distance=distance,
                overlap_distance=overlap_distance,
                overlap_percentage=overlap_percentage
            )
        
        return None
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points using Haversine formula.
        
        Returns:
            Distance in meters
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Distance in meters
        distance = CoverageCalculator.EARTH_RADIUS * c
        return distance
    
    @staticmethod
    def get_coverage_area_geojson(camera: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate GeoJSON for camera coverage area.
        
        Args:
            camera: Camera dictionary with required keys:
                   - id, name, latitude, longitude, coverage_radius
                   - Optional: field_of_view_angle, coverage_direction
                   
        Returns:
            GeoJSON Feature object or None if invalid camera data
        """
        lat = camera.get('latitude')
        lon = camera.get('longitude')
        radius = camera.get('coverage_radius', 50.0)
        fov_angle = camera.get('field_of_view_angle', 360.0)
        direction = camera.get('coverage_direction', 0.0)
        
        if not lat or not lon:
            return None
        
        try:
            # Choose coverage calculation method based on field of view
            if fov_angle >= 360.0:
                coordinates = CoverageCalculator.calculate_circular_coverage(lat, lon, radius)
                area_type = 'circular'
            else:
                coordinates = CoverageCalculator.calculate_directional_coverage(
                    lat, lon, radius, direction, fov_angle
                )
                area_type = 'directional'
            
            # Convert to GeoJSON format
            geojson = {
                "type": "Feature",
                "properties": {
                    "camera_id": camera.get('id'),
                    "camera_name": camera.get('name'),
                    "coverage_radius": radius,
                    "field_of_view": fov_angle,
                    "direction": direction,
                    "area_type": area_type
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates]
                }
            }
            
            return geojson
            
        except ValueError as e:
            print(f"Error generating GeoJSON for camera {camera.get('id')}: {e}")
            return None
    
    @staticmethod
    def calculate_coverage_area_size(coordinates: List[List[float]]) -> float:
        """
        Calculate the approximate area of a coverage polygon in square meters.
        
        Uses the shoelace formula for polygon area calculation.
        
        Args:
            coordinates: List of [lat, lon] coordinate pairs
            
        Returns:
            Area in square meters
        """
        if len(coordinates) < 3:
            return 0.0
        
        # Convert coordinates to meters using approximate conversion
        # This is a simplified calculation - for precise area calculation,
        # proper map projection should be used
        
        area = 0.0
        n = len(coordinates)
        
        for i in range(n):
            j = (i + 1) % n
            
            # Convert lat/lon to approximate meters
            x1 = coordinates[i][1] * 111320 * math.cos(math.radians(coordinates[i][0]))
            y1 = coordinates[i][0] * 110540
            x2 = coordinates[j][1] * 111320 * math.cos(math.radians(coordinates[j][0]))
            y2 = coordinates[j][0] * 110540
            
            area += x1 * y2 - x2 * y1
        
        return abs(area) / 2.0
    
    @staticmethod
    def _validate_coordinates(lat: float, lon: float) -> bool:
        """Validate latitude and longitude values."""
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            return -90 <= lat_f <= 90 and -180 <= lon_f <= 180
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def create_coverage_area(camera: Dict[str, Any]) -> Optional[CoverageArea]:
        """
        Create a CoverageArea object from camera data.
        
        Args:
            camera: Camera dictionary with coverage parameters
            
        Returns:
            CoverageArea object or None if invalid data
        """
        lat = camera.get('latitude')
        lon = camera.get('longitude')
        radius = camera.get('coverage_radius', 50.0)
        fov_angle = camera.get('field_of_view_angle', 360.0)
        direction = camera.get('coverage_direction', 0.0)
        
        if not lat or not lon:
            return None
        
        try:
            # Calculate coordinates based on coverage type
            if fov_angle >= 360.0:
                coordinates = CoverageCalculator.calculate_circular_coverage(lat, lon, radius)
                area_type = 'circular'
            else:
                coordinates = CoverageCalculator.calculate_directional_coverage(
                    lat, lon, radius, direction, fov_angle
                )
                area_type = 'directional'
            
            return CoverageArea(
                camera_id=camera.get('id'),
                center_lat=lat,
                center_lon=lon,
                radius=radius,
                field_of_view=fov_angle,
                direction=direction,
                coordinates=coordinates,
                area_type=area_type
            )
            
        except ValueError:
            return None