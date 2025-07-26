"""
Camera API Handler for Web Interface

This module provides API endpoints for camera viewer functionality,
RTSP stream management, and device information handling.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from aiohttp import web, ClientSession
import aiosqlite
from datetime import datetime

from .camera_viewer import CameraViewer
from .rtsp_proxy import get_proxy_instance


class CameraAPI:
    """API handler for camera-related endpoints."""
    
    def __init__(self, db_path: str = "camera_data.db", device_db_path: str = "device_info.db"):
        """Initialize camera API handler."""
        self.db_path = db_path
        self.device_db_path = device_db_path
        self.camera_viewer = CameraViewer(db_path, device_db_path)
        self.proxy = get_proxy_instance()
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize the camera API."""
        try:
            await self.camera_viewer.initialize_device_database()
            self.logger.info("Camera API initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing camera API: {e}")
            raise
    
    async def get_camera_viewer(self, request):
        """API endpoint to get camera viewer HTML."""
        try:
            camera_id = int(request.match_info['camera_id'])
            
            # Get camera viewer data
            result = await self.camera_viewer.get_camera_viewer_data(camera_id)
            
            if result['success']:
                return web.json_response(result)
            else:
                return web.json_response(result, status=404)
                
        except ValueError:
            return web.json_response({
                'success': False,
                'message': 'Invalid camera ID'
            }, status=400)
        except Exception as e:
            self.logger.error(f"Error in get_camera_viewer: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def create_stream_proxy(self, request):
        """API endpoint to create RTSP stream proxy."""
        try:
            data = await request.json()
            camera_id = data.get('camera_id')
            rtsp_url = data.get('rtsp_url')
            
            if not camera_id or not rtsp_url:
                return web.json_response({
                    'success': False,
                    'message': 'camera_id and rtsp_url are required'
                }, status=400)
            
            # Create proxy session
            result = await self.proxy.create_proxy_session(camera_id, rtsp_url)
            
            status = 200 if result['success'] else 400
            return web.json_response(result, status=status)
            
        except Exception as e:
            self.logger.error(f"Error creating stream proxy: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def stop_stream_proxy(self, request):
        """API endpoint to stop RTSP stream proxy."""
        try:
            session_id = request.match_info['session_id']
            
            result = await self.proxy.stop_proxy_session(session_id)
            
            status = 200 if result['success'] else 400
            return web.json_response(result, status=status)
            
        except Exception as e:
            self.logger.error(f"Error stopping stream proxy: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def get_camera_info(self, request):
        """API endpoint to get camera information including device details."""
        try:
            camera_id = int(request.match_info['camera_id'])
            
            # Get camera stream info
            stream_info = await self.camera_viewer.get_camera_stream_info(camera_id)
            
            if stream_info:
                return web.json_response({
                    'success': True,
                    'camera': stream_info.to_dict()
                })
            else:
                return web.json_response({
                    'success': False,
                    'message': 'Camera not found'
                }, status=404)
                
        except ValueError:
            return web.json_response({
                'success': False,
                'message': 'Invalid camera ID'
            }, status=400)
        except Exception as e:
            self.logger.error(f"Error getting camera info: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def update_device_info(self, request):
        """API endpoint to update device information for a camera."""
        try:
            camera_id = int(request.match_info['camera_id'])
            data = await request.json()
            
            # Extract device information
            manufacturer = data.get('manufacturer')
            model = data.get('model')
            serial_number = data.get('serial_number')
            rtsp_url = data.get('rtsp_url')
            username = data.get('username')
            password = data.get('password')
            
            # Update device info
            result = await self.camera_viewer.add_device_info(
                camera_id, manufacturer, model, serial_number, 
                rtsp_url, username, password
            )
            
            status = 200 if result['success'] else 400
            return web.json_response(result, status=status)
            
        except ValueError:
            return web.json_response({
                'success': False,
                'message': 'Invalid camera ID'
            }, status=400)
        except Exception as e:
            self.logger.error(f"Error updating device info: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def get_manufacturers(self, request):
        """API endpoint to get all manufacturer information."""
        try:
            manufacturers = await self.camera_viewer.get_all_manufacturers()
            
            return web.json_response({
                'success': True,
                'manufacturers': manufacturers,
                'count': len(manufacturers)
            })
            
        except Exception as e:
            self.logger.error(f"Error getting manufacturers: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def get_proxy_sessions(self, request):
        """API endpoint to get active proxy sessions."""
        try:
            sessions = await self.proxy.list_active_sessions()
            
            return web.json_response({
                'success': True,
                'sessions': sessions,
                'count': len(sessions)
            })
            
        except Exception as e:
            self.logger.error(f"Error getting proxy sessions: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    async def test_camera_stream(self, request):
        """API endpoint to test camera stream connectivity."""
        try:
            data = await request.json()
            rtsp_url = data.get('rtsp_url')
            
            if not rtsp_url:
                return web.json_response({
                    'success': False,
                    'message': 'rtsp_url is required'
                }, status=400)
            
            # Test stream connectivity (simplified test)
            try:
                # Extract IP from RTSP URL for ping test
                import re
                ip_match = re.search(r'rtsp://(?:[^:]+:[^@]+@)?([^:/]+)', rtsp_url)
                if ip_match:
                    ip_address = ip_match.group(1)
                    
                    # Test ping connectivity
                    from ping3 import ping
                    result = ping(ip_address, timeout=3)
                    
                    if result is not None and result > 0:
                        return web.json_response({
                            'success': True,
                            'message': 'Camera appears to be reachable',
                            'ping_time': result,
                            'ip_address': ip_address
                        })
                    else:
                        return web.json_response({
                            'success': False,
                            'message': 'Camera is not reachable via ping',
                            'ip_address': ip_address
                        })
                else:
                    return web.json_response({
                        'success': False,
                        'message': 'Could not extract IP address from RTSP URL'
                    })
                    
            except Exception as test_error:
                return web.json_response({
                    'success': False,
                    'message': f'Stream test failed: {str(test_error)}'
                })
                
        except Exception as e:
            self.logger.error(f"Error testing camera stream: {e}")
            return web.json_response({
                'success': False,
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    def create_routes(self) -> web.Application:
        """Create web application with camera API routes."""
        app = web.Application()
        
        # Camera viewer routes
        app.router.add_get('/api/camera/viewer/{camera_id}', self.get_camera_viewer)
        app.router.add_get('/api/camera/info/{camera_id}', self.get_camera_info)
        app.router.add_put('/api/camera/device/{camera_id}', self.update_device_info)
        
        # Stream proxy routes
        app.router.add_post('/api/camera/stream/{camera_id}', self.create_stream_proxy)
        app.router.add_delete('/api/camera/stream/{session_id}', self.stop_stream_proxy)
        app.router.add_get('/api/camera/sessions', self.get_proxy_sessions)
        
        # Utility routes
        app.router.add_get('/api/camera/manufacturers', self.get_manufacturers)
        app.router.add_post('/api/camera/test-stream', self.test_camera_stream)
        
        return app


# Global API instance
_api_instance = None

def get_camera_api() -> CameraAPI:
    """Get global camera API instance."""
    global _api_instance
    if _api_instance is None:
        _api_instance = CameraAPI()
    return _api_instance

async def initialize_camera_api():
    """Initialize camera API."""
    api = get_camera_api()
    await api.initialize()
    return api