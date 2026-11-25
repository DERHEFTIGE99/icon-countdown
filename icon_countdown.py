"""Event-Countdown fuer das Spiel-Icon (Farm Aura for Brainrot).

Aktuelles Event: DUELS + ADMIN ABUSE, Start Sa 28.11.2026 15:00 deutsche Zeit (14:00 UTC).
Berechnet aus der Uhrzeit, welches Countdown-Bild gerade dran ist, und setzt es per
Open Cloud als Place-Icon, falls es nicht schon gesetzt ist.

Ablauf (deutsche Zeit):
  vor Fr 27.11. 15:00: normales Icon
  volle Stunden: 24 HOURS ... 1 HOUR, dann Sa 14:30 30 MINUTES, 14:45 15 MINUTES,
  14:55 5 MINUTES, 15:00-17:00 NOW, danach wieder das normale Icon.
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

PLACE_ID = "134522606448687"
EVENT_START = datetime(2026, 11, 28, 14, 0, 0, tzinfo=timezone.utc)  # Sa 15:00 deutsche Zeit (Duels)
NOW_DURATION = 2 * 3600          # "NOW" bleibt 2 Stunden
MAX_HOURS = 24                   # Countdown beginnt 24 h vorher
ORIGINAL_ICON = "130514801796403"  # normales Icon (base_icon.png, 25.11. per API als Gruppen-Bild hochgeladen)

ICONS = {
    "24H": "137463528249408", "23H": "102313961678755", "22H": "81158216045232",
    "21H": "113056903474600", "20H": "84148144448728", "19H": "101128542050647",
    "18H": "110820621228953", "17H": "93567377990531", "16H": "82697066302956",
    "15H": "126217185583754", "14H": "134251440713219", "13H": "127417804972006",
    "12H": "106127880219949", "11H": "122073795016085", "10H": "117204464611888",
    "9H": "132651038754463", "8H": "121903903432887", "7H": "116847404119009",
    "6H": "119411434383002", "5H": "84284895865173", "4H": "99619030880251",
    "3H": "125000001488376", "2H": "126306477207131", "1H": "133863362750795",
    "30M": "130401701028972", "15M": "124429797494652", "5M": "85899050601293",
    "NOW": "131115297497663", "ORIGINAL": ORIGINAL_ICON, "BEFORE": ORIGINAL_ICON,
}

API = "https://apis.roblox.com/assets/v1/assets/" + PLACE_ID
EARLY = 0  # Sekunden Toleranz (0 = Wechsel exakt zur vollen Stunde)
# Dauerlauf max. 5,5 h (GitHub-Limit pro Job: 6 h); per LOOP_MINUTES kuerzer zum Testen
LOOP_SECONDS = int(os.environ.get("LOOP_MINUTES") or 330) * 60
LEAD = 60  # Sekunden frueher wechseln: Roblox braucht ~30-90 s, bis das neue Icon ueberall sichtbar ist


def now() -> float:
    """'Countdown-Uhr': LEAD Sekunden vor der echten Zeit."""
    return time.time() + LEAD


def stage_at(t: float) -> str:
    r = EVENT_START.timestamp() - t  # Sekunden bis Eventstart
    if r <= -NOW_DURATION:
        return "ORIGINAL"
    if r <= 0:
        return "NOW"
    if r <= 5 * 60:
        return "5M"
    if r <= 15 * 60:
        return "15M"
    if r <= 30 * 60:
        return "30M"
    if r > MAX_HOURS * 3600:
        return "BEFORE"  # Countdown hat noch nicht begonnen: normales Icon
    hours = math.ceil((r - EARLY) / 3600)
    return f"{max(1, min(MAX_HOURS, hours))}H"


def next_change(t: float) -> float:
    """Zeitpunkt des naechsten Stufenwechsels (Sekunden-Suche, max. 2 h voraus)."""
    cur = stage_at(t)
    step = int(t) + 1
    while step < t + 7200:
        if stage_at(step) != cur:
            return step
        step += 1
    return t + 7200


def api_key() -> str:
    key = os.environ.get("ROBLOX_API_KEY", "").strip()
    if not key:
        sys.exit("ROBLOX_API_KEY fehlt (GitHub Secret anlegen).")
    return key


def current_icon() -> str:
    key = api_key()
    print(f"Key: Laenge {len(key)} Zeichen")
    req = urllib.request.Request(API + "?readMask=icon", headers={"x-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"GET fehlgeschlagen: {e.code} {e.read().decode()[:500]}")
    return data.get("icon", "").replace("assets/", "")


def set_icon(asset_id: str) -> None:
    # Update Asset verlangt multipart/form-data mit dem Feld "request" (ohne fileContent!)
    boundary = uuid.uuid4().hex
    payload = json.dumps({"assetId": PLACE_ID, "icon": f"assets/{asset_id}"})
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="request"\r\n'
        "Content-Type: application/json\r\n\r\n"
        f"{payload}\r\n--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        API + "?updateMask=icon", data=body, method="PATCH",
        headers={"x-api-key": api_key(), "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("PATCH", resp.status, resp.read().decode()[:300])
    except urllib.error.HTTPError as e:
        sys.exit(f"PATCH fehlgeschlagen: {e.code} {e.read().decode()[:500]}")


def apply(dry: bool) -> str:
    stage = stage_at(now())
    want = ICONS[stage]
    if dry:
        print(f"[dry-run] Stufe {stage} -> assets/{want}")
        return stage
    have = current_icon()
    if have == want:
        print(f"Stufe {stage}: Icon ist schon gesetzt ({want}).")
    else:
        print(f"Stufe {stage}: setze Icon {have} -> {want}")
        set_icon(want)
        time.sleep(10)  # PATCH ist asynchron: kurz warten, dann nachlesen
        check = current_icon()
        print("Kontrolle:", "OK, Icon ist gesetzt" if check == want else f"Roblox meldet noch {check}")
    return stage


def write_output(line: str) -> None:
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as fh:
        fh.write(line + "\n")


def run_loop(dry: bool) -> None:
    """Bleibt bis zu LOOP_SECONDS wach und setzt jeden Wechsel selbst.
    Danach meldet es 'restart=true', damit der Workflow sich neu startet
    (GitHub-Cron ist bei neuen Repos unzuverlaessig)."""
    start = now()
    while True:
        try:
            stage = apply(dry)
        except (SystemExit, Exception) as e:  # einzelner API-/Netzfehler: kurz warten, nochmal
            print("Fehler:", e, "- neuer Versuch in 60 s", flush=True)
            time.sleep(60)
            continue
        if stage == "ORIGINAL":  # Event + NOW vorbei, Original-Icon ist wieder drin
            print("FERTIG")
            write_output("finished=true")
            return
        nxt = next_change(now())
        if nxt - start > LOOP_SECONDS:
            print("Laufzeit fast um - starte neuen Lauf.")
            write_output("restart=true")
            return
        wait = max(1, nxt - now() + 2)
        print(f"Naechster Wechsel in {int(wait)} s ({datetime.fromtimestamp(nxt, timezone.utc):%H:%M:%S} UTC).", flush=True)
        time.sleep(wait)


def main() -> None:
    dry = "--dry-run" in sys.argv
    if "--table" in sys.argv:  # Kontrolle: alle Wechselzeiten ausgeben
        t = EVENT_START.timestamp() - (MAX_HOURS + 1) * 3600
        end = EVENT_START.timestamp() + NOW_DURATION + 60
        while t < end:
            n = next_change(t)
            print(datetime.fromtimestamp(n, timezone.utc).strftime("%d.%m. %H:%M:%S UTC"), "->", stage_at(n))
            t = n
        return

    if "--loop" in sys.argv:
        run_loop(dry)
        return

    stage = apply(dry)
    # Steht ein Wechsel in den naechsten ~5,5 Minuten an? Dann bis dahin warten
    # und direkt umstellen (GitHub-Cron ist sonst ungenau).
    nxt = next_change(now())
    wait = nxt - now()
    if 0 < wait <= 330 and stage != "ORIGINAL":
        print(f"Naechster Wechsel in {int(wait)} s - warte.")
        time.sleep(wait + 2)
        apply(dry)

    if stage == "ORIGINAL" and time.time() > EVENT_START.timestamp() + NOW_DURATION + 900:
        print("FERTIG")  # Signal fuer den Workflow, sich selbst abzuschalten
        with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as fh:
            fh.write("finished=true\n")


if __name__ == "__main__":
    main()
