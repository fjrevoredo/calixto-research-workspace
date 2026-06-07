# Findings

Extracted facts with finding IDs. Each finding MUST reference at least one source ID.

## fnd_001
**Source:** src_001
**Fact:** Python's asyncio library was added to the standard library in version 3.4 (PEP 3156) and provides infrastructure for writing single-threaded concurrent code using coroutines.
**Quote:** "asyncio is a library to write concurrent code using the async/await syntax."
**Confidence:** high
**Source URL:** https://www.reddit.com/r/Python/comments/yqrr94/python_asyncio_the_complete_guide/

## fnd_002
**Source:** src_002
**Fact:** The async/await syntax was introduced in Python 3.5 as a clearer way to write coroutines, replacing the older @asyncio.coroutine and yield from syntax.
**Confidence:** high
**Source URL:** https://realpython.com/async-io-python/

## fnd_003
**Source:** src_002
**Fact:** asyncio uses an event loop that runs all coroutines on a single OS thread. This is the key difference from threading, which uses multiple OS threads.
**Confidence:** high
**Source URL:** https://realpython.com/async-io-python/

## fnd_004
**Source:** src_003
**Fact:** Python's Global Interpreter Lock (GIL) prevents multiple threads from executing Python bytecode in parallel, making threading less effective for CPU-bound work. asyncio does not bypass the GIL; it sidesteps the need for threads by being cooperatively scheduled.
**Confidence:** high
**Source URL:** https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html

## fnd_005
**Source:** src_002
**Fact:** asyncio coroutines are cooperatively scheduled: a coroutine only yields control when it explicitly awaits something (typically I/O). This avoids the race conditions common in threaded code.
**Confidence:** high
**Source URL:** https://realpython.com/async-io-python/

## fnd_006
**Source:** src_004
**Fact:** asyncio is well-suited for I/O-bound workloads such as network requests, database queries, and file I/O. Each coroutine is cheap (~kilobytes of memory) compared to threads (~megabytes).
**Confidence:** medium
**Source URL:** https://www.patricksoftwareblog.com/introduction_to_asyncio_in_python.html

## fnd_007
**Source:** src_005
**Fact:** A common anti-pattern is to call blocking I/O inside a coroutine, which stalls the entire event loop. The fix is to use run_in_executor to push blocking calls to a thread pool, or use async-native libraries.
**Confidence:** high
**Source URL:** https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-1.html

## fnd_008
**Source:** src_002
**Fact:** asyncio provides primitives like asyncio.gather() and asyncio.create_task() to run multiple coroutines concurrently and aggregate their results.
**Confidence:** high
**Source URL:** https://realpython.com/async-io-python/

## fnd_009
**Source:** src_001
**Fact:** The asyncio ecosystem has matured significantly: aiohttp for HTTP clients, asyncpg for PostgreSQL, motor for MongoDB, and aioredis for Redis are all stable and production-ready.
**Confidence:** medium
**Source URL:** https://www.reddit.com/r/Python/comments/yqrr94/python_asyncio_the_complete_guide/

## fnd_010
**Source:** src_003
**Fact:** Python 3.11+ introduced asyncio.TaskGroup, which provides structured concurrency: tasks are tracked as a group and exceptions in one task cancel the others, simplifying error handling.
**Confidence:** high
**Source URL:** https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html
