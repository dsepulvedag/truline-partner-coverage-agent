"""Run the Snowflake notebook cells from this machine with a named Snowflake CLI connection.

    uv run --python 3.11 --with "snowflake-snowpark-python[pandas]" --with numpy \
        python data_gen/run_snowflake.py work_intel 1000

Executes notebook cells 1 (setup), 3 (generator), 4 (generate), 5 (checks), 6 (app views);
the optional real-name cells 2a/2b are skipped (cell 4 still uses REAL_COMPANIES_SEED if it exists).
"""
import json
import os
import sys

import snowflake.snowpark.context as ctx
from snowflake.snowpark import Session

HERE = os.path.dirname(os.path.abspath(__file__))
conn, n_accounts = sys.argv[1], int(sys.argv[2])
role = sys.argv[3] if len(sys.argv) > 3 else None

cfg = {"connection_name": conn}
if role:
    cfg["role"] = role
session = Session.builder.configs(cfg).create()
session.query_tag = "truline_data_gen"
ctx.get_active_session = lambda: session

cells = [c for c in json.load(open(os.path.join(HERE, "truline_snowflake_notebook.ipynb")))["cells"]
         if c["cell_type"] == "code"]
src = {c["source"][0].split(")")[0].lstrip("# "): "".join(c["source"]) for c in cells}

g = {}
exec(src["1"], g)
g["N_ACCOUNTS"] = n_accounts
g["N_REAL"] = round(n_accounts * 5_000 / 300_000)
print(n_accounts, "accounts,", g["N_REAL"], "with real names")
for k in ["3", "4", "5", "6"]:
    print(f"\n##### cell {k}")
    exec(src[k], g)
