"""
Unit tests for prompt management
"""
import pytest
import tempfile
from pathlib import Path
import yaml

from prompts.manager import PromptManager
from prompts.templates import PromptTemplate, PromptVariable
from config.base import AnalysisMode


class TestPromptTemplate:
    """Test prompt template functionality"""
    
    def test_simple_template(self):
        """Test simple template without variables"""
        template = PromptTemplate(
            name="simple",
            content="This is a simple prompt.",
            description="A simple test prompt"
        )
        
        assert template.name == "simple"
        assert template.content == "This is a simple prompt."
        assert template.description == "A simple test prompt"
        assert len(template.variables) == 0
    
    def test_template_with_variables(self):
        """Test template with variables"""
        variables = [
            PromptVariable(
                name="user_name",
                description="User's name",
                required=True
            ),
            PromptVariable(
                name="task",
                description="Task to perform",
                required=True,
                default="analyze"
            )
        ]
        
        template = PromptTemplate(
            name="with_vars",
            content="Hello {user_name}, please {task} this.",
            variables=variables
        )
        
        assert len(template.variables) == 2
        assert template.variables[0].name == "user_name"
        assert template.variables[1].default == "analyze"
    
    def test_render_template(self):
        """Test template rendering"""
        template = PromptTemplate(
            name="greeting",
            content="Hello {name}, welcome to {place}!",
            variables=[
                PromptVariable(name="name", required=True),
                PromptVariable(name="place", required=True)
            ]
        )
        
        # Render with all variables
        rendered = template.render(name="Alice", place="Wonderland")
        assert rendered == "Hello Alice, welcome to Wonderland!"
        
        # Test with missing required variable
        with pytest.raises(ValueError, match="Missing required variable"):
            template.render(name="Alice")
    
    def test_render_with_defaults(self):
        """Test template rendering with default values"""
        template = PromptTemplate(
            name="task",
            content="Perform {action} on {target}",
            variables=[
                PromptVariable(name="action", required=True, default="analyze"),
                PromptVariable(name="target", required=True)
            ]
        )
        
        # Use default for action
        rendered = template.render(target="data")
        assert rendered == "Perform analyze on data"
        
        # Override default
        rendered = template.render(action="process", target="data")
        assert rendered == "Perform process on data"
    
    def test_validate_template(self):
        """Test template validation"""
        # Valid template
        template = PromptTemplate(
            name="valid",
            content="Hello {name}",
            variables=[PromptVariable(name="name", required=True)]
        )
        
        is_valid, errors = template.validate()
        assert is_valid is True
        assert len(errors) == 0
        
        # Template with undefined variable
        template = PromptTemplate(
            name="invalid",
            content="Hello {name} and {undefined}",
            variables=[PromptVariable(name="name", required=True)]
        )
        
        is_valid, errors = template.validate()
        assert is_valid is False
        assert any("undefined" in error for error in errors)
    
    def test_extract_variables(self):
        """Test variable extraction from content"""
        template = PromptTemplate(
            name="extract",
            content="User {user_id} performed {action} at {timestamp}"
        )
        
        variables = template.extract_variables()
        assert len(variables) == 3
        assert "user_id" in variables
        assert "action" in variables
        assert "timestamp" in variables
    
    def test_template_metadata(self):
        """Test template metadata"""
        template = PromptTemplate(
            name="meta",
            content="Test content",
            description="Test template",
            version="1.0.0",
            author="Test Author",
            tags=["test", "unit-test"]
        )
        
        assert template.version == "1.0.0"
        assert template.author == "Test Author"
        assert "test" in template.tags
        assert "unit-test" in template.tags


