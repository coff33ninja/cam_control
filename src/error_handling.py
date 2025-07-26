"""
Comprehensive Error Handling and Validation Module for Interactive Camera Mapping

This module provides robust error handling, validation, and fallback mechanisms
for the interactive camera mapping system, addressing all aspects of data integrity,
database operations, connectivity testing, and JavaScript integration.
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import aiosqlite
from contextlib import asynccontextmanager


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    VALIDATION = "validation"
    DATABASE = "database"
    NETWORK = "network"
    JAVASCRIPT = "javascript"
    COORDINATE = "coordinate"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


@dataclass
class ValidationError:
    """Represents a validation error with detailed information."""
    field: str
    value: Any
    message: str
    error_code: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'field': self.field,
            'value': str(self.value) if self.value is not None else None,
            'message': self.message,
            'error_code': self.error_code,
            'severity': self.severity.value
        }


@dataclass
class OperationResult:
    """Result of an operation with comprehensive error information."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[ValidationError]] = None
    error_category: Optional[ErrorCategory] = None
    retry_possible: bool = False
    fallback_applied: bool = False
    execution_time: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'success': self.success,
            'message': self.message,
            'data': self.data,
            'retry_possible': self.retry_possible,
            'fallback_applied': self.fallback_applied,
            'execution_time': self.execution_time
        }
        
        if self.errors:
            result['errors'] = [error.to_dict() for error in self.errors]
        
        if self.error_category:
            result['error_category'] = self.error_category.value
        
        return result


