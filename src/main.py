"""
Dollar Debasement Dashboard
Author: ChatGPT (GPT-5 Thinking mini)

This script downloads US series (Big Mac proxy, US retail gasoline, CPI, median house price, gold)
and builds a simple dashboard of "real purchasing power" indicators: how many Big Macs, gallons of gas,
gold ounces, and median homes $100, $1,000 or $10,000 could buy over time.

Requirements:
- Python 3.8+
- pandas
- matplotlib
- requests

Notes:
- The Economist Big Mac index is not available via a free API; this script attempts to pull a usable
  Big Mac time series from a few public endpoints. If you have a CSV of Big Mac prices, point the
  BIG_MAC_CSV_PATH variable to it and the script will use that.
- The script uses FRED for CPI and Median Sales Price (MSPUS) and EIA for gasoline historical prices.
  You can register for a FRED API key and set FRED_API_KEY environment variable for more robust calls.

Outputs:
- ./outputs/ contains CSV snapshots and PNG charts.

Citations and sources embedded in code comments.
"""

import os
import io
import math
import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# ---------------------- User settings ----------------------
OUTPUT_DIR = 'outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# If you have a local Big Mac CSV, set this path (columns: date, price_usd)
BIG_MAC_CSV_PATH = 'data/big-mac-source-data-v2.csv'

# FRED and EIA endpoints (no API key required for simple CSV downloads from FRED via fred.stlouisfed.org if available)
FRED_BASE = 'https://fred.stlouisfed.org/graph/fredgraph.csv'
EIA_GAS_MONTHLY_URL = 'https://www.eia.gov/dnav/pet/hist_xls/RMG_NA_pct_2.xls'  # fallback - or use the web page

# Series to fetch (FRED series IDs)
SERIES = {
    'CPIAUCSL': 'CPI - All Urban Consumers (All Items) (monthly)',
    'MSPUS': 'Median Sales Price of Houses Sold for the United States (quarterly)',
    'CSUSHPINSA': 'S&P/Case-Shiller U.S. National Home Price Index (monthly, index)'
}

# Helper: download CSV from FRED (series as query param)
def fred_csv(series_id, start_date=None, end_date=None):
    params = {'id': series_id}
    if start_date: params['cosd'] = start_date
    if end_date: params['coed'] = end_date
    r = requests.get(FRED_BASE, params=params, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), parse_dates=['DATE']).rename(columns={'DATE':'date', series_id:'value'})

# ---------------------- Load / fetch data ----------------------
print('Loading local series...')
cpi_path = 'data/CPIAUCSL.csv'
try:
    cpi = pd.read_csv(cpi_path, parse_dates=['observation_date'])
    cpi = cpi.rename(columns={'observation_date': 'date', 'CPIAUCSL': 'value'})
    cpi.to_csv(os.path.join(OUTPUT_DIR,'cpi.csv'), index=False)
    print('CPI loaded from local:', cpi.shape)
except Exception as e:
    print('Failed to load local CPI:', e)
    cpi = None

# Median sales price (quarterly)
msp_path = 'data/MSPUS.csv'
try:
    msp = pd.read_csv(msp_path, parse_dates=['observation_date'])
    msp = msp.rename(columns={'observation_date': 'date', 'MSPUS': 'value'})
    msp.to_csv(os.path.join(OUTPUT_DIR,'median_sales_price.csv'), index=False)
    print('Median sales price loaded from local:', msp.shape)
except Exception as e:
    print('Failed to load local MSPUS:', e)
    msp = None

# Gasoline: fallback to EIA simple CSV if available, else parse manually
print('Loading gasoline data from local CSV...')
gasoline_path = 'data/Gas-Prices-Per-Gallon-All-Grades.csv'
try:
    gasoline = pd.read_csv(gasoline_path)
    gasoline['Date'] = pd.to_datetime(gasoline['Date'], format='%b-%Y')
    gasoline = gasoline.rename(columns={'Date': 'date', 'U.S. All Grades All Formulations Retail Gasoline Prices (Dollars per Gallon)': 'price'})
    gasoline = gasoline[['date', 'price']]
    gasoline.to_csv(os.path.join(OUTPUT_DIR,'gasoline.csv'), index=False)
    print('Gasoline series loaded:', gasoline.shape)
except Exception as e:
    print('Failed to load gasoline CSV:', e)
    gasoline = None

