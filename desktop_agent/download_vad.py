import os
import torch
import requests

def download_silero_vad():
    """
    Downloads the Silero VAD JIT model for offline use in CareerCaster.
    Saves it to desktop_agent/models/silero_vad.jit
    """
    # 1. Define paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, "models")
    target_path = os.path.join(models_dir, "silero_vad.jit")
    
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)
        
    print(f"[*] Target Directory: {models_dir}")
    
    # 2. Silero VAD JIT URL (Official Stable Release)
    # We use torch.hub to get the path, then copy it, or download directly.
    # Direct download is more reliable for a "clean" script.
    url = "https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.jit"
    
    if os.path.exists(target_path):
        print(f"[!] {target_path} already exists. Skipping download.")
        return

    print(f"[*] Downloading Silero VAD JIT from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"[+] Successfully downloaded VAD model to: {target_path}")
        print("[+] CareerCaster is now ready for offline stealth execution.")
        
    except Exception as e:
        print(f"[!] Download failed: {e}")
        print("[!] Attempting fallback via torch.hub (requires internet)...")
        try:
            # Fallback only if direct download fails
             model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                          model='silero_vad',
                                          force_reload=False,
                                          trust_repo=True)
             torch.jit.save(model, target_path)
             print(f"[+] Fallback Success: Model saved to {target_path}")
        except Exception as fe:
            print(f"[!!] Total Failure: {fe}")

if __name__ == "__main__":
    download_silero_vad()
