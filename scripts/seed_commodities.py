"""Seed commodity records."""

from db.connection import get_client
from config.commodities import COMMODITIES


def seed_commodities():
    client = get_client()
    for commodity in COMMODITIES:
        client.table("commodities").upsert(
            commodity, on_conflict="name"
        ).execute()
        print(f"Seeded commodity: {commodity['display_name']}")


if __name__ == "__main__":
    seed_commodities()
