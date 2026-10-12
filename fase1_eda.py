"""Phase 1 - Exploratory Data Analysis of Superstore.
Run: python3 fase1_eda.py   (CSV must be extracted next to this file)
"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
df = pd.read_csv(HERE / "sample_superstore_prepared.csv", sep=";", decimal=",", encoding="utf-8-sig")
df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True)

print("=" * 70, "\n1. WHAT IS IN THE DATA")
print(f"Rows: {len(df):,} order lines · Columns: {df.shape[1]}")
print(f"Period: {df['Order Date'].min():%d %b %Y} -> {df['Order Date'].max():%d %b %Y}")
print(f"Orders: {df['Order ID'].nunique():,} · Customers: {df['Customer ID'].nunique():,} · "
      f"Products: {df['Product ID'].nunique():,} · Cities (stores): {df['City'].nunique()} · States: {df['State'].nunique()}")
print(f"Categories: {', '.join(sorted(df['Category'].unique()))} ({df['Sub-Category'].nunique()} sub-categories)")

print("\n2. CAN I TRUST IT? (missing / duplicates)")
print(f"Missing values: {int(df.isna().sum().sum())} · Duplicated rows: {int(df.duplicated().sum())}")
print("Note: Postal Code is a number; ZIP codes starting with 0 lost their leading zero.")

print("\n3. KEY STATISTICS")
print(df[["Sales", "Quantity", "Discount", "Profit"]].describe().round(2).to_string())
print(f"\nTotal sales: ${df.Sales.sum():,.0f} · Total profit: ${df.Profit.sum():,.0f} "
      f"· Margin: {df.Profit.sum() / df.Sales.sum():.1%}")
loss = (df.Profit < 0).mean()
print(f"Order lines sold at a loss: {loss:.1%}")

print("\n4. HOW STORES PERFORM (top 10 cities by sales)")
city = (df.groupby(["City", "State"])
          .agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"),
               Orders=("Order ID", "nunique"), AvgDiscount=("Discount", "mean"))
          .sort_values("Sales", ascending=False))
city["Margin"] = city.Profit / city.Sales
print(city.head(10).round(2).to_string())
print("\nWorst 5 cities by profit:")
print(city.sort_values("Profit").head(5).round(2).to_string())

print("\n5. WHY? Discount drives profit")
bands = pd.cut(df.Discount, [-0.01, 0, 0.2, 0.4, 1], labels=["0%", "1-20%", "21-40%", ">40%"])
print(df.groupby(bands, observed=True).agg(Lines=("Profit", "size"), Profit=("Profit", "sum"),
                                           AvgProfitPerLine=("Profit", "mean")).round(1).to_string())
print(f"Correlation discount vs profit: {df.Discount.corr(df.Profit):.2f}")

print("\nCONCLUSION")
print("- Top sellers (New York City, Los Angeles, Seattle) are big markets with LOW discounts (~6%),")
print("  so they keep ~17-24% margin.")
print("- Philadelphia, Houston and Chicago sell a lot but LOSE money: average discount 33-38%.")
print("- Every discount above 20% turns the average order line into a loss.")
print("- Technology and Office Supplies make the profit; Furniture sells as much but earns almost nothing.")
