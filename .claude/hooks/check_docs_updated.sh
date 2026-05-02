#!/usr/bin/env bash
# Warn if backend/frontend source files changed but docs were not updated.
changed=$(git status --short 2>/dev/null | awk '{print $NF}')
code_changed=$(echo "$changed" | grep -cE '^(backend|frontend/src)/' || true)
docs_changed=$(echo "$changed" | grep -cE '^(docs/|CLAUDE\.md)' || true)

if [ "$code_changed" -gt 0 ] && [ "$docs_changed" -eq 0 ]; then
  echo '{"systemMessage": "DOCS NOT UPDATED: code changed but no docs/*.md or CLAUDE.md was updated — add a doc update to this PR."}'
fi
