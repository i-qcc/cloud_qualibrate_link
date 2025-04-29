import os
from pathlib import Path
from cloud_qualibrate_link.qualibrate_cloud_handler import QualibrateCloudHandler
from iqcc_cloud_client import IQCC_Cloud
import json
import base64
from datetime import datetime, timedelta

def get_largest_existing_id(cloud_storage_dir: Path) -> int:
    """Get the largest experiment ID that is already downloaded."""
    largest_id = None
    for date_dir in cloud_storage_dir.iterdir():
        for exp_dir in date_dir.iterdir():   
            if exp_dir.is_dir() and "_" in exp_dir.name:  # Check if it follows the expected pattern
                exp_id = int(exp_dir.name.split("_")[0])  # ID is now at the start
                if largest_id is None or exp_id > largest_id:
                  largest_id = exp_id
    return largest_id

def collect_experiments(backend_name: str, max_experiments: int = 10000) -> None:
    """
    Collect experiments from the cloud, skipping already downloaded ones.
    
    Args:
        backend_name (str): Name of the quantum computer backend
        max_experiments (int): Maximum number of experiments to download (default: 10000)
    """
    # Initialize cloud client
    qc = IQCC_Cloud(quantum_computer_backend=backend_name, datastore="iqcc")
    
    # Get cloud storage directory
    cloud_storage_dir = Path.home() / ".from_cloud_storage" / "user_storage" / "QC1"
    cloud_storage_dir.mkdir(exist_ok=True)
    
    # Get largest existing ID
    largest_existing_id = get_largest_existing_id(cloud_storage_dir)
    if largest_existing_id:
        print(f"Largest existing experiment ID: {largest_existing_id}")
    
    # Get the last max_experiments experiments
    metadata_list = list(qc.data.list("node", limit=max_experiments))
    print(f"Found {len(metadata_list)} experiments in the cloud")
    
    # Count new experiments (taking advantage of sorted metadata_list)
    if largest_existing_id:
        # Find the first position where ID is greater than largest_existing_id
        new_experiments_count = 0
        for metadata in metadata_list:
            if int(metadata.id) > largest_existing_id:
                new_experiments_count += 1
            else:
                break
    else:
        new_experiments_count = len(metadata_list)
    print(f"Found {new_experiments_count} new experiments to process")
    
    # Process experiments
    processed_count = 0
    for metadata in metadata_list:
        # Skip if ID is not newer than our largest existing ID
        if largest_existing_id and int(metadata.id) <= largest_existing_id:
            print(f"Reached existing experiment ID {largest_existing_id}, stopping")
            break
            
        try:
            # Create experiment directory
            exp_name = qc.data.get(metadata.id).data['name']
            print(f"\nProcessing experiment: {exp_name}")
            
            # Extract timestamp and create date folder
            timestamp = metadata.timestamp
            # Convert to GMT+3 (add 3 hours)
            timestamp_gmt3 = timestamp + timedelta(hours=3)
            date_folder = timestamp_gmt3.strftime("%Y-%m-%d")
            
            # Create date-based directory structure
            date_dir = cloud_storage_dir / date_folder
            date_dir.mkdir(exist_ok=True)
            
            experiment_folder_name = f"{metadata.id}_{exp_name}"
            experiment_dir = date_dir / experiment_folder_name
            experiment_dir.mkdir(exist_ok=True)
            
            # Save experiment data using QualibrateCloudHandler
            QualibrateCloudHandler._save_experiment_data(qc, metadata.id, experiment_dir)
            processed_count += 1
            print(f"Processed {processed_count} new experiments")
            
        except Exception as e:
            print(f"Error processing experiment {metadata.id}: {str(e)}")
            
    print(f"\nCompleted! Processed {processed_count} new experiments")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect experiments from the cloud")
    parser.add_argument("--backend-name", default="qc_qwfix", help="Name of the quantum computer backend")
    parser.add_argument("--max-experiments", type=int, default=1000, help="Maximum number of experiments to download")
    
    args = parser.parse_args()
    
    collect_experiments(
        backend_name=args.backend_name,
        max_experiments=args.max_experiments
    ) 