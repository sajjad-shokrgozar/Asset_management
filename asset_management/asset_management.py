# asset_management_api/asset_management.py

import pandas as pd
import datetime, time, jdatetime
import numpy as np
from scipy.stats import norm
import requests
import math
import matplotlib.pyplot as plt
from scipy.optimize import root_scalar


class Asset_management:

    def __init__(self, risk_free_rate=0.3):
        self.headers = {
            'Host': 'cdn.tsetmc.com',
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.risk_free_rate = risk_free_rate
        self.c_date = datetime.date.today()

    def cumulation(self, x):
        x['weighted_price'] = x['price'] * x['vol']

        x['price'] = float(x['weighted_price'].sum() / x['vol'].sum())
        x['vol'] = x['vol'].sum()
        return x
    
    def get_total_trades(self, excel_name, sheet_name, tse_data):
        trades_df = pd.read_excel(excel_name, sheet_name=sheet_name)
        trades_df = trades_df[['date', 'fund', 'symbol', 'position', 'price', 'vol']]
        trades_df = pd.merge(trades_df, tse_data[['symbol', 'market']], how='left', on='symbol')
        trades_df['market'].fillna('option', inplace=True)
        trades_df['date'] = trades_df['date'].replace(r'- (.*)', '', regex=True)
        # find option type
        trades_df['type'] = None
        trades_df.loc[(trades_df['symbol'].str.startswith('ط')) & (trades_df['market'] == 'option'), 'type'] = 'put'
        trades_df.loc[(trades_df['symbol'].str.startswith('ض')) & (trades_df['market'] == 'option'), 'type'] = 'call'
        # find holding days
        trades_df['holding_days'] = trades_df.apply(lambda x: -self.cal_ttm(self.to_gregorian_date(x['date'])), axis=1)

        return trades_df

    def get_cumulative_trades(self, total_trades_df, tse_data):
        # match tse data with trades
        ls_cum_df = pd.merge(total_trades_df, tse_data, how='left', on='symbol')
        ls_cum_df = ls_cum_df[['date', 'fund', 'symbol', 'position', 'price', 'vol', 'type_x', 'holding_days']]
        ls_cum_df.rename({'type_x': 'type'}, axis=1, inplace=True)

        # adding opened_iv, opened_delta columns
        # ls_cum_df = ls_cum_df[~ls_cum_df['strike'].isna()]
        # ls_cum_df['opened_iv'] = ls_cum_df.apply(lambda x: implied_volatility(x['ua_price'], x['strike'], x['price'], x['ttm'], risk_free_rate, x['type']), axis=1)
        # ls_cum_df['opened_delta'] = ls_cum_df.apply(lambda x: delta(x['ua_price'], x['strike'], x['ttm'], risk_free_rate, x['opened_iv'], x['type']), axis=1)
        # ls_cum_df = ls_cum_df[['account', 'strategy_id', 'date', 'option', 'position', 'price', 'vol', 'ua_price', 'strike', 'type', 'holding_days', 'ttm', 'opened_iv', 'opened_delta']]

        # removing nans: somtimes there is nan that comes from not existence in tse_data because of not existing order in order book
        # ls_cum_df = ls_cum_df.groupby(['account', 'strategy_id']).apply(lambda x: x if len(x['option'].unique()) > 1 else None).reset_index(drop=True)

        # cumulation process
        ls_cum_df = ls_cum_df.groupby(['symbol', 'position']).apply(lambda x: self.cumulation(x)).reset_index(drop=True)
        ls_cum_df = ls_cum_df.drop_duplicates(subset=['symbol', 'position'])

        return ls_cum_df
    
    def create_portfolio(self, tdf, tse_data):
        tdf['net_vol'] = tdf.apply(lambda row: row['vol'] if row['position'] == 'long' else -row['vol'], axis=1)

        # Group by symbol and calculate the net volume and current value
        portfolio = tdf.groupby('symbol').agg(
            net_volume=('net_vol', 'sum'),
            avg_price=('price', 'mean'),  # Average price for simplicity, can be adjusted
            fund=('fund', 'first')
        ).reset_index()

        portfolio = pd.merge(portfolio, tse_data[['symbol', 'market']], how='left', on='symbol')
        portfolio['market'].fillna('option', inplace=True)

        # Calculate current value based on net volume and average price
        # portfolio['current_value'] = portfolio['net_volume'] * portfolio['avg_price']

        # Filter out symbols with zero net volume
        portfolio = portfolio[portfolio['net_volume'] != 0]
        portfolio = portfolio[['symbol', 'fund', 'market', 'net_volume']]
        portfolio.columns = ['symbol', 'fund', 'market', 'vol']

        portfolio['type'] = None
        portfolio.loc[(portfolio['symbol'].str.startswith('ط')) & (portfolio['market'] == 'option'), 'type'] = 'put'
        portfolio.loc[(portfolio['symbol'].str.startswith('ض')) & (portfolio['market'] == 'option'), 'type'] = 'call'

        portfolio['position'] = 'long'
        portfolio.loc[portfolio['vol'] < 0, 'position'] = 'short'

        portfolio.columns = ['symbol', 'fund', 'market', 'vol', 'type', 'position']
        return portfolio[['symbol', 'fund', 'market', 'type', 'position', 'vol']]
        
    
    # Define the NPV function
    def npv(self, cf_value_and_T, r):
        return (cf_value_and_T['value'] * (1 + r)**(cf_value_and_T['until_now'] / 30)).sum()

    # Optimized IRR function with dynamic bracket adjustment
    def irr(self, cf_value_and_T):
        # Start with an initial bracket
        lower, upper = -0.99, 10
        # Expand bracket until f(lower) and f(upper) have opposite signs
        while self.npv(cf_value_and_T, lower) * self.npv(cf_value_and_T, upper) > 0:
            upper += 10
            if upper > 1000:  # Prevent infinite loop
                return None
                # raise ValueError("IRR not found within reasonable range.")
        
        # Use root_scalar to find IRR
        result = root_scalar(lambda r: self.npv(cf_value_and_T, r), bracket=[lower, upper], method='brentq', xtol=1e-6)
        return result.root  # Return the IRR