"""gpu detection via pynvml."""

import pynvml


def detect_gpu(device_index=0):
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
    name = pynvml.nvmlDeviceGetName(handle)
    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
    driver = pynvml.nvmlSystemGetDriverVersion()
    pynvml.nvmlShutdown()
    return {
        "name": name,
        "vram_mb": mem.total // (1024 * 1024),
        "vram_bytes": mem.total,
        "driver": driver,
    }
