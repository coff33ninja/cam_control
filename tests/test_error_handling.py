"""
Comprehensive tests for the error handling and validation module.

This test suite validates all aspects of error handling including coordinate validation,
database transaction management, JavaScript fallback mechanisms, and retry logic.
"""

import asyncio
import json
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
import aiosqlite

from error_handling import (
    CoordinateValidator, DatabaseTransactionManager, JavaScriptFallbackManager,
    ConnectivityRetryManager, ComprehensiveErrorHandler, ValidationError,
    OperationResult, ErrorSeverity, ErrorCategory
)


class TestCoordinateValidator:
    """Test coordinate validation functionality."""
    
    def test_valid_coordinates(self):
        """Test validation of valid coordinates."""
        # Test valid coordinates
        is_valid, errors = CoordinateValidator.validate_coordinates(40.7128, -74.0060)
        assert is_valid is True
        assert len(errors) == 0
        
        # Test boundary values
        is_valid, errors = CoordinateValidator.validate_coordinates(90.0, 180.0)
        assert is_valid is True
        assert len(errors) == 0
        
        is_valid, errors = CoordinateValidator.validate_coordinates(-90.0, -180.0)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_invalid_coordinates(self):
        """Test validation of invalid coordinates."""
        # Test latitude too high
        is_valid, errors = CoordinateValidator.validate_coordinates(91.0, 0.0)
        assert is_valid is False
        assert len(errors) == 1
        assert errors[0].error_code == "COORD_LAT_TOO_HIGH"
        assert errors[0].severity == ErrorSeverity.HIGH
        
        # Test latitude too low
        is_valid, errors = CoordinateValidator.validate_coordinates(-91.0, 0.0)
        assert is_valid is False
        assert len(errors) == 1
        assert errors[0].error_code == "COORD_LAT_TOO_LOW"
        
        # Test longitude too high
        is_valid, errors = CoordinateValidator.validate_coordinates(0.0, 181.0)
        assert is_valid is False
        assert len(errors) == 1
        assert errors[0].error_code == "COORD_LON_TOO_HIGH"
        
        # Test longitude too low
        is_valid, errors = CoordinateValidator.validate_coordinates(0.0, -181.0)
        assert is_valid is False
        assert len(errors) == 1
        assert errors[0].error_code == "COORD_LON_TOO_LOW"
    
    def test_null_coordinates(self):
        """Test validation of null coordinates."""
        is_valid, errors = CoordinateValidator.validate_coordinates(None, None)
        assert is_valid is False
        assert len(errors) == 2
        assert any(e.error_code == "COORD_LAT_NULL" for e in errors)
        assert any(e.error_code == "COORD_LON_NULL" for e in errors)
    
    def test_invalid_format_coordinates(self):
        """Test validation of invalid format coordinates."""
        is_valid, errors = CoordinateValidator.validate_coordinates("invalid", "also_invalid")
        assert is_valid is False
        assert len(errors) == 2
        assert any(e.error_code == "COORD_LAT_INVALID_FORMAT" for e in errors)
        assert any(e.error_code == "COORD_LON_INVALID_FORMAT" for e in errors)
    
    def test_valid_coverage_parameters(self):
        """Test validation of valid coverage parameters."""
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(50.0, 90.0, 45.0)
        assert is_valid is True
        assert len(errors) == 0
        
        # Test boundary values
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(1.0, 1.0, 0.0)
        assert is_valid is True
        assert len(errors) == 0
        
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(10000.0, 360.0, 359.0)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_invalid_coverage_parameters(self):
        """Test validation of invalid coverage parameters."""
        # Test radius too low
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(0.0, 90.0, 45.0)
        assert is_valid is False
        assert any(e.error_code == "COVERAGE_RADIUS_TOO_LOW" for e in errors)
        
        # Test radius too high
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(10001.0, 90.0, 45.0)
        assert is_valid is False
        assert any(e.error_code == "COVERAGE_RADIUS_TOO_HIGH" for e in errors)
        
        # Test field of view too low
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(50.0, 0.0, 45.0)
        assert is_valid is False
        assert any(e.error_code == "FOV_ANGLE_TOO_LOW" for e in errors)
        
        # Test field of view too high (should be warning, not error)
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(50.0, 361.0, 45.0)
        assert is_valid is False
        assert any(e.error_code == "FOV_ANGLE_TOO_HIGH" for e in errors)
        
        # Test direction too low (should be warning)
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(50.0, 90.0, -1.0)
        assert is_valid is False
        assert any(e.error_code == "COVERAGE_DIRECTION_TOO_LOW" for e in errors)
        
        # Test direction too high (should be warning)
        is_valid, errors = CoordinateValidator.validate_coverage_parameters(50.0, 90.0, 360.0)
        assert is_valid is False
        assert any(e.error_code == "COVERAGE_DIRECTION_TOO_HIGH" for e in errors)


