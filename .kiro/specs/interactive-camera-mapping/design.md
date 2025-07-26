# Design Document

## ⚠️ **CRITICAL: BACKUP INSTRUCTIONS**

**BEFORE MAKING ANY CHANGES TO THE CODEBASE, ALWAYS CREATE BACKUPS:**

### 🔄 **Pre-Implementation Backup Checklist**
- [ ] **Create Full System Backup**: `cp -r . ../interactive-camera-mapping-backup-$(date +%Y%m%d-%H%M%S)`
- [ ] **Backup Core Modules**: `cp -r src/ backups/src-backup-$(date +%Y%m%d-%H%M%S)/`
- [ ] **Backup Database**: `cp camera_data.db backups/camera_data-backup-$(date +%Y%m%d-%H%M%S).db`
- [ ] **Backup Main Application**: `cp Manager.py backups/Manager-backup-$(date +%Y%m%d-%H%M%S).py`
- [ ] **Backup Requirements**: `cp requirements.txt backups/requirements-backup-$(date +%Y%m%d-%H%M%S).txt`
- [ ] **Backup Test Scripts**: `cp -r test_scripts/ backups/test_scripts-backup-$(date +%Y%m%d-%H%M%S)/`

### 🧪 **Pre-Change Validation**
- [ ] **Test Current Imports**: Run `python -c "from src import *; print('All imports working')"`
- [ ] **Validate Dependencies**: Run `pip check` to verify all dependencies are satisfied
- [ ] **Test Core Functions**: Run `python test_scripts/simple_test_task_22.py` to validate current functionality
- [ ] **Database Schema Check**: Run `python test_scripts/verify_schema.py` to confirm database integrity
- [ ] **Module Import Test**: Run `python -c "import sys; sys.path.append('src'); from enhanced_camera_models import *; from interactive_map_manager import *; from dvr_manager import *; print('Core modules importable')"`

### 🔧 **Backup Commands**
```bash
# Create timestamped backup directory
mkdir -p backups/$(date +%Y%m%d-%H%M%S)

# Full system backup
tar -czf backups/full-system-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  --exclude='backups' \
  --exclude='__pycache__' \
  --exclude='.git' \
  .

# Core files backup
cp Manager.py backups/Manager-$(date +%Y%m%d-%H%M%S).py
cp requirements.txt backups/requirements-$(date +%Y%m%d-%H%M%S).txt
cp -r src/ backups/src-$(date +%Y%m%d-%H%M%S)/
cp -r tests/ backups/tests-$(date +%Y%m%d-%H%M%S)/
```

### 🚨 **NEVER MODIFY WITHOUT BACKUP**
- Core modules in `src/` directory
- Main application `Manager.py`
- Database files `*.db`
- Configuration files
- Test scripts and validation tools

---

## Overview

The Interactive Camera Mapping System is designed as a modular, scalable web application that provides comprehensive security camera management through an interactive web interface. The system follows a layered architecture with clear separation of concerns, utilizing Python for backend services, SQLite for data persistence, Gradio for the web interface, and Folium with custom JavaScript for interactive mapping.

## Architecture

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Interface Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Gradio UI     │  │  Interactive    │  │   RTSP Stream   │ │
│  │   Components    │  │   Map (Folium)  │  │    Viewer       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Camera        │  │      DVR        │  │   Interactive   │ │
│  │  Management     │  │   Management    │  │  Map Manager    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Connectivity   │  │   Location      │  │  Configuration  │ │
│  │   Monitor       │  │   Detector      │  │    Manager      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Data Access Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Enhanced      │  │      DVR        │  │    Error        │ │
│  │    Camera       │  │     Models      │  │   Handling      │ │
│  │    Models       │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                   Data Persistence Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Primary DB    │  │   Secondary DB  │  │   File System   │ │
│  │ (camera_data.db)│  │ (device_info.db)│  │   (Configs)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Web Interface Layer
- **Gradio UI Components**: Modern web interface with tabbed navigation
- **Interactive Map (Folium)**: JavaScript-enhanced maps with drag-and-drop
- **RTSP Stream Viewer**: Pop-out camera viewing windows

