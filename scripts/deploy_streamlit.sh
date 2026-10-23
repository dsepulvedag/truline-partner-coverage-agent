#!/usr/bin/env bash
# Upload the workbench files to the stage and (re)create the Streamlit app. Usage: scripts/deploy_streamlit.sh [connection]
set -euo pipefail
CONN="${1:-work_intel}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGE="@TRULINE.APP.STREAMLIT_STAGE/workbench"
snow sql -c "$CONN" -q "CREATE STAGE IF NOT EXISTS TRULINE.APP.STREAMLIT_STAGE DIRECTORY = (ENABLE = TRUE)" >/dev/null
cd "$ROOT/streamlit"
for f in streamlit_app.py common.py requirements.txt views/*.py .streamlit/config.toml; do
  dir="$(dirname "$f")"; [ "$dir" = "." ] && dir="" || dir="/$dir"
  snow sql -c "$CONN" -q "PUT 'file://$PWD/$f' '$STAGE$dir' AUTO_COMPRESS = FALSE OVERWRITE = TRUE" >/dev/null
  echo "uploaded $f"
done
snow sql -c "$CONN" -f "$ROOT/sql/60_streamlit.sql"
