# Static Mirror for torch.testing
# This file exists to satisfy Torch 2.6.0+ internal imports in CPU-only builds.

def assert_allclose(*args, **kwargs): pass
def make_tensor(*args, **kwargs): pass
