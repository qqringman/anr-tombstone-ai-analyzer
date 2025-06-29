from enum import Enum

class ModelProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

class AnalysisMode(Enum):
    QUICK = "quick"
    INTELLIGENT = "intelligent"
    LARGE_FILE = "large_file"
    MAX_TOKEN = "max_token"
