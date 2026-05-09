import pandas as pd
import numpy as np
import os

def main():
    print("Loading Price Data for Days 2, 3, and 4...")
    days = ['day_2', 'day_3', 'day_4']
    all_dfs = []
    
    for day in days:
        filename = f'prices_round_5_{day}.csv'
        possible_paths = [f'round5/{filename}', filename, f'ROUND_5/{filename}']
        
        df_day = None
        for path in possible_paths:
            if os.path.exists(path):
                print(f"Found {filename} at: {path}")
                df_day = pd.read_csv(path, sep=';')
                break
        if df_day is not None:
            all_dfs.append(df_day)

    if not all_dfs:
        print("Error: Could not find any price data files.")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    
    print("\nExtracting Macro Price Trends...")
    # Pivot to get raw mid_prices
    pivot_df = df.pivot_table(index=['day', 'timestamp'], columns='product', values='mid_price').ffill().dropna()
    
    # Normalize the prices so every day starts at 0 (Removes overnight gaps)
    for day in days:
        day_idx = int(day.split('_')[1])
        if day_idx in pivot_df.index.get_level_values('day'):
            start_prices = pivot_df.loc[day_idx].iloc[0]
            pivot_df.loc[day_idx] = pivot_df.loc[day_idx] - start_prices

    products = pivot_df.columns
    print("Running 50x50 Trend-Shift Analysis (Looking for Forcing Moves)...")
    
    results = []
    
    # Sweep delays from 1 to 30 timestamps
    for shift_val in range(1, 31): 
        shifted_prices = pivot_df.shift(shift_val)
        
        for p_lead in products:
            for p_lag in products:
                if p_lead == p_lag: continue
                
                # Correlate the Raw Price Trends
                corr = shifted_prices[p_lead].corr(pivot_df[p_lag])
                
                # In raw prices, we are looking for massive structural ties (> 0.85)
                if abs(corr) > 0.85: 
                    results.append({
                        'Leader': p_lead,
                        'Lagger': p_lag,
                        'Ticks_Delay': shift_val,
                        'Correlation': corr
                    })
    
    if results:
        res_df = pd.DataFrame(results).sort_values(by='Correlation', key=abs, ascending=False)
        # Keep only the strongest optimal delay for each pair
        res_df = res_df.drop_duplicates(subset=['Leader', 'Lagger'])
        
        print("\n=======================================================")
        print(" 🚀 MACRO LEAD-LAG: THE MARKET'S FORCING MOVES")
        print("=======================================================\n")
        print(res_df.head(15).to_string(index=False))
    else:
        print("No massive price-trend relationships found.")

if __name__ == "__main__":
    main()