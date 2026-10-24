"""City-level gazetteer. Incidents are only ever placed at these coarse points, never at street level."""

NATIONWIDE = "Nationwide"

# name -> (latitude, longitude, province)
GAZETTEER: dict[str, tuple[float, float, str]] = {
    "Kathmandu": (27.7172, 85.3240, "Bagmati"),
    "Lalitpur": (27.6588, 85.3247, "Bagmati"),
    "Bhaktapur": (27.6710, 85.4298, "Bagmati"),
    "Hetauda": (27.4287, 85.0322, "Bagmati"),
    "Bharatpur": (27.6833, 84.4333, "Bagmati"),
    "Pokhara": (28.2096, 83.9856, "Gandaki"),
    "Butwal": (27.7006, 83.4483, "Lumbini"),
    "Bhairahawa": (27.5000, 83.4500, "Lumbini"),
    "Nepalgunj": (28.0500, 81.6167, "Lumbini"),
    "Surkhet": (28.6019, 81.6339, "Karnali"),
    "Dhangadhi": (28.6833, 80.6000, "Sudurpashchim"),
    "Birgunj": (27.0104, 84.8770, "Madhesh"),
    "Simara": (27.1590, 84.9800, "Madhesh"),
    "Janakpur": (26.7288, 85.9260, "Madhesh"),
    "Biratnagar": (26.4525, 87.2718, "Koshi"),
    "Itahari": (26.6650, 87.2790, "Koshi"),
    "Dharan": (26.8065, 87.2846, "Koshi"),
}
