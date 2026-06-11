import json, math

# Elo values extracted from https://www.eloratings.net/World.tsv (fetched 2026-06-10)
# key = eloratings.net 2-letter code
elo_raw = {
 "ES":2157,"AR":2114,"FR":2063,"EN":2021,"BR":1991,"PT":1986,"CO":1982,"NL":1948,
 "EC":1938,"DE":1932,"NO":1914,"HR":1911,"TR":1910,"JP":1906,"BE":1893,"UY":1892,
 "CH":1891,"MX":1875,"SN":1867,"PY":1833,"AT":1830,"MA":1827,"CA":1788,"SQ":1782,
 "AU":1777,"IR":1772,"DZ":1760,"KR":1758,"CZ":1740,"PA":1730,"US":1726,"UZ":1714,
 "SE":1712,"JO":1680,"EG":1696,"CI":1695,"CD":1661,"IQ":1618,"TN":1628,"BA":1595,
 "CV":1578,"SA":1569,"NZ":1562,"HT":1548,"ZA":1518,"GH":1510,"CW":1434,"QA":1421,
}

# name -> (FIFA trigram, eloratings code, confederation)
teams = {
 "Mexico":("MEX","MX","CONCACAF"), "South Korea":("KOR","KR","AFC"),
 "Czech Republic":("CZE","CZ","UEFA"), "South Africa":("RSA","ZA","CAF"),
 "Switzerland":("SUI","CH","UEFA"), "Canada":("CAN","CA","CONCACAF"),
 "Qatar":("QAT","QA","AFC"), "Bosnia and Herzegovina":("BIH","BA","UEFA"),
 "Brazil":("BRA","BR","CONMEBOL"), "Morocco":("MAR","MA","CAF"),
 "Scotland":("SCO","SQ","UEFA"), "Haiti":("HAI","HT","CONCACAF"),
 "United States":("USA","US","CONCACAF"), "Turkey":("TUR","TR","UEFA"),
 "Australia":("AUS","AU","AFC"), "Paraguay":("PAR","PY","CONMEBOL"),
 "Germany":("GER","DE","UEFA"), "Ecuador":("ECU","EC","CONMEBOL"),
 "Ivory Coast":("CIV","CI","CAF"), "Curacao":("CUW","CW","CONCACAF"),
 "Netherlands":("NED","NL","UEFA"), "Japan":("JPN","JP","AFC"),
 "Sweden":("SWE","SE","UEFA"), "Tunisia":("TUN","TN","CAF"),
 "Belgium":("BEL","BE","UEFA"), "Iran":("IRN","IR","AFC"),
 "Egypt":("EGY","EG","CAF"), "New Zealand":("NZL","NZ","OFC"),
 "Spain":("ESP","ES","UEFA"), "Uruguay":("URU","UY","CONMEBOL"),
 "Saudi Arabia":("KSA","SA","AFC"), "Cape Verde":("CPV","CV","CAF"),
 "France":("FRA","FR","UEFA"), "Senegal":("SEN","SN","CAF"),
 "Norway":("NOR","NO","UEFA"), "Iraq":("IRQ","IQ","AFC"),
 "Argentina":("ARG","AR","CONMEBOL"), "Austria":("AUT","AT","UEFA"),
 "Algeria":("ALG","DZ","CAF"), "Jordan":("JOR","JO","AFC"),
 "Portugal":("POR","PT","UEFA"), "Colombia":("COL","CO","CONMEBOL"),
 "DR Congo":("COD","CD","CAF"), "Uzbekistan":("UZB","UZ","AFC"),
 "England":("ENG","EN","UEFA"), "Croatia":("CRO","HR","UEFA"),
 "Panama":("PAN","PA","CONCACAF"), "Ghana":("GHA","GH","CAF"),
}

groups = {
 "A":["Mexico","South Korea","Czech Republic","South Africa"],
 "B":["Switzerland","Canada","Qatar","Bosnia and Herzegovina"],
 "C":["Brazil","Morocco","Scotland","Haiti"],
 "D":["United States","Turkey","Australia","Paraguay"],
 "E":["Germany","Ecuador","Ivory Coast","Curacao"],
 "F":["Netherlands","Japan","Sweden","Tunisia"],
 "G":["Belgium","Iran","Egypt","New Zealand"],
 "H":["Spain","Uruguay","Saudi Arabia","Cape Verde"],
 "I":["France","Senegal","Norway","Iraq"],
 "J":["Argentina","Austria","Algeria","Jordan"],
 "K":["Portugal","Colombia","DR Congo","Uzbekistan"],
 "L":["England","Croatia","Panama","Ghana"],
}
name_to_group = {n:g for g,members in groups.items() for n in members}

# --- Elo -> attack/defense transformation ---
# Mean Elo of the 48-team field defines the "average WC team" baseline.
mean_elo = sum(elo_raw[t[1]] for t in teams.values()) / len(teams)
LEAGUE_AVG_GOALS = 1.35   # avg goals per team per match (recent WC group stages ~2.5-2.8 total)
K = 0.25                  # tuned: K=0.45 gave absurd 8.8 xG for max-mismatch; 0.25 keeps extremes ~4 xG

def strengths(elo):
    rel = (elo - mean_elo) / 400.0
    attack  = round(10 ** ( rel * K), 3)   # multiplier >1 if above average
    defense = round(10 ** (-rel * K), 3)   # multiplier <1 if above average (concede less)
    return attack, defense

out = {}
for name,(fifa,ecode,conf) in teams.items():
    elo = elo_raw[ecode]
    atk, dfn = strengths(elo)
    out[fifa] = {
        "team_id": fifa, "name": name, "group": name_to_group[name],
        "confederation": conf, "elo_rating": elo,
        "attack_strength": atk, "defense_strength": dfn,
        "elo_source": "eloratings.net World.tsv", "last_updated": "2026-06-10",
    }

with open("/home/claude/wc2026/teams_seed.json","w") as f:
    json.dump(out, f, indent=2)

print(f"48 teams written. Mean Elo of field: {mean_elo:.0f}\n")
print("Sanity checks (xG_A = avg_goals * attack_A * defense_B):")
def xg(a,b):
    A,B = out[a],out[b]
    return LEAGUE_AVG_GOALS*A["attack_strength"]*B["defense_strength"], \
           LEAGUE_AVG_GOALS*B["attack_strength"]*A["defense_strength"]
for a,b in [("ESP","CUW"),("BRA","MAR"),("USA","PAR"),("ARG","JOR"),("FRA","NOR")]:
    ga,gb = xg(a,b)
    print(f"  {a} (elo {out[a]['elo_rating']}) vs {b} (elo {out[b]['elo_rating']}): xG {ga:.2f} - {gb:.2f}")
