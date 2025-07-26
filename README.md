# Interactive Camera Mapping System

A comprehensive security camera management system with interactive mapping, real-time monitoring, and advanced visualization capabilities.

> **⚠️ DEVELOPMENT STATUS**: This is an initial implementation and proof of concept. Not all features have been thoroughly tested and some functionality may be incomplete or require additional setup. Use for development and testing purposes.

## 🚀 Features

### 📹 Camera Management
- **CRUD Operations**: Create, read, update, and delete cameras with comprehensive validation
- **Custom Naming**: Assign custom names to cameras with fallback to default naming
- **Coverage Visualization**: Interactive coverage areas with circular and directional patterns
- **Real-time Monitoring**: Live connectivity status with automatic refresh
- **Memory Card Tracking**: Monitor memory card status and reset dates

### 📺 DVR Management
- **DVR Integration**: Full DVR management with camera assignment capabilities
- **Location Inheritance**: Cameras inherit DVR locations when not specified
- **Visual Connections**: Map visualization showing DVR-camera relationships
- **Custom Naming**: Custom names for DVRs with intelligent fallback

### 🗺️ Interactive Mapping
- **Drag & Drop**: Move cameras and DVRs by dragging markers on the map
- **Real-time Updates**: Coverage areas update instantly during drag operations
- **Multiple Map Layers**: OpenStreetMap, Terrain, Light, and Dark themes
- **Connectivity Status**: Color-coded markers showing online/offline status
- **Location Detection**: Automatic script location detection for map centering

### 📍 Location Services
- **Address Conversion**: Convert addresses to coordinates with geocoding
- **Location Detection**: IP-based and timezone-based location detection
- **Coordinate Validation**: Comprehensive coordinate validation and error handling
- **Caching System**: Efficient caching for geocoding and location services

### 🎥 Camera Viewing
- **RTSP Integration**: View camera streams via RTSP protocol
- **Pop-out Viewer**: Click cameras on map to open stream viewer
- **Device Information**: Display manufacturer, model, and serial numbers
- **Proxy Support**: Bandwidth-efficient streaming through proxy server

### ⚙️ Configuration Management
- **Save/Load Layouts**: Save and restore camera positions and configurations
- **Batch Operations**: Bulk operations for multiple cameras
- **Import/Export**: CSV import/export for camera and DVR data
- **Database Migration**: Automatic schema updates and migrations

## 📁 Project Structure

```
├── src/                          # Core source code modules
│   ├── address_converter.py     # Address to coordinate conversion
│   ├── camera_api.py            # Camera API endpoints
│   ├── camera_viewer.py         # RTSP camera viewing
│   ├── connectivity_monitor.py  # Real-time connectivity monitoring
│   ├── coverage_calculator.py   # Coverage area calculations
│   ├── device_manager.py        # Device information management
│   ├── dvr_manager.py           # DVR management system
│   ├── enhanced_camera_models.py # Enhanced camera data models
│   ├── error_handling.py        # Comprehensive error handling
│   ├── interactive_map_manager.py # Interactive map functionality
│   ├── location_detector.py     # Location detection service
│   ├── map_configuration_manager.py # Configuration management
│   └── rtsp_proxy.py            # RTSP streaming proxy
├── tests/                        # Unit and integration tests
├── test_scripts/                 # Test and validation scripts
├── docs/                         # Documentation files
├── demos/                        # Demo applications
├── Manager.py                    # Main Gradio application
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- SQLite 3
- FFmpeg (for RTSP streaming)

### Setup
1. **Clone the repository**
   ```bash
   git clone https://github.com/coff33ninja/cam_control
   cd Camera_Inventory_Manager
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database**
   ```bash
   python init_database.py
   ```

5. **Run the application**
   ```bash
   python Manager.py
   ```

## 🚀 Quick Start

1. **Launch the application**
   ```bash
   python Manager.py
   ```

