"""Base interfaces for the Rule-Based Evaluation Engine."""

from typing import Any
from pydantic import BaseModel, Field

class EvaluationResult(BaseModel):
    """Result of a single evaluation rule."""
    metric_name: str
    score: float | None = None
    status: str = Field(..., description="GOOD, WARNING, CRITICAL, EXPECTED, INSUFFICIENT, NOT_EVALUATED")
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evaluator:
    """Base class for all evaluators."""
    
    name: str = "base_evaluator"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        """
        Evaluate an AI Run based on its data.
        
        Args:
            ai_run_data (dict): A dictionary representing the AI run state and trace.
                Typically includes:
                - ticket_data: dict
                - retrieved_documents: list[dict]
                - classification: dict
                - diagnosis: dict
                - recommendation: dict
                - action_proposal: dict
                - confidence: float
                - risk_level: str
                - policy_result: dict
                
        Returns:
            EvaluationResult: The structured result of the evaluation.
        """
        raise NotImplementedError("Subclasses must implement evaluate()")
