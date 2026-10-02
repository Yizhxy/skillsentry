Statistical analysis task on a two-sheet Excel workbook. Use the xlsx workflow (openpyxl + recalc.py) to write formulas and recalculate results; see the skill documentation for the correct toolchain and formula patterns.

Work with protein expression data from cancer cell line experiments. Open `protein_expression.xlsx`, which has two sheets: "Task" (your workspace) and "Data" (the raw expression values).

## Background

Quantitative proteomics data from cancer cell lines compares control vs treated conditions. Find which proteins show significant differences between the two groups.

## Steps

### 1. Extract expression data

The Data sheet holds expression values for 200 proteins across 50 samples. Look up the expression values of the 10 target proteins in column A (rows 11-20) for the 10 samples in row 10, and put them in cells C11:L20 on the Task sheet.

Match on both protein ID and sample name. INDEX-MATCH works well for this two-way lookup; VLOOKUP or other approaches are fine too.

### 2. Compute group statistics

Row 9 marks samples as "Control" vs "Treated" (highlighted in blue). For each protein, compute:
- Mean and standard deviation for control samples
- Mean and standard deviation for treated samples

The data is already log2-transformed; use regular mean and stdev.

Write results to the yellow cells, rows 24-27, columns B-K.

### 3. Compute fold change

For each protein (data is already log2-transformed), compute:
- Log2 Fold Change = Treated Mean - Control Mean
- Fold Change = 2^(Log2 Fold Change)

Fill columns C and D, rows 32-41 (yellow cells).

## Constraints

- Keep the file format, colors, and fonts unchanged
- No macros or VBA code
- Use formulas, not hard-coded numbers
- Note: sample names in the Data sheet have prefixes like "MDAMB468_BREAST_TenPx01"
