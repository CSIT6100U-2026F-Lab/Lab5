"""
Workload patterns for Lab 5 word-count cache metrics.

Start the REST backend from Lab5 first:

    python3 backend/rest_service.py

Then, also from Lab5:

    python3 frontend/workload_test.py

Does not modify data/main.py or data/utils.js. Uses a scratch file
wkld_scratch.txt and deletes it afterward.

Each pattern is a short sequence repeated REPEAT times. write_then_read
is write_heavy for one half, then read_heavy for the other. Metrics
are reset before every pattern. UPDATE = POST /update, COUNT = GET /wordcount.
"""

import http.client
import json
import os
import sys

HOST = "127.0.0.1"
PORT = int(os.environ.get("REST_PORT", "8000"))
REPEAT = 400
SCRATCH = "wkld_scratch.txt"


def rest(method, path, payload=None):
    """Call the REST API. Returns (status_code, parsed_json_or_None)."""
    headers = {}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        status = response.status
    finally:
        conn.close()
    parsed = None
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            parsed = None
    return status, parsed


def update_scratch(n):
    content = "token{}\n".format(n) * 3
    status, _body = rest("POST", "/update/{}".format(SCRATCH), {"content": content})
    if status != 200:
        raise RuntimeError("update failed: {}".format(status))


def get_wordcount():
    status, body = rest("GET", "/wordcount")
    if status != 200:
        raise RuntimeError("wordcount failed: {}".format(status))
    return body


def reset_metrics():
    status, _body = rest("POST", "/wordcount/metrics/reset")
    if status != 200:
        raise RuntimeError("reset failed: {}".format(status))


def read_metrics():
    status, body = rest("GET", "/wordcount/metrics")
    if status != 200 or not body:
        raise RuntimeError("metrics failed: {}".format(status))
    return body


def ensure_scratch():
    status, _body = rest("POST", "/create/{}".format(SCRATCH), {"content": "seed\n"})
    if status == 409:
        update_scratch(0)
        return
    if status != 201:
        raise RuntimeError("create scratch failed: {}".format(status))


def delete_scratch():
    rest("DELETE", "/file/{}".format(SCRATCH))


def run_pattern(name, runner):
    ensure_scratch()
    reset_metrics()
    runner()
    stats = read_metrics()
    delete_scratch()
    print(
        "{:<18}  miss_rate={:.3f}  cache_build_rate={:.3f}  "
        "(COUNT misses={}/{}  computes={}  backend_calls={})".format(
            name,
            stats["miss_rate"],
            stats["cache_build_rate"],
            stats["misses"],
            stats["hits"] + stats["misses"],
            stats["computes"],
            stats["backend_calls"],
        )
    )
    return stats


def pattern_write_heavy():
    """Four UPDATEs, then one COUNT."""
    step = 0
    for _ in range(REPEAT):
        for _inner in range(4):
            update_scratch(step)
            step += 1
        get_wordcount()


def pattern_read_heavy():
    """One UPDATE, then five COUNTs."""
    step = 0
    for _ in range(REPEAT):
        update_scratch(step)
        step += 1
        for _inner in range(5):
            get_wordcount()


def pattern_balanced():
    """Two UPDATEs, then two COUNTs."""
    step = 0
    for _ in range(REPEAT):
        update_scratch(step)
        step += 1
        update_scratch(step)
        step += 1
        get_wordcount()
        get_wordcount()


def pattern_write_then_read():
    """First half: write_heavy motif. Second half: read_heavy motif."""
    pattern_write_heavy()
    pattern_read_heavy()


def main():
    try:
        rest("GET", "/files")
    except OSError:
        print(
            "cannot reach {}:{} — start python3 backend/rest_service.py".format(
                HOST, PORT
            ),
            file=sys.stderr,
        )
        return 2

    print("REPEAT={}  scratch={}".format(REPEAT, SCRATCH))
    print("UPDATE = POST /update/{}   COUNT = GET /wordcount".format(SCRATCH))
    print("")
    run_pattern("write_heavy", pattern_write_heavy)
    run_pattern("read_heavy", pattern_read_heavy)
    run_pattern("balanced", pattern_balanced)
    run_pattern("write_then_read", pattern_write_then_read)
    return 0


if __name__ == "__main__":
    sys.exit(main())
