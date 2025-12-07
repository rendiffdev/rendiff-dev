"""
Input validation utilities with security enhancements
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse

from api.config import settings
from api.services.storage import StorageService


# Allowed file extensions
ALLOWED_VIDEO_EXTENSIONS = {
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", 
    ".mpeg", ".mpg", ".m4v", ".3gp", ".3g2", ".mxf", ".ts", ".vob"
}

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", 
    ".opus", ".ape", ".alac", ".aiff", ".dts", ".ac3"
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"
}

# Security patterns - updated to support Unicode while blocking dangerous chars
SAFE_FILENAME_REGEX = re.compile(r'^[a-zA-Z0-9\-_\.\u00C0-\u017F\u0400-\u04FF\u4e00-\u9fff\u3040-\u309F\u30A0-\u30FF]+$', re.UNICODE)
CODEC_REGEX = re.compile(r'^[a-zA-Z0-9\-_]+$')

# Security configuration
ALLOWED_BASE_PATHS = {
    '/storage', '/tmp/rendiff', '/app/uploads', '/app/temp'
}

class SecurityError(Exception):
    """Security validation error."""
    pass


def validate_secure_path(path: str, base_paths: set = None) -> str:
    """
    Validate and sanitize file paths to prevent directory traversal.
    
    Args:
        path: The path to validate
        base_paths: Set of allowed base paths
        
    Returns:
        Canonical path if valid
        
    Raises:
        SecurityError: If path is unsafe
    """
    if not path:
        raise SecurityError("Path cannot be empty")
    
    if base_paths is None:
        base_paths = ALLOWED_BASE_PATHS
    
    # Check for null bytes and dangerous characters
    dangerous_chars = ['\x00', '|', ';', '&', '$', '`', '<', '>', '"', "'"]
    for char in dangerous_chars:
        if char in path:
            raise SecurityError(f"Dangerous character detected in path: {char}")
    
    # Validate path length
    if len(path) > 4096:
        raise SecurityError("Path length exceeds maximum allowed")
    
    try:
        # First canonicalize the path to resolve symlinks and traversal attempts
        canonical_path = os.path.realpath(os.path.abspath(path))
        
        # AFTER canonicalization, check for traversal patterns in the result
        if '..' in canonical_path:
            raise SecurityError("Directory traversal detected in canonical path")
        
        # Check if canonical path is within allowed base paths
        is_allowed = False
        for base_path in base_paths:
            base_canonical = os.path.realpath(os.path.abspath(base_path))
            # Ensure proper path comparison with trailing separator
            if canonical_path.startswith(base_canonical + os.sep) or canonical_path == base_canonical:
                is_allowed = True
                break
        
        if not is_allowed:
            raise SecurityError(f"Path outside allowed directories: {canonical_path}")
        
        return canonical_path
        
    except OSError as e:
        raise SecurityError(f"Invalid path: {e}")


async def validate_input_path(
    path: str, 
    storage_service: StorageService
) -> Tuple[str, str]:
    """
    Validate input file path with security checks.
    Returns: (backend_name, validated_path)
    """
    if not path:
        raise ValueError("Input path cannot be empty")
    
    # Parse storage URI
    backend_name, file_path = storage_service.parse_uri(path)
    
    # Check if backend exists
    if backend_name not in storage_service.backends:
        raise ValueError(f"Unknown storage backend: {backend_name}")
    
    # Security validation for local paths
    if backend_name == 'local':
        try:
            file_path = validate_secure_path(file_path)
        except SecurityError as e:
            raise ValueError(f"Security validation failed: {e}")
    
    # Validate filename components
    filename = Path(file_path).name
    if not SAFE_FILENAME_REGEX.match(filename):
        raise ValueError(f"Invalid filename format: {filename}")
    
    # Validate file extension
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in (ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS):
        raise ValueError(f"Unsupported input file type: {file_ext}")
    
    # Check if file exists and validate size - atomic check to prevent TOCTOU
    backend = storage_service.backends[backend_name]
    try:
        # Try to get file info instead of just exists() to make it atomic
        if hasattr(backend, 'get_file_info'):
            file_info = await backend.get_file_info(file_path)
            if not file_info:
                raise ValueError(f"Input file not found: {path}")
            
            # Validate file size (max 10GB for input files)
            file_size = file_info.get('size', 0)
            max_size = 10 * 1024 * 1024 * 1024  # 10GB
            if file_size > max_size:
                raise ValueError(f"Input file too large: {file_size} bytes (max {max_size})")
                
        else:
            # Fallback to exists() if get_file_info not available
            if not await backend.exists(file_path):
                raise ValueError(f"Input file not found: {path}")
            
            # Try to get size if possible
            if hasattr(backend, 'get_size'):
                try:
                    file_size = await backend.get_size(file_path)
                    max_size = 10 * 1024 * 1024 * 1024  # 10GB
                    if file_size > max_size:
                        raise ValueError(f"Input file too large: {file_size} bytes (max {max_size})")
                except Exception:
                    # Size check failed, continue without it
                    pass
                    
    except Exception as e:
        if "too large" in str(e).lower():
            raise ValueError(str(e))
        elif "not found" in str(e).lower() or "does not exist" in str(e).lower():
            raise ValueError(f"Input file not found: {path}")
        raise ValueError(f"Error accessing input file: {e}")
    
    return backend_name, file_path


async def validate_output_path(
    path: str,
    storage_service: StorageService
) -> Tuple[str, str]:
    """
    Validate output file path with security checks.
    Returns: (backend_name, validated_path)
    """
    if not path:
        raise ValueError("Output path cannot be empty")
    
    # Parse storage URI
    backend_name, file_path = storage_service.parse_uri(path)
    
    # Check if backend exists
    if backend_name not in storage_service.backends:
        raise ValueError(f"Unknown storage backend: {backend_name}")
    
    # Security validation for local paths
    if backend_name == 'local':
        try:
            file_path = validate_secure_path(file_path)
        except SecurityError as e:
            raise ValueError(f"Security validation failed: {e}")
    
    # Validate filename components
    filename = Path(file_path).name
    if not SAFE_FILENAME_REGEX.match(filename):
        raise ValueError(f"Invalid filename format: {filename}")
    
    # Check if backend allows output
    storage_config = storage_service.config
    output_backends = storage_config.get("policies", {}).get("output_backends", [])
    if output_backends and backend_name not in output_backends:
        raise ValueError(f"Backend '{backend_name}' not allowed for output")
    
    # Validate file extension for output
    file_ext = Path(file_path).suffix.lower()
    allowed_output_extensions = ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS
    if file_ext and file_ext not in allowed_output_extensions:
        raise ValueError(f"Unsupported output file type: {file_ext}")
    
    # Ensure directory exists
    backend = storage_service.backends[backend_name]
    output_dir = str(Path(file_path).parent)
    await backend.ensure_dir(output_dir)
    
    return backend_name, file_path


def validate_operations(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize operations list with enhanced security checks."""
    if not operations:
        # Empty operations list is valid - will use default transcoding
        return []

    max_ops = settings.MAX_OPERATIONS_PER_JOB
    if len(operations) > max_ops:  # Prevent DOS through too many operations
        raise ValueError(f"Too many operations specified (maximum {max_ops})")
    
    validated = []
    
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValueError(f"Operation {i} must be a dictionary")
        
        if "type" not in op:
            raise ValueError(f"Operation {i} missing 'type' field")
        
        op_type = op["type"]
        
        # Validate operation type
        if not isinstance(op_type, str):
            raise ValueError(f"Operation {i} type must be a string")
        
        # Check for command injection in operation type
        if not re.match(r'^[a-zA-Z_]+$', op_type):
            raise SecurityError(f"Invalid operation type format: {op_type}")
        
        if op_type == "trim":
            validated_op = validate_trim_operation(op)
        elif op_type == "watermark":
            validated_op = validate_watermark_operation(op)
        elif op_type == "filter":
            validated_op = validate_filter_operation(op)
        elif op_type in ("stream", "streaming"):
            validated_op = validate_stream_operation(op)
        elif op_type == "transcode":
            validated_op = validate_transcode_operation(op)
        elif op_type == "scale":
            validated_op = validate_scale_operation(op)
        elif op_type == "crop":
            validated_op = validate_crop_operation(op)
        elif op_type == "rotate":
            validated_op = validate_rotate_operation(op)
        elif op_type == "flip":
            validated_op = validate_flip_operation(op)
        elif op_type == "audio":
            validated_op = validate_audio_operation(op)
        elif op_type == "subtitle":
            validated_op = validate_subtitle_operation(op)
        elif op_type == "concat":
            validated_op = validate_concat_operation(op)
        elif op_type == "thumbnail":
            validated_op = validate_thumbnail_operation(op)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")
        
        validated.append(validated_op)
    
    # Validate codec-container compatibility
    validate_codec_container_compatibility(validated)
    
    # Validate resource limits
    validate_resource_limits(validated)
    
    return validated

