import torch
import os

def check_model():
    path = "desktop_agent/models/silero_vad.jit"
    print(f"Checking model at: {path}")
    if not os.path.exists(path):
        print("File does not exist")
        return
    
    print(f"File size: {os.path.getsize(path)} bytes")
    try:
        model = torch.jit.load(path)
        print("Success: Model loaded successfully!")
    except Exception as e:
        print(f"Error: Model loading failed: {e}")

if __name__ == "__main__":
    check_model()
