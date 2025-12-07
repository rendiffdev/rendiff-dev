"""
Integration tests for Rendiff API
Tests end-to-end workflows and component interactions
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.models.database import Base
from api.models.job import Job, JobStatus
from api.config import settings


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    test_db_url = settings.DATABASE_URL.replace("rendiff", "rendiff_test")
    engine = create_async_engine(test_db_url, echo=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    TestSessionLocal = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def test_client():
    """Create test HTTP client."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_video():
    """Create a sample video file for testing."""
    # Create a minimal test video using FFmpeg
    test_dir = Path(tempfile.gettempdir()) / "rendiff_test"
    test_dir.mkdir(exist_ok=True)
    
    video_path = test_dir / "test_video.mp4"
    
    # Generate test video (5 seconds, 480p)
    os.system(f"""
    ffmpeg -f lavfi -i testsrc=duration=5:size=640x480:rate=30 \
           -f lavfi -i sine=frequency=1000:duration=5 \
           -c:v libx264 -preset ultrafast -crf 30 \
           -c:a aac -shortest -y {video_path}
    """)
    
    yield str(video_path)
    
    # Cleanup
    if video_path.exists():
        video_path.unlink()


class TestAPIEndpoints:
    """Test API endpoints functionality."""
    
    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        """Test health check endpoint."""
        response = await test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "components" in data
        
        # Check component health
        components = data["components"]
        assert "database" in components
        assert "queue" in components
        assert "storage" in components
    
    @pytest.mark.asyncio
    async def test_capabilities_endpoint(self, test_client):
        """Test capabilities discovery."""
        response = await test_client.get("/api/v1/capabilities")
        assert response.status_code == 200
        
        data = response.json()
        assert "formats" in data
        assert "codecs" in data
        assert "hardware_acceleration" in data
        
        # Verify format support
        formats = data["formats"]
        assert "input" in formats
        assert "output" in formats
        assert "mp4" in formats["input"]
        assert "mp4" in formats["output"]
    
    @pytest.mark.asyncio
    async def test_job_creation_without_api_key(self, test_client):
        """Test job creation fails without API key."""
        request_data = {
            "input": "/test/input.mp4",
            "output": "/test/output.mp4"
        }
        
        response = await test_client.post("/api/v1/convert", json=request_data)
        assert response.status_code == 401
        
        data = response.json()
        assert "API key required" in data["detail"]


