# Static Mirror for torch.distributed.rpc
# This file exists to satisfy Torch 2.6.0+ internal imports in CPU-only builds.

def is_available(): return False
