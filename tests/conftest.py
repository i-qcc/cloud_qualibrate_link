import pytest
import os
from pathlib import Path

@pytest.fixture
def experiment_path():
    return f"/home/omrieoqm/.qualibrate/user_storage/QC1/2025-04-14/#3987_ramsey_flux_calibration_160603"

@pytest.fixture
def backend_name():
    return "arbel" 