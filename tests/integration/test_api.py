"""
Integration tests for API endpoints
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from flask import Flask

from api.app import create_app
from config.base import AnalysisMode, ModelProvider


class TestAPIEndpoints:
    """Test API endpoint integration"""
    
    @pytest.fixture
    def app(self, test_config):
        """Create test Flask app"""
        app = create_app(test_config)
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def auth_headers(self):
        """Create auth headers"""
        return {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'status' in data
        assert 'version' in data
        assert 'timestamp' in data
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']
    
    def test_api_documentation(self, client):
        """Test API documentation endpoint"""
        response = client.get('/api/docs')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'endpoints' in data
        assert len(data['endpoints']) > 0
        
        # Check endpoint structure
        for endpoint in data['endpoints']:
            assert 'path' in endpoint
            assert 'method' in endpoint
            assert 'description' in endpoint
    
    def test_cost_estimation(self, client, auth_headers):
        """Test cost estimation endpoint"""
        payload = {
            'file_size_kb': 10.0,
            'mode': 'intelligent'
        }
        
        response = client.post(
            '/api/ai/estimate-analysis-cost',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'data' in data
        assert 'cost_estimates' in data['data']
        
        # Check cost estimates
        estimates = data['data']['cost_estimates']
        assert len(estimates) > 0
        
        for estimate in estimates:
            assert 'model' in estimate
            assert 'provider' in estimate
            assert 'total_cost' in estimate
            assert estimate['total_cost'] > 0
    
    def test_file_size_check(self, client, auth_headers):
        """Test file size check endpoint"""
        # Test valid size
        payload = {'file_size': 5 * 1024 * 1024}  # 5MB
        
        response = client.post(
            '/api/ai/check-file-size',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['is_valid'] is True
        assert 'max_size' in data['data']
        
        # Test invalid size
        payload = {'file_size': 100 * 1024 * 1024}  # 100MB
        
        response = client.post(
            '/api/ai/check-file-size',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['is_valid'] is False
    
    @patch('core.engine.AiAnalysisEngine')
    def test_basic_analysis(self, mock_engine_class, client, auth_headers):
        """Test basic analysis endpoint"""
        # Setup mock
        mock_engine = AsyncMock()
        mock_engine_class.return_value = mock_engine
        
        async def mock_analyze(*args, **kwargs):
            yield "Analysis "
            yield "result"
        
        mock_engine.analyze = mock_analyze
        
        # Test request
        payload = {
            'content': 'Test ANR log content',
            'log_type': 'anr',
            'mode': 'quick'
        }
        
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert 'data' in data
        assert 'result' in data['data']
        assert data['data']['result'] == "Analysis result"
    
    def test_sse_analysis(self, client, auth_headers):
        """Test SSE analysis endpoint"""
        with patch('core.engine.AiAnalysisEngine') as mock_engine_class:
            # Setup mock
            mock_engine = AsyncMock()
            mock_engine_class.return_value = mock_engine
            
            async def mock_analyze(*args, **kwargs):
                yield "Chunk 1"
                yield "Chunk 2"
                yield "Chunk 3"
            
            mock_engine.analyze = mock_analyze
            mock_engine.get_status = Mock(return_value={
                'progress': {'progress_percentage': 50}
            })
            
            # Test request
            payload = {
                'content': 'Test content',
                'log_type': 'anr',
                'mode': 'quick'
            }
            
            response = client.post(
                '/api/ai/analyze-with-cancellation',
                headers=auth_headers,
                json=payload
            )
            
            assert response.status_code == 200
            assert response.content_type == 'text/event-stream'
            
            # Read SSE events
            events = []
            for line in response.get_data(as_text=True).split('\n'):
                if line.startswith('data: '):
                    events.append(json.loads(line[6:]))
            
            # Check events
            assert len(events) > 0
            assert any(e['type'] == 'start' for e in events)
            assert any(e['type'] == 'content' for e in events)
            assert any(e['type'] == 'complete' for e in events)
    
    def test_cancel_analysis(self, client, auth_headers):
        """Test analysis cancellation endpoint"""
        with patch('core.cancellation.CancellationManager') as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager.cancel_analysis = AsyncMock(return_value=True)
            mock_manager_class.return_value = mock_manager
            
            analysis_id = 'test-analysis-123'
            
            response = client.post(
                f'/api/ai/cancel/{analysis_id}',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['cancelled'] is True
    
    def test_get_task_status(self, client, auth_headers):
        """Test task status endpoint"""
        with patch('core.engine.AiAnalysisEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.get_task_status = Mock(return_value={
                'id': 'task-123',
                'status': 'completed',
                'created_at': '2024-01-15T10:30:00',
                'mode': 'quick',
                'log_type': 'anr',
                'has_result': True,
                'has_error': False
            })
            mock_engine_class.return_value = mock_engine
            
            response = client.get(
                '/api/ai/task/task-123',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['success'] is True
            assert data['data']['id'] == 'task-123'
            assert data['data']['status'] == 'completed'
    
    def test_error_handling(self, client, auth_headers):
        """Test API error handling"""
        # Test missing required field
        payload = {
            'log_type': 'anr',
            'mode': 'quick'
            # Missing 'content'
        }
        
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'error' in data
        assert 'content' in data['error'].lower()
    
    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting"""
        # Make multiple rapid requests
        responses = []
        
        for _ in range(10):
            response = client.get(
                '/api/health',
                headers=auth_headers
            )
            responses.append(response)
        
        # Should eventually get rate limited
        # (This assumes rate limiting is configured for testing)
        status_codes = [r.status_code for r in responses]
        
        # All should succeed in test environment
        assert all(code in [200, 429] for code in status_codes)
    
    def test_cors_headers(self, client):
        """Test CORS headers"""
        response = client.options('/api/health')
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers


