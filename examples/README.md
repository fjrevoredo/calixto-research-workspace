# Examples

`examples/sample-workspace/` is reference research data for the asyncio sample
question.

It is useful for:

- inspecting the traceability chain
- reading a populated `config.json`
- reviewing example findings, insights, and report output
- testing toolkit-side audit commands against known data

## Audit The Sample

From the toolkit root:

```bash
uv run python scripts/workspace_info.py audit sample-workspace --path examples
```

## Relationship To Standalone Workspaces

New research sessions should be created with:

```bash
uv run python scripts/init_workspace.py <name>
```

That generates a standalone runtime snapshot under `workspaces/<name>/`.

The committed sample focuses on example research state. The standalone runtime
boundary itself is validated by the runtime manifest and the workspace
initialization tests.

## Sample Question

> What are the trade-offs of Python's asyncio for I/O-bound workloads compared
> to threading and multiprocessing?
