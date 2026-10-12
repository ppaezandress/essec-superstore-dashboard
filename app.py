"""Superstore app - AI & Business Decisions (ESSEC) - Vibe coding challenge.
Run: streamlit run app.py   (CSV extracted next to this file)
Built with Claude Code (Anthropic) as the coding assistant.
Design: "Data-Dense Dashboard" style (ui-ux-pro-max) + dataviz rules (status colours, thin marks, one axis).
"""
import os
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import external_data as ex  # noqa: E402  (Phase 5: datausa.io, census.gov, open-meteo.com)
FOCUS_CITIES = ["New York City", "Houston", "Seattle", "Chicago"]
MAX_SAFE_DISCOUNT = 0.20

# Colour tokens: blue = neutral data, status green/red only for profit vs loss (always with a text label)
BLUE, GOOD, CRITICAL = "#2A78D6", "#0CA30C", "#D03B3B"
INK, INK_2, GRID = "#0F172A", "#52514E", "#E5E9F0"
CATEGORY_COLOURS = ["#2A78D6", "#EB6834", "#1BAF7A"]  # dataviz categorical slots 1-3, fixed order
DIVERGING = [[0, "#B3261E"], [0.5, "#F0EFEC"], [1, "#1E5BB8"]]  # loss (red) <- neutral grey -> profit (blue)
GAINS, LOSSES = "Makes money", "Loses money"
STATUS = {GAINS: GOOD, LOSSES: CRITICAL}

STATE_CODES = {
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

st.set_page_config(page_title="Superstore Dashboard", page_icon=":material/storefront:", layout="wide")


ORIGINAL_FILE = "sample_superstore_prepared.csv"
NEW_FILE = "sample_superstore_prepared_2014_2019.csv"  # Phase 3: Moodle file with synthetic 2018-2019 data
STORES = ["New York City", "Los Angeles", "Seattle", "San Francisco", "Philadelphia", "Houston", "Chicago",
          "San Diego", "Detroit", "Dallas"]  # store numbers 1-10 handed out in class
OUR_STORE = "San Diego"  # we are team 8 -> store 8


def read_superstore(name):
    d = pd.read_csv(HERE / name, sep=";", decimal=",", encoding="utf-8-sig")
    d["Order Date"] = pd.to_datetime(d["Order Date"], dayfirst=True)
    d["Discount amount"] = d.Sales / (1 - d.Discount) * d.Discount  # $ given away: list price - price paid
    return d


@st.cache_data
def load():
    original = read_superstore(ORIGINAL_FILE)
    new = read_superstore(NEW_FILE) if (HERE / NEW_FILE).exists() else None
    coords = pd.read_csv(HERE / "city_coords.csv")
    return original, new, coords


def money(x):
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x / 1_000_000:.1f}M"
    if x >= 100_000:
        return f"{sign}${x / 1_000:.0f}K"
    return f"{sign}${x:,.0f}"


def M(x):
    """money() for markdown text: escape $ so Streamlit does not render it as LaTeX."""
    return money(x).replace("$", "\\$")


def short(name, n=48):
    return name if len(name) <= n else name[: n - 1] + "…"


def status(p):
    return GAINS if p >= 0 else LOSSES


def summary(d, by):
    out = (d.groupby(by).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), Orders=("Order ID", "nunique"),
                             Units=("Quantity", "sum"), Discount=("Discount", "mean")).reset_index())
    out["Margin"] = out.Profit / out.Sales
    out["Profit per unit"] = out.Profit / out.Units
    return out


def style(fig, height=380, legend=True):
    """Shared chart chrome: thin rounded bars, hairline grid, recessive axes, one font."""
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Fira Sans, sans-serif", size=13, color=INK_2),
        hoverlabel=dict(bgcolor="white", font_size=13, font_family="Fira Sans, sans-serif"),
        showlegend=legend, legend=dict(orientation="h", y=1.08, x=0, title_text=""),
        bargap=0.35, bargroupgap=0.08,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="", title_font=dict(size=12))
    fig.update_yaxes(gridcolor=GRID, zeroline=True, zerolinecolor="#C9D1DC", linecolor=GRID, title_font=dict(size=12))
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4, marker_line_width=0)
    return fig


def colour_profit(v):
    return f"color: {CRITICAL}; font-weight: 600" if v < 0 else f"color: {INK}"


def DOLLARS(v):
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


@st.cache_data(ttl=86400, show_spinner="Collecting population data from datausa.io…")
def ext_places():
    return ex.places_population()


@st.cache_data(ttl=86400, show_spinner=False)
def ext_states():
    return ex.states_population()


@st.cache_data(ttl=86400, show_spinner="Collecting population, income and poverty (US Census via datausa.io)…")
def ext_city(place_id):
    return ex.city_series(place_id)


@st.cache_data(ttl=86400, show_spinner="Collecting weather history from open-meteo.com…")
def ext_weather(lat, lon):
    return ex.weather_monthly(lat, lon)


@st.cache_data(ttl=86400, show_spinner="Collecting unemployment from census.gov…")
def ext_unemployment(place_id, key):
    return ex.census_unemployment(place_id, key)


def census_key():
    try:
        return st.secrets["CENSUS_API_KEY"]
    except Exception:
        return os.environ.get("CENSUS_API_KEY")


FMT = {"Sales": DOLLARS, "Profit": DOLLARS, "Margin": "{:.0%}", "Discount": "{:.0%}", "Orders": "{:,}",
       "Units": "{:,}", "Avg order": DOLLARS, "Profit per unit": lambda v: f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}", "Population": "{:,.0f}",
       "Sales per 1,000 people": DOLLARS, "Median income": DOLLARS, "Poverty rate": "{:.1%}"}

original, new, coords = load()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### :material/database: Data")
    if new is not None:
        choice = st.radio("Which file?", ["2014-2019 (new file, Phase 3)", "2014-2017 (original file)"],
                          label_visibility="collapsed")
        df = new if choice.startswith("2014-2019") else original
    else:
        df = original
    END = int(df.Order_year.max())
    st.markdown("### :material/filter_alt: Filters")
    st.caption("Every chart updates when you change these. Leave a filter empty to see everything.")
    cats = st.multiselect("Category", sorted(df.Category.unique()), placeholder="All categories")
    pool = df[df.Category.isin(cats)] if cats else df
    subs = st.multiselect("Sub-category", sorted(pool["Sub-Category"].unique()), placeholder="All sub-categories")
    years = st.multiselect("Year", sorted(df.Order_year.unique()), placeholder="All years")
    st.divider()
    st.caption(f"Data: Superstore sample, a US retail chain (2014-{END}). 2018-2019 rows are synthetic "
               f"(generated with AI by the teacher).  \nBuilt with Claude Code.")

f = df
if cats:
    f = f[f.Category.isin(cats)]
if subs:
    f = f[f["Sub-Category"].isin(subs)]
if years:
    f = f[f.Order_year.isin(years)]
if f.empty:
    st.warning("No sales match this selection. Try removing a filter.", icon=":material/info:")
    st.stop()

# ---------- Header ----------
st.title("Superstore: where do we make money?")
st.caption("Sales dashboard for a US retail chain · AI & Business Decisions, ESSEC")

safe = f[f.Discount <= MAX_SAFE_DISCOUNT].Profit.sum()
risky = f[f.Discount > MAX_SAFE_DISCOUNT].Profit.sum()
st.info(f"**Key insight: the problem is not sales, it is discounts.**  \n"
        f"Sales with 20% discount or less made **{M(safe)}** profit. "
        f"Sales above 20% discount made **{M(risky)}**.", icon=":material/lightbulb:")

