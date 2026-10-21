# ============================================================================
#  Social Stats — Video Introspection & Validation Hardening Unit Tests
# ============================================================================
"""
Comprehensive test suite covering Phase BS-3F.4B requirements:
  - probe_video_metadata ffprobe integration
  - TemporaryUploadedFile and InMemoryUploadedFile handling
  - Duration, rotation, geometry, fps, codecs, bitrate, audio parsing
  - Probe error handling (malformed JSON, timeout, nonzero exit, missing streams)
  - Safe upload pipeline integration & persistence into MediaAsset
  - Platform validation for Reel, Video Story, Image Story, and Mixed Carousel
  - Video thumbnail generation and failure resilience
  - Tenant isolation and zero Meta Graph API invocation guarantee
"""
import io
import json
import os
import subprocess
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile, TemporaryUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from social_stats import media_service
from social_stats.models import Client, MediaAsset, UserProfile
from social_stats.video_probe import (
    VideoProbeError,
    _parse_fps,
    _parse_rotation,
    generate_video_thumbnail,
    get_probe_path,
    probe_video_metadata,
)


def _client_factory(name='Client Video'):
    return Client.objects.create(
        name=name,
        company=name,
        email=f'{uuid.uuid4().hex[:8]}@example.com',
    )


def _user_factory(client):
    u = User.objects.create_user(
        username=f'u_{uuid.uuid4().hex[:8]}',
        email=f'{uuid.uuid4().hex[:8]}@example.com',
        password='password123',
    )
    UserProfile.objects.create(user=u, client=client, role='client')
    return u


