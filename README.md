# Qualibrate handler for IQCC cloud

A Python tool for uploading [Qualibrate](https://github.com/qua-platform/qualibrate) experiment data to [IQCC](https://i-qcc.com) cloud storage.

## Features

- Loads and processes Qualibrate experiment data from local directories
- Converts PNG files to base64 format
- Uploads experiment data to cloud storage using IQCC Cloud
- Supports uploading node.json, state.json, wiring.json, data.json and PNG files
- Uploads raw-data files (`*.h5`, `*.npz`) so plots can be recreated from the cloud
- Downloads and stores calibration data from the cloud, restoring the node folder layout

## Cloud datasets

Each node is pushed as a parent dataset (datatype = node name) with these children:

| datatype    | content                                                       |
|-------------|---------------------------------------------------------------|
| `node_info` | `node.json`                                                   |
| `state`     | `quam_state/state.json`                                       |
| `wiring`    | `quam_state/wiring.json`                                      |
| `node_data` | `data.json` (fit results and references to the dataset files) |
| `figure`    | one per `*.png`, base64 encoded                               |
| `exp_data`  | a single dataset bundling all `*.h5` / `*.npz` files          |

The `exp_data` payload is
`{"__type__": "exp_data/bundle", "files": [{"file_name", "size", "sha256", "data"}, ...]}`,
where `data` is the file zlib compressed then base64 encoded. The size and
sha256 of each original file are checked on download.

The total encoded size of the bundle is capped by `max_raw_bytes` (default
15 MiB). If it does not fit, the largest files are skipped with a warning and
listed under `skipped_raw_files` in the parent dataset. Raw-data upload can be
turned off with `upload_raw_data=False`.

## Installation

`pip install iqcc-qualibrate2cloud`

## Usage

```python
from iqcc-qualibrate2cloud import QualibrateCloudHandler

# Initialize the handler with your experiment path
handler = QualibrateCloudHandler("/path/to/your/experiment")

# Upload the experiment data (including raw data) to the cloud
handler.upload_to_cloud("your_quantum_computer_backend")

# Upload without raw data, or with a different per-file size cap
handler.upload_to_cloud("your_quantum_computer_backend", upload_raw_data=False)
handler.upload_to_cloud(
    "your_quantum_computer_backend", max_raw_bytes=5 * 1024**2
)

# Download calibration data from the cloud
QualibrateCloudHandler.store_from_cloud("your_quantum_computer_backend")
```

## Development

### Running Tests
```bash
uvx ruff run pytest
```

### Code Formatting
```bash
uvx ruff format
```

### Linting
```bash
uvx ruff check
```