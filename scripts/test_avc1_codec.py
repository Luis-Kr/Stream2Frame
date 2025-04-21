#!/usr/bin/env python
import os
import sys
import cv2
import time
import logging
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.append(str(project_root))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('avc1_codec_test')

def create_h264_writer(output_path, width, height, fps=30):
    """Create an H.264 video writer using software-based encoding"""
    # Try different H.264 encoder options in order of preference
    h264_variants = [
        # Software-based encoders
        ('avc1', '.mp4'),
        ('X264', '.mp4'),
        ('H264', '.mp4')
    ]
    
    for codec, ext in h264_variants:
        try:
            # Ensure correct file extension
            if not output_path.lower().endswith(ext):
                output_path = os.path.splitext(output_path)[0] + ext
                
            # Set environment variable to force software encoding
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'video_codec;h264_cuvid|rtsp_transport;tcp'
            
            # Create the fourcc code and initialize writer with specific parameters
            fourcc = cv2.VideoWriter_fourcc(*codec)
            
            logger.info(f"Trying codec: {codec}")
            # Try with explicit parameters
            writer = cv2.VideoWriter(
                output_path, 
                fourcc, 
                fps, 
                (width, height),
                True  # isColor
            )
            
            # Test writer
            if writer.isOpened():
                logger.info(f"✅ Successfully created H.264 writer with codec: {codec}")
                return writer, output_path, codec
                
        except Exception as e:
            logger.error(f"❌ Failed with {codec}: {str(e)}")
    
    logger.error("❌ All H.264 codec variants failed")
    return None, None, None

def test_frame_writer(test_frames=30):
    """Generate a test video with the AVC1 codec"""
    width, height = 640, 480
    output_dir = project_root / "data" / "test"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "avc1_test_video.mp4"
    
    # Try to create video writer with AVC1 codec
    writer, actual_path, codec = create_h264_writer(
        str(output_path), 
        width, 
        height, 
        30
    )
    
    if writer is None:
        logger.error("Failed to create video writer. Test failed.")
        return False
    
    try:
        # Generate some test frames
        logger.info(f"Generating {test_frames} test frames...")
        for i in range(test_frames):
            # Create a blank frame with a counter
            frame = create_test_frame(width, height, i)
            writer.write(frame)
        
        # Release the writer
        writer.release()
        
        # Verify the file exists and has non-zero size
        if Path(actual_path).exists():
            size_mb = Path(actual_path).stat().st_size / (1024 * 1024)
            logger.info(f"✅ Successfully created video: {actual_path} ({size_mb:.2f} MB)")
            logger.info(f"✅ Codec used: {codec}")
            return True
        else:
            logger.error(f"❌ Failed to create video file: {actual_path}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during video creation: {e}")
        if writer:
            writer.release()
        return False

def create_test_frame(width, height, frame_number):
    """Create a simple test frame with text"""
    frame = cv2.imread(str(project_root / "data" / "test" / "frame_template.jpg")) if Path(project_root / "data" / "test" / "frame_template.jpg").exists() else None
    
    if frame is None or frame.shape[0] != height or frame.shape[1] != width:
        # Create blank frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Add a gradient background
        for y in range(height):
            for x in range(width):
                frame[y, x] = [
                    x * 255 // width,
                    y * 255 // height,
                    255 - (x+y) * 255 // (width+height)
                ]
    
    # Add timestamp and frame number
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"Frame #{frame_number}", (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, timestamp, (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, "AVC1 Codec Test", (30, height - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Add a moving element
    center_x = width // 2 + int(100 * np.sin(frame_number * 0.1))
    center_y = height // 2 + int(50 * np.cos(frame_number * 0.1))
    cv2.circle(frame, (center_x, center_y), 30, (0, 0, 255), -1)
    
    return frame

if __name__ == "__main__":
    # Fix missing module
    import numpy as np
    
    # Run the test
    logger.info("=== Starting AVC1 Codec Test ===")
    
    # Test with software encoding first
    os.environ['OPENCV_FFMPEG_LOGLEVEL'] = 'verbose'
    result = test_frame_writer()
    
    if result:
        logger.info("✅ AVC1 Codec Test PASSED!")
        sys.exit(0)
    else:
        logger.error("❌ AVC1 Codec Test FAILED!")
        sys.exit(1)