def validate_codec_container_compatibility(operations: List[Dict[str, Any]]) -> None:
    """Validate codec and container compatibility."""
    # Define compatible combinations
    CODEC_CONTAINER_COMPATIBILITY = {
        'mp4': {'video': ['h264', 'h265', 'hevc', 'libx264', 'libx265'], 'audio': ['aac', 'mp3']},
        'mkv': {'video': ['h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1'], 'audio': ['aac', 'ac3', 'opus', 'flac']},
        'webm': {'video': ['vp8', 'vp9'], 'audio': ['opus', 'vorbis']},
        'avi': {'video': ['h264', 'libx264'], 'audio': ['mp3', 'ac3']},
        'mov': {'video': ['h264', 'h265', 'libx264'], 'audio': ['aac']},
    }
    
    for op in operations:
        if op.get("type") == "transcode":
            # Check for format specification
            output_format = None
            if "format" in op:
                output_format = op["format"].lower()
            
            if output_format and output_format in CODEC_CONTAINER_COMPATIBILITY:
                compat = CODEC_CONTAINER_COMPATIBILITY[output_format]
                
                # Check video codec compatibility
                video_codec = op.get("video_codec")
                if video_codec and video_codec not in compat['video']:
                    raise ValueError(
                        f"Video codec '{video_codec}' incompatible with container '{output_format}'. "
                        f"Compatible codecs: {', '.join(compat['video'])}"
                    )
                
                # Check audio codec compatibility
                audio_codec = op.get("audio_codec")
                if audio_codec and audio_codec not in compat['audio']:
                    raise ValueError(
                        f"Audio codec '{audio_codec}' incompatible with container '{output_format}'. "
                        f"Compatible codecs: {', '.join(compat['audio'])}"
                    )


