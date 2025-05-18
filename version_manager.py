#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

def get_current_version() -> str:
    """Read the current version from pyproject.toml."""
    with open("pyproject.toml", "r") as f:
        content = f.read()
        match = re.search(r'version = "([\d.]+)"', content)
        if not match:
            raise ValueError("Could not find version in pyproject.toml")
        return match.group(1)

def get_remote_version() -> str:
    """Get the version from the remote repository."""
    try:
        # Fetch the latest changes
        subprocess.run(["git", "fetch", "origin"], check=True)
        
        # Get the remote version from pyproject.toml
        result = subprocess.run(
            ["git", "show", "origin/main:pyproject.toml"],
            capture_output=True,
            text=True,
            check=True
        )
        
        match = re.search(r'version = "([\d.]+)"', result.stdout)
        if not match:
            raise ValueError("Could not find version in remote pyproject.toml")
        return match.group(1)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching remote version: {e}")
        sys.exit(1)

def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse version string into major, minor, patch components."""
    major, minor, patch = map(int, version.split("."))
    return major, minor, patch

def update_version(new_version: str) -> None:
    """Update the version in all relevant files."""
    # Update pyproject.toml
    with open("pyproject.toml", "r") as f:
        content = f.read()
    
    new_content = re.sub(
        r'version = "[\d.]+"',
        f'version = "{new_version}"',
        content
    )
    
    with open("pyproject.toml", "w") as f:
        f.write(new_content)
    
    # Update __init__.py
    init_path = Path("cloud_qualibrate_link/__init__.py")
    if init_path.exists():
        with open(init_path, "r") as f:
            content = f.read()
        
        new_content = re.sub(
            r'__version__ = "[\d.]+"',
            f'__version__ = "{new_version}"',
            content
        )
        
        with open(init_path, "w") as f:
            f.write(new_content)

def main():
    current_version = get_current_version()
    remote_version = get_remote_version()
    
    current_major, current_minor, current_patch = parse_version(current_version)
    remote_major, remote_minor, remote_patch = parse_version(remote_version)
    
    # Check if versions are the same
    if current_version == remote_version:
        # Increment patch version
        new_version = f"{current_major}.{current_minor}.{current_patch + 1}"
        print(f"Current version {current_version} is the same as remote. Incrementing to {new_version}")
        update_version(new_version)
        return
    
    # Check if current version is more than one patch version ahead
    if current_patch > remote_patch + 1:
        new_version = f"{current_major}.{current_minor}.{remote_patch + 1}"
        print(f"Warning: Current version {current_version} is more than one patch version ahead of remote {remote_version}")
        print(f"Lowering version to {new_version}")
        update_version(new_version)
        return
    
    # Check if current version is exactly one patch version ahead
    if current_patch == remote_patch + 1:
        print(f"Current version {current_version} is exactly one patch version ahead of remote {remote_version}")
        print("No changes needed.")
        return
    
    # If we get here, the current version is behind the remote version
    print(f"Error: Current version {current_version} is behind remote version {remote_version}")
    sys.exit(1)

if __name__ == "__main__":
    main() 