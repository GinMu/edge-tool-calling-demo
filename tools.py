"""Ethereum transfer tool - builds transaction data structure."""

import json
from pathlib import Path
from edgestudio.tools import edge_tool


def _load_facts_store():
    """Load the facts store from eth-facts-v4.json."""
    facts_path = Path(__file__).parent / "eth-facts-v4.json"
    with open(facts_path) as f:
        return json.load(f)


@edge_tool(
    description=(
        "Query the Ethereum research facts store for risk addresses. "
        "Returns facts with topic='risk address known' from ethereum_research_v1 store."
    ),
    intent_tags=["facts", "lookup", "risk"],
)
def facts_lookup(topic: str = "risk address known") -> dict:
    """Query the facts store for information about Ethereum addresses.

    Retrieves facts from ethereum_research_v1 store filtered by topic.
    Use this to get current risk addresses before building transfers.

    Args:
        topic: Topic filter for facts (default: 'risk address known').

    Returns:
        dict containing matching facts and metadata about the query.
    """
    facts_store = _load_facts_store()
    matching_facts = [
        fact for fact in facts_store.get("facts", [])
        if fact.get("topic") == topic
    ]
    return {
        "store": facts_store.get("store"),
        "topic_queried": topic,
        "facts_count": len(matching_facts),
        "facts": matching_facts,
        "message": f"Found {len(matching_facts)} facts with topic='{topic}'",
    }


@edge_tool(
    description=(
        "Build an Ethereum transfer transaction data structure. "
        "AI must verify destination address is safe before calling."
    ),
    intent_tags=["transfer", "build_tx"],
)
def build_transfer(to: str) -> dict:
    """Build a transfer transaction data structure.

    Constructs transaction data for a given destination address.
    Risk verification should be completed by AI before calling this tool.

    Args:
        to: Destination Ethereum address (0x-prefixed, 42 characters).

    Returns:
        dict with transaction data structure ready for further processing.
    """
    return {
        "transaction": {
            "to": to,
            "type": "eth_transfer",
            "status": "prepared",
        },
        "message": "Transaction data structure built. Ready for AI review and broadcasting.",
    }

