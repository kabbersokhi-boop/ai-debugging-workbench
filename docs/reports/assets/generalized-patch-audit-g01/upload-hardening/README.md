# Exact-byte patch upload check

Tested implementation: `1747a58d5f8ceaef204381efd39d18d4fbd801a0`.
The source change after `fd043ce...` only preserves a UTF-8 BOM in uploaded patch text,
allowing strict admission to reject it instead of silently accepting rewritten bytes.
Backend/source-admission/execution modules and runtime images are unchanged.

`check.log`: 207 offline tests passed, plus lint/format/types/frontend build.
`browser.log`: exact uploaded BOM text was retained; delayed runtime discovery kept plan
preparation disabled; the normal candidate then executed, downloaded and reopened successfully.
`preservation.json`: actual API/broker/backend/frontend bytes match this implementation and
all 1,153 protected historical files remain unchanged.

The full regression run for this implementation is GitHub Actions run 39320478263. The final
PR-head check additionally covers the report/evidence-only commit. Real upstream execution
reports remain in `../final/`; their exact final execution engine is unchanged.