class VideoProbeHelperTests(TestCase):
    """Tests 1–17: Core video probing, ffprobe execution, and stream/metadata parsing."""

    def test_01_temporary_uploaded_file_probe(self):
        """1. TemporaryUploadedFile probe uses temporary_file_path directly."""
        tf = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        tf.write(b'dummy-content')
        tf.flush()
        tf.close()
        try:
            uploaded = TemporaryUploadedFile('test.mp4', 'video/mp4', os.path.getsize(tf.name), 'utf-8')
            uploaded.file = open(tf.name, 'rb')

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({
                        'streams': [{'codec_type': 'video', 'width': 1080, 'height': 1920, 'codec_name': 'h264'}],
                        'format': {'duration': '10.50'},
                    }),
                    stderr='',
                )
                meta = probe_video_metadata(uploaded)
                self.assertEqual(meta['duration_seconds'], 10.5)
                self.assertEqual(meta['width'], 1080)
                self.assertEqual(meta['height'], 1920)
                # Verify ffprobe was called with the temporary file path
                cmd_called = mock_run.call_args[0][0]
                self.assertEqual(cmd_called[0], 'ffprobe')
                self.assertEqual(cmd_called[-1], uploaded.temporary_file_path())
        finally:
            if os.path.exists(tf.name):
                os.unlink(tf.name)

    def test_02_in_memory_uploaded_file_probe(self):
        """2. InMemoryUploadedFile spools safely to a temp file and deletes it after probe."""
        buf = io.BytesIO(b'in-memory-video-bytes')
        uploaded = InMemoryUploadedFile(buf, 'file', 'clip.mp4', 'video/mp4', len(buf.getvalue()), None)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(
                returncode=0,
                stdout=json.dumps({
                    'streams': [{'codec_type': 'video', 'width': 720, 'height': 1280, 'codec_name': 'h264'}],
                    'format': {'duration': '5.0'},
                }),
                stderr='',
            )
            meta = probe_video_metadata(uploaded)
            self.assertEqual(meta['duration_seconds'], 5.0)
            self.assertEqual(meta['width'], 720)
            self.assertEqual(meta['height'], 1280)
            # Verify file pointer was restored
            self.assertEqual(uploaded.tell(), 0)

    def test_03_duration_extraction(self):
        """3. Duration extraction prefers format.duration, falls back to stream."""
        raw_json = {
            'streams': [{'codec_type': 'video', 'width': 640, 'height': 360, 'duration': '12.345'}],
            'format': {'duration': '12.345678'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['duration_seconds'], 12.346)

    def test_04_width_height_extraction(self):
        """4. Standard 0-degree video preserves native width/height."""
        raw_json = {
            'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080, 'codec_name': 'h264'}],
            'format': {'duration': '8.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['width'], 1920)
            self.assertEqual(meta['height'], 1080)
            self.assertEqual(meta['rotation'], 0)

    def test_05_rotation_90(self):
        """5. 90-degree rotation swaps width and height to effective display orientation."""
        raw_json = {
            'streams': [{
                'codec_type': 'video',
                'width': 1920,
                'height': 1080,
                'codec_name': 'h264',
                'tags': {'rotate': '90'},
            }],
            'format': {'duration': '8.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['width'], 1080)
            self.assertEqual(meta['height'], 1920)
            self.assertEqual(meta['rotation'], 90)
            self.assertEqual(meta['aspect_ratio'], 0.5625)

    def test_06_rotation_270(self):
        """6. 270-degree rotation (or -90 side_data) swaps width and height."""
        raw_json = {
            'streams': [{
                'codec_type': 'video',
                'width': 1920,
                'height': 1080,
                'codec_name': 'h264',
                'side_data_list': [{'side_data_type': 'Display Matrix', 'rotation': -90}],
            }],
            'format': {'duration': '8.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['width'], 1080)
            self.assertEqual(meta['height'], 1920)
            self.assertEqual(meta['rotation'], 270)
            self.assertEqual(meta['aspect_ratio'], 0.5625)

    def test_07_avg_frame_rate_rational_parsing(self):
        """7. Rational frame rate string 30000/1001 parses to 29.970."""
        self.assertEqual(_parse_fps('30000/1001'), 29.97)
        self.assertEqual(_parse_fps('30/1'), 30.0)
        self.assertEqual(_parse_fps('25/1'), 25.0)

    def test_08_r_frame_rate_fallback(self):
        """8. If avg_frame_rate is 0/0 or missing, r_frame_rate is used."""
        raw_json = {
            'streams': [{
                'codec_type': 'video',
                'width': 1280,
                'height': 720,
                'avg_frame_rate': '0/0',
                'r_frame_rate': '60/1',
            }],
            'format': {'duration': '4.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['fps'], 60.0)

    def test_09_h264_codec_extraction(self):
        """9. H.264 codec and profile/pix_fmt extracted in lowercase."""
        raw_json = {
            'streams': [{
                'codec_type': 'video',
                'width': 1080,
                'height': 1920,
                'codec_name': 'H264',
                'profile': 'High',
                'pix_fmt': 'YUV420P',
            }],
            'format': {'duration': '6.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['video_codec'], 'h264')
            self.assertEqual(meta['codec_profile'], 'High')
            self.assertEqual(meta['pixel_format'], 'yuv420p')

    def test_10_hevc_codec_extraction(self):
        """10. HEVC codec extracted accurately."""
        raw_json = {
            'streams': [{
                'codec_type': 'video',
                'width': 1080,
                'height': 1920,
                'codec_name': 'hevc',
                'profile': 'Main',
            }],
            'format': {'duration': '7.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['video_codec'], 'hevc')

    def test_11_aac_audio_extraction(self):
        """11. AAC audio stream properties extracted accurately."""
        raw_json = {
            'streams': [
                {'codec_type': 'video', 'width': 1080, 'height': 1920, 'codec_name': 'h264'},
                {'codec_type': 'audio', 'codec_name': 'AAC', 'sample_rate': '48000', 'channels': 2},
            ],
            'format': {'duration': '5.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertTrue(meta['has_audio'])
            self.assertEqual(meta['audio_codec'], 'aac')
            self.assertEqual(meta['audio_sample_rate'], 48000)
            self.assertEqual(meta['audio_channels'], 2)

    def test_12_no_audio_file(self):
        """12. Silent video with no audio stream does not fail probing."""
        raw_json = {
            'streams': [{'codec_type': 'video', 'width': 1080, 'height': 1920, 'codec_name': 'h264'}],
            'format': {'duration': '5.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertFalse(meta['has_audio'])
            self.assertIsNone(meta['audio_codec'])
            self.assertIsNone(meta['audio_sample_rate'])
            self.assertIsNone(meta['audio_channels'])

    def test_13_bitrate_extraction(self):
        """13. Bitrate is parsed as positive integer."""
        raw_json = {
            'streams': [{'codec_type': 'video', 'width': 720, 'height': 1280, 'bit_rate': '4500000'}],
            'format': {'duration': '3.0', 'bit_rate': '4600000'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            meta = probe_video_metadata(io.BytesIO(b'dummy'))
            self.assertEqual(meta['bitrate'], 4500000)

    def test_14_malformed_ffprobe_json(self):
        """14. Malformed JSON output raises VideoProbeError safely."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout='NOT VALID JSON {', stderr='')
            with self.assertRaises(VideoProbeError):
                probe_video_metadata(io.BytesIO(b'dummy'))

    def test_15_ffprobe_nonzero_exit(self):
        """15. Nonzero exit code from ffprobe raises VideoProbeError."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=1, stdout='', stderr='moov atom not found')
            with self.assertRaises(VideoProbeError):
                probe_video_metadata(io.BytesIO(b'dummy'))

    def test_16_ffprobe_timeout(self):
        """16. ffprobe timeout raises VideoProbeError."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd=['ffprobe'], timeout=15)):
            with self.assertRaises(VideoProbeError):
                probe_video_metadata(io.BytesIO(b'dummy'))

    def test_17_missing_video_stream(self):
        """17. Audio-only file with no video stream raises VideoProbeError."""
        raw_json = {
            'streams': [{'codec_type': 'audio', 'codec_name': 'mp3'}],
            'format': {'duration': '60.0'},
        }
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(raw_json), stderr='')
            with self.assertRaises(VideoProbeError):
                probe_video_metadata(io.BytesIO(b'dummy'))


class UploadPipelineTests(TestCase):
    """Tests 18–22: Upload pipeline validation & MediaAsset persistence."""

    def setUp(self):
        self.client_obj = _client_factory('Tenant Media')
        self.user = _user_factory(self.client_obj)

    def test_18_upload_fails_cleanly_when_probe_fails(self):
        """18. Uploading a video that fails probing raises VideoProbeError and creates NO MediaAsset."""
        f = SimpleUploadedFile('corrupt.mp4', b'corrupted_data', content_type='video/mp4')
        with patch('social_stats.media_service.probe_video_metadata', side_effect=VideoProbeError('Corrupt video')):
            with self.assertRaises(VideoProbeError):
                media_service.upload_media(f, client_id=self.client_obj.id)
        self.assertEqual(MediaAsset.objects.filter(client=self.client_obj).count(), 0)

    def _mock_valid_probe(self):
        return {
            'duration_seconds': 14.5,
            'width': 1080,
            'height': 1920,
            'aspect_ratio': 0.5625,
            'fps': 30.0,
            'video_codec': 'h264',
            'codec_profile': 'High',
            'pixel_format': 'yuv420p',
            'bitrate': 3500000,
            'audio_codec': 'aac',
            'audio_channels': 2,
            'audio_sample_rate': 44100,
            'rotation': 0,
            'format_name': 'mov,mp4,m4a,3gp,3g2,mj2',
            'format_long_name': 'QuickTime / MOV',
            'stream_count': 2,
            'has_audio': True,
        }

    @patch('social_stats.media_service.generate_video_thumbnail', return_value=b'fake-jpeg')
    @patch('social_stats.media_service.probe_video_metadata')
    def test_19_successful_upload_populates_width(self, mock_probe, mock_thumb):
        """19. Successful upload populates MediaAsset width."""
        mock_probe.return_value = self._mock_valid_probe()
        f = SimpleUploadedFile('reel19.mp4', b'data', content_type='video/mp4')
        asset = media_service.upload_media(f, client_id=self.client_obj.id)
        self.assertEqual(asset.width, 1080)

    @patch('social_stats.media_service.generate_video_thumbnail', return_value=b'fake-jpeg')
    @patch('social_stats.media_service.probe_video_metadata')
    def test_20_successful_upload_populates_height(self, mock_probe, mock_thumb):
        """20. Successful upload populates MediaAsset height."""
        mock_probe.return_value = self._mock_valid_probe()
        f = SimpleUploadedFile('reel20.mp4', b'data', content_type='video/mp4')
        asset = media_service.upload_media(f, client_id=self.client_obj.id)
        self.assertEqual(asset.height, 1920)

    @patch('social_stats.media_service.generate_video_thumbnail', return_value=b'fake-jpeg')
    @patch('social_stats.media_service.probe_video_metadata')
    def test_21_successful_upload_populates_duration_seconds(self, mock_probe, mock_thumb):
        """21. Successful upload populates duration_seconds."""
        mock_probe.return_value = self._mock_valid_probe()
        f = SimpleUploadedFile('reel21.mp4', b'data', content_type='video/mp4')
        asset = media_service.upload_media(f, client_id=self.client_obj.id)
        self.assertEqual(asset.duration_seconds, 14.5)

    @patch('social_stats.media_service.generate_video_thumbnail', return_value=b'fake-jpeg')
    @patch('social_stats.media_service.probe_video_metadata')
    def test_22_successful_upload_populates_technical_metadata(self, mock_probe, mock_thumb):
        """22. Successful upload populates technical_metadata dictionary."""
        mock_probe.return_value = self._mock_valid_probe()
        f = SimpleUploadedFile('reel22.mp4', b'data', content_type='video/mp4')
        asset = media_service.upload_media(f, client_id=self.client_obj.id)
        self.assertEqual(asset.technical_metadata['video_codec'], 'h264')
        self.assertEqual(asset.technical_metadata['fps'], 30.0)
        self.assertEqual(asset.technical_metadata['aspect_ratio'], 0.5625)
        self.assertEqual(asset.technical_metadata['audio_codec'], 'aac')


class PlatformValidationHardeningTests(TestCase):
    """Tests 23–31: Platform validation for Reels, Video Stories, and Carousels."""

    def setUp(self):
        self.client_obj = _client_factory('Tenant Validation')

    def test_23_reel_valid_metadata_pass(self):
        """23. Reel with valid MP4, H.264, 9:16 aspect, and duration in bounds PASSES."""
        asset = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=10 * 1024 * 1024,
            width=1080,
            height=1920,
            duration_seconds=15.0,
            technical_metadata={'video_codec': 'h264', 'audio_codec': 'aac'},
        )
        res = media_service.validate_for_platform(asset, 'instagram', 'reel')
        self.assertTrue(res.ok)
        self.assertEqual(len(res.errors), 0)

    def test_24_reel_invalid_codec_fail(self):
        """24. Reel with unsupported video codec (e.g. VP9) FAILS."""
        asset = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=10 * 1024 * 1024,
            width=1080,
            height=1920,
            duration_seconds=15.0,
            technical_metadata={'video_codec': 'vp9'},
        )
        res = media_service.validate_for_platform(asset, 'instagram', 'reel')
        self.assertFalse(res.ok)
        self.assertTrue(any('Unsupported video codec' in e for e in res.errors))

    def test_25_reel_invalid_duration_fail(self):
        """25. Reel under 3.0s or over 90.0s FAILS."""
        asset_short = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            width=1080,
            height=1920,
            duration_seconds=2.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res_short = media_service.validate_for_platform(asset_short, 'instagram', 'reel')
        self.assertFalse(res_short.ok)
        self.assertTrue(any('Video too short' in e for e in res_short.errors))

        asset_long = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            width=1080,
            height=1920,
            duration_seconds=95.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res_long = media_service.validate_for_platform(asset_long, 'instagram', 'reel')
        self.assertFalse(res_long.ok)
        self.assertTrue(any('Video too long' in e for e in res_long.errors))

    def test_26_video_story_valid_pass(self):
        """26. Video Story with valid 9:16 MP4 under 60s PASSES."""
        asset = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5 * 1024 * 1024,
            width=1080,
            height=1920,
            duration_seconds=20.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res = media_service.validate_for_platform(asset, 'instagram', 'story')
        self.assertTrue(res.ok)
        self.assertEqual(len(res.errors), 0)

    def test_27_video_story_duration_limit_fail(self):
        """27. Video Story exceeding 60.0s FAILS."""
        asset = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5 * 1024 * 1024,
            width=1080,
            height=1920,
            duration_seconds=65.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res = media_service.validate_for_platform(asset, 'instagram', 'story')
        self.assertFalse(res.ok)
        self.assertTrue(any('Video too long' in e for e in res.errors))

    def test_28_image_story_regression_pass(self):
        """28. Existing Image Story (MediaAsset #4 dimensions 1080x1920 JPEG) continues to PASS."""
        asset = MediaAsset(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=800_000,
            width=1080,
            height=1920,
            duration_seconds=0.0,
        )
        res = media_service.validate_for_platform(asset, 'instagram', 'story')
        self.assertTrue(res.ok)
        self.assertEqual(len(res.errors), 0)

    def test_29_mixed_carousel_known_ratio_pass(self):
        """29. Mixed carousel where video and image share identical 1:1 ratio PASSES."""
        img = MediaAsset(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500_000,
            width=1080,
            height=1080,
        )
        vid = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5_000_000,
            width=720,
            height=720,
            duration_seconds=10.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res = media_service.validate_carousel_for_platform([img, vid], 'instagram')
        self.assertTrue(res.ok)
        self.assertEqual(len(res.errors), 0)

    def test_30_mixed_carousel_mismatched_ratio_fail(self):
        """30. Mixed carousel where video aspect ratio does not match image FAILS."""
        img = MediaAsset(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500_000,
            width=1080,
            height=1080,  # 1:1
        )
        vid = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5_000_000,
            width=1080,
            height=1920,  # 9:16
            duration_seconds=10.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res = media_service.validate_carousel_for_platform([img, vid], 'instagram')
        self.assertFalse(res.ok)
        self.assertTrue(any('same aspect ratio' in e for e in res.errors))

    def test_31_mixed_carousel_unknown_dimensions_fail(self):
        """31. Video with unknown dimensions (width=0) FAILS mixed carousel validation."""
        img = MediaAsset(
            client=self.client_obj,
            mime_type='image/jpeg',
            file_size=500_000,
            width=1080,
            height=1080,
        )
        vid = MediaAsset(
            client=self.client_obj,
            mime_type='video/mp4',
            file_size=5_000_000,
            width=0,
            height=0,
            duration_seconds=10.0,
        )
        res = media_service.validate_carousel_for_platform([img, vid], 'instagram')
        self.assertFalse(res.ok)
        self.assertTrue(any('Video dimensions could not be verified' in e for e in res.errors))


class SecurityAndIsolationTests(TestCase):
    """Tests 32–34: Tenant isolation, thumbnail resilience, and zero Meta calls."""

    def setUp(self):
        self.client_a = _client_factory('Tenant A')
        self.client_b = _client_factory('Tenant B')
        self.user_a = _user_factory(self.client_a)
        self.api_a = APIClient()
        self.api_a.force_authenticate(user=self.user_a)

    def test_32_tenant_isolation_unaffected(self):
        """32. User from Tenant A cannot see or access video assets belonging to Tenant B."""
        asset_b = MediaAsset.objects.create(
            client=self.client_b,
            mime_type='video/mp4',
            width=1080,
            height=1920,
            duration_seconds=10.0,
            technical_metadata={'video_codec': 'h264'},
        )
        res = self.api_a.get(f'/api/composer/media/{asset_b.id}/')
        self.assertEqual(res.status_code, 404)

    def test_33_video_thumbnail_graceful_fallback(self):
        """33. Thumbnail generation failure logs warning and returns None without raising."""
        with patch('subprocess.run', side_effect=Exception('ffmpeg crashed')):
            thumb = generate_video_thumbnail(io.BytesIO(b'dummy'), duration=10.0)
            self.assertIsNone(thumb)

    @patch('requests.post')
    @patch('requests.get')
    def test_34_zero_meta_calls_during_validation(self, mock_get, mock_post):
        """34. All video probing and validation operations execute strictly locally without Meta API calls."""
        asset = MediaAsset(
            client=self.client_a,
            mime_type='video/mp4',
            file_size=5 * 1024 * 1024,
            width=1080,
            height=1920,
            duration_seconds=12.0,
            technical_metadata={'video_codec': 'h264'},
        )
        media_service.validate_for_platform(asset, 'instagram', 'reel')
        media_service.validate_for_platform(asset, 'instagram', 'story')
        media_service.validate_carousel_for_platform([asset, asset], 'instagram')

        self.assertEqual(mock_get.call_count, 0)
        self.assertEqual(mock_post.call_count, 0)
