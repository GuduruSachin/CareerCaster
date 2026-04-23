import os

def get_master_api_key():
    """
    Retrieves the global API key for CareerCaster.
    Prioritizes environment variables, then falls back to a local key file.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    
    # Developmental fallback / hardcoded placeholder for enterprise distribution
    # In a real build, this would be injected by the CI/CD pipeline
    return "YOUR_ENTERPRISE_API_KEY_HERE"
