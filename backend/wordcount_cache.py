"""
In-memory cache for the workspace word count.

Only word count is cached. File list / file body are always read from disk.

COUNT fallback (already implemented):
  If the cache is valid (no create/update/delete since the last compute),
  return the stored value (hit). Otherwise scan data/ now, store the
  result, and return it (miss).

Create / update / delete must call invalidate() so the next COUNT recomputes.
Optional strategies may call rebuild() to warm the cache without a COUNT.
"""

import threading

import data_logic

_lock = threading.Lock()
_cached_count = None
_valid = False

_hits = 0
_misses = 0
_computes = 0
_backend_calls = 0


def invalidate():
    """Mark the cache unusable. Next COUNT will recompute."""
    global _valid
    with _lock:
        _valid = False


def rebuild():
    """Scan data/ now and store the result. Counts as a cache build, not a COUNT."""
    global _cached_count, _valid, _computes
    with _lock:
        _computes += 1
        _cached_count = data_logic.count_words()
        _valid = True
        return _cached_count


def get_word_count():
    """Return the word count, recomputing on miss (COUNT fallback)."""
    global _cached_count, _valid, _hits, _misses, _computes
    with _lock:
        if _valid:
            _hits += 1
            return _cached_count, True
        _misses += 1
        _computes += 1
        _cached_count = data_logic.count_words()
        _valid = True
        return _cached_count, False


def note_backend_call():
    """Count one REST call toward cache_build_rate's denominator."""
    global _backend_calls
    with _lock:
        _backend_calls += 1


def reset_metrics():
    """Clear hit / miss / compute / backend-call counters. Cache contents stay."""
    global _hits, _misses, _computes, _backend_calls
    with _lock:
        _hits = 0
        _misses = 0
        _computes = 0
        _backend_calls = 0


def metrics():
    """Snapshot of cache counters for the workload tester."""
    with _lock:
        n_count = _hits + _misses
        miss_rate = (_misses / n_count) if n_count else 0.0
        cache_build_rate = (
            (_computes / _backend_calls) if _backend_calls else 0.0
        )
        return {
            "miss_rate": miss_rate,
            "cache_build_rate": cache_build_rate,
            "hits": _hits,
            "misses": _misses,
            "computes": _computes,
            "backend_calls": _backend_calls,
            "valid": _valid,
        }
