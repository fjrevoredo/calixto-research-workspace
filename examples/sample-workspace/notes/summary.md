# Summary

Synthesized insights with insight IDs. Each insight MUST reference at least one finding ID.

## ins_001
**Based on:** fnd_001, fnd_002, fnd_005
**Insight:** Python's asyncio is a single-threaded, cooperatively-scheduled concurrency model that uses the async/await syntax introduced in Python 3.5 and added to the standard library in 3.4 [fnd_001, fnd_002]. Because scheduling is cooperative, a coroutine only yields control at explicit await points, which eliminates many race conditions inherent to threaded code [fnd_005].

## ins_002
**Based on:** fnd_003, fnd_004
**Insight:** The combination of the GIL and the single-threaded event loop means asyncio is not a substitute for multiprocessing on CPU-bound work [fnd_004]. It is, however, much more efficient than threading for I/O-bound workloads because each coroutine uses ~kilobytes of memory versus ~megabytes for a thread [fnd_003].

## ins_003
**Based on:** fnd_006, fnd_009
**Insight:** Asyncio's strength is its growing ecosystem of async-native libraries: aiohttp, asyncpg, motor, aioredis [fnd_009]. For I/O-bound workloads that have async library support, asyncio scales to tens of thousands of concurrent operations on a single thread [fnd_006].

## ins_004
**Based on:** fnd_007, fnd_010
**Insight:** The biggest practical pitfall is calling blocking I/O inside a coroutine, which stalls the event loop [fnd_007]. Modern Python (3.11+) mitigates this with structured concurrency via asyncio.TaskGroup, which makes error handling across concurrent tasks much cleaner [fnd_010].

## ins_005
**Based on:** fnd_006, fnd_008
**Insight:** For I/O-bound workloads, asyncio generally outperforms threading due to lower per-task overhead and the absence of thread-safety complexity [fnd_006]. Tools like asyncio.gather() and asyncio.create_task() make it ergonomic to express "run all of these concurrently and aggregate" [fnd_008].
