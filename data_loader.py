import pandas as pd
from pathlib import Path
def load_data():
    file_name = r"C:\Users\Admin\Downloads\edmitted\Most-Recent-Cohorts-All-Data-Elements.csv"

    path = Path(file_name)

    if not path.exists():
        raise FileNotFoundError("CSV file not found")

    df = pd.read_csv(path, low_memory=False)

    return df

def get_data():
    return load_data()