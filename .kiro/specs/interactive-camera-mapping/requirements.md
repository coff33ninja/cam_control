# Requirements Document

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

## Introduction

The Interactive Camera Mapping System is a comprehensive security camera management platform that provides real-time monitoring, interactive mapping, and advanced visualization capabilities. The system enables users to manage cameras and DVRs through an intuitive web interface with drag-and-drop functionality, coverage area visualization, and real-time connectivity monitoring.

## Requirements

### Requirement 1: Core System Setup and Database Management

**User Story:** As a system administrator, I want a properly initialized database system with all required tables and relationships, so that the application can store and manage camera, DVR, and location data reliably.

#### Acceptance Criteria

1. WHEN the system is first installed THEN the database SHALL be initialized with all required tables (cameras, dvrs, script_locations, action_log, map_configurations, device_info)
2. WHEN database migrations are run THEN the system SHALL add missing columns and maintain data integrity
3. WHEN the database schema is validated THEN all foreign key constraints SHALL be properly configured
4. WHEN coordinate data is stored THEN the system SHALL validate latitude/longitude bounds (-90 to 90, -180 to 180)
5. WHEN IP/MAC addresses are stored THEN the system SHALL validate proper network address formats
6. WHEN dates are stored THEN the system SHALL enforce ISO date format compliance

### Requirement 2: Interactive Mapping and Visualization

**User Story:** As a security operator, I want an interactive map that displays cameras and DVRs with coverage areas, so that I can visualize the security system layout and make informed decisions about camera placement.

#### Acceptance Criteria

1. WHEN the map loads THEN the system SHALL display cameras and DVRs as interactive markers
2. WHEN a camera has coverage parameters THEN the system SHALL display circular or directional coverage areas
3. WHEN multiple map layers are available THEN the user SHALL be able to switch between OpenStreetMap, Terrain, Light, and Dark themes
4. WHEN the script location is detected THEN the map SHALL center on the detected coordinates with appropriate zoom level
5. WHEN location detection fails THEN the system SHALL use default location (New York City) and notify the user
6. WHEN devices have connectivity status THEN markers SHALL be color-coded (green for online, red for offline)

### Requirement 3: Drag-and-Drop Functionality

**User Story:** As a security operator, I want to drag camera and DVR markers to new positions on the map, so that I can quickly update device locations and see coverage changes in real-time.

#### Acceptance Criteria

1. WHEN a user drags a camera marker THEN the system SHALL update the camera's coordinates in the database
2. WHEN a camera is moved THEN the coverage area SHALL update in real-time during the drag operation
3. WHEN coordinate updates succeed THEN the system SHALL display a confirmation message with new coordinates
4. WHEN coordinate updates fail THEN the system SHALL revert the marker to its original position
5. WHEN JavaScript errors occur THEN the system SHALL enable fallback mode with read-only map functionality
6. WHEN drag operations are performed THEN the system SHALL validate coordinate bounds before saving

### Requirement 4: Camera Management System

**User Story:** As a security administrator, I want comprehensive camera management capabilities with validation and custom naming, so that I can efficiently organize and maintain the camera inventory.

#### Acceptance Criteria

1. WHEN creating a camera THEN the system SHALL validate all required fields (location, name, MAC, IP, date)
2. WHEN updating camera properties THEN the system SHALL maintain data integrity and log changes
3. WHEN deleting a camera THEN the system SHALL perform proper cleanup and update related records
4. WHEN searching for cameras THEN the system SHALL find devices by name, IP, location, or custom name
5. WHEN custom names are assigned THEN the system SHALL use custom names with fallback to default naming
6. WHEN coverage parameters are set THEN the system SHALL validate radius (1-10000m), angle (1-360°), and direction (0-359°)

### Requirement 5: DVR Management and Location Inheritance

**User Story:** As a security administrator, I want DVR management with automatic location inheritance for assigned cameras, so that I can organize cameras by DVR and reduce manual coordinate entry.

#### Acceptance Criteria

