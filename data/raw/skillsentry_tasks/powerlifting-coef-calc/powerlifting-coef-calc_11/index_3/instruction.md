Preserve the existing formatting and sheet structure unless instructed otherwise. The following task involves working with an Excel workbook, and you should use the xlsx skill's recommended toolchain (openpyxl / pandas + recalc.py) to complete the required steps.

You need to calculate the lifting scores for International Powerlifting Federation competitions in the file `/root/data/openipf.xlsx`.
The workbook contains two sheets: "Data", which contains all performance records of lifters, and "Wilks", which is empty for you to work on. The entries for "Data" are documented in `/root/data/data-readme.md`.

**Variant: Wilks coefficient (male and female)**

You need to calculate the [Wilks](https://en.wikipedia.org/wiki/Wilks_coefficient) coefficients for each competitor.

The Wilks formula:
- For males:   Wilks = Total × 500 / (A₀ + A₁×BW + A₂×BW² + A₃×BW³ + A₄×BW⁴ + A₅×BW⁵)
  - Coefficients: a=-216.0475144, b=16.2606339, c=-0.002388645, d=-0.00113732, e=7.01863e-6, f=-1.291e-8
- For females: same formula with: a=594.31747775582, b=-27.23842536447, c=0.82112226871, d=-0.00930733913, e=4.731582e-5, f=-9.054e-8
- Bodyweight clamped: Males [40, 200.95], Females [26.51, 154.53]

Please keep 3 digits precision for all computation.

Proceed as follows. First, find which columns are needed to compute Wilks, copy these columns to "Wilks" with the lifters' name, and keep the order and names of the columns the same in "Wilks" as in "Data". Then, with the data you have in "Wilks", append a new column "TotalKg" after the existing columns, using Excel formula to compute each lifter's total lifted weights in Kg. Finally, with the data you have and added in "Wilks", append a new column "Wilks" after "TotalKg", using Excel formula to compute each lifter's Wilks coefficients.
