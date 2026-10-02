import os
import numpy as np
import pandas as pd
from statsmodels.tsa.filters.hp_filter import hpfilter


def load_and_process():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_dir = os.path.join(base_dir, "environment")

    if os.path.exists(os.path.join(env_dir, "ERP-2025-table10.xls")):
        pce_path = os.path.join(env_dir, "ERP-2025-table10.xls")
        pfi_path = os.path.join(env_dir, "ERP-2025-table12.xls")
        cpi_path = os.path.join(env_dir, "CPI.xlsx")
    else:
        pce_path = "ERP-2025-table10.xls"
        pfi_path = "ERP-2025-table12.xls"
        cpi_path = "CPI.xlsx"

    df10 = pd.read_excel(pce_path, header=None)
    df12 = pd.read_excel(pfi_path, header=None)
    df_cpi = pd.read_excel(cpi_path)

    def clean_erp(df, col_name, start_year=1985, end_year=2024):
        start_idx = None
        for idx, row in df.iterrows():
            if str(row[0]).strip() == "1985.":
                start_idx = idx
                break

        if start_idx is None:
            raise ValueError(f"Could not find start year {start_year} in dataframe")

        data = []

        # 1. Parse Annuals (1985-2023)
        for _idx, row in df.iterrows():
            s = str(row[0]).strip()
            if s.endswith(".") and s[:-1].isdigit():
                y = int(s[:-1])
                if start_year <= y <= min(2024, 2023):
                    val = row[1]
                    data.append({"Year": y, col_name: val})

        # 2. Parse 2024 (Average of available quarters)
        vals_2024 = []
        found_2024 = False
        for _idx, row in df.iterrows():
            s = str(row[0]).strip()
            if "2024" in s and ":" in s:
                found_2024 = True
                vals_2024.append(row[1])
            elif found_2024:
                if s.startswith("II") or s.startswith("III") or s.startswith("IV"):
                    vals_2024.append(row[1])
                else:
                    break

        if vals_2024:
            q_clean = [pd.to_numeric(v, errors="coerce") for v in vals_2024]
            q_clean = [v for v in q_clean if not pd.isna(v)]
            if q_clean:
                avg_2024 = sum(q_clean) / len(q_clean)
                data.append({"Year": 2024, col_name: avg_2024})

        sub = pd.DataFrame(data)
        sub = sub[(sub["Year"] >= start_year) & (sub["Year"] <= end_year)]
        sub[col_name] = pd.to_numeric(sub[col_name], errors="coerce")
        return sub.reset_index(drop=True)

    df_pce = clean_erp(df10, "PCE")
    df_pfi = clean_erp(df12, "PFI")

    cpi_c1 = df_cpi.columns[0]
    cpi_c2 = df_cpi.columns[1]
    df_cpi = df_cpi[[cpi_c1, cpi_c2]].copy()
    df_cpi.columns = ["Year", "CPI"]
    df_cpi = df_cpi[(df_cpi["Year"] >= 1985) & (df_cpi["Year"] <= 2024)]

    df = df_pce.merge(df_pfi, on="Year").merge(df_cpi, on="Year")

    df["Real_PCE"] = df["PCE"] / df["CPI"]
    df["Real_PFI"] = df["PFI"] / df["CPI"]
    df["ln_Real_PCE"] = np.log(df["Real_PCE"])
    df["ln_Real_PFI"] = np.log(df["Real_PFI"])

    cycle_pce, _ = hpfilter(df["ln_Real_PCE"], lamb=100)
    cycle_pfi, _ = hpfilter(df["ln_Real_PFI"], lamb=100)

    corr = np.corrcoef(cycle_pce, cycle_pfi)[0, 1]
    return corr


if __name__ == "__main__":
    try:
        correlation = load_and_process()
        print(f"Calculated Correlation: {correlation:.5f}")

        output_path = "/root/answer.txt"
        if not os.path.exists("/root") and os.path.exists("."):
            output_path = "answer.txt"

        with open(output_path, "w") as f:
            f.write(f"{correlation:.5f}")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