k = st.columns(4)
kpis = [("Sales", money(f.Sales.sum()), "Total revenue"),
        ("Profit", money(f.Profit.sum()), "What is left after costs"),
        ("Margin", f"{f.Profit.sum() / f.Sales.sum():.1%}", "Profit for every $1 sold"),
        ("Average discount", f"{f.Discount.mean():.0%}", "Average discount per sale")]
for col, (label, value, helptext) in zip(k, kpis):
    col.metric(label, value, help=helptext, border=True)

tabs = st.tabs([":material/auto_stories: The story", ":material/map: Store map", ":material/category: Categories",
                ":material/location_city: Our 4 cities", ":material/storefront: Our store",
                ":material/sell: Promotions",
                ":material/public: City context"])

city = summary(f, ["City", "State"]).merge(coords, on=["City", "State"], how="left")
city["Result"] = city.Profit.apply(status)
city["Avg order"] = city.Sales / city.Orders

# Phase 5: attach Census population to every store (works offline from external_cache/)
try:
    places, places_origin = ext_places()
    city["code"] = city.State.map(STATE_CODES)
    city = ex.match_cities(city, places)
    city["Sales per 1,000 people"] = city.Sales / city.Population * 1000
    EXT_OK = True
except Exception as err:  # no internet and no cache: the rest of the app still works
    EXT_OK, EXT_ERROR = False, err

# ---------- 1. The story (Phase 1: EDA + how stores perform and why) ----------
with tabs[0]:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("#### What happens to profit when we give discounts?")
        bands = pd.cut(f.Discount, [-0.01, 0, 0.2, 0.4, 1], labels=["No discount", "1-20%", "21-40%", "Over 40%"])
        disc = f.groupby(bands, observed=True).agg(Profit=("Profit", "sum"), Lines=("Profit", "size")).reset_index()
        disc["Result"] = disc.Profit.apply(status)
        fig = px.bar(disc, x="Discount", y="Profit", color="Result", color_discrete_map=STATUS,
                     text=disc.Profit.apply(money), labels={"Discount": "Discount given", "Profit": "Profit ($)"},
                     hover_data={"Lines": ":,", "Result": False, "Profit": ":$,.0f"})
        fig.update_traces(textposition="outside", textfont=dict(color=INK, size=13), cliponaxis=False)
        st.plotly_chart(style(fig))
        st.caption("Each bar adds up the profit of every sale in that discount range.")
    with right:
        st.markdown("#### How do sales evolve over time?")
        q = f.groupby(f["Order Date"].dt.to_period("Q")).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"))
        q.index = q.index.astype(str)
        fig = px.bar(q.reset_index(), x="Order Date", y=["Sales", "Profit"], barmode="group",
                     color_discrete_sequence=[BLUE, "#9DC3F0"], labels={"Order Date": "Quarter", "value": "$"})
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(style(fig))
        by_q = f.groupby(f["Order Date"].dt.quarter).Sales.sum()
        by_y = f.groupby(f["Order Date"].dt.year).Sales.sum()
        falls = [str(y) for y, chg in by_y.diff().items() if chg < 0]
        trend = ("Sales grow every year." if not falls else
                 f"Sales grow overall ({by_y.index[0]}-{by_y.index[-1]}: {by_y.iloc[-1] / by_y.iloc[0] - 1:+.0%}), "
                 f"with a dip in {', '.join(falls)}.") if len(by_y) > 1 else ""
        qy = f.groupby([f["Order Date"].dt.year, f["Order Date"].dt.quarter]).Sales.sum().unstack()
        q4_always = bool((qy.idxmax(axis=1) == 4).all())
        st.caption(f"{trend} Q4 (Oct-Dec) is {'every year ' if q4_always else ''}the strongest quarter"
                   f"{'' if q4_always else ' overall'}: {M(by_q.get(4, 0))} vs {M(by_q.get(1, 0))} in Q1.")

    st.markdown("#### Which stores sell the most, and why?")
    left, right = st.columns([3, 2], gap="large")
    top8 = city.sort_values("Sales", ascending=False).head(8)
    with left:
        labelled = city.nlargest(6, "Sales").City.tolist()
        fig = px.scatter(city, x="Orders", y="Sales", color="Result", color_discrete_map=STATUS, hover_name="City",
                         text=city.City.where(city.City.isin(labelled), ""),
                         hover_data={"Sales": ":$,.0f", "Profit": ":$,.0f", "Discount": ":.0%", "Result": False},
                         labels={"Orders": "Number of orders", "Sales": "Sales ($)"})
        fig.update_traces(marker=dict(size=9, opacity=0.75, line=dict(width=1.5, color="white")),
                          textposition="middle left", textfont=dict(color=INK, size=12))
        fig.update_xaxes(showgrid=True, gridcolor=GRID)
        st.plotly_chart(style(fig, height=400))
    with right:
        corr_orders = city.Orders.corr(city.Sales)
        corr_basket = city["Avg order"].corr(city.Sales)
        st.markdown(
            f"- **Top stores sell more because they get more orders.** Sales follow the number of orders almost "
            f"perfectly (correlation **{corr_orders:.2f}**), but not the size of each order ({corr_basket:.2f}). "
            f"They are the biggest markets: {', '.join(top8.City.head(4))}.\n"
            f"- **The best ones also discount little.** The profitable top stores give about "
            f"{top8[top8.Profit >= 0].Discount.mean():.0%} discount; the loss-making ones give "
            f"{top8[top8.Profit < 0].Discount.mean():.0%}.\n"
            f"- **Big discounts do not buy bigger baskets.** Average order in the loss-making top stores: "
            f"{M(top8[top8.Profit < 0]['Avg order'].mean())}, vs {M(top8[top8.Profit >= 0]['Avg order'].mean())} "
            f"in the profitable ones.")
        st.dataframe(top8[["City", "Orders", "Avg order", "Sales", "Profit", "Discount"]].style.format(FMT)
                     .map(colour_profit, subset=["Profit"]), hide_index=True)

    with st.expander("Can we trust this data?", icon=":material/fact_check:"):
        st.markdown(f"- **{len(df):,}** sales lines · **{df['Order ID'].nunique():,}** orders · "
                    f"**{df['Customer ID'].nunique():,}** customers · **{df['Product ID'].nunique():,}** products · "
                    f"**{df.City.nunique()}** cities in **{df.State.nunique()}** states\n"
                    f"- From **{df['Order Date'].min():%b %Y}** to **{df['Order Date'].max():%b %Y}**\n"
                    f"- Missing values: **{int(df.isna().sum().sum())}** · Duplicated rows: "
                    f"**{int(df.duplicated().sum())}**, so the data is complete\n"
                    f"- **{(df.Profit < 0).mean():.0%}** of sales lines lose money\n"
                    f"- Note: postal codes are stored as numbers, so ZIP codes starting with 0 lost that 0")
        st.dataframe(df[["Sales", "Quantity", "Discount", "Profit"]].describe().round(2))

