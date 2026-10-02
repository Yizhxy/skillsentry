This task calls for constructing a self-contained data-visualisation web application with D3.js v6. All output files (HTML, JS, CSS, data) have to be stored under /root/output/. Adhere to the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Please employ D3.js (v6) to visualize input data located at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Deliver output as `/root/output/index.html`. Produce:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

**Core requirements (required for all variants):**
- A bubble chart where each bubble corresponds to one stock:
   1. Scaled by market capitalization (ETFs given a uniform size)
   2. Colored by sector; placed by D3 force simulation with forceX/forceY grouping per sector
   3. forceCollide to avoid overlap
   4. Each bubble tagged with ticker symbol inside
   5. Hover tooltip displaying ticker, name, sector (no tooltip for ETFs)
   6. Legend as a `<div>` element
- A data table showing all 50 stocks: "Ticker symbol", "Full company name", "Sector", "Market cap" (formatted, e.g. "1.64T")
- Two-way linking: click a bubble → highlight table row; click a table row → highlight bubble
- `** All SVG <circle> elements must represent individual stock bubbles only. **`
- `** Legend must be implemented as a div element. **`

**Extra chart (stacked beneath the bubble chart):**
A **treemap** with two levels: Sector → Company:
- Top-level rectangles = sectors (scaled by total sector market cap)
- Sub-rectangles = individual companies (scaled by market cap)
- Each company tagged with ticker; colored by sector
- Hover tooltip displaying company name and market cap
- Clicking a company in the treemap highlights its matching bubble and table row
