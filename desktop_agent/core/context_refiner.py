import re

def extract_query_keywords(query):
    """
    Universal Keyword Extraction:
    Extracts potential technical/topic keywords (alphanumeric, 2+ chars).
    """
    TECH_WHITELIST = {'c#', 'sql', 'aws', 'ef', 'mvc', 'api', 'git', 'iis', 's3'}
    
    # Use a broader search for 2+ char alphanumeric strings that might include + or #
    # We use a pattern that looks for alphanumeric clusters and then verify boundaries
    found_keywords = set()
    
    # Capture standard alphanumeric words 2+ chars
    alpha_matches = re.findall(r'[a-zA-Z0-9+#]{2,}', query.lower())
    for m in alpha_matches:
        found_keywords.add(m)
    
    # Explicitly check whitelist with safer boundary detection
    q_lower = f" {query.lower()} "
    for term in TECH_WHITELIST:
        if f" {term} " in q_lower or re.search(rf'[^a-zA-Z0-9]{re.escape(term)}[^a-zA-Z0-9]', q_lower):
            found_keywords.add(term)
            
    return found_keywords

def extract_snippets(query, full_text, window_chars=500):
    """
    Project-Prioritized Snippet Recovery:
    Specific focus on finding project headers and real-world examples for Umesh.
    Normlizes text to handle PDF/Doc multiline issues.
    """
    if not full_text or full_text == "N/A":
        return "No specific context available."
    
    # Normalization: Replace newlines and tabs with single spaces
    clean_text = re.sub(r'[\t\r\n]+', ' ', full_text)
    
    keywords = extract_query_keywords(query)
    text_lower = clean_text.lower()
    
    # Project Header Heuristic
    project_indices = [m.start() for m in re.finditer(r'(?i)(Project|Title|Client):\s*([^\n\r]+)', clean_text)]
    
    matches = []
    for kw in keywords:
        # Avoid escaping regex chars like + # if they are in the keyword
        pattern = rf'\b{re.escape(kw)}\b'
        for match in re.finditer(pattern, text_lower):
            matches.append(match.start())
    
    if not matches and not project_indices:
        return clean_text[:600] + "..."
    
    all_targets = sorted(list(set(matches + project_indices)))
    
    merged_windows = []
    if all_targets:
        current_start = max(0, all_targets[0] - (window_chars // 2))
        current_end = min(len(clean_text), all_targets[0] + (window_chars // 2))
        
        for m in all_targets[1:]:
            m_start = max(0, m - (window_chars // 2))
            m_end = min(len(clean_text), m + (window_chars // 2))
            
            if m_start <= current_end:
                current_end = max(current_end, m_end)
            else:
                merged_windows.append((current_start, current_end))
                current_start = m_start
                current_end = m_end
        merged_windows.append((current_start, current_end))
    
    final_snippets = []
    for start, end in merged_windows:
        chunk = clean_text[start:end].strip()
        chunk_lower = chunk.lower()
        
        has_kw = any(kw in chunk_lower for kw in keywords)
        has_proj = any(p in chunk_lower for p in ["project", "client", "title", "enterprise", "system", "tracker", "dashboard"])
        
        if has_kw and has_proj:
            final_snippets.insert(0, chunk)
        else:
            final_snippets.append(chunk)
    
    result = " ... ".join(final_snippets)
    if len(result) > 5000:
        result = result[:5000] + "..."
        
    return result

def detect_intent(query):
    """
    Dynamic Intent Classification.
    """
    q = query.lower()
    
    # STAR Mode: Past actions, challenges, project history
    star_triggers = [
        "describe", "how did you", "tell me about", "give me an example", 
        "situation", "conflict", "challenge", "handled", "managed", "experience with",
        "contribution", "role in", "walk me through"
    ]
    
    # ARCHITECT Mode: Definitions, system design, how-to
    architect_triggers = [
        "architecture", "system design", "scaling", "optimization", "pattern", 
        "trade-off", "scalability", "how-to", "define", "explain", "why use"
    ]
    
    if any(t in q for t in star_triggers):
        return "STAR"
    if any(t in q for t in architect_triggers):
        return "ARCHITECT"
    
    return "GENERAL"

def check_knowledge_gap(query, cv_text):
    """
    Local Gap Analysis:
    Checks if tech keywords in query are absent in the CV.
    Uses normalized text for reliability.
    """
    if not cv_text or cv_text == "N/A":
        return False
    
    # Normalize CV text for matching
    clean_cv = re.sub(r'[\t\r\n]+', ' ', cv_text).lower()
        
    keywords = extract_query_keywords(query)
    if not keywords:
        return False
    
    for kw in keywords:
        if kw not in clean_cv:
            return True
            
    return False
