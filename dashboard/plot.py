import matplotlib.pyplot as plt
import streamlit as st


def price_trend(df):
    """Plot price trend over time for quotes."""
    if df.empty:
        st.info("No data available for price trend")
        return

    try:
        # Convert price strings to float, handling None and "N/A" values
        df = df.copy()

        # Filter out rows where price is None, "N/A", or invalid
        df = df[df["price"].notna()]  # Remove NaN values
        df = df[df["price"] != "N/A"]  # Remove "N/A" values

        if df.empty:
            st.info("No valid price data available for trend")
            return

        # Convert price strings to float (remove $ sign)
        df["price"] = df["price"].str.replace("$", "").astype(float)

        # Sort by created_at for proper trend line
        df = df.sort_values("created_at")

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df["created_at"], df["price"], marker="o", linewidth=2, markersize=6)
        ax.set_xlabel("Time")
        ax.set_ylabel("Price (USD)")
        ax.set_title("Quote Price Trend – Last N")

        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45)
        plt.tight_layout()

        st.pyplot(fig, clear_figure=True)

    except Exception as e:
        st.error(f"Error creating price trend plot: {str(e)}")
        st.info("Unable to display price trend at this time")
