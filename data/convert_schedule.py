"""Convert calendar CSV export -> data/schedule.json + data/odds_reference.json.
Discarded from source: end date/time and all-day flag (every match = start + 2h).
Odds deliberately split out: runtime never stores betting data (guardrail policy);
odds_reference.json exists only for offline model calibration."""
import csv, json, re
from datetime import datetime

NAME_TO_FIFA = {
 "Mexico":"MEX","South Africa":"RSA","South Korea":"KOR","Czechia":"CZE",
 "Canada":"CAN","Bosnia-Herzegovina":"BIH","United States":"USA","Paraguay":"PAR",
 "Qatar":"QAT","Switzerland":"SUI","Brazil":"BRA","Morocco":"MAR","Haiti":"HAI",
 "Scotland":"SCO","Australia":"AUS","Türkiye":"TUR","Germany":"GER","Curaçao":"CUW",
 "Netherlands":"NED","Japan":"JPN","Ivory Coast":"CIV","Ecuador":"ECU","Sweden":"SWE",
 "Tunisia":"TUN","Spain":"ESP","Cape Verde":"CPV","Belgium":"BEL","Egypt":"EGY",
 "Saudi Arabia":"KSA","Uruguay":"URU","Iran":"IRN","New Zealand":"NZL","France":"FRA",
 "Senegal":"SEN","Iraq":"IRQ","Norway":"NOR","Argentina":"ARG","Algeria":"ALG",
 "Austria":"AUT","Jordan":"JOR","Portugal":"POR","Congo DR":"COD","England":"ENG",
 "Croatia":"CRO","Ghana":"GHA","Panama":"PAN","Uzbekistan":"UZB","Colombia":"COL",
}
VENUE_ALIASES = {
 "SoFi Stadium":"sofi","NRG Stadium":"nrg","Gillette Stadium":"gillette",
 "Estadio BBVA":"bbva","AT&T Stadium":"att","MetLife Stadium":"metlife",
 "Estadio Banorte":"azteca","Estadio Akron":"akron",
 "Mercedes-Benz Stadium":"mercedes_benz","Lumen Field":"lumen","Levi's Stadium":"levis",
 "BMO Field":"bmo","BC Place":"bc_place","Hard Rock Stadium":"hard_rock",
 "GEHA Field at Arrowhead Stadium":"arrowhead","Lincoln Financial Field":"lincoln_financial",
}
ODDS = re.compile(r'Odds \(DraftKings\):\s*([A-Z]{3})\s*([+-]\d+)')
OU   = re.compile(r'O/U:\s*([\d.]+)')

def stage_for(n):  # n = 1-based match number
    if n <= 72:  return "group"
    if n <= 88:  return "round_of_32"
    if n <= 96:  return "round_of_16"
    if n <= 100: return "quarterfinal"
    if n <= 102: return "semifinal"
    return "third_place" if n == 103 else "final"

def implied_prob(a):
    a = int(a)
    return abs(a)/(abs(a)+100) if a < 0 else 100/(a+100)

teams = json.load(open("teams_seed.json"))
team_group = {t["team_id"]: t["group"] for t in teams.values()}

schedule, odds_ref = [], []
rows = list(csv.DictReader(open("/home/claude/sched/raw_schedule_v2.csv", encoding="utf-8")))
for i, row in enumerate(rows, start=1):
    side_a, side_b = row["Subject"].split(" vs ", 1)
    dt = datetime.strptime(f"{row['Start Date']} {row['Start Time']}", "%m/%d/%Y %I:%M %p")
    venue_name = row["Location"].split(",")[0].strip()
    vid, stage = VENUE_ALIASES[venue_name], stage_for(i)
    rec = dict(match_id=f"M{i:03d}", stage=stage, group=None,
               team_a=None, team_b=None, placeholder_a=None, placeholder_b=None,
               datetime_pacific=dt.strftime("%Y-%m-%dT%H:%M:%S-07:00"),
               venue_id=vid, status="scheduled", score_a=None, score_b=None)
    if stage == "group":
        ta, tb = NAME_TO_FIFA[side_a], NAME_TO_FIFA[side_b]
        assert team_group[ta] == team_group[tb], f"M{i:03d}: cross-group pairing {ta}/{tb}"
        rec.update(team_a=ta, team_b=tb, group=team_group[ta])
        om, oum = ODDS.search(row["Description"]), OU.search(row["Description"])
        if om:
            odds_ref.append(dict(match_id=rec["match_id"], teams=[ta,tb],
                favorite=om.group(1), moneyline_american=int(om.group(2)),
                implied_win_prob=round(implied_prob(om.group(2)),3),
                over_under=float(oum.group(1)) if oum else None,
                note="includes bookmaker vig; calibration only, never loaded to DynamoDB"))
    else:
        rec.update(placeholder_a=side_a, placeholder_b=side_b)
    schedule.append(rec)

# ---- validations ----
by_stage, apps, venue_use, cohost = {}, {}, {}, []
venues = json.load(open("venues.json"))
for r in schedule:
    by_stage[r["stage"]] = by_stage.get(r["stage"],0)+1
    venue_use[r["venue_id"]] = venue_use.get(r["venue_id"],0)+1
    if r["stage"]=="group":
        for t in (r["team_a"], r["team_b"]): apps[t]=apps.get(t,0)+1
        for t in ("MEX","USA","CAN"):
            if t in (r["team_a"], r["team_b"]):
                home = {"MEX":"Mexico","USA":"USA","CAN":"Canada"}[t]
                cohost.append((t, venues[r["venue_id"]]["country"]==home))

print("total matches:", len(schedule), "| by stage:", by_stage)
bad = {t:c for t,c in apps.items() if c!=3}
print("teams with != 3 group matches:", bad or "none")
print("co-host group matches on home soil:", f"{sum(h for _,h in cohost)}/{len(cohost)}")
print("all 16 venues used:", len(venue_use)==16, "| all venues resolved:", all(r["venue_id"] for r in schedule))
print("odds records:", len(odds_ref))
json.dump(schedule, open("schedule.json","w"), indent=2)
json.dump(odds_ref, open("odds_reference.json","w"), indent=2)
print("wrote schedule.json + odds_reference.json")