# Big Mac: prefer local CSV; otherwise use a recent single-point price as a placeholder and instruct user how to replace
# Load historical Big Mac data
historical_path = 'data/big-mac-historical-source-data.csv'
if os.path.exists(historical_path):
    historical = pd.read_csv(historical_path, parse_dates=['date'])
    historical = historical[historical['iso_a3'] == 'USA'][['date', 'local_price']].rename(columns={'local_price': 'price'})
    historical['date'] = historical['date'].dt.tz_localize(None)  # Make timezone-naive
else:
    historical = pd.DataFrame()

# Load current Big Mac data
current_path = 'data/big-mac-source-data-v2.csv'
if os.path.exists(current_path):
    current = pd.read_csv(current_path, parse_dates=['date'])
    current = current[current['iso_a3'] == 'USA'][['date', 'local_price']].rename(columns={'local_price': 'price'})
    current['date'] = current['date'].dt.tz_localize(None)  # Make timezone-naive
else:
    current = pd.DataFrame()

# Combine and sort
bigmac = pd.concat([historical, current]).drop_duplicates(subset=['date']).sort_values('date')
bigmac.to_csv(os.path.join(OUTPUT_DIR, 'bigmac_combined.csv'), index=False)
print('Combined Big Mac data created from historical and current sources.')

# ---------------------- Build dashboard series (real purchasing power measures) ----------------------
print('Building summary indicators...')
# Example: compute how many Big Macs per $100, how many gallons per $100, and median homes purchasable with $100,000
summary = {}
if bigmac is not None:
    bigmac['bigmac_per_10k'] = 10000.0 / bigmac['price']
    summary['bigmac'] = bigmac[['date','price','bigmac_per_10k']].dropna()
if gasoline is not None:
    gasoline['gallon_per_10k'] = 10000.0 / gasoline['price']
    summary['gasoline'] = gasoline[['date','price','gallon_per_10k']]
if msp is not None:
    # convert quarterly MSPUS into yearly snapshots and compute how many median homes per $100k
    msp['homes_per_10k'] = 10000.0 / msp['value']
    summary['median_home'] = msp[['date','value','homes_per_10k']]
if cpi is not None:
    cpi['inverted_pct'] = 1 / cpi['value']
    summary['cpi'] = cpi[['date','value','inverted_pct']]

# Save summary CSVs
for k,df in summary.items():
    df.to_csv(os.path.join(OUTPUT_DIR,f'summary_{k}.csv'), index=False)

# ---------------------- Plotting ----------------------
print('Plotting charts...')
plt.rcParams['figure.dpi'] = 120

if 'bigmac' in summary:
    df = summary['bigmac']
    df = df[df['date'] >= pd.to_datetime('1995-01-01')]
    initial = df['bigmac_per_10k'].iloc[0]
    df['bigmac_pct'] = (df['bigmac_per_10k'] / initial) * 100
    plt.figure()
    plt.plot(df['date'], df['bigmac_pct'])
    plt.title('Big Mac Purchasing Power (% of 1995)')
    plt.xlabel('Date')
    plt.ylabel('Percentage of 1995 Value')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,'bigmac_cost_percentage_1995.png'))
    print('Saved bigmac_cost_percentage_1995.png')

if 'gasoline' in summary:
    df = summary['gasoline']
    df = df[df['date'] >= pd.to_datetime('1995-01-01')]
    # resample to annual average for cleaner chart
    ann = df.set_index('date').resample('YE').mean().reset_index()
    initial = ann['gallon_per_10k'].iloc[0]
    ann['gallon_pct'] = (ann['gallon_per_10k'] / initial) * 100
    plt.figure()
    plt.plot(ann['date'], ann['gallon_pct'])
    plt.title('Gasoline Purchasing Power (% of 1995)')
    plt.xlabel('Date')
    plt.ylabel('Percentage of 1995 Value')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,'gas_gallons_cost_percentage_1995.png'))
    print('Saved gas_gallons_cost_percentage_1995.png')

