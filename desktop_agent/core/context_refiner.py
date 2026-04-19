import re

def extract_snippets(query, full_text, window=3):
    """
    RAG-Lite Snippet Extraction:
    Finds keywords from the query in the full text and returns surrounding sentences.
    """
    if not full_text or full_text == "N/A":
        return "No specific context available."
    
    # Extract keywords (words > 3 chars, alphanumeric)
    keywords = re.findall(r'\b\w{4,}\b', query.lower())
    if not keywords:
        return full_text[:500] + "..." # Fallback to start
    
    # Split text into sentences (basic split)
    sentences = re.split(r'(?<=[.!?]) +', full_text)
    
    matched_indices = []
    for i, sent in enumerate(sentences):
        if any(kw in sent.lower() for kw in keywords):
            matched_indices.append(i)
    
    if not matched_indices:
        return full_text[:500] + "..."
    
    # Take unique indices with window
    final_indices = set()
    for idx in matched_indices:
        for i in range(max(0, idx - window), min(len(sentences), idx + window + 1)):
            final_indices.add(i)
    
    result = " ".join([sentences[i] for i in sorted(list(final_indices))])
    
    # Token safety (approx)
    if len(result) > 2000:
        result = result[:2000] + "..."
        
    return result

def detect_intent(query):
    """
    Metadata detection for persona pivoting.
    """
    q = query.lower()
    star_keywords = ["tell me about", "situation", "conflict", "experience with", "teamwork", "leadership", "challenge", "project", "behavioral"]
    tech_keywords = ["architecture", "scaling", "optimization", "system design", "pattern", "microservices", "database", "security", "framework"]
    
    if any(k in q for k in star_keywords):
        return "STAR-Experience"
    if any(k in q for k in tech_keywords):
        return "Architect-Technical"
    
    return "General-Technical"

def check_knowledge_gap(query, cv_text):
    """
    Detect if the user is asked about something NOT in their CV.
    """
    if not cv_text or cv_text == "N/A":
        return False
        
    # Common tech keywords to check
    tech_stack = ["sql", "python", "javascript", "react", "angular", "node", "aws", "azure", "docker", "kubernetes", 
                  "c#", ".net", "java", "spring", "c++", "golang", "swift", "kotlin", "typescript", "ruby", "php"]
    
    q_tech = [t for t in tech_stack if re.search(rf'\b{t}\b', query.lower())]
    if not q_tech:
        return False
        
    cv_lower = cv_text.lower()
    for t in q_tech:
        if t not in cv_lower:
            return True # Missing at least one tech mentioned
            
    return False