1. WHEN creating a DVR THEN the system SHALL validate required fields and prevent duplicate IP/MAC addresses
2. WHEN assigning a camera to a DVR THEN the camera SHALL inherit the DVR's location if no camera location is specified
3. WHEN updating DVR locations THEN assigned cameras SHALL optionally inherit the new location
4. WHEN displaying the map THEN visual connections SHALL show relationships between DVRs and cameras
5. WHEN DVRs have custom names THEN the system SHALL use custom names with intelligent fallback
6. WHEN unassigning cameras from DVRs THEN the system SHALL maintain camera location data

### Requirement 6: Connectivity Monitoring and Status Display

**User Story:** As a security operator, I want real-time connectivity monitoring with visual status indicators, so that I can quickly identify offline devices and take corrective action.

#### Acceptance Criteria

1. WHEN testing device connectivity THEN the system SHALL use ping to determine online/offline status
2. WHEN connectivity status is determined THEN the system SHALL cache results for 30 seconds to improve performance
3. WHEN displaying devices on the map THEN markers SHALL be color-coded based on connectivity status
4. WHEN connectivity tests fail THEN the system SHALL provide clear error messages
5. WHEN real-time monitoring is active THEN status updates SHALL refresh automatically
6. WHEN network errors occur THEN the system SHALL handle failures gracefully without crashing

### Requirement 7: RTSP Streaming and Camera Viewing

**User Story:** As a security operator, I want to view live camera streams through RTSP with bandwidth optimization, so that I can monitor camera feeds without overwhelming the network.

#### Acceptance Criteria

1. WHEN clicking a camera marker THEN the system SHALL open a camera viewer with RTSP stream
2. WHEN multiple streams are active THEN the system SHALL use proxy server for bandwidth optimization
3. WHEN device information is available THEN the system SHALL display manufacturer, model, and serial numbers
4. WHEN auto-detection runs THEN the system SHALL identify device manufacturers and models
5. WHEN stream sessions are created THEN the system SHALL manage up to 50 concurrent sessions
6. WHEN streams fail to load THEN the system SHALL provide clear error messages and fallback options

### Requirement 8: Error Handling and Validation

**User Story:** As a system user, I want comprehensive error handling with clear validation messages, so that I can understand and correct input errors quickly.

#### Acceptance Criteria

1. WHEN invalid coordinates are entered THEN the system SHALL provide specific error messages about valid ranges
2. WHEN database operations fail THEN the system SHALL perform automatic rollback and retry with exponential backoff
3. WHEN JavaScript errors occur THEN the system SHALL enable read-only fallback mode
4. WHEN validation fails THEN error messages SHALL specify the field, current value, and required format
5. WHEN network operations timeout THEN the system SHALL provide retry options
6. WHEN critical errors occur THEN the system SHALL log errors for debugging while maintaining user experience

### Requirement 9: Configuration Management and Data Persistence

**User Story:** As a security administrator, I want to save and restore camera layouts and system configurations, so that I can maintain consistent setups and recover from changes.

#### Acceptance Criteria

1. WHEN saving a layout THEN the system SHALL store camera positions and coverage parameters
2. WHEN loading a configuration THEN the system SHALL restore camera positions and validate data integrity
3. WHEN exporting data THEN the system SHALL provide CSV format for cameras and DVRs
4. WHEN importing data THEN the system SHALL validate format and prevent duplicate entries
5. WHEN configurations are managed THEN the system SHALL maintain version history
6. WHEN system settings change THEN the system SHALL persist changes across application restarts

### Requirement 10: Performance and Scalability

**User Story:** As a system administrator, I want the system to perform efficiently with large datasets and concurrent users, so that response times remain acceptable as the system scales.

#### Acceptance Criteria

1. WHEN handling large camera datasets THEN map rendering SHALL complete within 5 seconds
2. WHEN multiple users access the system THEN database connections SHALL be managed efficiently
3. WHEN drag operations are performed THEN coordinate updates SHALL complete within 1 second
4. WHEN caching is implemented THEN location and connectivity results SHALL improve response times
5. WHEN memory usage is monitored THEN the system SHALL not exhibit memory leaks during long-running sessions
6. WHEN database queries are executed THEN proper indexing SHALL ensure optimal performance
