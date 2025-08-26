import json
import os
import time

import pandas as pd
import requests
import streamlit as st

from plot import price_trend

API_BASE = os.getenv("API_BASE", "http://api:8000")
DEMO_MODE = os.getenv("DEMO_MODE", "").lower() in {"1", "true", "yes"}


def _format_negotiation_turn(turn: dict, turn_number: int) -> str:
    """
    Format a negotiation turn for display with robust parsing.

    Handles both buyer responses (simple strings) and seller responses (nested objects).

    Args:
        turn: Dictionary containing turn data
        turn_number: The turn number for display

    Returns:
        Formatted string for display
    """
    role = turn.get("role", "unknown")

    try:
        if role == "seller":
            # Seller responses can be either nested objects or simple values
            price = _extract_seller_price(turn)
            action = _extract_seller_action(turn)
            reason = _extract_seller_reason(turn)

            price_str = f"${price:.2f}" if price is not None else "N/A"
            reason_str = f" - {reason}" if reason else ""

            return f"<strong>Turn {turn_number}</strong>: {role} → {price_str} ({action}){reason_str}"

        elif role == "buyer":
            # Buyer responses are typically simple strings or nested objects
            response, action = _extract_buyer_response(turn)
            reason = _extract_buyer_reason(turn)

            # Try to format as price if it's numeric
            try:
                price_val = float(response) if response != "accept" else None
                response_str = (
                    f"${price_val:.2f}" if price_val is not None else response
                )
            except (ValueError, TypeError):
                response_str = str(response)

            action_str = f" ({action})" if action and action != response else ""
            reason_str = f" - {reason}" if reason else ""

            return f"<strong>Turn {turn_number}</strong>: {role} → {response_str}{action_str}{reason_str}"

        else:
            # Fallback for unknown turn types
            action = turn.get("action", "unknown")
            response = turn.get("response", turn.get("price", "N/A"))

            return (
                f"<strong>Turn {turn_number}</strong>: {role} → {response} ({action})"
            )

    except Exception as e:
        # Robust error handling - always return something meaningful
        return (
            f"<strong>Turn {turn_number}</strong>: {role} → [parsing error: {str(e)}]"
        )


def _extract_seller_price(turn: dict) -> float | None:
    """Extract price from seller turn with multiple fallback strategies."""
    response = turn.get("response")

    # Strategy 1: Nested object response (new format)
    if isinstance(response, dict):
        price = response.get("price")
        if price is not None:
            return float(price)

    # Strategy 2: Direct price field (fallback format)
    direct_price = turn.get("price")
    if direct_price is not None:
        try:
            return float(direct_price)
        except (ValueError, TypeError):
            pass

    # Strategy 3: Simple response value (if it's numeric)
    if isinstance(response, (int, float)):
        return float(response)

    return None


def _extract_seller_action(turn: dict) -> str:
    """Extract action from seller turn with fallback strategies."""
    response = turn.get("response")

    # Strategy 1: Nested object response
    if isinstance(response, dict):
        action = response.get("action")
        if action:
            return str(action)

    # Strategy 2: Direct action field
    action = turn.get("action")
    if action:
        return str(action)

    return "quote"  # Default fallback


def _extract_seller_reason(turn: dict) -> str | None:
    """Extract reasoning from seller turn."""
    response = turn.get("response")

    if isinstance(response, dict):
        reason = response.get("reason")
        if reason:
            return str(reason)

    # Fallback to reasoning field
    reasoning = turn.get("reasoning")
    if reasoning:
        return str(reasoning)

    return None


def _extract_buyer_response(turn: dict) -> tuple[str, str | None]:
    """
    Extract response and action from buyer turn.

    Returns:
        Tuple of (response, action)
    """
    response = turn.get("response")
    action = turn.get("action")

    # Handle nested response object (if buyer format changes)
    if isinstance(response, dict):
        actual_response = response.get("price", response.get("action", "N/A"))
        actual_action = response.get("action", action)
        return str(actual_response), actual_action

    # Handle simple response (current buyer format)
    if response is not None:
        return str(response), action

    # Fallback
    return "N/A", action


def _extract_buyer_reason(turn: dict) -> str | None:
    """Extract reasoning from buyer turn."""
    # Check for reason in the response object (new format)
    response = turn.get("response")
    if isinstance(response, dict):
        reason = response.get("reason")
        if reason:
            return str(reason)

    # Check for direct reason field in turn
    reason = turn.get("reason")
    if reason:
        return str(reason)

    return None


st.set_page_config("AgentCloud Dashboard", layout="wide")

