# Qualibrate Cloud Handler

A Python tool for uploading Qualibrate experiment data to cloud storage.

## Features

- Loads and processes Qualibrate experiment data from local directories
- Converts PNG files to base64 format
- Uploads experiment data to cloud storage using IQCC Cloud
- Supports uploading node.json, state.json, wiring.json, and PNG files
- Downloads and stores calibration data from the cloud

## Installation

### Prerequisites
- Python 3.12 or higher
- iqcc-cloud package (installed separately via wheel file)
- pathlib (included in Python standard library)

### Using pip
```bash
pip install qualibrate-cloud
```

### Development Setup
1. Clone the repository:
```bash
git clone git@github.com:i-qcc/cloud_qualibrate_link.git
cd cloud_qualibrate_link
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Activate the virtual environment:
```bash
poetry shell
```

## Usage

```python
from qualibrate_cloud_handler import QualibrateCloudHandler

# Initialize the handler with your experiment path
handler = QualibrateCloudHandler("/path/to/your/experiment")

# Upload the experiment data to the cloud
handler.upload_to_cloud("your_quantum_computer_backend")

# Download calibration data from the cloud
QualibrateCloudHandler.store_from_cloud("your_quantum_computer_backend")
```

## Project Structure

The experiment directory should contain:
- `node.json` - Experiment metadata and configuration
- `quam_state/` directory containing:
  - `state.json` - Experiment state information
  - `wiring.json` - Wiring configuration
- PNG files (optional) - Any PNG files in the experiment directory will be processed and uploaded

## Development

### Running Tests
```bash
poetry run pytest
```

### Code Formatting
```bash
poetry run black .
poetry run isort .
```

### Linting
```bash
poetry run flake8
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Make your changes
4. Run tests and ensure they pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 