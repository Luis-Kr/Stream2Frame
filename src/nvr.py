from datetime import datetime, timedelta
from pathlib import Path
import warnings
from typing import List, Tuple
import cv2
import pandas as pd 
import logging
import sys
import subprocess
from collections import defaultdict
from natsort import natsorted
import csv
import numpy as np
from multiprocessing import Pool, cpu_count
from itertools import islice

# Hydra and OmegaConf imports
import hydra
from hydra import compose, initialize
from omegaconf import DictConfig

sys.path.append(str(Path(__file__).parent.parent.absolute()))

# Custom imports
import utils as utils

# Ignore warnings
warnings.filterwarnings("ignore")

# get the path of the current file
root_dir = Path(__file__).parent.parent.absolute()

def convert_single_camera(cfg: DictConfig, 
                          logger: logging.Logger, 
                          year: str, 
                          month: str, 
                          day: str, 
                          camera_name: str, 
                          cam_mac_address: str) -> None:
    
    # Keep exact camera name (e.g., G5Bullet_07)
    search_pattern = f"{cam_mac_address}_0_rotating*.ubv"
    src_dir = Path(root_dir) / cfg.NVR.src_dir / str(year) / f"{month:02}" / f"{day:02}"
    dst_dir = Path(root_dir) / cfg.NVR.dst_dir / f"{year}-{month:02}-{day:02}" / camera_name
    
    utils.log_separator(logger)
    logger.info(f"::: Processing camera {camera_name} with MAC address {cam_mac_address} :::")
    logger.info(f"Source directory: {src_dir}")
    logger.info(f"Destination directory: {dst_dir}")
    utils.log_separator(logger)
    
    # Initialize the prefix counter
    prefix_counter = 1
    
    if not dst_dir.exists():
        dst_dir.mkdir(parents=True)

    # Loop through each matching file in the source directory
    for file in sorted(Path(src_dir).glob(search_pattern)):
        # Use exact camera_name from config
        current_dst_dir = dst_dir / f"{camera_name}_{cam_mac_address}_{year}-{month:02d}-{day:02d}_{prefix_counter}"

        # Run the command for each file
        subprocess.run([
            "/usr/share/unifi-protect/app/node_modules/.bin/ubnt_ubvexport",
            "-s", str(file),
            "-d", str(current_dst_dir)
        ], capture_output=True)
        
        # Define the output file path for the ubnt_ubvinfo command
        output_file = f"{current_dst_dir}.txt"

        # Run the ubnt_ubvinfo command for each file and capture the output
        with open(output_file, 'w') as f:
            subprocess.run([
                "/usr/share/unifi-protect/app/node_modules/.bin/ubnt_ubvinfo",
                "-f", str(file),
                "-t", "7",
                "-H",
            ], stdout=f, stderr=subprocess.STDOUT)

        # Log success message
        logger.info(f"Successfully converted {file} to {current_dst_dir}")

        # Increment the prefix counter
        prefix_counter += 1
        
        break
        

def rename_mp4_files(logger: logging.Logger, src_dir: Path) -> None:
    # Loop through the files in the directory
    for file in src_dir.iterdir():
        if file.is_file() and file.suffix == '.mp4' and '_0.mp4' in str(file):
            # Extract the base name up to _0.mp4 and preserve the camera name format
            base_name = str(file)
            new_name = base_name.replace('_0.mp4', '.mp4')
            new_file = Path(new_name)
            
            # Rename the file
            file.rename(new_file)
            logger.info(f"Renamed {file} to {new_file}")
                
                
