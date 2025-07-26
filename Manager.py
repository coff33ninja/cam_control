import aiosqlite
import pandas as pd
import gradio as gr
import os
import asyncio
import re
import json
from datetime import datetime
from ping3 import ping
import folium
from folium.plugins import MarkerCluster
import io
import shutil

# Import from organized modules
from src.connectivity_monitor import ConnectivityMonitor
from src.coverage_calculator import CoverageCalculator
from src.interactive_map_manager import InteractiveMapManager
from src.map_configuration_manager import MapConfigurationManager
from src.enhanced_camera_models import EnhancedCamera, MapConfiguration
from src.dvr_manager import DVRManager, DVR, create_dvr_from_form_data, get_dvr_dropdown_choices
from src.error_handling import (
    ComprehensiveErrorHandler, CoordinateValidator, ValidationError,
    OperationResult, ErrorCategory, get_error_handler
)

# Database setup
DB_NAME = "camera_data.db"
BACKUP_DIR = "backups"

# Custom CSS for modern UI
CUSTOM_CSS = """
.dashboard-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 20px;
    text-align: center;
}

.stats-card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    margin: 10px;
    text-align: center;
}

.action-button {
    background: #4CAF50;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 6px;
    cursor: pointer;
    margin: 5px;
    font-size: 14px;
}

.action-button:hover {
    background: #45a049;
}

.delete-button {
    background: #f44336;
}

.delete-button:hover {
    background: #da190b;
}

.search-container {
    background: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}

.modal-content {
    background: white;
    padding: 20px;
    border-radius: 10px;
    max-width: 600px;
    margin: auto;
}
"""

async def init_db():
    """Initialize the SQLite database with cameras, dvrs, action_log, and map_configurations tables."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Cameras table with coverage parameters
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                name TEXT NOT NULL,
                mac_address TEXT NOT NULL UNIQUE,
                ip_address TEXT NOT NULL UNIQUE,
                locational_group TEXT,
                date_installed TEXT NOT NULL,
                dvr_id INTEGER,
                latitude REAL,
                longitude REAL,
                has_memory_card BOOLEAN NOT NULL,
                memory_card_last_reset TEXT,
                coverage_radius REAL DEFAULT 50.0,
                field_of_view_angle REAL DEFAULT 360.0,
                coverage_direction REAL DEFAULT 0.0,
                FOREIGN KEY (dvr_id) REFERENCES dvrs(id)
            )
        """)
        # DVRs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dvrs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dvr_type TEXT NOT NULL,
                location TEXT NOT NULL,
                ip_address TEXT NOT NULL UNIQUE,
                mac_address TEXT NOT NULL UNIQUE,
                storage_capacity TEXT,
                date_installed TEXT NOT NULL,
                latitude REAL,
                longitude REAL
            )
        """)
        # Action log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                details TEXT
            )
        """)
        # Map configurations table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS map_configurations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                configuration_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()
        
        # Run migration to add coverage columns to existing cameras
        await migrate_camera_coverage_columns(db)

async def migrate_camera_coverage_columns(db):
    """Add coverage columns to existing cameras table if they don't exist."""
    try:
        # Check if coverage columns exist
        cursor = await db.execute("PRAGMA table_info(cameras)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Add coverage_radius column if it doesn't exist
        if 'coverage_radius' not in column_names:
            await db.execute("ALTER TABLE cameras ADD COLUMN coverage_radius REAL DEFAULT 50.0")
        
        # Add field_of_view_angle column if it doesn't exist
        if 'field_of_view_angle' not in column_names:
            await db.execute("ALTER TABLE cameras ADD COLUMN field_of_view_angle REAL DEFAULT 360.0")
        
        # Add coverage_direction column if it doesn't exist
        if 'coverage_direction' not in column_names:
            await db.execute("ALTER TABLE cameras ADD COLUMN coverage_direction REAL DEFAULT 0.0")
        
        await db.commit()
    except Exception as e:
        print(f"Migration error: {e}")

# Validation functions - direct imports from enhanced models
validate_mac = EnhancedCamera.validate_mac_address
validate_ip = EnhancedCamera.validate_ip_address
validate_date = EnhancedCamera.validate_date
validate_coordinates = EnhancedCamera.validate_coordinates
validate_coverage_parameters = EnhancedCamera.validate_coverage_parameters

# Core classes are imported from organized src/ modules

# Database statistics
async def get_dashboard_stats():
    """Get dashboard statistics."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Camera count
            cursor = await db.execute("SELECT COUNT(*) FROM cameras")
            camera_count = (await cursor.fetchone())[0]
            
            # DVR count
            cursor = await db.execute("SELECT COUNT(*) FROM dvrs")
            dvr_count = (await cursor.fetchone())[0]
            
            # Recent actions count (last 7 days)
            cursor = await db.execute("""
                SELECT COUNT(*) FROM action_log 
                WHERE timestamp >= datetime('now', '-7 days')
            """)
            recent_actions = (await cursor.fetchone())[0]
            
            # Cameras with memory cards
            cursor = await db.execute("SELECT COUNT(*) FROM cameras WHERE has_memory_card = 1")
            memory_card_count = (await cursor.fetchone())[0]
            
            return camera_count, dvr_count, recent_actions, memory_card_count
    except Exception as e:
        return 0, 0, 0, 0

async def get_cameras_list():
    """Get list of cameras for display."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT c.id, 
                       COALESCE(NULLIF(c.custom_name, ''), c.name) as display_name,
                       c.location, c.ip_address, c.date_installed, 
                       COALESCE(NULLIF(d.custom_name, ''), d.name) as dvr_name, 
                       c.has_memory_card
                FROM cameras c
                LEFT JOIN dvrs d ON c.dvr_id = d.id
                ORDER BY c.date_installed DESC
                LIMIT 50
            """)
            rows = await cursor.fetchall()
            columns = ["ID", "Display Name", "Location", "IP Address", "Date Installed", "DVR", "Memory Card"]
            return pd.DataFrame(rows, columns=columns)
    except Exception as e:
        return pd.DataFrame()

async def get_dvrs_list():
    """Get list of DVRs for display."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("""
                SELECT id, 
                       COALESCE(NULLIF(custom_name, ''), name) as display_name,
                       dvr_type, location, ip_address, storage_capacity, date_installed
                FROM dvrs
                ORDER BY date_installed DESC
                LIMIT 50
            """)
            rows = await cursor.fetchall()
            columns = ["ID", "Display Name", "Type", "Location", "IP Address", "Storage", "Date Installed"]
            return pd.DataFrame(rows, columns=columns)
    except Exception as e:
        return pd.DataFrame()

# CRUD Operations
async def add_camera(location, name, mac_address, ip_address, locational_group, 
                    date_installed, dvr_id, latitude, longitude, has_memory_card, 
                    memory_card_last_reset, coverage_radius=50.0, field_of_view_angle=360.0, 
                    coverage_direction=0.0, custom_name="", address=""):
    """Add a camera to the database."""
    try:
        if not all([location, name, mac_address, ip_address, date_installed]):
            return "❌ All required fields must be filled!"
        
        if not validate_mac(mac_address):
            return "❌ Invalid MAC address format!"
        if not validate_ip(ip_address):
            return "❌ Invalid IP address format!"
        if not validate_date(date_installed):
            return "❌ Invalid date format! Use YYYY-MM-DD."
        if not validate_coordinates(latitude, longitude):
            return "❌ Invalid latitude/longitude values!"
        if not validate_coverage_parameters(coverage_radius, field_of_view_angle, coverage_direction):
            return "❌ Invalid coverage parameters!"
        if not EnhancedCamera.validate_custom_name(custom_name):
            return "❌ Invalid custom name! Must be 1-100 characters, alphanumeric, spaces, hyphens, underscores, dots only."
        
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                "SELECT id FROM cameras WHERE mac_address = ? OR ip_address = ?", 
                (mac_address, ip_address)
            )
            if await cursor.fetchone():
                return "❌ MAC or IP address already exists!"
            
            # Handle DVR location inheritance
            final_latitude = float(latitude) if latitude else None
            final_longitude = float(longitude) if longitude else None
            location_inherited = False
            
            # If camera has no location but is assigned to a DVR, inherit DVR location
            if dvr_id and (not final_latitude or not final_longitude):
                cursor = await db.execute("""
                    SELECT latitude, longitude, custom_name FROM dvrs WHERE id = ?
                """, (dvr_id,))
                dvr_data = await cursor.fetchone()
                
                if dvr_data and dvr_data[0] and dvr_data[1]:
                    final_latitude = float(dvr_data[0])
                    final_longitude = float(dvr_data[1])
                    location_inherited = True
                    print(f"📍 Camera location inherited from DVR '{dvr_data[2]}': ({final_latitude}, {final_longitude})")
            
            await db.execute("""
                INSERT INTO cameras (location, name, mac_address, ip_address, locational_group, 
                                   date_installed, dvr_id, latitude, longitude, has_memory_card, 
                                   memory_card_last_reset, coverage_radius, field_of_view_angle, 
                                   coverage_direction, custom_name, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                location, name, mac_address, ip_address, locational_group or "", 
                date_installed, dvr_id or None, 
                final_latitude, final_longitude,
                bool(has_memory_card), memory_card_last_reset or None,
                float(coverage_radius), float(field_of_view_angle), float(coverage_direction),
                custom_name or "", address or ""
            ))
            await db.commit()
        
        success_message = "✅ Camera added successfully!"
        if location_inherited:
            success_message += f" (Location inherited from DVR: {final_latitude:.6f}, {final_longitude:.6f})"
        
        return success_message
    except Exception as e:
        return f"❌ Error adding camera: {str(e)}"

async def add_dvr(custom_name, dvr_type, location, ip_address, mac_address, 
                 storage_capacity, date_installed, latitude, longitude, address=""):
    """Add a DVR to the database using the new DVRManager."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        result = await dvr_manager.create_dvr(
            custom_name=custom_name,
            ip_address=ip_address,
            dvr_type=dvr_type,
            location=location,
            mac_address=mac_address,
            storage_capacity=storage_capacity,
            date_installed=date_installed,
            address=address,
            latitude=latitude,
            longitude=longitude
        )
        
        if result['success']:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Error adding DVR: {str(e)}"

async def search_devices_async(search_term, device_type):
    """Search cameras or DVRs (async version)."""
    try:
        if device_type == "Cameras":
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("""
                    SELECT c.id, 
                           COALESCE(NULLIF(c.custom_name, ''), c.name) as display_name,
                           c.location, c.ip_address, c.mac_address, 
                           c.date_installed, d.name as dvr_name
                    FROM cameras c
                    LEFT JOIN dvrs d ON c.dvr_id = d.id
                    WHERE c.name LIKE ? OR c.custom_name LIKE ? OR c.location LIKE ? OR c.ip_address LIKE ?
                    ORDER BY COALESCE(NULLIF(c.custom_name, ''), c.name)
                """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
                rows = await cursor.fetchall()
                columns = ["ID", "Display Name", "Location", "IP Address", "MAC Address", "Date Installed", "DVR"]
                return pd.DataFrame(rows, columns=columns)
        else:
            async with aiosqlite.connect(DB_NAME) as db:
                cursor = await db.execute("""
                    SELECT id, 
                           COALESCE(NULLIF(custom_name, ''), name) as display_name,
                           dvr_type, location, ip_address, mac_address, 
                           storage_capacity, date_installed
                    FROM dvrs
                    WHERE name LIKE ? OR custom_name LIKE ? OR location LIKE ? OR ip_address LIKE ?
                    ORDER BY COALESCE(NULLIF(custom_name, ''), name)
                """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
                rows = await cursor.fetchall()
                columns = ["ID", "Display Name", "Type", "Location", "IP Address", "MAC Address", "Storage", "Date Installed"]
                return pd.DataFrame(rows, columns=columns)
    except Exception as e:
        return pd.DataFrame()

def search_devices(search_term, device_type):
    """Search cameras or DVRs (synchronous wrapper for Gradio)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(search_devices_async(search_term, device_type))
        loop.close()
        return result
    except Exception as e:
        return pd.DataFrame()

