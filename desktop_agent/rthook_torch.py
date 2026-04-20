import sys
import types

# --- PyInstaller Runtime Hook: torch.distributed package mock ---
# This script runs BEFORE the main application in the frozen EXE.
# We ONLY mock the distributed components to satisfy Torch 2.6.0+ internal imports
# without shadowing the real torch library.

def install_torch_mocks():
    # IMPORTANT: We DO NOT mock 'torch' itself here. 
    # If we put a dummy 'torch' in sys.modules, the real library won't load.
    
    if 'torch.distributed' not in sys.modules:
        dist_mock = types.ModuleType('torch.distributed')
        dist_mock.__path__ = []  # CRITICAL: Mark as a package for sub-imports like .rpc
        sys.modules['torch.distributed'] = dist_mock
        
        # Inject required attributes for sanity checks
        dist_mock.is_available = lambda: False
        dist_mock.is_initialized = lambda: False
        dist_mock.get_rank = lambda: 0
        dist_mock.get_world_size = lambda: 1
        
        # Mock submodules specifically targeted by torch internals
        for sub in ['rpc', 'autograd', 'launcher', 'c10d', 'optim']:
            sub_name = f'torch.distributed.{sub}'
            if sub_name not in sys.modules:
                sys.modules[sub_name] = types.ModuleType(sub_name)

    # Also mock torch.testing as it's often excluded to save space
    if 'torch.testing' not in sys.modules:
        sys.modules['torch.testing'] = types.ModuleType('torch.testing')

try:
    install_torch_mocks()
except Exception:
    pass 