2. **Access the web interface**
   - Open your browser to the displayed URL (typically `http://localhost:7860`)

3. **Add your first camera**
   - Go to "Camera Management" tab
   - Click "Add Camera"
   - Fill in the required information
   - Optionally add coordinates or address for map visualization

4. **View the interactive map**
   - Go to "Interactive Map" tab
   - See your cameras plotted on the map
   - Drag cameras to new positions
   - Click cameras to view live streams (if RTSP configured)

## 📖 Usage Guide

### Camera Management
- **Adding Cameras**: Use the Camera Management tab to add new cameras with all relevant details
- **Custom Names**: Assign meaningful names to cameras for easier identification
- **Coverage Settings**: Configure coverage radius, field of view, and direction
- **DVR Assignment**: Assign cameras to DVRs for organized management

### Interactive Mapping
- **Drag & Drop**: Click and drag camera/DVR markers to reposition them
- **Coverage Visualization**: See camera coverage areas with different colors for online/offline status
- **Map Layers**: Switch between different map styles using the layer control
- **Connectivity Status**: Green markers indicate online devices, red indicates offline

### DVR Management
- **DVR Setup**: Add DVRs with custom names and location information
- **Camera Assignment**: Assign cameras to DVRs for organized management
- **Location Inheritance**: Cameras without coordinates inherit DVR location
- **Visual Connections**: See connections between DVRs and cameras on the map

### Configuration Management
- **Save Layouts**: Save current camera positions and settings
- **Load Configurations**: Restore previously saved layouts
- **Export Data**: Export camera and DVR data to CSV files
- **Import Data**: Bulk import from CSV files

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_location_detection.py -v
python -m pytest tests/test_address_conversion.py -v
python -m pytest tests/test_dvr_management.py -v
python -m pytest tests/test_custom_naming_integration.py -v

# Run test scripts
python test_scripts/simple_test_task_22.py
```

## 🔧 Configuration

### Database Configuration
- Default database: `camera_data.db`
- Device information database: `device_info.db`
- Automatic schema migrations on startup

### Map Configuration
- Default map center: Auto-detected based on script location
- Fallback location: New York City (40.7128, -74.0060)
- Supported map layers: OpenStreetMap, Terrain, Light, Dark

### RTSP Configuration
- Default RTSP port: 554
- Proxy server for bandwidth optimization
- Support for multiple camera manufacturers

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the documentation in the `docs/` folder
- Run the test scripts in `test_scripts/` to validate your setup
- Review the error logs for troubleshooting information

## � VDevelopment Status

### ✅ **Implemented Features:**
- Basic camera and DVR management (CRUD operations)
- Interactive map with Folium integration
- Database schema and migrations
- Location detection and geocoding
- Coverage area calculations
- Drag-and-drop JavaScript framework (initial implementation)
- Comprehensive test suite structure

### ⚠️ **In Development / Needs Testing:**
- **Drag-and-drop functionality**: JavaScript implementation exists but requires thorough testing
- **Real-time coordinate updates**: Backend integration for drag operations
- **RTSP streaming**: Camera viewer implementation needs validation
- **Connectivity monitoring**: Real-time status updates
- **Configuration management**: Save/load functionality

### 🔧 **Known Issues:**
- Some JavaScript drag functionality may not work consistently across all browsers
- RTSP proxy server needs additional configuration
- Error handling could be more robust in some areas
- Performance optimization needed for large numbers of cameras

### 📋 **TODO:**
- Complete drag-and-drop backend integration
- Implement real-time WebSocket updates
- Add comprehensive error handling
- Performance testing with large datasets
- Cross-browser compatibility testing
- Documentation improvements

## 🔄 Version History

- **v0.1.0**: Initial implementation with core features and proof of concept

## 🙏 Acknowledgments

- Folium for interactive mapping capabilities
- Gradio for the web interface framework
- SQLite for reliable data storage
- OpenStreetMap for map tiles and data
