import matplotlib.pyplot as plt
import streamlit as st


def price_trend(df):
    """Plot price trend over time for quotes."""
    if df.empty:
        return

    # Convert price strings to float
    df = df.copy()
    df["price"] = df["price"].str.replace("$", "").astype(float)

    fig, ax = plt.subplots()
    ax.plot(df["created_at"], df["price"], marker="o")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price (USD)")
    ax.set_title("Quote Price Trend – Last N")

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)
    plt.tight_layout()

    st.pyplot(fig, clear_figure=True)
