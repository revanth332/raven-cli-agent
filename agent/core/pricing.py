"""
Centralized model pricing (USD per 1M tokens) and context limit matrix.
"""

from typing import Dict, Any, Tuple

# Default pricing matrix: model_name -> (prompt_cost_per_1M, completion_cost_per_1M, context_window_limit)
MODEL_PRICING_REGISTRY: Dict[str, Dict[str, Any]] = {
    # OpenAI models
    "gpt-4o": {"input_cost_per_1m": 2.50, "output_cost_per_1m": 10.00, "context_limit": 128000},
    "gpt-4o-mini": {"input_cost_per_1m": 0.15, "output_cost_per_1m": 0.60, "context_limit": 128000},
    "o1": {"input_cost_per_1m": 15.00, "output_cost_per_1m": 60.00, "context_limit": 200000},
    "o3-mini": {"input_cost_per_1m": 1.10, "output_cost_per_1m": 4.40, "context_limit": 200000},
    
    # Anthropic models
    "claude-3-5-sonnet": {"input_cost_per_1m": 3.00, "output_cost_per_1m": 15.00, "context_limit": 200000},
    "claude-3-7-sonnet": {"input_cost_per_1m": 3.00, "output_cost_per_1m": 15.00, "context_limit": 200000},
    "claude-3-5-haiku": {"input_cost_per_1m": 0.80, "output_cost_per_1m": 4.00, "context_limit": 200000},
    "anthropic/claude-3.5-sonnet": {"input_cost_per_1m": 3.00, "output_cost_per_1m": 15.00, "context_limit": 200000},
    
    # Google Gemini models
    "gemini-3.6-flash": {"input_cost_per_1m": 1.50, "output_cost_per_1m": 7.50, "context_limit": 1048576},
    "gemini-3.5-flash": {"input_cost_per_1m": 1.50, "output_cost_per_1m": 9.00, "context_limit": 1048576},
    "gemini-3.1-pro-preview": {"input_cost_per_1m": 2.00, "output_cost_per_1m": 12.00, "context_limit": 1048576},
    
    # DeepSeek models
    "deepseek-chat": {"input_cost_per_1m": 0.14, "output_cost_per_1m": 0.28, "context_limit": 64000},
    "deepseek-reasoner": {"input_cost_per_1m": 0.55, "output_cost_per_1m": 2.19, "context_limit": 64000},
    "deepseek/deepseek-chat": {"input_cost_per_1m": 0.14, "output_cost_per_1m": 0.28, "context_limit": 64000},
    "deepseek/deepseek-r1": {"input_cost_per_1m": 0.55, "output_cost_per_1m": 2.19, "context_limit": 64000},
    
    # Meta / Qwen models
    "meta-llama/llama-3.3-70b-instruct": {"input_cost_per_1m": 0.30, "output_cost_per_1m": 0.40, "context_limit": 128000},
    "qwen/qwen-2.5-72b-instruct": {"input_cost_per_1m": 0.35, "output_cost_per_1m": 0.40, "context_limit": 128000},
}

DEFAULT_MODEL_PRICING = {
    "input_cost_per_1m": 0,
    "output_cost_per_1m": 0,
    "context_limit": 128000
}


def get_model_pricing(model_name: str) -> Dict[str, Any]:
    """
    Returns pricing and context limit configuration for a model name.
    Matches exact or partial key names (case-insensitive).
    """
    if not model_name:
        return DEFAULT_MODEL_PRICING.copy()
        
    lower_model = model_name.lower().strip()
    
    # Direct match
    if lower_model in MODEL_PRICING_REGISTRY:
        return MODEL_PRICING_REGISTRY[lower_model].copy()
        
    # Substring / prefix match
    for key, info in MODEL_PRICING_REGISTRY.items():
        if key in lower_model or lower_model.endswith(key):
            return info.copy()
            
    return DEFAULT_MODEL_PRICING.copy()


def calculate_cost(prompt_tokens: int, completion_tokens: int, model_name: str) -> float:
    """
    Calculates total USD cost for given prompt and completion tokens.
    """
    pricing = get_model_pricing(model_name)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input_cost_per_1m"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output_cost_per_1m"]
    return round(input_cost + output_cost, 6)
