import os

from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5-mini")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Hardcoded cookware list per spec
AVAILABLE_COOKWARE = [
    "Spatula",
    "Frying Pan",
    "Little Pot",
    "Stovetop",
    "Whisk",
    "Knife",
    "Ladle",
    "Spoon",
]

# Model temperature settings
CLASSIFICATION_TEMPERATURE = 0.0  # Deterministic for classification
CREATIVE_TEMPERATURE = 0.7  # Creative for recipe generation
