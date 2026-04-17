#!/bin/bash
set -euo pipefail

# Export the Marimo app as a static WASM site for GitHub Pages.
# The exported HTML runs Python in the browser via Pyodide — no server needed.
#
# Usage:
#   ./scripts/export_wasm.sh
#
# Prerequisites:
#   - pip install marimo
#   - data/results.db must exist (run the CLI first)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$ROOT_DIR/data/results.db" ]; then
    echo "Error: data/results.db not found."
    echo "Run the CLI first to populate it:"
    echo "  python -m eth_tracestat.cli --rpc <url> --start <block> --count 10 --results-db data/results.db"
    exit 1
fi

cd "$ROOT_DIR"

echo "Pre-computing views..."
python3 scripts/precompute.py

echo "Embedding data into app for WASM export..."
# Read the JSON data and inject it into a copy of app.py
DATA_JSON=$(cat docs/data.json)
cp app.py app_wasm.py
# Replace the placeholder line with the actual data
python3 -c "
import sys
with open('app_wasm.py', 'r') as f:
    content = f.read()
with open('docs/data.json', 'r') as f:
    data = f.read()
content = content.replace(
    '    _embedded = None  # STATIC_DATA_EMBED',
    '    _embedded = ' + data + '  # STATIC_DATA_EMBED',
)
with open('app_wasm.py', 'w') as f:
    f.write(content)
"

echo "Exporting Marimo app to WASM..."
marimo export html-wasm app_wasm.py -o docs/index.html --mode run --no-sandbox
rm app_wasm.py

echo "Patching HTML metadata..."
sed -i '' 's|<title>app wasm</title>|<title>eth-tracestat</title>|' docs/index.html
sed -i '' 's|<meta name="description" content="a marimo app" />|<meta name="description" content="Ethereum storage slot and account access pattern analysis" />|' docs/index.html

echo "Compressing results.db for download..."
sqlite3 data/results.db ".backup /tmp/results_clean.db"
gzip -c /tmp/results_clean.db > data/results.db.gz
rm /tmp/results_clean.db
echo "  data/results.db.gz ($(du -h data/results.db.gz | cut -f1))"

echo ""
echo "Exported to docs/index.html"
echo ""
echo "To deploy:"
echo "  1. git add docs/ && git commit -m 'update github pages'"
echo "  2. Push to GitHub"
echo "  3. Enable Pages from Settings > Pages > Source: Deploy from branch > /docs"
