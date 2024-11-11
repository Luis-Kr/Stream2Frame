# Stream2Frame

A Python-based tool for processing and extracting frames from UniFi Protect camera recordings.

## Overview

Stream2Frame is designed to process .ubv video files from UniFi Protect cameras, convert them to MP4 format, extract frames at specified intervals, and transfer the processed data to a remote server.

## Features

- Converts UniFi Protect .ubv files to MP4 format
- Extracts frames at 2-minute intervals
- Generates synchronized CSV files with frame timestamps
- Creates a consolidated video files
- Transfers processed data to a remote server
- Automatic cleanup of processed files

## Configuration

1. Create and edit `config/utils/cams.yaml` to define your cameras:

```yaml

CameraName: MAC_ADDRESS

```

2. Configure the Hydra settings in the config directory for:
- Source and destination directories
- Remote server settings
- Processing parameters


## Usage

1. Run the main processing script:

```bash

./scripts/main_wrapper.sh

```

2. For manual execution with specific dates:

```bash

python src/main.py NVR.year=YYYY NVR.month=MM NVR.day=DD

```

3. Clean up processed files:

```bash

# Run delete_files.sh periodically to clean up processed files and maintain storage space.

./src/delete_files.sh

```