def concat_videos(src_dir: Path, logger: logging.Logger) -> None:
    # Group files by their base name
    video_groups = defaultdict(list)
    for file in src_dir.iterdir():
        if file.is_file() and file.suffix == '.mp4':
            base_name = file.stem.rsplit('_', 1)[0]
            video_groups[base_name].append(file)
            
    print(video_groups)

    # Stitch videos together
    for base_name, files in video_groups.items():
        if len(files) > 1:
            # Sort files by their suffix number
            files.sort(key=lambda x: int(x.stem.rsplit('_', 1)[1]))

            # Create a temporary text file listing the files to concatenate
            concat_file_path = src_dir / f"{base_name}_concat_list.txt"
            with open(concat_file_path, 'w') as concat_file:
                for file in files:
                    concat_file.write(f"file '{file}'\n")

            # Construct the output file name
            output_file = src_dir / f"{base_name}.mp4"

            # Run ffmpeg to concatenate the files
            ffmpeg_command = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file_path),
                '-c', 'copy',
                str(output_file)
            ]

            try:
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Stitched {files} into {output_file}")
            except subprocess.CalledProcessError as e:
                logger.error(f"An error occurred while stitching videos: {e}")

            # Remove the temporary text file
            concat_file_path.unlink()
            

def find_file_pairs(src_dir: Path) -> List[Tuple[str, str]]:
    file_pairs = []

    # Loop through the mp4 files in the source directory and find corresponding txt files
    for mp4_file in natsorted(src_dir.rglob("*.mp4")):
        txt_file = mp4_file.with_suffix('.txt')
        file_pairs.append((str(mp4_file), str(txt_file)))

    return file_pairs


def process_frame_data(mp4_txt_file: str) -> Tuple[List[int], List[str]]:
    """
    Processes video frame data to add an offset to the CTS column,
    and resamples the data to 5-minute intervals to get frame numbers and corresponding dates.

    Args:
        mp4_txt_file (str): Path to the text file containing video frame data.

    Returns:
        tuple: A tuple containing two lists - frame numbers and corresponding frame dates.
    """
    # Read the file into a pandas DataFrame and convert the 'CTS' column to datetime
    df = pd.read_csv(mp4_txt_file, sep='\s+', skipfooter=5, on_bad_lines='skip', engine='python')
    df['CTS'] = pd.to_datetime(df['CTS'])
    
    # Add the offset to the 'CTS' column and ensure it's a DatetimeIndex
    df['CTS'] = df['CTS'] + timedelta(hours=1, minutes=59, seconds=59)
    df['CTS'] = pd.to_datetime(df['CTS'], format='%Y-%m-%d %H:%M:%S')

    # Add a column with numbers from 0 to the number of rows in the DataFrame
    df['frame'] = range(len(df))

    # Set the 'CTS' column as the index and resample the DataFrame to 5-minute intervals
    df.set_index('CTS', inplace=True)
    frame_numbers = df['frame'].resample('2min').first().dropna().tolist()
    
    # Get the corresponding frame dates
    frame_dates = [df.iloc[date].name.strftime('%Y-%m-%d_%H_%M_%S') for date in frame_numbers]
    
    return frame_numbers, frame_dates


