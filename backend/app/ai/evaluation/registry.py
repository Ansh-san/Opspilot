"""Evaluation Registry for OpsPilot Phase 6."""

import logging
from app.ai.evaluation.base import Evaluator, EvaluationResult
from app.ai.evaluation.groundedness import GroundednessEvaluator
from app.ai.evaluation.rules import (
    RetrievalEvaluator,
    ConfidenceValidator,
    ClassificationEvaluator,
    ToolPolicyEvaluator,
    HumanOverrideEvaluator,
)

logger = logging.getLogger(__name__)


class EvaluationRegistry:
    """Registry to hold and execute all active evaluators."""

    def __init__(self):
        self.evaluators: list[Evaluator] = [
            RetrievalEvaluator(),
            GroundednessEvaluator(),
            ConfidenceValidator(),
            ClassificationEvaluator(),
            ToolPolicyEvaluator(),
            HumanOverrideEvaluator(),
        ]

    def run_all(self, ai_run_data: dict) -> list[dict]:
        """
        Execute all registered evaluators against the provided AI run data.
        Returns a list of dictionaries suitable for storing in JSONB.
        """
        results = []
        for evaluator in self.evaluators:
            try:
                result: EvaluationResult = evaluator.evaluate(ai_run_data)
                results.append(result.model_dump())
            except Exception as e:
                logger.exception("Evaluator %s failed: %s", evaluator.name, e)
                results.append({
                    "metric_name": evaluator.name,
                    "score": None,
                    "status": "NOT_EVALUATED",
                    "explanation": f"Evaluator failed with exception: {e}",
                    "metadata": {}
                })
        return results


# Global registry instance
eval_registry = EvaluationRegistry()
