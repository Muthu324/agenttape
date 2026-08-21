import sys
from src.core.matcher import SemanticMatcher

def run_mutation_benchmark() -> dict:
    """Evaluates prompt-resilient matching stability across mutated variations."""
    matcher = SemanticMatcher(threshold=0.92)
    
    baseline_prompt = "You are a senior system auditor. Analyze the following local system repository file logs to isolate memory leak vulnerabilities."
    
    # Adversarial changes that routinely break standard strict-hash mock engines
    mutations = [
        "You are a senior system auditor. Analyze the following local system repository file logs to isolate memory leak vulnerabilities. [Current Time: 2026-08-21T14:22:10Z]",
        "please analyze the following local system repository file logs to isolate memory leak vulnerabilities.",
        "   you are a senior system auditor. analyze the following local system repository file logs to isolate memory leak vulnerabilities   ",
        "You are a senior system auditor. Check the following local system repository file logs to identify memory leak defects.",
    ]
    
    invalid_prompts = [
        "Delete all database transaction rows immediately.",
        "Generate a joke about deployment pipelines.",
    ]
    
    true_positives = 0
    false_positives = 0
    
    # Test tolerance stability against acceptable changes
    for mutated in mutations:
        score = matcher.calculate_similarity(baseline_prompt, mutated)
        if score >= matcher.threshold:
            true_positives += 1
            
    # Test safety against unauthorized prompt drift (False matches)
    for invalid in invalid_prompts:
        score = matcher.calculate_similarity(baseline_prompt, invalid)
        if score >= matcher.threshold:
            false_positives += 1
            
    return {
        "total_mutations_evaluated": len(mutations),
        "true_positive_replay_rate": (true_positives / len(mutations)) * 100,
        "false_positive_leak_rate": (false_positives / len(invalid_prompts)) * 100
    }
