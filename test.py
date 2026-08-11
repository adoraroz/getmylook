import pandas as pd
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://docs.google.com/spreadsheets/d/14KWYBgvA3kP2CKw5MQxCsDA-QQY0oQoJdz289ESo7p8/export?format=csv&gid=0"

try:
    df = pd.read_csv(url)
    print("Success! DataFrame Shape:", df.shape)
    print("Columns found:", df.columns.tolist())
    print(df.head())
except Exception as e:
    print("Pandas failed to read the CSV:")
    print(e)