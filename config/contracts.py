"""
Futures contract normalization rules and reference data.
See CLAUDE.md for the full normalization table.
"""

# Month code → month number
MONTH_CODES = {
    "F": "01", "G": "02", "H": "03", "J": "04", "K": "05", "M": "06",
    "N": "07", "Q": "08", "U": "09", "V": "10", "X": "11", "Z": "12",
}

# Standard futures prefixes by commodity
CONTRACT_PREFIXES = {
    "soybeans":      "ZS",
    "corn":          "ZC",
    "srw_wheat":     "ZW",
    "hrw_wheat":     "KE",
    "swr_wheat":     "ZW",
    "wheat_general": "ZW",
    "canola":        "RS",
}

# Great Lakes format commodity map: @C → ZC
GREAT_LAKES_PREFIX_MAP = {"C": "ZC", "S": "ZS", "W": "ZW"}

# Active contracts to monitor (update seasonally)
ACTIVE_CONTRACTS = [
    "ZSH26", "ZSK26", "ZSN26", "ZSX26",   # Soybeans
    "ZCH26", "ZCK26", "ZCN26", "ZCZ26",   # Corn
    "ZWH26", "ZWN26", "ZWZ26",             # Wheat
    "RSK26", "RSN26", "RSX26",             # Canola
]