def extract_frames_to_video_and_csv(logger: logging.Logger, 
                                  mp4_file: str,
                                  fn: int,
                                  frame_numbers: List[int], 
                                  frame_dates: List[str],
                                  camera_name: str,
                                  output_dir: str,
                                  video_writer: cv2.VideoWriter = None,
                                  frame_width: int = None,
                                  frame_height: int = None,
                                  batch_size: int = 500) -> Tuple[int, cv2.VideoWriter, int, int]:
    """High-performance version optimized for speed"""
    
    # Enable OpenCV optimizations
    cv2.setUseOptimized(True)
    
    # Minimize logging during processing to improve performance
    minimal_logging = True
    
    video_capture = cv2.VideoCapture(mp4_file)
    if not video_capture.isOpened():
        logger.error(f"Could not open video: {mp4_file}")
        return fn, video_writer, frame_width, frame_height

    # Initialize video writer if needed
    if frame_width is None or frame_height is None:
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if video_writer is None:
        output_video_path = Path(output_dir) / f'{camera_name}_output_video.mp4'
        # Use mp4v codec which is faster on most systems
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(str(output_video_path), fourcc, 30, (frame_width, frame_height))
        if not video_writer.isOpened():
            logger.error("Failed to initialize video writer. Trying MJPG.")
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            video_writer = cv2.VideoWriter(str(output_video_path.with_suffix('.avi')), fourcc, 30, (frame_width, frame_height))

    # Prepare CSV file
    csv_file_path = Path(output_dir) / f'{camera_name}_frame_data.csv'
    csv_exists = csv_file_path.exists()
    
    # Direct array for storing CSV data
    csv_data = []
    if not csv_exists:
        csv_data.append(['frame_number', 'frame_date'])
    
    # Sort frame numbers once for sequential access (major performance boost)
    frame_data = sorted(zip(frame_numbers, frame_dates), key=lambda x: x[0])
    total_frames = len(frame_data)
    
    if total_frames == 0:
        logger.warning("No frames to extract")
        return fn, video_writer, frame_width, frame_height
    
    start_time = datetime.now()
    frames_processed = 0
    
    try:
        # Buffer for more efficient file IO
        prev_frame_number = -1
        
        # Process all frames at once - minimize logging during processing
        for frame_number, frame_date in frame_data:
            # Optimize seeks by checking if we need to move
            if prev_frame_number != frame_number - 1:
                video_capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
            
            ret, frame = video_capture.read()
            prev_frame_number = frame_number
            
            if not ret:
                continue
            
            # Write frame directly to reduce memory usage
            video_writer.write(frame)
            csv_data.append([fn, frame_date])
            fn += 1
            frames_processed += 1
            
            # Report progress less frequently
            if not minimal_logging and frames_processed % 2000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                fps = frames_processed / elapsed if elapsed > 0 else 0
                logger.info(f"Progress: {frames_processed}/{total_frames} frames ({fps:.2f} fps)")
    
    except Exception as e:
        logger.error(f"Error processing frames: {e}")
    
    finally:
        # Write all CSV data at once (much faster)
        with open(csv_file_path, mode='w', newline='') as csv_file:
            csv.writer(csv_file).writerows(csv_data)
        
        # Calculate and log performance 
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > 0 and frames_processed > 0:
            logger.info(f"Performance: {frames_processed} frames in {elapsed:.2f}s ({frames_processed/elapsed:.2f} fps)")
    
    return fn, video_writer, frame_width, frame_height


def transfer_data_local_remote(logger: logging.Logger, 
                               local_dir: str, 
                               remote_user: str, 
                               remote_host: str, 
                               remote_dir: str) -> None:
    # Construct the rsync command
    rsync_command = [
        'rsync',
        '-avz',  # Options: archive mode, verbose, compress file data during the transfer
        '--progress',
        '-e', 'ssh',  # Use SSH for the transfer
        local_dir,
        f'{remote_user}@{remote_host}:{remote_dir}',
    ]

    # Execute the rsync command
    try:
        subprocess.run(rsync_command, check=True)
        logger.info(f"Data transferred successfully from {local_dir} to {remote_user}@{remote_host}:{remote_dir}")
    except subprocess.CalledProcessError as e:
        logger.info(f"An error occurred while transferring data: {e}")


# def capture_and_save_frames(logger: logging.Logger, 
#                             mp4_file: str,
#                             frame_numbers: List[int], 
#                             frame_dates: List[str],
#                             camera_name: str,
#                             output_dir: str) -> None:
#     """
#     Captures frames from a video file at specified frame numbers and saves them with corresponding dates.

#     Args:
#         mp4_file (str): Path to the video file.
#         frame_numbers (List[int]): List of frame numbers to capture.
#         frame_dates (List[str]): List of corresponding frame dates for naming the saved frames.
#     """
#     video_capture = cv2.VideoCapture(mp4_file)

#     if not video_capture.isOpened():
#         logger.info("Error: Could not open video.")
#         return

#     for i, (frame_number, frame_date) in enumerate(zip(frame_numbers, frame_dates)):
#         try:
#             video_capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_number))
#             ret, frame = video_capture.read()
            
#             if not ret:
#                 print("Break: Could not read frame or video is fully processed.")
#                 break
            
#             frame_filename = Path(output_dir) / f'{camera_name}_{frame_date}.jpg'
#             logger.info(f"Writing frame {frame_filename}")
#             cv2.imwrite(frame_filename, frame)
        
#         except Exception as e:
#             logger.error(f"Error: {e}")
#             logger.error(f"Could not write frame of camera {camera_name} with the date: {frame_date}.")
#             continue

#     video_capture.release()