def validate_trim_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate trim operation with enhanced security checks."""
    validated = {"type": "trim"}
    
    # Validate start time
    if "start" in op:
        start = op["start"]
        if isinstance(start, (int, float)):
            if start < 0 or start > 86400:  # Max 24 hours
                raise ValueError("Start time out of valid range (0-86400 seconds)")
            validated["start"] = float(start)
        elif isinstance(start, str):
            if len(start) > 20:  # Reasonable length limit
                raise ValueError("Start time string too long")
            validated["start"] = parse_time_string(start)
        else:
            raise ValueError("Invalid start time format - must be number or time string")
    
    # Validate duration or end time
    if "duration" in op:
        duration = op["duration"]
        if isinstance(duration, (int, float)):
            if duration <= 0 or duration > 86400:  # Max 24 hours
                raise ValueError("Duration out of valid range (0-86400 seconds)")
            validated["duration"] = float(duration)
        elif isinstance(duration, str):
            if len(duration) > 20:
                raise ValueError("Duration string too long")
            parsed_duration = parse_time_string(duration)
            if parsed_duration <= 0:
                raise ValueError("Duration must be positive")
            validated["duration"] = parsed_duration
        else:
            raise ValueError("Invalid duration format - must be number or time string")
    elif "end" in op:
        end = op["end"]
        if isinstance(end, (int, float)):
            if end < 0 or end > 86400:  # Max 24 hours
                raise ValueError("End time out of valid range (0-86400 seconds)")
            validated["end"] = float(end)
        elif isinstance(end, str):
            if len(end) > 20:
                raise ValueError("End time string too long")
            validated["end"] = parse_time_string(end)
        else:
            raise ValueError("Invalid end time format - must be number or time string")
    
    # Validate that we have at least duration or end time
    if "start" in validated and "duration" not in validated and "end" not in validated:
        raise ValueError("Trim operation requires either duration or end time when start is specified")
    
    return validated


def validate_watermark_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate watermark operation."""
    if "image" not in op:
        raise ValueError("Watermark operation requires 'image' field")
    
    return {
        "type": "watermark",
        "image": op["image"],
        "position": op.get("position", "bottom-right"),
        "opacity": float(op.get("opacity", 0.8)),
        "scale": float(op.get("scale", 0.1)),
    }


def validate_filter_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate filter operation."""
    allowed_filters = {
        "denoise", "deinterlace", "stabilize", "sharpen", "blur",
        "brightness", "contrast", "saturation", "hue", "eq", "gamma",
        "fade_in", "fade_out", "speed"
    }

    validated = {"type": "filter"}

    # Support named filter or direct params
    if "name" in op:
        filter_name = op["name"]
        if filter_name not in allowed_filters:
            raise ValueError(f"Unknown filter: {filter_name}")
        validated["name"] = filter_name
        validated["params"] = op.get("params", {})
    else:
        # Support direct filter params without name
        for key in op:
            if key != "type" and key in allowed_filters:
                validated[key] = op[key]

    # Validate specific filter parameters
    if "brightness" in validated:
        b = validated["brightness"]
        if not isinstance(b, (int, float)) or b < -1 or b > 1:
            raise ValueError("Brightness must be between -1 and 1")
    if "contrast" in validated:
        c = validated["contrast"]
        if not isinstance(c, (int, float)) or c < 0 or c > 4:
            raise ValueError("Contrast must be between 0 and 4")
    if "saturation" in validated:
        s = validated["saturation"]
        if not isinstance(s, (int, float)) or s < 0 or s > 3:
            raise ValueError("Saturation must be between 0 and 3")
    if "speed" in validated:
        sp = validated["speed"]
        if not isinstance(sp, (int, float)) or sp < 0.25 or sp > 4:
            raise ValueError("Speed must be between 0.25 and 4")

    return validated


def validate_stream_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate streaming operation."""
    stream_format = op.get("format", "hls").lower()
    if stream_format not in ["hls", "dash"]:
        raise ValueError(f"Unknown streaming format: {stream_format}")

    return {
        "type": "stream",
        "format": stream_format,
        "variants": op.get("variants", []),
        "segment_duration": int(op.get("segment_duration", 6)),
    }