# Network and Mapping Functions
def test_device_connection(ip_address):
    """Test device connectivity using ping."""
    try:
        if not validate_ip(ip_address):
            return f"❌ Invalid IP address: {ip_address}"
        
        response_time = ping(ip_address, timeout=3)
        if response_time is None:
            return f"❌ No response from {ip_address}"
        else:
            return f"✅ {ip_address} is online ({response_time:.2f}ms)"
    except Exception as e:
        return f"❌ Error testing {ip_address}: {str(e)}"

# Map generation functions have been moved to InteractiveMapManager

async def generate_map_html():
    """Generate enhanced HTML for the security map with coverage areas."""
    try:
        # Use the new InteractiveMapManager for enhanced functionality
        map_manager = InteractiveMapManager()
        return await map_manager.create_enhanced_map()
        
    except Exception as e:
        # Return error message in HTML format
        return f"""
        <div style="padding: 20px; text-align: center;">
            <h3>❌ Error generating enhanced map</h3>
            <p>{str(e)}</p>
            <p>Please check your camera coordinates and try again.</p>
        </div>
        """

# Camera coordinate updates are handled by InteractiveMapManager.handle_camera_move

def test_connection(ip_address):
    """Test connection to device using ping - wrapper for ConnectivityMonitor."""
    try:
        if not validate_ip(ip_address):
            return f"❌ Invalid IP address format: {ip_address}"
        
        # Use the connectivity monitor for testing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        connectivity_monitor = ConnectivityMonitor()
        result = loop.run_until_complete(
            connectivity_monitor.test_camera_connectivity(ip_address)
        )
        loop.close()
        
        return result.status_text
        
    except Exception as e:
        return f"❌ Error testing {ip_address}: {str(e)}"

# Map data functions are now in InteractiveMapManager

def create_interactive_map():
    """Create enhanced interactive map with coverage areas and connectivity status."""
    try:
        # Get map data synchronously for initial load
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Use the enhanced map manager
        map_manager = InteractiveMapManager()
        map_html = loop.run_until_complete(map_manager.create_enhanced_map())
        loop.close()
        
        return map_html
        
    except Exception as e:
        error_map = folium.Map(location=[40.7128, -74.0060], zoom_start=10)
        folium.Marker(
            [40.7128, -74.0060],
            popup=f"Error loading enhanced map: {str(e)}",
            icon=folium.Icon(color='red', icon='exclamation-sign')
        ).add_to(error_map)
        return error_map._repr_html_()

async def update_device_coordinates(device_id, device_type, latitude, longitude):
    """Update device coordinates in the database."""
    try:
        if not validate_coordinates(latitude, longitude):
            return "❌ Invalid latitude/longitude values!"
        
        table_name = "cameras" if device_type == "camera" else "dvrs"
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(f"""
                UPDATE {table_name}
                SET latitude = ?, longitude = ?
                WHERE id = ?
            """, (float(latitude), float(longitude), device_id))
            await db.commit()
        
        return f"✅ {device_type.title()} coordinates updated successfully!"
    except Exception as e:
        return f"❌ Error updating coordinates: {str(e)}"

