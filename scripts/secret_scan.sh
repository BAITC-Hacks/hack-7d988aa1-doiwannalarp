#!/usr/bin/env bash
set -euo pipefail

PATTERNS=('sk-[A-Za-z0-9_-]{20,}' 'nvapi-[A-Za-z0-9_-]+' 'OPENAI_API_KEY=.+')

found=0

SELF="scripts/secret_scan.sh"

echo "Scanning tracked files..."
for pattern in "${PATTERNS[@]}"; do
    if git grep -nE "$pattern" -- . ':!*.lock' ":!$SELF" 2>/dev/null | grep -vE 'OPENAI_API_KEY=\s*$'; then
        found=1
    fi
done

echo "Scanning git history..."
for pattern in "${PATTERNS[@]}"; do
    if git log -p --all -- . ":!$SELF" 2>/dev/null | grep -E "$pattern" | grep -vE '^\+?OPENAI_API_KEY=\s*$'; then
        found=1
    fi
done

if [ "$found" -eq 1 ]; then
    echo "FAILED: potential secret(s) found"
    exit 1
fi

echo "OK: no secrets found"
exit 0
