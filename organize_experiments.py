import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import shutil

def organize_experiments():
    # Base paths
    source_dir = Path("/home/omrieoqm/.from_cloud_storage")
    base_data_dir = Path("/home/omrieoqm/data")
    
    # Create base data directory if it doesn't exist
    base_data_dir.mkdir(exist_ok=True)
    
    # Process each experiment folder
    for exp_folder in source_dir.iterdir():
        if not exp_folder.is_dir():
            continue
            
        # Read node.json
        node_json_path = exp_folder / "node.json"
        if not node_json_path.exists():
            print(f"Warning: node.json not found in {exp_folder}")
            continue
            
        try:
            with open(node_json_path, 'r') as f:
                node_data = json.load(f)
                
            # Extract timestamp and convert to GMT+3
            created_at = node_data.get('created_at')
            if not created_at:
                print(f"Warning: created_at not found in {node_json_path}")
                continue
                
            # Parse timestamp and add 3 hours for GMT+3
            timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            timestamp_gmt3 = timestamp + timedelta(hours=3)
            
            # Create date folder name
            date_folder = timestamp_gmt3.strftime("%Y-%m-%d")
            target_dir = base_data_dir / date_folder
            
            # Create date folder if it doesn't exist
            target_dir.mkdir(exist_ok=True)
            
            # Move experiment folder
            target_path = target_dir / exp_folder.name
            if target_path.exists():
                print(f"Warning: {target_path} already exists, skipping")
                continue
                
            shutil.move(str(exp_folder), str(target_path))
            print(f"Moved {exp_folder.name} to {date_folder}")
            
        except Exception as e:
            print(f"Error processing {exp_folder}: {str(e)}")

if __name__ == "__main__":
    organize_experiments() 