# UI Components
def create_dashboard():
    """Create the main dashboard interface."""
    with gr.Blocks(css=CUSTOM_CSS, title="Security System Manager") as app:
        
        # Header
        gr.HTML("""
            <div class="dashboard-header">
                <h1>🔒 Security System Manager</h1>
                <p>Manage your cameras, DVRs, and security infrastructure</p>
            </div>
        """)
        
        # Dashboard Stats
        with gr.Row():
            camera_stat = gr.HTML()
            dvr_stat = gr.HTML()
            actions_stat = gr.HTML()
            memory_stat = gr.HTML()
        
        # Main Navigation Tabs
        with gr.Tabs():
            
            # Dashboard Tab
            with gr.Tab("📊 Dashboard"):
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh Stats", variant="primary")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📹 Recent Cameras")
                        cameras_df = gr.Dataframe(
                            headers=["ID", "Name", "Location", "IP Address", "Date Installed", "DVR", "Memory Card"],
                            interactive=False,
                            wrap=True
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 📺 Recent DVRs")
                        dvrs_df = gr.Dataframe(
                            headers=["ID", "Name", "Type", "Location", "IP Address", "Storage", "Date Installed"],
                            interactive=False,
                            wrap=True
                        )
            
            # Camera Management Tab
            with gr.Tab("📹 Camera Management"):
                with gr.Row():
                    add_camera_btn = gr.Button("➕ Add Camera", variant="primary")
                    search_cameras_btn = gr.Button("🔍 Search Cameras")
                    edit_camera_btn = gr.Button("✏️ Edit Camera", variant="secondary")
                
                # Add Camera Modal (initially hidden)
                with gr.Group(visible=False) as add_camera_modal:
                    gr.Markdown("### Add New Camera")
                    with gr.Row():
                        with gr.Column():
                            cam_location = gr.Textbox(label="Location *", placeholder="e.g., Main Entrance")
                            cam_name = gr.Textbox(label="Camera Name *", placeholder="e.g., CAM-001")
                            cam_mac = gr.Textbox(label="MAC Address *", placeholder="00:1A:2B:3C:4D:5E")
                            cam_ip = gr.Textbox(label="IP Address *", placeholder="192.168.1.100")
                        with gr.Column():
                            cam_group = gr.Textbox(label="Locational Group", placeholder="Building A")
                            cam_date = gr.Textbox(label="Date Installed *", placeholder="2024-01-15")
                            cam_dvr_dropdown = gr.Dropdown(label="Assign to DVR", choices=[], interactive=True)
                            cam_memory = gr.Checkbox(label="Has Memory Card")
                    
                    with gr.Row():
                        cam_custom_name = gr.Textbox(label="Custom Name", placeholder="Optional custom name")
                        cam_address = gr.Textbox(label="Address", placeholder="Physical address")
                    
                    with gr.Row():
                        convert_cam_address_btn = gr.Button("🗺️ Convert Address to Coordinates", variant="secondary")
                    
                    with gr.Row():
                        cam_lat = gr.Number(label="Latitude")
                        cam_lon = gr.Number(label="Longitude")
                        cam_memory_reset = gr.Textbox(label="Memory Card Last Reset", placeholder="2024-01-01")
                    
                    cam_address_conversion_result = gr.HTML(value="", visible=False)
                    
                    with gr.Row():
                        save_camera_btn = gr.Button("💾 Save Camera", variant="primary")
                        cancel_camera_btn = gr.Button("❌ Cancel")
                    
                    add_camera_result = gr.Textbox(label="Result", interactive=False)
                
                # Search Modal (initially hidden)
                with gr.Group(visible=False) as search_camera_modal:
                    gr.Markdown("### Search Cameras")
                    with gr.Row():
                        search_term = gr.Textbox(label="Search Term", placeholder="Enter name, location, or IP...")
                        search_btn = gr.Button("🔍 Search", variant="primary")
                        close_search_btn = gr.Button("❌ Close")
                    
                    search_results = gr.Dataframe(interactive=False)
                
                # Camera ID Input Modal (initially hidden)
                with gr.Group(visible=False) as camera_id_input_modal:
                    gr.Markdown("### Enter Camera ID to Edit")
                    camera_id_input = gr.Number(label="Camera ID", placeholder="Enter camera ID...")
                    with gr.Row():
                        load_camera_btn = gr.Button("📂 Load Camera", variant="primary")
                        cancel_camera_id_btn = gr.Button("❌ Cancel")
                
                # Edit Camera Modal (initially hidden)
                with gr.Group(visible=False) as edit_camera_modal:
                    gr.Markdown("### ✏️ Edit Camera")
                    
                    edit_camera_id = gr.Number(label="Camera ID", visible=False)
                    
                    with gr.Row():
                        with gr.Column():
                            edit_cam_location = gr.Textbox(label="Location *")
                            edit_cam_name = gr.Textbox(label="Camera Name *")
                            edit_cam_mac = gr.Textbox(label="MAC Address *")
                            edit_cam_ip = gr.Textbox(label="IP Address *")
                        with gr.Column():
                            edit_cam_group = gr.Textbox(label="Locational Group")
                            edit_cam_date = gr.Textbox(label="Date Installed *")
                            edit_cam_dvr_dropdown = gr.Dropdown(label="Assign to DVR", choices=[], interactive=True)
                            edit_cam_memory = gr.Checkbox(label="Has Memory Card")
                    
                    with gr.Row():
                        edit_cam_custom_name = gr.Textbox(label="Custom Name")
                        edit_cam_address = gr.Textbox(label="Address")
                    
                    with gr.Row():
                        edit_cam_lat = gr.Number(label="Latitude")
                        edit_cam_lon = gr.Number(label="Longitude")
                        edit_cam_memory_reset = gr.Textbox(label="Memory Card Last Reset")
                    
                    with gr.Row():
                        update_camera_btn = gr.Button("💾 Update Camera", variant="primary")
                        update_camera_with_inheritance_btn = gr.Button("💾 Update & Inherit DVR Location", variant="secondary")
                        cancel_edit_camera_btn = gr.Button("❌ Cancel")
                    
                    edit_camera_result = gr.Textbox(label="Result", interactive=False)
            
            # DVR Management Tab
            with gr.Tab("📺 DVR Management"):
                with gr.Row():
                    add_dvr_btn = gr.Button("➕ Add DVR", variant="primary")
                    search_dvrs_btn = gr.Button("🔍 Search DVRs")
                
                # Add DVR Modal (initially hidden)
                with gr.Group(visible=False) as add_dvr_modal:
                    gr.Markdown("### Add New DVR")
                    with gr.Row():
                        with gr.Column():
                            dvr_name = gr.Textbox(label="DVR Name *", placeholder="e.g., DVR-001")
                            dvr_type = gr.Textbox(label="DVR Type *", placeholder="e.g., 16-Channel")
                            dvr_location = gr.Textbox(label="Location *", placeholder="e.g., Server Room")
                            dvr_ip = gr.Textbox(label="IP Address *", placeholder="192.168.1.200")
                        with gr.Column():
                            dvr_mac = gr.Textbox(label="MAC Address *", placeholder="00:1A:2B:3C:4D:5F")
                            dvr_storage = gr.Textbox(label="Storage Capacity", placeholder="2TB")
                            dvr_date = gr.Textbox(label="Date Installed *", placeholder="2024-01-15")
                    
                    with gr.Row():
                        dvr_address = gr.Textbox(label="Address", placeholder="Physical address")
                    
                    with gr.Row():
                        convert_dvr_address_btn = gr.Button("🗺️ Convert Address to Coordinates", variant="secondary")
                    
                    with gr.Row():
                        dvr_lat = gr.Number(label="Latitude")
                        dvr_lon = gr.Number(label="Longitude")
                    
                    dvr_address_conversion_result = gr.HTML(value="", visible=False)
                    
                    with gr.Row():
                        save_dvr_btn = gr.Button("💾 Save DVR", variant="primary")
                        save_dvr_with_inheritance_btn = gr.Button("💾 Save DVR & Update Cameras", variant="secondary")
                        cancel_dvr_btn = gr.Button("❌ Cancel")
                    
                    add_dvr_result = gr.Textbox(label="Result", interactive=False)
                
                # Search DVR Modal (initially hidden)
                with gr.Group(visible=False) as search_dvr_modal:
                    gr.Markdown("### Search DVRs")
                    with gr.Row():
                        dvr_search_term = gr.Textbox(label="Search Term", placeholder="Enter name, location, or IP...")
                        dvr_search_btn = gr.Button("🔍 Search", variant="primary")
                        close_dvr_search_btn = gr.Button("❌ Close")
                    
                    dvr_search_results = gr.Dataframe(interactive=False)
                
                # DVR Location Inheritance Modal (initially hidden)
                with gr.Group(visible=False) as dvr_location_inheritance_modal:
                    gr.Markdown("### 📍 DVR Location Inheritance")
                    gr.Markdown("When you update a DVR's location, you can choose to update all cameras assigned to this DVR.")
                    
                    dvr_inheritance_info = gr.HTML(value="")
                    
                    with gr.Row():
                        confirm_inheritance_btn = gr.Button("✅ Update DVR and Cameras", variant="primary")
                        update_dvr_only_btn = gr.Button("📺 Update DVR Only", variant="secondary")
                        cancel_inheritance_btn = gr.Button("❌ Cancel", variant="stop")
                    
                    dvr_inheritance_result = gr.HTML(value="")
                    
                    # Hidden state to store DVR inheritance data
                    dvr_inheritance_state = gr.State(value={})
            
            # Interactive Map Tab
            with gr.Tab("🗺️ Interactive Map"):
                gr.Markdown("### Enhanced Security System Map")
                gr.Markdown("Interactive map with drag-and-drop camera positioning, real-time coverage visualization, and configuration management")
                
                # Main control buttons
                with gr.Row():
                    refresh_enhanced_map_btn = gr.Button("🔄 Refresh Map", variant="primary")
                    test_all_connections_btn = gr.Button("🔗 Test All Connections")
                    edit_coverage_btn = gr.Button("📐 Edit Coverage Parameters", variant="secondary")
                
                # Configuration management controls
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("**Configuration Management**")
                        with gr.Row():
                            save_config_btn = gr.Button("💾 Save Configuration", variant="secondary")
                            load_config_btn = gr.Button("📂 Load Configuration", variant="secondary")
                            list_configs_btn = gr.Button("📋 List Configurations", variant="secondary")
                    
                    with gr.Column(scale=1):
                        config_status = gr.HTML(
                            value="<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Ready to manage configurations</div>"
                        )
                
                # Enhanced map display
                enhanced_map_html = gr.HTML(label="Enhanced Security Map", value="Loading enhanced map...")
                
                # Configuration Management Modals
                with gr.Group(visible=False) as save_config_modal:
                    gr.Markdown("### 💾 Save Map Configuration")
                    with gr.Row():
                        config_name_input = gr.Textbox(
                            label="Configuration Name *",
                            placeholder="e.g., Main Building Layout",
                            interactive=True
                        )
                        config_description_input = gr.Textbox(
                            label="Description",
                            placeholder="Optional description of this configuration",
                            interactive=True
                        )
                    
                    with gr.Row():
                        confirm_save_config_btn = gr.Button("💾 Save", variant="primary")
                        cancel_save_config_btn = gr.Button("❌ Cancel", variant="secondary")
                    
                    save_config_result = gr.Textbox(label="Save Result", interactive=False)
                
                with gr.Group(visible=False) as load_config_modal:
                    gr.Markdown("### 📂 Load Map Configuration")
                    config_dropdown = gr.Dropdown(
                        label="Select Configuration",
                        choices=[],
                        interactive=True
                    )
                    config_details = gr.HTML(
                        value="<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a configuration to view details</div>"
                    )
                    
                    with gr.Row():
                        confirm_load_config_btn = gr.Button("📂 Load", variant="primary")
                        cancel_load_config_btn = gr.Button("❌ Cancel", variant="secondary")
                        delete_config_btn = gr.Button("🗑️ Delete", variant="secondary")
                    
                    load_config_result = gr.Textbox(label="Load Result", interactive=False)
                
                with gr.Group(visible=False) as config_list_modal:
                    gr.Markdown("### 📋 Configuration List")
                    config_list_display = gr.HTML(value="Loading configurations...")
                    
                    with gr.Row():
                        refresh_config_list_btn = gr.Button("🔄 Refresh", variant="secondary")
                        close_config_list_btn = gr.Button("❌ Close", variant="secondary")
                
                # Coverage Parameter Editing Modal (initially hidden)
                with gr.Group(visible=False) as coverage_edit_modal:
                    gr.Markdown("### 📐 Edit Camera Coverage Parameters")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            # Camera selection
                            coverage_camera_dropdown = gr.Dropdown(
                                label="Select Camera",
                                choices=[],
                                interactive=True
                            )
                            
                            # Camera type presets
                            gr.Markdown("**Camera Type Presets**")
                            camera_preset_dropdown = gr.Dropdown(
                                label="Apply Preset",
                                choices=[
                                    "Custom",
                                    "Standard Security Camera (50m, 360°)",
                                    "PTZ Camera (100m, 360°)",
                                    "Dome Camera (75m, 360°)",
                                    "Bullet Camera (60m, 90°)",
                                    "Fisheye Camera (30m, 360°)",
                                    "Long Range Camera (200m, 45°)",
                                    "Wide Angle Camera (40m, 120°)"
                                ],
                                value="Custom",
                                interactive=True
                            )
                            
                            apply_preset_btn = gr.Button("✨ Apply Preset", variant="secondary")
                        
                        with gr.Column(scale=2):
                            # Coverage parameters
                            gr.Markdown("**Coverage Parameters**")
                            
                            coverage_radius_slider = gr.Slider(
                                minimum=1,
                                maximum=1000,
                                value=50,
                                step=1,
                                label="Coverage Radius (meters)",
                                interactive=True
                            )
                            
                            field_of_view_slider = gr.Slider(
                                minimum=1,
                                maximum=360,
                                value=360,
                                step=1,
                                label="Field of View Angle (degrees)",
                                interactive=True
                            )
                            
                            coverage_direction_slider = gr.Slider(
                                minimum=0,
                                maximum=359,
                                value=0,
                                step=1,
                                label="Coverage Direction (degrees from North)",
                                interactive=True
                            )
                            
                            # Real-time preview info
                            coverage_preview_info = gr.HTML(
                                value="<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a camera to preview coverage parameters</div>"
                            )
                    
                    with gr.Row():
                        save_coverage_btn = gr.Button("💾 Save Coverage Parameters", variant="primary")
                        cancel_coverage_btn = gr.Button("❌ Cancel", variant="secondary")
                        reset_coverage_btn = gr.Button("🔄 Reset to Defaults", variant="secondary")
                    
                    coverage_edit_result = gr.Textbox(label="Result", interactive=False)
                
                # Device coordinate update section (for manual updates)
                with gr.Group():
                    gr.Markdown("### Manual Coordinate Updates")
                    gr.Markdown("*Note: You can also drag cameras directly on the map above*")
                    with gr.Row():
                        device_id_input = gr.Number(label="Device ID", precision=0)
                        device_type_input = gr.Dropdown(
                            choices=["camera", "dvr"], 
                            label="Device Type", 
                            value="camera"
                        )
                    with gr.Row():
                        new_lat_input = gr.Number(label="New Latitude")
                        new_lon_input = gr.Number(label="New Longitude")
                        update_coords_btn = gr.Button("📍 Update Coordinates", variant="secondary")
                    
                    coord_update_result = gr.Textbox(label="Update Result", interactive=False)
                
                # Connection test results
                connection_results = gr.Textbox(
                    label="Connection Test Results", 
                    interactive=False, 
                    lines=10,
                    visible=False
                )
            
            # Map Tab
            with gr.Tab("🗺️ Location Map"):
                with gr.Row():
                    refresh_map_btn = gr.Button("🔄 Refresh Map", variant="primary")
                    ping_device_btn = gr.Button("📡 Test Connection")
                
                with gr.Row():
                    with gr.Column(scale=3):
                        gr.Markdown("### 📍 Device Locations & Coverage Areas")
                        map_display = gr.HTML(value=create_interactive_map(), label="Interactive Map")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 🛠️ Map Tools")
                        
                        # Device coordinate updater
                        with gr.Group():
                            gr.Markdown("**Update Device Location**")
                            update_device_id = gr.Number(label="Device ID", precision=0)
                            update_device_type = gr.Dropdown(
                                choices=["camera", "dvr"], 
                                label="Device Type", 
                                value="camera"
                            )
                            update_lat = gr.Number(label="New Latitude")
                            update_lon = gr.Number(label="New Longitude")
                            update_coords_btn = gr.Button("📍 Update Location", variant="secondary")
                            update_result = gr.Textbox(label="Update Result", interactive=False)
                        
                        # Connection tester
                        with gr.Group():
                            gr.Markdown("**Test Device Connection**")
                            ping_ip = gr.Textbox(label="IP Address", placeholder="192.168.1.100")
                            ping_result = gr.Textbox(label="Ping Result", interactive=False)
                        
                        # Map legend
                        gr.HTML("""
                            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 20px;">
                                <h4>🗺️ Map Legend</h4>
                                <p><span style="color: blue;">🔵</span> <strong>Blue Markers:</strong> Cameras</p>
                                <p><span style="color: red;">🔴</span> <strong>Red Markers:</strong> DVRs</p>
                                <p><span style="color: lightblue;">⭕</span> <strong>Blue Circles:</strong> Camera Coverage Areas (~50m)</p>
                                <p><strong>💡 Tip:</strong> Click markers for device details</p>
                            </div>
                        """)
        
        # Initialize enhanced map manager and configuration manager
        try:
            from interactive_map_manager import InteractiveMapManager as EnhancedInteractiveMapManager
            map_manager = EnhancedInteractiveMapManager(DB_NAME)
        except ImportError:
            # Fallback to built-in InteractiveMapManager if external one not available
            map_manager = InteractiveMapManager()
        
        # Import configuration manager
        try:
            from map_configuration_manager import MapConfigurationManager
            config_manager = MapConfigurationManager(DB_NAME)
        except ImportError:
            # Create a simple fallback configuration manager
            class FallbackConfigManager:
                def __init__(self, db_name):
                    self.db_name = db_name
                
                async def save_configuration(self, name, description=""):
                    return type('Result', (), {'success': False, 'message': 'Configuration manager not available'})()
                
                async def load_configuration(self, config_id):
                    return type('Result', (), {'success': False, 'message': 'Configuration manager not available'})()
                
                async def list_configurations(self):
                    return type('Result', (), {'success': False, 'message': 'Configuration manager not available', 'configurations': []})()
                
                async def delete_configuration(self, config_id):
                    return type('Result', (), {'success': False, 'message': 'Configuration manager not available'})()
                
                async def get_configuration_details(self, config_id):
                    return None
            
            config_manager = FallbackConfigManager(DB_NAME)
        
        # Enhanced map functions
        async def refresh_enhanced_map():
            """Refresh the enhanced interactive map."""
            try:
                return await map_manager.create_enhanced_map()
            except Exception as e:
                return f"<div style='color: red; padding: 20px;'>❌ Error loading enhanced map: {str(e)}</div>"
        
        async def focus_map_on_device(device_id: int, device_type: str):
            """Focus the map on a specific device location."""
            try:
                return await map_manager.create_enhanced_map(focus_device_id=device_id, focus_device_type=device_type)
            except Exception as e:
                return f"<div style='color: red; padding: 20px;'>❌ Error focusing on device: {str(e)}</div>"
        
        async def test_all_device_connections():
            """Test connectivity to all cameras and DVRs."""
            try:
                # Get all cameras and DVRs
                cameras = await map_manager._get_cameras_with_coverage()
                dvrs = await map_manager._get_dvrs_for_map()
                
                # Initialize connectivity monitor
                connectivity_monitor = ConnectivityMonitor()
                
                # Test cameras
                camera_results = []
                for camera_data in cameras:
                    camera = EnhancedCamera.from_db_row(camera_data)
                    result = await connectivity_monitor.test_camera_connectivity(camera.ip_address)
                    status = "✅ Online" if result['is_online'] else "❌ Offline"
                    camera_results.append(f"📹 {camera.name} ({camera.ip_address}): {status}")
                
                # Test DVRs
                dvr_results = []
                for dvr_data in dvrs:
                    dvr_id, name, location, ip, lat, lon, dvr_type = dvr_data
                    result = await connectivity_monitor.test_camera_connectivity(ip)
                    status = "✅ Online" if result['is_online'] else "❌ Offline"
                    dvr_results.append(f"📺 {name} ({ip}): {status}")
                
                # Combine results
                all_results = camera_results + dvr_results
                results_text = "\n".join(all_results) if all_results else "No devices found to test"
                
                return gr.update(value=results_text, visible=True)
                
            except Exception as e:
                return gr.update(value=f"❌ Error testing connections: {str(e)}", visible=True)
        
        # Configuration management functions
        async def open_save_config_modal():
            """Open the save configuration modal."""
            return gr.update(visible=True)
        
        async def save_map_configuration(name: str, description: str = ""):
            """Save current map configuration."""
            try:
                if not name or not name.strip():
                    return "❌ Configuration name cannot be empty"
                
                result = await config_manager.save_configuration(name.strip(), description.strip())
                
                if result.success:
                    return f"✅ Configuration '{name}' saved successfully!"
                else:
                    return f"❌ {result.message}"
                    
            except Exception as e:
                return f"❌ Error saving configuration: {str(e)}"
        
        async def open_load_config_modal():
            """Open the load configuration modal and populate dropdown."""
            try:
                configs = await config_manager.list_configurations()
                
                if configs and len(configs) > 0:
                    choices = []
                    for config in configs:
                        choices.append((f"{config.name} ({config.camera_count} cameras)", config.id))
                    
                    return (
                        gr.update(visible=True),
                        gr.update(choices=choices),
                        "<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a configuration to view details</div>"
                    )
                else:
                    return (
                        gr.update(visible=True),
                        gr.update(choices=[]),
                        "<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>No configurations found</div>"
                    )
                    
            except Exception as e:
                return (
                    gr.update(visible=True),
                    gr.update(choices=[]),
                    f"<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>Error loading configurations: {str(e)}</div>"
                )
        
        async def show_config_details(config_id):
            """Show details for selected configuration."""
            if not config_id:
                return "<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a configuration to view details</div>"
            
            try:
                config = await config_manager.get_configuration_details(config_id)
                
                if config:
                    created_date = config.created_at.strftime("%Y-%m-%d %H:%M")
                    updated_date = config.updated_at.strftime("%Y-%m-%d %H:%M")
                    
                    return f"""
                    <div style='padding: 15px; background: #e8f4fd; border-radius: 8px; border-left: 4px solid #2196F3;'>
                        <h4>📋 {config.name}</h4>
                        <p><strong>Description:</strong> {config.description or 'No description'}</p>
                        <p><strong>Cameras:</strong> {len(config.camera_positions)} cameras</p>
                        <p><strong>Created:</strong> {created_date}</p>
                        <p><strong>Updated:</strong> {updated_date}</p>
                    </div>
                    """
                else:
                    return "<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>Configuration not found</div>"
                    
            except Exception as e:
                return f"<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>Error loading details: {str(e)}</div>"
        
        async def load_map_configuration(config_id):
            """Load selected configuration."""
            if not config_id:
                return "❌ Please select a configuration to load"
            
            try:
                result = await config_manager.load_configuration(config_id)
                
                if result.success:
                    return f"✅ Configuration loaded successfully! {result.message}"
                else:
                    return f"❌ {result.message}"
                    
            except Exception as e:
                return f"❌ Error loading configuration: {str(e)}"
        
        async def delete_map_configuration(config_id):
            """Delete selected configuration."""
            if not config_id:
                return "❌ Please select a configuration to delete"
            
            try:
                result = await config_manager.delete_configuration(config_id)
                
                if result.success:
                    return f"✅ Configuration deleted successfully!"
                else:
                    return f"❌ {result.message}"
                    
            except Exception as e:
                return f"❌ Error deleting configuration: {str(e)}"
        
        async def list_all_configurations():
            """List all available configurations."""
            try:
                configs = await config_manager.list_configurations()
                
                if configs and len(configs) > 0:
                    config_html = "<div style='padding: 15px;'><h4>📋 Available Configurations</h4>"
                    
                    for config in configs:
                        created_date = config.created_at.strftime("%Y-%m-%d %H:%M")
                        config_html += f"""
                        <div style='margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; border-left: 3px solid #007bff;'>
                            <strong>{config.name}</strong> ({config.camera_count} cameras)<br>
                            <small>{config.description or 'No description'}</small><br>
                            <small>Created: {created_date}</small>
                        </div>
                        """
                    
                    config_html += "</div>"
                    return config_html
                else:
                    return "<div style='padding: 15px; text-align: center; color: #666;'>No configurations found</div>"
                    
            except Exception as e:
                return f"<div style='padding: 15px; color: red;'>Error listing configurations: {str(e)}</div>"
        
        # Coverage parameter editing functions
        async def get_cameras_for_coverage_editing():
            """Get list of cameras for coverage parameter editing dropdown."""
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    cursor = await db.execute("""
                        SELECT id, name, location, coverage_radius, field_of_view_angle, coverage_direction
                        FROM cameras 
                        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                        ORDER BY name
                    """)
                    cameras = await cursor.fetchall()
                    
                    choices = []
                    for camera in cameras:
                        camera_id, name, location, radius, angle, direction = camera
                        choices.append((f"{name} ({location})", camera_id))
                    
                    return gr.update(choices=choices)
            except Exception as e:
                print(f"Error getting cameras for coverage editing: {e}")
                return gr.update(choices=[])
        
        async def load_camera_coverage_parameters(camera_id):
            """Load coverage parameters for selected camera."""
            if not camera_id:
                return (
                    50, 360, 0,
                    "<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a camera to preview coverage parameters</div>"
                )
            
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    cursor = await db.execute("""
                        SELECT name, location, coverage_radius, field_of_view_angle, coverage_direction, ip_address
                        FROM cameras WHERE id = ?
                    """, (camera_id,))
                    camera = await cursor.fetchone()
                    
                    if camera:
                        name, location, radius, angle, direction, ip = camera
                        
                        # Generate preview info
                        coverage_type = "Circular" if angle >= 360 else "Directional"
                        direction_text = f", facing {direction}° from North" if angle < 360 else ""
                        
                        preview_html = f"""
                        <div style='padding: 15px; background: #e8f4fd; border-radius: 8px; border-left: 4px solid #2196F3;'>
                            <h4>📹 {name}</h4>
                            <p><strong>Location:</strong> {location}</p>
                            <p><strong>IP Address:</strong> {ip}</p>
                            <p><strong>Coverage Type:</strong> {coverage_type}</p>
                            <p><strong>Coverage Area:</strong> {radius}m radius{direction_text}</p>
                            <p><strong>Field of View:</strong> {angle}°</p>
                        </div>
                        """
                        
                        return radius, angle, direction, preview_html
                    else:
                        return (
                            50, 360, 0,
                            "<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>Camera not found</div>"
                        )
            except Exception as e:
                return (
                    50, 360, 0,
                    f"<div style='padding: 10px; background: #ffebee; border-radius: 5px; color: #c62828;'>Error loading camera: {str(e)}</div>"
                )
        
        def apply_camera_preset(preset_name):
            """Apply camera type preset to coverage parameters."""
            presets = {
                "Standard Security Camera (50m, 360°)": (50, 360, 0),
                "PTZ Camera (100m, 360°)": (100, 360, 0),
                "Dome Camera (75m, 360°)": (75, 360, 0),
                "Bullet Camera (60m, 90°)": (60, 90, 0),
                "Fisheye Camera (30m, 360°)": (30, 360, 0),
                "Long Range Camera (200m, 45°)": (200, 45, 0),
                "Wide Angle Camera (40m, 120°)": (40, 120, 0)
            }
            
            if preset_name in presets:
                radius, angle, direction = presets[preset_name]
                return radius, angle, direction
            else:
                # Return current values for "Custom" or unknown presets
                return gr.update(), gr.update(), gr.update()
        
        def update_coverage_preview(camera_id, radius, angle, direction):
            """Update coverage preview when parameters change."""
            if not camera_id:
                return "<div style='padding: 10px; background: #f0f0f0; border-radius: 5px;'>Select a camera to preview coverage parameters</div>"
            
            # Validate parameters
            validation_errors = []
            if radius < 1 or radius > 1000:
                validation_errors.append("Coverage radius must be between 1 and 1000 meters")
            if angle < 1 or angle > 360:
                validation_errors.append("Field of view angle must be between 1 and 360 degrees")
            if direction < 0 or direction >= 360:
                validation_errors.append("Coverage direction must be between 0 and 359 degrees")
            
            if validation_errors:
                error_html = "<br>".join([f"• {error}" for error in validation_errors])
                return f"""
                <div style='padding: 15px; background: #ffebee; border-radius: 8px; border-left: 4px solid #f44336;'>
                    <h4>⚠️ Validation Errors</h4>
                    {error_html}
                </div>
                """
            
            # Generate updated preview
            coverage_type = "Circular" if angle >= 360 else "Directional"
            direction_text = f", facing {direction}° from North" if angle < 360 else ""
            
            # Calculate coverage area
            import math
            if angle >= 360:
                area = math.pi * (radius ** 2)
                area_text = f"{area:.0f} m²"
            else:
                sector_area = (angle / 360) * math.pi * (radius ** 2)
                area_text = f"{sector_area:.0f} m² (sector)"
            
            return f"""
            <div style='padding: 15px; background: #e8f5e8; border-radius: 8px; border-left: 4px solid #4caf50;'>
                <h4>📐 Coverage Preview</h4>
                <p><strong>Type:</strong> {coverage_type}</p>
                <p><strong>Radius:</strong> {radius}m</p>
                <p><strong>Field of View:</strong> {angle}°{direction_text}</p>
                <p><strong>Coverage Area:</strong> {area_text}</p>
                <p><strong>Status:</strong> ✅ Parameters valid</p>
            </div>
            """
        
        async def save_coverage_parameters(camera_id, radius, angle, direction):
            """Save coverage parameters to database."""
            if not camera_id:
                return "❌ Please select a camera first"
            
            # Validate parameters
            if not validate_coverage_parameters(radius, angle, direction):
                return "❌ Invalid coverage parameters. Please check the values and try again."
            
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    # Update camera coverage parameters
                    await db.execute("""
                        UPDATE cameras 
                        SET coverage_radius = ?, field_of_view_angle = ?, coverage_direction = ?
                        WHERE id = ?
                    """, (float(radius), float(angle), float(direction), camera_id))
                    
                    # Log the action
                    await db.execute("""
                        INSERT INTO action_log (timestamp, action_type, table_name, record_id, details)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        datetime.now().isoformat(),
                        "UPDATE",
                        "cameras",
                        camera_id,
                        f"Updated coverage parameters: radius={radius}m, angle={angle}°, direction={direction}°"
                    ))
                    
                    await db.commit()
                
                # Get camera name for confirmation
                async with aiosqlite.connect(DB_NAME) as db:
                    cursor = await db.execute("SELECT name FROM cameras WHERE id = ?", (camera_id,))
                    camera = await cursor.fetchone()
                    camera_name = camera[0] if camera else f"Camera {camera_id}"
                
                return f"✅ Coverage parameters updated successfully for {camera_name}!"
                
            except Exception as e:
                return f"❌ Error saving coverage parameters: {str(e)}"
        
        def reset_coverage_to_defaults():
            """Reset coverage parameters to default values."""
            return 50, 360, 0
        
        # Event handlers
        async def update_stats():
            camera_count, dvr_count, recent_actions, memory_count = await get_dashboard_stats()
            cameras_data = await get_cameras_list()
            dvrs_data = await get_dvrs_list()
            
            return (
                f'<div class="stats-card"><h3>{camera_count}</h3><p>📹 Total Cameras</p></div>',
                f'<div class="stats-card"><h3>{dvr_count}</h3><p>📺 Total DVRs</p></div>',
                f'<div class="stats-card"><h3>{recent_actions}</h3><p>📊 Recent Actions</p></div>',
                f'<div class="stats-card"><h3>{memory_count}</h3><p>💾 Memory Cards</p></div>',
                cameras_data,
                dvrs_data
            )
        
        # Synchronous wrapper functions for Gradio handlers
        def update_stats_sync():
            """Synchronous wrapper for update_stats."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(update_stats())
                loop.close()
                return result
            except Exception as e:
                return "❌ Error", "❌ Error", "❌ Error", "❌ Error", pd.DataFrame(), pd.DataFrame()

        def refresh_enhanced_map_sync():
            """Synchronous wrapper for refresh_enhanced_map."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(refresh_enhanced_map())
                loop.close()
                return result
            except Exception as e:
                return f"<div style='color: red; padding: 20px;'>❌ Error refreshing map: {str(e)}</div>"

        def add_camera_sync(location, name, mac_address, ip_address, locational_group, 
                           date_installed, dvr_id, latitude, longitude, has_memory_card, 
                           memory_card_last_reset, custom_name, address):
            """Synchronous wrapper for add_camera with address conversion."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Convert address to coordinates if provided and coordinates are empty
                converted_lat, converted_lon = latitude, longitude
                if address and address.strip() and (not latitude or not longitude):
                    from src.address_converter import AddressConverter
                    converter = AddressConverter()
                    conversion_result = loop.run_until_complete(
                        converter.address_to_coordinates(address.strip())
                    )
                    
                    if conversion_result['success']:
                        converted_lat = conversion_result['latitude']
                        converted_lon = conversion_result['longitude']
                        print(f"✅ Address converted: {address} -> ({converted_lat}, {converted_lon})")
                    else:
                        print(f"⚠️ Address conversion failed: {conversion_result.get('error', 'Unknown error')}")
                
                result = loop.run_until_complete(
                    add_camera(location, name, mac_address, ip_address, locational_group, 
                              date_installed, dvr_id, converted_lat, converted_lon, has_memory_card, 
                              memory_card_last_reset, 50.0, 360.0, 0.0, custom_name, address)
                )
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error adding camera: {str(e)}"

        async def update_dvr_location_with_inheritance(dvr_id, latitude, longitude, address="", 
                                                      update_cameras=False):
            """Update DVR location and optionally propagate to assigned cameras."""
            try:
                dvr_manager = DVRManager(DB_NAME)
                
                # Update DVR location
                result = await dvr_manager.update_dvr_location(dvr_id, latitude, longitude, address)
                
                if not result['success']:
                    return result
                
                # If requested, propagate location to assigned cameras
                if update_cameras:
                    propagation_result = await dvr_manager.propagate_dvr_location_to_cameras(
                        dvr_id, force_update=True
                    )
                    
                    if propagation_result['success']:
                        result['message'] += f" and propagated to {propagation_result['cameras_updated']} cameras"
                    else:
                        result['message'] += f" but failed to propagate to cameras: {propagation_result['message']}"
                
                return result
                
            except Exception as e:
                return {
                    'success': False,
                    'message': f"Error updating DVR location: {str(e)}"
                }

        def update_dvr_location_sync(dvr_id, latitude, longitude, address="", update_cameras=False):
            """Synchronous wrapper for DVR location update with inheritance."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(
                    update_dvr_location_with_inheritance(dvr_id, latitude, longitude, address, update_cameras)
                )
                loop.close()
                
                if result['success']:
                    return f"✅ {result['message']}"
                else:
                    return f"❌ {result['message']}"
                    
            except Exception as e:
                return f"❌ Error updating DVR location: {str(e)}"

        def open_camera_modal_with_dvr_choices():
            """Open camera modal and populate DVR dropdown choices."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Get DVR choices for dropdown
                dvr_choices = loop.run_until_complete(get_dvr_dropdown_choices())
                loop.close()
                
                return (
                    gr.update(visible=True),  # Show modal
                    gr.update(choices=dvr_choices, value=None)  # Update dropdown with choices
                )
            except Exception as e:
                print(f"Error opening camera modal: {e}")
                return (
                    gr.update(visible=True),
                    gr.update(choices=[("No DVR", None)], value=None)
                )

        def add_dvr_sync(name, dvr_type, location, ip_address, mac_address, 
                        storage_capacity, date_installed, latitude, longitude, address):
            """Synchronous wrapper for add_dvr with address conversion."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Convert address to coordinates if provided and coordinates are empty
                converted_lat, converted_lon = latitude, longitude
                if address and address.strip() and (not latitude or not longitude):
                    from src.address_converter import AddressConverter
                    converter = AddressConverter()
                    conversion_result = loop.run_until_complete(
                        converter.address_to_coordinates(address.strip())
                    )
                    
                    if conversion_result['success']:
                        converted_lat = conversion_result['latitude']
                        converted_lon = conversion_result['longitude']
                        print(f"✅ Address converted: {address} -> ({converted_lat}, {converted_lon})")
                    else:
                        print(f"⚠️ Address conversion failed: {conversion_result.get('error', 'Unknown error')}")
                
                result = loop.run_until_complete(
                    add_dvr(name, dvr_type, location, ip_address, mac_address, 
                           storage_capacity, date_installed, converted_lat, converted_lon, address)
                )
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error adding DVR: {str(e)}"

        def add_dvr_with_inheritance_sync(name, dvr_type, location, ip_address, mac_address, 
                                        storage_capacity, date_installed, latitude, longitude, address):
            """Add DVR and show inheritance options if cameras would be affected."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # First add the DVR normally
                result = loop.run_until_complete(
                    add_dvr(name, dvr_type, location, ip_address, mac_address, 
                           storage_capacity, date_installed, latitude, longitude, address)
                )
                
                # If DVR was added successfully and has coordinates, check for cameras that could inherit location
                if "✅" in result and latitude and longitude:
                    # Get the newly created DVR ID (this is a simplified approach)
                    cursor = loop.run_until_complete(
                        aiosqlite.connect(DB_NAME).__aenter__()
                    )
                    db = cursor
                    cursor = loop.run_until_complete(
                        db.execute("SELECT id FROM dvrs WHERE ip_address = ?", (ip_address,))
                    )
                    dvr_row = loop.run_until_complete(cursor.fetchone())
                    
                    if dvr_row:
                        dvr_id = dvr_row[0]
                        
                        # Check for cameras without coordinates that could inherit this location
                        cursor = loop.run_until_complete(
                            db.execute("""
                                SELECT COUNT(*) FROM cameras 
                                WHERE (latitude IS NULL OR longitude IS NULL)
                            """)
                        )
                        unlocated_cameras = (loop.run_until_complete(cursor.fetchone()))[0]
                        
                        if unlocated_cameras > 0:
                            result += f"\n💡 There are {unlocated_cameras} cameras without coordinates that could inherit this DVR's location when assigned."
                    
                    loop.run_until_complete(db.close())
                
                loop.close()
                return result
                
            except Exception as e:
                return f"❌ Error adding DVR with inheritance check: {str(e)}"

        async def assign_camera_to_dvr_with_inheritance(camera_id, dvr_id, inherit_location=True):
            """Assign camera to DVR with location inheritance."""
            try:
                dvr_manager = DVRManager(DB_NAME)
                result = await dvr_manager.assign_camera_to_dvr(camera_id, dvr_id, inherit_location)
                return result
            except Exception as e:
                return {
                    'success': False,
                    'message': f"Error assigning camera to DVR: {str(e)}"
                }

        def assign_camera_to_dvr_sync(camera_id, dvr_id, inherit_location=True):
            """Synchronous wrapper for camera to DVR assignment."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(
                    assign_camera_to_dvr_with_inheritance(camera_id, dvr_id, inherit_location)
                )
                loop.close()
                
                if result['success']:
                    return f"✅ {result['message']}"
                else:
                    return f"❌ {result['message']}"
                    
            except Exception as e:
                return f"❌ Error assigning camera to DVR: {str(e)}"

        async def get_dvr_camera_inheritance_info(dvr_id, latitude, longitude):
            """Get information about cameras that would be affected by DVR location change."""
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    # Get DVR info
                    cursor = await db.execute("""
                        SELECT custom_name, ip_address FROM dvrs WHERE id = ?
                    """, (dvr_id,))
                    dvr_data = await cursor.fetchone()
                    
                    if not dvr_data:
                        return {
                            'success': False,
                            'message': "DVR not found"
                        }
                    
                    dvr_name = dvr_data[0] or f"DVR-{dvr_data[1]}"
                    
                    # Get cameras assigned to this DVR
                    cursor = await db.execute("""
                        SELECT id, name, custom_name, latitude, longitude 
                        FROM cameras WHERE dvr_id = ?
                    """, (dvr_id,))
                    cameras = await cursor.fetchall()
                    
                    cameras_without_location = []
                    cameras_with_location = []
                    
                    for camera in cameras:
                        camera_name = camera[2] if camera[2] else camera[1]
                        if not camera[3] or not camera[4]:  # No coordinates
                            cameras_without_location.append(camera_name)
                        else:
                            cameras_with_location.append(camera_name)
                    
                    return {
                        'success': True,
                        'dvr_name': dvr_name,
                        'cameras_without_location': cameras_without_location,
                        'cameras_with_location': cameras_with_location,
                        'total_cameras': len(cameras),
                        'new_coordinates': f"{latitude:.6f}, {longitude:.6f}"
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'message': f"Error getting inheritance info: {str(e)}"
                }

        def show_dvr_inheritance_dialog(dvr_id, latitude, longitude):
            """Show DVR location inheritance confirmation dialog."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                info = loop.run_until_complete(
                    get_dvr_camera_inheritance_info(dvr_id, latitude, longitude)
                )
                loop.close()
                
                if not info['success']:
                    return gr.update(visible=False), f"❌ {info['message']}"
                
                # Create HTML info display
                html_content = f"""
                <div style="padding: 15px; background: #f8f9fa; border-radius: 8px; margin: 10px 0;">
                    <h4>📺 DVR: {info['dvr_name']}</h4>
                    <p><strong>New Location:</strong> {info['new_coordinates']}</p>
                    <p><strong>Total Assigned Cameras:</strong> {info['total_cameras']}</p>
                """
                
                if info['cameras_without_location']:
                    html_content += f"""
                    <div style="margin: 10px 0; padding: 10px; background: #e3f2fd; border-radius: 5px;">
                        <strong>📍 Cameras that will inherit DVR location ({len(info['cameras_without_location'])}):</strong>
                        <ul>
                    """
                    for camera in info['cameras_without_location']:
                        html_content += f"<li>{camera}</li>"
                    html_content += "</ul></div>"
                
                if info['cameras_with_location']:
                    html_content += f"""
                    <div style="margin: 10px 0; padding: 10px; background: #fff3e0; border-radius: 5px;">
                        <strong>⚠️ Cameras with existing locations ({len(info['cameras_with_location'])}):</strong>
                        <ul>
                    """
                    for camera in info['cameras_with_location']:
                        html_content += f"<li>{camera} (will keep current location)</li>"
                    html_content += "</ul></div>"
                
                html_content += "</div>"
                
                return gr.update(visible=True), html_content
                
            except Exception as e:
                return gr.update(visible=False), f"❌ Error showing inheritance dialog: {str(e)}"

        async def get_camera_for_editing(camera_id):
            """Get camera data for editing form."""
            try:
                async with aiosqlite.connect(DB_NAME) as db:
                    cursor = await db.execute("""
                        SELECT id, location, name, mac_address, ip_address, locational_group,
                               date_installed, dvr_id, latitude, longitude, has_memory_card,
                               memory_card_last_reset, custom_name, address
                        FROM cameras WHERE id = ?
                    """, (camera_id,))
                    
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    
                    return {
                        'id': row[0],
                        'location': row[1] or "",
                        'name': row[2] or "",
                        'mac_address': row[3] or "",
                        'ip_address': row[4] or "",
                        'locational_group': row[5] or "",
                        'date_installed': row[6] or "",
                        'dvr_id': row[7],
                        'latitude': row[8],
                        'longitude': row[9],
                        'has_memory_card': bool(row[10]) if row[10] is not None else False,
                        'memory_card_last_reset': row[11] or "",
                        'custom_name': row[12] or "",
                        'address': row[13] or ""
                    }
                    
            except Exception as e:
                print(f"Error getting camera for editing: {e}")
                return None

        def open_camera_edit_modal(camera_id):
            """Open camera edit modal with populated data."""
            try:
                if not camera_id:
                    return (
                        gr.update(visible=False),
                        gr.update(choices=[("No DVR", None)]),
                        "❌ Please provide a camera ID"
                    )
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Get camera data
                camera_data = loop.run_until_complete(get_camera_for_editing(int(camera_id)))
                
                if not camera_data:
                    loop.close()
                    return (
                        gr.update(visible=False),
                        gr.update(choices=[("No DVR", None)]),
                        "❌ Camera not found"
                    )
                
                # Get DVR choices
                dvr_choices = loop.run_until_complete(get_dvr_dropdown_choices())
                loop.close()
                
                # Return updates for all form fields
                return (
                    gr.update(visible=True),  # Show modal
                    gr.update(choices=dvr_choices, value=camera_data['dvr_id']),  # DVR dropdown
                    camera_data['id'],  # Camera ID
                    camera_data['location'],  # Location
                    camera_data['name'],  # Name
                    camera_data['mac_address'],  # MAC
                    camera_data['ip_address'],  # IP
                    camera_data['locational_group'],  # Group
                    camera_data['date_installed'],  # Date
                    camera_data['has_memory_card'],  # Memory card
                    camera_data['custom_name'],  # Custom name
                    camera_data['address'],  # Address
                    camera_data['latitude'],  # Latitude
                    camera_data['longitude'],  # Longitude
                    camera_data['memory_card_last_reset'],  # Memory reset
                    ""  # Clear result
                )
                
            except Exception as e:
                return (
                    gr.update(visible=False),
                    gr.update(choices=[("No DVR", None)]),
                    f"❌ Error opening edit modal: {str(e)}"
                )

        async def update_camera(camera_id, location, name, mac_address, ip_address, locational_group,
                              date_installed, dvr_id, latitude, longitude, has_memory_card,
                              memory_card_last_reset, custom_name, address, inherit_dvr_location=False):
            """Update camera with optional DVR location inheritance."""
            try:
                # Validate required fields
                if not all([location, name, mac_address, ip_address, date_installed]):
                    return "❌ All required fields must be filled!"
                
                # Validate formats
                if not validate_mac(mac_address):
                    return "❌ Invalid MAC address format!"
                if not validate_ip(ip_address):
                    return "❌ Invalid IP address format!"
                if not validate_date(date_installed):
                    return "❌ Invalid date format! Use YYYY-MM-DD."
                if not validate_coordinates(latitude, longitude):
                    return "❌ Invalid latitude/longitude values!"
                if not EnhancedCamera.validate_custom_name(custom_name):
                    return "❌ Invalid custom name! Must be 1-100 characters, alphanumeric, spaces, hyphens, underscores, dots only."
                
                async with aiosqlite.connect(DB_NAME) as db:
                    # Check for duplicate MAC/IP (excluding current camera)
                    cursor = await db.execute("""
                        SELECT id FROM cameras 
                        WHERE (mac_address = ? OR ip_address = ?) AND id != ?
                    """, (mac_address, ip_address, camera_id))
                    
                    if await cursor.fetchone():
                        return "❌ MAC or IP address already exists for another camera!"
                    
                    # Handle DVR location inheritance
                    final_latitude = float(latitude) if latitude else None
                    final_longitude = float(longitude) if longitude else None
                    location_inherited = False
                    
                    # If inherit_dvr_location is True or camera has no location but is assigned to a DVR
                    if dvr_id and (inherit_dvr_location or (not final_latitude or not final_longitude)):
                        cursor = await db.execute("""
                            SELECT latitude, longitude, custom_name FROM dvrs WHERE id = ?
                        """, (dvr_id,))
                        dvr_data = await cursor.fetchone()
                        
                        if dvr_data and dvr_data[0] and dvr_data[1]:
                            final_latitude = float(dvr_data[0])
                            final_longitude = float(dvr_data[1])
                            location_inherited = True
                            print(f"📍 Camera location inherited from DVR '{dvr_data[2]}': ({final_latitude}, {final_longitude})")
                    
                    # Update camera
                    await db.execute("""
                        UPDATE cameras SET 
                            location = ?, name = ?, mac_address = ?, ip_address = ?, 
                            locational_group = ?, date_installed = ?, dvr_id = ?, 
                            latitude = ?, longitude = ?, has_memory_card = ?, 
                            memory_card_last_reset = ?, custom_name = ?, address = ?
                        WHERE id = ?
                    """, (
                        location, name, mac_address, ip_address, locational_group or "",
                        date_installed, dvr_id or None, final_latitude, final_longitude,
                        bool(has_memory_card), memory_card_last_reset or None,
                        custom_name or "", address or "", camera_id
                    ))
                    
                    await db.commit()
                    
                    success_message = "✅ Camera updated successfully!"
                    if location_inherited:
                        success_message += f" (Location inherited from DVR: {final_latitude:.6f}, {final_longitude:.6f})"
                    
                    return success_message
                    
            except Exception as e:
                return f"❌ Error updating camera: {str(e)}"

        def update_camera_sync(camera_id, location, name, mac_address, ip_address, locational_group,
                             date_installed, dvr_id, latitude, longitude, has_memory_card,
                             memory_card_last_reset, custom_name, address):
            """Synchronous wrapper for camera update."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(
                    update_camera(camera_id, location, name, mac_address, ip_address, locational_group,
                                date_installed, dvr_id, latitude, longitude, has_memory_card,
                                memory_card_last_reset, custom_name, address, False)
                )
                loop.close()
                return result
                
            except Exception as e:
                return f"❌ Error updating camera: {str(e)}"

        def update_camera_with_inheritance_sync(camera_id, location, name, mac_address, ip_address, locational_group,
                                              date_installed, dvr_id, latitude, longitude, has_memory_card,
                                              memory_card_last_reset, custom_name, address):
            """Synchronous wrapper for camera update with DVR location inheritance."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(
                    update_camera(camera_id, location, name, mac_address, ip_address, locational_group,
                                date_installed, dvr_id, latitude, longitude, has_memory_card,
                                memory_card_last_reset, custom_name, address, True)
                )
                loop.close()
                return result
                
            except Exception as e:
                return f"❌ Error updating camera with inheritance: {str(e)}"
        
        def convert_camera_address(address):
            """Convert camera address to coordinates."""
            try:
                if not address or not address.strip():
                    return (
                        None, None,
                        "<div style='color: orange; padding: 10px; background: #fff3cd; border-radius: 5px;'>⚠️ Please enter an address to convert</div>"
                    )
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                from src.address_converter import AddressConverter
                converter = AddressConverter()
                result = loop.run_until_complete(
                    converter.address_to_coordinates(address.strip())
                )
                loop.close()
                
                if result['success']:
                    success_msg = f"""
                    <div style='color: green; padding: 10px; background: #d4edda; border-radius: 5px;'>
                        ✅ Address converted successfully!<br>
                        <strong>Coordinates:</strong> {result['latitude']:.6f}, {result['longitude']:.6f}<br>
                        <strong>Formatted Address:</strong> {result.get('formatted_address', address)}
                    </div>
                    """
                    return result['latitude'], result['longitude'], success_msg
                else:
                    error_msg = f"""
                    <div style='color: red; padding: 10px; background: #f8d7da; border-radius: 5px;'>
                        ❌ Address conversion failed<br>
                        <strong>Error:</strong> {result.get('error', 'Unknown error')}<br>
                        <em>Please enter coordinates manually or try a different address format</em>
                    </div>
                    """
                    return None, None, error_msg
                    
            except Exception as e:
                error_msg = f"""
                <div style='color: red; padding: 10px; background: #f8d7da; border-radius: 5px;'>
                    ❌ Error during address conversion<br>
                    <strong>Error:</strong> {str(e)}
                </div>
                """
                return None, None, error_msg
        
        def convert_dvr_address(address):
            """Convert DVR address to coordinates."""
            try:
                if not address or not address.strip():
                    return (
                        None, None,
                        "<div style='color: orange; padding: 10px; background: #fff3cd; border-radius: 5px;'>⚠️ Please enter an address to convert</div>"
                    )
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                from src.address_converter import AddressConverter
                converter = AddressConverter()
                result = loop.run_until_complete(
                    converter.address_to_coordinates(address.strip())
                )
                loop.close()
                
                if result['success']:
                    success_msg = f"""
                    <div style='color: green; padding: 10px; background: #d4edda; border-radius: 5px;'>
                        ✅ Address converted successfully!<br>
                        <strong>Coordinates:</strong> {result['latitude']:.6f}, {result['longitude']:.6f}<br>
                        <strong>Formatted Address:</strong> {result.get('formatted_address', address)}
                    </div>
                    """
                    return result['latitude'], result['longitude'], success_msg
                else:
                    error_msg = f"""
                    <div style='color: red; padding: 10px; background: #f8d7da; border-radius: 5px;'>
                        ❌ Address conversion failed<br>
                        <strong>Error:</strong> {result.get('error', 'Unknown error')}<br>
                        <em>Please enter coordinates manually or try a different address format</em>
                    </div>
                    """
                    return None, None, error_msg
                    
            except Exception as e:
                error_msg = f"""
                <div style='color: red; padding: 10px; background: #f8d7da; border-radius: 5px;'>
                    ❌ Error during address conversion<br>
                    <strong>Error:</strong> {str(e)}
                </div>
                """
                return None, None, error_msg

        def test_all_device_connections_sync():
            """Synchronous wrapper for test_all_device_connections."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(test_all_device_connections())
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error testing connections: {str(e)}"

        def save_map_configuration_sync(name, description=""):
            """Synchronous wrapper for save_map_configuration."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(save_map_configuration(name, description))
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error saving configuration: {str(e)}"

        def open_load_config_modal_sync():
            """Synchronous wrapper for open_load_config_modal."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(open_load_config_modal())
                loop.close()
                return result
            except Exception as e:
                return gr.update(visible=False), gr.update(choices=[]), "❌ Error loading configurations"

        def load_map_configuration_sync(config_id):
            """Synchronous wrapper for load_map_configuration."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(load_map_configuration(config_id))
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error loading configuration: {str(e)}"

        def delete_map_configuration_sync(config_id):
            """Synchronous wrapper for delete_map_configuration."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(delete_map_configuration(config_id))
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error deleting configuration: {str(e)}"

        def list_all_configurations_sync():
            """Synchronous wrapper for list_all_configurations."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(list_all_configurations())
                loop.close()
                return result
            except Exception as e:
                return "❌ Error listing configurations"

        def open_coverage_modal_sync():
            """Synchronous wrapper for open_coverage_modal."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(open_coverage_modal())
                loop.close()
                return result
            except Exception as e:
                return gr.update(visible=False), gr.update(choices=[])

        def load_camera_coverage_parameters_sync(camera_id):
            """Synchronous wrapper for load_camera_coverage_parameters."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(load_camera_coverage_parameters(camera_id))
                loop.close()
                return result
            except Exception as e:
                return 50.0, 360.0, 0.0, "❌ Error loading parameters"

        def save_coverage_parameters_sync(camera_id, radius, angle, direction):
            """Synchronous wrapper for save_coverage_parameters."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(save_coverage_parameters(camera_id, radius, angle, direction))
                loop.close()
                return result
            except Exception as e:
                return f"❌ Error saving coverage parameters: {str(e)}"

        def initialize_enhanced_map_sync():
            """Synchronous wrapper for initialize_enhanced_map."""
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(initialize_enhanced_map())
                loop.close()
                return result
            except Exception as e:
                return f"<div style='color: red; padding: 20px;'>❌ Error initializing map: {str(e)}</div>"

        # Button event handlers
        refresh_btn.click(
            update_stats_sync,
            outputs=[camera_stat, dvr_stat, actions_stat, memory_stat, cameras_df, dvrs_df]
        )
        
        # Modal toggle handlers with DVR dropdown population
        add_camera_btn.click(
            open_camera_modal_with_dvr_choices,
            outputs=[add_camera_modal, cam_dvr_dropdown]
        )
        cancel_camera_btn.click(lambda: gr.update(visible=False), outputs=add_camera_modal)
        
        add_dvr_btn.click(lambda: gr.update(visible=True), outputs=add_dvr_modal)
        cancel_dvr_btn.click(lambda: gr.update(visible=False), outputs=add_dvr_modal)
        
        search_cameras_btn.click(lambda: gr.update(visible=True), outputs=search_camera_modal)
        close_search_btn.click(lambda: gr.update(visible=False), outputs=search_camera_modal)
        
        search_dvrs_btn.click(lambda: gr.update(visible=True), outputs=search_dvr_modal)
        close_dvr_search_btn.click(lambda: gr.update(visible=False), outputs=search_dvr_modal)
        
        # Enhanced map event handlers
        refresh_enhanced_map_btn.click(
            refresh_enhanced_map_sync,
            outputs=enhanced_map_html
        )
        
        test_all_connections_btn.click(
            test_all_device_connections_sync,
            outputs=connection_results
        )
        
        # Configuration management event handlers
        save_config_btn.click(
            open_save_config_modal,
            outputs=save_config_modal
        )
        
        cancel_save_config_btn.click(
            lambda: gr.update(visible=False),
            outputs=save_config_modal
        )
        
        confirm_save_config_btn.click(
            save_map_configuration_sync,
            inputs=[config_name_input, config_description_input],
            outputs=save_config_result
        )
        
        load_config_btn.click(
            open_load_config_modal_sync,
            outputs=[load_config_modal, config_dropdown, config_details]
        )
        
        cancel_load_config_btn.click(
            lambda: gr.update(visible=False),
            outputs=load_config_modal
        )
        
        config_dropdown.change(
            show_config_details,
            inputs=config_dropdown,
            outputs=config_details
        )
        
        confirm_load_config_btn.click(
            load_map_configuration_sync,
            inputs=config_dropdown,
            outputs=load_config_result
        )
        
        delete_config_btn.click(
            delete_map_configuration_sync,
            inputs=config_dropdown,
            outputs=load_config_result
        )
        
        list_configs_btn.click(
            lambda: gr.update(visible=True),
            outputs=config_list_modal
        )
        
        close_config_list_btn.click(
            lambda: gr.update(visible=False),
            outputs=config_list_modal
        )
        
        refresh_config_list_btn.click(
            list_all_configurations_sync,
            outputs=config_list_display
        )
        
        # Coverage parameter editing handlers
        async def open_coverage_modal():
            camera_choices = await get_cameras_for_coverage_editing()
            return gr.update(visible=True), camera_choices
        
        edit_coverage_btn.click(
            open_coverage_modal_sync,
            outputs=[coverage_edit_modal, coverage_camera_dropdown]
        )
        
        cancel_coverage_btn.click(
            lambda: gr.update(visible=False),
            outputs=coverage_edit_modal
        )
        
        # Coverage parameter change handlers
        coverage_camera_dropdown.change(
            load_camera_coverage_parameters_sync,
            inputs=coverage_camera_dropdown,
            outputs=[coverage_radius_slider, field_of_view_slider, coverage_direction_slider, coverage_preview_info]
        )
        
        apply_preset_btn.click(
            apply_camera_preset,
            inputs=camera_preset_dropdown,
            outputs=[coverage_radius_slider, field_of_view_slider, coverage_direction_slider]
        )
        
        # Real-time preview updates
        for component in [coverage_radius_slider, field_of_view_slider, coverage_direction_slider]:
            component.change(
                update_coverage_preview,
                inputs=[coverage_camera_dropdown, coverage_radius_slider, field_of_view_slider, coverage_direction_slider],
                outputs=coverage_preview_info
            )
        
        # Save and reset handlers
        save_coverage_btn.click(
            save_coverage_parameters_sync,
            inputs=[coverage_camera_dropdown, coverage_radius_slider, field_of_view_slider, coverage_direction_slider],
            outputs=coverage_edit_result
        )
        
        reset_coverage_btn.click(
            reset_coverage_to_defaults,
            outputs=[coverage_radius_slider, field_of_view_slider, coverage_direction_slider]
        )
        
        # Save handlers
        save_camera_btn.click(
            add_camera_sync,
            inputs=[cam_location, cam_name, cam_mac, cam_ip, cam_group, cam_date, 
                   cam_dvr_dropdown, cam_lat, cam_lon, cam_memory, cam_memory_reset, 
                   cam_custom_name, cam_address],
            outputs=add_camera_result
        )
        
        save_dvr_btn.click(
            add_dvr_sync,
            inputs=[dvr_name, dvr_type, dvr_location, dvr_ip, dvr_mac, 
                   dvr_storage, dvr_date, dvr_lat, dvr_lon, dvr_address],
            outputs=add_dvr_result
        )
        
        save_dvr_with_inheritance_btn.click(
            add_dvr_with_inheritance_sync,
            inputs=[dvr_name, dvr_type, dvr_location, dvr_ip, dvr_mac, 
                   dvr_storage, dvr_date, dvr_lat, dvr_lon, dvr_address],
            outputs=add_dvr_result
        )
        
        # Address conversion handlers
        convert_cam_address_btn.click(
            convert_camera_address,
            inputs=[cam_address],
            outputs=[cam_lat, cam_lon, cam_address_conversion_result]
        ).then(
            lambda: gr.update(visible=True),
            outputs=cam_address_conversion_result
        )
        
        convert_dvr_address_btn.click(
            convert_dvr_address,
            inputs=[dvr_address],
            outputs=[dvr_lat, dvr_lon, dvr_address_conversion_result]
        ).then(
            lambda: gr.update(visible=True),
            outputs=dvr_address_conversion_result
        )
        
        # Search handlers
        search_btn.click(
            lambda term: search_devices(term, "Cameras"),
            inputs=search_term,
            outputs=search_results
        )
        
        dvr_search_btn.click(
            lambda term: search_devices(term, "DVRs"),
            inputs=dvr_search_term,
            outputs=dvr_search_results
        )
        
        # DVR Location Inheritance event handlers
        confirm_inheritance_btn.click(
            lambda state: update_dvr_location_sync(
                state.get('dvr_id'), state.get('latitude'), state.get('longitude'), 
                state.get('address', ''), True
            ) if state else "❌ No DVR data available",
            inputs=dvr_inheritance_state,
            outputs=dvr_inheritance_result
        ).then(
            lambda: (gr.update(visible=False), {}),
            outputs=[dvr_location_inheritance_modal, dvr_inheritance_state]
        )
        
        update_dvr_only_btn.click(
            lambda state: update_dvr_location_sync(
                state.get('dvr_id'), state.get('latitude'), state.get('longitude'), 
                state.get('address', ''), False
            ) if state else "❌ No DVR data available",
            inputs=dvr_inheritance_state,
            outputs=dvr_inheritance_result
        ).then(
            lambda: (gr.update(visible=False), {}),
            outputs=[dvr_location_inheritance_modal, dvr_inheritance_state]
        )
        
        cancel_inheritance_btn.click(
            lambda: (gr.update(visible=False), {}, ""),
            outputs=[dvr_location_inheritance_modal, dvr_inheritance_state, dvr_inheritance_result]
        )
        
        # Camera editing event handlers
        edit_camera_btn.click(
            lambda: gr.update(visible=True),
            outputs=camera_id_input_modal
        )
        
        cancel_camera_id_btn.click(
            lambda: gr.update(visible=False),
            outputs=camera_id_input_modal
        )
        
        load_camera_btn.click(
            open_camera_edit_modal,
            inputs=camera_id_input,
            outputs=[
                edit_camera_modal, edit_cam_dvr_dropdown, edit_camera_id,
                edit_cam_location, edit_cam_name, edit_cam_mac, edit_cam_ip,
                edit_cam_group, edit_cam_date, edit_cam_memory, edit_cam_custom_name,
                edit_cam_address, edit_cam_lat, edit_cam_lon, edit_cam_memory_reset,
                edit_camera_result
            ]
        ).then(
            lambda: gr.update(visible=False),
            outputs=camera_id_input_modal
        )
        
        cancel_edit_camera_btn.click(
            lambda: gr.update(visible=False),
            outputs=edit_camera_modal
        )
        
        update_camera_btn.click(
            update_camera_sync,
            inputs=[
                edit_camera_id, edit_cam_location, edit_cam_name, edit_cam_mac, edit_cam_ip,
                edit_cam_group, edit_cam_date, edit_cam_dvr_dropdown, edit_cam_lat, edit_cam_lon,
                edit_cam_memory, edit_cam_memory_reset, edit_cam_custom_name, edit_cam_address
            ],
            outputs=edit_camera_result
        )
        
        update_camera_with_inheritance_btn.click(
            update_camera_with_inheritance_sync,
            inputs=[
                edit_camera_id, edit_cam_location, edit_cam_name, edit_cam_mac, edit_cam_ip,
                edit_cam_group, edit_cam_date, edit_cam_dvr_dropdown, edit_cam_lat, edit_cam_lon,
                edit_cam_memory, edit_cam_memory_reset, edit_cam_custom_name, edit_cam_address
            ],
            outputs=edit_camera_result
        )
        
        # Map handlers for the old map tab (keeping for compatibility)
        refresh_map_btn.click(
            lambda: create_interactive_map(),
            outputs=map_display
        )
        
        update_coords_btn.click(
            update_device_coordinates,
            inputs=[update_device_id, update_device_type, update_lat, update_lon],
            outputs=update_result
        )
        
        ping_device_btn.click(
            test_connection,
            inputs=ping_ip,
            outputs=ping_result
        )
        
        # Enhanced map coordinate update handler
        update_coords_btn.click(
            update_device_coordinates,
            inputs=[device_id_input, device_type_input, new_lat_input, new_lon_input],
            outputs=coord_update_result
        )
        
        # Initialize enhanced map on load
        async def initialize_enhanced_map():
            """Initialize the enhanced map when the app loads."""
            try:
                return await map_manager.create_enhanced_map()
            except Exception as e:
                return f"<div style='color: red; padding: 20px;'>❌ Error initializing enhanced map: {str(e)}</div>"
        
        # Initialize dashboard and enhanced map on load
        app.load(
            update_stats_sync,
            outputs=[camera_stat, dvr_stat, actions_stat, memory_stat, cameras_df, dvrs_df]
        )
        
        app.load(
            initialize_enhanced_map_sync,
            outputs=enhanced_map_html
        )
        
        # Initialize configuration list on load
        app.load(
            list_all_configurations_sync,
            outputs=config_list_display
        )
    
    return app

# Main execution
if __name__ == "__main__":
    # Initialize database
    asyncio.run(init_db())
    
    # Create and launch the app
    app = create_dashboard()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )

# DVR Management Functions
async def assign_camera_to_dvr_async(camera_id, dvr_id, inherit_location=True):
    """Assign camera to DVR with location inheritance."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        result = await dvr_manager.assign_camera_to_dvr(
            camera_id=camera_id,
            dvr_id=dvr_id,
            inherit_location=inherit_location
        )
        
        if result['success']:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Error assigning camera to DVR: {str(e)}"