class TestDatabaseTransactionManager:
    """Test database transaction management functionality."""
    
    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # Initialize test database
        async with aiosqlite.connect(temp_file.name) as db:
            await db.execute("""
                CREATE TABLE cameras (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    latitude REAL,
                    longitude REAL,
                    coverage_radius REAL DEFAULT 50.0,
                    field_of_view_angle REAL DEFAULT 360.0,
                    coverage_direction REAL DEFAULT 0.0
                )
            """)
            await db.execute("""
                CREATE TABLE action_log (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    action_type TEXT,
                    table_name TEXT,
                    record_id INTEGER,
                    details TEXT
                )
            """)
            await db.execute("""
                INSERT INTO cameras (id, name, latitude, longitude)
                VALUES (1, 'Test Camera', 40.7128, -74.0060)
            """)
            await db.commit()
        
        yield temp_file.name
        
        # Cleanup
        os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_successful_coordinate_update(self, temp_db):
        """Test successful coordinate update with transaction."""
        manager = DatabaseTransactionManager(temp_db)
        
        result = await manager.update_camera_coordinates_atomic(1, 41.0, -75.0)
        
        assert result.success is True
        assert "coordinates updated" in result.message
        assert result.data['camera_id'] == 1
        assert result.data['new_coordinates']['latitude'] == 41.0
        assert result.data['new_coordinates']['longitude'] == -75.0
        
        # Verify database was updated
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("SELECT latitude, longitude FROM cameras WHERE id = 1")
            row = await cursor.fetchone()
            assert row[0] == 41.0
            assert row[1] == -75.0
    
    @pytest.mark.asyncio
    async def test_invalid_coordinate_update(self, temp_db):
        """Test coordinate update with invalid coordinates."""
        manager = DatabaseTransactionManager(temp_db)
        
        result = await manager.update_camera_coordinates_atomic(1, 91.0, 0.0)  # Invalid latitude
        
        assert result.success is False
        assert result.error_category == ErrorCategory.VALIDATION
        assert len(result.errors) > 0
        assert any(e.error_code == "COORD_LAT_TOO_HIGH" for e in result.errors)
    
    @pytest.mark.asyncio
    async def test_nonexistent_camera_update(self, temp_db):
        """Test coordinate update for non-existent camera."""
        manager = DatabaseTransactionManager(temp_db)
        
        result = await manager.update_camera_coordinates_atomic(999, 40.0, -74.0)
        
        assert result.success is False
        assert "not found" in result.message
        assert result.error_category == ErrorCategory.DATABASE
    
    @pytest.mark.asyncio
    async def test_coverage_parameter_update(self, temp_db):
        """Test coverage parameter update with transaction."""
        manager = DatabaseTransactionManager(temp_db)
        
        params = {
            'radius': 100.0,
            'field_of_view_angle': 90.0,
            'coverage_direction': 45.0
        }
        
        result = await manager.update_coverage_parameters_atomic(1, params)
        
        assert result.success is True
        assert "coverage parameters updated" in result.message
        assert result.data['camera_id'] == 1
        
        # Verify database was updated
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("""
                SELECT coverage_radius, field_of_view_angle, coverage_direction 
                FROM cameras WHERE id = 1
            """)
            row = await cursor.fetchone()
            assert row[0] == 100.0
            assert row[1] == 90.0
            assert row[2] == 45.0


