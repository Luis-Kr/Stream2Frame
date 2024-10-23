from datetime import datetime, timedelta
from pathlib import Path
import warnings
from typing import List, Tuple
import re
import shutil
import os
import logging
import sys
from pprint import pprint
import pandas as pd
import glob

# Hydra and OmegaConf imports
import hydra
from hydra import compose, initialize
from omegaconf import DictConfig

sys.path.append(str(Path(__file__).parent.parent.absolute()))

# Custom imports
import utils as utils
import nvr as nvr

# Ignore warnings
warnings.filterwarnings("ignore")

# get the path of the current file
root_dir = Path(__file__).parent.parent.absolute()


@hydra.main(version_base=None, config_path="../config", config_name="main")
def main(cfg: DictConfig) -> None:
    # Clear the hydra config cache
    utils.clear_hydra_cache()
    
    # Get the list of cameras
    cams = list(cfg.cams.items())
    
    for camera_name, cam_mac_address in cams:
        
        date_yesterday = datetime(cfg.NVR.year, cfg.NVR.month, cfg.NVR.day).strftime("%Y-%m-%d")
        logger = utils.logger_setup("main", root_dir / cfg.NVR.logger_dir / camera_name / f"{date_yesterday}.log")
        
        utils.log_separator(logger)
        logger.info(f"::: Processing camera {camera_name} :::")
        utils.log_separator(logger)
        
        try:
            nvr.convert_single_camera(cfg=cfg, 
                                        logger=logger, 
                                        year=cfg.NVR.year, 
                                        month=cfg.NVR.month, 
                                        day=cfg.NVR.day, 
                                        camera_name=camera_name, 
                                        cam_mac_address=cam_mac_address)
            
        except Exception as e:
            logger.error(f"Error processing camera {camera_name}: {e}")
            continue
        
    for camera_name, _ in cams:
        src_dir = root_dir / cfg.NVR.dst_dir / f"{cfg.NVR.year}-{cfg.NVR.month:02}-{cfg.NVR.day:02}" / camera_name
        dst_dir = root_dir / cfg.NVR.dst_dir_videos / f"{cfg.NVR.year}-{cfg.NVR.month:02}-{cfg.NVR.day:02}" / camera_name
        
        # Check if dst_dir and all parent directories exist
        if not dst_dir.exists():
            dst_dir.mkdir(parents=True)
        
        nvr.rename_mp4_files(logger, src_dir)
        file_pairs = nvr.find_file_pairs(src_dir)
        
        fn=0
        for mp4_file, txt_infofile in file_pairs:
            logger.info(f"::: Processing file {mp4_file}... and {txt_infofile} ... :::")
            
            try:
                frame_numbers, frame_dates = nvr.process_frame_data(txt_infofile)
                fn = nvr.extract_frames_to_video_and_csv(logger=logger, 
                                                            mp4_file=mp4_file,
                                                            fn=fn,
                                                            frame_numbers=frame_numbers, 
                                                            frame_dates=frame_dates,
                                                            camera_name=camera_name,
                                                            output_dir=dst_dir)
            except Exception as e:
                logger.error(f"Error processing file {mp4_file}: {e}")
                continue
            
        # Transfer the data to the server
        try:
            output_video_path = dst_dir / f'{camera_name}_output_video.mp4'
            csv_file_path = dst_dir / f'{camera_name}_frame_data.csv'
            remote_dir = Path(cfg.ssh.pylos.remote_dir_base) / camera_name / f"{cfg.NVR.year}" / f"{cfg.NVR.month}" / f"{cfg.NVR.day}"
            
            nvr.transfer_data_local_remote(logger=logger,
                                            local_dir=str(output_video_path), 
                                            remote_user=cfg.ssh.pylos.remote_user, 
                                            remote_host=cfg.ssh.pylos.remote_host, 
                                            remote_dir=str(remote_dir))
            
            nvr.transfer_data_local_remote(logger=logger,
                                            local_dir=str(csv_file_path), 
                                            remote_user=cfg.ssh.pylos.remote_user, 
                                            remote_host=cfg.ssh.pylos.remote_host, 
                                            remote_dir=str(remote_dir))
            
        except Exception as e:
            logger.error(f"Error transferring data to the server: {e}")
            continue


if __name__ == "__main__":
    main()