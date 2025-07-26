"""
Performance Tests for Interactive Camera Mapping System

This test suite validates performance characteristics of the mapping system:
- Map generation time with varying camera counts
- Coverage calculation performance
- Drag-and-drop response times
- Memory usage during large operations
- Concurrent operation handling

Requirements tested:
- System should handle 100+ cameras without significant performance degradation
- Map generation should complete within reasonable time limits
- Coverage calculations should be efficient for real-time updates
"""

import asyncio
import time
import sqlite3
import tempfile
import os
import sys
import pytest
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from interactive_map_manager import InteractiveMapManager
from coverage_calculator import CoverageCalculator
from connectivity_monitor import ConnectivityMonitor
from map_configuration_manager import MapConfigurationManager


class TestMappingPerformance:
    """Performance tests for the interactive mapping system."""
    
    @pytest.fixture
    def large_camera_db(self):
        """Create a database with a large number of cameras for performance testing."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(db_fd)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create schema
        cursor.execute("""
            CREATE TABLE cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                mac_address TEXT,
                latitude REAL,
                longitude REAL,
                coverage_radius REAL DEFAULT 50.0,
                field_of_view_angle REAL DEFAULT 360.0,
                coverage_direction REAL DEFAULT 0.0,
                has_memory_card BOOLEAN DEFAULT 0,
                memory_card_last_reset TEXT,
                dvr_id INTEGER,
                locational_group TEXT,
                date_installed TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE map_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                configuration_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                details TEXT
            )
        """)
        
        # Generate 500 test cameras spread across a realistic area
        cameras = []
        base_lat = 40.7128  # NYC
        base_lon = -74.0060
        
        for i in range(1, 501):
            # Spread cameras in a 10km x 10km grid
            lat_offset = (i % 50) * 0.002  # ~200m spacing
            lon_offset = (i // 50) * 0.002
            
            lat = base_lat + lat_offset
            lon = base_lon + lon_offset
            
            # Vary coverage parameters for realistic testing
            radius = 30.0 + (i % 100)  # 30-130m radius
            angle = 360.0 if i % 3 == 0 else 90.0 + (i % 180)  # Mix of circular and directional
            direction = (i * 37) % 360  # Pseudo-random directions
            
            cameras.append((
                i, f'CAM-{i:03d}', f'Location {i}', f'192.168.{(i//254)+1}.{i%254+1}',
                f'00:1A:2B:{(i//65536):02X}:{(i//256)%256:02X}:{i%256:02X}',
                lat, lon, radius, angle, direction
            ))
        
        cursor.executemany("""
            INSERT INTO cameras (id, name, location, ip_address, mac_address, latitude, longitude,
                               coverage_radius, field_of_view_angle, coverage_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, cameras)
        
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_map_generation_performance_scaling(self, large_camera_db):
        """Test map generation performance with increasing camera counts."""
        map_manager = InteractiveMapManager(large_camera_db)
        
        # Test with different camera counts
        camera_counts = [10, 50, 100, 250, 500]
        generation_times = []
        
        for count in camera_counts:
            # Temporarily limit cameras in database
            conn = sqlite3.connect(large_camera_db)
            cursor = conn.cursor()
            
            # Disable cameras beyond the test count
            cursor.execute("UPDATE cameras SET latitude = NULL WHERE id > ?", (count,))
            conn.commit()
            conn.close()
            
            # Measure map generation time
            start_time = time.time()
            map_html = await map_manager.create_enhanced_map()
            generation_time = time.time() - start_time
            generation_times.append(generation_time)
            
            # Verify map was generated successfully
            assert isinstance(map_html, str)
            assert len(map_html) > 1000  # Should be substantial HTML
            assert f'CAM-{count:03d}' in map_html  # Should include the last camera
            
            print(f"Map generation with {count} cameras: {generation_time:.2f}s")
        
        # Performance should not degrade exponentially
        # Allow some increase but not more than linear scaling
        for i in range(1, len(generation_times)):
            ratio = generation_times[i] / generation_times[0]
            camera_ratio = camera_counts[i] / camera_counts[0]
            
            # Performance should not be worse than 2x linear scaling
            assert ratio < (camera_ratio * 2), f"Performance degraded too much: {ratio} vs expected max {camera_ratio * 2}"
        
        # Restore all cameras
        conn = sqlite3.connect(large_camera_db)
        cursor = conn.cursor()
        cursor.execute("UPDATE cameras SET latitude = 40.7128 + (id % 50) * 0.002 WHERE latitude IS NULL")
        conn.commit()
        conn.close()
    
    @pytest.mark.asyncio
    async def test_coverage_calculation_performance(self, large_camera_db):
        """Test performance of coverage area calculations."""
        # Test circular coverage calculation performance
        start_time = time.time()
        
        for i in range(1000):
            lat = 40.7128 + (i * 0.001)
            lon = -74.0060 + (i * 0.001)
            radius = 50.0 + (i % 100)
            
            coords = CoverageCalculator.calculate_circular_coverage(lat, lon, radius)
            assert len(coords) > 0
        
        circular_time = time.time() - start_time
        print(f"1000 circular coverage calculations: {circular_time:.2f}s")
        
        # Should complete within reasonable time
        assert circular_time < 5.0  # 5 seconds for 1000 calculations
        
        # Test directional coverage calculation performance
        start_time = time.time()
        
        for i in range(1000):
            lat = 40.7128 + (i * 0.001)
            lon = -74.0060 + (i * 0.001)
            radius = 50.0 + (i % 100)
            direction = (i * 37) % 360
            angle = 90.0 + (i % 180)
            
            coords = CoverageCalculator.calculate_directional_coverage(lat, lon, radius, direction, angle)
            assert len(coords) > 0
        
        directional_time = time.time() - start_time
        print(f"1000 directional coverage calculations: {directional_time:.2f}s")
        
        # Should complete within reasonable time
        assert directional_time < 10.0  # 10 seconds for 1000 calculations
    
    @pytest.mark.asyncio
    async def test_drag_drop_response_time(self, large_camera_db):
        """Test response time for drag-and-drop operations."""
        map_manager = InteractiveMapManager(large_camera_db)
        
        # Test multiple drag operations
        response_times = []
        
        for i in range(1, 21):  # Test 20 drag operations
            new_lat = 40.7128 + (i * 0.001)
            new_lon = -74.0060 + (i * 0.001)
            
            start_time = time.time()
            result = await map_manager.handle_camera_move(i, new_lat, new_lon)
            response_time = time.time() - start_time
            response_times.append(response_time)
            
            assert result['success'] is True
            print(f"Drag operation {i}: {response_time:.3f}s")
        
        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        print(f"Average drag response time: {avg_response_time:.3f}s")
        print(f"Maximum drag response time: {max_response_time:.3f}s")
        
        # Response times should be reasonable for interactive use
        assert avg_response_time < 0.5  # Average under 500ms
        assert max_response_time < 1.0   # Maximum under 1 second
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_performance(self, large_camera_db):
        """Test performance under concurrent operations."""
        map_manager = InteractiveMapManager(large_camera_db)
        
        # Test concurrent drag operations
        async def perform_drag(camera_id):
            new_lat = 40.7128 + (camera_id * 0.001)
            new_lon = -74.0060 + (camera_id * 0.001)
            return await map_manager.handle_camera_move(camera_id, new_lat, new_lon)
        
        # Perform 20 concurrent drag operations
        start_time = time.time()
        tasks = [perform_drag(i) for i in range(1, 21)]
        results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        # Verify all operations succeeded
        for result in results:
            assert result['success'] is True
        
        print(f"20 concurrent drag operations: {concurrent_time:.2f}s")
        
        # Should complete within reasonable time
        assert concurrent_time < 5.0  # 5 seconds for 20 concurrent operations
    
    @pytest.mark.asyncio
    async def test_connectivity_monitoring_performance(self, large_camera_db):
        """Test performance of connectivity monitoring with many cameras."""
        connectivity_monitor = ConnectivityMonitor(large_camera_db, cache_timeout=60)
        
        # Create device list for all 500 cameras
        devices = []
        for i in range(1, 501):
            devices.append({
                'id': i,
                'ip_address': f'192.168.{(i//254)+1}.{i%254+1}',
                'name': f'CAM-{i:03d}',
                'type': 'camera'
            })
        
        # Mock ping to simulate network responses
        with patch('src.connectivity_monitor.ping') as mock_ping:
            # Simulate mixed response times
            mock_ping.side_effect = [0.05 if i % 3 != 0 else None for i in range(500)]
            
            start_time = time.time()
            results = await connectivity_monitor.batch_connectivity_test(devices)
            batch_time = time.time() - start_time
            
            print(f"Batch connectivity test for 500 cameras: {batch_time:.2f}s")
            
            # Should complete within reasonable time
            assert batch_time < 60.0  # 1 minute for 500 cameras
            assert len(results) == 500
            
            # Test cache performance
            start_time = time.time()
            cached_results = await connectivity_monitor.batch_connectivity_test(devices)
            cached_time = time.time() - start_time
            
            print(f"Cached connectivity test for 500 cameras: {cached_time:.2f}s")
            
            # Cached results should be much faster
            assert cached_time < (batch_time * 0.1)  # Should be at least 10x faster
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_large_operations(self, large_camera_db):
        """Test memory usage during large-scale operations."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        map_manager = InteractiveMapManager(large_camera_db)
        
        # Generate map with all 500 cameras
        map_html = await map_manager.create_enhanced_map()
        
        after_map_memory = process.memory_info().rss / 1024 / 1024  # MB
        map_memory_increase = after_map_memory - initial_memory
        
        print(f"Memory usage - Initial: {initial_memory:.1f}MB, After map: {after_map_memory:.1f}MB")
        print(f"Map generation memory increase: {map_memory_increase:.1f}MB")
        
        # Memory increase should be reasonable
        assert map_memory_increase < 500  # Less than 500MB increase
        
        # Test memory usage during batch operations
        connectivity_monitor = ConnectivityMonitor(large_camera_db)
        
        devices = []
        for i in range(1, 501):
            devices.append({
                'id': i,
                'ip_address': f'192.168.{(i//254)+1}.{i%254+1}',
                'name': f'CAM-{i:03d}',
                'type': 'camera'
            })
        
        with patch('src.connectivity_monitor.ping', return_value=0.05):
            await connectivity_monitor.batch_connectivity_test(devices)
        
        after_connectivity_memory = process.memory_info().rss / 1024 / 1024  # MB
        connectivity_memory_increase = after_connectivity_memory - after_map_memory
        
        print(f"Connectivity test memory increase: {connectivity_memory_increase:.1f}MB")
        
        # Memory increase should be reasonable
        assert connectivity_memory_increase < 100  # Less than 100MB additional increase
    
    @pytest.mark.asyncio
    async def test_configuration_save_load_performance(self, large_camera_db):
        """Test performance of configuration save/load operations."""
        config_manager = MapConfigurationManager(large_camera_db)
        
        # Test saving configuration with 500 cameras
        start_time = time.time()
        save_result = await config_manager.save_configuration(
            "Performance Test Config",
            "Configuration with 500 cameras for performance testing"
        )
        save_time = time.time() - start_time
        
        assert save_result.success is True
        config_id = save_result.configuration_id
        
        print(f"Configuration save time (500 cameras): {save_time:.2f}s")
        
        # Should complete within reasonable time
        assert save_time < 10.0  # 10 seconds max
        
        # Test loading configuration
        start_time = time.time()
        load_result = await config_manager.load_configuration(config_id)
        load_time = time.time() - start_time
        
        assert load_result.success is True
        
        print(f"Configuration load time (500 cameras): {load_time:.2f}s")
        
        # Should complete within reasonable time
        assert load_time < 30.0  # 30 seconds max (includes database updates)
    
    def test_coverage_overlap_detection_performance(self, large_camera_db):
        """Test performance of coverage overlap detection."""
        # Create camera data for overlap testing
        cameras = []
        for i in range(1, 101):  # Test with 100 cameras
            cameras.append({
                'id': i,
                'name': f'CAM-{i:03d}',
                'latitude': 40.7128 + (i % 10) * 0.001,  # Cluster cameras for overlaps
                'longitude': -74.0060 + (i // 10) * 0.001,
                'coverage_radius': 50.0 + (i % 50),
                'field_of_view_angle': 360.0,
                'coverage_direction': 0.0
            })
        
        start_time = time.time()
        overlaps = CoverageCalculator.find_coverage_overlaps(cameras)
        overlap_time = time.time() - start_time
        
        print(f"Overlap detection for 100 cameras: {overlap_time:.2f}s")
        print(f"Found {len(overlaps)} overlapping pairs")
        
        # Should complete within reasonable time
        assert overlap_time < 5.0  # 5 seconds for 100 cameras
        
        # Verify overlaps were found (cameras are clustered, so should have overlaps)
        assert len(overlaps) > 0


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '-s'])  # -s to show print statements