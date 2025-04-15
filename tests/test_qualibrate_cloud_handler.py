import pytest
from pathlib import Path
from cloud_qualibrate_link.qualibrate_cloud_handler import QualibrateCloudHandler

def test_qualibrate_cloud_handler_initialization(experiment_path, backend_name):
    # Initialize the handler
    handler = QualibrateCloudHandler(experiment_path)
    
    # Test that the handler was initialized correctly
    assert handler.experiment_path == Path(experiment_path)
    assert handler.experiment_name is not None
    
    # Test that the data was loaded
    assert handler.node_data is not None
    assert handler.state_data is not None
    assert handler.wiring_data is not None
    
    # Test upload to cloud
    handler.upload_to_cloud(backend_name)
    
    # Note: The actual cloud upload can't be fully tested without proper credentials
    # and a test environment. This test assumes the files exist and the handler
    # can be initialized successfully. 

def test_store_from_cloud(backend_name):
    # Call the store_from_cloud method
    QualibrateCloudHandler.store_from_cloud(backend_name, limit=1)
    
    # Get the cloud storage directory
    cloud_storage_dir = Path.home() / ".from_cloud_storage"
    
    # Check that the directory exists
    assert cloud_storage_dir.exists()
    assert cloud_storage_dir.is_dir()
    
    # Check that there are experiment directories
    experiment_dirs = list(cloud_storage_dir.glob("*"))
    assert len(experiment_dirs) > 0
    
    # For each experiment directory, check the structure
    for exp_dir in experiment_dirs:
        # Check main files
        assert (exp_dir / "node.json").exists()
        
        # Check quam_state directory and its files
        quam_state_dir = exp_dir / "quam_state"
        assert quam_state_dir.exists()
        assert quam_state_dir.is_dir()
        assert (quam_state_dir / "state.json").exists()
        assert (quam_state_dir / "wiring.json").exists()
        
        # Check for PNG files
        png_files = list(exp_dir.glob("*.png"))
        assert len(png_files) > 0
        
        # Check that the directory name follows the expected pattern
        assert "_" in exp_dir.name  # Should contain experiment name and ID 