# ---------- 2. Map (Phase 2: stores on a map) ----------
with tabs[1]:
    st.markdown("#### Which states and stores make money?")
    c1, c2 = st.columns([2, 3])
    options = ["Profit", "Sales", "Average discount"] + (["Sales per 1,000 people"] if EXT_OK else [])
    colour_by = c1.segmented_control("Colour the states by", options, default="Profit") or "Profit"
    all_cities = c2.toggle("Show every city (not only the 25 biggest)", value=False)

    state = summary(f, "State")
    state["code"] = state.State.map(STATE_CODES)
    if EXT_OK:
        state = state.merge(ext_states()[0], on="State", how="left")
        state["Per 1,000"] = state.Sales / state.Population * 1000
    if colour_by == "Profit":
        zmax = state.Profit.abs().max()
        scale, z, zmin, title, fmt = DIVERGING, state.Profit, -zmax, "Profit ($)", "$,.0f"
    elif colour_by == "Sales":
        scale, z, zmin, zmax, title, fmt = "Blues", state.Sales, 0, state.Sales.max(), "Sales ($)", "$,.0f"
    elif colour_by == "Sales per 1,000 people":
        # cap at the 90th percentile so one tiny state (Delaware) does not wash out the rest
        scale, z, zmin, zmax, title, fmt = ("Purples", state["Per 1,000"], 0, state["Per 1,000"].quantile(0.9),
                                            f"Sales per 1,000 people ($, 2014-{END})", "$,.0f")
    else:
        scale, z, zmin, zmax, title, fmt = "Oranges", state.Discount, 0, state.Discount.max(), "Avg discount", ".0%"

    fig = go.Figure(go.Choropleth(
        locations=state.code, z=z, locationmode="USA-states", colorscale=scale, zmin=zmin, zmax=zmax,
        marker_line_color="white", marker_line_width=1,
        colorbar=dict(title=dict(text=title, side="top"), orientation="h", y=-0.02, len=0.45, thickness=10,
                      tickformat=("$,.0f" if colour_by == "Sales per 1,000 people" else "$~s") if fmt.startswith("$")
                      else ".0%", outlinewidth=0),
        customdata=state[["State", "Sales", "Profit", "Discount"]].values,
        hovertemplate="<b>%{customdata[0]}</b><br>Sales %{customdata[1]:$,.0f}<br>"
                      "Profit %{customdata[2]:$,.0f}<br>Avg discount %{customdata[3]:.0%}<extra></extra>"))

    pts = city if all_cities else city.nlargest(25, "Sales")
    # Hand-placed labels so neighbouring cities do not overlap
    LABEL_POS = {"New York City": "top right", "Philadelphia": "bottom left", "Los Angeles": "middle left",
                 "San Diego": "bottom right", "San Francisco": "middle left", "Seattle": "top center",
                 "Houston": "bottom center", "Chicago": "top left", "Detroit": "top right"}
    fig.add_trace(go.Scattergeo(
        lat=pts.lat, lon=pts.lon, mode="markers+text",
        text=[c if c in LABEL_POS else "" for c in pts.City],
        textposition=[LABEL_POS.get(c, "top center") for c in pts.City],
        textfont=dict(size=12, color=INK, family="Fira Sans, sans-serif"),
        marker=dict(size=pts.Sales, sizemode="area", sizeref=2.0 * city.Sales.max() / (46 ** 2), sizemin=3,
                    color=[GOOD if p >= 0 else CRITICAL for p in pts.Profit], opacity=0.85,
                    line=dict(width=1.5, color="white")),
        customdata=pts.reindex(columns=["City", "State", "Sales", "Profit", "Discount", "Population",
                                        "Sales per 1,000 people"]).values,
        hovertemplate="<b>%{customdata[0]}</b>, %{customdata[1]}<br>Sales %{customdata[2]:$,.0f}<br>"
                      "Profit %{customdata[3]:$,.0f}<br>Avg discount %{customdata[4]:.0%}<br>"
                      "Population %{customdata[5]:,.0f}<br>Sales per 1,000 people %{customdata[6]:$,.0f}"
                      "<extra></extra>",
        showlegend=False))
    fig.update_geos(scope="usa", bgcolor="rgba(0,0,0,0)", showlakes=False, landcolor="#EEF2F7",
                    subunitcolor="white")
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Fira Sans, sans-serif", color=INK_2),
                      hoverlabel=dict(bgcolor="white", font_family="Fira Sans, sans-serif"), dragmode=False)
    st.plotly_chart(fig, config={"scrollZoom": False, "displayModeBar": False})
    st.caption(f"**States:** coloured by {colour_by.lower()}"
               + (" (red = loss, blue = profit, grey = break-even)." if colour_by == "Profit" else ".")
               + " **Circles:** one per city, size = sales; green = the store makes money, red = it loses money."
               + (" Hover a circle to see its population (US Census 2017, via datausa.io)." if EXT_OK else ""))

    top = city.sort_values("Sales", ascending=False).head(10)
    losers = top[top.Profit < 0]
    if not losers.empty:
        st.error(f"**{len(losers)} of the 10 biggest stores lose money:** {', '.join(losers.City)}. "
                 f"Their average discount is {losers.Discount.mean():.0%}, "
                 f"vs {top[top.Profit >= 0].Discount.mean():.0%} in the profitable ones.", icon=":material/warning:")
    l, r = st.columns(2, gap="large")
    l.markdown("**Top 10 stores by sales**")
    l.dataframe(top[["City", "State", "Sales", "Profit", "Discount"]].style.format(FMT)
                .map(colour_profit, subset=["Profit"]), hide_index=True)
    r.markdown("**States that lose the most money**")
    r.dataframe(state.nsmallest(10, "Profit")[["State", "Sales", "Profit", "Discount"]].style.format(FMT)
                .map(colour_profit, subset=["Profit"]), hide_index=True)

# ---------- 3. Categories (Phase 2: compare categories by volume, amount, profit, discount) ----------
with tabs[2]:
    st.markdown("#### Which products make the money?")
    cat = summary(f, "Category").sort_values("Category")
    for col, (_, r) in zip(st.columns(len(cat)), cat.iterrows()):
        with col.container(border=True):
            st.markdown(f"**{r.Category}**")
            a, b = st.columns(2)
            a.metric("Sales", money(r.Sales))
            b.metric("Profit", money(r.Profit))
            st.markdown(f"**{r.Margin:.0%} margin** · **{M(r['Profit per unit'])}** profit per unit · "
                        f"{r.Discount:.0%} average discount")
            st.caption(f"{r.Orders:,} orders · {r.Units:,} units sold")

    st.markdown("#### Side by side: each category's share of the total")
    share = pd.DataFrame({
        "Category": cat.Category,
        "Orders": cat.Orders / cat.Orders.sum(), "Units sold": cat.Units / cat.Units.sum(),
        "Sales": cat.Sales / cat.Sales.sum(),
        "Profit": cat.Profit.clip(lower=0) / max(cat.Profit.clip(lower=0).sum(), 1),
    }).melt(id_vars="Category", var_name="Measure", value_name="Share")
    fig = px.bar(share, x="Measure", y="Share", color="Category", barmode="group",
                 color_discrete_sequence=CATEGORY_COLOURS, text=share.Share.map("{:.0%}".format),
                 labels={"Measure": "", "Share": "Share of total"})
    fig.update_traces(textposition="outside", textfont=dict(color=INK, size=12), cliponaxis=False)
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(style(fig, height=380))
    if len(cat) > 1:
        top_units = cat.loc[cat.Units.idxmax()]
        top_profit = cat.loc[cat.Profit.idxmax()]
        worst = cat.loc[cat.Margin.idxmin()]
        st.caption(f"{top_units.Category} sells the most units; {top_profit.Category} makes the most profit. "
                   f"{worst.Category} keeps only {worst.Margin:.0%} margin.")

    st.markdown("#### Profit by sub-category")
    sub = summary(f, "Sub-Category").sort_values("Profit")
    sub["Result"] = sub.Profit.apply(status)
    fig = px.bar(sub, x="Profit", y="Sub-Category", orientation="h", color="Result", color_discrete_map=STATUS,
                 hover_data={"Sales": ":$,.0f", "Discount": ":.0%", "Result": False, "Profit": ":$,.0f"},
                 labels={"Profit": "Profit ($)", "Sub-Category": ""})
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    st.plotly_chart(style(fig, height=max(320, 28 * len(sub))))
    neg = sub[sub.Profit < 0]
    if not neg.empty:
        st.caption(f"Losing money: {', '.join(neg['Sub-Category'])}. "
                   f"Their average discount is {neg.Discount.mean():.0%}.")
    with st.expander("Full report table: orders, units, sales, profit and discount", icon=":material/table:"):
        st.dataframe(summary(f, ["Category", "Sub-Category"]).sort_values(["Category", "Sales"],
                                                                          ascending=[True, False])
                     .style.format(FMT).map(colour_profit, subset=["Profit", "Margin"]), hide_index=True)


