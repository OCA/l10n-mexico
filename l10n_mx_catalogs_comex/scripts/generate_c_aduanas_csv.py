# -*- coding: utf-8 -*-

import csv
import requests
from bs4 import BeautifulSoup

URL = "https://www.censecar.com.mx/listado-de-aduanas-de-mexico"

response = requests.get(URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

rows = []

table_rows = soup.find_all("tr")

for tr in table_rows:
    cols = tr.find_all("td")

    if len(cols) != 4:
        continue

    code = cols[0].get_text(strip=True)
    name = cols[1].get_text(strip=True)
    city = cols[2].get_text(strip=True)
    state = cols[3].get_text(strip=True)

    if not code:
        continue

    rows.append({
        "id": f"c_aduana_{code}",
        "code": code,
        "name": name,
        "city": city,
        "state": state,
        "active": "True",
    })

with open("../data/l10n_mx_catalogs.c_aduana.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "id",
            "code",
            "name",
            "city",
            "state",
            "active",
        ],
    )

    writer.writeheader()
    writer.writerows(rows)

print(f"Generados {len(rows)} registros")
