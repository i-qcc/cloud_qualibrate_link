import json
import os
from types import SimpleNamespace

import pytest

from iqcc_qualibrate2cloud import qualibrate_cloud_handler as handler_module
from iqcc_qualibrate2cloud import QualibrateCloudHandler


class FakeDataService:
    def __init__(self):
        self.datasets = {}

    def push(self, datatype, data="", comment="", parent_id=None):
        dataset_id = len(self.datasets) + 1
        self.datasets[dataset_id] = SimpleNamespace(
            id=dataset_id, type=datatype, data=data, parent_id=parent_id
        )
        return self.datasets[dataset_id]

    def get(self, dataset_id):
        return self.datasets[dataset_id]

    def list_children(
        self, parent_dataset_id, datatype=None, limit=10, **kwargs
    ):
        children = [
            d
            for d in self.datasets.values()
            if d.parent_id == parent_dataset_id
            and (datatype is None or d.type == datatype)
        ]
        return children[:limit]


@pytest.fixture
def fake_cloud(monkeypatch):
    data = FakeDataService()
    monkeypatch.setattr(
        handler_module,
        "IQCC_Cloud",
        lambda **kwargs: SimpleNamespace(data=data),
    )
    return data


@pytest.fixture
def node_dir(tmp_path):
    node = tmp_path / "#1_test_node"
    (node / "quam_state").mkdir(parents=True)
    (node / "node.json").write_text(
        json.dumps({"metadata": {"name": "test_node"}, "data": {}})
    )
    (node / "quam_state" / "state.json").write_text(json.dumps({"q": 1}))
    (node / "quam_state" / "wiring.json").write_text(json.dumps({"w": 2}))
    (node / "data.json").write_text(
        json.dumps({"ds_raw": "./ds_raw.h5", "fit_results": {"q1": 0.5}})
    )
    (node / "figure.png").write_bytes(b"\x89PNG fake")
    (node / "ds_raw.h5").write_bytes(b"\x89HDF" + bytes(range(256)) * 100)
    (node / "ds_fit.h5").write_bytes(b"\x89HDF" + os.urandom(5000))
    (node / "arrays.npz").write_bytes(b"PK" + bytes(1000))
    return node


def test_round_trip_restores_all_files(fake_cloud, node_dir, tmp_path):
    QualibrateCloudHandler(str(node_dir)).upload_to_cloud("backend")

    types = sorted(d.type for d in fake_cloud.datasets.values())
    assert types.count("raw_data") == 3
    assert {"wiring", "node_data", "figure"} <= set(types)

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    QualibrateCloudHandler._save_experiment_data(
        SimpleNamespace(data=fake_cloud), 1, out_dir
    )

    for rel in [
        "node.json",
        "data.json",
        "quam_state/wiring.json",
        "figure.png",
        "ds_raw.h5",
        "ds_fit.h5",
        "arrays.npz",
    ]:
        original, restored = node_dir / rel, out_dir / rel
        if rel.endswith(".json"):
            assert json.loads(restored.read_text()) == json.loads(
                original.read_text()
            )
        else:
            assert restored.read_bytes() == original.read_bytes()


def test_raw_data_opt_out(fake_cloud, node_dir):
    QualibrateCloudHandler(str(node_dir)).upload_to_cloud(
        "backend", upload_raw_data=False
    )
    assert "raw_data" not in {d.type for d in fake_cloud.datasets.values()}


def test_files_over_cap_are_skipped(fake_cloud, node_dir):
    QualibrateCloudHandler(str(node_dir)).upload_to_cloud(
        "backend", max_raw_file_bytes=2000
    )
    uploaded = {
        d.data["file_name"]
        for d in fake_cloud.datasets.values()
        if d.type == "raw_data"
    }
    assert uploaded == {"ds_raw.h5", "arrays.npz"}
    assert fake_cloud.datasets[1].data["skipped_raw_files"] == ["ds_fit.h5"]


def test_corrupted_payload_is_rejected(node_dir):
    payload = QualibrateCloudHandler.encode_raw_file(node_dir / "ds_raw.h5")
    payload["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="sha256"):
        QualibrateCloudHandler.decode_raw_file(payload)

    payload = QualibrateCloudHandler.encode_raw_file(node_dir / "ds_raw.h5")
    payload["size"] = 10
    with pytest.raises(ValueError, match="size"):
        QualibrateCloudHandler.decode_raw_file(payload)
