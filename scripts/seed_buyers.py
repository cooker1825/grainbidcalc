"""Seed initial buyer records from buyer_profiles."""

from db.connection import get_client
from parsing.buyer_profiles import BUYER_PROFILES


def seed_buyers():
    client = get_client()
    for short_name, profile in BUYER_PROFILES.items():
        client.table("buyers").upsert({
            "short_name": short_name,
            "name": profile["name"],
            "source_type": "email",
            "notes": profile.get("format_hints", ""),
        }, on_conflict="short_name").execute()
        print(f"Seeded buyer: {profile['name']}")


if __name__ == "__main__":
    seed_buyers()
