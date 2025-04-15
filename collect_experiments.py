import os
from pathlib import Path
from cloud_qualibrate_link.qualibrate_cloud_handler import QualibrateCloudHandler
from iqcc_cloud_client import IQCC_Cloud
import json
import base64

def get_largest_existing_id(cloud_storage_dir: Path) -> int:
    """Get the largest experiment ID that is already downloaded."""
    largest_id = None
    for exp_dir in cloud_storage_dir.glob("*"):
        if "_" in exp_dir.name:  # Check if it follows the expected pattern
            exp_id = int(exp_dir.name.split("_")[-1])
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
    cloud_storage_dir = Path.home() / ".from_cloud_storage"
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
            experiment_folder_name = f"{exp_name}_{metadata.id}"
            experiment_dir = cloud_storage_dir / experiment_folder_name
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
    parser.add_argument("backend_name", help="Name of the quantum computer backend")
    parser.add_argument("--max-experiments", type=int, default=10000, help="Maximum number of experiments to download")
    
    args = parser.parse_args()
    
    collect_experiments(
        backend_name=args.backend_name,
        max_experiments=args.max_experiments
    ) 