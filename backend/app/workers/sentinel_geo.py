"""Map Sentinel evaluation camera labels to approximate Gujarat coordinates (GIS)."""

from __future__ import annotations

CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "Ahmedabad": (23.0225, 72.5714),
    "Gandhinagar": (23.2156, 72.6369),
    "Junagadh": (21.5222, 70.4579),
    "Somnath": (20.8880, 70.4012),
    "Rajkot": (22.3039, 70.8022),
    "Navsari": (20.9517, 72.9324),
    "Gandevi": (20.8126, 72.9981),
    "Patan": (23.8493, 72.1266),
    "Dehgam": (23.1700, 72.8200),
    "Bilimora": (20.7696, 72.9614),
    "Gandhidham": (23.0753, 70.1337),
    "Adalaj": (23.1645, 72.5810),
}

# keyword (lowercase) -> (lat, lon, city)
KEYWORDS: list[tuple[str, float, float, str]] = [
    ("chiman", 23.0218, 72.5718, "Ahmedabad"),
    ("janpath", 23.0229, 72.5622, "Ahmedabad"),
    ("o.n.g.c", 23.0355, 72.5088, "Ahmedabad"),
    ("ongc", 23.0355, 72.5088, "Ahmedabad"),
    ("paldi", 23.0116, 72.5634, "Ahmedabad"),
    ("visat", 23.0724, 72.5809, "Ahmedabad"),
    ("cn vidhyalaya", 23.0398, 72.5495, "Ahmedabad"),
    ("delight", 23.0410, 72.5620, "Ahmedabad"),
    ("suvidha", 23.0550, 72.5480, "Ahmedabad"),
    ("adalaj", 23.1645, 72.5810, "Adalaj"),
    ("timbavadi", 21.5285, 70.4490, "Junagadh"),
    ("majewadi", 21.5310, 70.4705, "Junagadh"),
    ("bypass", 21.5450, 70.4650, "Junagadh"),
    ("char-chowk", 21.5228, 70.4570, "Junagadh"),
    ("dolatpara", 21.5355, 70.4520, "Junagadh"),
    ("junagadh", 21.5222, 70.4579, "Junagadh"),
    ("gir-somnath", 20.8880, 70.4012, "Somnath"),
    ("hero-showroom", 20.8880, 70.4012, "Somnath"),
    ("rajkot", 22.3039, 70.8022, "Rajkot"),
    ("gandevi", 20.8126, 72.9981, "Gandevi"),
    ("navsari", 20.9517, 72.9324, "Navsari"),
    ("khaparia", 20.8126, 72.9981, "Gandevi"),
    ("mohanpura", 23.2156, 72.6369, "Gandhinagar"),
    ("patan", 23.8493, 72.1266, "Patan"),
    ("dethali", 23.8493, 72.1266, "Patan"),
    ("mervada", 23.2156, 72.6369, "Gandhinagar"),
    ("kheram", 23.2156, 72.6369, "Gandhinagar"),
    ("dehgam", 23.1700, 72.8200, "Dehgam"),
    ("dhanori", 23.2156, 72.6369, "Gandhinagar"),
    ("tankal", 20.7700, 72.9600, "Bilimora"),
    ("bilimora", 20.7696, 72.9614, "Bilimora"),
    ("gandhidham", 23.0753, 70.1337, "Gandhidham"),
    ("rambaugh", 23.0753, 70.1337, "Gandhidham"),
    ("testing", 23.2156, 72.6369, "Gandhinagar"),
]


def geocode(location: str) -> tuple[float, float, str]:
    blob = (location or "").lower()
    for key, lat, lon, city in KEYWORDS:
        if key in blob:
            return lat, lon, city
    return 23.0225, 72.5714, "Ahmedabad"
