"""
Centralized model pricing (USD per 1M tokens) and context limit matrix.
"""

from typing import Dict, Any, Tuple

# Default pricing matrix: model_name -> (prompt_cost_per_1M, completion_cost_per_1M, context_window_limit)
MODEL_PRICING_REGISTRY: Dict[str, Dict[str, Any]] = {
    # OpenAI models
    "gpt-5.6-sol": {"input_cost_per_1m": 5.00, "output_cost_per_1m": 30.00, "context_limit": 128000},
    "gpt-5.6-terra": {"input_cost_per_1m": 2.00, "output_cost_per_1m": 12.00, "context_limit": 128000},
    "gpt-5.6-luna": {"input_cost_per_1m": 0.20, "output_cost_per_1m": 1.20, "context_limit": 128000},
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
    "gemini-3.8-flash": {"input_cost_per_1m": 0.75, "output_cost_per_1m": 3.75, "context_limit": 1048576},
    "gemini-3.7-flash": {"input_cost_per_1m": 0.75, "output_cost_per_1m": 3.75, "context_limit": 1048576},
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

# Dynamically registered model pricing from discovery endpoints
DYNAMIC_MODEL_PRICING_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_dynamic_model_pricing(
    model_name: str,
    input_cost_per_1m: float,
    output_cost_per_1m: float,
    context_limit: int = 128000
) -> None:
    """
    Registers or updates model pricing and context limit dynamically at runtime.
    """
    if not model_name:
        return
    lower_model = model_name.lower().strip()
    DYNAMIC_MODEL_PRICING_REGISTRY[lower_model] = {
        "input_cost_per_1m": float(input_cost_per_1m),
        "output_cost_per_1m": float(output_cost_per_1m),
        "context_limit": int(context_limit) if context_limit else 128000,
    }


def get_model_pricing(model_name: str) -> Dict[str, Any]:
    """
    Returns pricing and context limit configuration for a model name.
    Matches dynamic registry first, then static registry (exact or partial, case-insensitive).
    """
    if not model_name:
        return DEFAULT_MODEL_PRICING.copy()
        
    lower_model = model_name.lower().strip()
    
    # Dynamic registry direct match
    if lower_model in DYNAMIC_MODEL_PRICING_REGISTRY:
        return DYNAMIC_MODEL_PRICING_REGISTRY[lower_model].copy()

    # Dynamic registry partial match
    for key, info in DYNAMIC_MODEL_PRICING_REGISTRY.items():
        if key in lower_model or lower_model.endswith(key):
            return info.copy()

    # Static registry direct match
    if lower_model in MODEL_PRICING_REGISTRY:
        return MODEL_PRICING_REGISTRY[lower_model].copy()
        
    # Static registry substring / prefix match
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
