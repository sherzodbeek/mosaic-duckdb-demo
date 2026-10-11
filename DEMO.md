# Demo guide

Step-by-step commands for the live demo. Each step lists the command, what it does,
and the output you should see. Do steps 0–3 **before** the presentation; steps 4–5 are
the live part.

You need **two terminal windows**, because both demos run a web server that keeps the
terminal busy until you stop it with `Ctrl+C`.

---

## Step 0 — One-time setup

Run these once, in a terminal:

```bash
# Go to the project folder (the quotes are needed because the path has spaces)
cd "/Users/sherzod/study/2026 Fall/CSE 578 Data Visualization/cse578-mosaic"

# Create a private Python environment in .venv/ (skip if .venv/ already exists)
python3 -m venv .venv

# Turn the environment on — your prompt now starts with (.venv)
source .venv/bin/activate

# Install DuckDB, Mosaic vgplot, Embedding Atlas, UMAP, etc.
pip install -r requirements.txt

# Check the Embedding Atlas command is available — prints a version number
embedding-atlas --version
```

> **Every new terminal window** needs the `cd …` and `source .venv/bin/activate` lines again.
> If you see `command not found` or `ModuleNotFoundError`, you forgot to activate.

---

## Step 1 — Generate the data

```bash
python generate_synthetic_olist.py --orders 100000
```

**What it does:** writes six CSV files to `data/synthetic/` with the same file names and
columns as the real Kaggle Olist dataset: orders, order items, customers, products,
category names and reviews. Review comments are in English. Late deliveries get worse
scores and complaints about delivery, as in the real data.

**Expected output** (about 2 seconds):

```
wrote 100,000 orders / 113,918 items to data/synthetic
```

| Option | Meaning |
|---|---|
| `--orders 100000` | Number of orders to create. Use `1000000` for a stress test. |
| `--out data/synthetic` | Output folder (this is the default). |
| `--seed 578` | Random seed. Same seed gives the same data every time. |

---

## Step 2 — Join the CSVs into Parquet files with DuckDB

```bash
python prepare_data.py --src data/synthetic
```

**What it does:** DuckDB reads the six CSVs, joins them with SQL and writes two compact
Parquet files that the demos load:

- `web/orders.parquet` — one row per delivered order item (used by the dashboard)
- `web/reviews.parquet` — one row per order with a written review (used by Embedding Atlas)

**Expected output** (under 1 second):

```
orders.parquet: 110,464 rows | reviews.parquet: 39,136 rows | 0.3s in DuckDB
```

> To use the real Kaggle data instead, download it and pass its folder:
> `python prepare_data.py --src ~/Downloads/olist`. The real comments are in Portuguese.

---

## Step 3 — Export the dashboard and build the review map

```bash
python dashboard.py
```

**What it does:** runs the Python vgplot code in `dashboard.py` and saves the chart
specification to `web/dashboard.json`. The browser page reads this file.

**Expected output:**

```
wrote …/cse578-mosaic/web/dashboard.json (5 rows, data: ['orders'])
```

```bash
python reviews_atlas.py --no-launch
```

**What it does:** turns each review into numbers (TF-IDF → SVD), places similar reviews
close together on a 2-D map (UMAP), and saves the result to `web/reviews_xy.parquet`.
`--no-launch` builds the file without opening the UI.

**Expected output** (about 15 seconds; the UMAP `UserWarning` about `n_jobs` is harmless):

```
wrote …/cse578-mosaic/web/reviews_xy.parquet (30,000 reviews)
```

---

## Step 4 — Live demo A: crossfilter dashboard

**Terminal 1:**

```bash
python -m http.server 8000 --directory web
```

**What it does:** serves the `web/` folder at a local address. Leave it running.
The page must be opened through this server; double-clicking `index.html` will not work.

**Open:** <http://localhost:8000> (needs internet, because the page downloads Mosaic and
DuckDB-WASM from a CDN).

**What to show, in order:**

1. **Header stats:** rows in DuckDB (~110k) and bytes returned. The first load transfers
   only about 87 KB, because the browser gets aggregates, not rows.
2. **Live SQL log** (right side): each chart sent one `SELECT … GROUP BY` query. Expand an
   entry to show the full SQL.
3. **Drag** on the weekly timeline across **Nov 2017 – Mar 2018**. The log shows
   **pre-agg** entries: on the first brush, Mosaic builds small summary tables ("data cubes").
4. **Move the brush around.** The new entries are tagged **cube** and take a few ms each.
   These are lookups on the summary tables, not rescans of the full dataset.
5. **Click the 1★ bar** in *Review score*. The delay histogram shifts right and turns red,
   which shows that late deliveries drive bad reviews.
6. **Click RJ** in the states chart. Every other view updates again.
7. Shift-click selects several bars. Click a bar again to deselect it.
   **Reload the page** to reset everything.

**Stop the server:** press `Ctrl+C` in Terminal 1.

---

## Step 5 — Live demo B: review map in Embedding Atlas

**Terminal 2** (activate first: `cd …` and `source .venv/bin/activate`):

```bash
python reviews_atlas.py
```

**What it does:** rebuilds `web/reviews_xy.parquet` (about 15 seconds), then starts
Embedding Atlas on it. To skip the rebuild, start it directly with the file from step 3:

```bash
embedding-atlas web/reviews_xy.parquet --text review_text --x x --y y --neighbors neighbors
```