def assign_camera_to_dvr(camera_id, dvr_id, inherit_location=True):
    """Synchronous wrapper for camera-DVR assignment."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(assign_camera_to_dvr_async(camera_id, dvr_id, inherit_location))
        loop.close()
        return result
    except Exception as e:
        return f"❌ Error assigning camera to DVR: {str(e)}"

async def propagate_dvr_location_async(dvr_id, force_update=False):
    """Propagate DVR location to assigned cameras."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        result = await dvr_manager.propagate_dvr_location_to_cameras(
            dvr_id=dvr_id,
            force_update=force_update
        )
        
        if result['success']:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Error propagating DVR location: {str(e)}"

def propagate_dvr_location(dvr_id, force_update=False):
    """Synchronous wrapper for DVR location propagation."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(propagate_dvr_location_async(dvr_id, force_update))
        loop.close()
        return result
    except Exception as e:
        return f"❌ Error propagating DVR location: {str(e)}"

async def get_dvr_with_cameras_async(dvr_id):
    """Get DVR details with assigned cameras."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        result = await dvr_manager.get_dvr_with_cameras(dvr_id)
        
        if result:
            return result
        else:
            return {"dvr": None, "cameras": [], "camera_count": 0}
            
    except Exception as e:
        print(f"Error getting DVR with cameras: {e}")
        return {"dvr": None, "cameras": [], "camera_count": 0}

