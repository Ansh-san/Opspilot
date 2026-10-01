# app/ai/evaluation/groundedness.py
from app.ai.evaluation.base import Evaluator, EvaluationResult

class GroundednessEvaluator(Evaluator):
    name = "evidence_coverage"
    
    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        retrieved_chunks = ai_run_data.get("retrieved_documents", [])
        cited_sources = ai_run_data.get("diagnosis", {}).get("supporting_evidence", [])
        
        if not retrieved_chunks:
            return EvaluationResult(
                metric_name=self.name, score=None, status="NOT_EVALUATED",
                explanation="No documents were retrieved. Cannot evaluate groundedness.",
                metadata={"retrieved_count": 0, "cited_count": len(cited_sources)}
            )
        
        retrieved_ids = {chunk["chunk_id"] for chunk in retrieved_chunks}
        cited_ids = {source.get("chunk_id") for source in cited_sources if source.get("chunk_id")}
        
        unsupported_claims = cited_ids - retrieved_ids
        supported_claims = cited_ids & retrieved_ids
        coverage = len(supported_claims) / len(retrieved_ids) if retrieved_ids else 0
        
        if unsupported_claims:
            status = "WARNING"
            explanation = f"AI cited {len(unsupported_claims)} source(s) not found in retrieved documents."
        elif coverage >= 0.5:
            status = "GOOD"
            explanation = f"AI referenced {len(supported_claims)}/{len(retrieved_ids)} retrieved sources. Coverage: {coverage:.0%}."
        else:
            status = "WARNING"
            explanation = f"AI referenced only {len(supported_claims)}/{len(retrieved_ids)} retrieved sources. Most evidence unused."
        
        return EvaluationResult(
            metric_name=self.name, score=round(coverage, 3), status=status, explanation=explanation,
            metadata={"retrieved_count": len(retrieved_ids), "cited_count": len(cited_ids), 
                      "supported_count": len(supported_claims), "unsupported_claims": list(unsupported_claims)}
        )