class TestJavaScriptFallbackManager:
    """Test JavaScript fallback functionality."""
    
    def test_fallback_mode_management(self):
        """Test enabling and disabling fallback mode."""
        manager = JavaScriptFallbackManager()
        
        assert manager.is_fallback_active() is False
        
        manager.enable_fallback_mode("Test error")
        assert manager.is_fallback_active() is True
        assert manager.fallback_reason == "Test error"
        
        manager.disable_fallback_mode()
        assert manager.is_fallback_active() is False
        assert manager.fallback_reason is None
    
    def test_javascript_error_handling(self):
        """Test JavaScript error handling."""
        manager = JavaScriptFallbackManager()
        
        error_details = {
            'type': 'drag_error',
            'message': 'Failed to update marker position'
        }
        
        result = manager.handle_javascript_error(error_details)
        
        assert result.success is True  # Fallback is successful
        assert result.fallback_applied is True
        assert result.error_category == ErrorCategory.JAVASCRIPT
        assert manager.is_fallback_active() is True
    
    def test_fallback_map_generation(self):
        """Test generation of fallback map HTML."""
        manager = JavaScriptFallbackManager()
        manager.enable_fallback_mode("Test fallback")
        
        cameras = [
            {
                'id': 1,
                'name': 'Test Camera',
                'location': 'Test Location',
                'ip_address': '192.168.1.100',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'coverage_radius': 50,
                'is_online': True
            }
        ]
        
        html = manager.get_fallback_map_html(cameras)
        
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Read-Only Mode" in html
        assert "Test Camera" in html
    
    def test_empty_camera_fallback_map(self):
        """Test fallback map generation with no cameras."""
        manager = JavaScriptFallbackManager()
        manager.enable_fallback_mode("No cameras available")
        
        html = manager.get_fallback_map_html([])
        
        assert isinstance(html, str)
        assert len(html) > 0
        assert "Read-Only Mode" in html


class TestConnectivityRetryManager:
    """Test connectivity retry logic."""
    
    @pytest.mark.asyncio
    async def test_successful_operation_no_retry(self):
        """Test successful operation that doesn't need retry."""
        manager = ConnectivityRetryManager(max_retries=3)
        
        async def successful_operation():
            return {"status": "success"}
        
        result = await manager.retry_with_exponential_backoff(
            successful_operation, "test_operation"
        )
        
        assert result.success is True
        assert "completed successfully" in result.message
        assert result.data['result']['status'] == "success"
    
    @pytest.mark.asyncio
    async def test_operation_succeeds_after_retry(self):
        """Test operation that succeeds after retries."""
        manager = ConnectivityRetryManager(max_retries=3, base_delay=0.01)  # Fast for testing
        
        call_count = 0
        
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return {"status": "success", "attempts": call_count}
        
        result = await manager.retry_with_exponential_backoff(
            flaky_operation, "flaky_test"
        )
        
        assert result.success is True
        assert call_count == 3
        assert "succeeded after 3 attempts" in result.message
    
    @pytest.mark.asyncio
    async def test_operation_fails_after_all_retries(self):
        """Test operation that fails after all retries."""
        manager = ConnectivityRetryManager(max_retries=2, base_delay=0.01)
        
        async def failing_operation():
            raise ConnectionError("Persistent failure")
        
        result = await manager.retry_with_exponential_backoff(
            failing_operation, "failing_test"
        )
        
        assert result.success is False
        assert "failed after 3 attempts" in result.message
        assert result.error_category == ErrorCategory.NETWORK
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        manager = ConnectivityRetryManager(max_retries=3, base_delay=0.01)
        
        call_count = 0
        
        async def validation_error_operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")  # Non-retryable error
        
        result = await manager.retry_with_exponential_backoff(
            validation_error_operation, "validation_test"
        )
        
        assert result.success is False
        assert call_count == 1  # Should not retry
        assert result.error_category == ErrorCategory.VALIDATION


