Use D3.js (v6) to visualize input data stored at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Return output as `/root/output/index.html`. Generate:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

**Base requirements (mandatory for all variants):**
- A bubble chart where each bubble maps to one stock:
   1. Sized by market capitalization (ETFs sized uniformly)
   2. Colored by sector; positioned by D3 force simulation with forceX/forceY clustering per sector
   3. ForceCollide to prevent overlap
   4. Each bubble labeled with ticker symbol inside
   5. Hover tooltip with ticker, name, sector (no tooltip for ETFs)
   6. Legend as a `<div>` element
- A data table listing all 50 stocks: "Ticker symbol", "Full company name", "Sector", "Market cap" (formatted, e.g. "1.64T")
- Bidirectional linking: click a bubble → highlight table row; click a table row → highlight bubble
- `** All SVG <circle> elements must represent individual stock bubbles only. **`
- `** Legend must be implemented as a div element. **`

**Additional chart (stacked below the bubble chart):**
A **scatter plot** where each point represents one stock:
- X-axis: latest closing price from `/root/data/indiv-stock/` CSVs
- Y-axis: market capitalization
- Points colored by sector (same scheme as bubble chart)
- Hover tooltip showing ticker, name, price, market cap

Clicking a scatter plot point also highlights the corresponding bubble and table row (three-way linking).