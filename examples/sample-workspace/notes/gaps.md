# Gaps

Identified gaps in the research and follow-up questions to investigate.

## Open Questions

- **CPU-bound work comparison**: How does asyncio compare to multiprocessing (not threading) for CPU-bound work? Current research focuses on I/O-bound comparisons; multiprocessing for CPU-bound tasks deserves its own review.
- **Real-world benchmarks**: The findings cite qualitative comparisons but lack controlled benchmark numbers. A reproducible benchmark comparing asyncio vs threading on a real workload (e.g., 10k concurrent HTTP requests) would strengthen the conclusions.
- **Library coverage gaps**: Some legacy libraries (e.g., older database drivers) do not have async equivalents. How much does library ecosystem coverage limit asyncio adoption in practice?
- **Debugging and observability**: How does debugging asyncio code compare to threading? Are there well-trodden tools for async-aware tracing and profiling?

## Suggested Next Searches

- "asyncio vs multiprocessing benchmark Python"
- "asyncio debugging py-spy aiomonitor"
- "Python async library coverage 2024"
- "asyncio production case studies Reddit HN"
