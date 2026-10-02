This task involves an Excel workbook. Use the xlsx skill's recommended toolchain (openpyxl / pandas + recalc.py) for the required steps. Preserve the existing formatting and sheet structure unless instructed otherwise.

Calculate the lifting scores for International Powerlifting Federation competitions in the file `/root/data/openipf.xlsx`.
The workbook has two sheets:
1. "Data": all performance records of lifters,
2. "Dots": empty, for you to work on.
The entries for "Data" are documented in `/root/data/data-readme.md`.

**Variant: only Raw (no equipment) lifters - Dots coefficient**

Filter the data to include only Raw equipment lifters (Equipment == 'Raw') before copying to the Dots sheet.

Keep 3 digits precision for all computation.

Step 1: Find the columns needed to compute Dots.
Copy them to "Dots" with the lifters' name.
Keep column order and names in "Dots" the same as in "Data".

Step 2: Using the data in "Dots",
append a new column "TotalKg" after the existing columns,
with an Excel formula computing each lifter's total lifted weights in Kg.

Step 3: Using the data in "Dots" (existing and added),
append a new column "Dots" after "TotalKg",
with an Excel formula computing each lifter's Dots coefficients.
