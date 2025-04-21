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
import re

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
    """
    Concatenate video files in the source directory.
    Handles two cases:
    1. Regular concatenation of videos with same base name but different sequence numbers
    2. Special case for split files with patterns like _1.mp4, _2.mp4, etc.
    """
    # Handle split video files first (files with _N.mp4 pattern)
    split_groups = defaultdict(list)
    for file in src_dir.iterdir():
        if file.is_file() and file.suffix == '.mp4':
            # Match pattern like 'G5Bullet_27_F4E2C678D10D_2025-04-12_8_1.mp4'
            match = re.search(r'^(.+_\d+)_(\d+)\.mp4$', file.name)
            if match:
                base_name = match.group(1)  # e.g., 'G5Bullet_27_F4E2C678D10D_2025-04-12_8'
                split_groups[base_name].append(file)
    
    # Process the split files
    for base_name, files in split_groups.items():
        if len(files) > 1:
            # Sort files by their suffix number
            files.sort(key=lambda x: int(re.search(r'^.+_(\d+)\.mp4$', x.name).group(1)))
            
            # Create a temporary text file listing the files to concatenate
            concat_file_path = src_dir / f"{base_name}_concat_list.txt"
            with open(concat_file_path, 'w') as concat_file:
                for file in files:
                    concat_file.write(f"file '{file.name}'\n")
            
            # Construct the output file name - match the base name format that corresponds to the txt file
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
                logger.info(f"Concatenating split files for {base_name}: {[f.name for f in files]}")
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Successfully concatenated split files into {output_file}")
                
                # Optionally remove the original split files
                for file in files:
                    file.unlink()
                    logger.info(f"Removed original split file: {file}")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"An error occurred while concatenating split videos: {e}")
            
            # Remove the temporary text file
            concat_file_path.unlink()
    
    # Now handle the regular concatenation case (files with same base but different sequence numbers)
    video_groups = defaultdict(list)
    for file in src_dir.iterdir():
        if file.is_file() and file.suffix == '.mp4':
            # Skip files that were already processed as split files
            if any(file.name.startswith(f"{base}_") for base in split_groups.keys()):
                continue
                
            base_name = file.stem.rsplit('_', 1)[0]
            video_groups[base_name].append(file)

    # Process regular video groups
    for base_name, files in video_groups.items():
        if len(files) > 1:
            # Sort files by their suffix number
            files.sort(key=lambda x: int(x.stem.rsplit('_', 1)[1]))

            # Create a temporary text file listing the files to concatenate
            concat_file_path = src_dir / f"{base_name}_concat_list.txt"
            with open(concat_file_path, 'w') as concat_file:
                for file in files:
                    concat_file.write(f"file '{file.name}'\n")

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
                logger.info(f"Concatenating sequence files: {[f.name for f in files]}")
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Successfully concatenated sequence files into {output_file}")
            except subprocess.CalledProcessError as e:
                logger.error(f"An error occurred while concatenating sequence videos: {e}")

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


# def extract_frames_ffmpeg(logger: logging.Logger,
#                           mp4_file: str,
#                           fn: int,
#                           frame_numbers: List[int],
#                           frame_dates: List[str],
#                           camera_name: str,
#                           output_dir: str,
#                           write_csv: bool = True) -> Tuple[int, List]:
#     """Ultra-fast frame extraction using direct FFmpeg commands"""
    
#     import shutil  # Add missing import
    
#     output_dir_path = Path(output_dir)
#     output_video_path = output_dir_path / f'{camera_name}_output_video.mp4'
#     csv_file_path = output_dir_path / f'{camera_name}_frame_data.csv'
#     csv_exists = csv_file_path.exists()
    
#     # Create a temp directory for frames
#     temp_dir = output_dir_path / "temp_frames"
#     temp_dir.mkdir(exist_ok=True)
    
#     # Sort frame numbers for sequential access
#     frame_data = sorted(zip(frame_numbers, frame_dates), key=lambda x: x[0])
#     total_frames = len(frame_data)
    
#     if total_frames == 0:
#         logger.warning("No frames to extract")
#         return fn, []
    
#     frame_data_list = []
#     start_time = datetime.now()
#     frames_processed = 0  # Initialize this variable before it's used
    
