import os
import requests
import json
import pandas as pd
import streamlit as st
import time
from dashboard.plot import price_trend

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config("AgentCloud Dashboard", layout="wide")

# Sidebar controls
with st.sidebar:
    st.title("Dashboard Controls")
    refresh = st.toggle("Auto-refresh (5s)", value=False)
    n_quotes = st.slider("Rows", 10, 50, 20)

st.title("🤖 AgentCloud - Live Quote Feed")


@st.cache_data(ttl=5)
def fetch_quotes(n: int = 20):
    """Fetch recent quotes from the API with caching."""
    try:
        resp = requests.get(f"{API_BASE}/quotes/recent?limit={n}", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if not data:  # If no quotes exist yet
            st.info("No quotes found. Create some quotes to see them here.")
            return pd.DataFrame()

        # Convert to DataFrame and format columns
        df = pd.DataFrame(data)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["price"] = df["price"].apply(lambda x: f"${x:.2f}")
        df["buyer_max_price"] = df["buyer_max_price"].apply(lambda x: f"${x:.2f}")

        # Sort columns for better display
        columns = [
            "id",
            "resource_type",
            "duration_hours",
            "price",
            "buyer_max_price",
            "status",
            "created_at",
            "buyer_id",
            "negotiation_log",
            "transactions",
        ]
        return df[columns]
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch quotes: {str(e)}")
        if hasattr(e.response, "text"):
            st.error(f"Error details: {e.response.text}")
        return pd.DataFrame()


# Auto-refresh loop
while True:
    # Fetch data
    df = fetch_quotes(n_quotes)

    # Display interactive dataframe
    if not df.empty:
        selected_quotes = st.dataframe(
            df,
            use_container_width=True,
            height=400,
            column_config={
                "id": "Quote ID",
                "resource_type": "Resource",
                "duration_hours": "Duration (hrs)",
                "price": "Price",
                "buyer_max_price": "Max Price",
                "status": "Status",
                "created_at": "Created At",
                "buyer_id": "Buyer ID",
                "negotiation_log": None,  # Hide this column
                "transactions": None,  # Hide this column
            },
            hide_index=True,  # Hide the index column
            on_select="rerun",
            selection_mode="single-row",
            key="quote_table",
        )

        # Handle row selection
        if selected_quotes.selection["rows"]:
            # Get the selected quote
            quote_id = df.iloc[selected_quotes.selection["rows"][0]]["id"]
            quote_row = df[df["id"] == quote_id]
            if not quote_row.empty:
                q = quote_row.iloc[0].to_dict()
                st.subheader(f"Quote {q['id']} details")
                st.write(
                    f"**Status:** {q['status']} • **Price:** {q['price']} • **Max Price:** {q['buyer_max_price']}"
                )

                # Add Replay button
                if st.button("Replay negotiation"):

                    @st.dialog(f"Negotiation log - Quote {q['id']}")
                    def show_negotiation():
                        log = (
                            json.loads(q["negotiation_log"])
                            if isinstance(q["negotiation_log"], str)
                            else q["negotiation_log"]
                        )
                        total_turns = len(log)

                        for i, turn in enumerate(log):
                            st.markdown(
                                f"**Turn {i+1}**: {turn['role']} → ${turn['price']}"
                            )
                            st.progress((i + 1) / total_turns)
                            time.sleep(0.5)  # Add delay for animation effect

                    show_negotiation()  # Call the decorated function

                # Display negotiation log as expandable JSON
                if q["negotiation_log"]:
                    st.subheader("Negotiation Log")
                    st.json(
                        (
                            json.loads(q["negotiation_log"])
                            if isinstance(q["negotiation_log"], str)
                            else q["negotiation_log"]
                        ),
                        expanded=False,
                    )

                # Display transactions if any
                if q["transactions"]:
                    st.subheader("Transactions")
                    for tx in q["transactions"]:
                        st.write(
                            f"- {tx['provider'].upper()}: {tx['status']} (${tx['amount_usd']:.2f})"
                        )
            else:
                st.error(f"Quote ID {quote_id} not found")

    else:
        st.info("No quotes found. Create some quotes to see them here.")

    # Add price trend visualization
    st.divider()
    st.subheader("Price Trend")
    price_trend(df[::-1])  # Reverse order for oldest → newest

    # Handle auto-refresh
    if not refresh:
        break
    time.sleep(5)
    st.experimental_rerun()