def validate_scale_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate scale operation."""
    validated = {"type": "scale"}

    # Width and height
    if "width" in op:
        width = op["width"]
        if width != "auto" and width != -1:
            if not isinstance(width, (int, float)):
                raise ValueError("Width must be a number or 'auto'")
            width = int(width)
            if width < 32 or width > 7680:
                raise ValueError("Width out of valid range (32-7680)")
            if width % 2 != 0:
                raise ValueError("Width must be even number")
        validated["width"] = width

    if "height" in op:
        height = op["height"]
        if height != "auto" and height != -1:
            if not isinstance(height, (int, float)):
                raise ValueError("Height must be a number or 'auto'")
            height = int(height)
            if height < 32 or height > 4320:
                raise ValueError("Height out of valid range (32-4320)")
            if height % 2 != 0:
                raise ValueError("Height must be even number")
        validated["height"] = height

    # Scaling algorithm
    if "algorithm" in op:
        allowed_algorithms = {"lanczos", "bicubic", "bilinear", "neighbor", "area", "fast_bilinear"}
        if op["algorithm"] not in allowed_algorithms:
            raise ValueError(f"Invalid scaling algorithm: {op['algorithm']}")
        validated["algorithm"] = op["algorithm"]

    return validated


def validate_crop_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate crop operation."""
    validated = {"type": "crop"}

    for field in ["width", "height", "x", "y"]:
        if field in op:
            value = op[field]
            if isinstance(value, str):
                # Allow FFmpeg expressions like 'iw', 'ih', 'iw/2'
                if not re.match(r'^[a-zA-Z0-9\+\-\*\/\(\)\.]+$', value):
                    raise ValueError(f"Invalid {field} expression: {value}")
                validated[field] = value
            elif isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"{field} must be non-negative")
                validated[field] = int(value) if field in ["x", "y"] else value
            else:
                raise ValueError(f"{field} must be a number or expression")

    return validated


def validate_rotate_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate rotate operation."""
    validated = {"type": "rotate"}

    if "angle" in op:
        angle = op["angle"]
        if not isinstance(angle, (int, float)):
            raise ValueError("Angle must be a number")
        # Normalize to -360 to 360 range
        angle = angle % 360
        if angle > 180:
            angle -= 360
        validated["angle"] = angle

    return validated


def validate_flip_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate flip operation."""
    validated = {"type": "flip"}

    direction = op.get("direction", "horizontal")
    if direction not in ["horizontal", "vertical", "both"]:
        raise ValueError(f"Invalid flip direction: {direction}")
    validated["direction"] = direction

    return validated


def validate_audio_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate audio processing operation."""
    validated = {"type": "audio"}

    # Volume adjustment
    if "volume" in op:
        volume = op["volume"]
        if isinstance(volume, (int, float)):
            if volume < 0 or volume > 10:
                raise ValueError("Volume must be between 0 and 10")
            validated["volume"] = volume
        elif isinstance(volume, str):
            # Allow dB notation like "-3dB" or "2dB"
            if not re.match(r'^-?\d+(\.\d+)?dB$', volume):
                raise ValueError("Volume string must be in dB format (e.g., '-3dB')")
            validated["volume"] = volume

    # Normalization
    if "normalize" in op:
        validated["normalize"] = bool(op["normalize"])
        if "normalize_type" in op:
            if op["normalize_type"] not in ["loudnorm", "dynaudnorm"]:
                raise ValueError("Invalid normalize type")
            validated["normalize_type"] = op["normalize_type"]

    # Sample rate
    if "sample_rate" in op:
        sr = op["sample_rate"]
        allowed_sample_rates = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000]
        if sr not in allowed_sample_rates:
            raise ValueError(f"Invalid sample rate: {sr}")
        validated["sample_rate"] = sr

    # Channels
    if "channels" in op:
        channels = op["channels"]
        if channels not in [1, 2, 6, 8]:
            raise ValueError("Channels must be 1, 2, 6, or 8")
        validated["channels"] = channels

    return validated


def validate_subtitle_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate subtitle operation."""
    validated = {"type": "subtitle"}

    if "path" not in op:
        raise ValueError("Subtitle operation requires 'path' field")

    path = op["path"]
    # Validate subtitle file extension
    allowed_ext = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
    ext = Path(path).suffix.lower()
    if ext not in allowed_ext:
        raise ValueError(f"Invalid subtitle format: {ext}")

    validated["path"] = path

    # Optional styling
    if "style" in op:
        validated["style"] = op["style"]

    return validated


