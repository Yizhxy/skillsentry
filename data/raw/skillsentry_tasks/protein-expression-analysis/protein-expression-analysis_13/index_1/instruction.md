This statistical analysis task relies on an Excel workbook containing two sheets. Apply the xlsx workflow (openpyxl + recalc.py) to enter formulas and recompute results. The skill documentation offers direction on the proper toolchain and formula patterns.

You'll be handling protein expression data from cancer cell line experiments. Open `protein_expression.xlsx` - it contains two sheets: "Task" is where you'll carry out your work, and "Data" holds the raw expression values.

## What is this about?

We have quantitative proteomics data from cancer cell lines contrasting control vs treated conditions. Your task is to determine which proteins show significant differences between the two groups.

## Procedure

### 1. Retrieve the expression data

The Data sheet contains expression values for 200 proteins across 50 samples. For the 10 target proteins in column A (rows 21-30), retrieve their expression values for the 10 samples in row 10. Place these in the corresponding cells on the Task sheet.

You'll have to match on both protein ID and sample name. INDEX-MATCH suits this kind of two-way lookup well, though VLOOKUP or other methods are acceptable too.
### 2. Work out group statistics

Row 9 indicates which samples are "Control" vs "Treated" (highlighted in blue). For each protein, work out:
- Mean and standard deviation for control samples
- Mean and standard deviation for treated samples

### 3. Significance testing

For each protein, perform a **two-sample t-test** contrasting Control vs Treated expression.
- Place the t-statistic in column M (row 11-20 of Task sheet)
- Place the p-value in column N
- Label "Significant" in column O if p-value < 0.01, otherwise "Not Significant"

### 4. Recap

At the bottom of your analysis section, include:
- Total count of significant proteins found
- List of significant protein IDs

The aim is to find proteins whose expression is significantly changed by treatment.