def get_dvr_with_cameras(dvr_id):
    """Synchronous wrapper for getting DVR with cameras."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_dvr_with_cameras_async(dvr_id))
        loop.close()
        return result
    except Exception as e:
        print(f"Error getting DVR with cameras: {e}")
        return {"dvr": None, "cameras": [], "camera_count": 0}

async def get_dvr_choices_async():
    """Get DVR choices for dropdown."""
    try:
        return await get_dvr_dropdown_choices()
    except Exception as e:
        print(f"Error getting DVR choices: {e}")
        return [("No DVR", None)]

def get_dvr_choices():
    """Synchronous wrapper for getting DVR choices."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_dvr_choices_async())
        loop.close()
        return result
    except Exception as e:
        print(f"Error getting DVR choices: {e}")
        return [("No DVR", None)]

async def update_dvr_location_async(dvr_id, latitude, longitude, address=""):
    """Update DVR location and optionally propagate to cameras."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        result = await dvr_manager.update_dvr_location(
            dvr_id=dvr_id,
            latitude=latitude,
            longitude=longitude,
            address=address
        )
        
        if result['success']:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"
            
    except Exception as e:
        return f"❌ Error updating DVR location: {str(e)}"

def update_dvr_location(dvr_id, latitude, longitude, address=""):
    """Synchronous wrapper for DVR location update."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(update_dvr_location_async(dvr_id, latitude, longitude, address))
        loop.close()
        return result
    except Exception as e:
        return f"❌ Error updating DVR location: {str(e)}"

