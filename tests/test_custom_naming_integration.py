#!/usr/bin/env python3
"""
Integration Tests for Custom Naming System

This module tests the custom naming functionality across all components
including cameras, DVRs, map visualization, and database operations.
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Import the modules to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.enhanced_camera_models import EnhancedCamera
from src.dvr_manager import DVR, DVRManager
from src.interactive_map_manager import InteractiveMapManager


class TestCustomNamingIntegration:
    """Integration tests for custom naming system across all components."""
    
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
    
    @pytest.fixture
    def map_manager(self, temp_db):
        """Create an InteractiveMapManager instance with temporary database."""
        return InteractiveMapManager(temp_db)
    
    def test_camera_display_name_with_custom_name(self):
        """Test camera display name with custom name set."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Front Door Camera",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        assert camera.get_display_name() == "Front Door Camera"
    
    def test_camera_display_name_without_custom_name(self):
        """Test camera display name without custom name."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        assert camera.get_display_name() == "CAM-001"
    
    def test_camera_display_name_with_whitespace_custom_name(self):
        """Test camera display name with whitespace-only custom name."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="   ",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        assert camera.get_display_name() == "CAM-001"
    
    def test_camera_display_name_with_none_custom_name(self):
        """Test camera display name with None custom name."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name=None,
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        assert camera.get_display_name() == "CAM-001"
    
    def test_dvr_display_name_with_custom_name(self):
        """Test DVR display name with custom name set."""
        dvr = DVR(
            id=1,
            custom_name="Main Server DVR",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        
        assert dvr.get_display_name() == "Main Server DVR"
    
    def test_dvr_display_name_without_custom_name(self):
        """Test DVR display name without custom name."""
        dvr = DVR(
            id=1,
            custom_name="",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        
        assert dvr.get_display_name() == "DVR-192-168-1-100"
    
    def test_camera_map_marker_uses_display_name(self):
        """Test that camera map markers use display names."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Security Camera Alpha",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        marker_config = camera.to_map_marker()
        
        assert marker_config['display_name'] == "Security Camera Alpha"
        assert "Security Camera Alpha" in marker_config['tooltip']
        assert "Security Camera Alpha" in marker_config['popup_content']
    
    def test_dvr_map_marker_uses_display_name(self):
        """Test that DVR map markers use display names."""
        dvr = DVR(
            id=1,
            custom_name="Primary DVR System",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room",
            latitude=40.7128,
            longitude=-74.0060,
            is_online=True
        )
        
        marker_config = dvr.to_map_marker()
        
        assert marker_config['name'] == "Primary DVR System"
        assert "Primary DVR System" in marker_config['tooltip']
        assert "Primary DVR System" in marker_config['popup_content']
    
    def test_camera_custom_name_validation_valid(self):
        """Test camera custom name validation with valid names."""
        valid_names = [
            "Front Door Camera",
            "Security-Cam-01",
            "Parking_Lot_View",
            "Camera.Main.Entrance",
            "CAM 123",
            "",  # Empty is valid (optional)
            None  # None is valid (optional)
        ]
        
        for name in valid_names:
            assert EnhancedCamera.validate_custom_name(name) == True
    
    def test_camera_custom_name_validation_invalid(self):
        """Test camera custom name validation with invalid names."""
        invalid_names = [
            "A" * 101,  # Too long (>100 characters)
            "Camera@#$%",  # Invalid characters
            "Camera<script>",  # Potentially dangerous
            "   ",  # Only whitespace (but this should be handled by display logic)
        ]
        
        for name in invalid_names:
            if name != "   ":  # Whitespace is technically valid, handled by display logic
                assert EnhancedCamera.validate_custom_name(name) == False
    
    @pytest.mark.asyncio
    async def test_dvr_creation_with_custom_name(self, dvr_manager):
        """Test DVR creation with custom name integration."""
        result = await dvr_manager.create_dvr(
            custom_name="Main Security DVR",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        
        assert result['success'] == True
        assert "Main Security DVR" in result['message']
        
        # Verify the DVR was created with correct custom name
        dvr = await dvr_manager.get_dvr(result['dvr_id'])
        assert dvr.custom_name == "Main Security DVR"
        assert dvr.get_display_name() == "Main Security DVR"
    
    @pytest.mark.asyncio
    async def test_dvr_update_custom_name(self, dvr_manager):
        """Test updating DVR custom name."""
        # Create DVR
        create_result = await dvr_manager.create_dvr(
            custom_name="Original Name",
            ip_address="192.168.1.100"
        )
        dvr_id = create_result['dvr_id']
        
        # Update custom name
        update_result = await dvr_manager.update_dvr(
            dvr_id,
            custom_name="Updated Security DVR"
        )
        
        assert update_result['success'] == True
        
        # Verify the update
        updated_dvr = await dvr_manager.get_dvr(dvr_id)
        assert updated_dvr.custom_name == "Updated Security DVR"
        assert updated_dvr.get_display_name() == "Updated Security DVR"
    
    def test_camera_serialization_includes_custom_name(self):
        """Test that camera serialization includes custom name."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Lobby Security Camera",
            location="Main Lobby",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        # Test dictionary serialization
        camera_dict = camera.to_dict()
        assert camera_dict['custom_name'] == "Lobby Security Camera"
        
        # Test JSON serialization
        camera_json = camera.to_json()
        assert '"custom_name": "Lobby Security Camera"' in camera_json
        
        # Test deserialization
        restored_camera = EnhancedCamera.from_dict(camera_dict)
        assert restored_camera.custom_name == "Lobby Security Camera"
        assert restored_camera.get_display_name() == "Lobby Security Camera"
    
    def test_dvr_serialization_includes_custom_name(self):
        """Test that DVR serialization includes custom name."""
        dvr = DVR(
            id=1,
            custom_name="Primary Recording System",
            ip_address="192.168.1.100",
            dvr_type="16-Channel",
            location="Server Room"
        )
        
        # Test dictionary serialization
        dvr_dict = dvr.to_dict()
        assert dvr_dict['custom_name'] == "Primary Recording System"
        
        # Test JSON serialization
        dvr_json = dvr.to_json()
        assert '"custom_name": "Primary Recording System"' in dvr_json
        
        # Test deserialization
        restored_dvr = DVR.from_dict(dvr_dict)
        assert restored_dvr.custom_name == "Primary Recording System"
        assert restored_dvr.get_display_name() == "Primary Recording System"
    
    def test_camera_popup_content_shows_both_names(self):
        """Test that camera popup shows both original and custom names when different."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Front Door Security",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E",
            latitude=40.7128,
            longitude=-74.0060,
            is_online=True
        )
        
        popup_content = camera._generate_popup_content()
        
        # Should show custom name as main title
        assert "Front Door Security" in popup_content
        # Should show original name as "Original Name" when different
        assert "CAM-001" in popup_content
        assert "Original Name" in popup_content
    
    def test_camera_popup_content_single_name(self):
        """Test that camera popup shows only one name when custom name matches original."""
        camera = EnhancedCamera(
            id=1,
            name="Front Door Camera",
            custom_name="Front Door Camera",  # Same as original
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E",
            latitude=40.7128,
            longitude=-74.0060,
            is_online=True
        )
        
        popup_content = camera._generate_popup_content()
        
        # Should show the name as main title
        assert "Front Door Camera" in popup_content
        # Should NOT show "Original Name" section since they're the same
        assert popup_content.count("Front Door Camera") == 1  # Only appears once
    
    def test_camera_validation_errors_include_custom_name(self):
        """Test that camera validation includes custom name validation."""
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="A" * 101,  # Too long
            location="Test",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E"
        )
        
        validation_results = camera.validate_all_fields()
        assert validation_results['custom_name'] == False
        
        errors = camera.get_validation_errors()
        assert any("custom name" in error.lower() for error in errors)
    
    @pytest.mark.asyncio
    async def test_map_generation_uses_custom_names(self, map_manager, temp_db):
        """Test that map generation uses custom names for markers."""
        # This test would require setting up a database with cameras and DVRs
        # For now, we'll test the marker generation logic directly
        
        # Create sample camera with custom name
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Main Entrance Camera",
            location="Front Door",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Test marker configuration
        marker_config = camera.to_map_marker()
        
        # Verify custom name is used in all relevant places
        assert marker_config['display_name'] == "Main Entrance Camera"
        assert "Main Entrance Camera" in marker_config['tooltip']
        assert "Main Entrance Camera" in marker_config['popup_content']
    
    def test_custom_name_fallback_behavior(self):
        """Test custom name fallback behavior across different scenarios."""
        test_cases = [
            # (custom_name, original_name, expected_display_name)
            ("Custom Name", "Original", "Custom Name"),
            ("", "Original", "Original"),
            ("   ", "Original", "Original"),  # Whitespace only
            (None, "Original", "Original"),
            ("Custom Name", "", "Custom Name"),  # Edge case: empty original
        ]
        
        for custom_name, original_name, expected in test_cases:
            camera = EnhancedCamera(
                id=1,
                name=original_name,
                custom_name=custom_name,
                location="Test",
                ip_address="192.168.1.50",
                mac_address="00:1A:2B:3C:4D:5E"
            )
            
            assert camera.get_display_name() == expected, f"Failed for custom='{custom_name}', original='{original_name}'"
    
    def test_dvr_custom_name_fallback_behavior(self):
        """Test DVR custom name fallback behavior."""
        test_cases = [
            # (custom_name, ip_address, expected_display_name)
            ("Custom DVR", "192.168.1.100", "Custom DVR"),
            ("", "192.168.1.100", "DVR-192-168-1-100"),
            ("   ", "192.168.1.100", "DVR-192-168-1-100"),  # Whitespace only
            (None, "192.168.1.100", "DVR-192-168-1-100"),
        ]
        
        for custom_name, ip_address, expected in test_cases:
            dvr = DVR(
                id=1,
                custom_name=custom_name,
                ip_address=ip_address,
                dvr_type="Test",
                location="Test"
            )
            
            assert dvr.get_display_name() == expected, f"Failed for custom='{custom_name}', ip='{ip_address}'"
    
    def test_cross_component_name_consistency(self):
        """Test that custom names are consistent across different components."""
        # Create camera with custom name
        camera = EnhancedCamera(
            id=1,
            name="CAM-001",
            custom_name="Security Camera Alpha",
            location="Main Entrance",
            ip_address="192.168.1.50",
            mac_address="00:1A:2B:3C:4D:5E",
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Test consistency across different representations
        display_name = camera.get_display_name()
        marker_config = camera.to_map_marker()
        camera_dict = camera.to_dict()
        
        # All should use the same display name
        assert display_name == "Security Camera Alpha"
        assert marker_config['display_name'] == "Security Camera Alpha"
        assert camera_dict['custom_name'] == "Security Camera Alpha"
        
        # Restored camera should maintain consistency
        restored_camera = EnhancedCamera.from_dict(camera_dict)
        assert restored_camera.get_display_name() == "Security Camera Alpha"


if __name__ == '__main__':
    # Run tests if script is executed directly
    pytest.main([__file__, '-v'])