#### 2. Business Logic Layer
- **Camera Management**: CRUD operations, validation, custom naming
- **DVR Management**: DVR operations with location inheritance
- **Interactive Map Manager**: Map generation and coordinate updates
- **Connectivity Monitor**: Real-time device status monitoring
- **Location Detector**: IP-based and timezone-based location detection
- **Configuration Manager**: Save/load system configurations

#### 3. Data Access Layer
- **Enhanced Camera Models**: Rich data models with validation
- **DVR Models**: DVR data structures with relationships
- **Error Handling**: Comprehensive validation and error recovery

#### 4. Data Persistence Layer
- **Primary Database**: Main camera and DVR data storage
- **Secondary Database**: Device manufacturer information
- **File System**: Configuration files and cached data

## Components and Interfaces

### Database Schema

#### Primary Database (camera_data.db)

**cameras table:**
```sql
CREATE TABLE cameras (
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
    custom_name TEXT,
    address TEXT,
    FOREIGN KEY (dvr_id) REFERENCES dvrs(id)
);
```

**dvrs table:**
```sql
CREATE TABLE dvrs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    custom_name TEXT,
    dvr_type TEXT,
    location TEXT,
    ip_address TEXT NOT NULL UNIQUE,
    mac_address TEXT,
    storage_capacity TEXT,
    date_installed TEXT,
    latitude REAL,
    longitude REAL,
    address TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**script_locations table:**
```sql
CREATE TABLE script_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    detection_method TEXT,
    detected_at TEXT NOT NULL,
    is_current BOOLEAN DEFAULT 1,
    confidence_score REAL DEFAULT 1.0
);
```

**action_log table:**
```sql
CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id INTEGER,
    details TEXT
);
```

**map_configurations table:**
```sql
CREATE TABLE map_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    configuration_data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

#### Secondary Database (device_info.db)
- Device manufacturer information
- Model specifications
- Default RTSP configurations

### Core Interfaces

#### EnhancedCamera Model
```python
@dataclass
class EnhancedCamera:
    id: int
    name: str
    location: str
    ip_address: str
    mac_address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coverage_radius: float = 50.0
    field_of_view_angle: float = 360.0
    coverage_direction: float = 0.0
    custom_name: Optional[str] = None
    # ... additional fields
```

#### DVR Model
```python
@dataclass
class DVR:
    id: int
    custom_name: str
    ip_address: str
    dvr_type: str = "Unknown"
    location: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    # ... additional fields
```

#### InteractiveMapManager Interface
```python
class InteractiveMapManager:
    async def create_enhanced_map(self) -> str
    async def handle_camera_move(self, camera_id: int, lat: float, lon: float) -> Dict[str, Any]
    async def update_coverage_parameters(self, camera_id: int, params: Dict[str, float]) -> Dict[str, Any]
```

#### DVRManager Interface
```python
class DVRManager:
    async def create_dvr(self, **kwargs) -> Dict[str, Any]
    async def assign_camera_to_dvr(self, camera_id: int, dvr_id: int, inherit_location: bool = True) -> Dict[str, Any]
    async def propagate_dvr_location_to_cameras(self, dvr_id: int, force_update: bool = False) -> Dict[str, Any]
```

## Data Models

### Camera Coverage Model
```python
class CoverageArea:
    radius: float  # Coverage radius in meters (1-10000)
    field_of_view_angle: float  # Viewing angle in degrees (1-360)
    coverage_direction: float  # Direction in degrees (0-359)
    
    def calculate_circular_coverage(self) -> List[Tuple[float, float]]
    def calculate_directional_coverage(self) -> List[Tuple[float, float]]
```

### Location Detection Model
```python
class LocationResult:
    success: bool
    latitude: float
    longitude: float
    address: str
    detection_method: str
    confidence_score: float
    error_message: Optional[str]
```

### Validation Models
```python
class ValidationError:
    field: str
    value: Any
    message: str
    error_code: str
    severity: ErrorSeverity

class OperationResult:
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    errors: Optional[List[ValidationError]]
    retry_possible: bool
```

## Error Handling

