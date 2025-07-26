"""
Camera Viewer Component for RTSP Stream Display

This module provides functionality for viewing camera streams via RTSP protocol
in pop-out windows when cameras are clicked on the interactive map.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import aiosqlite


@dataclass
class CameraStreamInfo:
    """Camera stream information for RTSP viewing."""
    camera_id: int
    name: str
    custom_name: Optional[str]
    ip_address: str
    rtsp_url: Optional[str]
    manufacturer: Optional[str]
    model: Optional[str]
    serial_number: Optional[str]
    is_online: bool
    stream_port: int = 554
    username: Optional[str] = None
    password: Optional[str] = None
    
    def get_display_name(self) -> str:
        """Get display name for camera."""
        return self.custom_name.strip() if self.custom_name and self.custom_name.strip() else self.name
    
    def get_rtsp_url(self) -> str:
        """Generate RTSP URL for camera stream."""
        if self.rtsp_url:
            return self.rtsp_url
        
        # Generate default RTSP URL based on IP address
        base_url = f"rtsp://{self.ip_address}:{self.stream_port}"
        
        # Add authentication if available
        if self.username and self.password:
            base_url = f"rtsp://{self.username}:{self.password}@{self.ip_address}:{self.stream_port}"
        
        # Common RTSP paths for different manufacturers
        rtsp_paths = {
            'hikvision': '/Streaming/Channels/101',
            'dahua': '/cam/realmonitor?channel=1&subtype=0',
            'axis': '/axis-media/media.amp',
            'foscam': '/videoMain',
            'generic': '/stream1'
        }
        
        # Use manufacturer-specific path if known
        manufacturer_lower = (self.manufacturer or '').lower()
        for mfg, path in rtsp_paths.items():
            if mfg in manufacturer_lower:
                return base_url + path
        
        # Default path
        return base_url + rtsp_paths['generic']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'camera_id': self.camera_id,
            'name': self.name,
            'custom_name': self.custom_name,
            'display_name': self.get_display_name(),
            'ip_address': self.ip_address,
            'rtsp_url': self.get_rtsp_url(),
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'is_online': self.is_online,
            'stream_port': self.stream_port
        }


class CameraViewer:
    """Camera viewer for RTSP stream display and management."""
    
    def __init__(self, db_path: str = "camera_data.db", device_db_path: str = "device_info.db"):
        """Initialize camera viewer with database connections."""
        self.db_path = db_path
        self.device_db_path = device_db_path
        self.logger = logging.getLogger(__name__)
    
    async def initialize_device_database(self):
        """Initialize secondary database for device information."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                # Create device_info table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS device_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        camera_id INTEGER UNIQUE,
                        manufacturer TEXT,
                        model TEXT,
                        serial_number TEXT,
                        firmware_version TEXT,
                        rtsp_url TEXT,
                        rtsp_port INTEGER DEFAULT 554,
                        username TEXT,
                        password TEXT,
                        stream_quality TEXT DEFAULT 'main',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (camera_id) REFERENCES cameras (id)
                    )
                """)
                
                # Create manufacturer_info table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS manufacturer_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        manufacturer_name TEXT UNIQUE,
                        default_rtsp_path TEXT,
                        default_port INTEGER DEFAULT 554,
                        default_username TEXT,
                        default_password TEXT,
                        support_url TEXT,
                        documentation_url TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.commit()
                
                # Insert common manufacturer defaults
                await self._insert_default_manufacturers(db)
                
                self.logger.info("Device database initialized successfully")
                
        except Exception as e:
            self.logger.error(f"Error initializing device database: {e}")
            raise
    
    async def _insert_default_manufacturers(self, db: aiosqlite.Connection):
        """Insert default manufacturer information."""
        manufacturers = [
            ('Hikvision', '/Streaming/Channels/101', 554, 'admin', 'admin123', 'https://www.hikvision.com/support/', 'https://www.hikvision.com/en/support/documentation/'),
            ('Dahua', '/cam/realmonitor?channel=1&subtype=0', 554, 'admin', 'admin', 'https://www.dahuasecurity.com/support', 'https://www.dahuasecurity.com/support/documentation'),
            ('Axis', '/axis-media/media.amp', 554, 'root', 'pass', 'https://www.axis.com/support', 'https://www.axis.com/support/documentation'),
            ('Foscam', '/videoMain', 554, 'admin', '', 'https://www.foscam.com/support/', 'https://www.foscam.com/support/documentation/'),
            ('Reolink', '/h264Preview_01_main', 554, 'admin', '', 'https://reolink.com/support/', 'https://reolink.com/support/documentation/'),
            ('Ubiquiti', '/s0', 554, 'ubnt', 'ubnt', 'https://help.ui.com/', 'https://help.ui.com/'),
            ('Generic', '/stream1', 554, 'admin', 'admin', '', '')
        ]
        
        for mfg_data in manufacturers:
            try:
                await db.execute("""
                    INSERT OR IGNORE INTO manufacturer_info 
                    (manufacturer_name, default_rtsp_path, default_port, default_username, default_password, support_url, documentation_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, mfg_data)
            except Exception as e:
                self.logger.warning(f"Could not insert manufacturer {mfg_data[0]}: {e}")
    
    async def get_camera_stream_info(self, camera_id: int) -> Optional[CameraStreamInfo]:
        """Get camera stream information including device details."""
        try:
            # Get camera basic info
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, name, custom_name, ip_address
                    FROM cameras WHERE id = ?
                """, (camera_id,))
                
                camera_row = await cursor.fetchone()
                if not camera_row:
                    return None
            
            # Get device info from secondary database
            device_info = await self._get_device_info(camera_id)
            
            # Test connectivity
            is_online = await self._test_camera_connectivity(camera_row[3])  # ip_address
            
            return CameraStreamInfo(
                camera_id=camera_row[0],
                name=camera_row[1],
                custom_name=camera_row[2],
                ip_address=camera_row[3],
                rtsp_url=device_info.get('rtsp_url'),
                manufacturer=device_info.get('manufacturer'),
                model=device_info.get('model'),
                serial_number=device_info.get('serial_number'),
                is_online=is_online,
                stream_port=device_info.get('rtsp_port', 554),
                username=device_info.get('username'),
                password=device_info.get('password')
            )
            
        except Exception as e:
            self.logger.error(f"Error getting camera stream info for camera {camera_id}: {e}")
            return None
    
    async def _get_device_info(self, camera_id: int) -> Dict[str, Any]:
        """Get device information from secondary database."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                cursor = await db.execute("""
                    SELECT manufacturer, model, serial_number, firmware_version,
                           rtsp_url, rtsp_port, username, password, stream_quality
                    FROM device_info WHERE camera_id = ?
                """, (camera_id,))
                
                row = await cursor.fetchone()
                if row:
                    return {
                        'manufacturer': row[0],
                        'model': row[1],
                        'serial_number': row[2],
                        'firmware_version': row[3],
                        'rtsp_url': row[4],
                        'rtsp_port': row[5] or 554,
                        'username': row[6],
                        'password': row[7],
                        'stream_quality': row[8] or 'main'
                    }
                
                return {}
                
        except Exception as e:
            self.logger.warning(f"Could not get device info for camera {camera_id}: {e}")
            return {}
    
    async def _test_camera_connectivity(self, ip_address: str) -> bool:
        """Test camera connectivity via ping."""
        try:
            from ping3 import ping
            result = ping(ip_address, timeout=2)
            return result is not None and result > 0
        except Exception:
            return False
    
    async def add_device_info(self, camera_id: int, manufacturer: str = None, model: str = None,
                             serial_number: str = None, rtsp_url: str = None,
                             username: str = None, password: str = None) -> Dict[str, Any]:
        """Add or update device information for a camera."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                # Check if device info already exists
                cursor = await db.execute(
                    "SELECT id FROM device_info WHERE camera_id = ?", 
                    (camera_id,)
                )
                existing = await cursor.fetchone()
                
                now = datetime.now().isoformat()
                
                if existing:
                    # Update existing record
                    await db.execute("""
                        UPDATE device_info SET
                            manufacturer = COALESCE(?, manufacturer),
                            model = COALESCE(?, model),
                            serial_number = COALESCE(?, serial_number),
                            rtsp_url = COALESCE(?, rtsp_url),
                            username = COALESCE(?, username),
                            password = COALESCE(?, password),
                            updated_at = ?
                        WHERE camera_id = ?
                    """, (manufacturer, model, serial_number, rtsp_url, username, password, now, camera_id))
                else:
                    # Insert new record
                    await db.execute("""
                        INSERT INTO device_info 
                        (camera_id, manufacturer, model, serial_number, rtsp_url, username, password, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (camera_id, manufacturer, model, serial_number, rtsp_url, username, password, now, now))
                
                await db.commit()
                
                return {
                    'success': True,
                    'message': f'Device information updated for camera {camera_id}'
                }
                
        except Exception as e:
            self.logger.error(f"Error adding device info for camera {camera_id}: {e}")
            return {
                'success': False,
                'message': f'Error updating device information: {str(e)}'
            }
    
    async def get_all_manufacturers(self) -> List[Dict[str, Any]]:
        """Get all manufacturer information."""
        try:
            async with aiosqlite.connect(self.device_db_path) as db:
                cursor = await db.execute("""
                    SELECT manufacturer_name, default_rtsp_path, default_port,
                           default_username, default_password, support_url, documentation_url
                    FROM manufacturer_info
                    ORDER BY manufacturer_name
                """)
                
                rows = await cursor.fetchall()
                manufacturers = []
                
                for row in rows:
                    manufacturers.append({
                        'name': row[0],
                        'default_rtsp_path': row[1],
                        'default_port': row[2],
                        'default_username': row[3],
                        'default_password': row[4],
                        'support_url': row[5],
                        'documentation_url': row[6]
                    })
                
                return manufacturers
                
        except Exception as e:
            self.logger.error(f"Error getting manufacturers: {e}")
            return []
    
    def generate_camera_viewer_html(self, stream_info: CameraStreamInfo) -> str:
        """Generate HTML for camera viewer pop-out window."""
        rtsp_url = stream_info.get_rtsp_url()
        display_name = stream_info.get_display_name()
        
        # Generate device info section
        device_info_html = ""
        if stream_info.manufacturer or stream_info.model or stream_info.serial_number:
            device_info_html = f"""
            <div class="device-info">
                <h4>📱 Device Information</h4>
                <table class="device-table">
                    {f'<tr><td><strong>Manufacturer:</strong></td><td>{stream_info.manufacturer}</td></tr>' if stream_info.manufacturer else ''}
                    {f'<tr><td><strong>Model:</strong></td><td>{stream_info.model}</td></tr>' if stream_info.model else ''}
                    {f'<tr><td><strong>Serial Number:</strong></td><td>{stream_info.serial_number}</td></tr>' if stream_info.serial_number else ''}
                </table>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>📹 {display_name} - Camera View</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: #333;
                }}
                
                .camera-viewer {{
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                    overflow: hidden;
                    max-width: 800px;
                    margin: 0 auto;
                }}
                
                .header {{
                    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                    color: white;
                    padding: 15px 20px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                
                .header h2 {{
                    margin: 0;
                    font-size: 1.4em;
                }}
                
                .status {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                
                .status-indicator {{
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: {'#4CAF50' if stream_info.is_online else '#f44336'};
                    animation: pulse 2s infinite;
                }}
                
                @keyframes pulse {{
                    0% {{ opacity: 1; }}
                    50% {{ opacity: 0.5; }}
                    100% {{ opacity: 1; }}
                }}
                
                .video-container {{
                    position: relative;
                    background: #000;
                    min-height: 400px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                
                .video-player {{
                    width: 100%;
                    height: 400px;
                    background: #000;
                }}
                
                .stream-error {{
                    color: #fff;
                    text-align: center;
                    padding: 40px;
                }}
                
                .controls {{
                    padding: 15px 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #dee2e6;
                }}
                
                .control-group {{
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    margin-bottom: 10px;
                }}
                
                .btn {{
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    transition: all 0.3s ease;
                }}
                
                .btn-primary {{
                    background: #007bff;
                    color: white;
                }}
                
                .btn-primary:hover {{
                    background: #0056b3;
                }}
                
                .btn-secondary {{
                    background: #6c757d;
                    color: white;
                }}
                
                .btn-secondary:hover {{
                    background: #545b62;
                }}
                
                .device-info {{
                    padding: 15px 20px;
                    background: #f8f9fa;
                    border-top: 1px solid #dee2e6;
                }}
                
                .device-info h4 {{
                    margin: 0 0 10px 0;
                    color: #495057;
                }}
                
                .device-table {{
                    width: 100%;
                    font-size: 13px;
                }}
                
                .device-table td {{
                    padding: 4px 8px;
                    border-bottom: 1px solid #dee2e6;
                }}
                
                .stream-info {{
                    font-size: 12px;
                    color: #6c757d;
                    margin-top: 10px;
                }}
                
                .loading {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    font-size: 16px;
                }}
                
                .spinner {{
                    border: 3px solid rgba(255,255,255,0.3);
                    border-top: 3px solid white;
                    border-radius: 50%;
                    width: 30px;
                    height: 30px;
                    animation: spin 1s linear infinite;
                    margin-right: 15px;
                }}
                
                @keyframes spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
        </head>
        <body>
            <div class="camera-viewer">
                <div class="header">
                    <h2>📹 {display_name}</h2>
                    <div class="status">
                        <div class="status-indicator"></div>
                        <span>{'Online' if stream_info.is_online else 'Offline'}</span>
                    </div>
                </div>
                
                <div class="video-container">
                    <div id="video-player" class="video-player">
                        <div class="loading">
                            <div class="spinner"></div>
                            Loading camera stream...
                        </div>
                    </div>
                </div>
                
                <div class="controls">
                    <div class="control-group">
                        <button class="btn btn-primary" onclick="startStream()">▶️ Start Stream</button>
                        <button class="btn btn-secondary" onclick="stopStream()">⏹️ Stop Stream</button>
                        <button class="btn btn-secondary" onclick="refreshStream()">🔄 Refresh</button>
                        <button class="btn btn-secondary" onclick="toggleFullscreen()">⛶ Fullscreen</button>
                    </div>
                    
                    <div class="stream-info">
                        <strong>Stream URL:</strong> <code>{rtsp_url}</code><br>
                        <strong>IP Address:</strong> {stream_info.ip_address}<br>
                        <strong>Port:</strong> {stream_info.stream_port}
                    </div>
                </div>
                
                {device_info_html}
            </div>
            
            <script>
                let streamActive = false;
                let videoElement = null;
                
                function initializeStream() {{
                    const container = document.getElementById('video-player');
                    
                    // Try to use HTML5 video with HLS.js for RTSP streaming
                    if ('{rtsp_url}'.startsWith('rtsp://')) {{
                        // For RTSP streams, we need a proxy or conversion service
                        showStreamProxy();
                    }} else {{
                        // For HTTP streams, use direct video element
                        createVideoElement();
                    }}
                }}
                
                function showStreamProxy() {{
                    const container = document.getElementById('video-player');
                    container.innerHTML = `
                        <div class="stream-error">
                            <h3>📡 RTSP Stream Proxy</h3>
                            <p>This camera uses RTSP protocol. Stream will be proxied through the server.</p>
                            <p><strong>Stream URL:</strong> {rtsp_url}</p>
                            <button class="btn btn-primary" onclick="requestProxyStream()">🔗 Connect via Proxy</button>
                            <div style="margin-top: 20px; font-size: 12px; color: #ccc;">
                                <p>💡 The proxy server will handle RTSP to HTTP conversion to reduce bandwidth usage.</p>
                            </div>
                        </div>
                    `;
                }}
                
                function requestProxyStream() {{
                    const container = document.getElementById('video-player');
                    container.innerHTML = `
                        <div class="loading">
                            <div class="spinner"></div>
                            Connecting to proxy server...
                        </div>
                    `;
                    
                    // Make request to proxy server
                    fetch('/api/camera/stream/{stream_info.camera_id}', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            'rtsp_url': '{rtsp_url}',
                            'camera_id': {stream_info.camera_id}
                        }})
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success) {{
                            createProxyVideoElement(data.proxy_url);
                        }} else {{
                            showStreamError(data.message || 'Failed to connect to proxy');
                        }}
                    }})
                    .catch(error => {{
                        showStreamError('Connection error: ' + error.message);
                    }});
                }}
                
                function createProxyVideoElement(proxyUrl) {{
                    const container = document.getElementById('video-player');
                    videoElement = document.createElement('video');
                    videoElement.controls = true;
                    videoElement.autoplay = true;
                    videoElement.style.width = '100%';
                    videoElement.style.height = '100%';
                    videoElement.src = proxyUrl;
                    
                    videoElement.onerror = function() {{
                        showStreamError('Failed to load video stream');
                    }};
                    
                    videoElement.onloadstart = function() {{
                        streamActive = true;
                    }};
                    
                    container.innerHTML = '';
                    container.appendChild(videoElement);
                }}
                
                function createVideoElement() {{
                    const container = document.getElementById('video-player');
                    videoElement = document.createElement('video');
                    videoElement.controls = true;
                    videoElement.autoplay = true;
                    videoElement.style.width = '100%';
                    videoElement.style.height = '100%';
                    
                    // Try to load the stream
                    videoElement.src = '{rtsp_url}';
                    videoElement.onerror = function() {{
                        showStreamError('Unable to load camera stream. RTSP may require proxy.');
                    }};
                    
                    container.innerHTML = '';
                    container.appendChild(videoElement);
                }}
                
                function showStreamError(message) {{
                    const container = document.getElementById('video-player');
                    container.innerHTML = `
                        <div class="stream-error">
                            <h3>⚠️ Stream Error</h3>
                            <p>${{message}}</p>
                            <button class="btn btn-primary" onclick="initializeStream()">🔄 Retry</button>
                        </div>
                    `;
                }}
                
                function startStream() {{
                    if (videoElement) {{
                        videoElement.play();
                        streamActive = true;
                    }} else {{
                        initializeStream();
                    }}
                }}
                
                function stopStream() {{
                    if (videoElement) {{
                        videoElement.pause();
                        streamActive = false;
                    }}
                }}
                
                function refreshStream() {{
                    initializeStream();
                }}
                
                function toggleFullscreen() {{
                    if (videoElement) {{
                        if (videoElement.requestFullscreen) {{
                            videoElement.requestFullscreen();
                        }} else if (videoElement.webkitRequestFullscreen) {{
                            videoElement.webkitRequestFullscreen();
                        }} else if (videoElement.msRequestFullscreen) {{
                            videoElement.msRequestFullscreen();
                        }}
                    }}
                }}
                
                // Initialize when page loads
                window.onload = function() {{
                    initializeStream();
                }};
                
                // Cleanup when window closes
                window.onbeforeunload = function() {{
                    if (streamActive && videoElement) {{
                        videoElement.pause();
                        videoElement.src = '';
                    }}
                }};
            </script>
        </body>
        </html>
        """
        
        return html_content
    
    async def get_camera_viewer_data(self, camera_id: int) -> Dict[str, Any]:
        """Get camera viewer data for API response."""
        stream_info = await self.get_camera_stream_info(camera_id)
        
        if not stream_info:
            return {
                'success': False,
                'message': f'Camera {camera_id} not found'
            }
        
        return {
            'success': True,
            'camera_info': stream_info.to_dict(),
            'viewer_html': self.generate_camera_viewer_html(stream_info)
        }