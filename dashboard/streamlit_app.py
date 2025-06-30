import os
import requests
import json
import pandas as pd
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config("AgentCloud Dashboard", layout="wide")
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


# Fetch initial data
df = fetch_quotes()

# Display interactive dataframe
if not df.empty:
    selected = st.dataframe(
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
    )

    # Handle row selection
    sel_rows = st.session_state.get("dataframe-row-selected-indices", [])
    if sel_rows:
        q = df.iloc[sel_rows[0]].to_dict()
        st.subheader(f"Quote {q['id']} details")
        st.write(
            f"**Status:** {q['status']} • **Price:** {q['price']} • **Max Price:** {q['buyer_max_price']}"
        )

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
    st.info("No quotes found. Create some quotes to see them here.")
