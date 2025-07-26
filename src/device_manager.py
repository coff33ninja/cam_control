"""
Device Management Utility for Camera System

This module provides utilities for managing device information,
including manufacturer data, model information, and RTSP configuration.
"""

import asyncio
import json
import logging
import csv
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiosqlite


class DeviceManager:
    """Manager for camera device information and manufacturer data."""
    
    def __init__(self, device_db_path: str = "device_info.db"):
        """Initialize device manager."""
        self.device_db_path = device_db_path
        self.logger = logging.getLogger(__name__)
    
    async def import_device_data_from_csv(self, csv_file_path: str) -> Dict[str, Any]:
        """Import device data from CSV file."""
        try:
            imported_count = 0
            errors = []
            
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                async with aiosqlite.connect(self.device_db_path) as db:
                    for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                        try:
                            camera_id = int(row.get('camera_id', 0))
                            manufacturer = row.get('manufacturer', '').strip()
                            model = row.get('model', '').strip()
                            serial_number = row.get('serial_number', '').strip()
                            rtsp_url = row.get('rtsp_url', '').strip()
                            username = row.get('username', '').strip()
                            password = row.get('password', '').strip()
                            
                            if not camera_id:
                                errors.append(f"Row {row_num}: Missing camera_id")
                                continue
                            
                            # Insert or update device info
                            await db.execute("""
                                INSERT OR REPLACE INTO device_info 
                                (camera_id, manufacturer, model, serial_number, rtsp_url, username, password, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (camera_id, manufacturer, model, serial_number, rtsp_url, username, password, datetime.now().isoformat()))
                            
                            imported_count += 1
                            
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                    
                    await db.commit()
            
            return {
                'success': True,
                'imported_count': imported_count,
                'errors': errors,
                'message': f'Successfully imported {imported_count} device records'
            }
            
        except Exception as e:
            self.logger.error(f"Error importing device data from CSV: {e}")
            return {
                'success': False,
                'message': f'Error importing CSV: {str(e)}',
                'imported_count': 0,
                'errors': [str(e)]
            }
    
    async def export_device_data_to_csv(self, csv_file_path: str) -> Dict[str, Any]:
        """Export device data to CSV file."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                cursor = await db.execute("""
                    SELECT camera_id, manufacturer, model, serial_number, firmware_version,
                           rtsp_url, rtsp_port, username, password, stream_quality
                    FROM device_info
                    ORDER BY camera_id
                """)
                
                rows = await cursor.fetchall()
                
                with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = [
                        'camera_id', 'manufacturer', 'model', 'serial_number', 
                        'firmware_version', 'rtsp_url', 'rtsp_port', 'username', 
                        'password', 'stream_quality'
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    
                    for row in rows:
                        writer.writerow({
                            'camera_id': row[0],
                            'manufacturer': row[1] or '',
                            'model': row[2] or '',
                            'serial_number': row[3] or '',
                            'firmware_version': row[4] or '',
                            'rtsp_url': row[5] or '',
                            'rtsp_port': row[6] or 554,
                            'username': row[7] or '',
                            'password': row[8] or '',
                            'stream_quality': row[9] or 'main'
                        })
                
                return {
                    'success': True,
                    'exported_count': len(rows),
                    'file_path': csv_file_path,
                    'message': f'Successfully exported {len(rows)} device records'
                }
                
        except Exception as e:
            self.logger.error(f"Error exporting device data to CSV: {e}")
            return {
                'success': False,
                'message': f'Error exporting CSV: {str(e)}',
                'exported_count': 0
            }
    
    async def auto_detect_device_info(self, camera_id: int, ip_address: str) -> Dict[str, Any]:
        """Auto-detect device information from camera IP address."""
        try:
            device_info = {
                'manufacturer': None,
                'model': None,
                'serial_number': None,
                'rtsp_url': None,
                'confidence': 0.0
            }
            
            # Try to detect manufacturer from common RTSP paths
            rtsp_tests = [
                ('Hikvision', f'rtsp://{ip_address}:554/Streaming/Channels/101'),
                ('Dahua', f'rtsp://{ip_address}:554/cam/realmonitor?channel=1&subtype=0'),
                ('Axis', f'rtsp://{ip_address}:554/axis-media/media.amp'),
                ('Foscam', f'rtsp://{ip_address}:554/videoMain'),
                ('Reolink', f'rtsp://{ip_address}:554/h264Preview_01_main'),
                ('Ubiquiti', f'rtsp://{ip_address}:554/s0')
            ]
            
            # Test connectivity to different RTSP paths
            detected_manufacturer = None
            working_rtsp_url = None
            
            for manufacturer, rtsp_url in rtsp_tests:
                if await self._test_rtsp_connectivity(rtsp_url):
                    detected_manufacturer = manufacturer
                    working_rtsp_url = rtsp_url
                    device_info['confidence'] = 0.8
                    break
            
            if detected_manufacturer:
                device_info['manufacturer'] = detected_manufacturer
                device_info['rtsp_url'] = working_rtsp_url
                
                # Try to get more detailed info via HTTP API (if available)
                additional_info = await self._get_device_info_via_http(ip_address, detected_manufacturer)
                if additional_info:
                    device_info.update(additional_info)
                    device_info['confidence'] = min(1.0, device_info['confidence'] + 0.2)
            
            # If no manufacturer detected, try generic RTSP paths
            if not detected_manufacturer:
                generic_paths = ['/stream1', '/live', '/video', '/cam1']
                for path in generic_paths:
                    rtsp_url = f'rtsp://{ip_address}:554{path}'
                    if await self._test_rtsp_connectivity(rtsp_url):
                        device_info['manufacturer'] = 'Generic'
                        device_info['rtsp_url'] = rtsp_url
                        device_info['confidence'] = 0.3
                        break
            
            return {
                'success': True,
                'device_info': device_info,
                'message': f'Auto-detection completed with {device_info["confidence"]:.1%} confidence'
            }
            
        except Exception as e:
            self.logger.error(f"Error auto-detecting device info for camera {camera_id}: {e}")
            return {
                'success': False,
                'message': f'Auto-detection failed: {str(e)}',
                'device_info': None
            }
    
    async def _test_rtsp_connectivity(self, rtsp_url: str, timeout: int = 5) -> bool:
        """Test RTSP connectivity to a URL."""
        try:
            # Simple connectivity test - try to connect to RTSP port
            import socket
            from urllib.parse import urlparse
            
            parsed = urlparse(rtsp_url)
            host = parsed.hostname
            port = parsed.port or 554
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            return result == 0
            
        except Exception:
            return False
    
    async def _get_device_info_via_http(self, ip_address: str, manufacturer: str) -> Optional[Dict[str, Any]]:
        """Try to get device information via HTTP API."""
        try:
            import aiohttp
            
            # Common HTTP API endpoints for different manufacturers
            api_endpoints = {
                'Hikvision': f'http://{ip_address}/ISAPI/System/deviceInfo',
                'Dahua': f'http://{ip_address}/cgi-bin/magicBox.cgi?action=getDeviceType',
                'Axis': f'http://{ip_address}/axis-cgi/param.cgi?action=list&group=Properties.System',
                'Foscam': f'http://{ip_address}/cgi-bin/CGIProxy.fcgi?cmd=getDevInfo'
            }
            
            endpoint = api_endpoints.get(manufacturer)
            if not endpoint:
                return None
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(endpoint) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse response based on manufacturer
                        if manufacturer == 'Hikvision':
                            return self._parse_hikvision_device_info(content)
                        elif manufacturer == 'Dahua':
                            return self._parse_dahua_device_info(content)
                        elif manufacturer == 'Axis':
                            return self._parse_axis_device_info(content)
                        elif manufacturer == 'Foscam':
                            return self._parse_foscam_device_info(content)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Could not get device info via HTTP for {ip_address}: {e}")
            return None
    
    def _parse_hikvision_device_info(self, xml_content: str) -> Dict[str, Any]:
        """Parse Hikvision device info from XML response."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_content)
            
            info = {}
            
            # Extract model
            model_elem = root.find('.//model')
            if model_elem is not None:
                info['model'] = model_elem.text
            
            # Extract serial number
            serial_elem = root.find('.//serialNumber')
            if serial_elem is not None:
                info['serial_number'] = serial_elem.text
            
            return info
            
        except Exception:
            return {}
    
    def _parse_dahua_device_info(self, content: str) -> Dict[str, Any]:
        """Parse Dahua device info from response."""
        try:
            info = {}
            
            # Dahua responses are usually key=value pairs
            for line in content.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'type' in key or 'model' in key:
                        info['model'] = value
                    elif 'serial' in key:
                        info['serial_number'] = value
            
            return info
            
        except Exception:
            return {}
    
    def _parse_axis_device_info(self, content: str) -> Dict[str, Any]:
        """Parse Axis device info from response."""
        try:
            info = {}
            
            # Axis responses are parameter=value pairs
            for line in content.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if 'prodtype' in key or 'prodshortname' in key:
                        info['model'] = value
                    elif 'serialnumber' in key:
                        info['serial_number'] = value
            
            return info
            
        except Exception:
            return {}
    
    def _parse_foscam_device_info(self, content: str) -> Dict[str, Any]:
        """Parse Foscam device info from response."""
        try:
            info = {}
            
            # Foscam responses are usually XML or key-value pairs
            if '<' in content:  # XML response
                import xml.etree.ElementTree as ET
                root = ET.fromstring(content)
                
                model_elem = root.find('.//productName')
                if model_elem is not None:
                    info['model'] = model_elem.text
                
                serial_elem = root.find('.//serialNo')
                if serial_elem is not None:
                    info['serial_number'] = serial_elem.text
            
            return info
            
        except Exception:
            return {}
    
    async def bulk_auto_detect(self, camera_ids: List[int] = None) -> Dict[str, Any]:
        """Perform bulk auto-detection for multiple cameras."""
        try:
            # Get camera list from main database
            async with aiosqlite.connect("camera_data.db") as db:
                if camera_ids:
                    placeholders = ','.join('?' * len(camera_ids))
                    cursor = await db.execute(f"""
                        SELECT id, ip_address FROM cameras 
                        WHERE id IN ({placeholders}) AND ip_address IS NOT NULL
                    """, camera_ids)
                else:
                    cursor = await db.execute("""
                        SELECT id, ip_address FROM cameras 
                        WHERE ip_address IS NOT NULL
                    """)
                
                cameras = await cursor.fetchall()
            
            results = []
            successful_detections = 0
            
            for camera_id, ip_address in cameras:
                self.logger.info(f"Auto-detecting device info for camera {camera_id} ({ip_address})")
                
                result = await self.auto_detect_device_info(camera_id, ip_address)
                results.append({
                    'camera_id': camera_id,
                    'ip_address': ip_address,
                    'result': result
                })
                
                if result['success'] and result['device_info']['manufacturer']:
                    # Save detected info to database
                    device_info = result['device_info']
                    
                    async with aiosqlite.connect(self.device_db_path) as db:
                        await db.execute("""
                            INSERT OR REPLACE INTO device_info 
                            (camera_id, manufacturer, model, serial_number, rtsp_url, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            camera_id,
                            device_info.get('manufacturer'),
                            device_info.get('model'),
                            device_info.get('serial_number'),
                            device_info.get('rtsp_url'),
                            datetime.now().isoformat()
                        ))
                        await db.commit()
                    
                    successful_detections += 1
                
                # Small delay to avoid overwhelming devices
                await asyncio.sleep(1)
            
            return {
                'success': True,
                'total_cameras': len(cameras),
                'successful_detections': successful_detections,
                'results': results,
                'message': f'Bulk auto-detection completed. {successful_detections}/{len(cameras)} cameras detected successfully.'
            }
            
        except Exception as e:
            self.logger.error(f"Error in bulk auto-detection: {e}")
            return {
                'success': False,
                'message': f'Bulk auto-detection failed: {str(e)}',
                'results': []
            }
    
    async def get_device_statistics(self) -> Dict[str, Any]:
        """Get statistics about device information in the database."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                # Total devices
                cursor = await db.execute("SELECT COUNT(*) FROM device_info")
                total_devices = (await cursor.fetchone())[0]
                
                # Devices by manufacturer
                cursor = await db.execute("""
                    SELECT manufacturer, COUNT(*) 
                    FROM device_info 
                    WHERE manufacturer IS NOT NULL 
                    GROUP BY manufacturer 
                    ORDER BY COUNT(*) DESC
                """)
                by_manufacturer = dict(await cursor.fetchall())
                
                # Devices with complete info
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM device_info 
                    WHERE manufacturer IS NOT NULL 
                    AND model IS NOT NULL 
                    AND rtsp_url IS NOT NULL
                """)
                complete_info = (await cursor.fetchone())[0]
                
                # Devices with RTSP URLs
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM device_info 
                    WHERE rtsp_url IS NOT NULL AND rtsp_url != ''
                """)
                with_rtsp = (await cursor.fetchone())[0]
                
                return {
                    'success': True,
                    'statistics': {
                        'total_devices': total_devices,
                        'by_manufacturer': by_manufacturer,
                        'complete_info_count': complete_info,
                        'with_rtsp_count': with_rtsp,
                        'completion_rate': (complete_info / total_devices * 100) if total_devices > 0 else 0
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Error getting device statistics: {e}")
            return {
                'success': False,
                'message': f'Error getting statistics: {str(e)}'
            }