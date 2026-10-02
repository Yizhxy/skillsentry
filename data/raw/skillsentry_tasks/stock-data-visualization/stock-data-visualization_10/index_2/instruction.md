Build a self-contained data-visualisation web application using D3.js v6. Place all output files (HTML, JS, CSS, data) under /root/output/. Follow the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Use D3.js (v6) to visualize input data at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/` for company stock details and individual stock price histories.
Return the output as a single-page web app at `/root/output/index.html`, openable in a web browser.
Generate these supporting files:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

Show two charts side by side horizontally:
- A bubble chart, one bubble per stock:
   1. Size bubbles by market capitalization (larger bubble for larger market cap). ETFs don't have market cap data, so size them uniformly
   2. Color bubbles by sector and position them with D3.js force simulation for clusters by sector: use forceX/forceY so bubbles of the same sector are close together in the same cluster. Add legends showing the sector name of each color.
   3. Keep each sector's clusters close together and reasonably centered in the chart (not scattered far away).
   4. Use forceCollide so bubbles don't overlap.
   5. Label each bubble with its ticker symbol inside
   6. On hover, show a tooltip with the bubble's ticker, name, and sector. (Note: ETF entries have no marketCap, country, or website data, so do not show tooltip for them)
- A data table next to the bubble chart listing all 50 stocks with columns "Ticker symbol", "Full company name", "Sector", and "Market cap" (formatted as an easy-to-read number e.g., "1.64T")
- Link the bubble chart and table: clicking a bubble highlights its row in the table at the same time, and vice versa.
- ** All SVG <circle> elements must represent individual stock bubbles only. No auxiliary or decorative SVG circles are allowed. **
- ** Include a legend for the bubble chart, implemented as a div element.**
- Display all text in full without truncation.