| Option | Meaning |
|---|---|
| `--text review_text` | Column shown when you hover or select a point |
| `--x x --y y` | Use the precomputed 2-D coordinates (no model download) |
| `--neighbors neighbors` | Precomputed "most similar reviews" for each point |
| `--port 5056` | Add this if port 5055 is already in use |

**Open:** <http://localhost:5055> in **Chrome or Edge**. The map needs WebGPU; in other
browsers only the side charts and table work.

**What to show, in order:**

1. **Hover over points.** Similar comments sit next to each other.
2. **Color the map by `late`.**
3. **Select review scores 1 and 2** in the side chart. Two separate low-score regions stand out:
   - a **delivery-complaint** region ("Product never arrived, tracking stuck for days") —
     mostly late orders;
   - a **product-complaint** region ("Product is broken, I want my money back") —
     mostly on-time orders.
4. **The point:** the same star rating hides two different business problems, a carrier
   problem and a seller/product problem.
5. **Lasso-select one region.** The side charts update. The map is just another Mosaic
   chart, the same architecture as demo A.

**Stop the server:** press `Ctrl+C` in Terminal 2.

---

## Q&A: Why Mosaic, not other tools?

**The point of the demo:** this is a teaching demo, not a pitch to replace other tools.
The course teaches *what* linked views and brushing are. This demo shows *how* a tool
keeps them fast on large data. The live SQL log shows each chart's query, the summary
tables being built, and how few bytes come back.

| Tool | What it's good at | Why it doesn't fit this demo |
|---|---|---|
| **matplotlib** | Static, publication-quality figures | It draws pictures, not interactive views. No brushing, no linked charts. |
| **Altair / Vega-Lite / Plotly** | Interactive charts from Python | They send raw rows to the browser. Altair refuses more than 5,000 rows by default. Linked brushing gets slow at hundreds of thousands of rows. |
| **Power BI / Tableau** | Business dashboards, sharing, refresh schedules, access control | They also push work into a query engine; Tableau has done "charts as queries" since the early 2000s. But they're closed, so you can't show or change how it works. They also need licenses to share, and Power BI Desktop is Windows-only. |
| **Mosaic + DuckDB** | Linked, interactive exploration of millions of rows, code-first | Open source, shows its SQL, and runs in a notebook or a static web page with no server. |

**If someone asks "Why not Power BI?":** agree that Power BI already uses the same idea.
Mosaic is an open, inspectable version of it. Then point to what Mosaic adds:

- **No server or license.** The whole database runs inside the browser tab, so you can
  share it as a plain web page.
- **It's code, not clicks.** The dashboard is a Python file you can version and rerun.
- **New chart types can join the linked views.** Embedding Atlas is built this way: its
  map is just another Mosaic chart, so it filters together with ordinary bar charts.
- **You can watch it work.** Every query is visible, which is the point of the demo.

**Use Mosaic + DuckDB when:**

- You have roughly 100k to tens of millions of rows and want to explore them with linked charts.
- You work in Python or Jupyter and want reproducible, code-based dashboards.
- You want to share a dashboard as a static web page with no backend.
- You need a custom view (like an embedding map) linked with standard charts.

**Use something else when:**

| Situation | Better choice |
|---|---|
| Business users need refresh schedules, access control, Microsoft 365 sharing | Power BI or Tableau |
| A figure for a paper or report | matplotlib |
| Data under about 50k rows | Altair or Plotly (simpler and fast enough) |
| Billions of rows | A warehouse or server-side DuckDB (the in-browser database runs out of memory) |
| Calculations that can't be written in SQL, like UMAP | Compute them in Python first, as this project does |

> **One line for the slide:** Power BI and Tableau hide this engine inside a product.
> Mosaic gives you the same engine as an open library, so you can see it, change it and
> add new chart types to it.

---

## Optional extras

**Same dashboard inside Jupyter** (DuckDB runs in the Python kernel, no browser database):

```bash
pip install jupyterlab        # one time; not in requirements.txt
jupyter lab
```

Then in a notebook cell:

```python
import os; os.chdir("web")            # the spec loads orders.parquet from web/
import sys; sys.path.insert(0, "..")  # so `dashboard.py` can be imported
from dashboard import view
view
```

**Stress test with ~1.1 million rows:** repeat steps 1–3 with a bigger dataset, then restart step 4:

```bash
python generate_synthetic_olist.py --orders 1000000
python prepare_data.py --src data/synthetic
python dashboard.py
```

To go back to the normal size, rerun steps 1–3 with `--orders 100000`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: embedding-atlas` or `ModuleNotFoundError` | Run `source .venv/bin/activate` in that terminal |
| `Address already in use` | A server from earlier is still running. Stop it with `Ctrl+C`, or find it with `lsof -i :8000` (or `:5055`) and `kill <PID>` |
| Dashboard shows "Failed to start" | Open <http://localhost:8000>, not the `index.html` file. Check the internet connection (CDN) |
| Dashboard shows old data after regenerating | Hard refresh with `Cmd+Shift+R` |
| Embedding map is blank, side charts work | The browser has no WebGPU. Use recent Chrome or Edge |

## Pre-demo checklist

- [ ] Steps 0–3 done and outputs match
- [ ] Internet connection works (dashboard loads from a CDN)
- [ ] Chrome or Edge open for the Embedding Atlas map
- [ ] Two terminals open, both in the project folder with `.venv` activated
- [ ] Test-run steps 4 and 5 once, then reload both pages to reset them