class CoordinateValidator:
    """
    Comprehensive coordinate validation with detailed error messages.
    
    Requirements addressed:
    - Implement coordinate validation with proper error messages for invalid positions
    """
    
    @staticmethod
    def validate_coordinates(latitude: Union[str, float, None], 
                           longitude: Union[str, float, None]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate latitude and longitude coordinates with detailed error reporting.
        
        Args:
            latitude: Latitude value to validate
            longitude: Longitude value to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for None values
        if latitude is None:
            errors.append(ValidationError(
                field="latitude",
                value=latitude,
                message="Latitude cannot be null or empty",
                error_code="COORD_LAT_NULL",
                severity=ErrorSeverity.HIGH
            ))
        
        if longitude is None:
            errors.append(ValidationError(
                field="longitude",
                value=longitude,
                message="Longitude cannot be null or empty",
                error_code="COORD_LON_NULL",
                severity=ErrorSeverity.HIGH
            ))
        
        if errors:
            return False, errors
        
        # Convert to float and validate ranges
        try:
            lat_float = float(latitude)
            
            if lat_float < -90.0:
                errors.append(ValidationError(
                    field="latitude",
                    value=latitude,
                    message=f"Latitude {lat_float} is below minimum (-90.0). Must be between -90.0 and 90.0 degrees.",
                    error_code="COORD_LAT_TOO_LOW",
                    severity=ErrorSeverity.HIGH
                ))
            elif lat_float > 90.0:
                errors.append(ValidationError(
                    field="latitude",
                    value=latitude,
                    message=f"Latitude {lat_float} is above maximum (90.0). Must be between -90.0 and 90.0 degrees.",
                    error_code="COORD_LAT_TOO_HIGH",
                    severity=ErrorSeverity.HIGH
                ))
                
        except (ValueError, TypeError) as e:
            errors.append(ValidationError(
                field="latitude",
                value=latitude,
                message=f"Invalid latitude format: '{latitude}'. Must be a valid decimal number.",
                error_code="COORD_LAT_INVALID_FORMAT",
                severity=ErrorSeverity.HIGH
            ))
        
        try:
            lon_float = float(longitude)
            
            if lon_float < -180.0:
                errors.append(ValidationError(
                    field="longitude",
                    value=longitude,
                    message=f"Longitude {lon_float} is below minimum (-180.0). Must be between -180.0 and 180.0 degrees.",
                    error_code="COORD_LON_TOO_LOW",
                    severity=ErrorSeverity.HIGH
                ))
            elif lon_float > 180.0:
                errors.append(ValidationError(
                    field="longitude",
                    value=longitude,
                    message=f"Longitude {lon_float} is above maximum (180.0). Must be between -180.0 and 180.0 degrees.",
                    error_code="COORD_LON_TOO_HIGH",
                    severity=ErrorSeverity.HIGH
                ))
                
        except (ValueError, TypeError) as e:
            errors.append(ValidationError(
                field="longitude",
                value=longitude,
                message=f"Invalid longitude format: '{longitude}'. Must be a valid decimal number.",
                error_code="COORD_LON_INVALID_FORMAT",
                severity=ErrorSeverity.HIGH
            ))
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_coverage_parameters(radius: Union[str, float, None],
                                   field_of_view: Union[str, float, None],
                                   direction: Union[str, float, None]) -> Tuple[bool, List[ValidationError]]:
        """
        Validate camera coverage parameters with detailed error reporting.
        
        Args:
            radius: Coverage radius in meters
            field_of_view: Field of view angle in degrees
            direction: Coverage direction in degrees
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate coverage radius
        if radius is not None:
            try:
                radius_float = float(radius)
                
                if radius_float <= 0:
                    errors.append(ValidationError(
                        field="coverage_radius",
                        value=radius,
                        message=f"Coverage radius {radius_float} must be greater than 0 meters.",
                        error_code="COVERAGE_RADIUS_TOO_LOW",
                        severity=ErrorSeverity.MEDIUM
                    ))
                elif radius_float > 10000:  # 10km max
                    errors.append(ValidationError(
                        field="coverage_radius",
                        value=radius,
                        message=f"Coverage radius {radius_float} exceeds maximum (10000m). Consider using a smaller radius.",
                        error_code="COVERAGE_RADIUS_TOO_HIGH",
                        severity=ErrorSeverity.MEDIUM
                    ))
                    
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    field="coverage_radius",
                    value=radius,
                    message=f"Invalid coverage radius format: '{radius}'. Must be a positive number.",
                    error_code="COVERAGE_RADIUS_INVALID_FORMAT",
                    severity=ErrorSeverity.MEDIUM
                ))
        
        # Validate field of view angle
        if field_of_view is not None:
            try:
                fov_float = float(field_of_view)
                
                if fov_float <= 0:
                    errors.append(ValidationError(
                        field="field_of_view_angle",
                        value=field_of_view,
                        message=f"Field of view angle {fov_float} must be greater than 0 degrees.",
                        error_code="FOV_ANGLE_TOO_LOW",
                        severity=ErrorSeverity.MEDIUM
                    ))
                elif fov_float > 360:
                    errors.append(ValidationError(
                        field="field_of_view_angle",
                        value=field_of_view,
                        message=f"Field of view angle {fov_float} exceeds maximum (360°). Using 360° for full coverage.",
                        error_code="FOV_ANGLE_TOO_HIGH",
                        severity=ErrorSeverity.LOW
                    ))
                    
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    field="field_of_view_angle",
                    value=field_of_view,
                    message=f"Invalid field of view format: '{field_of_view}'. Must be a number between 1 and 360.",
                    error_code="FOV_ANGLE_INVALID_FORMAT",
                    severity=ErrorSeverity.MEDIUM
                ))
        
        # Validate coverage direction
        if direction is not None:
            try:
                direction_float = float(direction)
                
                if direction_float < 0:
                    errors.append(ValidationError(
                        field="coverage_direction",
                        value=direction,
                        message=f"Coverage direction {direction_float} must be 0 or greater. Using 0° (North).",
                        error_code="COVERAGE_DIRECTION_TOO_LOW",
                        severity=ErrorSeverity.LOW
                    ))
                elif direction_float >= 360:
                    errors.append(ValidationError(
                        field="coverage_direction",
                        value=direction,
                        message=f"Coverage direction {direction_float} must be less than 360°. Using {direction_float % 360}°.",
                        error_code="COVERAGE_DIRECTION_TOO_HIGH",
                        severity=ErrorSeverity.LOW
                    ))
                    
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    field="coverage_direction",
                    value=direction,
                    message=f"Invalid coverage direction format: '{direction}'. Must be a number between 0 and 359.",
                    error_code="COVERAGE_DIRECTION_INVALID_FORMAT",
                    severity=ErrorSeverity.MEDIUM
                ))
        
        return len(errors) == 0, errors


class DatabaseTransactionManager:
    """
    Database transaction manager with atomic operations and rollback support.
    
    Requirements addressed:
    - Add database transaction handling for atomic coordinate updates
    """
    
    def __init__(self, db_name: str = "camera_data.db", max_retries: int = 3):
        """
        Initialize the transaction manager.
        
        Args:
            db_name: Path to the SQLite database
            max_retries: Maximum number of retry attempts for failed operations
        """
        self.db_name = db_name
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
    
    @asynccontextmanager
    async def atomic_transaction(self):
        """
        Context manager for atomic database transactions with automatic rollback.
        
        Usage:
            async with transaction_manager.atomic_transaction() as db:
                await db.execute("UPDATE cameras SET ...")
                # Automatic commit on success, rollback on exception
        """
        db = None
        try:
            db = await aiosqlite.connect(self.db_name)
            await db.execute("BEGIN IMMEDIATE")  # Start immediate transaction
            
            yield db
            
            await db.commit()
            self.logger.debug("Transaction committed successfully")
            
        except Exception as e:
            if db:
                await db.rollback()
                self.logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            if db:
                await db.close()
    
    async def update_camera_coordinates_atomic(self, camera_id: int, latitude: float, 
                                             longitude: float) -> OperationResult:
        """
        Atomically update camera coordinates with validation and rollback support.
        
        Args:
            camera_id: ID of the camera to update
            latitude: New latitude coordinate
            longitude: New longitude coordinate
            
        Returns:
            OperationResult with success status and details
        """
        start_time = time.time()
        
        # Validate coordinates first
        is_valid, validation_errors = CoordinateValidator.validate_coordinates(latitude, longitude)
        if not is_valid:
            return OperationResult(
                success=False,
                message="❌ Invalid coordinates provided",
                errors=validation_errors,
                error_category=ErrorCategory.VALIDATION,
                retry_possible=False,
                execution_time=time.time() - start_time
            )
        
        # Attempt atomic update with retries
        for attempt in range(self.max_retries):
            try:
                async with self.atomic_transaction() as db:
                    # Get original coordinates for rollback information
                    cursor = await db.execute(
                        "SELECT latitude, longitude FROM cameras WHERE id = ?",
                        (camera_id,)
                    )
                    original = await cursor.fetchone()
                    
                    if not original:
                        return OperationResult(
                            success=False,
                            message=f"❌ Camera {camera_id} not found",
                            error_category=ErrorCategory.DATABASE,
                            retry_possible=False,
                            execution_time=time.time() - start_time
                        )
                    
                    # Update coordinates
                    await db.execute(
                        "UPDATE cameras SET latitude = ?, longitude = ? WHERE id = ?",
                        (float(latitude), float(longitude), camera_id)
                    )
                    
                    # Verify update was successful
                    if db.total_changes == 0:
                        raise Exception("No rows were updated")
                    
                    # Log the coordinate update
                    await self._log_coordinate_update(db, camera_id, latitude, longitude, original)
                    
                    return OperationResult(
                        success=True,
                        message=f"✅ Camera {camera_id} coordinates updated to ({latitude:.6f}, {longitude:.6f})",
                        data={
                            'camera_id': camera_id,
                            'new_coordinates': {'latitude': latitude, 'longitude': longitude},
                            'original_coordinates': {'latitude': original[0], 'longitude': original[1]}
                        },
                        execution_time=time.time() - start_time
                    )
                    
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < self.max_retries - 1:
                    # Database is locked, wait and retry
                    wait_time = (attempt + 1) * 0.1  # Exponential backoff
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return OperationResult(
                        success=False,
                        message=f"❌ Database error: {str(e)}",
                        error_category=ErrorCategory.DATABASE,
                        retry_possible=attempt < self.max_retries - 1,
                        execution_time=time.time() - start_time
                    )
            
            except Exception as e:
                self.logger.error(f"Error updating camera coordinates (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))  # Brief delay before retry
                    continue
                else:
                    return OperationResult(
                        success=False,
                        message=f"❌ Failed to update coordinates after {self.max_retries} attempts: {str(e)}",
                        error_category=ErrorCategory.DATABASE,
                        retry_possible=False,
                        execution_time=time.time() - start_time
                    )
        
        # Should not reach here, but just in case
        return OperationResult(
            success=False,
            message="❌ Unexpected error in coordinate update",
            error_category=ErrorCategory.SYSTEM,
            retry_possible=False,
            execution_time=time.time() - start_time
        )
    
    async def update_coverage_parameters_atomic(self, camera_id: int, 
                                              coverage_params: Dict[str, float]) -> OperationResult:
        """
        Atomically update camera coverage parameters with validation.
        
        Args:
            camera_id: ID of the camera to update
            coverage_params: Dictionary with coverage parameters
            
        Returns:
            OperationResult with success status and details
        """
        start_time = time.time()
        
        # Extract and validate parameters
        radius = coverage_params.get('radius')
        field_of_view = coverage_params.get('field_of_view_angle')
        direction = coverage_params.get('coverage_direction')
        
        is_valid, validation_errors = CoordinateValidator.validate_coverage_parameters(
            radius, field_of_view, direction
        )
        
        if not is_valid:
            return OperationResult(
                success=False,
                message="❌ Invalid coverage parameters provided",
                errors=validation_errors,
                error_category=ErrorCategory.VALIDATION,
                retry_possible=False,
                execution_time=time.time() - start_time
            )
        
        # Attempt atomic update
        for attempt in range(self.max_retries):
            try:
                async with self.atomic_transaction() as db:
                    # Get original parameters
                    cursor = await db.execute("""
                        SELECT coverage_radius, field_of_view_angle, coverage_direction 
                        FROM cameras WHERE id = ?
                    """, (camera_id,))
                    original = await cursor.fetchone()
                    
                    if not original:
                        return OperationResult(
                            success=False,
                            message=f"❌ Camera {camera_id} not found",
                            error_category=ErrorCategory.DATABASE,
                            retry_possible=False,
                            execution_time=time.time() - start_time
                        )
                    
                    # Update parameters
                    await db.execute("""
                        UPDATE cameras 
                        SET coverage_radius = ?, field_of_view_angle = ?, coverage_direction = ?
                        WHERE id = ?
                    """, (
                        float(radius) if radius is not None else original[0],
                        float(field_of_view) if field_of_view is not None else original[1],
                        float(direction) if direction is not None else original[2],
                        camera_id
                    ))
                    
                    if db.total_changes == 0:
                        raise Exception("No rows were updated")
                    
                    return OperationResult(
                        success=True,
                        message=f"✅ Camera {camera_id} coverage parameters updated",
                        data={
                            'camera_id': camera_id,
                            'updated_parameters': coverage_params,
                            'original_parameters': {
                                'radius': original[0],
                                'field_of_view_angle': original[1],
                                'coverage_direction': original[2]
                            }
                        },
                        execution_time=time.time() - start_time
                    )
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    return OperationResult(
                        success=False,
                        message=f"❌ Failed to update coverage parameters: {str(e)}",
                        error_category=ErrorCategory.DATABASE,
                        retry_possible=False,
                        execution_time=time.time() - start_time
                    )
        
        return OperationResult(
            success=False,
            message="❌ Unexpected error in coverage parameter update",
            error_category=ErrorCategory.SYSTEM,
            retry_possible=False,
            execution_time=time.time() - start_time
        )
    
    async def _log_coordinate_update(self, db: aiosqlite.Connection, camera_id: int,
                                   new_lat: float, new_lon: float, original: Tuple):
        """Log coordinate update to action log."""
        try:
            details = {
                'camera_id': camera_id,
                'new_coordinates': {'latitude': new_lat, 'longitude': new_lon},
                'original_coordinates': {'latitude': original[0], 'longitude': original[1]},
                'timestamp': datetime.now().isoformat()
            }
            
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
        except Exception as e:
            self.logger.error(f"Error logging coordinate update: {e}")


class JavaScriptFallbackManager:
    """
    Fallback mechanisms for JavaScript failures with read-only mode support.
    
    Requirements addressed:
    - Create fallback mechanisms for JavaScript failures (read-only mode)
    """
    
    def __init__(self):
        """Initialize the fallback manager."""
        self.fallback_mode = False
        self.fallback_reason = None
        self.logger = logging.getLogger(__name__)
    
    def enable_fallback_mode(self, reason: str):
        """
        Enable fallback mode due to JavaScript failure.
        
        Args:
            reason: Reason for enabling fallback mode
        """
        self.fallback_mode = True
        self.fallback_reason = reason
        self.logger.warning(f"Fallback mode enabled: {reason}")
    
    def disable_fallback_mode(self):
        """Disable fallback mode."""
        self.fallback_mode = False
        self.fallback_reason = None
        self.logger.info("Fallback mode disabled")
    
    def is_fallback_active(self) -> bool:
        """Check if fallback mode is currently active."""
        return self.fallback_mode
    
    def get_fallback_map_html(self, cameras: List[Dict[str, Any]]) -> str:
        """
        Generate read-only map HTML when JavaScript fails.
        
        Args:
            cameras: List of camera data dictionaries
            
        Returns:
            HTML string for read-only map
        """
        try:
            import folium
            from folium.plugins import MarkerCluster
            
            # Create basic map without JavaScript interactions
            if cameras:
                # Calculate center from camera positions
                valid_coords = [(c['latitude'], c['longitude']) 
                              for c in cameras 
                              if c.get('latitude') and c.get('longitude')]
                
                if valid_coords:
                    center_lat = sum(coord[0] for coord in valid_coords) / len(valid_coords)
                    center_lon = sum(coord[1] for coord in valid_coords) / len(valid_coords)
                else:
                    center_lat, center_lon = 40.7128, -74.0060  # Default to NYC
            else:
                center_lat, center_lon = 40.7128, -74.0060
            
            # Create read-only map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=13,
                tiles='OpenStreetMap'
            )
            
            # Add fallback notice
            fallback_notice = f"""
            <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%); 
                        background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; 
                        padding: 10px 20px; border-radius: 5px; z-index: 1000; 
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <strong>⚠️ Read-Only Mode</strong><br>
                Interactive features are disabled due to: {self.fallback_reason}<br>
                <small>Camera positions cannot be modified in this mode.</small>
            </div>
            """
            m.get_root().html.add_child(folium.Element(fallback_notice))
            
            # Add cameras as static markers
            for camera in cameras:
                if camera.get('latitude') and camera.get('longitude'):
                    # Determine marker color based on connectivity
                    is_online = camera.get('is_online', False)
                    marker_color = 'green' if is_online else 'red'
                    status_text = '✅ Online' if is_online else '❌ Offline'
                    
                    popup_content = f"""
                    <div style="width: 250px;">
                        <h4>📹 {camera.get('name', 'Unknown Camera')}</h4>
                        <p><strong>Location:</strong> {camera.get('location', 'Unknown')}</p>
                        <p><strong>IP:</strong> {camera.get('ip_address', 'Unknown')}</p>
                        <p><strong>Status:</strong> {status_text}</p>
                        <p><strong>Coverage:</strong> {camera.get('coverage_radius', 50)}m radius</p>
                        <hr>
                        <p style="color: #856404; font-size: 12px;">
                            <strong>Note:</strong> Interactive features are disabled in read-only mode.
                        </p>
                    </div>
                    """
                    
                    folium.Marker(
                        location=[camera['latitude'], camera['longitude']],
                        popup=folium.Popup(popup_content, max_width=300),
                        tooltip=f"📹 {camera.get('name', 'Camera')} (Read-Only)",
                        icon=folium.Icon(
                            color=marker_color,
                            icon='video-camera',
                            prefix='fa'
                        )
                    ).add_to(m)
                    
                    # Add static coverage area
                    folium.Circle(
                        location=[camera['latitude'], camera['longitude']],
                        radius=camera.get('coverage_radius', 50),
                        popup=f"Coverage Area - {camera.get('name', 'Camera')} (Read-Only)",
                        color='blue',
                        fill=True,
                        fillColor='lightblue',
                        fillOpacity=0.2 if is_online else 0.1,
                        weight=1,
                        dashArray='5, 5'  # Dashed to indicate read-only
                    ).add_to(m)
            
            return m._repr_html_()
            
        except Exception as e:
            self.logger.error(f"Error creating fallback map: {e}")
            return self._get_error_fallback_html(str(e))
    
    def _get_error_fallback_html(self, error_message: str) -> str:
        """Generate error fallback HTML when map creation fails completely."""
        return f"""
        <div style="width: 100%; height: 400px; display: flex; align-items: center; 
                    justify-content: center; background: #f8f9fa; border: 1px solid #dee2e6; 
                    border-radius: 5px;">
            <div style="text-align: center; color: #6c757d;">
                <h3>❌ Map Unavailable</h3>
                <p>Unable to display map due to system error:</p>
                <p style="font-family: monospace; background: #e9ecef; padding: 10px; 
                          border-radius: 3px; margin: 10px 0;">{error_message}</p>
                <p><small>Please refresh the page or contact support if the problem persists.</small></p>
            </div>
        </div>
        """
    
    def handle_javascript_error(self, error_details: Dict[str, Any]) -> OperationResult:
        """
        Handle JavaScript errors and enable appropriate fallback.
        
        Args:
            error_details: Dictionary with error information
            
        Returns:
            OperationResult with fallback information
        """
        error_type = error_details.get('type', 'unknown')
        error_message = error_details.get('message', 'Unknown JavaScript error')
        
        # Enable fallback mode
        self.enable_fallback_mode(f"JavaScript error: {error_message}")
        
        return OperationResult(
            success=True,  # Fallback is successful even if original operation failed
            message="⚠️ Switched to read-only mode due to JavaScript error",
            data={
                'fallback_mode': True,
                'original_error': error_details,
                'fallback_reason': self.fallback_reason
            },
            error_category=ErrorCategory.JAVASCRIPT,
            fallback_applied=True
        )


class ConnectivityRetryManager:
    """
    Retry logic for connectivity testing and database operations.
    
    Requirements addressed:
    - Implement retry logic for connectivity testing and database operations
    """
    
    def __init__(self, max_retries: int = 3, base_delay: float = 0.5, max_delay: float = 5.0):
        """
        Initialize the retry manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.logger = logging.getLogger(__name__)
    
    async def retry_with_exponential_backoff(self, operation: Callable, 
                                           operation_name: str,
                                           *args, **kwargs) -> OperationResult:
        """
        Execute operation with exponential backoff retry logic.
        
        Args:
            operation: Async function to execute
            operation_name: Name of the operation for logging
            *args, **kwargs: Arguments to pass to the operation
            
        Returns:
            OperationResult with operation results
        """
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    # Calculate delay with exponential backoff
                    delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                    self.logger.info(f"Retrying {operation_name} (attempt {attempt + 1}) after {delay:.2f}s delay")
                    await asyncio.sleep(delay)
                
                # Execute the operation
                result = await operation(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                
                # If operation returns OperationResult, update it with retry info
                if isinstance(result, OperationResult):
                    result.execution_time = time.time() - start_time
                    if attempt > 0:
                        result.message += f" (succeeded after {attempt + 1} attempts)"
                    return result
                else:
                    # Wrap result in OperationResult
                    return OperationResult(
                        success=True,
                        message=f"✅ {operation_name} completed successfully",
                        data=result if isinstance(result, dict) else {'result': result},
                        execution_time=time.time() - start_time
                    )
                    
            except Exception as e:
                last_exception = e
                self.logger.warning(f"{operation_name} failed on attempt {attempt + 1}: {e}")
                
                # Don't retry on certain types of errors
                if self._is_non_retryable_error(e):
                    break
        
        # All retries exhausted
        return OperationResult(
            success=False,
            message=f"❌ {operation_name} failed after {self.max_retries + 1} attempts",
            error_category=self._categorize_error(last_exception),
            retry_possible=False,
            execution_time=time.time() - start_time,
            data={'last_error': str(last_exception)}
        )
    
    def _is_non_retryable_error(self, exception: Exception) -> bool:
        """Determine if an error should not be retried."""
        non_retryable_errors = [
            ValueError,  # Invalid input data
            TypeError,   # Type errors
            KeyError,    # Missing required keys
        ]
        
        return any(isinstance(exception, error_type) for error_type in non_retryable_errors)
    
    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """Categorize exception for error reporting."""
        if isinstance(exception, (aiosqlite.Error, aiosqlite.OperationalError)):
            return ErrorCategory.DATABASE
        elif isinstance(exception, (ConnectionError, TimeoutError)):
            return ErrorCategory.NETWORK
        elif isinstance(exception, (ValueError, TypeError)):
            return ErrorCategory.VALIDATION
        else:
            return ErrorCategory.SYSTEM


class ComprehensiveErrorHandler:
    """
    Main error handler that coordinates all error handling components.
    
    This class provides a unified interface for all error handling functionality
    in the interactive camera mapping system.
    """
    
    def __init__(self, db_name: str = "camera_data.db"):
        """Initialize the comprehensive error handler."""
        self.db_name = db_name
        self.transaction_manager = DatabaseTransactionManager(db_name)
        self.fallback_manager = JavaScriptFallbackManager()
        self.retry_manager = ConnectivityRetryManager()
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration for error handling."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('camera_mapping_errors.log'),
                logging.StreamHandler()
            ]
        )
    
    async def handle_camera_coordinate_update(self, camera_id: int, latitude: float, 
                                            longitude: float) -> OperationResult:
        """
        Handle camera coordinate updates with comprehensive error handling.
        
        Args:
            camera_id: ID of the camera to update
            latitude: New latitude coordinate
            longitude: New longitude coordinate
            
        Returns:
            OperationResult with comprehensive error information
        """
        # Use retry manager for the database operation
        return await self.retry_manager.retry_with_exponential_backoff(
            self.transaction_manager.update_camera_coordinates_atomic,
            f"update_camera_{camera_id}_coordinates",
            camera_id, latitude, longitude
        )
    
    async def handle_coverage_parameter_update(self, camera_id: int, 
                                             coverage_params: Dict[str, float]) -> OperationResult:
        """
        Handle coverage parameter updates with comprehensive error handling.
        
        Args:
            camera_id: ID of the camera to update
            coverage_params: Dictionary with coverage parameters
            
        Returns:
            OperationResult with comprehensive error information
        """
        return await self.retry_manager.retry_with_exponential_backoff(
            self.transaction_manager.update_coverage_parameters_atomic,
            f"update_camera_{camera_id}_coverage",
            camera_id, coverage_params
        )
    
    def handle_javascript_failure(self, error_details: Dict[str, Any], 
                                cameras: List[Dict[str, Any]]) -> Tuple[str, OperationResult]:
        """
        Handle JavaScript failures with fallback to read-only mode.
        
        Args:
            error_details: Details about the JavaScript error
            cameras: List of camera data for fallback map
            
        Returns:
            Tuple of (fallback_map_html, operation_result)
        """
        # Handle the JavaScript error
        result = self.fallback_manager.handle_javascript_error(error_details)
        
        # Generate fallback map
        fallback_html = self.fallback_manager.get_fallback_map_html(cameras)
        
        return fallback_html, result
    
    def validate_and_sanitize_input(self, input_data: Dict[str, Any]) -> OperationResult:
        """
        Validate and sanitize input data comprehensively.
        
        Args:
            input_data: Dictionary with input data to validate
            
        Returns:
            OperationResult with validation results and sanitized data
        """
        errors = []
        sanitized_data = {}
        
        # Validate coordinates if present
        if 'latitude' in input_data or 'longitude' in input_data:
            lat = input_data.get('latitude')
            lon = input_data.get('longitude')
            
            is_valid, coord_errors = CoordinateValidator.validate_coordinates(lat, lon)
            errors.extend(coord_errors)
            
            if is_valid:
                sanitized_data['latitude'] = float(lat)
                sanitized_data['longitude'] = float(lon)
        
        # Validate coverage parameters if present
        coverage_fields = ['coverage_radius', 'field_of_view_angle', 'coverage_direction']
        if any(field in input_data for field in coverage_fields):
            radius = input_data.get('coverage_radius')
            fov = input_data.get('field_of_view_angle')
            direction = input_data.get('coverage_direction')
            
            is_valid, coverage_errors = CoordinateValidator.validate_coverage_parameters(
                radius, fov, direction
            )
            errors.extend(coverage_errors)
            
            if is_valid:
                if radius is not None:
                    sanitized_data['coverage_radius'] = float(radius)
                if fov is not None:
                    sanitized_data['field_of_view_angle'] = float(fov)
                if direction is not None:
                    sanitized_data['coverage_direction'] = float(direction)
        
        # Copy other safe fields
        safe_fields = ['camera_id', 'name', 'location', 'ip_address']
        for field in safe_fields:
            if field in input_data:
                sanitized_data[field] = input_data[field]
        
        return OperationResult(
            success=len(errors) == 0,
            message="✅ Input validation successful" if len(errors) == 0 else "❌ Input validation failed",
            data=sanitized_data,
            errors=errors,
            error_category=ErrorCategory.VALIDATION if errors else None
        )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get summary of error handling status and statistics.
        
        Returns:
            Dictionary with error handling statistics
        """
        return {
            'fallback_mode_active': self.fallback_manager.is_fallback_active(),
            'fallback_reason': self.fallback_manager.fallback_reason,
            'database_connection': self.db_name,
            'max_retries': self.retry_manager.max_retries,
            'timestamp': datetime.now().isoformat()
        }


# Utility functions for error handling
def format_validation_errors(errors: List[ValidationError]) -> str:
    """Format validation errors as a readable string."""
    if not errors:
        return "No validation errors"
    
    formatted = "Validation Errors:\n"
    for error in errors:
        severity_icon = {
            ErrorSeverity.LOW: "ℹ️",
            ErrorSeverity.MEDIUM: "⚠️", 
            ErrorSeverity.HIGH: "❌",
            ErrorSeverity.CRITICAL: "🚨"
        }.get(error.severity, "❓")
        
        formatted += f"  {severity_icon} {error.field}: {error.message}\n"
    
    return formatted


def create_error_response(message: str, error_category: ErrorCategory, 
                         errors: List[ValidationError] = None) -> Dict[str, Any]:
    """Create standardized error response dictionary."""
    return OperationResult(
        success=False,
        message=message,
        errors=errors,
        error_category=error_category
    ).to_dict()


# Global error handler instance
_global_error_handler = None

def get_error_handler(db_name: str = "camera_data.db") -> ComprehensiveErrorHandler:
    """Get or create global error handler instance."""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ComprehensiveErrorHandler(db_name)
    return _global_error_handler