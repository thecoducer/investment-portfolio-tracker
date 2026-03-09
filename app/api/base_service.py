"""
Base service with common functionality for all data services.
"""

from typing import Any


class BaseDataService:
    """Base class for data services with common operations."""

    def add_account_info(self, items: list[dict[str, Any]], account_name: str) -> None:
        """
        Add account name to data items.

        Args:
            items: List of data items to enrich
            account_name: Name of the account
        """
        for item in items:
            item["account"] = account_name

    def merge_items(self, all_items: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        """
        Merge items from multiple accounts.

        Args:
            all_items: List of item lists from different accounts

        Returns:
            Merged list of all items
        """
        return [item for items in all_items for item in items]