class TestAPIAuthentication:
    """Test API authentication"""
    
    @pytest.fixture
    def secure_app(self, test_config):
        """Create app with authentication enabled"""
        app = create_app(test_config)
        app.config['TESTING'] = True
        app.config['REQUIRE_AUTH'] = True
        app.config['API_TOKEN'] = 'secret-token'
        return app
    
    @pytest.fixture
    def secure_client(self, secure_app):
        """Create secure test client"""
        return secure_app.test_client()
    
    def test_unauthorized_access(self, secure_client):
        """Test access without token"""
        response = secure_client.post(
            '/api/ai/analyze-with-ai',
            json={'content': 'test', 'log_type': 'anr', 'mode': 'quick'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'unauthorized' in data['error'].lower()
    
    def test_invalid_token(self, secure_client):
        """Test access with invalid token"""
        headers = {
            'Authorization': 'Bearer invalid-token',
            'Content-Type': 'application/json'
        }
        
        response = secure_client.post(
            '/api/ai/analyze-with-ai',
            headers=headers,
            json={'content': 'test', 'log_type': 'anr', 'mode': 'quick'}
        )
        
        assert response.status_code == 401
    
    def test_valid_token(self, secure_client):
        """Test access with valid token"""
        headers = {
            'Authorization': 'Bearer secret-token',
            'Content-Type': 'application/json'
        }
        
        with patch('core.engine.AiAnalysisEngine'):
            response = secure_client.get(
                '/api/health',
                headers=headers
            )
            
            assert response.status_code == 200


class TestAPIValidation:
    """Test API input validation"""
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_invalid_log_type(self, client, auth_headers):
        """Test invalid log type"""
        payload = {
            'content': 'test',
            'log_type': 'invalid_type',
            'mode': 'quick'
        }
        
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'log_type' in data['error']
    
    def test_invalid_mode(self, client, auth_headers):
        """Test invalid analysis mode"""
        payload = {
            'content': 'test',
            'log_type': 'anr',
            'mode': 'invalid_mode'
        }
        
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'mode' in data['error']
    
    def test_empty_content(self, client, auth_headers):
        """Test empty content"""
        payload = {
            'content': '',
            'log_type': 'anr',
            'mode': 'quick'
        }
        
        response = client.post(
            '/api/ai/analyze-with-ai',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'content' in data['error'].lower()
    
    def test_invalid_file_size(self, client, auth_headers):
        """Test invalid file size"""
        payload = {
            'file_size': -1000
        }
        
        response = client.post(
            '/api/ai/check-file-size',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'file_size' in data['error']
    
    def test_invalid_cost_estimation_params(self, client, auth_headers):
        """Test invalid cost estimation parameters"""
        # Negative file size
        payload = {
            'file_size_kb': -10,
            'mode': 'quick'
        }
        
        response = client.post(
            '/api/ai/estimate-analysis-cost',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400
        
        # Invalid mode
        payload = {
            'file_size_kb': 10,
            'mode': 'super_intelligent'
        }
        
        response = client.post(
            '/api/ai/estimate-analysis-cost',
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 400


class TestAPIMetrics:
    """Test API metrics and monitoring"""
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get('/metrics')
        
        assert response.status_code == 200
        assert response.content_type == 'text/plain; version=0.0.4; charset=utf-8'
        
        # Check for standard metrics
        metrics_text = response.get_data(as_text=True)
        assert 'http_requests_total' in metrics_text
        assert 'http_request_duration_seconds' in metrics_text
        assert 'python_info' in metrics_text
    
    def test_custom_metrics(self, client, auth_headers):
        """Test custom application metrics"""
        # Make some API calls to generate metrics
        for _ in range(3):
            client.post(
                '/api/ai/estimate-analysis-cost',
                headers=auth_headers,
                json={'file_size_kb': 10, 'mode': 'quick'}
            )
        
        # Check metrics
        response = client.get('/metrics')
        metrics_text = response.get_data(as_text=True)
        
        # Should include custom metrics
        assert 'ai_analysis_requests_total' in metrics_text
        assert 'ai_analysis_duration_seconds' in metrics_text
        assert 'ai_tokens_used_total' in metrics_text