### Error Categories
- **VALIDATION**: Input validation errors
- **DATABASE**: Database operation failures
- **NETWORK**: Connectivity and network errors
- **JAVASCRIPT**: Frontend interaction errors
- **COORDINATE**: Geographic coordinate errors
- **CONFIGURATION**: System configuration errors
- **SYSTEM**: General system errors

### Error Handling Strategy

#### Database Error Handling
```python
class DatabaseTransactionManager:
    @asynccontextmanager
    async def atomic_transaction(self):
        # Automatic rollback on exceptions
        # Retry logic with exponential backoff
        # Transaction isolation
```

#### JavaScript Error Handling
```python
class JavaScriptFallbackManager:
    def enable_fallback_mode(self, reason: str):
        # Switch to read-only map mode
        # Display user notification
        # Maintain basic functionality
```

#### Coordinate Validation
```python
class CoordinateValidator:
    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> Tuple[bool, List[ValidationError]]:
        # Validate latitude bounds (-90 to 90)
        # Validate longitude bounds (-180 to 180)
        # Provide detailed error messages
```

## Testing Strategy

### Unit Testing
- **Location Detection**: Mock geolocation services
- **Address Conversion**: Mock geocoding APIs
- **DVR Management**: Database operation testing
- **Camera Models**: Validation and serialization testing

### Integration Testing
- **Map Generation**: End-to-end map creation
- **Drag-and-Drop**: JavaScript interaction testing
- **Database Migration**: Schema update testing
- **Configuration Management**: Save/load testing

### Performance Testing
- **Large Dataset Handling**: Test with 1000+ cameras
- **Concurrent Operations**: Multi-user simulation
- **Memory Usage**: Long-running session testing
- **Database Performance**: Query optimization validation

### Test Coverage Areas
```
✅ Fully Covered:
- Location detection with fallback methods
- Address conversion and geocoding
- DVR management CRUD operations
- Custom naming system integration
- Coordinate validation
- Error handling and validation

🔄 Partially Covered:
- Interactive map generation
- RTSP streaming functionality
- Database migration scripts
- Configuration management

📝 Future Coverage:
- Performance benchmarking
- Load testing with large datasets
- Cross-browser compatibility
- Security testing
```

## Security Considerations

### Input Validation
- SQL injection prevention through parameterized queries
- XSS prevention in web interface
- Coordinate bounds validation
- Network address format validation

### Data Protection
- Database transaction integrity
- Configuration file access control
- Error message sanitization
- Logging without sensitive data exposure

### Network Security
- RTSP stream access control
- IP address validation
- Ping operation rate limiting
- Proxy server security

## Performance Optimization

### Database Optimization
- Proper indexing on frequently queried columns
- Connection pooling for concurrent access
- Query optimization for large datasets
- Efficient pagination for large result sets

### Map Performance
- Marker clustering for large camera counts
- Lazy loading of coverage areas
- Efficient JavaScript for drag operations
- Caching of map tiles and data

### Caching Strategy
- Location detection results (1 hour TTL)
- Connectivity status (30 seconds TTL)
- Geocoding results (24 hours TTL)
- Map configuration data (session-based)

## Deployment Architecture

### System Requirements
- Python 3.8 or higher
- SQLite 3
- FFmpeg (for RTSP streaming)
- Modern web browser with JavaScript support

### File Structure
```
Camera_Inventory_Manager/
├── src/                          # Core source modules
│   ├── interactive_map_manager.py
│   ├── enhanced_camera_models.py
│   ├── dvr_manager.py
│   ├── error_handling.py
│   └── ...
├── tests/                        # Unit and integration tests
├── test_scripts/                 # Validation scripts
├── demos/                        # Demo applications
├── Manager.py                    # Main Gradio application
├── init_database.py             # Database initialization
├── database_migration.py        # Schema migrations
└── requirements.txt             # Python dependencies
```

### Configuration Management
- Environment-specific settings
- Database connection parameters
- Map service configurations
- RTSP proxy settings
- Logging configuration

This design provides a robust, scalable foundation for the Interactive Camera Mapping System with clear separation of concerns, comprehensive error handling, and extensive testing coverage.