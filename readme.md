# Lab 5 — Cached word count


## 1. Overview


In Lab5, we have the File CRUD APIs (same as Lab3), as well as the Word Count API (from Lab2), all implemented using REST. Thus, we have the following APIs in `backend/rest_service.py`:
+ `list_files`
+ `get_file`
+ `create_file`
+ `delete_file`
+ `update_file` (**UPDATE**)
+ `get_word_count` (**COUNT**)

In this Lab, we want to build **a cache mechanism** for COUNT.

### 1.1 Motivation for Caching

For COUNT, scanning the whole `data/` is relatively expensive. One idea is to compute the count *ahead of time* (for example after UPDATE) and keep it in a cache, so COUNT can return immediately.

However, any file write makes that cache outdated.
+ In this lab, you only need to reason about the UPDATE API. 

The starter code already provides a naive strategy
+ It invalidates the cache on every UPDATE.
+ It only recomputes the cache when a COUNT is called and the cache is missed (see `wordcount_cache.py/get_word_count`).
+ In this case, a COUNT after an UPDATE is always a miss.

You need a better strategy that **selectively rebuilds** the word-count cache so later COUNTs can hit, without rebuilding on every UPDATE.

## 2. Setup

```bash
pip install -r requirements.txt
```

## 3. Start

Separate terminals:

```bash
python3 backend/rest_service.py
python3 frontend/serve.py
```

Editor (COUNT in the toolbar): http://127.0.0.1:5500/  

If a previous run left a port busy:

```bash
lsof -tiTCP:8000,5500 -sTCP:LISTEN | xargs kill
```

The following command runs the cache workloads (REST server must be running):

```bash
python3 frontend/workload_test.py
```

## 4. TODO

Fill in the `# TODO` regions in `backend/rest_service.py` next to:
+ `update_file` (**UPDATE**): This is the write that should drive your cache strategy.
+ `get_word_count` (**COUNT**): Your strategy may have something to do with this method as well.
+ NOTE: you can also define additional helper functions or use global variables to implement the cache.


`wordcount_cache.py` provides the helpers:
- `invalidate()` — mark the cache stale (the next COUNT recomputes).
- `rebuild()` — scan `data/` now and store the result (you will use it in `update_file`).
- `get_word_count()` — Returns the wordcount (from cache, or immediately rebuilding the cache on miss).


Requirements: **every** workload in `workload_test.py` must satisfy both
+ **cache miss rate** < 20%.
    `miss_rate = (# COUNT misses) / (# COUNT hits + misses)`  
    A miss is a COUNT that had to recompute (fallback). Hits and misses are only counted on COUNT.
+ **cache build rate** < 40%.
    `cache_build_rate = (# cache builds) / (# counted REST calls)` 
    Builds (`computes`) include COUNT fallback *and* any `rebuild()`. 
  

The returned `word_count` must still be the current total (COUNT fallback already guarantees this if you invalidate after an UPDATE that you do not rebuild).

**Hint:** profile the last 20 UPDATE and COUNT calls. Record the **average consecutive-UPDATE run length** in that window, and rebuild after that many UPDATEs in a row (so an UPDATE burst shares one build, and a following COUNT can hit).

## 5. Evaluation (`workload_test.py`)

REST must be running:

```shell
python3 frontend/workload_test.py
```

It uses a scratch file `wkld_scratch.txt` (not `data/main.py` / `data/utils.js`), resets metrics before each pattern, and prints `miss_rate` and `cache_build_rate`.

Each pattern repeats a short sequence `REPEAT` times (REPEAT=**400**).

| Name | Sequence × REPEAT |
|------|----------------|
| `write_heavy` | 4 UPDATEs, then 1 COUNT |
| `read_heavy` | 1 UPDATE, then 5 COUNTs |
| `balanced` | 2 UPDATEs, then 2 COUNTs |
| `write_then_read` | First half `write_heavy`, then `read_heavy` |

**Criterion** Pass if **each** of the four lines has `miss_rate < 0.20` and `cache_build_rate < 0.40`.


### 5.1 Expected results
Expected metrics for the hinted strategy (a few warmup misses are normal):

| Name | miss_rate | cache_build_rate |
|------|-----------|------------------|
| `write_heavy` | ~0.00 | < 0.20 |
| `read_heavy` | ~0.00 | < 0.20 |
| `balanced` | ~0.00 | < 0.30 |
| `write_then_read` | ~0.00 | < 0.20 |

Strategy 1 (Starter code)
+ Invalidate on every UPDATE, rebuild only on COUNT miss.

| Name | miss_rate | cache_build_rate |
|------|-----------|------------------|
| `write_heavy` | 1.00 | 0.20 |
| `read_heavy` | 0.20 | 0.17 |
| `balanced` | 0.50 | 0.25 |
| `write_then_read` | 0.33 | 0.18 |

Strategy 2 (rebuild on every UPDATE)
+ Rebuild the cache on every UPDATE.

| Name | miss_rate | cache_build_rate |
|------|-----------|------------------|
| `write_heavy` | 0.00 | 0.80 |
| `read_heavy` | 0.00 | 0.17 |
| `balanced` | 0.00 | 0.50 |
| `write_then_read` | 0.00 | 0.45 |

## 6. Ports

| Service | Bind | URL |
|---------|------|-----|
| Frontend | `127.0.0.1:5500` | http://127.0.0.1:5500/ |
| REST | `127.0.0.1:8000` | http://127.0.0.1:8000 |

## 7. File structure

```
Lab5/
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── serve.py            # static server on :5500
│   └── workload_test.py    # four REST mix patterns + metrics
├── backend/
│   ├── data_logic.py       # disk layer (provided)
│   ├── wordcount_cache.py  # COUNT fallback cache (provided)  
│   └── rest_service.py     # REST on :8000 — fill in the two TODOs
├── data/
└── requirements.txt
```