# Add custom CSS for better font rendering in negotiation log
st.markdown(
    """
<style>
.negotiation-turn {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 8px;
    margin: 4px 0;
    border-left: 3px solid #0066cc;
    background-color: #f8f9fa;
    border-radius: 4px;
}

.stMarkdown p {
    font-family: 'Helvetica Neue', Arial, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}

/* Fix font consistency for negotiation display */
.negotiation-display {
    font-family: 'Helvetica Neue', Arial, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
}

/* Keep JSON display in monospace but separate from negotiation text */
.negotiation-log {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.5;
}
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar controls
with st.sidebar:
    st.title("Dashboard Controls")
    refresh = st.toggle("Auto-refresh (5s)", value=False)
    n_quotes = st.slider("Rows", 10, 50, 20)

st.title("🤖 AgentCloud - Live Quote Feed")
if DEMO_MODE:
    with st.sidebar:
        st.subheader("Demo actions")
        if st.button("Create demo quote"):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/v1/quotes/request",
                    json={
                        "buyer_id": "demo_ui",
                        "resource_type": "GPU",
                        "duration_hours": 2,
                        "buyer_max_price": 12.0,
                    },
                    timeout=5,
                )
                if resp.status_code == 201:
                    st.success("Demo quote created")
                else:
                    st.error(f"Failed to create demo quote: {resp.text}")
            except Exception as e:
                st.error(f"Error: {str(e)}")


@st.cache_data(ttl=5)
def fetch_quotes(n: int = 20):
    """Fetch recent quotes from the API with caching."""
    try:
        resp = requests.get(f"{API_BASE}/api/v1/quotes/recent?limit={n}", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        if not data:  # If no quotes exist yet
            st.info("No quotes found. Create some quotes to see them here.")
            return pd.DataFrame(), []

        # Convert to DataFrame and format columns
        df = pd.DataFrame(data)
        df["created_at"] = pd.to_datetime(df["created_at"])

        # Handle price formatting with None values
        df["price"] = df["price"].apply(
            lambda x: f"${x:.2f}" if x is not None else "N/A"
        )
        df["buyer_max_price"] = df["buyer_max_price"].apply(
            lambda x: f"${x:.2f}" if x is not None else "N/A"
        )

        # Convert complex objects to strings for display compatibility
        df["negotiation_log"] = df["negotiation_log"].apply(
            lambda x: str(x) if x else "[]"
        )
        df["transactions"] = df["transactions"].apply(lambda x: str(x) if x else "[]")

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
        return df[columns], data  # Return both processed DataFrame and raw data
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch quotes: {str(e)}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            st.error(f"Error details: {e.response.text}")
        return pd.DataFrame(), []
    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return pd.DataFrame(), []


# Auto-refresh loop
while True:
    # Fetch data
    df, raw_data = fetch_quotes(n_quotes)

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
            # Get the selected quote ID
            quote_id = df.iloc[selected_quotes.selection["rows"][0]]["id"]

            # Find the raw data for this quote
            selected_quote_raw = next(
                (q for q in raw_data if q["id"] == quote_id), None
            )

            if selected_quote_raw:
                st.subheader(f"Quote {selected_quote_raw['id']} details")
                price_str = (
                    f"${selected_quote_raw['price']:.2f}"
                    if selected_quote_raw["price"] is not None
                    else "N/A"
                )
                max_price_str = (
                    f"${selected_quote_raw['buyer_max_price']:.2f}"
                    if selected_quote_raw["buyer_max_price"] is not None
                    else "N/A"
                )
                st.write(
                    f"**Status:** {selected_quote_raw['status']} • **Price:** {price_str} • **Max Price:** {max_price_str}"
                )

                # Add Replay button
                if st.button("Replay negotiation"):

                    @st.dialog(f"Negotiation log - Quote {selected_quote_raw['id']}")
                    def show_negotiation():
                        log = selected_quote_raw.get("negotiation_log", [])
                        if not log:
                            st.info("No negotiation log available")
                            return

                        total_turns = len(log)

                        for i, turn in enumerate(log):
                            display_text = _format_negotiation_turn(turn, i + 1)
                            # Use consistent font styling for negotiation display
                            st.markdown(
                                f'<div class="negotiation-display">{display_text}</div>',
                                unsafe_allow_html=True,
                            )
                            st.progress((i + 1) / total_turns)
                            time.sleep(0.5)  # Add delay for animation effect

                    show_negotiation()  # Call the decorated function

                # Display negotiation log as expandable JSON
                if selected_quote_raw.get("negotiation_log"):
                    st.subheader("Negotiation Log")
                    st.markdown('<div class="negotiation-log">', unsafe_allow_html=True)
                    st.json(
                        (
                            json.loads(selected_quote_raw["negotiation_log"])
                            if isinstance(selected_quote_raw["negotiation_log"], str)
                            else selected_quote_raw["negotiation_log"]
                        ),
                        expanded=False,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                # Display transactions if any
                if selected_quote_raw.get("transactions"):
                    st.subheader("Transactions")
                    for tx in selected_quote_raw["transactions"]:
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
    st.rerun()
