import json
import base64
from pathlib import Path
from iqcc_cloud_client import IQCC_Cloud

# Matplotlib figures are stored by QUAlibrate as PNG, Plotly figures as a JSON
# figure spec. Both are pushed under the "figure" datatype and told apart by
# the "__type__" field of the payload.
PNG_TYPE = "png/base64"
PLOTLY_TYPE = "plotly/json"

# Suffix of the Plotly figure specs written next to a node's results.
PLOTLY_SUFFIX = ".plotly.json"


class QualibrateCloudHandler:
    def __init__(self, experiment_path: str):
        """
        Initialize the QualibrateCloudHandler with an experiment path.

        Args:
            experiment_path (str): Path to the experiment folder
        """
        self.experiment_path = Path(experiment_path)
        self.experiment_file_name = self.experiment_path.stem

        self.node_data = None
        self.state_data = None
        self.figure_data = {}
        self.experiment_name = None

        self._load_experiment_data()

    @property
    def png_data(self) -> dict:
        """PNG figures only, kept for backwards compatibility."""
        return {
            name: figure
            for name, figure in self.figure_data.items()
            if figure.get("__type__") == PNG_TYPE
        }

    def _load_experiment_data(self) -> None:
        """Load all required experiment data and process figure files."""
        # Load node.json
        node_path = self.experiment_path / "node.json"
        if not node_path.exists():
            raise FileNotFoundError(
                f"node.json not found in {self.experiment_path}"
            )

        with open(node_path, "r") as f:
            self.node_data = json.load(f)

        # Extract experiment name from metadata
        self.experiment_name = self.node_data.get("metadata", {}).get("name")
        if not self.experiment_name:
            raise ValueError("Experiment name not found in node.json metadata")

        # Load state.json
        state_path = self.experiment_path / "quam_state" / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"state.json not found in {state_path}")

        with open(state_path, "r") as f:
            self.state_data = json.load(f)

        self._load_figures()

    def _load_figures(self) -> None:
        """Collect matplotlib PNG figures and Plotly figure specs."""
        # Matplotlib figures, saved as PNG.
        for png_file in self.experiment_path.glob("*.png"):
            with open(png_file, "rb") as f:
                png_bytes = f.read()

            self.figure_data[png_file.name] = {
                "data": base64.b64encode(png_bytes).decode("utf-8"),
                "__type__": PNG_TYPE,
                "file_name": png_file.name,
            }

        # Plotly figures, uploaded as the figure spec itself so the cloud can
        # re-render them interactively rather than storing a flat image.
        for plotly_file in self.experiment_path.glob(f"*{PLOTLY_SUFFIX}"):
            with open(plotly_file, "r") as f:
                figure_spec = json.load(f)

            self.figure_data[plotly_file.name] = {
                "data": figure_spec,
                "__type__": PLOTLY_TYPE,
                "file_name": plotly_file.name,
            }

    def upload_to_cloud(self, quantum_computer_backend: str) -> None:
        """
        Upload the experiment data to the cloud.

        Args:
            quantum_computer_backend (str): Name of the quantum computer backend
        """
        qc = IQCC_Cloud(
            quantum_computer_backend=quantum_computer_backend, datastore="iqcc"
        )

        # Push parent data
        parent = qc.data.push(
            datatype=self.experiment_name,
            data={
                "local_dir": str(self.experiment_path),
                "name": self.experiment_name,
            },
        )

        # Push node.json data
        qc.data.push(
            datatype="node_info",
            data=self.node_data,
            parent_id=parent.id,
            comment=self.experiment_name,
        )

        # Push state.json data
        qc.data.push(
            datatype="state",
            data=self.state_data,
            parent_id=parent.id,
            comment=self.experiment_name,
        )

        # Push figures (matplotlib PNGs and Plotly figure specs)
        for figure in self.figure_data.values():
            qc.data.push(
                datatype="figure",
                data=figure,
                parent_id=parent.id,
                comment=self.experiment_name,
            )

    @classmethod
    def _save_experiment_data(
        cls, qc: IQCC_Cloud, dataset_id: str, experiment_dir: Path
    ) -> None:
        """
        Save experiment data for a specific dataset ID.

        Args:
            qc: IQCC_Cloud instance
            dataset_id: ID of the dataset to save
            experiment_dir: Directory to save the experiment data
        """
        # Create quam_state directory
        quam_state_dir = experiment_dir / "quam_state"
        quam_state_dir.mkdir(exist_ok=True)

        # Get all related data
        try:
            node_info = None
            node_children = qc.data.list_children(
                datatype="node_info", parent_dataset_id=dataset_id
            )
            if node_children:
                node_info = qc.data.get(node_children[0].id)
                print("✓ Retrieved node_info")
            else:
                print("✗ No node_info found")
        except Exception as e:
            print(f"✗ Could not retrieve node_info: {str(e)}")
            node_info = None

        try:
            state_info = None
            state_children = qc.data.list_children(
                datatype="state", parent_dataset_id=dataset_id
            )
            if state_children:
                state_info = qc.data.get(state_children[0].id)
                print("✓ Retrieved state")
            else:
                print("✗ No state found")
        except Exception as e:
            print(f"✗ Could not retrieve state: {str(e)}")
            state_info = None

        try:
            wiring_info = None
            wiring_children = qc.data.list_children(
                datatype="wiring", parent_dataset_id=dataset_id
            )
            if wiring_children:
                wiring_info = qc.data.get(wiring_children[0].id)
                print("✓ Retrieved wiring")
            else:
                print("✗ No wiring found")
        except Exception as e:
            print(f"✗ Could not retrieve wiring: {str(e)}")
            wiring_info = None

        # Save node.json
        if node_info:
            with open(experiment_dir / "node.json", "w") as f:
                json.dump(node_info.data, f, indent=4)
            print("✓ Saved node.json")

        # Save state.json
        if state_info:
            with open(quam_state_dir / "state.json", "w") as f:
                json.dump(state_info.data, f, indent=4)
            print("✓ Saved state.json")

        # Save wiring.json
        if wiring_info:
            with open(quam_state_dir / "wiring.json", "w") as f:
                json.dump(wiring_info.data, f, indent=4)
            print("✓ Saved wiring.json")

        # Save figures (matplotlib PNGs and Plotly figure specs)
        figures = [
            qc.data.get(metadata.id)
            for metadata in qc.data.list_children(
                datatype="figure", parent_dataset_id=dataset_id
            )
        ]
        png_count = 0
        plotly_count = 0
        for figure in figures:
            figure_type = figure.data.get("__type__")
            file_name = figure.data.get("file_name")
            if not file_name:
                print(f"✗ Figure without a file name: {figure_type}")
                continue

            if figure_type == PNG_TYPE:
                png_bytes = base64.b64decode(figure.data["data"])
                with open(experiment_dir / file_name, "wb") as f:
                    f.write(png_bytes)
                png_count += 1
            elif figure_type == PLOTLY_TYPE:
                with open(experiment_dir / file_name, "w") as f:
                    json.dump(figure.data["data"], f)
                plotly_count += 1
            else:
                print(f"✗ Unexpected data type in figure file: {figure_type}")

        if png_count > 0:
            print(f"✓ Saved {png_count} PNG file(s)")
        if plotly_count > 0:
            print(f"✓ Saved {plotly_count} Plotly figure(s)")
        if png_count == 0 and plotly_count == 0:
            print("✗ No figure files found")

    @classmethod
    def store_from_cloud(
        cls,
        quantum_computer_backend: str,
        data_type: str = "node",
        limit: int = 1,
    ) -> None:
        """
        Download and store calibration data from the cloud.

        Args:
            quantum_computer_backend (str): Name of the quantum computer backend
            data_type (str): Type of data to download (default: "node")
            limit (int): Maximum number of experiments to download (default: 1)
        """
        qc = IQCC_Cloud(
            quantum_computer_backend=quantum_computer_backend, datastore="iqcc"
        )
        data_list = [
            qc.data.get(metadata.id)
            for metadata in qc.data.list(data_type, limit=limit)
        ]

        # Create .from_cloud_storage directory in home directory
        home_dir = Path.home()
        cloud_storage_dir = home_dir / ".from_cloud_storage"
        cloud_storage_dir.mkdir(exist_ok=True)

        for calibration_data in data_list:
            # Create experiment directory
            exp_name = calibration_data.data["name"]
            print(f"\nProcessing experiment: {exp_name}")
            experiment_folder_name = f"{calibration_data.id}_{exp_name}"
            experiment_dir = cloud_storage_dir / experiment_folder_name
            experiment_dir.mkdir(exist_ok=True)

            # Save experiment data
            cls._save_experiment_data(qc, calibration_data.id, experiment_dir)

            print(f"Completed processing experiment: {exp_name}\n")