class TestComprehensiveErrorHandler:
    """Test the main comprehensive error handler."""
    
    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # Initialize test database
        async with aiosqlite.connect(temp_file.name) as db:
            await db.execute("""
                CREATE TABLE cameras (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    latitude REAL,
                    longitude REAL,
                    coverage_radius REAL DEFAULT 50.0,
                    field_of_view_angle REAL DEFAULT 360.0,
                    coverage_direction REAL DEFAULT 0.0
                )
            """)
            await db.execute("""
                CREATE TABLE action_log (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    action_type TEXT,
                    table_name TEXT,
                    record_id INTEGER,
                    details TEXT
                )
            """)
            await db.execute("""
                INSERT INTO cameras (id, name, latitude, longitude)
                VALUES (1, 'Test Camera', 40.7128, -74.0060)
            """)
            await db.commit()
        
        yield temp_file.name
        
        # Cleanup
        os.unlink(temp_file.name)
    
    @pytest.mark.asyncio
    async def test_coordinate_update_handling(self, temp_db):
        """Test comprehensive coordinate update handling."""
        handler = ComprehensiveErrorHandler(temp_db)
        
        result = await handler.handle_camera_coordinate_update(1, 41.0, -75.0)
        
        assert result.success is True
        assert "coordinates updated" in result.message
    
    @pytest.mark.asyncio
    async def test_coverage_parameter_handling(self, temp_db):
        """Test comprehensive coverage parameter handling."""
        handler = ComprehensiveErrorHandler(temp_db)
        
        params = {'radius': 100.0, 'field_of_view_angle': 90.0, 'coverage_direction': 45.0}
        result = await handler.handle_coverage_parameter_update(1, params)
        
        assert result.success is True
        assert "coverage parameters updated" in result.message
    
    def test_javascript_failure_handling(self):
        """Test JavaScript failure handling."""
        handler = ComprehensiveErrorHandler()
        
        error_details = {'type': 'drag_error', 'message': 'Drag failed'}
        cameras = [{'id': 1, 'name': 'Test', 'latitude': 40.0, 'longitude': -74.0, 'is_online': True}]
        
        fallback_html, result = handler.handle_javascript_failure(error_details, cameras)
        
        assert isinstance(fallback_html, str)
        assert len(fallback_html) > 0
        assert result.success is True
        assert result.fallback_applied is True
    
    def test_input_validation_and_sanitization(self):
        """Test input validation and sanitization."""
        handler = ComprehensiveErrorHandler()
        
        # Test valid input
        valid_input = {
            'camera_id': 1,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'coverage_radius': 50.0
        }
        
        result = handler.validate_and_sanitize_input(valid_input)
        
        assert result.success is True
        assert result.data['latitude'] == 40.7128
        assert result.data['longitude'] == -74.0060
        assert result.data['coverage_radius'] == 50.0
        
        # Test invalid input
        invalid_input = {
            'latitude': 91.0,  # Invalid
            'longitude': -74.0060,
            'coverage_radius': -10.0  # Invalid
        }
        
        result = handler.validate_and_sanitize_input(invalid_input)
        
        assert result.success is False
        assert len(result.errors) > 0
        assert result.error_category == ErrorCategory.VALIDATION
    
    def test_error_summary(self):
        """Test error summary generation."""
        handler = ComprehensiveErrorHandler()
        
        summary = handler.get_error_summary()
        
        assert isinstance(summary, dict)
        assert 'fallback_mode_active' in summary
        assert 'database_connection' in summary
        assert 'max_retries' in summary
        assert 'timestamp' in summary


class TestValidationError:
    """Test ValidationError dataclass functionality."""
    
    def test_validation_error_creation(self):
        """Test creating ValidationError instances."""
        error = ValidationError(
            field="latitude",
            value=91.0,
            message="Latitude too high",
            error_code="COORD_LAT_TOO_HIGH",
            severity=ErrorSeverity.HIGH
        )
        
        assert error.field == "latitude"
        assert error.value == 91.0
        assert error.message == "Latitude too high"
        assert error.error_code == "COORD_LAT_TOO_HIGH"
        assert error.severity == ErrorSeverity.HIGH
    
    def test_validation_error_to_dict(self):
        """Test converting ValidationError to dictionary."""
        error = ValidationError(
            field="longitude",
            value=-181.0,
            message="Longitude too low",
            error_code="COORD_LON_TOO_LOW"
        )
        
        error_dict = error.to_dict()
        
        assert error_dict['field'] == "longitude"
        assert error_dict['value'] == "-181.0"
        assert error_dict['message'] == "Longitude too low"
        assert error_dict['error_code'] == "COORD_LON_TOO_LOW"
        assert error_dict['severity'] == ErrorSeverity.MEDIUM.value


class TestOperationResult:
    """Test OperationResult dataclass functionality."""
    
    def test_operation_result_creation(self):
        """Test creating OperationResult instances."""
        result = OperationResult(
            success=True,
            message="Operation successful",
            data={'key': 'value'},
            execution_time=0.5
        )
        
        assert result.success is True
        assert result.message == "Operation successful"
        assert result.data['key'] == 'value'
        assert result.execution_time == 0.5
    
    def test_operation_result_to_dict(self):
        """Test converting OperationResult to dictionary."""
        errors = [ValidationError("test", "value", "message", "CODE")]
        
        result = OperationResult(
            success=False,
            message="Operation failed",
            errors=errors,
            error_category=ErrorCategory.VALIDATION
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['success'] is False
        assert result_dict['message'] == "Operation failed"
        assert len(result_dict['errors']) == 1
        assert result_dict['error_category'] == ErrorCategory.VALIDATION.value


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])