#     try:
#         # Extract frames using FFmpeg
#         frame_list_file = output_dir_path / "frame_list.txt"
#         with open(frame_list_file, 'w') as f:
#             for i, (frame_number, frame_date) in enumerate(frame_data):
#                 output_frame = temp_dir / f"frame_{i:06d}.png"
#                 f.write(f"select=eq(n\\,{frame_number}),outputfile='{output_frame}'\n")
#                 frame_data_list.append({'frame_number': fn + i, 'frame_date': frame_date})
        
#         # Execute FFmpeg to extract all frames at once (much faster)
#         ffmpeg_extract_cmd = [
#             'ffmpeg', '-i', mp4_file, '-f', 'lavfi',
#             '-filter_complex', f"sendcmd=filename='{frame_list_file}'",
#             '-y', str(temp_dir / "dummy.mp4")  # Convert Path to string
#         ]
        
#         extract_result = subprocess.run(ffmpeg_extract_cmd, check=True, capture_output=True)
#         logger.debug(extract_result.stderr.decode())
        
#         # Create a new video from extracted frames
#         ffmpeg_concat_cmd = [
#             'ffmpeg', '-framerate', '30',
#             '-pattern_type', 'glob', '-i', f"{temp_dir}/*.png",
#             '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
#             '-y', str(output_video_path)  # Convert Path to string
#         ]
        
#         concat_result = subprocess.run(ffmpeg_concat_cmd, check=True, capture_output=True)
#         logger.debug(concat_result.stderr.decode())
        
#         frames_processed = len(frame_data_list)
#         fn += frames_processed
        
#     except Exception as e:
#         logger.error(f"Error processing frames with FFmpeg: {e}")
#         return fn, frame_data_list
    
#     finally:
#         # Write CSV efficiently
#         if write_csv and frame_data_list:
#             try:
#                 with open(csv_file_path, 'a' if csv_exists else 'w', newline='') as f:
#                     writer = csv.DictWriter(f, fieldnames=['frame_number', 'frame_date'])
#                     if not csv_exists:
#                         writer.writeheader()
#                     writer.writerows(frame_data_list)
#                 logger.info(f"Saved frame data to {csv_file_path}")
#             except Exception as e:
#                 logger.error(f"Error saving CSV file: {e}")
        
#         # Clean up temp files
#         try:
#             shutil.rmtree(temp_dir)
#             frame_list_file.unlink()
#         except Exception as e:
#             logger.warning(f"Error cleaning up temporary files: {e}")
        
#         # Log performance
#         elapsed = (datetime.now() - start_time).total_seconds()
#         if elapsed > 0 and frames_processed > 0:
#             logger.info(f"Performance: {frames_processed} frames in {elapsed:.2f}s ({frames_processed/elapsed:.2f} fps)")
    
#     return fn, frame_data_list


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
                                  batch_size: int = 500,
                                  write_csv: bool = True) -> Tuple[int, cv2.VideoWriter, int, int, List]:
    """High-performance version optimized for speed"""
    # Enable OpenCV optimizations
    cv2.setUseOptimized(True)
    
    # Minimize logging during processing to improve performance
    minimal_logging = True
    
    video_capture = cv2.VideoCapture(mp4_file)
    if not video_capture.isOpened():
        logger.error(f"Could not open video: {mp4_file}")
        return fn, video_writer, frame_width, frame_height, []

    # Initialize video writer if needed
    if frame_width is None or frame_height is None:
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if video_writer is None:
        output_video_path = Path(output_dir) / f'{camera_name}_output_video.mp4'
        # Use mp4v codec which is faster on most systems
        fourcc = cv2.VideoWriter_fourcc(*'avc1') #mp4v, avc1
        video_writer = cv2.VideoWriter(str(output_video_path), fourcc, 30, (frame_width, frame_height))
        if not video_writer.isOpened():
            logger.error("Failed to initialize video writer. Trying MJPG.")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(str(output_video_path.with_suffix('.avi')), fourcc, 30, (frame_width, frame_height))

    # Prepare CSV file if needed
    csv_file_path = Path(output_dir) / f'{camera_name}_frame_data.csv'
    csv_exists = csv_file_path.exists()
    
    # Direct array for storing CSV data
    frame_data_list = []
    csv_headers = ['frame_number', 'frame_date']
    
    # Sort frame numbers once for sequential access (major performance boost)
    frame_data = sorted(zip(frame_numbers, frame_dates), key=lambda x: x[0])
    total_frames = len(frame_data)
    
    if total_frames == 0:
        logger.warning("No frames to extract")
        return fn, video_writer, frame_width, frame_height, []
    
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
            frame_data_list.append({'frame_number': fn, 'frame_date': frame_date})
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
        # Write all CSV data at once if requested
        if write_csv and frame_data_list:
            try:
                df = pd.DataFrame(frame_data_list)
                # If file exists, append without headers
                if csv_exists:
                    df.to_csv(csv_file_path, mode='a', header=False, index=False)
                else:
                    df.to_csv(csv_file_path, index=False)
                logger.info(f"Saved frame data to {csv_file_path}")
            except Exception as e:
                logger.error(f"Error saving CSV file: {e}")
        
        # Calculate and log performance 
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > 0 and frames_processed > 0:
            logger.info(f"Performance: {frames_processed} frames in {elapsed:.2f}s ({frames_processed/elapsed:.2f} fps)")
    
    # Return the accumulated frame data along with other return values
    return fn, video_writer, frame_width, frame_height, frame_data_list


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


