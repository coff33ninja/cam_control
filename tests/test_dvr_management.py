#!/usr/bin/env python3
"""
Unit Tests for DVR Management System

This module tests the DVR management functionality including CRUD operations,
location inheritance, and camera assignment management.
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# Import the modules to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dvr_manager import DVR, DVRManager
from src.enhanced_camera_models import EnhancedCamera


class TestDVR:
    """Test suite for DVR data model."""
    
    @pytest.fixture
    def sample_dvr(self):
        """Create a sample DVR for testing."""
        return DVR(
            id=1,
            custom_name="Main DVR",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room",
            mac_address="00:1A:2B:3C:4D:5E",
            storage_capacity="2TB",
            date_installed="2024-01-15",
            latitude=40.7128,
            longitude=-74.0060,
            address="123 Main St, New York, NY",
            is_online=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def test_dvr_creation(self, sample_dvr):
        """Test DVR object creation."""
        assert sample_dvr.id == 1
        assert sample_dvr.custom_name == "Main DVR"
        assert sample_dvr.ip_address == "192.168.1.100"
        assert sample_dvr.dvr_type == "16-Channel"
        assert sample_dvr.location == "Server Room"
        assert sample_dvr.is_online == True
    
    def test_get_display_name_with_custom_name(self, sample_dvr):
        """Test display name with custom name set."""
        assert sample_dvr.get_display_name() == "Main DVR"
    
    def test_get_display_name_without_custom_name(self):
        """Test display name without custom name."""
        dvr = DVR(
            id=1,
            custom_name="",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        assert dvr.get_display_name() == "DVR-192-168-1-100"
    
    def test_get_display_name_with_whitespace_custom_name(self):
        """Test display name with whitespace-only custom name."""
        dvr = DVR(
            id=1,
            custom_name="   ",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        assert dvr.get_display_name() == "DVR-192-168-1-100"
    
    def test_validate_coordinates_valid(self):
        """Test coordinate validation with valid coordinates."""
        assert DVR.validate_coordinates(40.7128, -74.0060) == True
        assert DVR.validate_coordinates(-90, -180) == True
        assert DVR.validate_coordinates(90, 180) == True
        assert DVR.validate_coordinates(0, 0) == True
        assert DVR.validate_coordinates(None, None) == True  # Allow None
    
    def test_validate_coordinates_invalid(self):
        """Test coordinate validation with invalid coordinates."""
        assert DVR.validate_coordinates(91, 0) == False
        assert DVR.validate_coordinates(-91, 0) == False
        assert DVR.validate_coordinates(0, 181) == False
        assert DVR.validate_coordinates(0, -181) == False
        assert DVR.validate_coordinates("invalid", 0) == False
        assert DVR.validate_coordinates(0, "invalid") == False
    
    def test_validate_ip_address_valid(self):
        """Test IP address validation with valid addresses."""
        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "255.255.255.255",
            "0.0.0.0"
        ]
        
        for ip in valid_ips:
            assert DVR.validate_ip_address(ip) == True
    
    def test_validate_ip_address_invalid(self):
        """Test IP address validation with invalid addresses."""
        invalid_ips = [
            "256.1.1.1",  # Out of range
            "192.168.1",  # Incomplete
            "192.168.1.1.1",  # Too many octets
            "192.168.1.a",  # Non-numeric
            "",  # Empty
            "not.an.ip.address"  # Invalid format
        ]
        
        for ip in invalid_ips:
            assert DVR.validate_ip_address(ip) == False
    
    def test_validate_mac_address_valid(self):
        """Test MAC address validation with valid addresses."""
        valid_macs = [
            "00:1A:2B:3C:4D:5E",
            "FF:FF:FF:FF:FF:FF",
            "00:00:00:00:00:00",
            "aa:bb:cc:dd:ee:ff"
        ]
        
        for mac in valid_macs:
            assert DVR.validate_mac_address(mac) == True
    
    def test_validate_mac_address_invalid(self):
        """Test MAC address validation with invalid addresses."""
        invalid_macs = [
            "00:1A:2B:3C:4D",  # Too short
            "00:1A:2B:3C:4D:5E:6F",  # Too long
            "00-1A-2B-3C-4D-5E",  # Wrong separator
            "GG:1A:2B:3C:4D:5E",  # Invalid hex
            "",  # Empty
            "not:a:mac:address"  # Invalid format
        ]
        
        for mac in invalid_macs:
            assert DVR.validate_mac_address(mac) == False
    
    def test_validate_date_valid(self):
        """Test date validation with valid dates."""
        valid_dates = [
            "2024-01-15",
            "2023-12-31",
            "2024-02-29",  # Leap year
            None,  # Allow None
            ""  # Allow empty
        ]
        
        for date in valid_dates:
            assert DVR.validate_date(date) == True
    
    def test_validate_date_invalid(self):
        """Test date validation with invalid dates."""
        invalid_dates = [
            "2024-13-01",  # Invalid month
            "2024-01-32",  # Invalid day
            "2023-02-29",  # Not a leap year
            "01-15-2024",  # Wrong format
            "2024/01/15",  # Wrong separator
            "invalid-date"  # Invalid format
        ]
        
        for date in invalid_dates:
            assert DVR.validate_date(date) == False
    
    def test_validate_all_fields_valid(self, sample_dvr):
        """Test validation of all fields with valid DVR."""
        validation_results = sample_dvr.validate_all_fields()
        
        assert all(validation_results.values()) == True
        assert validation_results['coordinates'] == True
        assert validation_results['ip_address'] == True
        assert validation_results['mac_address'] == True
        assert validation_results['date_installed'] == True
    
    def test_validate_all_fields_invalid(self):
        """Test validation of all fields with invalid DVR."""
        dvr = DVR(
            id=1,
            custom_name="Test DVR",
            ip_address="256.1.1.1",  # Invalid IP
            dvr_type="Test",
            location="Test",
            mac_address="invalid-mac",  # Invalid MAC
            date_installed="invalid-date",  # Invalid date
            latitude=91,  # Invalid latitude
            longitude=0
        )
        
        validation_results = dvr.validate_all_fields()
        
        assert validation_results['coordinates'] == False
        assert validation_results['ip_address'] == False
        assert validation_results['mac_address'] == False
        assert validation_results['date_installed'] == False
    
    def test_is_valid_true(self, sample_dvr):
        """Test is_valid method with valid DVR."""
        assert sample_dvr.is_valid() == True
    
    def test_is_valid_false(self):
        """Test is_valid method with invalid DVR."""
        dvr = DVR(
            id=1,
            custom_name="Test DVR",
            ip_address="invalid-ip",
            dvr_type="Test",
            location="Test"
        )
        assert dvr.is_valid() == False
    
    def test_get_validation_errors(self):
        """Test getting validation errors."""
        dvr = DVR(
            id=1,
            custom_name="Test DVR",
            ip_address="256.1.1.1",
            dvr_type="Test",
            location="Test",
            mac_address="invalid-mac",
            date_installed="invalid-date",
            latitude=91,
            longitude=0
        )
        
        errors = dvr.get_validation_errors()
        
        assert len(errors) > 0
        assert any("Invalid coordinates" in error for error in errors)
        assert any("Invalid IP address" in error for error in errors)
        assert any("Invalid MAC address" in error for error in errors)
        assert any("Invalid installation date" in error for error in errors)
    
    def test_update_coordinates_valid(self, sample_dvr):
        """Test updating coordinates with valid values."""
        original_updated_at = sample_dvr.updated_at
        
        result = sample_dvr.update_coordinates(41.8781, -87.6298)
        
        assert result == True
        assert sample_dvr.latitude == 41.8781
        assert sample_dvr.longitude == -87.6298
        assert sample_dvr.updated_at > original_updated_at
    
    def test_update_coordinates_invalid(self, sample_dvr):
        """Test updating coordinates with invalid values."""
        original_lat = sample_dvr.latitude
        original_lon = sample_dvr.longitude
        
        result = sample_dvr.update_coordinates(91, 0)  # Invalid latitude
        
        assert result == False
        assert sample_dvr.latitude == original_lat  # Unchanged
        assert sample_dvr.longitude == original_lon  # Unchanged
    
    def test_update_connectivity_status(self, sample_dvr):
        """Test updating connectivity status."""
        test_time = datetime.now()
        
        sample_dvr.update_connectivity_status(False, test_time)
        
        assert sample_dvr.is_online == False
        assert sample_dvr.last_ping_time == test_time
    
    def test_to_map_marker(self, sample_dvr):
        """Test converting DVR to map marker configuration."""
        marker_config = sample_dvr.to_map_marker()
        
        assert marker_config['id'] == 1
        assert marker_config['name'] == "Main DVR"
        assert marker_config['location'] == "Server Room"
        assert marker_config['ip_address'] == "192.168.1.100"
        assert marker_config['latitude'] == 40.7128
        assert marker_config['longitude'] == -74.0060
        assert marker_config['is_online'] == True
        assert marker_config['marker_color'] == 'green'  # Online
        assert marker_config['device_type'] == 'dvr'
        assert 'popup_content' in marker_config
        assert 'tooltip' in marker_config
    
    def test_to_dict(self, sample_dvr):
        """Test converting DVR to dictionary."""
        dvr_dict = sample_dvr.to_dict()
        
        assert dvr_dict['id'] == 1
        assert dvr_dict['custom_name'] == "Main DVR"
        assert dvr_dict['ip_address'] == "192.168.1.100"
        assert dvr_dict['latitude'] == 40.7128
        assert dvr_dict['longitude'] == -74.0060
        assert isinstance(dvr_dict['created_at'], str)  # Should be ISO format
        assert isinstance(dvr_dict['updated_at'], str)  # Should be ISO format
    
    def test_to_json(self, sample_dvr):
        """Test converting DVR to JSON string."""
        json_str = sample_dvr.to_json()
        
        assert isinstance(json_str, str)
        assert '"id": 1' in json_str
        assert '"custom_name": "Main DVR"' in json_str
    
    def test_from_dict(self, sample_dvr):
        """Test creating DVR from dictionary."""
        dvr_dict = sample_dvr.to_dict()
        new_dvr = DVR.from_dict(dvr_dict)
        
        assert new_dvr.id == sample_dvr.id
        assert new_dvr.custom_name == sample_dvr.custom_name
        assert new_dvr.ip_address == sample_dvr.ip_address
        assert new_dvr.latitude == sample_dvr.latitude
        assert new_dvr.longitude == sample_dvr.longitude
    
    def test_from_json(self, sample_dvr):
        """Test creating DVR from JSON string."""
        json_str = sample_dvr.to_json()
        new_dvr = DVR.from_json(json_str)
        
        assert new_dvr.id == sample_dvr.id
        assert new_dvr.custom_name == sample_dvr.custom_name
        assert new_dvr.ip_address == sample_dvr.ip_address


class TestDVRManager:
    """Test suite for DVRManager class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        yield temp_file.name
        os.unlink(temp_file.name)
    
    @pytest.fixture
    def dvr_manager(self, temp_db):
        """Create a DVRManager instance with temporary database."""
        return DVRManager(temp_db)
    
    @pytest.mark.asyncio
    async def test_create_dvr_success(self, dvr_manager):
        """Test successful DVR creation."""
        result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room",
            mac_address="00:1A:2B:3C:4D:5E",
            storage_capacity="2TB",
            date_installed="2024-01-15",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        assert result['success'] == True
        assert "Test DVR" in result['message']
        assert result['dvr_id'] is not None
    
    @pytest.mark.asyncio
    async def test_create_dvr_missing_required_fields(self, dvr_manager):
        """Test DVR creation with missing required fields."""
        result = await dvr_manager.create_dvr(
            custom_name="",  # Missing name
            ip_address="192.168.1.100"
        )
        
        assert result['success'] == False
        assert "required" in result['message'].lower()
        assert result['dvr_id'] is None
    
    @pytest.mark.asyncio
    async def test_create_dvr_invalid_ip(self, dvr_manager):
        """Test DVR creation with invalid IP address."""
        result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="256.1.1.1"  # Invalid IP
        )
        
        assert result['success'] == False
        assert "Invalid IP address" in result['message']
        assert result['dvr_id'] is None
    
    @pytest.mark.asyncio
    async def test_create_dvr_invalid_mac(self, dvr_manager):
        """Test DVR creation with invalid MAC address."""
        result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100",
            mac_address="invalid-mac"
        )
        
        assert result['success'] == False
        assert "Invalid MAC address" in result['message']
        assert result['dvr_id'] is None
    
    @pytest.mark.asyncio
    async def test_create_dvr_invalid_coordinates(self, dvr_manager):
        """Test DVR creation with invalid coordinates."""
        result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100",
            latitude=91,  # Invalid latitude
            longitude=0
        )
        
        assert result['success'] == False
        assert "Invalid latitude/longitude" in result['message']
        assert result['dvr_id'] is None
    
    @pytest.mark.asyncio
    async def test_create_dvr_duplicate_ip(self, dvr_manager):
        """Test DVR creation with duplicate IP address."""
        # Create first DVR
        await dvr_manager.create_dvr(
            custom_name="First DVR",
            ip_address="192.168.1.100"
        )
        
        # Try to create second DVR with same IP
        result = await dvr_manager.create_dvr(
            custom_name="Second DVR",
            ip_address="192.168.1.100"  # Duplicate IP
        )
        
        assert result['success'] == False
        assert "already exists" in result['message']
        assert result['dvr_id'] is None
    
    @pytest.mark.asyncio
    async def test_get_dvr_exists(self, dvr_manager):
        """Test getting an existing DVR."""
        # Create DVR first
        create_result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Get the DVR
        dvr = await dvr_manager.get_dvr(dvr_id)
        
        assert dvr is not None
        assert dvr.id == dvr_id
        assert dvr.custom_name == "Test DVR"
        assert dvr.ip_address == "192.168.1.100"
    
    @pytest.mark.asyncio
    async def test_get_dvr_not_exists(self, dvr_manager):
        """Test getting a non-existent DVR."""
        dvr = await dvr_manager.get_dvr(999)  # Non-existent ID
        assert dvr is None
    
    @pytest.mark.asyncio
    async def test_get_all_dvrs(self, dvr_manager):
        """Test getting all DVRs."""
        # Create multiple DVRs
        await dvr_manager.create_dvr("DVR 1", "192.168.1.100")
        await dvr_manager.create_dvr("DVR 2", "192.168.1.101")
        await dvr_manager.create_dvr("DVR 3", "192.168.1.102")
        
        dvrs = await dvr_manager.get_all_dvrs()
        
        assert len(dvrs) == 3
        assert all(isinstance(dvr, DVR) for dvr in dvrs)
        names = [dvr.custom_name for dvr in dvrs]
        assert "DVR 1" in names
        assert "DVR 2" in names
        assert "DVR 3" in names
    
    @pytest.mark.asyncio
    async def test_update_dvr_success(self, dvr_manager):
        """Test successful DVR update."""
        # Create DVR first
        create_result = await dvr_manager.create_dvr(
            custom_name="Original DVR",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Update the DVR
        result = await dvr_manager.update_dvr(
            dvr_id,
            custom_name="Updated DVR",
            location="New Location"
        )
        
        assert result['success'] == True
        assert "Updated DVR" in result['message']
        
        # Verify the update
        updated_dvr = await dvr_manager.get_dvr(dvr_id)
        assert updated_dvr.custom_name == "Updated DVR"
        assert updated_dvr.location == "New Location"
    
    @pytest.mark.asyncio
    async def test_update_dvr_not_exists(self, dvr_manager):
        """Test updating a non-existent DVR."""
        result = await dvr_manager.update_dvr(999, custom_name="Test")
        
        assert result['success'] == False
        assert "not found" in result['message']
    
    @pytest.mark.asyncio
    async def test_update_dvr_location(self, dvr_manager):
        """Test updating DVR location."""
        # Create DVR first
        create_result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Update location
        result = await dvr_manager.update_dvr_location(
            dvr_id,
            latitude=41.8781,
            longitude=-87.6298,
            address="Chicago, IL"
        )
        
        assert result['success'] == True
        assert result['dvr']['latitude'] == 41.8781
        assert result['dvr']['longitude'] == -87.6298
        assert result['dvr']['address'] == "Chicago, IL"
    
    @pytest.mark.asyncio
    async def test_update_dvr_location_invalid_coordinates(self, dvr_manager):
        """Test updating DVR location with invalid coordinates."""
        # Create DVR first
        create_result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Try to update with invalid coordinates
        result = await dvr_manager.update_dvr_location(
            dvr_id,
            latitude=91,  # Invalid
            longitude=0
        )
        
        assert result['success'] == False
        assert "Invalid latitude/longitude" in result['message']
    
    @pytest.mark.asyncio
    async def test_delete_dvr_success(self, dvr_manager):
        """Test successful DVR deletion."""
        # Create DVR first
        create_result = await dvr_manager.create_dvr(
            custom_name="Test DVR",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Delete the DVR
        result = await dvr_manager.delete_dvr(dvr_id)
        
        assert result['success'] == True
        assert "deleted successfully" in result['message']
        
        # Verify deletion
        deleted_dvr = await dvr_manager.get_dvr(dvr_id)
        assert deleted_dvr is None
    
    @pytest.mark.asyncio
    async def test_delete_dvr_not_exists(self, dvr_manager):
        """Test deleting a non-existent DVR."""
        result = await dvr_manager.delete_dvr(999)
        
        assert result['success'] == False
        assert "not found" in result['message']


if __name__ == '__main__':
    # Run tests if script is executed directly
    pytest.main([__file__, '-v'])