def validate_thumbnail_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate thumbnail extraction operation."""
    validated = {"type": "thumbnail"}

    # Validate mode
    mode = op.get("mode", "single")
    allowed_modes = {"single", "multiple", "best", "sprite"}
    if mode not in allowed_modes:
        raise ValueError(f"Invalid thumbnail mode: {mode}. Allowed: {', '.join(allowed_modes)}")
    validated["mode"] = mode

    # Validate time (for single mode)
    if "time" in op:
        time = op["time"]
        if isinstance(time, (int, float)):
            if time < 0 or time > 86400:
                raise ValueError("Time out of valid range (0-86400 seconds)")
            validated["time"] = float(time)
        elif isinstance(time, str):
            validated["time"] = parse_time_string(time)
        else:
            raise ValueError("Time must be a number or time string")

    # Validate count
    if "count" in op:
        count = op["count"]
        if not isinstance(count, int) or count < 1 or count > 1000:
            raise ValueError("Count must be an integer between 1 and 1000")
        validated["count"] = count

    # Validate interval
    if "interval" in op:
        interval = op["interval"]
        if not isinstance(interval, (int, float)) or interval <= 0:
            raise ValueError("Interval must be a positive number")
        validated["interval"] = float(interval)

    # Validate dimensions
    if "width" in op:
        width = op["width"]
        if not isinstance(width, int) or width < 16 or width > 7680:
            raise ValueError("Width must be an integer between 16 and 7680")
        validated["width"] = width

    if "height" in op:
        height = op["height"]
        if not isinstance(height, int) or height < 16 or height > 4320:
            raise ValueError("Height must be an integer between 16 and 4320")
        validated["height"] = height

    # Validate quality (JPEG quality, 2-31 where lower is better)
    if "quality" in op:
        quality = op["quality"]
        if not isinstance(quality, int) or quality < 2 or quality > 31:
            raise ValueError("Quality must be an integer between 2 and 31 (lower is better)")
        validated["quality"] = quality

    # Sprite-specific options
    if mode == "sprite":
        if "cols" in op:
            cols = op["cols"]
            if not isinstance(cols, int) or cols < 1 or cols > 20:
                raise ValueError("Cols must be an integer between 1 and 20")
            validated["cols"] = cols

        if "rows" in op:
            rows = op["rows"]
            if not isinstance(rows, int) or rows < 1 or rows > 20:
                raise ValueError("Rows must be an integer between 1 and 20")
            validated["rows"] = rows

        if "tile_width" in op:
            validated["tile_width"] = int(op["tile_width"])
        if "tile_height" in op:
            validated["tile_height"] = int(op["tile_height"])

    # Best mode options
    if mode == "best" and "sample_frames" in op:
        sample = op["sample_frames"]
        if not isinstance(sample, int) or sample < 10 or sample > 1000:
            raise ValueError("Sample frames must be an integer between 10 and 1000")
        validated["sample_frames"] = sample

    return validated


def validate_concat_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate concatenation operation."""
    validated = {"type": "concat"}

    if "inputs" not in op:
        raise ValueError("Concat operation requires 'inputs' field with list of files")

    inputs = op["inputs"]
    if not isinstance(inputs, list) or len(inputs) < 2:
        raise ValueError("Concat requires at least 2 input files")

    if len(inputs) > 100:
        raise ValueError("Too many inputs for concat (max 100)")

    validated["inputs"] = inputs

    # Demuxer mode (safer) vs filter mode (more flexible)
    validated["mode"] = op.get("mode", "demuxer")
    if validated["mode"] not in ["demuxer", "filter"]:
        raise ValueError("Concat mode must be 'demuxer' or 'filter'")

    return validated


