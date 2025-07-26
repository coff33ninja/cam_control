"""
Comprehensive integration test for error handling and validation system.

This test verifies that all error handling components work together correctly
and that the system gracefully handles various failure scenarios.
"""

import asyncio
import tempfile
import os
import json
from unittest.mock import patch, AsyncMock
import aiosqlite

from error_handling import (
    ComprehensiveErrorHandler, CoordinateValidator, DatabaseTransactionManager,
    JavaScriptFallbackManager, ConnectivityRetryManager, get_error_handler,
    ValidationError, OperationResult, ErrorCategory, ErrorSeverity
)
from connectivity_monitor import ConnectivityMonitor
from interactive_map_manager import InteractiveMapManager


async def setup_test_database():
    """Create a temporary test database with sample data."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    async with aiosqlite.connect(temp_file.name) as db:
        # Create tables
        await db.execute("""
            CREATE TABLE cameras (
                id INTEGER PRIMARY KEY,
                name TEXT,
                location TEXT,
                ip_address TEXT,
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
            CREATE TABLE map_configurations (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT,
                configuration_data TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Insert test data
        await db.execute("""
            INSERT INTO cameras (id, name, location, ip_address, latitude, longitude)
            VALUES 
                (1, 'Test Camera 1', 'Building A', '192.168.1.100', 40.7128, -74.0060),
                (2, 'Test Camera 2', 'Building B', '192.168.1.101', 40.7500, -73.9900),
                (3, 'Test Camera 3', 'Building C', '192.168.1.102', 40.7200, -74.0100)
        """)
        
        await db.commit()
    
    return temp_file.name


async def test_coordinate_validation_integration():
    """Test coordinate validation integration with database operations."""
    print("🧪 Testing coordinate validation integration...")
    
    temp_db = await setup_test_database()
    
    try:
        handler = ComprehensiveErrorHandler(temp_db)
        
        # Test valid coordinate update
        result = await handler.handle_camera_coordinate_update(1, 41.0, -75.0)
        assert result.success is True
        assert "coordinates updated" in result.message
        print("✅ Valid coordinate update test passed")
        
        # Test invalid coordinate update
        result = await handler.handle_camera_coordinate_update(1, 91.0, 0.0)  # Invalid latitude
        assert result.success is False
        assert result.error_category == ErrorCategory.VALIDATION
        assert len(result.errors) > 0
        print("✅ Invalid coordinate validation test passed")
        
        # Test non-existent camera
        result = await handler.handle_camera_coordinate_update(999, 40.0, -74.0)
        assert result.success is False
        assert "not found" in result.message
        print("✅ Non-existent camera handling test passed")
        
    finally:
        os.unlink(temp_db)


async def test_database_transaction_rollback():
    """Test database transaction rollback on errors."""
    print("🧪 Testing database transaction rollback...")
    
    temp_db = await setup_test_database()
    
    try:
        transaction_manager = DatabaseTransactionManager(temp_db)
        
        # Get original coordinates
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("SELECT latitude, longitude FROM cameras WHERE id = 1")
            original = await cursor.fetchone()
        
        # Attempt invalid update (should rollback)
        result = await transaction_manager.update_camera_coordinates_atomic(1, 91.0, 0.0)
        assert result.success is False
        
        # Verify coordinates weren't changed
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("SELECT latitude, longitude FROM cameras WHERE id = 1")
            current = await cursor.fetchone()
            assert current[0] == original[0]  # Latitude unchanged
            assert current[1] == original[1]  # Longitude unchanged
        
        print("✅ Database transaction rollback test passed")
        
    finally:
        os.unlink(temp_db)


async def test_connectivity_retry_integration():
    """Test connectivity monitoring with retry logic."""
    print("🧪 Testing connectivity retry integration...")
    
    temp_db = await setup_test_database()
    
    try:
        monitor = ConnectivityMonitor(temp_db, cache_timeout=1)  # Short cache for testing
        
        # Test with mock ping that fails then succeeds
        call_count = 0
        
        async def mock_ping(ip):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return None  # Fail first attempt
            return 0.05  # Success on second attempt
        
        with patch.object(monitor, '_async_ping', side_effect=mock_ping):
            result = await monitor.test_camera_connectivity('192.168.1.100', 1, 'Test Camera')
            
            # Should succeed after retry
            assert result.is_online is True
            assert call_count >= 2  # At least one retry occurred
            print("✅ Connectivity retry test passed")
        
    finally:
        os.unlink(temp_db)


async def test_javascript_fallback_integration():
    """Test JavaScript fallback integration with map manager."""
    print("🧪 Testing JavaScript fallback integration...")
    
    temp_db = await setup_test_database()
    
    try:
        handler = ComprehensiveErrorHandler(temp_db)
        
        # Simulate JavaScript error
        error_details = {
            'type': 'drag_error',
            'message': 'Failed to update marker position',
            'camera_id': 1
        }
        
        # Get camera data for fallback map
        cameras = [
            {
                'id': 1,
                'name': 'Test Camera 1',
                'location': 'Building A',
                'ip_address': '192.168.1.100',
                'latitude': 40.7128,
                'longitude': -74.0060,
                'coverage_radius': 50,
                'is_online': True
            }
        ]
        
        fallback_html, result = handler.handle_javascript_failure(error_details, cameras)
        
        assert result.success is True
        assert result.fallback_applied is True
        assert result.error_category == ErrorCategory.JAVASCRIPT
        assert isinstance(fallback_html, str)
        assert "Read-Only Mode" in fallback_html
        assert "Test Camera 1" in fallback_html
        
        print("✅ JavaScript fallback integration test passed")
        
    finally:
        os.unlink(temp_db)


async def test_comprehensive_input_validation():
    """Test comprehensive input validation and sanitization."""
    print("🧪 Testing comprehensive input validation...")
    
    handler = ComprehensiveErrorHandler()
    
    # Test mixed valid and invalid input
    mixed_input = {
        'camera_id': 1,
        'latitude': 40.7128,      # Valid
        'longitude': 181.0,       # Invalid (too high)
        'coverage_radius': 50.0,  # Valid
        'field_of_view_angle': -10.0,  # Invalid (too low)
        'coverage_direction': 45.0,    # Valid
        'name': 'Test Camera',    # Valid (safe field)
        'malicious_script': '<script>alert("xss")</script>'  # Should be ignored
    }
    
    result = handler.validate_and_sanitize_input(mixed_input)
    
    assert result.success is False  # Should fail due to invalid fields
    assert len(result.errors) >= 2  # At least longitude and field_of_view errors
    
    # Check that valid fields are in sanitized data
    assert result.data['latitude'] == 40.7128
    assert result.data['coverage_radius'] == 50.0
    assert result.data['coverage_direction'] == 45.0
    assert result.data['name'] == 'Test Camera'
    
    # Check that malicious field is not in sanitized data
    assert 'malicious_script' not in result.data
    
    # Check specific error codes
    error_codes = [error.error_code for error in result.errors]
    assert 'COORD_LON_TOO_HIGH' in error_codes
    assert 'FOV_ANGLE_TOO_LOW' in error_codes
    
    print("✅ Comprehensive input validation test passed")


async def test_error_logging_and_recovery():
    """Test error logging and recovery mechanisms."""
    print("🧪 Testing error logging and recovery...")
    
    temp_db = await setup_test_database()
    
    try:
        handler = ComprehensiveErrorHandler(temp_db)
        
        # Perform operations that should be logged
        await handler.handle_camera_coordinate_update(1, 41.0, -75.0)  # Success
        await handler.handle_camera_coordinate_update(1, 91.0, 0.0)    # Failure
        
        # Check that operations were logged
        async with aiosqlite.connect(temp_db) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM action_log 
                WHERE action_type = 'coordinate_update'
            """)
            log_count = (await cursor.fetchone())[0]
            
            # Should have at least one successful log entry
            assert log_count >= 1
        
        print("✅ Error logging test passed")
        
        # Test error summary
        summary = handler.get_error_summary()
        assert isinstance(summary, dict)
        assert 'fallback_mode_active' in summary
        assert 'database_connection' in summary
        assert 'max_retries' in summary
        
        print("✅ Error recovery mechanisms test passed")
        
    finally:
        os.unlink(temp_db)


async def test_concurrent_operations_with_error_handling():
    """Test error handling under concurrent operations."""
    print("🧪 Testing concurrent operations with error handling...")
    
    temp_db = await setup_test_database()
    
    try:
        handler = ComprehensiveErrorHandler(temp_db)
        
        # Create multiple concurrent coordinate update tasks
        tasks = []
        for i in range(5):
            # Mix of valid and invalid coordinates
            if i % 2 == 0:
                lat, lon = 40.0 + i * 0.1, -74.0 + i * 0.1  # Valid
            else:
                lat, lon = 91.0 + i, 0.0  # Invalid
            
            task = handler.handle_camera_coordinate_update(1, lat, lon)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful_updates = 0
        failed_updates = 0
        
        for result in results:
            if isinstance(result, OperationResult):
                if result.success:
                    successful_updates += 1
                else:
                    failed_updates += 1
            else:
                failed_updates += 1
        
        # Should have some successes and some failures
        assert successful_updates > 0
        assert failed_updates > 0
        
        print(f"✅ Concurrent operations test passed ({successful_updates} successes, {failed_updates} failures)")
        
    finally:
        os.unlink(temp_db)


async def test_performance_under_load():
    """Test error handling performance under load."""
    print("🧪 Testing performance under load...")
    
    temp_db = await setup_test_database()
    
    try:
        handler = ComprehensiveErrorHandler(temp_db)
        
        import time
        start_time = time.time()
        
        # Perform many validation operations
        validation_tasks = []
        for i in range(100):
            input_data = {
                'latitude': 40.0 + (i % 10) * 0.1,
                'longitude': -74.0 + (i % 10) * 0.1,
                'coverage_radius': 50.0 + i,
                'camera_id': i % 3 + 1
            }
            
            # Add some invalid data
            if i % 10 == 0:
                input_data['latitude'] = 91.0  # Invalid
            
            validation_tasks.append(handler.validate_and_sanitize_input(input_data))
        
        # Execute validation tasks
        results = await asyncio.gather(*validation_tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Check that all operations completed
        assert len(results) == 100
        
        # Check performance (should complete in reasonable time)
        assert execution_time < 5.0  # Should complete within 5 seconds
        
        print(f"✅ Performance test passed ({execution_time:.2f}s for 100 operations)")
        
    finally:
        os.unlink(temp_db)


async def main():
    """Run all comprehensive error handling tests."""
    print("🚀 Starting Comprehensive Error Handling Integration Tests\n")
    
    try:
        await test_coordinate_validation_integration()
        print()
        
        await test_database_transaction_rollback()
        print()
        
        await test_connectivity_retry_integration()
        print()
        
        await test_javascript_fallback_integration()
        print()
        
        await test_comprehensive_input_validation()
        print()
        
        await test_error_logging_and_recovery()
        print()
        
        await test_concurrent_operations_with_error_handling()
        print()
        
        await test_performance_under_load()
        print()
        
        print("🎉 All comprehensive error handling integration tests passed!")
        print("\n📋 Error Handling Features Verified:")
        print("  ✅ Coordinate validation with detailed error messages")
        print("  ✅ Database transaction handling with atomic operations")
        print("  ✅ JavaScript fallback mechanisms (read-only mode)")
        print("  ✅ Retry logic for connectivity testing and database operations")
        print("  ✅ Comprehensive input validation and sanitization")
        print("  ✅ Error logging and recovery mechanisms")
        print("  ✅ Concurrent operation handling")
        print("  ✅ Performance under load")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())