# ---------- 4. Our 4 cities (Phase 2: recommendations by category, sub-category and product) ----------
def city_recommendations(name):
    d = df[df.City == name]
    chain_mix = df.groupby("Sub-Category").Sales.sum() / df.Sales.sum()
    chain_margin = df.groupby("Sub-Category").Profit.sum() / df.groupby("Sub-Category").Sales.sum()
    s = summary(d, "Sub-Category").set_index("Sub-Category")
    s["Gap"] = s.Sales / s.Sales.sum() - chain_mix.reindex(s.index)
    c = summary(d, "Category").set_index("Category")
    p = summary(d, "Product Name")
    chain_disc = df.Discount.mean()

    sales = {"Category": [], "Sub-category": [], "Product": []}
    profit = {"Category": [], "Sub-category": [], "Product": []}

    main, small = c.Sales.idxmax(), c.Sales.idxmin()
    sales["Category"].append(f"Maintain **{main}**, the main category ({c.Sales[main] / c.Sales.sum():.0%} of sales).")
    sales["Category"].append(f"Improve **{small}**, the smallest one ({c.Sales[small] / c.Sales.sum():.0%}): "
                             f"display it next to {main} products.")
    keep = s[s.Profit > 0].sort_values("Sales", ascending=False).head(3)
    sales["Sub-category"].append("Maintain the best sellers: " + ", ".join(
        f"**{i}** ({M(r.Sales)})" for i, r in keep.iterrows()) + ".")
    grow = s[chain_margin.reindex(s.index) > 0.1].sort_values("Gap").head(2)
    if not grow.empty:
        sales["Sub-category"].append("Improve " + " and ".join(f"**{i}**" for i in grow.index) +
                                     ": they sell less here than in the rest of the chain, and they earn "
                                     "over 10% margin chain-wide.")
    best_p = p[p.Profit > 0].nlargest(3, "Sales")
    sales["Product"].append("Keep in stock and visible: " + "; ".join(
        f"**{short(r['Product Name'])}** ({M(r.Sales)})" for _, r in best_p.iterrows()) + ".")

    for cat_name, r in c.sort_values("Margin").iterrows():
        if r.Profit < 0:
            profit["Category"].append(f"**{cat_name}** loses {M(-r.Profit)} with {r.Discount:.0%} average discount: "
                                      f"review its pricing first.")
    if not profit["Category"]:
        best_c = c.Margin.idxmax()
        profit["Category"].append(f"All categories make money. Maintain **{best_c}**, the most profitable "
                                  f"({c.Margin[best_c]:.0%} margin).")
    worst_s = s[s.Profit < 0].sort_values("Profit").head(3)
    for i, r in worst_s.iterrows():
        profit["Sub-category"].append(f"**{i}** loses {M(-r.Profit)} at {r.Discount:.0%} average discount: "
                                      f"cap the discount at {MAX_SAFE_DISCOUNT:.0%}.")
    if worst_s.empty:
        profit["Sub-category"].append("No sub-category loses money. Keep the current pricing.")
    worst_p = p[p.Profit < 0].nsmallest(3, "Profit")
    if not worst_p.empty:
        profit["Product"].append("Stop discounting: " + "; ".join(
            f"**{short(r['Product Name'])}** (loses {M(-r.Profit)} at {r.Discount:.0%} off)"
            for _, r in worst_p.iterrows()) + ".")
    best_pp = p.nlargest(2, "Profit")
    profit["Product"].append("Protect the margin of: " + "; ".join(
        f"**{short(r['Product Name'])}** ({M(r.Profit)} profit)" for _, r in best_pp.iterrows()) + ".")

    headline = ("Priority #1 is a discount policy, not more sales. This store gives far more discount than the chain."
                if d.Discount.mean() > chain_disc + 0.05 else
                "Healthy store: maintain the pricing policy and grow the weaker categories.")
    return d, sales, profit, headline


with tabs[3]:
    st.markdown(f"#### Recommendations for New York, Houston, Seattle and Chicago (2014-{END})")
    four = summary(df[df.City.isin(FOCUS_CITIES)], "City").set_index("City").loc[FOCUS_CITIES].reset_index()
    four["Result"] = four.Profit.apply(status)
    st.dataframe(four[["City", "Result", "Sales", "Profit", "Margin", "Profit per unit", "Discount"]]
                 .style.format(FMT).map(colour_profit, subset=["Profit", "Margin"]), hide_index=True)
    st.caption(f"Margin = profit ÷ sales. Profit per unit = profit ÷ units sold. Chain average discount: "
               f"{df.Discount.mean():.0%}. Recommendations use all categories and years of the chosen file "
               f"(the sidebar filters do not apply here).")

    pick = st.segmented_control("Choose a city", FOCUS_CITIES, default=FOCUS_CITIES[0]) or FOCUS_CITIES[0]
    d, sales, profit, headline = city_recommendations(pick)
    healthy = d.Profit.sum() >= 0
    note = (f"**{pick}** sells {M(d.Sales.sum())} and {'earns' if healthy else 'loses'} "
            f"{M(abs(d.Profit.sum()))} ({d.Profit.sum() / d.Sales.sum():.0%} margin) "
            f"with an average discount of {d.Discount.mean():.0%}. {headline}")
    if healthy:
        st.success(note, icon=":material/check_circle:")
    else:
        st.error(note, icon=":material/error:")

    a, b = st.columns(2, gap="medium")
    for col, title, icon, recs in [(a, "Sales: improve or maintain", "trending_up", sales),
                                   (b, "Profit: improve or maintain", "savings", profit)]:
        with col.container(border=True):
            st.markdown(f"##### :material/{icon}: {title}")
            for level, items in recs.items():
                if items:
                    st.markdown(f"**By {level.lower()}**\n" + "\n".join(f"- {x}" for x in items))

    report = ["# Superstore - store recommendations", ""]
    for c_name in FOCUS_CITIES:
        dd, ss, pp, hh = city_recommendations(c_name)
        report += [f"## {c_name}", f"Sales {money(dd.Sales.sum())} · profit {money(dd.Profit.sum())} · "
                   f"average discount {dd.Discount.mean():.0%}. {hh}", "", "### Sales"]
        report += [f"- {x}" for items in ss.values() for x in items] + ["", "### Profit"]
        report += [f"- {x}" for items in pp.values() for x in items] + [""]
    st.download_button("Download the report for the 4 cities", "\n".join(report).replace("\\$", "$"),
                       file_name="superstore_recommendations.md", icon=":material/download:")

# ---------- Our store (Phase 3: new 2014-2019 file, future positions) ----------
FORMER, LATEST = "Former data (2014-2017)", "New data (2018-2019)"
PERIOD_COLOURS = {FORMER: "#9DC3F0", LATEST: BLUE, "Trend 2020": "#C9D1DC"}


@st.cache_data
def file_check(_original, _new):
    same = (_new.head(len(_original))[_original.columns].astype(str).values ==
            _original.astype(str).values).all(axis=1).mean()
    return same, int(_new.drop(columns="Row ID").duplicated().sum())


def store_years(d):
    y = d.groupby("Order_year").agg(Orders=("Order ID", "nunique"), Units=("Quantity", "sum"), Sales=("Sales", "sum"),
                                    Discount_amount=("Discount amount", "sum"), Profit=("Profit", "sum"),
                                    Discount=("Discount", "mean")).rename(columns={"Discount_amount":
                                                                                    "Discount amount"})
    y["Margin"] = y.Profit / y.Sales
    y["Profit per unit"] = y.Profit / y.Units
    return y


