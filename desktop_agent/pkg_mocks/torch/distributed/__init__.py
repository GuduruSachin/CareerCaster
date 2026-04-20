# Static Mirror for torch.distributed
# This file exists to satisfy Torch 2.6.0+ internal imports in CPU-only builds.

def is_available(): return False
def is_initialized(): return False
def get_rank(): return 0
def get_world_size(): return 0