if 'median_home' in summary:
    df = summary['median_home']
    df = df[df['date'] >= pd.to_datetime('1995-01-01')]
    # annual snapshots
    ann = df.set_index('date').resample('YE').last().reset_index()
    initial = ann['homes_per_10k'].iloc[0]
    ann['homes_pct'] = (ann['homes_per_10k'] / initial) * 100
    plt.figure()
    plt.plot(ann['date'], ann['homes_pct'])
    plt.title('Median Home Purchasing Power (% of 1995)')
    plt.xlabel('Date')
    plt.ylabel('Percentage of 1995 Value')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,'homes_purchased_with_median_salary_percentage_1995.png'))
    print('Saved homes_purchased_with_median_salary_percentage_1995.png')
# Inverted CPI Purchasing Power Plot
if 'cpi' in summary:
    cpi_filtered = cpi[cpi['date'] >= pd.to_datetime('1995-01-01')].copy()
    cpi_filtered['inverted'] = 1 / cpi_filtered['value']
    ann_cpi = cpi_filtered.set_index('date').resample('YE').mean(numeric_only=True).reset_index()
    initial = ann_cpi['inverted'].iloc[0]
    ann_cpi['inverted_pct'] = (ann_cpi['inverted'] / initial) * 100
    plt.figure()
    plt.plot(ann_cpi['date'], ann_cpi['inverted_pct'])
    plt.title('Inverted CPI Purchasing Power (% of 1995)')
    plt.xlabel('Date')
    plt.ylabel('Percentage of 1995 Value')
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,'inverted_cpi_percentage_1995.png'))
    print('Saved inverted_cpi_percentage_1995.png')

# Combined Purchasing Power Plot
combined_data = {}

if 'bigmac' in summary:
    bm_df = summary['bigmac']
    bm_df = bm_df[bm_df['date'] >= pd.to_datetime('1995-01-01')]
    bm_ann = bm_df.set_index('date').resample('YE').mean().reset_index()
    initial_bm = bm_ann['bigmac_per_10k'].iloc[0]
    bm_ann['pct'] = (bm_ann['bigmac_per_10k'] / initial_bm) * 100
    combined_data['Big Mac'] = bm_ann

if 'gasoline' in summary:
    gas_df = summary['gasoline']
    gas_df = gas_df[gas_df['date'] >= pd.to_datetime('1995-01-01')]
    gas_ann = gas_df.set_index('date').resample('YE').mean().reset_index()
    initial_gas = gas_ann['gallon_per_10k'].iloc[0]
    gas_ann['pct'] = (gas_ann['gallon_per_10k'] / initial_gas) * 100
    combined_data['Gasoline'] = gas_ann

if 'median_home' in summary:
    home_df = summary['median_home']
    home_df = home_df[home_df['date'] >= pd.to_datetime('1995-01-01')]
    home_ann = home_df.set_index('date').resample('YE').last().reset_index()
    initial_home = home_ann['homes_per_10k'].iloc[0]
    home_ann['pct'] = (home_ann['homes_per_10k'] / initial_home) * 100
    combined_data['Median Home'] = home_ann

if 'cpi' in summary:
    cpi_df = summary['cpi']
    cpi_df = cpi_df[cpi_df['date'] >= pd.to_datetime('1995-01-01')]
    ann_cpi = cpi_df.set_index('date').resample('YE').mean().reset_index()
    initial_cpi = ann_cpi['inverted_pct'].iloc[0]
    ann_cpi['pct'] = (ann_cpi['inverted_pct'] / initial_cpi) * 100
    combined_data['Inverted CPI'] = ann_cpi

if combined_data:
    plt.figure(figsize=(10,6))
    colors = ['navy', 'blue', 'lightblue', 'red']
    i = 0
    for label, df in combined_data.items():
        plt.plot(df['date'], df['pct'], label=label, color=colors[i])
        i += 1
    plt.title('Combined Purchasing Power (% of 1995)')
    plt.xlabel('Date')
    plt.ylabel('Percentage of 1995 Value')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR,'combined_purchasing_power_1995.png'))
    print('Saved combined_purchasing_power_1995.png')
print('\nAll outputs are in the "outputs" folder.\n')
print('Citations:')
print('- EIA gasoline series: https://www.eia.gov/dnav/pet/hist/leafhandler.ashx?f=m&n=pet&s=emm_epm0_pte_nus_dpg')
print('- CPI and MSPUS (FRED): https://fred.stlouisfed.org/series/CPIAUCSL and https://fred.stlouisfed.org/series/MSPUS')
print('- Big Mac: use The Economist Big Mac Index. See https://github.com/TheEconomist/big-mac-data/blob/master/source-data/')

# End of script