# Enhanced search functions for DVRs
async def search_dvrs_async(search_term):
    """Search DVRs using the DVRManager."""
    try:
        dvr_manager = DVRManager(DB_NAME)
        dvrs = await dvr_manager.search_dvrs(search_term)
        
        # Convert to DataFrame format
        rows = []
        for dvr in dvrs:
            rows.append([
                dvr.id,
                dvr.get_display_name(),
                dvr.dvr_type,
                dvr.location,
                dvr.ip_address,
                dvr.mac_address,
                dvr.storage_capacity,
                dvr.date_installed
            ])
        
        columns = ["ID", "Name", "Type", "Location", "IP Address", "MAC Address", "Storage", "Date Installed"]
        return pd.DataFrame(rows, columns=columns)
        
    except Exception as e:
        print(f"Error searching DVRs: {e}")
        return pd.DataFrame()

def search_dvrs(search_term):
    """Synchronous wrapper for DVR search."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(search_dvrs_async(search_term))
        loop.close()
        return result
    except Exception as e:
        print(f"Error searching DVRs: {e}")
        return pd.DataFrame()

# Location click functionality
def generate_location_click_javascript():
    """Generate JavaScript for location click functionality."""
    return """
    <script>
    function openDVRLocation(dvrId) {
        console.log('Opening DVR location for ID:', dvrId);
        // This will be integrated with the map interface
        if (window.focusMapOnDVR) {
            window.focusMapOnDVR(dvrId);
        } else {
            alert('DVR Location - ID: ' + dvrId + '\\nThis feature will focus the map on the DVR location.');
        }
    }
    
    function openCameraLocation(cameraId) {
        console.log('Opening camera location for ID:', cameraId);
        // This will be integrated with the map interface
        if (window.focusMapOnCamera) {
            window.focusMapOnCamera(cameraId);
        } else {
            alert('Camera Location - ID: ' + cameraId + '\\nThis feature will focus the map on the camera location.');
        }
    }
    
    // Add these functions to the global window object
    window.openDVRLocation = openDVRLocation;
    window.openCameraLocation = openCameraLocation;
    </script>
    """