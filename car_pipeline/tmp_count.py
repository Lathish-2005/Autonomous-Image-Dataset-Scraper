import pandas as pd
import os

filepath = r"c:\Users\kotla\Downloads\NEW AGENT\car_pipeline\input\Testing of Car models official urls 1.xlsx"

try:
    # Read all sheets from the Excel file
    xls = pd.ExcelFile(filepath)
    print(f"File: {os.path.basename(filepath)}")
    print(f"Sheets found: {len(xls.sheet_names)}")
    
    total_makes = set()
    total_models = 0
    
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(filepath, sheet_name=sheet_name)
        
        # Check if the right columns are present
        if 'Manufacturer' in df.columns and 'Model Name' in df.columns:
            # Drop empty rows
            df = df.dropna(subset=['Manufacturer', 'Model Name'])
            
            makes = df['Manufacturer'].unique().tolist()
            models = len(df['Model Name'].unique())
            
            total_makes.update(makes)
            total_models += models
            
            print(f"  Sheet '{sheet_name}': {len(makes)} makes, {models} models")
        else:
            print(f"  Sheet '{sheet_name}' is missing expected columns.")
            
    print("\n--- Summary ---")
    print(f"Total Unique Makes: {len(total_makes)}")
    print(f"Total Unique Models: {total_models}")
    print(f"Makes: {', '.join(sorted([str(m) for m in total_makes]))}")
    
except Exception as e:
    print(f"Error parsing Excel file: {e}")
