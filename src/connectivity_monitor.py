"""
Real-time Connectivity Monitor for Camera Management System

This module provides comprehensive connectivity monitoring capabilities including
caching, batch testing, status color coding, and automatic refresh functionality
for cameras and DVRs in the surveillance system.
"""

import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from ping3 import ping
import aiosqlite
from concurrent.futures import ThreadPoolExecutor, as_completed
from .error_handling import get_error_handler


@dataclass
class ConnectivityResult:
    """Represents the connectivity test result for a device."""
    device_id: int
    device_type: str  # 'camera' or 'dvr'
    ip_address: str
    device_name: str
    is_online: bool
    response_time: Optional[float]
    status_text: str
    status_color: str
    timestamp: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectivityResult':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class ConnectivityStats:
    """Statistics about connectivity monitoring."""
    total_devices: int
    online_devices: int
    offline_devices: int
    average_response_time: Optional[float]
    last_update: datetime
    cache_hit_rate: float
    
    @property
    def online_percentage(self) -> float:
        """Calculate percentage of online devices."""
        if self.total_devices == 0:
            return 0.0
        return (self.online_devices / self.total_devices) * 100


class ConnectivityMonitor:
    """
    Monitors camera and DVR connectivity with advanced features.
    
    Features:
    - Caching for ping results with configurable timeout
    - Batch connectivity testing for multiple devices
    - Status color coding based on connectivity results
    - Automatic status refresh with configurable intervals
    - Comprehensive logging and statistics
    """
    
    def __init__(self, db_name: str = "camera_data.db", cache_timeout: int = 30, 
                 ping_timeout: int = 3, max_workers: int = 10):
        """
        Initialize the ConnectivityMonitor.
        
        Args:
            db_name: Path to the SQLite database
            cache_timeout: Cache timeout in seconds (default: 30)
            ping_timeout: Ping timeout in seconds (default: 3)
            max_workers: Maximum concurrent ping operations (default: 10)
        """
        self.db_name = db_name
        self.cache_timeout = cache_timeout
        self.ping_timeout = ping_timeout
        self.max_workers = max_workers
        
        # Cache for ping results: {ip_address: (ConnectivityResult, timestamp)}
        self.ping_cache: Dict[str, Tuple[ConnectivityResult, float]] = {}
        
        # Statistics tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_tests = 0
        
        # Auto-refresh settings
        self.auto_refresh_enabled = False
        self.refresh_interval = 60  # seconds
        self.refresh_task: Optional[asyncio.Task] = None
        self.refresh_callbacks: List[Callable[[Dict[str, ConnectivityResult]], None]] = []
        
        # Initialize retry settings for robust connectivity testing
        self.max_retries = 2
        self.base_delay = 0.5
    
    async def test_camera_connectivity(self, camera_ip: str, camera_id: int = None, 
                                     camera_name: str = None) -> ConnectivityResult:
        """
        Test camera connectivity with caching.
        
        Args:
            camera_ip: IP address of the camera
            camera_id: Camera ID (optional)
            camera_name: Camera name (optional)
            
        Returns:
            ConnectivityResult object with test results
            
        Requirements addressed:
        - 4.1: Test connectivity to all cameras and display their status
        """
        current_time = time.time()
        
        # Check cache first
        if camera_ip in self.ping_cache:
            cached_result, timestamp = self.ping_cache[camera_ip]
            if current_time - timestamp < self.cache_timeout:
                self.cache_hits += 1
                return cached_result
        
        self.cache_misses += 1
        self.total_tests += 1
        
        # Perform ping test with simple retry logic
        max_attempts = 3
        result = None
        
        for attempt in range(max_attempts):
            try:
                response_time = await self._async_ping(camera_ip)
                is_online = response_time is not None
                
                if is_online:
                    status_text = f"✅ Online ({response_time:.2f}ms)"
                    status_color = "green"
                    error_message = None
                else:
                    status_text = "❌ Offline"
                    status_color = "red"
                    error_message = "No response to ping"
                
                result = ConnectivityResult(
                    device_id=camera_id or 0,
                    device_type='camera',
                    ip_address=camera_ip,
                    device_name=camera_name or f"Camera {camera_ip}",
                    is_online=is_online,
                    response_time=response_time,
                    status_text=status_text,
                    status_color=status_color,
                    timestamp=datetime.now(),
                    error_message=error_message
                )
                
                # If we got a result (success or failure), break out of retry loop
                break
                
            except Exception as e:
                if attempt == max_attempts - 1:  # Last attempt
                    result = ConnectivityResult(
                        device_id=camera_id or 0,
                        device_type='camera',
                        ip_address=camera_ip,
                        device_name=camera_name or f"Camera {camera_ip}",
                        is_online=False,
                        response_time=None,
                        status_text=f"⚠️ Error: {str(e)[:50]}",
                        status_color="orange",
                        timestamp=datetime.now(),
                        error_message=str(e)
                    )
                else:
                    # Wait before retry
                    await asyncio.sleep(0.5 * (attempt + 1))
        
        # Fallback result if something went wrong
        if result is None:
            result = ConnectivityResult(
                device_id=camera_id or 0,
                device_type='camera',
                ip_address=camera_ip,
                device_name=camera_name or f"Camera {camera_ip}",
                is_online=False,
                response_time=None,
                status_text="⚠️ Unknown error",
                status_color="orange",
                timestamp=datetime.now(),
                error_message="Unknown connectivity test error"
            )
        
        # Cache the result
        self.ping_cache[camera_ip] = (result, current_time)
        
        return result
    
    async def test_dvr_connectivity(self, dvr_ip: str, dvr_id: int = None, 
                                  dvr_name: str = None) -> ConnectivityResult:
        """
        Test DVR connectivity with caching.
        
        Args:
            dvr_ip: IP address of the DVR
            dvr_id: DVR ID (optional)
            dvr_name: DVR name (optional)
            
        Returns:
            ConnectivityResult object with test results
        """
        current_time = time.time()
        
        # Check cache first
        if dvr_ip in self.ping_cache:
            cached_result, timestamp = self.ping_cache[dvr_ip]
            if current_time - timestamp < self.cache_timeout:
                self.cache_hits += 1
                # Update device type if it was cached as camera
                if cached_result.device_type != 'dvr':
                    cached_result.device_type = 'dvr'
                    cached_result.device_id = dvr_id or cached_result.device_id
                    cached_result.device_name = dvr_name or cached_result.device_name
                return cached_result
        
        self.cache_misses += 1
        self.total_tests += 1
        
        # Perform ping test
        try:
            response_time = await self._async_ping(dvr_ip)
            is_online = response_time is not None
            
            if is_online:
                status_text = f"✅ Online ({response_time:.2f}ms)"
                status_color = "green"
                error_message = None
            else:
                status_text = "❌ Offline"
                status_color = "red"
                error_message = "No response to ping"
            
            result = ConnectivityResult(
                device_id=dvr_id or 0,
                device_type='dvr',
                ip_address=dvr_ip,
                device_name=dvr_name or f"DVR {dvr_ip}",
                is_online=is_online,
                response_time=response_time,
                status_text=status_text,
                status_color=status_color,
                timestamp=datetime.now(),
                error_message=error_message
            )
            
        except Exception as e:
            result = ConnectivityResult(
                device_id=dvr_id or 0,
                device_type='dvr',
                ip_address=dvr_ip,
                device_name=dvr_name or f"DVR {dvr_ip}",
                is_online=False,
                response_time=None,
                status_text=f"⚠️ Error: {str(e)[:50]}",
                status_color="orange",
                timestamp=datetime.now(),
                error_message=str(e)
            )
        
        # Cache the result
        self.ping_cache[dvr_ip] = (result, current_time)
        
        return result
    
    async def batch_connectivity_test(self, devices: List[Dict[str, Any]]) -> Dict[str, ConnectivityResult]:
        """
        Test multiple devices concurrently.
        
        Args:
            devices: List of device dictionaries with keys:
                    - id, ip_address, name, type ('camera' or 'dvr')
                    
        Returns:
            Dictionary mapping device IDs to ConnectivityResult objects
            
        Requirements addressed:
        - 4.1: Test connectivity to all cameras and display their status
        """
        if not devices:
            return {}
        
        # Create tasks for concurrent testing
        tasks = []
        device_map = {}
        
        for device in devices:
            device_id = device.get('id')
            ip_address = device.get('ip_address')
            name = device.get('name', f"Device {ip_address}")
            device_type = device.get('type', 'camera')
            
            if not ip_address:
                continue
            
            device_map[ip_address] = device_id
            
            if device_type == 'dvr':
                task = self.test_dvr_connectivity(ip_address, device_id, name)
            else:
                task = self.test_camera_connectivity(ip_address, device_id, name)
            
            tasks.append(task)
        
        # Execute all tests concurrently with limited workers
        results = {}
        
        if tasks:
            # Use semaphore to limit concurrent operations
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def limited_test(task):
                async with semaphore:
                    return await task
            
            # Execute tasks with concurrency limit
            completed_results = await asyncio.gather(*[limited_test(task) for task in tasks], 
                                                    return_exceptions=True)
            
            # Process results
            for result in completed_results:
                if isinstance(result, ConnectivityResult):
                    results[result.device_id] = result
                elif isinstance(result, Exception):
                    print(f"Error in batch connectivity test: {result}")
        
        return results
    
    async def get_all_devices_status(self) -> Dict[str, ConnectivityResult]:
        """
        Get connectivity status for all cameras and DVRs from database.
        
        Returns:
            Dictionary mapping device IDs to ConnectivityResult objects
            
        Requirements addressed:
        - 4.1: Test connectivity to all cameras and display their status
        """
        devices = []
        
        try:
            async with aiosqlite.connect(self.db_name) as db:
                # Get cameras
                cursor = await db.execute("""
                    SELECT id, name, ip_address FROM cameras 
                    WHERE ip_address IS NOT NULL AND ip_address != ''
                """)
                cameras = await cursor.fetchall()
                
                for camera in cameras:
                    devices.append({
                        'id': camera[0],
                        'name': camera[1],
                        'ip_address': camera[2],
                        'type': 'camera'
                    })
                
                # Get DVRs
                cursor = await db.execute("""
                    SELECT id, name, ip_address FROM dvrs 
                    WHERE ip_address IS NOT NULL AND ip_address != ''
                """)
                dvrs = await cursor.fetchall()
                
                for dvr in dvrs:
                    devices.append({
                        'id': dvr[0],
                        'name': dvr[1],
                        'ip_address': dvr[2],
                        'type': 'dvr'
                    })
        
        except Exception as e:
            print(f"Error getting devices from database: {e}")
            return {}
        
        return await self.batch_connectivity_test(devices)
    
    def get_status_color(self, is_online: bool, has_error: bool = False) -> str:
        """
        Get marker color based on connectivity status.
        
        Args:
            is_online: Whether the device is online
            has_error: Whether there was an error during testing
            
        Returns:
            Color string for map markers
            
        Requirements addressed:
        - 4.2: Display marker in red when offline, green when online
        - 4.4: Display camera with warning indicator when testing fails
        """
        if has_error:
            return 'orange'  # Warning indicator
        return 'green' if is_online else 'red'
    
    def get_status_icon(self, is_online: bool, has_error: bool = False) -> str:
        """Get status icon based on connectivity."""
        if has_error:
            return '⚠️'
        return '✅' if is_online else '❌'
    
    def get_coverage_opacity(self, is_online: bool) -> float:
        """
        Get coverage area opacity based on connectivity status.
        
        Requirements addressed:
        - 4.2: Show reduced opacity for coverage area when offline
        - 4.3: Restore full opacity when camera comes back online
        """
        return 0.4 if is_online else 0.15
    
    def clear_cache(self):
        """Clear the ping cache."""
        self.ping_cache.clear()
        print("Connectivity cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        
        total_entries = len(self.ping_cache)
        expired_entries = 0
        
        for ip, (result, timestamp) in self.ping_cache.items():
            if current_time - timestamp >= self.cache_timeout:
                expired_entries += 1
        
        cache_hit_rate = 0.0
        if self.total_tests > 0:
            cache_hit_rate = (self.cache_hits / self.total_tests) * 100
        
        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'active_entries': total_entries - expired_entries,
            'cache_timeout': self.cache_timeout,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_tests': self.total_tests,
            'cache_hit_rate': cache_hit_rate
        }
    
    def get_connectivity_stats(self, results: Dict[str, ConnectivityResult]) -> ConnectivityStats:
        """
        Generate connectivity statistics from results.
        
        Args:
            results: Dictionary of connectivity results
            
        Returns:
            ConnectivityStats object with summary information
        """
        if not results:
            return ConnectivityStats(
                total_devices=0,
                online_devices=0,
                offline_devices=0,
                average_response_time=None,
                last_update=datetime.now(),
                cache_hit_rate=0.0
            )
        
        online_devices = sum(1 for r in results.values() if r.is_online)
        offline_devices = len(results) - online_devices
        
        # Calculate average response time for online devices
        response_times = [r.response_time for r in results.values() 
                         if r.is_online and r.response_time is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        
        # Calculate cache hit rate
        cache_hit_rate = 0.0
        if self.total_tests > 0:
            cache_hit_rate = (self.cache_hits / self.total_tests) * 100
        
        return ConnectivityStats(
            total_devices=len(results),
            online_devices=online_devices,
            offline_devices=offline_devices,
            average_response_time=avg_response_time,
            last_update=datetime.now(),
            cache_hit_rate=cache_hit_rate
        )
    
    async def start_auto_refresh(self, interval: int = 60):
        """
        Start automatic status refresh functionality.
        
        Args:
            interval: Refresh interval in seconds
            
        Requirements addressed:
        - 4.3: Automatic status refresh functionality with configurable intervals
        """
        self.refresh_interval = interval
        self.auto_refresh_enabled = True
        
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()
        
        self.refresh_task = asyncio.create_task(self._auto_refresh_loop())
        print(f"Auto-refresh started with {interval}s interval")
    
    async def stop_auto_refresh(self):
        """Stop automatic status refresh."""
        self.auto_refresh_enabled = False
        
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        
        print("Auto-refresh stopped")
    
    def add_refresh_callback(self, callback: Callable[[Dict[str, ConnectivityResult]], None]):
        """
        Add callback function to be called when auto-refresh completes.
        
        Args:
            callback: Function that takes connectivity results dictionary
        """
        self.refresh_callbacks.append(callback)
    
    def remove_refresh_callback(self, callback: Callable[[Dict[str, ConnectivityResult]], None]):
        """Remove refresh callback."""
        if callback in self.refresh_callbacks:
            self.refresh_callbacks.remove(callback)
    
    async def _auto_refresh_loop(self):
        """Internal auto-refresh loop."""
        while self.auto_refresh_enabled:
            try:
                # Get fresh connectivity status for all devices
                results = await self.get_all_devices_status()
                
                # Call all registered callbacks
                for callback in self.refresh_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(results)
                        else:
                            callback(results)
                    except Exception as e:
                        print(f"Error in refresh callback: {e}")
                
                # Wait for next refresh
                await asyncio.sleep(self.refresh_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in auto-refresh loop: {e}")
                await asyncio.sleep(5)  # Short delay before retrying
    
    async def _async_ping(self, ip_address: str) -> Optional[float]:
        """
        Perform asynchronous ping operation.
        
        Args:
            ip_address: IP address to ping
            
        Returns:
            Response time in milliseconds, or None if ping failed
        """
        def sync_ping():
            try:
                return ping(ip_address, timeout=self.ping_timeout)
            except Exception:
                return None
        
        # Run ping in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                result = await loop.run_in_executor(executor, sync_ping)
                return result * 1000 if result is not None else None  # Convert to milliseconds
            except Exception:
                return None
    
    async def refresh_all_statuses(self) -> Dict[str, ConnectivityResult]:
        """
        Force refresh of all device statuses, bypassing cache.
        
        Returns:
            Dictionary of fresh connectivity results
        """
        # Clear cache to force fresh tests
        self.clear_cache()
        
        # Run batch connectivity test
        return await self.get_all_devices_status()
    
    async def export_connectivity_log(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Export connectivity test results from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of connectivity results as dictionaries
        """
        # This would typically read from a persistent log
        # For now, return current cache data
        current_time = time.time()
        cutoff_time = current_time - (hours * 3600)
        
        log_entries = []
        for ip, (result, timestamp) in self.ping_cache.items():
            if timestamp >= cutoff_time:
                log_entries.append(result.to_dict())
        
        return sorted(log_entries, key=lambda x: x['timestamp'], reverse=True)
    
    def __del__(self):
        """Cleanup when monitor is destroyed."""
        if self.refresh_task and not self.refresh_task.done():
            self.refresh_task.cancel()


# Utility functions for working with connectivity monitoring
async def create_connectivity_monitor(db_name: str = "camera_data.db", 
                                    cache_timeout: int = 30) -> ConnectivityMonitor:
    """Create and initialize a ConnectivityMonitor instance."""
    monitor = ConnectivityMonitor(db_name=db_name, cache_timeout=cache_timeout)
    return monitor


def format_connectivity_summary(stats: ConnectivityStats) -> str:
    """Format connectivity statistics as a readable summary."""
    return f"""
📊 Connectivity Summary:
• Total Devices: {stats.total_devices}
• Online: {stats.online_devices} ({stats.online_percentage:.1f}%)
• Offline: {stats.offline_devices}
• Avg Response: {stats.average_response_time:.2f}ms" if stats.average_response_time else "N/A"
• Cache Hit Rate: {stats.cache_hit_rate:.1f}%
• Last Update: {stats.last_update.strftime('%Y-%m-%d %H:%M:%S')}
"""


def get_status_summary_by_type(results: Dict[str, ConnectivityResult]) -> Dict[str, Dict[str, int]]:
    """Get connectivity summary grouped by device type."""
    summary = {
        'camera': {'online': 0, 'offline': 0, 'error': 0},
        'dvr': {'online': 0, 'offline': 0, 'error': 0}
    }
    
    for result in results.values():
        device_type = result.device_type
        if device_type not in summary:
            summary[device_type] = {'online': 0, 'offline': 0, 'error': 0}
        
        if result.error_message:
            summary[device_type]['error'] += 1
        elif result.is_online:
            summary[device_type]['online'] += 1
        else:
            summary[device_type]['offline'] += 1
    
    return summary