class TestPromptManager:
    """Test prompt manager functionality"""
    
    @pytest.fixture
    def temp_prompt_dir(self):
        """Create temporary prompt directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_dir = Path(tmpdir) / "prompts"
            prompt_dir.mkdir()
            yield prompt_dir
    
    @pytest.fixture
    def manager(self, temp_prompt_dir):
        """Create prompt manager instance"""
        return PromptManager(prompt_dir=str(temp_prompt_dir))
    
    def test_load_from_yaml(self, manager, temp_prompt_dir):
        """Test loading prompts from YAML files"""
        # Create test prompt file
        prompt_data = {
            'name': 'test_anr_prompt',
            'description': 'Test ANR analysis prompt',
            'version': '1.0.0',
            'content': '''Analyze this ANR log:
{log_content}

Focus on: {focus_areas}''',
            'variables': [
                {
                    'name': 'log_content',
                    'description': 'ANR log content',
                    'required': True
                },
                {
                    'name': 'focus_areas',
                    'description': 'Areas to focus on',
                    'required': False,
                    'default': 'performance issues'
                }
            ]
        }
        
        prompt_file = temp_prompt_dir / 'test_anr.yaml'
        with open(prompt_file, 'w', encoding='utf-8') as f:
            yaml.dump(prompt_data, f)
        
        # Load prompts
        manager.load_prompts()
        
        # Check loaded prompt
        assert 'test_anr_prompt' in manager.templates
        template = manager.get_template('test_anr_prompt')
        assert template is not None
        assert template.version == '1.0.0'
        assert len(template.variables) == 2
    
    def test_get_prompt_for_mode(self, manager, temp_prompt_dir):
        """Test getting prompts for specific modes"""
        # Create mode-specific prompts
        quick_prompt = {
            'name': 'anr_quick',
            'content': 'Quick analysis of {log_content}',
            'mode': 'quick',
            'type': 'anr'
        }
        
        intelligent_prompt = {
            'name': 'anr_intelligent',
            'content': 'Detailed analysis of {log_content}',
            'mode': 'intelligent',
            'type': 'anr'
        }
        
        # Save prompts
        with open(temp_prompt_dir / 'anr_quick.yaml', 'w') as f:
            yaml.dump(quick_prompt, f)
        
        with open(temp_prompt_dir / 'anr_intelligent.yaml', 'w') as f:
            yaml.dump(intelligent_prompt, f)
        
        manager.load_prompts()
        
        # Get prompts by mode
        quick_template = manager.get_prompt_for_mode('anr', AnalysisMode.QUICK)
        assert quick_template is not None
        assert 'Quick analysis' in quick_template.content
        
        intelligent_template = manager.get_prompt_for_mode('anr', AnalysisMode.INTELLIGENT)
        assert intelligent_template is not None
        assert 'Detailed analysis' in intelligent_template.content
    
    def test_render_prompt(self, manager):
        """Test prompt rendering through manager"""
        # Add template manually
        template = PromptTemplate(
            name="test_render",
            content="Analyze {type} for {user}",
            variables=[
                PromptVariable(name="type", required=True),
                PromptVariable(name="user", required=True)
            ]
        )
        
        manager.templates["test_render"] = template
        
        # Render through manager
        rendered = manager.render_prompt(
            "test_render",
            type="ANR",
            user="developer"
        )
        
        assert rendered == "Analyze ANR for developer"
    
    def test_prompt_caching(self, manager):
        """Test prompt caching mechanism"""
        # Create template
        template = PromptTemplate(
            name="cached",
            content="Cached content: {value}"
        )
        
        manager.templates["cached"] = template
        
        # First render
        result1 = manager.render_prompt("cached", value="test1")
        
        # Second render with same params (should use cache)
        result2 = manager.render_prompt("cached", value="test1")
        
        assert result1 == result2
        
        # Different params (should not use cache)
        result3 = manager.render_prompt("cached", value="test2")
        
        assert result3 != result1
    
    def test_list_prompts(self, manager, temp_prompt_dir):
        """Test listing available prompts"""
        # Create multiple prompts
        prompts = [
            {'name': 'anr_quick', 'type': 'anr', 'mode': 'quick'},
            {'name': 'anr_intelligent', 'type': 'anr', 'mode': 'intelligent'},
            {'name': 'tombstone_quick', 'type': 'tombstone', 'mode': 'quick'}
        ]
        
        for prompt in prompts:
            with open(temp_prompt_dir / f"{prompt['name']}.yaml", 'w') as f:
                yaml.dump(prompt, f)
        
        manager.load_prompts()
        
        # List all prompts
        all_prompts = manager.list_prompts()
        assert len(all_prompts) == 3
        
        # List by type
        anr_prompts = manager.list_prompts(type_filter='anr')
        assert len(anr_prompts) == 2
        
        tombstone_prompts = manager.list_prompts(type_filter='tombstone')
        assert len(tombstone_prompts) == 1
        
        # List by mode
        quick_prompts = manager.list_prompts(mode_filter='quick')
        assert len(quick_prompts) == 2
    
    def test_prompt_validation(self, manager):
        """Test prompt validation through manager"""
        # Valid prompt
        valid_template = PromptTemplate(
            name="valid",
            content="Hello {name}",
            variables=[PromptVariable(name="name", required=True)]
        )
        
        manager.templates["valid"] = valid_template
        
        is_valid = manager.validate_prompt("valid")
        assert is_valid is True
        
        # Invalid prompt
        invalid_template = PromptTemplate(
            name="invalid",
            content="Hello {name} and {missing}",
            variables=[PromptVariable(name="name", required=True)]
        )
        
        manager.templates["invalid"] = invalid_template
        
        is_valid = manager.validate_prompt("invalid")
        assert is_valid is False
    
    def test_export_prompts(self, manager, temp_dir):
        """Test exporting prompts"""
        # Add templates
        templates = [
            PromptTemplate(
                name="export1",
                content="Content 1",
                description="Export test 1"
            ),
            PromptTemplate(
                name="export2",
                content="Content 2",
                description="Export test 2"
            )
        ]
        
        for template in templates:
            manager.templates[template.name] = template
        
        # Export to directory
        export_dir = temp_dir / "exported"
        manager.export_prompts(str(export_dir))
        
        # Check exported files
        assert (export_dir / "export1.yaml").exists()
        assert (export_dir / "export2.yaml").exists()
        
        # Load exported prompt
        with open(export_dir / "export1.yaml", 'r') as f:
            exported_data = yaml.safe_load(f)
        
        assert exported_data['name'] == 'export1'
        assert exported_data['content'] == 'Content 1'
    
    def test_prompt_inheritance(self, manager):
        """Test prompt inheritance/composition"""
        # Base template
        base_template = PromptTemplate(
            name="base_analysis",
            content="Standard analysis header\n{content}\nStandard footer"
        )
        
        # Specialized template
        specialized_template = PromptTemplate(
            name="anr_analysis",
            content=manager.render_prompt("base_analysis", 
                content="ANR specific analysis: {log_data}")
        )
        
        manager.templates["base_analysis"] = base_template
        manager.templates["anr_analysis"] = specialized_template
        
        # Render specialized
        result = manager.render_prompt("anr_analysis", log_data="test data")
        
        assert "Standard analysis header" in result
        assert "ANR specific analysis: test data" in result
        assert "Standard footer" in result


class TestPromptVersioning:
    """Test prompt versioning functionality"""
    
    def test_version_comparison(self):
        """Test comparing prompt versions"""
        v1 = PromptTemplate(
            name="versioned",
            content="Version 1 content",
            version="1.0.0"
        )
        
        v2 = PromptTemplate(
            name="versioned",
            content="Version 2 content",
            version="2.0.0"
        )
        
        # Simple version comparison
        assert v1.version < v2.version
    
    def test_version_migration(self):
        """Test prompt version migration"""
        old_prompt = PromptTemplate(
            name="migrate",
            content="Analyze {data}",
            version="1.0.0",
            variables=[PromptVariable(name="data", required=True)]
        )
        
        new_prompt = PromptTemplate(
            name="migrate",
            content="Analyze {data}\nAdditional context: {context}",
            version="2.0.0",
            variables=[
                PromptVariable(name="data", required=True),
                PromptVariable(name="context", required=False, default="none")
            ]
        )
        
        # New version should be backward compatible
        # (can still render with only old variables)
        rendered = new_prompt.render(data="test data")
        assert "test data" in rendered
        assert "none" in rendered  # Default value


class TestPromptExamples:
    """Test real-world prompt examples"""
    
    def test_anr_analysis_prompt(self):
        """Test ANR analysis prompt"""
        anr_prompt = PromptTemplate(
            name="anr_intelligent",
            content="""你是一位 Android 系統專家，專門分析 ANR (Application Not Responding) 日誌。