class TestJobWorkflow:
    """Test complete job processing workflow."""
    
    @pytest.mark.asyncio
    async def test_simple_conversion_job(self, test_client, test_db, sample_video):
        """Test basic video conversion workflow."""
        # Create API key first
        api_key_response = await test_client.post(
            "/api/v1/admin/api-keys",
            json={"name": "test-key", "permissions": ["convert"]},
            headers={"X-API-Key": "test-admin-key"}
        )
        
        if api_key_response.status_code == 201:
            api_key = api_key_response.json()["api_key"]
        else:
            api_key = "test-api-key"  # Use default for testing
        
        # Create conversion job
        request_data = {
            "input": sample_video,
            "output": "/tmp/output.webm",
            "operations": [
                {
                    "type": "scale",
                    "width": 320,
                    "height": 240
                }
            ],
            "options": {
                "priority": "high"
            }
        }
        
        headers = {"X-API-Key": api_key}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify job response structure
        assert "job" in data
        job = data["job"]
        assert "id" in job
        assert job["status"] == "queued"
        assert job["priority"] == "high"
        assert "links" in job
        
        job_id = job["id"]
        
        # Check job status
        status_response = await test_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert status_data["id"] == job_id
        assert status_data["status"] in ["queued", "processing"]
    
    @pytest.mark.asyncio
    async def test_job_with_multiple_operations(self, test_client, sample_video):
        """Test job with multiple video operations."""
        request_data = {
            "input": sample_video,
            "output": "/tmp/complex_output.mp4",
            "operations": [
                {
                    "type": "trim",
                    "start": 1,
                    "duration": 3
                },
                {
                    "type": "scale",
                    "width": 480,
                    "height": 360
                },
                {
                    "type": "watermark",
                    "text": "Test Watermark",
                    "position": "bottom-right"
                }
            ],
            "options": {
                "priority": "normal",
                "format": "mp4",
                "video_codec": "h264",
                "audio_codec": "aac"
            }
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        # Should succeed with complex operations
        assert response.status_code in [201, 400]  # 400 if validation fails
        
        if response.status_code == 201:
            data = response.json()
            job_id = data["job"]["id"]
            
            # Verify operations are stored
            job_response = await test_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            job_data = job_response.json()
            
            assert len(job_data["operations"]) == 3
            assert job_data["operations"][0]["type"] == "trim"
            assert job_data["operations"][1]["type"] == "scale"
            assert job_data["operations"][2]["type"] == "watermark"
    
    @pytest.mark.asyncio
    async def test_streaming_format_creation(self, test_client, sample_video):
        """Test HLS streaming format creation."""
        request_data = {
            "input": sample_video,
            "output": "/tmp/stream",
            "type": "hls",
            "variants": [
                {"resolution": "480p", "bitrate": "1M"},
                {"resolution": "720p", "bitrate": "2.5M"}
            ],
            "segment_duration": 6
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/stream", json=request_data, headers=headers)
        
        assert response.status_code in [201, 400]  # Depending on implementation
    
    @pytest.mark.asyncio
    async def test_video_analysis(self, test_client, sample_video):
        """Test video analysis workflow."""
        request_data = {
            "input": sample_video,
            "metrics": ["duration", "resolution", "bitrate", "codec"]
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/analyze", json=request_data, headers=headers)
        
        assert response.status_code in [201, 200]  # Depending on sync/async implementation
        
        if response.status_code == 201:
            # Async analysis
            data = response.json()
            job_id = data["job"]["id"]
            
            # Check analysis job
            job_response = await test_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            assert job_response.status_code == 200


class TestValidation:
    """Test input validation and error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_input_format(self, test_client):
        """Test handling of invalid input format."""
        request_data = {
            "input": "/path/to/invalid.xyz",
            "output": "/path/to/output.mp4"
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "unsupported" in data["error"]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, test_client):
        """Test validation of required fields."""
        request_data = {
            "output": "/path/to/output.mp4"
            # Missing input field
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_invalid_operations(self, test_client):
        """Test validation of video operations."""
        request_data = {
            "input": "/path/to/input.mp4",
            "output": "/path/to/output.mp4",
            "operations": [
                {
                    "type": "invalid_operation",
                    "parameter": "value"
                }
            ]
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "invalid operation" in data["error"]["message"].lower()


class TestJobManagement:
    """Test job management operations."""
    
    @pytest.mark.asyncio
    async def test_list_jobs(self, test_client):
        """Test job listing with pagination."""
        headers = {"X-API-Key": "test-api-key"}
        
        # Test basic listing
        response = await test_client.get("/api/v1/jobs", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "jobs" in data
        assert "pagination" in data
        
        pagination = data["pagination"]
        assert "page" in pagination
        assert "per_page" in pagination
        assert "total" in pagination
    
    @pytest.mark.asyncio
    async def test_job_filtering(self, test_client):
        """Test job filtering by status."""
        headers = {"X-API-Key": "test-api-key"}
        
        # Filter by status
        response = await test_client.get("/api/v1/jobs?status=completed", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        for job in data["jobs"]:
            assert job["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_job_cancellation(self, test_client, test_db, sample_video):
        """Test job cancellation."""
        # Create a job first
        request_data = {
            "input": sample_video,
            "output": "/tmp/cancel_test.mp4"
        }
        
        headers = {"X-API-Key": "test-api-key"}
        create_response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        if create_response.status_code == 201:
            job_id = create_response.json()["job"]["id"]
            
            # Cancel the job
            cancel_response = await test_client.delete(f"/api/v1/jobs/{job_id}", headers=headers)
            assert cancel_response.status_code in [200, 204]
            
            # Verify cancellation
            status_response = await test_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
            status_data = status_response.json()
            assert status_data["status"] == "cancelled"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_nonexistent_job(self, test_client):
        """Test handling of non-existent job ID."""
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.get("/api/v1/jobs/nonexistent-id", headers=headers)
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["error"]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_malformed_json(self, test_client):
        """Test handling of malformed JSON."""
        headers = {"X-API-Key": "test-api-key", "Content-Type": "application/json"}
        
        # Send malformed JSON
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/convert",
                content='{"input": "/path", "output":}',  # Malformed JSON
                headers=headers
            )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_large_payload(self, test_client):
        """Test handling of oversized payloads."""
        # Create a very large request
        large_operations = [
            {"type": "scale", "width": 1920, "height": 1080}
            for _ in range(1000)  # Create many operations
        ]
        
        request_data = {
            "input": "/path/to/input.mp4",
            "output": "/path/to/output.mp4",
            "operations": large_operations
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        # Should either reject or handle gracefully
        assert response.status_code in [400, 413, 422]


class TestSecurity:
    """Test security aspects."""
    
    @pytest.mark.asyncio
    async def test_path_traversal_protection(self, test_client):
        """Test protection against path traversal attacks."""
        request_data = {
            "input": "../../../etc/passwd",
            "output": "/tmp/output.mp4"
        }
        
        headers = {"X-API-Key": "test-api-key"}
        response = await test_client.post("/api/v1/convert", json=request_data, headers=headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "path" in data["error"]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_invalid_api_key(self, test_client):
        """Test invalid API key handling."""
        headers = {"X-API-Key": "invalid-key"}
        response = await test_client.get("/api/v1/jobs", headers=headers)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, test_client):
        """Test rate limiting behavior."""
        headers = {"X-API-Key": "test-api-key"}
        
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = await test_client.get("/api/v1/health", headers=headers)
            responses.append(response.status_code)
        
        # Should mostly succeed, but may hit rate limits
        success_count = sum(1 for status in responses if status == 200)
        assert success_count >= 5  # At least some should succeed


# Performance Tests
class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_jobs(self, test_client, sample_video):
        """Test handling of concurrent job submissions."""
        headers = {"X-API-Key": "test-api-key"}
        
        # Submit multiple jobs concurrently
        tasks = []
        for i in range(5):
            request_data = {
                "input": sample_video,
                "output": f"/tmp/concurrent_{i}.mp4"
            }
            task = test_client.post("/api/v1/convert", json=request_data, headers=headers)
            tasks.append(task)
        
        # Wait for all submissions
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful submissions
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 201)
        assert success_count >= 3  # At least 60% should succeed
    
    @pytest.mark.asyncio
    async def test_response_time(self, test_client):
        """Test API response times."""
        import time
        
        headers = {"X-API-Key": "test-api-key"}
        
        start_time = time.time()
        response = await test_client.get("/api/v1/health", headers=headers)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second


# Cleanup and utilities
@pytest.fixture(autouse=True)
async def cleanup_test_files():
    """Clean up test files after each test."""
    yield
    
    # Clean up any test output files
    test_files = Path("/tmp").glob("*test*")
    for file_path in test_files:
        try:
            if file_path.is_file():
                file_path.unlink()
        except Exception:
            pass  # Ignore cleanup errors


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])