"""Additional rule-based evaluators."""

from app.ai.evaluation.base import Evaluator, EvaluationResult


class RetrievalEvaluator(Evaluator):
    """Evaluates the quality of retrieved context."""
    name = "retrieval_quality"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        retrieved_chunks = ai_run_data.get("retrieved_documents", [])
        
        if not retrieved_chunks:
            return EvaluationResult(
                metric_name=self.name,
                score=0.0,
                status="INSUFFICIENT",
                explanation="No documents retrieved.",
                metadata={"chunk_count": 0}
            )

        similarities = [chunk.get("similarity_score", 0.0) for chunk in retrieved_chunks]
        avg_sim = sum(similarities) / len(similarities)
        top_sim = max(similarities)
        
        if avg_sim >= 0.8:
            status = "GOOD"
            explanation = "Retrieved high-quality context."
        elif top_sim >= 0.7:
            status = "WARNING"
            explanation = "Retrieved some relevant context, but average similarity is low."
        else:
            status = "INSUFFICIENT"
            explanation = "Retrieved context has low similarity scores."
            
        return EvaluationResult(
            metric_name=self.name,
            score=round(avg_sim, 3),
            status=status,
            explanation=explanation,
            metadata={
                "chunk_count": len(retrieved_chunks),
                "avg_similarity": round(avg_sim, 3),
                "top_similarity": round(top_sim, 3)
            }
        )


class ConfidenceValidator(Evaluator):
    """Validates if the agent's confidence matches its retrieved evidence."""
    name = "confidence_validation"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        confidence = ai_run_data.get("confidence", 0.0)
        retrieved_chunks = ai_run_data.get("retrieved_documents", [])
        chunk_count = len(retrieved_chunks)
        
        similarities = [chunk.get("similarity_score", 0.0) for chunk in retrieved_chunks]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

        if confidence >= 0.8 and chunk_count == 0:
            status = "CRITICAL"
            explanation = "Overconfident with no evidence."
        elif confidence >= 0.8 and avg_similarity >= 0.85:
            status = "ACCEPTABLE"
            explanation = "High confidence backed by strong evidence."
        elif confidence >= 0.8 and avg_similarity < 0.7:
            status = "WARNING"
            explanation = "Overconfident with weak evidence."
        elif confidence < 0.5 and chunk_count == 0:
            status = "EXPECTED"
            explanation = "Correctly uncertain due to lack of evidence."
        elif confidence < 0.5 and avg_similarity >= 0.85:
            status = "WARNING"
            explanation = "Underconfident despite strong evidence."
        else:
            status = "ACCEPTABLE"
            explanation = "Confidence generally aligns with evidence."
            
        return EvaluationResult(
            metric_name=self.name,
            score=confidence,
            status=status,
            explanation=explanation,
            metadata={
                "confidence": confidence,
                "retrieved_chunks": chunk_count,
                "avg_similarity": round(avg_similarity, 3)
            }
        )


class ClassificationEvaluator(Evaluator):
    """Compares AI classification against the final ticket state."""
    name = "classification_accuracy"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        ticket = ai_run_data.get("ticket_data", {})
        classification = ai_run_data.get("classification", {})
        
        if not classification:
            return EvaluationResult(
                metric_name=self.name, score=None, status="NOT_EVALUATED",
                explanation="No AI classification data available."
            )

        # Assuming ticket_data represents the "ground truth"
        expected_cat = ticket.get("category", "").lower()
        actual_cat = classification.get("category", "").lower()
        
        expected_pri = str(ticket.get("priority", "")).lower()
        actual_pri = str(classification.get("priority", "")).lower()
        
        expected_sev = str(ticket.get("severity", "")).lower()
        actual_sev = str(classification.get("severity", "")).lower()

        cat_match = expected_cat == actual_cat if expected_cat else True
        pri_match = expected_pri == actual_pri if expected_pri else True
        sev_match = expected_sev == actual_sev if expected_sev else True

        matches = [cat_match, pri_match, sev_match]
        accuracy = sum(matches) / 3.0

        if accuracy == 1.0:
            status = "GOOD"
            explanation = "Perfect classification match."
        elif accuracy >= 0.6:
            status = "WARNING"
            explanation = "Partial classification match."
        else:
            status = "CRITICAL"
            explanation = "Poor classification match."

        return EvaluationResult(
            metric_name=self.name,
            score=round(accuracy, 3),
            status=status,
            explanation=explanation,
            metadata={
                "category_match": cat_match,
                "priority_match": pri_match,
                "severity_match": sev_match
            }
        )


class ToolPolicyEvaluator(Evaluator):
    """Evaluates the policy/tool pipeline (proposed -> approved -> executed)."""
    name = "tool_policy"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        proposal = ai_run_data.get("action_proposal")
        policy = ai_run_data.get("policy_result", {})
        approval = ai_run_data.get("approval_data")
        
        if not proposal or proposal.get("proposed_action", "none").lower() == "none":
            return EvaluationResult(
                metric_name=self.name, score=None, status="EXPECTED",
                explanation="No action proposed."
            )

        proposed_action = proposal.get("proposed_action")
        
        if policy.get("requires_approval") and not approval:
            # Maybe approval was just created and is pending
            status = "EXPECTED"
            explanation = f"Proposed '{proposed_action}' and correctly blocked by policy for approval."
        elif policy.get("requires_approval") and approval:
            app_status = approval.get("status")
            if app_status == "approved":
                status = "GOOD"
                explanation = f"Proposed '{proposed_action}' and it was approved."
            elif app_status == "rejected":
                status = "WARNING"
                explanation = f"Proposed '{proposed_action}' but it was rejected."
            else:
                status = "EXPECTED"
                explanation = f"Proposed '{proposed_action}' is pending approval."
        else:
            # Low risk
            status = "GOOD"
            explanation = f"Proposed '{proposed_action}' and auto-executed safely."

        return EvaluationResult(
            metric_name=self.name,
            score=None,
            status=status,
            explanation=explanation,
            metadata={
                "proposed": True,
                "requires_approval": policy.get("requires_approval", False)
            }
        )


class HumanOverrideEvaluator(Evaluator):
    """Calculates human override metrics."""
    name = "human_override"

    def evaluate(self, ai_run_data: dict) -> EvaluationResult:
        # For a single run, it's either approved, rejected, or auto-executed.
        approval = ai_run_data.get("approval_data")
        policy = ai_run_data.get("policy_result", {})
        
        if not policy.get("requires_approval"):
            return EvaluationResult(
                metric_name=self.name, score=0.0, status="EXPECTED",
                explanation="Action did not require human override.",
                metadata={"auto_executed": True}
            )
            
        if not approval:
            return EvaluationResult(
                metric_name=self.name, score=None, status="EXPECTED",
                explanation="Pending human review.",
                metadata={"pending": True}
            )

        status_str = approval.get("status")
        if status_str == "rejected":
            return EvaluationResult(
                metric_name=self.name, score=1.0, status="WARNING",
                explanation="Human rejected the AI proposal.",
                metadata={"rejected": True}
            )
        elif status_str in ("approved", "executed"):
            return EvaluationResult(
                metric_name=self.name, score=0.0, status="GOOD",
                explanation="Human approved the AI proposal.",
                metadata={"approved": True}
            )
            
        return EvaluationResult(
            metric_name=self.name, score=None, status="NOT_EVALUATED",
            explanation=f"Approval status is {status_str}."
        )