def validate_transcode_operation(op: Dict[str, Any]) -> Dict[str, Any]:
    """Validate transcode operation with enhanced security checks."""
    validated = {"type": "transcode"}

    # Allowed video codecs
    ALLOWED_VIDEO_CODECS = {
        'h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1',
        'libx264', 'libx265', 'libvpx', 'libvpx-vp9', 'libaom-av1', 'libsvtav1',
        'prores', 'prores_ks', 'dnxhd', 'dnxhr', 'copy'
    }
    ALLOWED_AUDIO_CODECS = {
        'aac', 'mp3', 'opus', 'vorbis', 'ac3', 'eac3',
        'libfdk_aac', 'libopus', 'libvorbis', 'libmp3lame',
        'flac', 'pcm_s16le', 'pcm_s24le', 'pcm_s32le', 'pcm_f32le', 'copy'
    }
    ALLOWED_PRESETS = {'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow', 'placebo'}
    ALLOWED_PROFILES = {'baseline', 'main', 'high', 'high10', 'high422', 'high444'}
    ALLOWED_PIXEL_FORMATS = {'yuv420p', 'yuv422p', 'yuv444p', 'yuv420p10le', 'yuv422p10le', 'yuv444p10le', 'rgb24', 'rgba', 'nv12', 'p010le'}
    ALLOWED_HW_ACCEL = {'auto', 'none', 'nvenc', 'qsv', 'vaapi', 'videotoolbox', 'amf'}
    ALLOWED_TUNES = {'film', 'animation', 'grain', 'stillimage', 'fastdecode', 'zerolatency', 'psnr', 'ssim'}
    ALLOWED_LEVELS = {'1', '1.1', '1.2', '1.3', '2', '2.1', '2.2', '3', '3.1', '3.2', '4', '4.1', '4.2', '5', '5.1', '5.2', '6', '6.1', '6.2'}

    # Validate video codec
    if "video_codec" in op:
        codec = op["video_codec"]
        if not isinstance(codec, str):
            raise ValueError("Video codec must be a string")
        if codec not in ALLOWED_VIDEO_CODECS:
            raise ValueError(f"Invalid video codec: {codec}")
        validated["video_codec"] = codec

    # Validate audio codec
    if "audio_codec" in op:
        codec = op["audio_codec"]
        if not isinstance(codec, str):
            raise ValueError("Audio codec must be a string")
        if codec not in ALLOWED_AUDIO_CODECS:
            raise ValueError(f"Invalid audio codec: {codec}")
        validated["audio_codec"] = codec

    # Validate preset
    if "preset" in op:
        preset = op["preset"]
        if not isinstance(preset, str):
            raise ValueError("Preset must be a string")
        if preset not in ALLOWED_PRESETS:
            raise ValueError(f"Invalid preset: {preset}")
        validated["preset"] = preset

    # Validate profile (for H.264/H.265)
    if "profile" in op:
        profile = op["profile"]
        if not isinstance(profile, str):
            raise ValueError("Profile must be a string")
        if profile not in ALLOWED_PROFILES:
            raise ValueError(f"Invalid profile: {profile}")
        validated["profile"] = profile

    # Validate pixel format
    if "pixel_format" in op or "pix_fmt" in op:
        pix_fmt = op.get("pixel_format") or op.get("pix_fmt")
        if pix_fmt not in ALLOWED_PIXEL_FORMATS:
            raise ValueError(f"Invalid pixel format: {pix_fmt}")
        validated["pixel_format"] = pix_fmt

    # Validate hardware acceleration
    if "hardware_acceleration" in op or "hw_accel" in op:
        hw = op.get("hardware_acceleration") or op.get("hw_accel")
        if hw not in ALLOWED_HW_ACCEL:
            raise ValueError(f"Invalid hardware acceleration: {hw}")
        validated["hardware_acceleration"] = hw

    # Validate bitrates
    if "video_bitrate" in op:
        validated["video_bitrate"] = validate_bitrate(op["video_bitrate"])
    if "audio_bitrate" in op:
        validated["audio_bitrate"] = validate_bitrate(op["audio_bitrate"])
    if "max_bitrate" in op:
        validated["max_bitrate"] = validate_bitrate(op["max_bitrate"])
    if "buffer_size" in op:
        validated["buffer_size"] = validate_bitrate(op["buffer_size"])

    # Validate resolution
    if "width" in op or "height" in op:
        width = op.get("width")
        height = op.get("height")
        validated_resolution = validate_resolution(width, height)
        if validated_resolution:
            validated.update(validated_resolution)

    # Validate frame rate
    if "fps" in op:
        fps = op["fps"]
        if isinstance(fps, (int, float)):
            if fps <= 0 or fps > 120:  # Reasonable FPS limits
                raise ValueError("FPS out of valid range (1-120)")
            validated["fps"] = float(fps)
        else:
            raise ValueError("FPS must be a number")

    # Validate CRF
    if "crf" in op:
        crf = op["crf"]
        if isinstance(crf, (int, float)):
            if crf < 0 or crf > 51:  # Standard CRF range
                raise ValueError("CRF out of valid range (0-51)")
            validated["crf"] = int(crf)
        else:
            raise ValueError("CRF must be a number")

    # Validate GOP size (keyframe interval)
    if "gop_size" in op or "keyint" in op:
        gop = op.get("gop_size") or op.get("keyint")
        if isinstance(gop, int):
            if gop < 1 or gop > 600:
                raise ValueError("GOP size out of valid range (1-600)")
            validated["gop_size"] = gop
        else:
            raise ValueError("GOP size must be an integer")

    # Validate B-frames
    if "b_frames" in op or "bframes" in op:
        bf = op.get("b_frames") or op.get("bframes")
        if isinstance(bf, int):
            if bf < 0 or bf > 16:
                raise ValueError("B-frames out of valid range (0-16)")
            validated["b_frames"] = bf
        else:
            raise ValueError("B-frames must be an integer")

    # Validate two-pass encoding
    if "two_pass" in op:
        validated["two_pass"] = bool(op["two_pass"])

    # Validate tune parameter (for x264/x265)
    if "tune" in op:
        tune = op["tune"]
        if not isinstance(tune, str):
            raise ValueError("Tune must be a string")
        if tune not in ALLOWED_TUNES:
            raise ValueError(f"Invalid tune: {tune}. Allowed: {', '.join(ALLOWED_TUNES)}")
        validated["tune"] = tune

    # Validate level parameter (for H.264/H.265)
    if "level" in op:
        level = str(op["level"])
        if level not in ALLOWED_LEVELS:
            raise ValueError(f"Invalid level: {level}. Allowed: {', '.join(sorted(ALLOWED_LEVELS, key=lambda x: float(x)))}")
        validated["level"] = level

    # Validate encoder selection (e.g., 'svt' for SVT-AV1)
    if "encoder" in op:
        allowed_encoders = {'default', 'svt', 'aom', 'rav1e'}
        if op["encoder"] not in allowed_encoders:
            raise ValueError(f"Invalid encoder: {op['encoder']}")
        validated["encoder"] = op["encoder"]

    # Validate reference frames
    if "ref_frames" in op or "refs" in op:
        refs = op.get("ref_frames") or op.get("refs")
        if isinstance(refs, int):
            if refs < 1 or refs > 16:
                raise ValueError("Reference frames out of valid range (1-16)")
            validated["ref_frames"] = refs
        else:
            raise ValueError("Reference frames must be an integer")

    # Validate lookahead
    if "rc_lookahead" in op:
        lookahead = op["rc_lookahead"]
        if isinstance(lookahead, int):
            if lookahead < 0 or lookahead > 250:
                raise ValueError("RC lookahead out of valid range (0-250)")
            validated["rc_lookahead"] = lookahead
        else:
            raise ValueError("RC lookahead must be an integer")

    # Validate scene change threshold
    if "sc_threshold" in op:
        sc = op["sc_threshold"]
        if isinstance(sc, int):
            if sc < 0 or sc > 100:
                raise ValueError("Scene change threshold out of valid range (0-100)")
            validated["sc_threshold"] = sc
        else:
            raise ValueError("Scene change threshold must be an integer")

    # Validate audio sample rate
    if "audio_sample_rate" in op:
        sr = op["audio_sample_rate"]
        allowed_rates = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000]
        if sr not in allowed_rates:
            raise ValueError(f"Invalid audio sample rate: {sr}")
        validated["audio_sample_rate"] = sr

    # Validate audio channels
    if "audio_channels" in op:
        channels = op["audio_channels"]
        if channels not in [1, 2, 6, 8]:
            raise ValueError("Audio channels must be 1, 2, 6, or 8")
        validated["audio_channels"] = channels

    return validated


