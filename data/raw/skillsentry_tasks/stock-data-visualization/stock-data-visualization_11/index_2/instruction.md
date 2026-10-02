Build a self-contained data-visualisation web application using D3.js v6. Place all output files (HTML, JS, CSS, data) under /root/output/. Follow the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Use D3.js (v6) to visualize input data at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Output: `/root/output/index.html`. Also generate:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

**Base requirements (mandatory for all variants):**
- Bubble chart, one bubble per stock:
   1. Size by market capitalization (ETFs sized uniformly)
   2. Color by sector; position via D3 force simulation with forceX/forceY clustering per sector
   3. Use forceCollide to prevent overlap
   4. Label each bubble with ticker symbol inside
   5. Add hover tooltip with ticker, name, sector (no tooltip for ETFs)
   6. Render legend as a `<div>` element
- Data table of all 50 stocks: "Ticker symbol", "Full company name", "Sector", "Market cap" (formatted, e.g. "1.64T")
- Link bidirectionally: click a bubble → highlight table row; click a table row → highlight bubble
- `** All SVG <circle> elements must represent individual stock bubbles only. **`
- `** Legend must be implemented as a div element. **`

**Additional chart (arranged side by side with the bubble chart):**
Add a **vertical bar chart** of market capitalization per stock:
- Bar height = market cap (ETFs get a uniform small bar)
- Color bars by sector, same color scheme as the bubble chart
- X-axis: ticker symbols; Y-axis: market cap
- Show hover tooltip on bars with the same info as bubble tooltips

Link all three views (bubble chart, bar chart, table): clicking any element highlights the corresponding elements in all other views.
