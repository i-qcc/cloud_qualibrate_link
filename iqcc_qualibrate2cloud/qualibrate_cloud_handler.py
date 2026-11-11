import json
import base64
import hashlib
import zlib
from pathlib import Path
from iqcc_cloud_client import IQCC_Cloud

# Raw and fit datasets saved by QUAlibrate next to node.json (xarray HDF5 /
# numpy archives). Uploaded so plots can be recreated from the cloud copy.
RAW_DATA_SUFFIXES = (".h5", ".npz")
RAW_DATA_TYPE = "zlib/base64"

# Cloud dataset type for experiment data files (*.h5, *.npz).
EXP_DATA_DATATYPE = "exp_data"
EXP_BUNDLE_TYPE = "exp_data/bundle"
LEGACY_EXP_DATA_DATATYPE = "raw_data"
LEGACY_EXP_BUNDLE_TYPE = "raw_data/bundle"

# Upper bound on the total encoded size of the raw-data dataset. The cloud
# backend limits single messages to 20 MiB.
DEFAULT_MAX_RAW_BYTES = 15 * 1024**2

# list_children returns 10 items by default; nodes saved in batches can have
# many more raw-data files.
CHILDREN_LIMIT = 1000


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
        self.wiring_data = None
        self.results_data = None
        self.png_data = {}
        self.raw_data_files = []
        self.experiment_name = None

        self._load_experiment_data()

    def _load_experiment_data(self) -> None:
        """Load all required experiment data and process PNG files."""
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

        # wiring.json and data.json are optional (older nodes may lack them)
        wiring_path = self.experiment_path / "quam_state" / "wiring.json"
        if wiring_path.exists():
            with open(wiring_path, "r") as f:
                self.wiring_data = json.load(f)

        results_path = self.experiment_path / "data.json"
        if results_path.exists():
            with open(results_path, "r") as f:
                self.results_data = json.load(f)

        self.raw_data_files = sorted(
            path
            for path in self.experiment_path.iterdir()
            if path.is_file() and path.suffix in RAW_DATA_SUFFIXES
        )

        # Process PNG files
        for png_file in self.experiment_path.glob("*.png"):
            with open(png_file, "rb") as f:
                png_bytes = f.read()
                base64_str = base64.b64encode(png_bytes).decode("utf-8")

                self.png_data[png_file.name] = {
                    "data": base64_str,
                    "__type__": "png/base64",
                    "file_name": png_file.name,
                }

    @staticmethod
    def encode_raw_file(path: Path) -> dict:
        """Compress and base64-encode a raw-data file into a JSON payload.

        Args:
            path: Path to the raw-data file.

        Returns:
            dict: Payload with the encoded data and integrity information.
        """
        raw = path.read_bytes()
        return {
            "data": base64.b64encode(zlib.compress(raw, 6)).decode("ascii"),
            "__type__": RAW_DATA_TYPE,
            "file_name": path.name,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    @staticmethod
    def decode_raw_file(payload: dict) -> bytes:
        """Decode a raw-data payload produced by `encode_raw_file`.

        Args:
            payload: Payload as stored in the cloud.

        Returns:
            bytes: The original file content.

        Raises:
            ValueError: If the payload type is unknown or the decoded content
                does not match the recorded size or sha256.
        """
        if payload.get("__type__") != RAW_DATA_TYPE:
            raise ValueError(
                f"Unexpected raw data type: {payload.get('__type__')}"
            )
        size = payload["size"]
        # Bounded decompression: never expand beyond the recorded size.
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(
            base64.b64decode(payload["data"]), size + 1
        )
        if len(raw) != size or not decompressor.eof:
            raise ValueError("Decoded size does not match recorded size")
        if hashlib.sha256(raw).hexdigest() != payload["sha256"]:
            raise ValueError("sha256 mismatch")
        return raw

    def _encode_raw_data(
        self, max_raw_bytes: int
    ) -> tuple[dict | None, list[str]]:
        """Bundle the raw-data files into a single payload.

        Files are added smallest first until the total encoded size would
        exceed the cap; the remaining files are skipped.

        Args:
            max_raw_bytes: Maximum total encoded size of the bundle.

        Returns:
            tuple: The bundle payload (None if there are no files) and the
                names of the skipped files.
        """
        encoded = sorted(
            (self.encode_raw_file(p) for p in self.raw_data_files),
            key=lambda payload: len(payload["data"]),
        )
        files, skipped, total = [], [], 0
        for payload in encoded:
            total += len(payload["data"])
            if total > max_raw_bytes:
                total -= len(payload["data"])
                print(
                    f"✗ Skipping raw data file {payload['file_name']}: "
                    f"bundle would exceed {max_raw_bytes / 1e6:.1f} MB"
                )
                skipped.append(payload["file_name"])
            else:
                files.append(payload)
        if not files:
            return None, skipped
        files.sort(key=lambda payload: payload["file_name"])
        return {"__type__": EXP_BUNDLE_TYPE, "files": files}, skipped

    def upload_to_cloud(
        self,
        quantum_computer_backend: str,
        upload_raw_data: bool = True,
        max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
    ) -> None:
        """
        Upload the experiment data to the cloud.

        Args:
            quantum_computer_backend (str): Name of the quantum computer backend
            upload_raw_data (bool): Also upload raw-data files (*.h5, *.npz)
                as a single `exp_data` dataset (default: True)
            max_raw_bytes (int): Maximum total encoded size of the raw-data
                dataset; files that do not fit are skipped (default: 15 MiB)
        """
        raw_bundle, skipped_raw_files = (
            self._encode_raw_data(max_raw_bytes)
            if upload_raw_data
            else (None, [])
        )

        qc = IQCC_Cloud(
            quantum_computer_backend=quantum_computer_backend, datastore="iqcc"
        )

        # Push parent data
        parent_data = {
            "local_dir": str(self.experiment_path),
            "name": self.experiment_name,
        }
        if skipped_raw_files:
            parent_data["skipped_raw_files"] = skipped_raw_files
        parent = qc.data.push(
            datatype=self.experiment_name,
            data=parent_data,
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

        # Push wiring.json data
        if self.wiring_data is not None:
            qc.data.push(
                datatype="wiring",
                data=self.wiring_data,
                parent_id=parent.id,
                comment=self.experiment_name,
            )

        # Push data.json (fit results and dataset references)
        if self.results_data is not None:
            qc.data.push(
                datatype="node_data",
                data=self.results_data,
                parent_id=parent.id,
                comment=self.experiment_name,
            )

        # Push PNG files
        for png_data in self.png_data.values():
            qc.data.push(
                datatype="figure",
                data=png_data,
                parent_id=parent.id,
                comment=self.experiment_name,
            )

        # Push all raw-data files as one dataset
        if raw_bundle is not None:
            if (
                qc.data.push(
                    datatype=EXP_DATA_DATATYPE,
                    data=raw_bundle,
                    parent_id=parent.id,
                    comment=self.experiment_name,
                )
                is None
            ):
                print("✗ Failed to upload raw data")

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

        try:
            results_info = None
            results_children = qc.data.list_children(
                datatype="node_data", parent_dataset_id=dataset_id
            )
            if results_children:
                results_info = qc.data.get(results_children[0].id)
                print("✓ Retrieved node_data")
            else:
                print("✗ No node_data found")
        except Exception as e:
            print(f"✗ Could not retrieve node_data: {str(e)}")
            results_info = None

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

        # Save data.json
        if results_info:
            with open(experiment_dir / "data.json", "w") as f:
                json.dump(results_info.data, f, indent=4)
            print("✓ Saved data.json")

        # Save PNG files
        png_files = [
            qc.data.get(metadata.id)
            for metadata in qc.data.list_children(
                datatype="figure",
                parent_dataset_id=dataset_id,
                limit=CHILDREN_LIMIT,
            )
        ]
        png_count = 0
        for png_data in png_files:
            if png_data.data.get("__type__") == "png/base64":
                file_name = png_data.data.get("file_name")
                if file_name:
                    png_bytes = base64.b64decode(png_data.data["data"])
                    with open(experiment_dir / file_name, "wb") as f:
                        f.write(png_bytes)
                    png_count += 1
            else:
                print(
                    f"✗ Unexpected data type in PNG file: {png_data.data.get('__type__')}"
                )
        if png_count > 0:
            print(f"✓ Saved {png_count} PNG file(s)")
        else:
            print("✗ No PNG files found")

        # Save experiment data files (*.h5 / *.npz)
        raw_count = 0
        exp_data_children = []
        for datatype in (EXP_DATA_DATATYPE, LEGACY_EXP_DATA_DATATYPE):
            exp_data_children.extend(
                qc.data.list_children(
                    datatype=datatype,
                    parent_dataset_id=dataset_id,
                    limit=CHILDREN_LIMIT,
                )
                or []
            )
        for metadata in exp_data_children:
            data = qc.data.get(metadata.id).data
            # Bundled (exp_data or legacy raw_data) and single-file payloads.
            if data.get("__type__") in (
                EXP_BUNDLE_TYPE,
                LEGACY_EXP_BUNDLE_TYPE,
            ):
                payloads = data.get("files", [])
            else:
                payloads = [data]
            for payload in payloads:
                file_name = Path(payload.get("file_name", "")).name
                if not file_name:
                    print("✗ Raw data file without a file name")
                    continue
                try:
                    raw = cls.decode_raw_file(payload)
                except Exception as e:
                    print(f"✗ Could not decode raw data {file_name}: {str(e)}")
                    continue
                with open(experiment_dir / file_name, "wb") as f:
                    f.write(raw)
                raw_count += 1
        if raw_count > 0:
            print(f"✓ Saved {raw_count} raw data file(s)")
        else:
            print("✗ No raw data files found")

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
