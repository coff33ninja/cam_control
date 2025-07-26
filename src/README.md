# Source Code Documentation

This directory contains the core source code modules for the Interactive Camera Mapping System.

## 📁 Module Overview

### 🗺️ Mapping and Visualization
- **`interactive_map_manager.py`** - Core interactive mapping functionality with drag-and-drop
- **`coverage_calculator.py`** - Camera coverage area calculations and geometry
- **`map_configuration_manager.py`** - Save/load map configurations and layouts

### 📹 Camera Management
- **`enhanced_camera_models.py`** - Enhanced camera data models with coverage parameters
- **`camera_viewer.py`** - RTSP camera stream viewing functionality
- **`camera_api.py`** - API endpoints for camera operations
- **`device_manager.py`** - Device information and manufacturer data management

### 📺 DVR Management
- **`dvr_manager.py`** - Complete DVR management system with CRUD operations

### 📍 Location Services
- **`location_detector.py`** - Script location detection using IP geolocation
- **`address_converter.py`** - Address to coordinate conversion with geocoding

### 🔗 Connectivity and Monitoring
- **`connectivity_monitor.py`** - Real-time device connectivity monitoring
- **`rtsp_proxy.py`** - RTSP streaming proxy for bandwidth optimization

### 🛡️ Error Handling and Validation
- **`error_handling.py`** - Comprehensive error handling and validation framework

## 🔧 Module Dependencies

```
interactive_map_manager.py
├── enhanced_camera_models.py
├── coverage_calculator.py
├── location_detector.py
└── error_handling.py

dvr_manager.py
├── enhanced_camera_models.py
└── error_handling.py

camera_viewer.py
├── device_manager.py
└── rtsp_proxy.py

connectivity_monitor.py
└── error_handling.py
```

## 📖 Usage Examples

### Interactive Map Manager
```python
from src.interactive_map_manager import InteractiveMapManager

# Create map manager
map_manager = InteractiveMapManager("camera_data.db")

# Generate interactive map
map_html = await map_manager.create_enhanced_map()

# Handle camera movement
result = await map_manager.handle_camera_move(camera_id=1, lat=40.7128, lon=-74.0060)
```

### DVR Manager
```python
from src.dvr_manager import DVRManager

# Create DVR manager
dvr_manager = DVRManager("camera_data.db")

# Create new DVR
result = await dvr_manager.create_dvr(
    custom_name="Main DVR",
    ip_address="192.168.1.100",
    dvr_type="16-Channel",
    location="Server Room"
)

# Assign camera to DVR with location inheritance
result = await dvr_manager.assign_camera_to_dvr(
    camera_id=1, 
    dvr_id=1, 
    inherit_location=True
)
```

### Location Detector
```python
from src.location_detector import LocationDetector

# Create location detector
detector = LocationDetector("camera_data.db")

# Detect script location
result = await detector.detect_script_location()
print(f"Detected location: {result.latitude}, {result.longitude}")
```

### Coverage Calculator
```python
from src.coverage_calculator import CoverageCalculator

# Calculate circular coverage
coordinates = CoverageCalculator.calculate_circular_coverage(
    lat=40.7128, 
    lon=-74.0060, 
    radius=50.0
)

# Calculate directional coverage
coordinates = CoverageCalculator.calculate_directional_coverage(
    lat=40.7128, 
    lon=-74.0060, 
    radius=50.0,
    direction=45.0,  # Northeast
    angle=90.0       # 90-degree field of view
)
```

### Enhanced Camera Models
```python
from src.enhanced_camera_models import EnhancedCamera

# Create camera with coverage parameters
camera = EnhancedCamera(
    id=1,
    name="CAM-001",
    custom_name="Front Door Camera",
    location="Main Entrance",
    ip_address="192.168.1.50",
    mac_address="00:1A:2B:3C:4D:5E",
    latitude=40.7128,
    longitude=-74.0060,
    coverage_radius=50.0,
    field_of_view_angle=90.0,
    coverage_direction=45.0
)

# Get map marker configuration
marker_config = camera.to_map_marker()

# Validate camera data
if camera.is_valid():
    print("Camera data is valid")
else:
    errors = camera.get_validation_errors()
    print(f"Validation errors: {errors}")
```

## 🧪 Testing

Each module has corresponding tests in the `tests/` directory:

```bash
# Test specific modules
python -m pytest tests/test_location_detection.py -v
python -m pytest tests/test_address_conversion.py -v
python -m pytest tests/test_dvr_management.py -v
```

## 🔄 Database Schema

The modules work with the following database tables:

- **`cameras`** - Camera information with coverage parameters
- **`dvrs`** - DVR information and configuration
- **`script_locations`** - Detected script execution locations
- **`device_info`** - Device manufacturer and model information
- **`map_configurations`** - Saved map layouts and configurations
- **`action_log`** - System action logging

## 🛠️ Development Guidelines

### Adding New Modules
1. Follow the existing naming convention
2. Include comprehensive docstrings
3. Add type hints for all functions
4. Create corresponding tests
5. Update this README

### Error Handling
- Use the `error_handling.py` module for consistent error handling
- Return structured error responses with success/failure status
- Log errors appropriately for debugging

### Database Operations
- Use async/await for all database operations
- Implement proper transaction handling
- Include rollback mechanisms for critical operations

### Validation
- Validate all input parameters
- Use the validation methods in data models
- Provide clear error messages for validation failures