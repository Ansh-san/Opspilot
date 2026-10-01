"""Model Pricing Registry for FinOps / Cost Tracking."""

from typing import Dict, TypedDict

class ModelCost(TypedDict):
    input_cost_per_1m: float
    output_cost_per_1m: float

# Pricing per 1M tokens in USD
MODEL_PRICING: Dict[str, ModelCost] = {
    "gpt-4o-mini": {"input_cost_per_1m": 0.15, "output_cost_per_1m": 0.60},
    "gpt-4o": {"input_cost_per_1m": 5.00, "output_cost_per_1m": 15.00},
    "gpt-3.5-turbo": {"input_cost_per_1m": 0.50, "output_cost_per_1m": 1.50},
    "claude-3-haiku": {"input_cost_per_1m": 0.25, "output_cost_per_1m": 1.25},
    "claude-3-sonnet": {"input_cost_per_1m": 3.00, "output_cost_per_1m": 15.00},
    "claude-3-opus": {"input_cost_per_1m": 15.00, "output_cost_per_1m": 75.00},
    "mock": {"input_cost_per_1m": 0.0, "output_cost_per_1m": 0.0},
}

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float | None:
    """Calculates the estimated USD cost of an LLM run. Returns None if model is unknown."""
    if not model_name:
        return None
    
    # Try to match the exact model name, do NOT guess if unknown
    cost_info = MODEL_PRICING.get(model_name.lower())
    if not cost_info:
        return None
    
    input_cost = (max(0, input_tokens) / 1_000_000.0) * cost_info["input_cost_per_1m"]
    output_cost = (max(0, output_tokens) / 1_000_000.0) * cost_info["output_cost_per_1m"]
    
    return input_cost + output_cost
