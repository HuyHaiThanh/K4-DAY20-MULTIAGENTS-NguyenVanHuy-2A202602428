---
name: log-file-parsing-and-aggregation
description: Use this skill when extracting structured error information from raw log files, including filtering by severity, normalizing timestamps, and aggregating repeated messages.
---
- Extract log entries with specified severity levels (e.g., ERROR, CRITICAL).
- Convert timestamps to a uniform UTC format.
- Parse service names and normalize them according to naming conventions.
- Aggregate repeated log messages by summing repeat counts.
- Extract exception details from tracebacks when present.
- Sort and output structured log data following organization conventions.
