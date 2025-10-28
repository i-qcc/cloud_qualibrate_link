# Qualibrate handler for IQCC cloud

A Python tool for uploading [Qualibrate](https://github.com/qua-platform/qualibrate) experiment data to [IQCC](https://i-qcc.com) cloud storage.

## Features

- Loads and processes Qualibrate experiment data from local directories
- Converts PNG files to base64 format
- Uploads experiment data to cloud storage using IQCC Cloud
- Supports uploading node.json, state.json, wiring.json, and PNG files
- Downloads and stores calibration data from the cloud

## Installation

`pip install iqcc-qualibrate2cloud`

## Usage

```python
from iqcc-qualibrate2cloud import QualibrateCloudHandler

# Initialize the handler with your experiment path
handler = QualibrateCloudHandler("/path/to/your/experiment")

# Upload the experiment data to the cloud
handler.upload_to_cloud("your_quantum_computer_backend")

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