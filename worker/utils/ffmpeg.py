"""
FFmpeg wrapper utility for video processing operations.
Production-grade implementation with comprehensive error handling.
"""
import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple
import structlog

logger = structlog.get_logger()


class FFmpegError(Exception):
    """Base exception for FFmpeg operations."""
    pass


class FFmpegCommandError(FFmpegError):
    """Exception for FFmpeg command building errors."""
    pass


class FFmpegExecutionError(FFmpegError):
    """Exception for FFmpeg execution errors."""
    pass


class FFmpegTimeoutError(FFmpegError):
    """Exception for FFmpeg timeout errors."""
    pass


class HardwareAcceleration:
    """Hardware acceleration detection and management."""
    
    @staticmethod
    async def detect_capabilities() -> Dict[str, bool]:
        """Detect available hardware acceleration capabilities."""
        capabilities = {
            'nvenc': False,
            'qsv': False,
            'vaapi': False,
            'videotoolbox': False,
            'amf': False
        }
        
        try:
            # Check FFmpeg encoders
            result = await asyncio.create_subprocess_exec(
                'ffmpeg', '-encoders',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            encoders_output = stdout.decode()
            
            # Check for hardware encoders
            if 'h264_nvenc' in encoders_output:
                capabilities['nvenc'] = True
            if 'h264_qsv' in encoders_output:
                capabilities['qsv'] = True
            if 'h264_vaapi' in encoders_output:
                capabilities['vaapi'] = True
            if 'h264_videotoolbox' in encoders_output:
                capabilities['videotoolbox'] = True
            if 'h264_amf' in encoders_output:
                capabilities['amf'] = True
                
            logger.info("Hardware acceleration capabilities detected", capabilities=capabilities)
            return capabilities
            
        except Exception as e:
            logger.warning("Failed to detect hardware acceleration", error=str(e))
            return capabilities
    
    @staticmethod
    def get_best_encoder(codec: str, hardware_caps: Dict[str, bool]) -> str:
        """Get the best available encoder for a codec."""
        encoders = {
            'h264': {
                'nvenc': 'h264_nvenc',
                'qsv': 'h264_qsv', 
                'vaapi': 'h264_vaapi',
                'videotoolbox': 'h264_videotoolbox',
                'amf': 'h264_amf',
                'software': 'libx264'
            },
            'h265': {
                'nvenc': 'hevc_nvenc',
                'qsv': 'hevc_qsv',
                'vaapi': 'hevc_vaapi',
                'videotoolbox': 'hevc_videotoolbox',
                'amf': 'hevc_amf',
                'software': 'libx265'
            },
            'av1': {
                'nvenc': 'av1_nvenc',
                'vaapi': 'av1_vaapi',
                'software': 'libaom-av1'
            }
        }
        
        if codec not in encoders:
            return 'copy'  # Default to copy if codec not supported
        
        codec_encoders = encoders[codec]
        
        # Try hardware encoders first
        for hw_type, available in hardware_caps.items():
            if available and hw_type in codec_encoders:
                return codec_encoders[hw_type]
        
        # Fall back to software encoder
        return codec_encoders.get('software', 'copy')


class FFmpegCommandBuilder:
    """Build FFmpeg commands from operations and options with security validation."""
    
    # Security whitelists for command injection prevention
    ALLOWED_CODECS = {
        'video': {'h264', 'h265', 'hevc', 'vp8', 'vp9', 'av1', 'libx264', 'libx265', 'copy'},
        'audio': {'aac', 'mp3', 'opus', 'vorbis', 'ac3', 'libfdk_aac', 'copy'}
    }
    
    ALLOWED_FILTERS = {
        # Video scaling/transform
        'scale', 'crop', 'overlay', 'pad', 'setsar', 'setdar', 'transpose', 'hflip', 'vflip', 'rotate',
        # Color/quality
        'eq', 'hqdn3d', 'unsharp', 'format', 'colorchannelmixer', 'lut3d', 'curves', 'lutyuv', 'lutrgb',
        # Deinterlacing
        'yadif', 'bwdif', 'w3fdif', 'nnedi',
        # Frame rate/timing
        'fps', 'framerate', 'trim', 'atrim', 'setpts', 'asetpts',
        # Concatenation
        'concat', 'split', 'asplit',
        # Audio
        'volume', 'loudnorm', 'dynaudnorm', 'aresample', 'channelmap', 'pan', 'amerge', 'amix', 'atempo',
        # Effects
        'fade', 'afade', 'drawtext', 'subtitles', 'ass', 'boxblur', 'gblur', 'smartblur',
        # Stabilization
        'vidstabdetect', 'vidstabtransform', 'deshake',
        # Thumbnails
        'thumbnail', 'select', 'tile', 'palettegen', 'paletteuse', 'zoompan',
        # HDR/color space
        'zscale', 'tonemap', 'colorspace', 'colormatrix'
    }
    
    ALLOWED_PRESETS = {
        'ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 
        'slow', 'slower', 'veryslow', 'placebo'
    }
    
    ALLOWED_PIXEL_FORMATS = {
        'yuv420p', 'yuv422p', 'yuv444p', 'rgb24', 'rgba', 'bgr24', 'bgra'
    }
    
    # Safe parameter ranges
    SAFE_RANGES = {
        'crf': (0, 51),
        'bitrate_min': 100,    # 100 kbps minimum
        'bitrate_max': 50000,  # 50 Mbps maximum
        'fps_min': 1,
        'fps_max': 120,
        'width_min': 32,
        'width_max': 7680,     # 8K max
        'height_min': 32,
        'height_max': 4320,    # 8K max
        'threads_max': 64
    }
    
    def __init__(self, hardware_caps: Optional[Dict[str, bool]] = None):
        self.hardware_caps = hardware_caps or {}
        logger.info("FFmpegCommandBuilder initialized with security validation")
    
    def build_command(self, input_path: str, output_path: str, 
                     options: Dict[str, Any], operations: List[Dict[str, Any]]) -> List[str]:
        """Build complete FFmpeg command from operations with security validation."""
        # Validate all inputs first
        self._validate_paths(input_path, output_path)
        self._validate_options(options)
        self._validate_operations(operations)
        
        cmd = ['ffmpeg', '-y']  # -y to overwrite output files
        
        # Add hardware acceleration if available
        cmd.extend(self._add_hardware_acceleration())
        
        # Add input (already validated)
        cmd.extend(['-i', input_path])
        
        # Add operations
        video_filters = []
        audio_filters = []

        for operation in operations:
            op_type = operation.get('type')
            # Support both flat and nested params structure
            params = operation.get('params', {})
            if not params:
                params = {k: v for k, v in operation.items() if k != 'type'}

            if op_type == 'transcode':
                cmd.extend(self._handle_transcode(params))
            elif op_type == 'trim':
                cmd.extend(self._handle_trim(params))
            elif op_type == 'watermark':
                video_filters.append(self._handle_watermark(params))
            elif op_type == 'filter':
                vf, af = self._handle_filters(params)
                video_filters.extend(vf)
                audio_filters.extend(af)
            elif op_type == 'stream_map':
                cmd.extend(self._handle_stream_map(params))
            elif op_type in ('streaming', 'stream'):
                cmd.extend(self._handle_streaming(params))
            elif op_type == 'scale':
                video_filters.append(self._handle_scale(params))
            elif op_type == 'crop':
                video_filters.append(self._handle_crop(params))
            elif op_type == 'rotate':
                video_filters.append(self._handle_rotate(params))
            elif op_type == 'flip':
                video_filters.append(self._handle_flip(params))
            elif op_type == 'audio':
                audio_filters.extend(self._handle_audio(params))
            elif op_type == 'subtitle':
                video_filters.append(self._handle_subtitle(params))
        
        # Add video filters
        if video_filters:
            cmd.extend(['-vf', ','.join(video_filters)])
        
        # Add audio filters
        if audio_filters:
            cmd.extend(['-af', ','.join(audio_filters)])
        
        # Add global options
        cmd.extend(self._handle_global_options(options))
        
        # Add output (already validated)
        cmd.append(output_path)
        
        logger.info("Built secure FFmpeg command", command=' '.join(cmd))
        return cmd
    
    def _add_hardware_acceleration(self) -> List[str]:
        """Add hardware acceleration flags."""
        if self.hardware_caps.get('nvenc'):
            return ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
        elif self.hardware_caps.get('qsv'):
            return ['-hwaccel', 'qsv']
        elif self.hardware_caps.get('vaapi'):
            return ['-hwaccel', 'vaapi', '-hwaccel_device', '/dev/dri/renderD128']
        elif self.hardware_caps.get('videotoolbox'):
            return ['-hwaccel', 'videotoolbox']
        return []
    
    def _validate_paths(self, input_path: str, output_path: str):
        """Validate input and output paths for security."""
        import os
        
        # Check for null bytes and dangerous characters
        dangerous_chars = ['\x00', '|', ';', '&', '$', '`', '(', ')', '<', '>', '"', "'"]
        for path in [input_path, output_path]:
            for char in dangerous_chars:
                if char in path:
                    raise FFmpegCommandError(f"Dangerous character detected in path: {char}")
        
        # Validate path length
        if len(input_path) > 4096 or len(output_path) > 4096:
            raise FFmpegCommandError("Path length exceeds maximum allowed")
        
        # Ensure paths are absolute and normalized
        try:
            input_normalized = os.path.normpath(input_path)
            output_normalized = os.path.normpath(output_path)
            
            # Check for directory traversal attempts
            if '..' in input_normalized or '..' in output_normalized:
                raise FFmpegCommandError("Directory traversal attempt detected")
                
        except Exception as e:
            raise FFmpegCommandError(f"Path validation failed: {e}")
    
    def _validate_options(self, options: Dict[str, Any]):
        """Validate global options for security."""
        if not isinstance(options, dict):
            raise FFmpegCommandError("Options must be a dictionary")
        
        # Validate each option
        for key, value in options.items():
            if not isinstance(key, str):
                raise FFmpegCommandError("Option keys must be strings")
            
            # Check for command injection in option values
            if isinstance(value, str):
                self._validate_string_parameter(value, f"option_{key}")
    
    def _validate_operations(self, operations: List[Dict[str, Any]]):
        """Validate operations list for security."""
        if operations is None:
            return  # None is valid, treated as empty
        if not isinstance(operations, list):
            raise FFmpegCommandError("Operations must be a list")
        if not operations:
            return  # Empty list is valid

        allowed_operation_types = {
            'transcode', 'trim', 'watermark', 'filter', 'stream_map', 'streaming', 'stream',
            'scale', 'crop', 'rotate', 'flip', 'audio', 'subtitle', 'concat', 'thumbnail'
        }

        for i, operation in enumerate(operations):
            if not isinstance(operation, dict):
                raise FFmpegCommandError(f"Operation {i} must be a dictionary")

            op_type = operation.get('type')
            if op_type not in allowed_operation_types:
                raise FFmpegCommandError(f"Unknown operation type: {op_type}")

            # Support both flat params and nested 'params' structure
            params = operation.get('params', {})
            if not params:
                # Flat structure: extract params from operation itself
                params = {k: v for k, v in operation.items() if k != 'type'}

            if not isinstance(params, dict):
                raise FFmpegCommandError(f"Operation {i} params must be a dictionary")

            self._validate_operation_params(op_type, params)
    
    def _validate_operation_params(self, op_type: str, params: Dict[str, Any]):
        """Validate operation-specific parameters."""
        if op_type == 'transcode':
            self._validate_transcode_params(params)
        elif op_type == 'trim':
            self._validate_trim_params(params)
        elif op_type == 'filter':
            self._validate_filter_params(params)
        elif op_type == 'watermark':
            self._validate_watermark_params(params)
        elif op_type == 'streaming':
            self._validate_streaming_params(params)
    
    def _validate_transcode_params(self, params: Dict[str, Any]):
        """Validate transcoding parameters."""
        if 'video_codec' in params:
            codec = params['video_codec']
            if codec not in self.ALLOWED_CODECS['video']:
                raise FFmpegCommandError(f"Invalid video codec: {codec}")
        
        if 'audio_codec' in params:
            codec = params['audio_codec']
            if codec not in self.ALLOWED_CODECS['audio']:
                raise FFmpegCommandError(f"Invalid audio codec: {codec}")
        
        if 'preset' in params:
            preset = params['preset']
            if preset not in self.ALLOWED_PRESETS:
                raise FFmpegCommandError(f"Invalid preset: {preset}")
        
        # Validate numeric parameters
        self._validate_numeric_param(params.get('crf'), 'crf', self.SAFE_RANGES['crf'])
        self._validate_bitrate(params.get('video_bitrate'), 'video_bitrate')
        self._validate_bitrate(params.get('audio_bitrate'), 'audio_bitrate')
        self._validate_numeric_param(params.get('fps'), 'fps', (self.SAFE_RANGES['fps_min'], self.SAFE_RANGES['fps_max']))
        self._validate_resolution(params.get('width'), params.get('height'))
    
    def _validate_trim_params(self, params: Dict[str, Any]):
        """Validate trim parameters."""
        for time_param in ['start_time', 'duration', 'end_time']:
            if time_param in params:
                value = params[time_param]
                if isinstance(value, (int, float)):
                    if value < 0 or value > 86400:  # Max 24 hours
                        raise FFmpegCommandError(f"Invalid {time_param}: {value}")
                elif isinstance(value, str):
                    self._validate_time_string(value, time_param)
    
    def _validate_filter_params(self, params: Dict[str, Any]):
        """Validate filter parameters."""
        for key, value in params.items():
            if isinstance(value, str):
                self._validate_string_parameter(value, f"filter_{key}")
            elif isinstance(value, (int, float)):
                if abs(value) > 1000:  # Reasonable limit for filter values
                    raise FFmpegCommandError(f"Filter parameter {key} out of range: {value}")
    
    def _validate_watermark_params(self, params: Dict[str, Any]):
        """Validate watermark parameters."""
        # Validate position values
        for pos_param in ['x', 'y']:
            if pos_param in params:
                value = params[pos_param]
                if isinstance(value, str):
                    self._validate_string_parameter(value, f"watermark_{pos_param}")
        
        # Validate opacity
        if 'opacity' in params:
            opacity = params['opacity']
            if not isinstance(opacity, (int, float)) or opacity < 0 or opacity > 1:
                raise FFmpegCommandError(f"Invalid opacity: {opacity}")
    
    def _validate_streaming_params(self, params: Dict[str, Any]):
        """Validate streaming parameters."""
        # Validate streaming format
        if 'format' in params:
            allowed_formats = {'hls', 'dash'}
            if params['format'] not in allowed_formats:
                raise FFmpegCommandError(f"Invalid streaming format: {params['format']}")
        
        # Validate segment duration
        if 'segment_time' in params:
            segment_time = params['segment_time']
            if not isinstance(segment_time, (int, float)) or segment_time < 1 or segment_time > 60:
                raise FFmpegCommandError(f"Invalid segment time: {segment_time}")
        
        # Validate variants
        if 'variants' in params:
            if not isinstance(params['variants'], list):
                raise FFmpegCommandError("Variants must be a list")
            
            for i, variant in enumerate(params['variants']):
                if not isinstance(variant, dict):
                    raise FFmpegCommandError(f"Variant {i} must be a dictionary")
                
                # Validate resolution
                if 'resolution' in variant:
                    resolution = variant['resolution']
                    if not isinstance(resolution, str) or 'x' not in resolution:
                        raise FFmpegCommandError(f"Invalid resolution format in variant {i}: {resolution}")
                
                # Validate bitrate
                if 'bitrate' in variant:
                    self._validate_bitrate(variant['bitrate'], f"variant_{i}_bitrate")
    
    def _validate_string_parameter(self, value: str, param_name: str):
        """Validate string parameters for command injection."""
        if not isinstance(value, str):
            return
        
        # Check for command injection patterns
        dangerous_patterns = [
            ';', '|', '&', '$', '`', '$(', '${', '<(', '>(', '\n', '\r'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in value:
                raise FFmpegCommandError(f"Dangerous pattern in {param_name}: {pattern}")
        
        # Check length
        if len(value) > 1024:
            raise FFmpegCommandError(f"Parameter {param_name} too long")
    
    def _validate_numeric_param(self, value, param_name: str, valid_range: tuple):
        """Validate numeric parameters."""
        if value is None:
            return
        
        if not isinstance(value, (int, float)):
            raise FFmpegCommandError(f"Parameter {param_name} must be numeric")
        
        min_val, max_val = valid_range
        if value < min_val or value > max_val:
            raise FFmpegCommandError(f"Parameter {param_name} out of range [{min_val}, {max_val}]: {value}")
    
    def _validate_bitrate(self, bitrate, param_name: str):
        """Validate bitrate parameters."""
        if bitrate is None:
            return
        
        if isinstance(bitrate, str):
            # Parse bitrate strings like "1000k", "5M"
            import re
            match = re.match(r'^(\d+)([kKmM]?)$', bitrate)
            if not match:
                raise FFmpegCommandError(f"Invalid bitrate format: {bitrate}")
            
            value, unit = match.groups()
            value = int(value)
            
            if unit.lower() == 'k':
                value *= 1000
            elif unit.lower() == 'm':
                value *= 1000000
            
            if value < self.SAFE_RANGES['bitrate_min'] or value > self.SAFE_RANGES['bitrate_max']:
                raise FFmpegCommandError(f"Bitrate out of safe range: {bitrate}")
        elif isinstance(bitrate, (int, float)):
            if bitrate < self.SAFE_RANGES['bitrate_min'] or bitrate > self.SAFE_RANGES['bitrate_max']:
                raise FFmpegCommandError(f"Bitrate out of safe range: {bitrate}")
    
    def _validate_resolution(self, width, height):
        """Validate resolution parameters."""
        if width is not None:
            self._validate_numeric_param(width, 'width', 
                                       (self.SAFE_RANGES['width_min'], self.SAFE_RANGES['width_max']))
        
        if height is not None:
            self._validate_numeric_param(height, 'height', 
                                       (self.SAFE_RANGES['height_min'], self.SAFE_RANGES['height_max']))
    
    def _validate_time_string(self, time_str: str, param_name: str):
        """Validate time string format."""
        import re
        
        # Allow formats: HH:MM:SS, MM:SS, SS, HH:MM:SS.ms
        time_pattern = r'^(\d{1,2}:)?(\d{1,2}:)?\d{1,2}(\.\d{1,3})?$'
        if not re.match(time_pattern, time_str):
            raise FFmpegCommandError(f"Invalid time format for {param_name}: {time_str}")
    
    def _handle_transcode(self, params: Dict[str, Any]) -> List[str]:
        """Handle video transcoding parameters."""
        cmd_parts = []

        # Hardware acceleration preference
        hw_pref = params.get('hardware_acceleration', 'auto')

        # Video codec
        if 'video_codec' in params:
            codec = params['video_codec']
            if hw_pref == 'none' or codec == 'copy':
                # Use software encoder or copy
                encoder = 'copy' if codec == 'copy' else f"lib{codec}" if codec in ('x264', 'x265') else codec
            else:
                encoder = HardwareAcceleration.get_best_encoder(codec, self.hardware_caps)
            cmd_parts.extend(['-c:v', encoder])

        # Audio codec
        if 'audio_codec' in params:
            cmd_parts.extend(['-c:a', params['audio_codec']])

        # Video bitrate with VBV buffer
        if 'video_bitrate' in params:
            cmd_parts.extend(['-b:v', str(params['video_bitrate'])])
        if 'max_bitrate' in params:
            cmd_parts.extend(['-maxrate', str(params['max_bitrate'])])
        if 'buffer_size' in params:
            cmd_parts.extend(['-bufsize', str(params['buffer_size'])])

        # Audio bitrate
        if 'audio_bitrate' in params:
            cmd_parts.extend(['-b:a', str(params['audio_bitrate'])])

        # Resolution
        if 'width' in params and 'height' in params:
            cmd_parts.extend(['-s', f"{params['width']}x{params['height']}"])

        # Frame rate
        if 'fps' in params:
            cmd_parts.extend(['-r', str(params['fps'])])

        # Quality settings
        if 'crf' in params:
            cmd_parts.extend(['-crf', str(params['crf'])])
        if 'preset' in params:
            cmd_parts.extend(['-preset', params['preset']])

        # Profile (H.264/H.265)
        if 'profile' in params:
            cmd_parts.extend(['-profile:v', params['profile']])

        # Pixel format
        if 'pixel_format' in params:
            cmd_parts.extend(['-pix_fmt', params['pixel_format']])

        # GOP size (keyframe interval)
        if 'gop_size' in params:
            cmd_parts.extend(['-g', str(params['gop_size'])])

        # B-frames
        if 'b_frames' in params:
            cmd_parts.extend(['-bf', str(params['b_frames'])])

        # Audio sample rate
        if 'audio_sample_rate' in params:
            cmd_parts.extend(['-ar', str(params['audio_sample_rate'])])

        # Audio channels
        if 'audio_channels' in params:
            cmd_parts.extend(['-ac', str(params['audio_channels'])])

        # Faststart for web streaming (move moov atom to beginning)
        if params.get('faststart', True):
            cmd_parts.extend(['-movflags', '+faststart'])

        return cmd_parts
    
    def _handle_trim(self, params: Dict[str, Any]) -> List[str]:
        """Handle video trimming."""
        cmd_parts = []

        # Support both 'start'/'start_time' naming conventions
        start = params.get('start') or params.get('start_time')
        if start is not None:
            cmd_parts.extend(['-ss', str(start)])

        # Support both 'duration' and 'end'/'end_time'
        if 'duration' in params:
            cmd_parts.extend(['-t', str(params['duration'])])
        else:
            end = params.get('end') or params.get('end_time')
            if end is not None:
                cmd_parts.extend(['-to', str(end)])

        return cmd_parts
    
    def _handle_watermark(self, params: Dict[str, Any]) -> str:
        """Handle watermark overlay."""
        overlay_filter = "overlay="
        
        # Position
        x = params.get('x', '10')
        y = params.get('y', '10')
        overlay_filter += f"{x}:{y}"
        
        # Opacity
        if 'opacity' in params:
            alpha = params['opacity']
            overlay_filter = f"format=rgba,colorchannelmixer=aa={alpha}[watermark];[0:v][watermark]{overlay_filter}"
        
        return overlay_filter
    
    def _handle_filters(self, params: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Handle video and audio filters. Returns (video_filters, audio_filters)."""
        video_filters = []
        audio_filters = []

        # Color correction (eq filter)
        if 'brightness' in params or 'contrast' in params or 'saturation' in params or 'gamma' in params:
            eq_params = []
            if 'brightness' in params:
                eq_params.append(f"brightness={params['brightness']}")
            if 'contrast' in params:
                eq_params.append(f"contrast={params['contrast']}")
            if 'saturation' in params:
                eq_params.append(f"saturation={params['saturation']}")
            if 'gamma' in params:
                eq_params.append(f"gamma={params['gamma']}")
            video_filters.append(f"eq={':'.join(eq_params)}")

        # Denoising
        if params.get('denoise'):
            strength = params['denoise']
            if isinstance(strength, bool):
                video_filters.append("hqdn3d")
            else:
                video_filters.append(f"hqdn3d={strength}")

        # Sharpening
        if params.get('sharpen'):
            strength = params['sharpen']
            video_filters.append(f"unsharp=5:5:{strength}:5:5:{strength}")

        # Blur
        if params.get('blur'):
            strength = params['blur']
            video_filters.append(f"boxblur={strength}")

        # Deinterlacing
        if params.get('deinterlace'):
            mode = params.get('deinterlace_mode', 'send_frame')
            video_filters.append(f"yadif=mode={mode}")

        # Stabilization
        if params.get('stabilize'):
            video_filters.append("vidstabtransform=smoothing=10")

        # Fade in/out
        if params.get('fade_in'):
            video_filters.append(f"fade=t=in:st=0:d={params['fade_in']}")
            audio_filters.append(f"afade=t=in:st=0:d={params['fade_in']}")
        if params.get('fade_out'):
            # Note: fade_out duration - actual position needs video duration
            video_filters.append(f"fade=t=out:d={params['fade_out']}")
            audio_filters.append(f"afade=t=out:d={params['fade_out']}")

        # Speed adjustment
        if params.get('speed'):
            speed = params['speed']
            video_filters.append(f"setpts={1/speed}*PTS")
            audio_filters.append(f"atempo={speed}")

        # Named filter support (direct filter specification)
        if 'name' in params:
            filter_name = params['name']
            filter_params_dict = params.get('params', {})
            if filter_name in self.ALLOWED_FILTERS:
                if filter_params_dict:
                    filter_str = f"{filter_name}=" + ':'.join(f"{k}={v}" for k, v in filter_params_dict.items())
                else:
                    filter_str = filter_name
                video_filters.append(filter_str)

        return video_filters, audio_filters

    def _handle_scale(self, params: Dict[str, Any]) -> str:
        """Handle scale operation."""
        width = params.get('width', -1)
        height = params.get('height', -1)
        algorithm = params.get('algorithm', 'lanczos')

        # Handle special values
        if width == 'auto' or width == -1:
            width = -1
        if height == 'auto' or height == -1:
            height = -1

        # Build scale filter
        scale_filter = f"scale={width}:{height}"
        if algorithm:
            scale_filter += f":flags={algorithm}"

        return scale_filter

    def _handle_crop(self, params: Dict[str, Any]) -> str:
        """Handle crop operation."""
        width = params.get('width', 'iw')
        height = params.get('height', 'ih')
        x = params.get('x', 0)
        y = params.get('y', 0)

        return f"crop={width}:{height}:{x}:{y}"

    def _handle_rotate(self, params: Dict[str, Any]) -> str:
        """Handle rotation operation."""
        angle = params.get('angle', 0)

        # Handle common angles with transpose
        if angle == 90:
            return "transpose=1"
        elif angle == -90 or angle == 270:
            return "transpose=2"
        elif angle == 180:
            return "transpose=1,transpose=1"
        else:
            # Arbitrary angle rotation
            return f"rotate={angle}*PI/180"

    def _handle_flip(self, params: Dict[str, Any]) -> str:
        """Handle flip operation."""
        direction = params.get('direction', 'horizontal')

        if direction == 'horizontal':
            return "hflip"
        elif direction == 'vertical':
            return "vflip"
        elif direction == 'both':
            return "hflip,vflip"
        else:
            return "hflip"

    def _handle_audio(self, params: Dict[str, Any]) -> List[str]:
        """Handle audio processing operations."""
        filters = []

        # Volume adjustment
        if 'volume' in params:
            volume = params['volume']
            if isinstance(volume, (int, float)):
                filters.append(f"volume={volume}")
            elif isinstance(volume, str):
                filters.append(f"volume={volume}")

        # Audio normalization
        if params.get('normalize'):
            norm_type = params.get('normalize_type', 'loudnorm')
            if norm_type == 'loudnorm':
                # EBU R128 loudness normalization
                i = params.get('target_loudness', -24)
                tp = params.get('true_peak', -2)
                lra = params.get('loudness_range', 7)
                filters.append(f"loudnorm=I={i}:TP={tp}:LRA={lra}")
            elif norm_type == 'dynaudnorm':
                filters.append("dynaudnorm")

        # Sample rate conversion
        if 'sample_rate' in params:
            filters.append(f"aresample={params['sample_rate']}")

        # Channel layout
        if 'channels' in params:
            channels = params['channels']
            if channels == 1:
                filters.append("pan=mono|c0=0.5*c0+0.5*c1")
            elif channels == 2:
                filters.append("pan=stereo|c0=c0|c1=c1")

        return filters

    def _handle_subtitle(self, params: Dict[str, Any]) -> str:
        """Handle subtitle overlay."""
        subtitle_path = params.get('path', '')
        if not subtitle_path:
            return ""

        # Validate subtitle path
        self._validate_paths(subtitle_path, subtitle_path)

        # Determine subtitle type
        if subtitle_path.endswith('.ass') or subtitle_path.endswith('.ssa'):
            return f"ass={subtitle_path}"
        else:
            return f"subtitles={subtitle_path}"
    
    def _handle_stream_map(self, params: Dict[str, Any]) -> List[str]:
        """Handle stream mapping."""
        cmd_parts = []
        
        if 'video_stream' in params:
            cmd_parts.extend(['-map', f"0:v:{params['video_stream']}"])
        if 'audio_stream' in params:
            cmd_parts.extend(['-map', f"0:a:{params['audio_stream']}"])
        
        return cmd_parts
    
    def _handle_streaming(self, params: Dict[str, Any]) -> List[str]:
        """Handle adaptive streaming (HLS/DASH) output."""
        cmd_parts = []
        
        streaming_format = params.get('format', 'hls')
        segment_time = params.get('segment_time', 6)
        
        if streaming_format == 'hls':
            # HLS streaming configuration
            cmd_parts.extend(['-f', 'hls'])
            cmd_parts.extend(['-hls_time', str(segment_time)])
            cmd_parts.extend(['-hls_playlist_type', 'vod'])
            cmd_parts.extend(['-hls_segment_filename', 'segment_%03d.ts'])
            
            # Master playlist for multiple variants
            if 'variants' in params:
                cmd_parts.extend(['-master_pl_name', 'master.m3u8'])
                
                # Add variant streams
                for i, variant in enumerate(params['variants']):
                    if 'resolution' in variant and 'bitrate' in variant:
                        resolution = variant['resolution']
                        bitrate = variant['bitrate']
                        
                        # Add stream map for this variant
                        cmd_parts.extend(['-var_stream_map', f'v:{i},a:{i}'])
                        
        elif streaming_format == 'dash':
            # DASH streaming configuration
            cmd_parts.extend(['-f', 'dash'])
            cmd_parts.extend(['-seg_duration', str(segment_time)])
            cmd_parts.extend(['-use_template', '1'])
            cmd_parts.extend(['-use_timeline', '1'])
            
        return cmd_parts
    
    def _handle_global_options(self, options: Dict[str, Any]) -> List[str]:
        """Handle global FFmpeg options."""
        cmd_parts = []
        
        # Container format
        if 'format' in options:
            cmd_parts.extend(['-f', options['format']])
        
        # Metadata with proper escaping
        if 'metadata' in options:
            for key, value in options['metadata'].items():
                # Validate and escape metadata key and value
                safe_key = self._escape_metadata_field(key)
                safe_value = self._escape_metadata_field(str(value))
                cmd_parts.extend(['-metadata', f"{safe_key}={safe_value}"])
        
        # Threading
        if 'threads' in options:
            cmd_parts.extend(['-threads', str(options['threads'])])
        
        return cmd_parts
    
    def _escape_metadata_field(self, field: str) -> str:
        """Escape metadata field for FFmpeg command safety."""
        if not isinstance(field, str):
            field = str(field)
        
        # Remove or escape dangerous characters
        dangerous_chars = ['|', ';', '&', '$', '`', '<', '>', '"', "'", '\\', '\n', '\r', '\t']
        for char in dangerous_chars:
            field = field.replace(char, '_')
        
        # Limit length
        if len(field) > 255:
            field = field[:255]
        
        return field


class FFmpegProgressParser:
    """Parse FFmpeg progress output."""
    
    def __init__(self, total_duration: Optional[float] = None):
        self.total_duration = total_duration
        self.frame_pattern = re.compile(r'frame=\s*(\d+)')
        self.fps_pattern = re.compile(r'fps=\s*([\d.]+)')
        self.time_pattern = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})')
        self.bitrate_pattern = re.compile(r'bitrate=\s*([\d.]+)kbits/s')
        self.speed_pattern = re.compile(r'speed=\s*([\d.]+)x')
        
    def parse_progress(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse progress information from FFmpeg output line."""
        if not line.strip():
            return None
        
        progress = {}
        
        # Extract frame number
        frame_match = self.frame_pattern.search(line)
        if frame_match:
            progress['frame'] = int(frame_match.group(1))
        
        # Extract FPS
        fps_match = self.fps_pattern.search(line)
        if fps_match:
            progress['fps'] = float(fps_match.group(1))
        
        # Extract time
        time_match = self.time_pattern.search(line)
        if time_match:
            hours = int(time_match.group(1))
            minutes = int(time_match.group(2))
            seconds = int(time_match.group(3))
            centiseconds = int(time_match.group(4))
            total_seconds = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
            progress['time'] = total_seconds
            
            # Calculate percentage if total duration is known and valid
            if self.total_duration and self.total_duration > 0:
                progress['percentage'] = min(100.0, (total_seconds / self.total_duration) * 100)
            elif self.total_duration == 0:
                # Handle zero-duration edge case
                progress['percentage'] = 100.0 if total_seconds > 0 else 0.0
        
        # Extract bitrate
        bitrate_match = self.bitrate_pattern.search(line)
        if bitrate_match:
            progress['bitrate'] = float(bitrate_match.group(1))
        
        # Extract speed
        speed_match = self.speed_pattern.search(line)
        if speed_match:
            progress['speed'] = float(speed_match.group(1))
        
        return progress if progress else None


class FFmpegWrapper:
    """Main FFmpeg wrapper class."""
    
    def __init__(self):
        self.hardware_caps = {}
        self.command_builder = None
    
    async def initialize(self):
        """Initialize hardware capabilities and command builder."""
        self.hardware_caps = await HardwareAcceleration.detect_capabilities()
        self.command_builder = FFmpegCommandBuilder(self.hardware_caps)
        logger.info("FFmpeg wrapper initialized", hardware_caps=self.hardware_caps)
    
    async def probe_file(self, file_path: str) -> Dict[str, Any]:
        """Probe media file for information."""
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise FFmpegError(f"FFprobe failed: {stderr.decode()}")
            
            return json.loads(stdout.decode())
            
        except json.JSONDecodeError as e:
            raise FFmpegError(f"Failed to parse FFprobe output: {e}")
        except Exception as e:
            raise FFmpegError(f"FFprobe execution failed: {e}")
    
    async def execute_command(self, input_path: str, output_path: str,
                            options: Dict[str, Any], operations: List[Dict[str, Any]],
                            progress_callback: Optional[Callable] = None,
                            timeout: Optional[int] = None) -> Dict[str, Any]:
        """Execute FFmpeg command with progress tracking."""
        if not self.command_builder:
            await self.initialize()
        
        # Get input file info for progress calculation
        probe_info = await self.probe_file(input_path)
        duration = None
        if 'format' in probe_info and 'duration' in probe_info['format']:
            duration = float(probe_info['format']['duration'])
        
        # Build command
        cmd = self.command_builder.build_command(input_path, output_path, options, operations)
        
        # Create progress parser
        progress_parser = FFmpegProgressParser(duration)
        
        try:
            # Execute FFmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Monitor progress
            stderr_lines = []
            last_progress = {}
            
            async def read_stderr():
                if process.stderr:
                    async for line in process.stderr:
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        stderr_lines.append(line_str)
                        
                        # Parse progress
                        progress = progress_parser.parse_progress(line_str)
                        if progress and progress_callback:
                            last_progress.update(progress)
                            await progress_callback(progress)
            
            # Start stderr reader
            stderr_task = asyncio.create_task(read_stderr())
            
            # Wait for process completion with timeout
            try:
                if timeout:
                    await asyncio.wait_for(process.wait(), timeout=timeout)
                else:
                    await process.wait()
            except asyncio.TimeoutError:
                process.terminate()
                await process.wait()
                raise FFmpegTimeoutError(f"FFmpeg execution timed out after {timeout} seconds")
            
            # Wait for stderr reader to finish
            await stderr_task
            
            # Check return code
            if process.returncode != 0:
                error_msg = '\n'.join(stderr_lines[-10:])  # Last 10 lines of error
                raise FFmpegExecutionError(f"FFmpeg failed with code {process.returncode}: {error_msg}")
            
            # Get output file info
            output_info = await self.probe_file(output_path)
            
            return {
                'success': True,
                'output_info': output_info,
                'processing_stats': last_progress,
                'command': ' '.join(cmd)
            }
            
        except Exception as e:
            logger.error("FFmpeg execution failed", error=str(e), command=' '.join(cmd))
            raise
    
    async def get_file_duration(self, file_path: str) -> float:
        """Get media file duration in seconds."""
        probe_info = await self.probe_file(file_path)
        if 'format' in probe_info and 'duration' in probe_info['format']:
            return float(probe_info['format']['duration'])
        return 0.0
    
    def validate_operations(self, operations: List[Dict[str, Any]]) -> bool:
        """Validate operations before processing."""
        valid_operations = {
            'transcode', 'trim', 'watermark', 'filter', 'stream_map', 'streaming', 'stream',
            'scale', 'crop', 'rotate', 'flip', 'audio', 'subtitle', 'concat', 'thumbnail'
        }

        if not operations:
            return True  # Empty operations list is valid

        for operation in operations:
            if 'type' not in operation:
                return False
            if operation['type'] not in valid_operations:
                return False

            # Additional validation per operation type
            # Support both flat params and nested 'params' structure
            if operation['type'] == 'trim':
                params = operation.get('params', {})
                if not params:
                    params = {k: v for k, v in operation.items() if k != 'type'}
                if 'start' not in params and 'start_time' not in params and 'duration' not in params and 'end' not in params and 'end_time' not in params:
                    return False

        return True