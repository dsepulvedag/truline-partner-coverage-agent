"""Run the Snowflake notebook cells from this machine with a named Snowflake CLI connection.

    uv run --python 3.11 --with "snowflake-snowpark-python[pandas]" --with numpy \
        python data_gen/run_snowflake.py work_intel 1000 [--real-names]

Executes notebook cells 1 (setup), 3 (generator), 4 (generate), 5 (checks), 6 (app views);
--real-names also runs 2a/2b first (otherwise cell 4 still uses REAL_COMPANIES_SEED if it exists).
"""
import json
import os
import sys

import snowflake.snowpark.context as ctx
from snowflake.snowpark import Session

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
conn, n_accounts = args[0], int(args[1])
role = args[2] if len(args) > 2 else None
real_names = "--real-names" in sys.argv   # also run 2a/2b (needs the PEOPLE_DATA_LABS listing)

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
for k in (["2a", "2b"] if real_names else []) + ["3", "4", "5", "6"]:
    print(f"\n##### cell {k}")
    exec(src[k], g)
