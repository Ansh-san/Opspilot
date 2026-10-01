import pytest
from app.ai.evaluation.rules import RetrievalEvaluator, ConfidenceValidator, ClassificationEvaluator
from app.ai.evaluation.groundedness import GroundednessEvaluator

def test_retrieval_evaluator():
    evaluator = RetrievalEvaluator()
    
    # 1. GOOD case
    res1 = evaluator.evaluate({"retrieved_documents": [{"similarity_score": 0.9}, {"similarity_score": 0.85}]})
    assert res1.status == "GOOD"
    assert res1.score == 0.875
    
    # 2. WARNING case
    res2 = evaluator.evaluate({"retrieved_documents": [{"similarity_score": 0.75}, {"similarity_score": 0.5}]})
    assert res2.status == "WARNING"
    assert res2.score == 0.625
    
    # 3. INSUFFICIENT case
    res3 = evaluator.evaluate({"retrieved_documents": [{"similarity_score": 0.4}, {"similarity_score": 0.5}]})
    assert res3.status == "INSUFFICIENT"
    assert res3.score == 0.45
    
    # 4. No documents case
    res4 = evaluator.evaluate({})
    assert res4.status == "INSUFFICIENT"
    assert res4.score == 0.0

def test_groundedness_evaluator():
    evaluator = GroundednessEvaluator()
    
    # 1. No documents case
    res1 = evaluator.evaluate({})
    assert res1.status == "NOT_EVALUATED"
    
    # 2. GOOD (all cited sources found in retrieval)
    res2 = evaluator.evaluate({
        "retrieved_documents": [{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        "diagnosis": {"supporting_evidence": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]}
    })
    assert res2.status == "GOOD"
    assert res2.score == 1.0
    
    # 3. WARNING (unsupported claim)
    res3 = evaluator.evaluate({
        "retrieved_documents": [{"chunk_id": "c1"}],
        "diagnosis": {"supporting_evidence": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]}
    })
    assert res3.status == "WARNING"
    # coverage = supported(1) / retrieved(1) = 1.0 but it's a WARNING because of unsupported claim
    assert len(res3.metadata["unsupported_claims"]) == 1

def test_confidence_validator():
    evaluator = ConfidenceValidator()
    
    # CRITICAL: Overconfident with no evidence
    res1 = evaluator.evaluate({"confidence": 0.9, "retrieved_documents": []})
    assert res1.status == "CRITICAL"
    
    # ACCEPTABLE: High confidence, strong evidence
    res2 = evaluator.evaluate({"confidence": 0.9, "retrieved_documents": [{"similarity_score": 0.9}]})
    assert res2.status == "ACCEPTABLE"
    
    # WARNING: Overconfident with weak evidence
    res3 = evaluator.evaluate({"confidence": 0.9, "retrieved_documents": [{"similarity_score": 0.5}]})
    assert res3.status == "WARNING"

def test_classification_evaluator():
    evaluator = ClassificationEvaluator()
    
    # PERFECT match
    res1 = evaluator.evaluate({
        "ticket_data": {"category": "Network", "priority": "High", "severity": "S1"},
        "classification": {"category": "Network", "priority": "High", "severity": "S1"}
    })
    assert res1.status == "GOOD"
    assert res1.score == 1.0
    
    # PARTIAL match (2/3 correct)
    res2 = evaluator.evaluate({
        "ticket_data": {"category": "Network", "priority": "High", "severity": "S1"},
        "classification": {"category": "Network", "priority": "High", "severity": "S2"}
    })
    assert res2.status == "WARNING"
    assert res2.score == pytest.approx(0.666, 0.01)
    
    # POOR match (1/3 correct)
    res3 = evaluator.evaluate({
        "ticket_data": {"category": "Network", "priority": "High", "severity": "S1"},
        "classification": {"category": "Hardware", "priority": "Low", "severity": "S1"}
    })
    assert res3.status == "CRITICAL"
    assert res3.score == pytest.approx(0.333, 0.01)
