import os
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from iqcc_cloud_client import IQCC_Cloud

class QualibrateCloudHandler:
    def __init__(self, experiment_path: str):
        """
        Initialize the QualibrateCloudHandler with an experiment path.
        
        Args:
            experiment_path (str): Path to the experiment folder
        """
        self.experiment_path = Path(experiment_path)
        self.node_data = None
        self.state_data = None
        self.wiring_data = None
        self.png_data = {}
        self.experiment_name = None
        
        self._load_experiment_data()
    
    def _load_experiment_data(self) -> None:
        """Load all required experiment data and process PNG files."""
        # Load node.json
        node_path = self.experiment_path / "node.json"
        if not node_path.exists():
            raise FileNotFoundError(f"node.json not found in {self.experiment_path}")
        
        with open(node_path, 'r') as f:
            self.node_data = json.load(f)
        
        # Extract experiment name from metadata
        self.experiment_name = self.node_data.get('metadata', {}).get('name')
        if not self.experiment_name:
            raise ValueError("Experiment name not found in node.json metadata")
        
        # Load state.json
        state_path = self.experiment_path / "quam_state" / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"state.json not found in {state_path}")
        
        with open(state_path, 'r') as f:
            self.state_data = json.load(f)
        
        # Load wiring.json
        wiring_path = self.experiment_path / "quam_state" / "wiring.json"
        if not wiring_path.exists():
            raise FileNotFoundError(f"wiring.json not found in {wiring_path}")
        
        with open(wiring_path, 'r') as f:
            self.wiring_data = json.load(f)
        
        # Process PNG files
        for png_file in self.experiment_path.glob("*.png"):
            with open(png_file, 'rb') as f:
                png_bytes = f.read()
                base64_str = base64.b64encode(png_bytes).decode('utf-8')
                
                self.png_data[png_file.name] = {
                    "data": base64_str,
                    "__type__": "png/base64",
                    "file_name": png_file.name
                }
    
    def upload_to_cloud(self, quantum_computer_backend: str) -> None:
        """
        Upload the experiment data to the cloud.
        
        Args:
            quantum_computer_backend (str): Name of the quantum computer backend
        """
        qc = IQCC_Cloud(quantum_computer_backend=quantum_computer_backend, datastore="iqcc")
        
        # Push parent data
        parent = qc.data.push(
            datatype="node",
            data={
                "local_dir": str(self.experiment_path),
                "name": self.experiment_name
            }
        )
        
        # Push node.json data
        qc.data.push(
            datatype=f"node_info",
            data=self.node_data,
            parent_id=parent.id
        )
        
        # Push state.json data
        qc.data.push(
            datatype=f"state",
            data=self.state_data,
            parent_id=parent.id
        )
        
        # Push wiring.json data
        qc.data.push(
            datatype=f"wiring",
            data=self.wiring_data,
            parent_id=parent.id
        )
        
        # Push PNG files
        for png_data in self.png_data.values():
            qc.data.push(
                datatype=f"figure",
                data=png_data,
                parent_id=parent.id
            ) 
    
    @classmethod
    def store_from_cloud(cls, quantum_computer_backend: str, data_type: str = "node", limit: int = 1) -> None:
        """
        Download and store calibration data from the cloud.
        
        Args:
            quantum_computer_backend (str): Name of the quantum computer backend
        """
        qc = IQCC_Cloud(quantum_computer_backend=quantum_computer_backend, datastore="iqcc")
        data_list = [qc.data.get(metadata.id) for metadata in qc.data.list(data_type, limit=limit)]
        
        # Create .from_cloud_storage directory in home directory
        home_dir = Path.home()
        cloud_storage_dir = home_dir / ".from_cloud_storage"
        cloud_storage_dir.mkdir(exist_ok=True)
        
        for calibration_data in data_list:
            # Create experiment directory
            exp_name = calibration_data.data['name']
            experiment_folder_name = f"{exp_name}_{calibration_data.id}"
            experiment_dir = cloud_storage_dir / experiment_folder_name
            experiment_dir.mkdir(exist_ok=True)
            
            # Create quam_state directory
            quam_state_dir = experiment_dir / "quam_state"
            quam_state_dir.mkdir(exist_ok=True)
            
            # Get all related data
            node_info = qc.data.get(qc.data.list_children(datatype=f"node_info", parent_dataset_id=calibration_data.id)[0].id)
            state_info = qc.data.get(qc.data.list_children(datatype=f"state", parent_dataset_id=calibration_data.id)[0].id)
            wiring_info = qc.data.get(qc.data.list_children(datatype=f"wiring", parent_dataset_id=calibration_data.id)[0].id)
            
            # Save node.json
            if node_info:
                with open(experiment_dir / "node.json", 'w') as f:
                    json.dump(node_info.data, f, indent=4)
            
            # Save state.json
            if state_info:
                with open(quam_state_dir / "state.json", 'w') as f:
                    json.dump(state_info.data, f, indent=4)
            
            # Save wiring.json
            if wiring_info:
                with open(quam_state_dir / "wiring.json", 'w') as f:
                    json.dump(wiring_info.data, f, indent=4)
            
            # Save PNG files
            png_files = [qc.data.get(metadata.id) for metadata in qc.data.list_children(datatype="figure", parent_dataset_id=calibration_data.id)]
            for png_data in png_files:
                if png_data.data.get("__type__") == "png/base64":
                    file_name = png_data.data.get("file_name")
                    if file_name:
                        png_bytes = base64.b64decode(png_data.data["data"])
                        with open(experiment_dir / file_name, 'wb') as f:
                            f.write(png_bytes)
                else:
                    raise ValueError(f"Unexpected data type: {png_data.data.get('__type__')}")
        
        
            
