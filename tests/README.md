# Test Suite Documentation

This directory contains comprehensive unit and integration tests for the Interactive Camera Mapping System.

## 🧪 Test Structure

### Unit Tests
- **`test_location_detection.py`** - Location detection service with mocked geolocation
- **`test_address_conversion.py`** - Address conversion and geocoding functionality
- **`test_dvr_management.py`** - DVR management system and location inheritance
- **`test_custom_naming_integration.py`** - Custom naming system across all components

### Test Categories

#### 🗺️ Location and Mapping Tests
- IP geolocation with multiple service fallbacks
- Timezone-based location estimation
- Address to coordinate conversion
- Coordinate validation and error handling
- Caching behavior for location services

#### 📺 DVR Management Tests
- DVR CRUD operations
- Location inheritance logic
- Camera-DVR assignment functionality
- Validation and error handling
- Custom naming integration

#### 📹 Camera System Tests
- Enhanced camera model validation
- Custom naming functionality
- Map marker generation
- Coverage parameter validation
- Serialization and deserialization

#### 🔗 Integration Tests
- Cross-component naming consistency
- Database integration
- Map visualization integration
- Error handling across modules

## 🚀 Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test Files
```bash
# Location detection tests
python -m pytest tests/test_location_detection.py -v

# Address conversion tests
python -m pytest tests/test_address_conversion.py -v

# DVR management tests
python -m pytest tests/test_dvr_management.py -v

# Custom naming integration tests
python -m pytest tests/test_custom_naming_integration.py -v
```

### Run Tests with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=html
```

### Run Tests by Category
```bash
# Run only location-related tests
python -m pytest tests/ -k "location" -v

# Run only DVR-related tests
python -m pytest tests/ -k "dvr" -v

# Run only validation tests
python -m pytest tests/ -k "validation" -v
```

## 📊 Test Coverage

### Current Coverage Areas

#### ✅ Fully Covered
- Location detection with multiple fallback methods
- Address conversion and geocoding
- DVR management CRUD operations
- Custom naming system integration
- Coordinate validation
- Error handling and validation

#### 🔄 Partially Covered
- Interactive map generation (tested via unit tests)
- RTSP streaming functionality
- Database migration scripts
- Configuration management

#### 📝 Test Scenarios

### Location Detection Tests
- **Successful IP geolocation** - Tests multiple geolocation services
- **Service fallback behavior** - Tests fallback when services fail
- **Timezone estimation** - Tests timezone-based location detection
- **Caching functionality** - Tests location result caching
- **Coordinate validation** - Tests coordinate boundary validation
- **Error handling** - Tests error scenarios and recovery

### Address Conversion Tests
- **Geocoding success** - Tests address to coordinate conversion
- **Reverse geocoding** - Tests coordinate to address conversion
- **Batch processing** - Tests bulk address conversion
- **Cache management** - Tests geocoding result caching
- **Format validation** - Tests address format validation
- **Service integration** - Tests with mocked geocoding services

### DVR Management Tests
- **CRUD operations** - Create, read, update, delete DVRs
- **Location inheritance** - Camera location inheritance from DVRs
- **Assignment management** - Camera-DVR assignment functionality
- **Validation logic** - IP, MAC, coordinate validation
- **Custom naming** - DVR custom name functionality
- **Error scenarios** - Invalid data handling

### Custom Naming Integration Tests
- **Display name logic** - Custom name fallback behavior
- **Cross-component consistency** - Naming consistency across modules
- **Serialization** - Name preservation in data serialization
- **Map integration** - Custom names in map markers
- **Validation** - Custom name format validation

## 🛠️ Test Utilities

### Fixtures
- **`temp_db`** - Temporary database for isolated testing
- **`sample_camera`** - Pre-configured camera for testing
- **`sample_dvr`** - Pre-configured DVR for testing
- **`converter`** - Address converter instance
- **`detector`** - Location detector instance

### Mocking
- **Geolocation services** - Mocked HTTP responses
- **Database operations** - Isolated database testing
- **Network requests** - Controlled network behavior
- **Time-dependent operations** - Consistent time-based testing

## 📋 Test Data

### Sample Coordinates
- **New York City**: 40.7128, -74.0060
- **Los Angeles**: 34.0522, -118.2437
- **Chicago**: 41.8781, -87.6298
- **London**: 51.5074, -0.1278

### Sample Addresses
- "123 Main Street, New York, NY 10001"
- "1600 Pennsylvania Avenue, Washington, DC"
- "Times Square, New York"
- "Golden Gate Bridge, San Francisco, CA"

### Sample Device Data
- **IP Addresses**: 192.168.1.x range for testing
- **MAC Addresses**: Valid format with different manufacturers
- **Device Names**: Various naming patterns and edge cases

## 🔍 Test Debugging

### Verbose Output
```bash
python -m pytest tests/ -v -s
```

### Debug Specific Test
```bash
python -m pytest tests/test_location_detection.py::TestLocationDetector::test_detect_script_location_success -v -s
```

### Test with Debugging
```bash
python -m pytest tests/ --pdb
```

## 📈 Performance Testing

### Load Testing
```bash
# Test with multiple concurrent operations
python -m pytest tests/ -n auto
```

### Memory Testing
```bash
# Test for memory leaks
python -m pytest tests/ --memray
```

## 🚨 Common Test Issues

### Database Locks
- Tests use temporary databases to avoid conflicts
- Each test gets a fresh database instance
- Proper cleanup in fixtures

### Async Testing
- All async functions tested with `@pytest.mark.asyncio`
- Proper event loop handling
- Timeout handling for long-running operations

### Mock Configuration
- Consistent mock setup across tests
- Proper mock cleanup after tests
- Realistic mock responses

## 📝 Adding New Tests

### Test File Structure
```python
#!/usr/bin/env python3
"""
Test description
"""

import pytest
import asyncio
# ... other imports

class TestClassName:
    """Test suite description."""
    
    @pytest.fixture
    def fixture_name(self):
        """Fixture description."""
        # Setup code
        yield test_object
        # Cleanup code
    
    def test_function_name(self, fixture_name):
        """Test description."""
        # Test implementation
        assert expected == actual
    
    @pytest.mark.asyncio
    async def test_async_function(self, fixture_name):
        """Async test description."""
        result = await async_function()
        assert result.success == True
```

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`
- Fixtures: `<object_name>` or `<object_name>_<variant>`

### Best Practices
1. **Isolation** - Each test should be independent
2. **Clarity** - Test names should describe the scenario
3. **Coverage** - Test both success and failure cases
4. **Performance** - Keep tests fast and efficient
5. **Maintenance** - Update tests when code changes