def extract_frames_fallback(logger: logging.Logger,
                          mp4_file: str,
                          fn: int,
                          camera_name: str,
                          output_dir: str,
                          video_writer: cv2.VideoWriter = None,
                          frame_width: int = None,
                          frame_height: int = None,
                          interval_minutes: int = 2) -> Tuple[int, cv2.VideoWriter, int, int, List]:
    """
    Fallback function to extract frames directly from video without text file data.
    Uses fixed intervals based on video frame rate and duration.
    
    Args:
        logger: Logger object
        mp4_file: Path to the MP4 file
        fn: Current frame number counter
        camera_name: Name of the camera
        output_dir: Directory to save output
        video_writer: Optional video writer object
        frame_width: Optional frame width
        frame_height: Optional frame height
        interval_minutes: Interval between frames in minutes (default: 2)
        
    Returns:
        Tuple of (updated frame counter, video writer, width, height, frame data list)
    """
    logger.info(f"Using fallback frame extraction for {mp4_file}")
    
    # Enable OpenCV optimizations
    cv2.setUseOptimized(True)
    
    # Open the video file
    video_capture = cv2.VideoCapture(mp4_file)
    if not video_capture.isOpened():
        logger.error(f"Could not open video: {mp4_file}")
        return fn, video_writer, frame_width, frame_height, []
    
    # Get video properties
    if frame_width is None or frame_height is None:
        frame_width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Initialize video writer if needed
    if video_writer is None:
        output_video_path = Path(output_dir) / f'{camera_name}_output_video.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'avc1') #mp4v
        video_writer = cv2.VideoWriter(str(output_video_path), fourcc, 30, (frame_width, frame_height))
        if not video_writer.isOpened():
            logger.error("Failed to initialize video writer. Trying MJPG.")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(str(output_video_path.with_suffix('.avi')), fourcc, 30, (frame_width, frame_height))
    
    # Get video metadata
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if fps <= 0 or total_frames <= 0:
        logger.error(f"Invalid video properties: FPS={fps}, Total frames={total_frames}")
        return fn, video_writer, frame_width, frame_height, []
    
    # Calculate frames to extract (every interval_minutes minutes)
    frames_per_interval = int(fps * 60 * interval_minutes)
    
    # List to store extracted frame data
    frame_data_list = []
    start_time = datetime.now()
    frames_processed = 0
    
    try:
        # Extract frames at regular intervals
        for i in range(0, total_frames, frames_per_interval):
            # Set position to the frame number
            video_capture.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = video_capture.read()
            
            if not ret:
                logger.warning(f"Could not read frame {i} from {mp4_file}")
                continue
            
            # Write frame to video
            video_writer.write(frame)
            
            # Calculate approximate timestamp (use "missing" as per requirements)
            # This is a placeholder. We use "missing" to indicate timestamps need to be extracted later
            frame_date = "missing"
            
            # Add to frame data list
            frame_data_list.append({'frame_number': fn, 'frame_date': frame_date})
            fn += 1
            frames_processed += 1
            
            # Report progress less frequently to improve performance
            if frames_processed % 100 == 0:
                logger.debug(f"Fallback extraction progress: {frames_processed} frames processed")
    
    except Exception as e:
        logger.error(f"Error in fallback frame extraction: {e}")
    
    finally:
        video_capture.release()
        
        # Calculate and log performance
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed > 0 and frames_processed > 0:
            logger.info(f"Fallback performance: {frames_processed} frames in {elapsed:.2f}s ({frames_processed/elapsed:.2f} fps)")
    
    return fn, video_writer, frame_width, frame_height, frame_data_list