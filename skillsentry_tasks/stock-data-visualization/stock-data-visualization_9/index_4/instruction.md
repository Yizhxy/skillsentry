This task requires building a self-contained data-visualisation web application using D3.js v6. All output files (HTML, JS, CSS, data) must be placed under /root/output/. Follow the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Please use D3.js (v6) to visualize input data stored at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Please return the output as a single-page web app at `/root/output/index.html`.
Generate:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

This web-app should visualize the original **bubble chart + table** PLUS:
- A **"Download CSV" button** that exports the currently visible stock data (all 50 stocks) as a CSV file with columns: Ticker, Name, Sector, MarketCap
- The download should work client-side (using a data URL or Blob)
- All other requirements from the original task apply.
- ** All SVG <circle> elements must represent individual stock bubbles only. **
- ** Legend as a div element. **