請分析以下 ANR 日誌：
{log_content}

分析要求：
1. 識別主要線程狀態
2. 找出阻塞原因
3. 提供解決建議

輸出格式：
## 問題摘要
[簡述問題]

## 詳細分析
[詳細分析內容]

## 解決方案
[具體建議]""",
            variables=[
                PromptVariable(
                    name="log_content",
                    description="ANR log content",
                    required=True
                )
            ]
        )
        
        # Test rendering
        rendered = anr_prompt.render(log_content="[ANR LOG DATA]")
        
        assert "Android 系統專家" in rendered
        assert "[ANR LOG DATA]" in rendered
        assert "問題摘要" in rendered
        assert "詳細分析" in rendered
        assert "解決方案" in rendered
    
    def test_tombstone_analysis_prompt(self):
        """Test tombstone analysis prompt"""
        tombstone_prompt = PromptTemplate(
            name="tombstone_intelligent",
            content="""分析以下 Android Tombstone 崩潰日誌：

{crash_log}

請提供：
1. 崩潰類型: {crash_signal}
2. 崩潰位置分析
3. 可能的根本原因
4. 修復建議

重點關注記憶體相關問題和空指針異常。""",
            variables=[
                PromptVariable(name="crash_log", required=True),
                PromptVariable(
                    name="crash_signal",
                    required=False,
                    default="SIGSEGV"
                )
            ]
        )
        
        # Test with default signal
        rendered = tombstone_prompt.render(crash_log="[CRASH DATA]")
        assert "SIGSEGV" in rendered
        
        # Test with custom signal
        rendered = tombstone_prompt.render(
            crash_log="[CRASH DATA]",
            crash_signal="SIGABRT"
        )
        assert "SIGABRT" in rendered