def trend_2020(series):
    """Straight line through the 6 yearly values, read at 2020. A simple trend, not a promise."""
    import numpy as np
    s = series.dropna()
    slope, intercept = np.polyfit(s.index.astype(float), s.values.astype(float), 1)
    return slope * 2020 + intercept


with tabs[4]:
    if new is None:
        st.info(f"Put **{NEW_FILE}** (from Moodle) in this folder to compare the new data with the former.",
                icon=":material/schedule:")
    else:
        st.markdown("#### Our store: former data (2014-2017) vs new data (2018-2019)")
        labels = [f"Store {i} · {c}" for i, c in enumerate(STORES, 1)]
        pick_label = st.selectbox("The store our team was allotted (team 8 = store 8)", labels,
                                  index=STORES.index(OUR_STORE))
        store_city = STORES[labels.index(pick_label)]
        yearly = store_years(new[new.City == store_city])
        former, latest = yearly.loc[2014:2017].mean(), yearly.loc[2018:2019].mean()
        chain = store_years(new)
        chain_growth = chain.loc[2018:2019].Sales.mean() / chain.loc[2014:2017].Sales.mean() - 1

        def change(key):
            return latest[key] / former[key] - 1 if former[key] else float("nan")

        st.caption("Average per year in each period, so 4 years and 2 years can be compared fairly.")
        rows_k = [
            [("Units sold", "Units", lambda v: f"{v:,.0f}"), ("Orders", "Orders", lambda v: f"{v:,.0f}"),
             ("Sales", "Sales", money), ("Discount given", "Discount amount", money)],
            [("Profit", "Profit", money), ("Margin", "Margin", lambda v: f"{v:.0%}"),
             ("Profit per unit", "Profit per unit", lambda v: f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"),
             ("Average discount", "Discount", lambda v: f"{v:.0%}")],
        ]
        for row_k in rows_k:
            for col, (label, key, fmt) in zip(st.columns(4), row_k):
                if key in ("Margin", "Discount"):
                    delta = f"{(latest[key] - former[key]) * 100:+.1f} pts vs 2014-17"
                elif key in ("Profit", "Profit per unit"):
                    gap = latest[key] - former[key]
                    shown = money(abs(gap)) if key == "Profit" else f"${abs(gap):,.2f}"
                    delta = f"{'+' if gap >= 0 else '-'}{shown} vs 2014-17"
                else:
                    delta = f"{change(key):+.0%} vs 2014-17"
                worse_if_up = key in ("Discount amount", "Discount")
                col.metric(f"{label} / year (2018-19)" if key not in ("Margin", "Discount", "Profit per unit")
                           else f"{label} (2018-19)", fmt(latest[key]), delta,
                           delta_color="inverse" if worse_if_up else "normal", border=True)

        sales_chg, disc_chg = change("Sales"), change("Discount amount")
        flat = [y for y in (2018, 2019) if abs(yearly.Sales.get(y, 0) / yearly.Sales.get(2017, 1) - 1) < 0.001]
        if flat:
            st.info(f"**Data warning:** sales in {', '.join(map(str, flat))} are almost exactly the same as in 2017 "
                    f"(\\${yearly.Sales[2017]:,.0f} vs " + ", ".join(f"\\${yearly.Sales[y]:,.0f}" for y in flat) + "). Real stores never repeat a yearly total to the dollar: the synthetic "
                    f"generator probably copied 2017. Treat the 2018-2019 trend for this store with care.",
                    icon=":material/report:")
        story = (f"**{store_city}** sells {sales_chg:+.0%} per year in 2018-19 vs 2014-17 (whole chain: "
                 f"{chain_growth:+.0%}). Discount given: {disc_chg:+.0%}. Profit per year went from "
                 f"{M(former.Profit)} to {M(latest.Profit)}.")
        if latest.Profit < 0 and disc_chg > sales_chg:
            st.error(story + " **Growth is being bought with discounts, and every extra sale loses money.**",
                     icon=":material/error:")
        elif sales_chg < 0:
            st.warning(story + " **The store is losing ground while the chain grows.**",
                       icon=":material/trending_down:")
        elif latest.Profit < former.Profit:
            st.warning(story + " **Sales grow but profit falls: check discounts.**", icon=":material/warning:")
        else:
            st.success(story + " **Healthy growth: sales and profit move up together.**",
                       icon=":material/trending_up:")

        st.markdown("##### Year by year, with a simple 2020 trend")
        panels = [("Units", "Units sold"), ("Orders", "Orders"), ("Sales", "Sales ($)"),
                  ("Discount amount", "Discount given ($)")]
        fig = make_subplots(rows=2, cols=2, subplot_titles=[p[1] for p in panels], vertical_spacing=0.16,
                            horizontal_spacing=0.08)
        forecast = {}
        for i, (key, title) in enumerate(panels):
            r_, c_ = i // 2 + 1, i % 2 + 1
            forecast[key] = max(trend_2020(yearly[key]), 0)
            for period, years_ in [(FORMER, range(2014, 2018)), (LATEST, range(2018, 2020))]:
                part = yearly.loc[yearly.index.isin(years_), key]
                fig.add_trace(go.Bar(x=part.index.astype(str), y=part.values, name=period,
                                     marker_color=PERIOD_COLOURS[period], legendgroup=period, showlegend=i == 0,
                                     hovertemplate="%{x}: %{y:,.0f}<extra></extra>"), r_, c_)
            fig.add_trace(go.Bar(x=["2020"], y=[forecast[key]], name="Trend 2020", marker_color="#C9D1DC",
                                 legendgroup="trend", showlegend=i == 0,
                                 hovertemplate="2020 (trend): %{y:,.0f}<extra></extra>"), r_, c_)
        style(fig, height=520)
        fig.update_layout(margin=dict(t=40), legend=dict(y=1.12))
        fig.update_annotations(font=dict(size=13, color=INK, family="Fira Sans, sans-serif"))
        st.plotly_chart(fig)
        st.caption("Light blue = former file (2014-2017) · dark blue = new file (2018-2019) · grey = 2020 read from a "
                   "straight trend line through the 6 years. The trend is an estimate, not a forecast model.")

        table = yearly.copy()
        table.insert(0, "Data", [FORMER if y <= 2017 else LATEST for y in table.index])
        trend_profit = trend_2020(yearly.Profit)
        trend_row = {**forecast, "Data": "Trend 2020 (estimate)", "Profit": trend_profit,
                     "Discount": trend_2020(yearly.Discount), "Margin": trend_profit / forecast["Sales"],
                     "Profit per unit": trend_profit / forecast["Units"]}
        table.loc[2020] = pd.Series(trend_row)
        table.index.name = "Year"
        st.dataframe(table.reset_index().style.format(FMT | {"Discount amount": DOLLARS, "Orders": "{:,.0f}",
                                                             "Units": "{:,.0f}", "Year": "{}"}, na_rep="-")
                     .map(colour_profit, subset=["Profit"]), hide_index=True)
        st.session_state["phase3_forecast"] = {"store": store_city, **forecast,
                                               "Profit": trend_2020(yearly.Profit)}

        st.markdown("##### The 10 allotted stores: who grows and who loses ground")
        rank = []
        for i, c in enumerate(STORES, 1):
            y = store_years(new[new.City == c])
            f0, f1 = y.loc[2014:2017].mean(), y.loc[2018:2019].mean()
            rank.append({"Store": f"{i} · {c}", "Sales / year 2014-17": f0.Sales, "Sales / year 2018-19": f1.Sales,
                         "Sales change": f1.Sales / f0.Sales - 1, "Profit / year 2018-19": f1.Profit,
                         "Avg discount 2018-19": f1.Discount})
        rank = pd.DataFrame(rank).sort_values("Sales change", ascending=False)
        st.dataframe(rank.style.format({"Sales / year 2014-17": DOLLARS, "Sales / year 2018-19": DOLLARS,
                                        "Sales change": "{:+.0%}", "Profit / year 2018-19": DOLLARS,
                                        "Avg discount 2018-19": "{:.0%}"})
                     .map(colour_profit, subset=["Profit / year 2018-19", "Sales change"])
                     .apply(lambda r: ["background-color: #E8F0FB" if r.Store.endswith(store_city) else ""
                                       for _ in r], axis=1), hide_index=True)

        with st.expander("Is the new file reliable? Data check", icon=":material/fact_check:"):
            same, dups = file_check(original, new)
            added = new[new.Order_year >= 2018]
            st.markdown(
                f"- **{len(new):,}** sales lines from **{new['Order Date'].min():%b %Y}** to "
                f"**{new['Order Date'].max():%b %Y}**, same {new.shape[1] - 1} columns and same "
                f"{new.City.nunique()} cities as the original file\n"
                f"- The first **{len(original):,}** lines are **{same:.0%} identical** to the original file; "
                f"**{len(added):,}** lines are new (2018-2019)\n"
                f"- Missing values: **{int(new.drop(columns='Discount amount').isna().sum().sum())}** · "
                f"duplicated lines: **{dups}**\n"
                f"- The teacher said the 2018-2019 lines are **synthetic data generated with AI**: they follow the "
                f"patterns of 2014-2017, so they are useful to practise, not to predict the real future.")

# ---------- 5. Promotions (Phase 4: promo_engine.py from Moodle) ----------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TARGET_LABELS = {"sub_category": "Sub-category", "category": "Category", "product": "Product"}


@st.cache_data
def best_promotions(store):
    """Try every single promotion (category or sub-category, every discount, windows of 1-3 months),
    then combine the best ones (one per target, up to 5) while the score improves and the budget holds."""
    import promo_engine as pe
    opt = pe.get_options(store)
    targets = [("sub_category", s["sub_category"]) for s in opt["sub_categories"]] + \
              [("category", c) for c in opt["categories"]]
    cands = []
    for kind, value in targets:
        for d in pe.DISCOUNT_LEVELS:
            for a in range(1, 13):
                for b in range(a, min(a + 3, 13)):
                    promo = {kind: value, "discount": d, "start_month": a, "end_month": b}
                    r = pe.run_promotions(store, [promo])
                    if r["ok"]:
                        cands.append((r["score"], -r["budget_used"], -(b - a), promo))
    cands.sort(key=lambda c: c[:3], reverse=True)
    chosen, best, used_targets = [], None, set()
    for _, _, _, promo in cands:
        key = next(k for k in TARGET_LABELS if k in promo), next(promo[k] for k in TARGET_LABELS if k in promo)
        if key in used_targets or len(chosen) == 5:
            continue
        r = pe.run_promotions(store, chosen + [promo])
        if r["ok"] and (best is None or r["score"] > best["score"]):
            chosen, best = chosen + [promo], r
            used_targets.add(key)
    single = cands[0][3] if cands else None
    return chosen, best, single, len(cands)


def describe(promo):
    kind = next(k for k in TARGET_LABELS if k in promo)
    a, b = MONTHS[promo["start_month"] - 1], MONTHS[promo["end_month"] - 1]
    return f"{promo['discount']:.0%} off {promo[kind]} ({a}{'' if a == b else '-' + b})"


with tabs[5]:
    if not (HERE / "promo_engine.py").exists():
        st.info("Put **promo_engine.py** (from Moodle) in this folder to test promotions.", icon=":material/schedule:")
    else:
        import promo_engine as pe
        st.markdown("#### Test promotions for 2020 before launching them")
        stores = pe.list_stores()
        default_store = f"{OUR_STORE}, California"
        store = st.selectbox("Store (the engine knows every city; ours is first)",
                             [default_store] + [s for s in stores if s != default_store])
        base = pe.baseline(store)
        opt = pe.get_options(store)
        k = st.columns(3)
        k[0].metric("2020 sales with no promotion", money(base["baseline_sales"]), border=True)
        k[1].metric("2020 profit with no promotion", money(base["baseline_profit"]), border=True)
        k[2].metric("Promotion budget (6% of sales)", money(base["budget_limit"]), border=True,
                    help="The total discount given away cannot be higher than this.")
        st.caption("Rules of the engine: up to 5 promotions, discount up to 40%, months 1 to 12 of 2020, and the total "
                   "cost must fit in the budget. The same inputs always give the same result.")

        # ---- Suggested plan ----
        with st.container(border=True):
            st.markdown("##### :material/auto_awesome: Suggested plan for this store")
            plan, plan_res, single, n_tested = best_promotions(store)
            if plan_res:
                st.markdown(f"We tested **{n_tested:,}** single promotions and combined the best ones:")
                st.markdown("\n".join(f"{i}. {describe(p)}" for i, p in enumerate(plan, 1)))
                c = st.columns(4)
                c[0].metric("Sales 2020", money(plan_res["new_sales"]), f"{plan_res['sales_increase_pct']:+.1f}%")
                c[1].metric("Profit 2020", money(plan_res["new_profit"]), f"{plan_res['profit_increase_pct']:+.1f}%")
                c[2].metric("Score", f"{plan_res['score']:.2f}")
                c[3].metric("Budget used", f"{money(plan_res['budget_used'])} of {money(plan_res['budget_limit'])}")
                if st.button("Load this plan in the simulator", icon=":material/download:"):
                    # new widget keys (version + 1) so every dropdown is rebuilt showing the plan
                    st.session_state["promo_ver"] = st.session_state.get("promo_ver", 0) + 1
                    st.session_state["promo_rows"] = plan
                    st.session_state["promo_n_input"] = len(plan)
                    st.rerun()

        # ---- Simulator with dropdowns ----
        st.markdown("##### :material/tune: Build your own promotions")
        subs = [s["sub_category"] for s in opt["sub_categories"]]
        prods = {p["label"]: p["product_id"] for p in opt["products"]}
        disc_labels = {d["label"]: d["value"] for d in opt["discounts"]}
        loaded = st.session_state.get("promo_rows", [])
        if "promo_n_input" not in st.session_state:
            st.session_state["promo_n_input"] = 1
        n = st.number_input("How many promotions?", 1, pe.MAX_PROMOTIONS, key="promo_n_input")
        ver = st.session_state.get("promo_ver", 0)
        promos = []
        for i in range(int(n)):
            pre = loaded[i] if i < len(loaded) else {"sub_category": subs[0], "discount": 0.10,
                                                      "start_month": 11, "end_month": 12}
            pre_kind = next(k for k in TARGET_LABELS if k in pre)
            c1, c2, c3, c4, c5 = st.columns([1.2, 2.4, 1, 1, 1])
            kind = c1.selectbox("Target", list(TARGET_LABELS), index=list(TARGET_LABELS).index(pre_kind),
                                format_func=TARGET_LABELS.get, key=f"kind{i}_{store}_{ver}")
            if kind == "sub_category":
                options = subs
            elif kind == "category":
                options = opt["categories"]
            else:
                options = list(prods)
            pre_val = pre.get(kind)
            if kind == "product":
                pre_val = next((lab for lab, pid in prods.items() if pid == pre_val), None)
            target = c2.selectbox(TARGET_LABELS[kind], options,
                                  index=options.index(pre_val) if pre_val in options else 0, key=f"t{i}_{kind}_{store}_{ver}")
            dl = list(disc_labels)
            pre_d = f"{round(pre['discount'] * 100)}%"
            disc = c3.selectbox("Discount", dl, index=dl.index(pre_d) if pre_d in dl else 1, key=f"d{i}_{store}_{ver}")
            a = c4.selectbox("Start month", range(1, 13), index=pre["start_month"] - 1,
                             format_func=lambda m: MONTHS[m - 1], key=f"a{i}_{store}_{ver}")
            b = c5.selectbox("End month", range(1, 13), index=pre["end_month"] - 1,
                             format_func=lambda m: MONTHS[m - 1], key=f"b{i}_{store}_{ver}")
            promos.append({kind: prods[target] if kind == "product" else target, "discount": disc_labels[disc],
                           "start_month": a, "end_month": b})

        res = pe.run_promotions(store, promos)
        if not res["ok"]:
            st.error("The engine refused these promotions:\n\n" + "\n".join(f"- {e}" for e in res["errors"]),
                     icon=":material/block:")
        else:
            c = st.columns(4)
            c[0].metric("Sales 2020", money(res["new_sales"]), f"{res['sales_increase_pct']:+.1f}%", border=True)
            c[1].metric("Profit 2020", money(res["new_profit"]), f"{res['profit_increase_pct']:+.1f}%", border=True)
            c[2].metric("Score", f"{res['score']:.2f}", border=True,
                        help="Half the sales increase plus half the profit increase (capped at ±100%).")
            c[3].metric("Budget used", f"{money(res['budget_used'])} of {money(res['budget_limit'])}", border=True)
            st.progress(min(res["budget_used"] / res["budget_limit"], 1.0) if res["budget_limit"] else 0.0)

            bm = pd.DataFrame(res["by_month"])
            bm["Month"] = bm.month.map(lambda m: MONTHS[m - 1])
            fig = px.bar(bm.melt(id_vars="Month", value_vars=["baseline_sales", "new_sales"]), x="Month", y="value",
                         color="variable", barmode="group",
                         color_discrete_map={"baseline_sales": "#9DC3F0", "new_sales": BLUE},
                         labels={"value": "Sales ($)", "Month": ""})
            fig.for_each_trace(lambda tr: tr.update(name={"baseline_sales": "No promotion",
                                                          "new_sales": "With promotions"}[tr.name]))
            st.plotly_chart(style(fig, height=340))
            st.caption("Promotions pull some demand forward: the months right after a promotion sell a bit less.")

            # ---- Phase 4 report: first dataset, second dataset, 2020 forecast ----
            st.markdown("##### :material/summarize: Report: how we do, from the first file to 2020")
            city_name = store.split(",")[0]
            o = original[original.City == city_name]
            n_ = new[new.City == city_name] if new is not None else None
            rows_r = [{"Period": "First file: 2014-2017 (average per year)", "Sales": o.Sales.sum() / 4,
                       "Profit": o.Profit.sum() / 4}]
            if n_ is not None:
                n2 = n_[n_.Order_year >= 2018]
                rows_r.append({"Period": "Second file: 2018-2019 (average per year)", "Sales": n2.Sales.sum() / 2,
                               "Profit": n2.Profit.sum() / 2})
            rows_r += [{"Period": "2020 forecast, no promotion", "Sales": res["baseline_sales"],
                        "Profit": res["baseline_profit"]},
                       {"Period": "2020 forecast, with our promotions", "Sales": res["new_sales"],
                        "Profit": res["new_profit"]}]
            rep = pd.DataFrame(rows_r)
            rep["Margin"] = rep.Profit / rep.Sales
            st.dataframe(rep.style.format(FMT).map(colour_profit, subset=["Profit"]), hide_index=True)
            fig = px.bar(rep.melt(id_vars="Period", value_vars=["Sales", "Profit"]), x="Period", y="value",
                         color="variable", barmode="group", color_discrete_sequence=[BLUE, GOOD],
                         labels={"value": "$", "Period": ""})
            st.plotly_chart(style(fig, height=360))
            text = ["# Superstore - promotion report", f"Store: {store}", "", "## Promotions"]
            text += [f"- {describe(p)}" for p in promos]
            text += ["", "## Results"] + [f"- {r.Period}: sales {money(r.Sales)}, profit {money(r.Profit)}, "
                                          f"margin {r.Margin:.0%}" for r in rep.itertuples()]
            text += [f"- Score {res['score']:.2f}; budget used {money(res['budget_used'])} of "
                     f"{money(res['budget_limit'])}"]
            st.download_button("Download this report", "\n".join(text), file_name="promotion_report.md",
                               icon=":material/download:")


# ---------- 6. City context (Phase 5: external data from APIs) ----------
with tabs[6]:
    st.markdown("#### What is happening around the store? Data from outside Superstore")
    st.caption("Population, household income and poverty: US Census Bureau (ACS 5-year) through the datausa.io API · "
               "Weather: open-meteo.com historical archive · Unemployment: api.census.gov (needs a free key).")
    if not EXT_OK:
        st.error(f"External data is not available (no internet and no saved copy): {EXT_ERROR}",
                 icon=":material/cloud_off:")
    else:
        full = summary(df, ["City", "State"]).merge(coords, on=["City", "State"], how="left")
        full["code"] = full.State.map(STATE_CODES)
        full = ex.match_cities(full, places)
        full["Sales per 1,000 people"] = full.Sales / full.Population * 1000
        known = full.dropna(subset=["Place ID"]).sort_values("Sales", ascending=False).copy()
        known["label"] = known.City + ", " + known.code
        focus_labels = [known[known.City == c].label.iloc[0] for c in FOCUS_CITIES]
        ours = known[known.City == OUR_STORE].label.iloc[0]
        order = [ours] + focus_labels + [x for x in known.label if x not in focus_labels + [ours]]
        label = st.selectbox("Choose a city (you can also pick the store you are allotted in Phase 3)", order)
        row = known[known.label == label].iloc[0]

        series, s_origin = ext_city(row["Place ID"])
        weather, w_origin, w_days, w_missing = ext_weather(float(row.lat), float(row.lon))
        store = df[(df.City == row.City) & (df.State == row.State)]
        yearly = store.groupby("Order_year").Sales.sum()
        s = series.set_index("Year")

        def val(col, year):
            return s.at[year, col] if year in s.index and pd.notna(s.at[year, col]) else None

        def growth(a, b):
            return b / a - 1 if a and b else None

        pop_g = growth(val("Population", 2014), val("Population", END))
        inc_g = growth(val("Median income", 2014), val("Median income", END))
        sales_g = growth(yearly.get(2014), yearly.get(END))

        k = st.columns(4)
        k[0].metric(f"Population ({END})", f"{val('Population', END):,.0f}" if val("Population", END) else "n/a",
                    f"{pop_g:+.1%} since 2014" if pop_g is not None else None, border=True)
        k[1].metric(f"Median household income ({END})",
                    money(val("Median income", END)) if val("Median income", END) else "n/a",
                    f"{inc_g:+.1%} since 2014" if inc_g is not None else None, border=True)
        pov1, pov0 = val("Poverty rate", END), val("Poverty rate", 2014)
        k[2].metric(f"Poverty rate ({END})", f"{pov1:.1%}" if pov1 is not None else "n/a",
                    f"{(pov1 - pov0) * 100:+.1f} pts since 2014" if pov1 is not None and pov0 is not None else None,
                    delta_color="inverse", border=True)
        big_cities = full[full.Population > 100_000]["Sales per 1,000 people"]
        k[3].metric("Store sales per 1,000 people", money(row["Sales per 1,000 people"]), border=True,
                    help=f"Total 2014-{END} sales divided by the 2017 population. "
                         f"Median for Superstore cities over 100,000 people: {money(big_cities.median())}.")

        if None not in (pop_g, inc_g, sales_g):
            if sales_g < pop_g:
                st.warning(f"**The market grew but the store did not.** From 2014 to {END} {row.City}'s population "
                           f"grew {pop_g:+.1%} and household income {inc_g:+.1%}, but the store's sales changed "
                           f"{sales_g:+.1%}.", icon=":material/trending_down:")
            else:
                st.success(f"**The store grew faster than its market.** From 2014 to {END} sales changed "
                           f"{sales_g:+.1%}, while population grew {pop_g:+.1%} and household income {inc_g:+.1%}.",
                           icon=":material/trending_up:")

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"##### How {row.City} is changing (2014 = 100)")
            ev = []
            for col, name in [("Population", "Population"), ("Median income", "Household income")]:
                if val(col, 2014):
                    ev.append(pd.DataFrame({"Year": s.index, "Series": name, "Index": s[col] / val(col, 2014) * 100,
                                            "Value": s[col].values}))
            if 2014 in yearly.index:
                ev.append(pd.DataFrame({"Year": yearly.index, "Series": "Store sales",
                                        "Index": yearly.values / yearly[2014] * 100, "Value": yearly.values}))
            if ev:
                ev = pd.concat(ev)
                fig = px.line(ev, x="Year", y="Index", color="Series", markers=True,
                              color_discrete_sequence=CATEGORY_COLOURS, hover_data={"Value": ":,.0f"},
                              labels={"Index": "Index (2014 = 100)", "Year": ""})
                fig.add_hline(y=100, line_color="#C9D1DC", line_width=1)
                fig.update_traces(line_width=2, marker_size=8)
                fig.update_xaxes(dtick=1)
                st.plotly_chart(style(fig, height=400))
                st.caption(f"How to read it: 120 means 20% more than in 2014. Store sales stop in {END} because the "
                           f"Superstore file ends there; population and income continue to 2024.")
        with right:
            st.markdown("##### Does the weather drive sales?")
            w = weather[(weather.Month >= "2014-01-01") & (weather.Month <= f"{END}-12-01")]
            ms = store.groupby(store["Order Date"].dt.to_period("M")).Sales.sum()
            ms.index = ms.index.to_timestamp()
            w = w.merge(ms.rename("Sales").rename_axis("Month").reset_index(), on="Month", how="left").fillna(
                {"Sales": 0})
            r_temp, r_rain = w["Temperature (°C)"].corr(w.Sales), w["Rain (mm)"].corr(w.Sales)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                subplot_titles=("Average temperature (°C)", "Store sales per month ($)"))
            fig.add_trace(go.Scatter(x=w.Month, y=w["Temperature (°C)"], mode="lines",
                                     line=dict(color="#EB6834", width=2),
                                     hovertemplate="%{x|%b %Y}: %{y:.1f} °C<extra></extra>"), 1, 1)
            fig.add_trace(go.Bar(x=w.Month, y=w.Sales, marker_color=BLUE,
                                 hovertemplate="%{x|%b %Y}: %{y:$,.0f}<extra></extra>"), 2, 1)
            style(fig, height=400, legend=False)
            fig.update_layout(margin=dict(t=28))
            fig.update_annotations(font=dict(size=13, color=INK, family="Fira Sans, sans-serif"), x=0,
                                   xanchor="left")
            st.plotly_chart(fig)
            strongest = max(abs(r_temp), abs(r_rain))
            verdict = ("Yes, clearly" if strongest >= 0.5 else "A little" if strongest >= 0.3 else
                       "No, almost not at all")
            peak_q = store.groupby(store["Order Date"].dt.quarter).Sales.sum().idxmax()
            st.caption(f"**{verdict}.** Correlation with temperature: {r_temp:.2f}; with rain: {r_rain:.2f} "
                       f"(0 = no link, 1 = perfect link). This store sells most in Q{peak_q}.")

        st.markdown("##### Our 4 cities with their market data")
        rows = []
        for c in FOCUS_CITIES:
            r = known[known.City == c].iloc[0]
            ss = ext_city(r["Place ID"])[0].set_index("Year")
            rows.append({"City": c, "Population": ss.at[END, "Population"],
                         "Median income": ss.at[END, "Median income"], "Poverty rate": ss.at[END, "Poverty rate"],
                         "Sales": r.Sales, "Profit": r.Profit, "Sales per 1,000 people": r["Sales per 1,000 people"]})
        four_ext = pd.DataFrame(rows)
        st.dataframe(four_ext.style.format(FMT).map(colour_profit, subset=["Profit"]), hide_index=True)
        hi, lo = four_ext.loc[four_ext["Sales per 1,000 people"].idxmax()], \
            four_ext.loc[four_ext["Sales per 1,000 people"].idxmin()]
        st.caption(f"{hi.City} sells {M(hi['Sales per 1,000 people'])} per 1,000 people; {lo.City} only "
                   f"{M(lo['Sales per 1,000 people'])}. Same chain, very different reach: {lo.City} is the biggest "
                   f"untapped market of the four. Sales and profit: 2014-{END}; market data: {END}.")

        key = census_key()
        st.markdown("##### Unemployment rate (census.gov)")
        unemp_check = None
        if key:
            try:
                un, u_origin = ext_unemployment(row["Place ID"], key)
                fig = px.line(un, x="Year", y="Unemployment rate", markers=True, color_discrete_sequence=[BLUE])
                fig.update_yaxes(tickformat=".0%")
                fig.update_xaxes(dtick=1)
                st.plotly_chart(style(fig, height=300, legend=False))
                unemp_check = ex.check("api.census.gov (ACS B23025)", f"Unemployment rate · {row.City}", un,
                                       range(2014, 2018), origin=u_origin)
            except Exception as err:
                st.error(f"census.gov did not answer: {err}", icon=":material/cloud_off:")
        else:
            st.info("census.gov now asks for a free API key. Get one at api.census.gov/data/key_signup.html and add "
                    "`CENSUS_API_KEY = \"your key\"` to `.streamlit/secrets.toml`; this chart then appears. "
                    "Income and poverty above already come from the same Census survey (ACS), served by datausa.io.",
                    icon=":material/key:")

        st.markdown("##### Is the external data complete?")
        not_found = full[full.Match == "not found"]
        covered = full[full.Match != "not found"].Sales.sum() / full.Sales.sum()
        checks = [
            {"Source": "datausa.io (US Census ACS)", "Data": f"Population of every US place ({ex.MAP_YEAR})",
             "Rows": len(places), "Covers": str(ex.MAP_YEAR), "Missing years": "none",
             "Missing values": int(places.Population.isna().sum()),
             "Status": "Complete" + (" (offline copy)" if places_origin == "cache" else ""),
             "Notes": f"{len(full) - len(not_found)} of {len(full)} Superstore cities matched "
                      f"({int(full.Match.eq('approximate').sum())} by approximate name), {covered:.1%} of sales"},
            ex.check("datausa.io (US Census ACS)", f"Population, income, poverty · {row.City}", series,
                     range(2014, 2018), origin=s_origin),
            ex.check("open-meteo.com", f"Monthly weather · {row.City}", weather.assign(Year=weather.Month.dt.year)
                     .drop(columns="Month"), range(2014, 2020), origin=w_origin,
                     extra=f"{w_days:,} daily records, {w_missing} with gaps"),
            unemp_check or {"Source": "api.census.gov", "Data": "Unemployment rate", "Rows": 0, "Covers": "-",
                            "Missing years": "-", "Missing values": 0, "Status": "Not collected",
                            "Notes": "Needs a free census.gov API key"},
        ]
        st.dataframe(pd.DataFrame(checks).style.map(
            lambda v: f"color: {GOOD if str(v).startswith('Complete') else CRITICAL}; font-weight: 600",
            subset=["Status"]), hide_index=True)
        if not not_found.empty:
            st.caption("Cities without a Census match (towns and townships that the Census does not count as 'places'): "
                       + ", ".join(not_found.City + ", " + not_found.code) + ".")
