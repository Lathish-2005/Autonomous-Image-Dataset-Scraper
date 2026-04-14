import pandas as pd
import requests

df = pd.read_excel(r'input/URL FOR CAR MAKES AND THEIR MODELS.xlsx', sheet_name='Full URL Analysis', header=0)
tier1 = df[(df['URL Status'] == 'VALID') & (df['Source Tier'] == 'Tier 1')].head(20)

for _, row in tier1.iterrows():
    make = row['Car Make']
    model = row['Car Model']
    url = row['Corrected / Recommended URL']
    if 'acuranews.com' not in url and 'netcarshow.com' not in url:
        print(f"{make} | {model} | {url}")
