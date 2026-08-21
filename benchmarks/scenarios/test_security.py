from src.core.security import SecurityScrubber

def run_security_benchmark() -> dict:
    """Measures adversarial leak vector interception efficiency."""
    scrubber = SecurityScrubber()
    
    # Real-world high-risk data samples
    leak_vectors = {
        "openai_key": '{"api_key": "sk-proj-1234567890abcdef1234567890abcdef12345"}',
        "bearer_token": "Authorization: Bearer secret_jwt_token_here",
        "customer_email": "Contact user at developer.lead@enterprise-cloud.io for details.",
        "json_password": '{"auth_token": "super_secret_pass_123", "username": "admin"}'
    }
    
    leaks_survived = 0
    
    for key, raw_payload in leak_vectors.items():
        scrubbed_output = scrubber.scrub_text(raw_payload)
        
        # Audit checks checking if high-risk strings slipped past filters
        if "sk-proj-" in scrubbed_output: leaks_survived += 1
        if "secret_jwt_" in scrubbed_output: leaks_survived += 1
        if "developer.lead" in scrubbed_output: leaks_survived += 1
        if "super_secret_pass" in scrubbed_output: leaks_survived += 1
            
    return {
        "total_secrets_injected": len(leak_vectors),
        "leaks_survived_count": leaks_survived,
        "data_sanitization_efficiency": ((len(leak_vectors) - leaks_survived) / len(leak_vectors)) * 100
    }