def validate_bitrate(bitrate) -> str:
    """Validate bitrate parameter with security checks."""
    if isinstance(bitrate, str):
        # Validate bitrate format
        if not re.match(r'^\d+[kKmM]?$', bitrate):
            raise ValueError(f"Invalid bitrate format: {bitrate}")
        
        # Parse and validate range with overflow protection
        try:
            if bitrate.lower().endswith('k'):
                base_value = int(bitrate[:-1])
                if base_value > 2147483:  # Prevent overflow
                    raise ValueError("Bitrate value too large")
                value = base_value * 1000
            elif bitrate.lower().endswith('m'):
                base_value = int(bitrate[:-1])
                if base_value > 2147:  # Prevent overflow
                    raise ValueError("Bitrate value too large")
                value = base_value * 1000000
            else:
                value = int(bitrate)
                if value > 2147483647:  # Max int32
                    raise ValueError("Bitrate value too large")
        except ValueError as e:
            if "too large" in str(e):
                raise ValueError("Bitrate value causes overflow")
            raise ValueError(f"Invalid bitrate format: {bitrate}")
        
        # Check reasonable limits (100 kbps to 50 Mbps)
        if value < 100000 or value > 50000000:
            raise ValueError("Bitrate out of reasonable range (100k-50M)")
        
        return bitrate
    elif isinstance(bitrate, (int, float)):
        value = int(bitrate)
        if value < 100000 or value > 50000000:
            raise ValueError("Bitrate out of reasonable range (100000-50000000)")
        return str(value)
    else:
        raise ValueError("Bitrate must be string or number")


