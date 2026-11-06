import socket
import time

import psutil


def collect_local() -> dict:
    cpu = psutil.cpu_percent(interval=0.15)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/data")
    network = psutil.net_io_counters()
    return dict(
        timestamp=time.time(),
        hostname=socket.gethostname(),
        cpu_percent=cpu,
        cpu_count=psutil.cpu_count(),
        memory_total=memory.total,
        memory_used=memory.total - memory.available,
        memory_percent=memory.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_percent=disk.percent,
        net_sent=network.bytes_sent,
        net_recv=network.bytes_recv,
        uptime=time.time() - psutil.boot_time(),
    )
