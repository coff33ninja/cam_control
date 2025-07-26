"""
RTSP Proxy Server for Camera Stream Management

This module provides RTSP to HTTP proxy functionality to reduce server bandwidth
usage and allow remote viewing without interrupting server resources.
"""

import asyncio
import logging
import json
import subprocess
import tempfile
import os
import signal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import aiohttp
from aiohttp import web
import threading
import time


@dataclass
class ProxySession:
    """Represents an active proxy session."""
    session_id: str
    camera_id: int
    rtsp_url: str
    proxy_url: str
    process: Optional[subprocess.Popen] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    client_count: int = 0
    is_active: bool = True
    
    def update_access(self):
        """Update last accessed time."""
        self.last_accessed = datetime.now()
    
    def add_client(self):
        """Add a client to this session."""
        self.client_count += 1
        self.update_access()
    
    def remove_client(self):
        """Remove a client from this session."""
        self.client_count = max(0, self.client_count - 1)
        self.update_access()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if session has expired."""
        return (datetime.now() - self.last_accessed).total_seconds() > (timeout_minutes * 60)
    
    def stop(self):
        """Stop the proxy session."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                logging.warning(f"Error stopping proxy process: {e}")
        
        self.is_active = False


class RTSPProxy:
    """RTSP to HTTP proxy server for camera streams."""
    
    def __init__(self, base_port: int = 8080, max_sessions: int = 50):
        """Initialize RTSP proxy server."""
        self.base_port = base_port
        self.max_sessions = max_sessions
        self.sessions: Dict[str, ProxySession] = {}
        self.port_pool = set(range(base_port, base_port + max_sessions))
        self.used_ports = set()
        self.logger = logging.getLogger(__name__)
        self.cleanup_task = None
        self.app = None
        
        # Check for required dependencies
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if required dependencies are available."""
        try:
            # Check for FFmpeg
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise FileNotFoundError("FFmpeg not found")
            self.logger.info("FFmpeg found and available")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.logger.warning("FFmpeg not found. RTSP proxy functionality will be limited.")
    
    def _get_available_port(self) -> Optional[int]:
        """Get an available port for proxy session."""
        available_ports = self.port_pool - self.used_ports
        if available_ports:
            port = min(available_ports)
            self.used_ports.add(port)
            return port
        return None
    
    def _release_port(self, port: int):
        """Release a port back to the pool."""
        self.used_ports.discard(port)
    
    async def create_proxy_session(self, camera_id: int, rtsp_url: str, 
                                 session_id: str = None) -> Dict[str, Any]:
        """Create a new proxy session for RTSP stream."""
        try:
            # Check if we already have an active session for this camera
            existing_session = None
            for session in self.sessions.values():
                if session.camera_id == camera_id and session.is_active:
                    existing_session = session
                    break
            
            if existing_session:
                existing_session.add_client()
                return {
                    'success': True,
                    'session_id': existing_session.session_id,
                    'proxy_url': existing_session.proxy_url,
                    'message': 'Using existing proxy session'
                }
            
            # Check session limit
            if len(self.sessions) >= self.max_sessions:
                await self._cleanup_expired_sessions()
                if len(self.sessions) >= self.max_sessions:
                    return {
                        'success': False,
                        'message': 'Maximum proxy sessions reached'
                    }
            
            # Generate session ID if not provided
            if not session_id:
                session_id = f"proxy_{camera_id}_{int(time.time())}"
            
            # Get available port
            port = self._get_available_port()
            if not port:
                return {
                    'success': False,
                    'message': 'No available ports for proxy session'
                }
            
            # Create proxy URL
            proxy_url = f"http://localhost:{port}/stream.m3u8"
            
            # Start FFmpeg process for RTSP to HLS conversion
            process = await self._start_ffmpeg_process(rtsp_url, port)
            
            if not process:
                self._release_port(port)
                return {
                    'success': False,
                    'message': 'Failed to start proxy process'
                }
            
            # Create session
            session = ProxySession(
                session_id=session_id,
                camera_id=camera_id,
                rtsp_url=rtsp_url,
                proxy_url=proxy_url,
                process=process
            )
            session.add_client()
            
            self.sessions[session_id] = session
            
            self.logger.info(f"Created proxy session {session_id} for camera {camera_id}")
            
            return {
                'success': True,
                'session_id': session_id,
                'proxy_url': proxy_url,
                'message': 'Proxy session created successfully'
            }
            
        except Exception as e:
            self.logger.error(f"Error creating proxy session: {e}")
            return {
                'success': False,
                'message': f'Error creating proxy session: {str(e)}'
            }
    
    async def _start_ffmpeg_process(self, rtsp_url: str, port: int) -> Optional[subprocess.Popen]:
        """Start FFmpeg process for RTSP to HLS conversion."""
        try:
            # Create temporary directory for HLS segments
            temp_dir = tempfile.mkdtemp(prefix=f"rtsp_proxy_{port}_")
            
            # FFmpeg command for RTSP to HLS conversion
            cmd = [
                'ffmpeg',
                '-i', rtsp_url,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-f', 'hls',
                '-hls_time', '2',
                '-hls_list_size', '3',
                '-hls_flags', 'delete_segments',
                '-hls_segment_filename', f'{temp_dir}/segment_%03d.ts',
                f'{temp_dir}/stream.m3u8'
            ]
            
            # Start FFmpeg process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            # Wait a moment to check if process started successfully
            await asyncio.sleep(2)
            
            if process.poll() is not None:
                # Process died
                self.logger.error(f"FFmpeg process died immediately for {rtsp_url}")
                return None
            
            # Start HTTP server for HLS files
            await self._start_hls_server(temp_dir, port)
            
            return process
            
        except Exception as e:
            self.logger.error(f"Error starting FFmpeg process: {e}")
            return None
    
    async def _start_hls_server(self, temp_dir: str, port: int):
        """Start HTTP server to serve HLS files."""
        try:
            # Simple HTTP server for HLS files
            async def serve_hls(request):
                filename = request.match_info.get('filename', 'stream.m3u8')
                file_path = os.path.join(temp_dir, filename)
                
                if not os.path.exists(file_path):
                    return web.Response(status=404, text='File not found')
                
                # Determine content type
                if filename.endswith('.m3u8'):
                    content_type = 'application/vnd.apple.mpegurl'
                elif filename.endswith('.ts'):
                    content_type = 'video/mp2t'
                else:
                    content_type = 'application/octet-stream'
                
                # Add CORS headers
                headers = {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Cache-Control': 'no-cache'
                }
                
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    return web.Response(
                        body=content,
                        content_type=content_type,
                        headers=headers
                    )
                except Exception as e:
                    self.logger.error(f"Error serving file {filename}: {e}")
                    return web.Response(status=500, text='Server error')
            
            # Create web application for this port
            app = web.Application()
            app.router.add_get('/{filename}', serve_hls)
            app.router.add_get('/', serve_hls)  # Default to stream.m3u8
            
            # Start server in background
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, 'localhost', port)
            await site.start()
            
            self.logger.info(f"HLS server started on port {port}")
            
        except Exception as e:
            self.logger.error(f"Error starting HLS server on port {port}: {e}")
    
    async def stop_proxy_session(self, session_id: str, client_disconnect: bool = True) -> Dict[str, Any]:
        """Stop a proxy session."""
        try:
            session = self.sessions.get(session_id)
            if not session:
                return {
                    'success': False,
                    'message': 'Session not found'
                }
            
            if client_disconnect:
                session.remove_client()
            
            # Only stop session if no clients are connected
            if session.client_count <= 0:
                session.stop()
                
                # Release port
                port = int(session.proxy_url.split(':')[-1].split('/')[0])
                self._release_port(port)
                
                # Remove from sessions
                del self.sessions[session_id]
                
                self.logger.info(f"Stopped proxy session {session_id}")
                
                return {
                    'success': True,
                    'message': 'Proxy session stopped'
                }
            else:
                return {
                    'success': True,
                    'message': f'Client disconnected. {session.client_count} clients remaining'
                }
                
        except Exception as e:
            self.logger.error(f"Error stopping proxy session {session_id}: {e}")
            return {
                'success': False,
                'message': f'Error stopping session: {str(e)}'
            }
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a proxy session."""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        return {
            'session_id': session.session_id,
            'camera_id': session.camera_id,
            'rtsp_url': session.rtsp_url,
            'proxy_url': session.proxy_url,
            'client_count': session.client_count,
            'is_active': session.is_active,
            'created_at': session.created_at.isoformat(),
            'last_accessed': session.last_accessed.isoformat()
        }
    
    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active proxy sessions."""
        sessions = []
        for session in self.sessions.values():
            if session.is_active:
                sessions.append(await self.get_session_info(session.session_id))
        return sessions
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired proxy sessions."""
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired() or not session.is_active:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self.stop_proxy_session(session_id, client_disconnect=False)
        
        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    async def start_cleanup_task(self):
        """Start background task for session cleanup."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # Check every 5 minutes
                    await self._cleanup_expired_sessions()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in cleanup task: {e}")
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def shutdown(self):
        """Shutdown proxy server and clean up all sessions."""
        self.logger.info("Shutting down RTSP proxy server...")
        
        # Stop cleanup task
        await self.stop_cleanup_task()
        
        # Stop all active sessions
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.stop_proxy_session(session_id, client_disconnect=False)
        
        self.logger.info("RTSP proxy server shutdown complete")
    
    def create_api_routes(self) -> web.Application:
        """Create API routes for proxy management."""
        app = web.Application()
        
        async def create_session(request):
            """API endpoint to create proxy session."""
            try:
                data = await request.json()
                camera_id = data.get('camera_id')
                rtsp_url = data.get('rtsp_url')
                
                if not camera_id or not rtsp_url:
                    return web.json_response({
                        'success': False,
                        'message': 'camera_id and rtsp_url are required'
                    }, status=400)
                
                result = await self.create_proxy_session(camera_id, rtsp_url)
                status = 200 if result['success'] else 400
                
                return web.json_response(result, status=status)
                
            except Exception as e:
                return web.json_response({
                    'success': False,
                    'message': f'Server error: {str(e)}'
                }, status=500)
        
        async def stop_session(request):
            """API endpoint to stop proxy session."""
            try:
                session_id = request.match_info['session_id']
                result = await self.stop_proxy_session(session_id)
                status = 200 if result['success'] else 400
                
                return web.json_response(result, status=status)
                
            except Exception as e:
                return web.json_response({
                    'success': False,
                    'message': f'Server error: {str(e)}'
                }, status=500)
        
        async def get_session(request):
            """API endpoint to get session info."""
            try:
                session_id = request.match_info['session_id']
                info = await self.get_session_info(session_id)
                
                if info:
                    return web.json_response({
                        'success': True,
                        'session': info
                    })
                else:
                    return web.json_response({
                        'success': False,
                        'message': 'Session not found'
                    }, status=404)
                    
            except Exception as e:
                return web.json_response({
                    'success': False,
                    'message': f'Server error: {str(e)}'
                }, status=500)
        
        async def list_sessions(request):
            """API endpoint to list active sessions."""
            try:
                sessions = await self.list_active_sessions()
                return web.json_response({
                    'success': True,
                    'sessions': sessions,
                    'count': len(sessions)
                })
                
            except Exception as e:
                return web.json_response({
                    'success': False,
                    'message': f'Server error: {str(e)}'
                }, status=500)
        
        # Add routes
        app.router.add_post('/api/proxy/create', create_session)
        app.router.add_delete('/api/proxy/session/{session_id}', stop_session)
        app.router.add_get('/api/proxy/session/{session_id}', get_session)
        app.router.add_get('/api/proxy/sessions', list_sessions)
        
        return app


# Global proxy instance
_proxy_instance = None

def get_proxy_instance() -> RTSPProxy:
    """Get global proxy instance."""
    global _proxy_instance
    if _proxy_instance is None:
        _proxy_instance = RTSPProxy()
    return _proxy_instance

async def initialize_proxy():
    """Initialize proxy server."""
    proxy = get_proxy_instance()
    await proxy.start_cleanup_task()
    return proxy

async def shutdown_proxy():
    """Shutdown proxy server."""
    global _proxy_instance
    if _proxy_instance:
        await _proxy_instance.shutdown()
        _proxy_instance = None