def validate_resolution(width, height) -> Dict[str, int]:
    """Validate video resolution parameters with resource limits."""
    result = {}
    
    if width is not None:
        if not isinstance(width, (int, float)):
            raise ValueError("Width must be a number")
        width = int(width)
        if width < 32 or width > 7680:  # Min 32px, max 8K width
            raise ValueError("Width out of valid range (32-7680)")
        if width % 2 != 0:  # Must be even for most codecs
            raise ValueError("Width must be even number")
        result["width"] = width
    
    if height is not None:
        if not isinstance(height, (int, float)):
            raise ValueError("Height must be a number")
        height = int(height)
        if height < 32 or height > 4320:  # Min 32px, max 8K height
            raise ValueError("Height out of valid range (32-4320)")
        if height % 2 != 0:  # Must be even for most codecs
            raise ValueError("Height must be even number")
        result["height"] = height
    
    # Validate total pixel count for resource management
    if "width" in result and "height" in result:
        total_pixels = result["width"] * result["height"]
        max_pixels = 7680 * 4320  # 8K max
        if total_pixels > max_pixels:
            raise ValueError(
                f"Resolution {result['width']}x{result['height']} exceeds maximum pixel count "
                f"({total_pixels} > {max_pixels})"
            )
        
        # Warn about high-resource resolutions
        if total_pixels > 3840 * 2160:  # 4K
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "High resolution requested - may require significant resources",
                width=result["width"],
                height=result["height"],
                total_pixels=total_pixels
            )
    
    return result

def validate_resource_limits(operations: List[Dict[str, Any]]) -> None:
    """Validate resource consumption limits."""
    for op in operations:
        if op.get("type") == "transcode":
            # Check bitrate limits
            video_bitrate = op.get("video_bitrate")
            if video_bitrate:
                if isinstance(video_bitrate, str):
                    # Parse string bitrates like "100M"
                    if video_bitrate.lower().endswith('m'):
                        bitrate_val = int(video_bitrate[:-1])
                        if bitrate_val > 100:  # 100 Mbps max
                            raise ValueError(f"Video bitrate too high: {video_bitrate} (max 100M)")
                elif isinstance(video_bitrate, (int, float)):
                    if video_bitrate > 100000000:  # 100 Mbps in bps
                        raise ValueError(f"Video bitrate too high: {video_bitrate} bps (max 100M)")
            
            # Check framerate limits
            fps = op.get("fps")
            if fps and fps > 120:
                raise ValueError(f"Frame rate too high: {fps} fps (max 120)")
            
            # Check quality settings - allow CRF 0 for lossless encoding
            crf = op.get("crf")
            if crf is not None:
                # CRF 0-4 is typically lossless/near-lossless, requires explicit opt-in
                if crf < 0:
                    raise ValueError(f"CRF cannot be negative: {crf}")
                elif crf < 5:
                    # Allow but log warning for very high quality settings
                    if not op.get("allow_lossless", False):
                        import structlog
                        logger = structlog.get_logger()
                        logger.warning(
                            "Very low CRF requested (high quality/lossless)",
                            crf=crf,
                            tip="Set allow_lossless=true to suppress this warning"
                        )
        
        elif op.get("type") == "stream":
            # Check streaming variants
            variants = op.get("variants", [])
            if len(variants) > 10:
                raise ValueError(f"Too many streaming variants: {len(variants)} (max 10)")
            
            for i, variant in enumerate(variants):
                if "bitrate" in variant:
                    bitrate = variant["bitrate"]
                    if isinstance(bitrate, str) and bitrate.lower().endswith('m'):
                        bitrate_val = int(bitrate[:-1])
                        if bitrate_val > 50:  # 50 Mbps max per variant
                            raise ValueError(f"Variant {i} bitrate too high: {bitrate} (max 50M)")
        
        elif op.get("type") == "filter":
            # Limit complex filters
            filter_name = op.get("name", "")
            complex_filters = ["denoise", "stabilize"]  # CPU intensive
            if filter_name in complex_filters:
                import structlog
                logger = structlog.get_logger()
                logger.warning(
                    "CPU-intensive filter requested",
                    filter=filter_name,
                    operation_type=op.get("type")
                )


def parse_time_string(time_str: str) -> float:
    """Parse time string in format HH:MM:SS.ms to seconds with validation."""
    if not isinstance(time_str, str):
        raise ValueError("Time string must be a string")
    
    # Security check for time string format
    if not re.match(r'^(\d{1,2}:)?(\d{1,2}:)?\d{1,2}(\.\d{1,3})?$', time_str):
        raise ValueError(f"Invalid time format: {time_str}")
    
    parts = time_str.split(":")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            seconds = float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            seconds = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError(f"Invalid time format: {time_str}")
        
        # Validate reasonable time bounds
        if seconds < 0 or seconds > 86400:  # 24 hours max
            raise ValueError(f"Time out of reasonable range: {seconds}")
        
        return seconds
    except ValueError as e:
        raise ValueError(f"Invalid time format: {time_str} - {e}")