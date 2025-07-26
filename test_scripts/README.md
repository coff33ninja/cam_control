# Test Scripts

This directory contains validation and testing scripts for the Interactive Camera Mapping System.

## 🧪 Available Test Scripts

### Core Functionality Tests
- **`simple_test_task_22.py`** - Quick syntax and functionality validation
- **`test_task_22.py`** - Comprehensive Task 22 implementation testing
- **`test_task_23.py`** - Camera viewer and RTSP functionality testing

### Location and Integration Tests
- **`test_location_integration.py`** - Location detection integration testing
- **`test_location_refresh.py`** - Location refresh functionality testing
- **`test_task_21_implementation.py`** - DVR location inheritance testing

### Database and Schema Tests
- **`verify_schema.py`** - Database schema verification

## 🚀 Running Test Scripts

### Quick Validation
```bash
# Run quick syntax and functionality test
python test_scripts/simple_test_task_22.py

# Verify database schema
python test_scripts/verify_schema.py
```

### Comprehensive Testing
```bash
# Test Task 22 implementation (DVR visualization)
python test_scripts/test_task_22.py

# Test Task 23 implementation (Camera viewer)
python test_scripts/test_task_23.py

# Test Task 21 implementation (DVR location inheritance)
python test_scripts/test_task_21_implementation.py
```

### Location Testing
```bash
# Test location detection integration
python test_scripts/test_location_integration.py

# Test location refresh functionality
python test_scripts/test_location_refresh.py
```

## 📋 Test Script Details

### simple_test_task_22.py
**Purpose**: Quick validation of Task 22 implementation
**Features**:
- Syntax checking for core modules
- Feature implementation verification
- Requirements compliance checking
- Quick pass/fail results

**Output Example**:
```
🚀 Starting Task 22 Implementation Tests
✅ src/interactive_map_manager.py - Syntax OK
✅ src/enhanced_camera_models.py - Syntax OK
✅ DVR marker styling
✅ Visual connections
📊 Implementation score: 9/9 features implemented
```

### test_task_22.py
**Purpose**: Comprehensive testing of DVR visualization features
**Features**:
- DVR marker creation testing
- Connection visualization testing
- Enhanced camera model testing
- Map creation with DVR enhancements

### test_task_23.py
**Purpose**: Camera viewer and RTSP functionality testing
**Features**:
- Camera viewer component testing
- RTSP proxy functionality
- Device manager integration
- API endpoint validation

### Location Test Scripts
**Purpose**: Validate location detection and integration
**Features**:
- IP geolocation testing
- Location refresh mechanisms
- Map centering functionality
- Error handling validation

## 📊 Test Results Interpretation

### Success Indicators
- ✅ Green checkmarks indicate passing tests
- 📊 Score summaries show implementation completeness
- 🎉 Success messages confirm functionality

### Failure Indicators
- ❌ Red X marks indicate failing tests
- ⚠️ Warning symbols show potential issues
- Error messages provide debugging information

## 🔧 Troubleshooting

### Common Issues

#### Import Errors
```bash
# If you see import errors, ensure you're in the project root
cd /path/to/Camera_Inventory_Manager
python test_scripts/script_name.py
```

#### Database Errors
```bash
# Initialize database if needed
python init_database.py
```

#### Missing Dependencies
```bash
# Install required packages
pip install -r requirements.txt
```

### Debug Mode
Most test scripts support verbose output:
```bash
python test_scripts/test_task_22.py --verbose
```

## 📈 Performance Testing

### Load Testing
Some scripts include performance testing:
```bash
# Test with multiple cameras
python test_scripts/test_task_22.py --cameras=100
```

### Memory Testing
Monitor memory usage during tests:
```bash
# Run with memory monitoring
python -m memory_profiler test_scripts/test_task_22.py
```

## 🔄 Adding New Test Scripts

### Script Template
```python
#!/usr/bin/env python3
"""
Test Script Description
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_functionality():
    """Test specific functionality."""
    try:
        # Test implementation
        print("✅ Test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main test execution."""
    print("🚀 Starting Test Script")
    
    success = test_functionality()
    
    if success:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Best Practices
1. **Clear Output** - Use emoji and clear messages
2. **Error Handling** - Catch and report errors gracefully
3. **Documentation** - Include docstrings and comments
4. **Exit Codes** - Return appropriate exit codes
5. **Modularity** - Break tests into logical functions

## 📝 Test Script Maintenance

### Regular Updates
- Update test scripts when features change
- Add new tests for new functionality
- Remove obsolete tests
- Update expected results

### Version Compatibility
- Test scripts should work with current codebase
- Update imports when modules are reorganized
- Maintain backward compatibility where possible

## 🎯 Test Coverage

### Current Coverage
- ✅ Core module syntax validation
- ✅ DVR visualization features
- ✅ Camera viewer functionality
- ✅ Location detection services
- ✅ Database schema validation

### Future Coverage
- Performance benchmarking
- Load testing with large datasets
- Integration testing with external services
- User interface testing
- Security testing

## 📞 Support

For test script issues:
1. Check the main README for setup instructions
2. Verify all dependencies are installed
3. Ensure database is properly initialized
4. Review error messages for specific issues
5. Check module imports and paths