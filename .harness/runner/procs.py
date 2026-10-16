"""Process handling and usage constants shared by every executor."""
import ctypes
import os
import re
import subprocess
import time

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read")
# executor exit codes, so the run loop can branch without magic numbers per executor
EXIT_RATE_LIMIT = 75
EXIT_TIMEOUT = 124

# Win32 bits for a kill-on-close job object; every call degrades gracefully on failure.
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 0x00000102

if os.name == "nt":
    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

_JOBS = {}


def _kernel32():
    return ctypes.WinDLL("kernel32", use_last_error=True)


def create_job():
    """Create a kill-on-close Windows job object; None on posix or any failure."""
    if os.name != "nt":
        return None
    try:
        k32 = _kernel32()
        k32.CreateJobObjectW.restype = ctypes.c_void_p
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(
            ctypes.c_void_p(job), _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            k32.CloseHandle(ctypes.c_void_p(job))
            return None
        return job
    except Exception:
        return None


def assign_job(job, pid):
    """Put pid (and its future children) into job; False on posix or any failure."""
    if os.name != "nt" or not job:
        return False
    try:
        k32 = _kernel32()
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not h:
            return False
        try:
            return bool(k32.AssignProcessToJobObject(ctypes.c_void_p(job), ctypes.c_void_p(h)))
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        return False


def close_job(job):
    """Release a job handle; never raises."""
    if os.name != "nt" or not job:
        return
    try:
        _kernel32().CloseHandle(ctypes.c_void_p(job))
    except Exception:
        pass


def register_job(pid, job):
    """Remember which job owns a pid so stop_process_tree can terminate it."""
    if os.name != "nt" or not job:
        return
    _JOBS[pid] = job


def job_for(pid):
    if os.name != "nt":
        return None
    return _JOBS.get(pid)


def pid_alive(pid):
    """True only if pid is a live process; False on posix or any failure."""
    if os.name != "nt":
        return False
    try:
        k32 = _kernel32()
        k32.OpenProcess.restype = ctypes.c_void_p
        h = k32.OpenProcess(_SYNCHRONIZE, False, pid)
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(ctypes.c_void_p(h), 0) == _WAIT_TIMEOUT
        finally:
            k32.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        return False


def zero_usage():
    return {**dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}


def stop_process_tree(p, timeout=10):
    """Kill p and its descendants. Prefers the registered job; falls back to taskkill.
    Returns None and never raises."""
    if os.name == "nt":
        job = job_for(p.pid)
        if job is not None:
            try:
                _kernel32().TerminateJobObject(ctypes.c_void_p(job), 1)
            except Exception:
                pass
            close_job(job)
            _JOBS.pop(p.pid, None)
        else:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            except Exception:
                pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not pid_alive(p.pid):
                break
            time.sleep(0.05)
    else:
        try:
            p.kill()
        except Exception:
            pass
