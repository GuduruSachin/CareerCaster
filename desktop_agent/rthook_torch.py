import sys
import types

# --- PyInstaller Runtime Hook: torch.distributed package mock ---
# This script runs before the main application to handle 
# Missing/Incomplete torch.distributed in CPU-only builds.

def install_torch_package_mock():
    # 1. Ensure 'torch' exists in sys.modules
    if 'torch' not in sys.modules:
        sys.modules['torch'] = types.ModuleType('torch')
        
    # 2. Inject 'torch.distributed' as a PACKAGE
    if 'torch.distributed' not in sys.modules:
        dist_mock = types.ModuleType('torch.distributed')
        # Setting __path__ to an empty list makes it a package for the importer
        dist_mock.__path__ = [] 
        sys.modules['torch.distributed'] = dist_mock
        
        # 3. Add required attributes for model initialization
        dist_mock.is_available = lambda: False
        dist_mock.is_initialized = lambda: False
        dist_mock.get_rank = lambda: 0
        dist_mock.get_world_size = lambda: 1
        
        # 4. Mock essential sub-modules that Torch 2.6.0+ internally expects
        # These are usually what trigger the "module not found" errors
        for sub in ['rpc', 'autograd', 'launcher', 'c10d', 'optim']:
            full_name = f'torch.distributed.{sub}'
            if full_name not in sys.modules:
                sys.modules[full_name] = types.ModuleType(full_name)

    # 5. Handle torch.testing and other common crashing sub-modules
    if 'torch.testing' not in sys.modules:
        sys.modules['torch.testing'] = types.ModuleType('torch.testing')

try:
    install_torch_package_mock()
except Exception:
    pass # Silent fail to ensure app attempts to load anyway
