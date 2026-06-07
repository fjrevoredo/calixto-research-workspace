# Report: Python asyncio for I/O-Bound Workloads

## Summary

Python's asyncio provides an efficient, single-threaded concurrency model ideal for I/O-bound workloads. Compared to threading, it offers lower per-task overhead and fewer race conditions, at the cost of requiring async-native libraries throughout the stack [src_002, src_003, src_004]. For CPU-bound work, asyncio is not a substitute for multiprocessing because of the Global Interpreter Lock [src_003].

## Background

Python's asyncio library was added to the standard library in 3.4 (PEP 3156) and gained the now-ubiquitous `async`/`await` syntax in 3.5 [src_001, src_002]. It provides infrastructure for writing single-threaded concurrent code using coroutines, with the event loop as its central scheduler.

The motivation for asyncio was twofold:

1. **Threading is hard.** Threaded code is prone to race conditions, deadlocks, and the need for explicit locks. asyncio's cooperative scheduling sidesteps most of these issues.
2. **The GIL limits threading for CPU-bound work.** Python's Global Interpreter Lock prevents multi-threaded CPU parallelism. asyncio does not bypass the GIL; it sidesteps the need for threads entirely on a single core [src_003].

## Methods

### asyncio: single-threaded, cooperative

asyncio runs all coroutines on a single OS thread under the control of an event loop [src_002]. A coroutine only yields control when it explicitly `await`s something (typically I/O). This is the key difference from threading: there is no preemption, no race conditions on shared state.

Memory overhead is also lower: each coroutine is on the order of a few kilobytes, versus a megabyte or more per thread [src_004]. This makes it practical to have tens of thousands of concurrent operations on a single thread.

### Threading: pre-emptive, multi-threaded

Threading uses multiple OS threads, each running Python bytecode in turn. Threads are pre-emptively scheduled, which means shared state can be modified at any time, requiring locks to stay safe. Combined with the GIL, threading is most useful for I/O-bound work where threads spend most of their time waiting (where the GIL is released) and less useful for CPU-bound work [src_003].

### Multiprocessing: separate processes

Multiprocessing sidesteps the GIL by using separate OS processes, each with its own interpreter. This is the right tool for CPU-bound work but has higher overhead per task than asyncio or threading.

## Comparison

| Dimension | asyncio | Threading | Multiprocessing |
|---|---|---|---|
| Execution model | Single thread, cooperative | Multi-thread, pre-emptive | Multi-process |
| Per-task overhead | Kilobytes | Megabytes | Tens of megabytes |
| Race conditions | None (cooperative) | Common | Common |
| CPU-bound work | No (GIL) | No (GIL) | Yes |
| I/O-bound work | Excellent | Good | Good |
| Ecosystem maturity | Strong (aiohttp, asyncpg, etc.) | Mature | Mature |

For typical I/O-bound workloads (web requests, database queries, file I/O), asyncio scales better than threading because of the lower per-task overhead and the absence of contention on shared state [src_002, src_004, src_005].

## Common Pitfalls

The most common asyncio mistake is calling blocking I/O inside a coroutine, which stalls the event loop until the call returns [src_005]. The fix is either:

1. Use an async-native library (e.g., `aiohttp` instead of `requests`).
2. Push the blocking call to a thread pool via `loop.run_in_executor()`.
3. Wrap with `asyncio.to_thread()` (Python 3.9+).

Python 3.11's `asyncio.TaskGroup` provides structured concurrency that simplifies error handling: if one task in the group fails, the others are cancelled automatically [src_003]. This eliminates much of the boilerplate of older "gather and check exceptions" patterns.

## Recommendations

- **New I/O-bound services**: prefer asyncio with async-native libraries.
- **Legacy code with blocking libraries**: threading is a pragmatic bridge; consider asyncio + `run_in_executor` as an incremental migration path.
- **CPU-bound work**: use multiprocessing; asyncio will not help and may hurt by making the code more complex.
- **Mixed workloads**: consider a hybrid: an asyncio event loop orchestrating CPU-bound work in a process pool.

## Limitations

This review focuses on qualitative trade-offs drawn from documentation and practitioner experience. We did not run controlled benchmarks, and our source set is small (5 web sources, 3 arXiv papers) and English-only. For production decisions, a benchmark on your actual workload is recommended. See `notes/gaps.md` for follow-up questions.

## References

See [`bibliography.md`](./bibliography.md) for the full source list with quality ratings.
