"""
Scientific Anki Struggle & Relapse Analysis Service.

Uses cognitive psychology metrics (Ebbinghaus forgetting dynamics, Bjork desirable difficulties,
and FSRS/SM-2 retrieval friction) to identify, score, and diagnose today's struggle cards.
Provides 1-click Anki filtered deck opening and direct lecture slide mapping.
"""

from datetime import datetime, date, time
import json
import os
import re
import sqlite3
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.anki_desktop_sync import find_local_anki_collection, clean_deck_name
from app.services.anki_local_service import check_ankiconnect_health


def strip_html(text: str) -> str:
    """Removes HTML tags and cleans whitespace for card text preview."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def calculate_struggle_score(ease: int, time_ms: int, historical_lapses: int, is_curriculum: bool = True) -> float:
    """
    Computes scientific struggle score S_struggle:
    - Ease == 1 (Again/Lapse): +4.0 (acute retrieval failure)
    - Ease == 2 (Hard): +2.0 (high cognitive strain)
    - Response latency: up to +2.0 if user hesitated > 15 seconds
    - Historical lapses: up to +3.0 for chronic leeches
    - Curriculum relevance bonus: +1.0
    """
    score = 0.0
    if ease == 1:
        score += 4.0
    elif ease == 2:
        score += 2.0
    elif ease == 3:
        score += 0.5

    if time_ms > 15000:
        latency_penalty = min(2.0, (time_ms - 15000) / 15000.0)
        score += latency_penalty

    score += min(3.0, historical_lapses * 0.75)

    if is_curriculum:
        score += 1.0

    return round(score, 2)


def diagnose_struggle_cause(question: str, answer: str, ease: int, time_sec: float, historical_lapses: int) -> Dict[str, str]:
    """Generates cognitive diagnosis and actionable mnemonic anchor."""
    q_lower = (question + " " + answer).lower()

    if re.search(r"\b\d+[\.,]?\d*\s*(mg|g|ml|l|%|mmol|µmol|fl|pg|kpa|mmhg|/µl|/nl)\b", q_lower) or any(k in q_lower for k in ["normwert", "grenzwert", "referenzbereich", "hämotokrit", "hämoglobin"]):
        return {
            "type": "numbers_lab",
            "badge": "🔢 Laborwert / Zahlenanker",
            "diagnosis": "Zahlenwerte erzeugen isolierte Gedächtnisspuren ohne semantisches Netz.",
            "anchor_tip": "Verknüpfe den Wert mit einem visuellen Extrem (z.B. Normal vs. Pathologisch / Schockraum) statt der reinen Zahl."
        }

    if any(k in q_lower for k in ["faktor", "kaskade", "zymogen", "thrombin", "aktiviert", "synthese", "rezeptor", "zyklus"]):
        return {
            "type": "cascade_mechanism",
            "badge": "⚡ Reaktionskette / Kaskade",
            "diagnosis": "Multistep-Abläufe neigen zu Positionsvertauschungen (Primäre vs. Sekundäre Hämostase).",
            "anchor_tip": "Lerne die Schrittfolge als linearen Dominostein: Was ist der Auslöser (Trigger), was das Endprodukt (Fibrin)?"
        }

    if any(k in q_lower for k in ["unterschied", "differenz", "vs", "versus", "t-zell", "b-zell", "granulozyt", "mono"]):
        return {
            "type": "differential",
            "badge": "⚖️ Differenzierung / Verwechslung",
            "diagnosis": "Phänotypische Verwechslungsgefahr ähnlicher Zelltypen oder Marker.",
            "anchor_tip": "Fokussiere dich ausschließlich auf das EINE Alleinstellungsmerkmal (z.B. CD-Marker oder Granula-Färbung)."
        }

    if historical_lapses >= 3:
        return {
            "type": "chronic_leech",
            "badge": "🔁 Chronischer Leech (>3 Lapses)",
            "diagnosis": "Instabile Repräsentation. Die Formulierung der Karte erzeugt wahrscheinlich kognitive Interferenz.",
            "anchor_tip": "Schau dir einmalig die Originalfolie des Dozenten an, um den Kontext wiederherzustellen."
        }

    return {
        "type": "cognitive_friction",
        "badge": "🧠 Hohe Abruf-Latenz",
        "diagnosis": f"Lange Antwortzeit ({time_sec:.1f}s) deutet auf lückenhaften semantischen Abruf hin.",
        "anchor_tip": "Formuliere die Kernantwort in eigenen Worten in einem prägnanten 3-Wort-Satz."
    }


def find_slide_mapping_for_card(question: str, answer: str, deck_name: str) -> Dict[str, Any]:
    """Maps card content to relevant UZH lecture slides based on keywords."""
    combined = (question + " " + answer + " " + deck_name).lower()

    mappings = [
        {
            "keywords": ["gerinnung", "hämostase", "thrombo", "faktor", "inr", "quick", "ptt", "fibrin"],
            "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/6-7_CM_Blutgerinnung.pdf",
            "title": "Blutgerinnung & Hämostase (Manatschal)",
            "estimated_slides": "Folien 12–24",
            "page_hint": 14
        },
        {
            "keywords": ["hämoglobin", "myoglobin", "sauerstoff", "co2", "bohr", "2,3-bpg", "desoxy"],
            "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/1-4_CM_Myoglobin_Hamoglobin.pdf",
            "title": "Myoglobin & Hämoglobin (Manatschal)",
            "estimated_slides": "Folien 18–32",
            "page_hint": 20
        },
        {
            "keywords": ["säure", "base", "bicarbonat", "puffer", "azidose", "alkalose", "henderson"],
            "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/5_CM_Saure-Base_CO2-Transport.pdf",
            "title": "Säure-Base & CO2-Transport",
            "estimated_slides": "Folien 8–18",
            "page_hint": 10
        },
        {
            "keywords": ["komplement", "c3", "c5", "mac", "opsonisierung"],
            "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Cristina Manatschal/8_CM_Komplementsystem.pdf",
            "title": "Komplementsystem (Manatschal)",
            "estimated_slides": "Folien 4–10",
            "page_hint": 6
        },
        {
            "keywords": ["immun", "t-zell", "b-zell", "leukozyt", "mhc", "zytokin", "antikörper", "thymus"],
            "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
            "title": "Adaptives & Angeborenes Immunsystem (Tuzlak)",
            "estimated_slides": "Folien 15–35",
            "page_hint": 18
        },
        {
            "keywords": ["herz", "myokard", "ekg", "vektor", "systole", "diastole", "klappe", "aorta"],
            "slide_pdf": "TB herz-Kreislauf/Archive_1/Anatomie/Sommer_HerzGefaessentwicklung-VAM.pdf",
            "title": "Herz- und Gefässentwicklung",
            "estimated_slides": "Folien 10–25",
            "page_hint": 12
        },
        {
            "keywords": ["lunge", "atmung", "alveol", "surfactant", "ventilation", "pleura"],
            "slide_pdf": "Atmung/Sommer_LungenZwerchentw-VAM.pdf",
            "title": "Lungen- & Zwerchfellentwicklung",
            "estimated_slides": "Folien 6–16",
            "page_hint": 8
        },
    ]

    for m in mappings:
        if any(k in combined for k in m["keywords"]):
            return {
                "has_slide_link": True,
                "slide_pdf": m["slide_pdf"],
                "slide_title": m["title"],
                "estimated_slides": m["estimated_slides"],
                "page_hint": m["page_hint"]
            }

    return {
        "has_slide_link": True,
        "slide_pdf": "Vorlesungen im Themenblock Blut und Immunsystem/Tuzlak_Adaptives und angeborenes Immunsystem.pdf",
        "slide_title": "Themenblock Blut & Immunsystem Foliensatz",
        "estimated_slides": "Allgemeine Folienübersicht",
        "page_hint": 1
    }


def get_today_struggle_analysis(query_date: Optional[date] = None, limit: int = 15) -> Dict[str, Any]:
    """
    Extracts cards reviewed today with Ease 1 (Again), Ease 2 (Hard), or high latency.
    Computes scientific struggle score, cognitive diagnosis, and links to Anki & slides.
    """
    now = datetime.now()
    q_date = query_date or now.date()

    target_path = find_local_anki_collection()
    if not target_path or not target_path.exists():
        return {
            "available": False,
            "error": "Keine lokale Anki-Datenbank gefunden.",
            "total_struggles": 0,
            "cards": [],
            "anki_query": "rated:1:1",
            "summary": "Lokale Anki-Datenbank nicht erreichbar."
        }

    try:
        uri = f"file:///{target_path.as_posix()}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()

        day_start_dt = datetime(q_date.year, q_date.month, q_date.day, 4, 0, 0)
        day_start_ms = int(day_start_dt.timestamp() * 1000)
        day_end_ms = day_start_ms + (86400 * 1000)

        decks = {}
        for did, dname in cur.execute("SELECT id, name FROM decks").fetchall():
            decks[did] = clean_deck_name(dname)

        sql = """SELECT r.id, r.cid, c.did, r.ease, r.time, r.type, c.lapses, c.reps, c.ivl, n.sfld, n.flds FROM revlog r JOIN cards c ON r.cid = c.id JOIN notes n ON c.nid = n.id WHERE r.id >= ? AND r.id < ? ORDER BY r.id DESC"""
        rows = cur.execute(sql, (day_start_ms, day_end_ms)).fetchall()

        cards_dict = {}
        for r in rows:
            rev_id, cid, did, ease, time_ms, rev_type, lapses, reps, ivl, sfld, flds = r
            if ease in (1, 2) or time_ms > 25000:
                if cid not in cards_dict:
                    cards_dict[cid] = {
                        "cid": cid,
                        "did": did,
                        "deck_name": decks.get(did, "Unbekanntes Deck"),
                        "ease": ease,
                        "time_ms": time_ms,
                        "rev_type": rev_type,
                        "lapses": lapses,
                        "reps": reps,
                        "sfld": sfld,
                        "flds": flds,
                    }
                else:
                    if ease == 1 and cards_dict[cid]["ease"] > 1:
                        cards_dict[cid]["ease"] = 1
                        cards_dict[cid]["time_ms"] = max(cards_dict[cid]["time_ms"], time_ms)

        processed_cards = []
        for cid, data in cards_dict.items():
            question_raw = data["sfld"]
            fields = data["flds"].split("\x1f") if data["flds"] else []
            answer_raw = fields[1] if len(fields) > 1 else ""

            q_clean = strip_html(question_raw)
            a_clean = strip_html(answer_raw)
            time_sec = round(data["time_ms"] / 1000.0, 1)

            s_score = calculate_struggle_score(
                ease=data["ease"],
                time_ms=data["time_ms"],
                historical_lapses=data["lapses"],
                is_curriculum=True
            )

            diagnosis = diagnose_struggle_cause(
                question=q_clean,
                answer=a_clean,
                ease=data["ease"],
                time_sec=time_sec,
                historical_lapses=data["lapses"]
            )

            slide_info = find_slide_mapping_for_card(
                question=q_clean,
                answer=a_clean,
                deck_name=data["deck_name"]
            )

            ease_label = "Nochmal (Lapse)" if data["ease"] == 1 else ("Schwer" if data["ease"] == 2 else "Lange Latenz")
            ease_color = "#f85149" if data["ease"] == 1 else "#d29922"

            processed_cards.append({
                "cid": cid,
                "question": q_clean[:180] + ("..." if len(q_clean) > 180 else ""),
                "answer": a_clean[:140] + ("..." if len(a_clean) > 140 else ""),
                "deck_name": data["deck_name"],
                "ease": data["ease"],
                "ease_label": ease_label,
                "ease_color": ease_color,
                "time_sec": time_sec,
                "historical_lapses": data["lapses"],
                "struggle_score": s_score,
                "diagnosis": diagnosis,
                "slide_info": slide_info,
            })

        processed_cards.sort(key=lambda x: -x["struggle_score"])
        top_cards = processed_cards[:limit]

        if top_cards:
            cids_str = ",".join(str(c["cid"]) for c in top_cards)
            anki_query = f"cid:{cids_str}"
        else:
            anki_query = "rated:1:1"

        lapses_count = sum(1 for c in processed_cards if c["ease"] == 1)
        hard_count = sum(1 for c in processed_cards if c["ease"] == 2)

        return {
            "available": True,
            "query_date": q_date.isoformat(),
            "total_struggles": len(processed_cards),
            "lapses_count": lapses_count,
            "hard_count": hard_count,
            "cards": top_cards,
            "anki_query": anki_query,
            "anki_browse_url": f"anki://search?q={anki_query}",
            "summary": f"{len(processed_cards)} Problemkarten heute identifiziert ({lapses_count}x Nochmal, {hard_count}x Schwer).",
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "total_struggles": 0,
            "cards": [],
            "anki_query": "rated:1:1",
            "summary": f"Fehler bei der Struggle-Analyse: {str(e)}"
        }


def trigger_anki_browse(query: str = "rated:1:1") -> Dict[str, Any]:
    """Triggers AnkiConnect guiBrowse to show the struggle cards in Anki Desktop."""
    health = check_ankiconnect_health()
    if not health.get("available"):
        return {
            "success": False,
            "message": "Anki Desktop ist nicht geöffnet oder AnkiConnect ist nicht aktiv. Bitte Anki öffnen.",
            "query": query,
            "manual_instruction": f"Öffne Anki -> 'Kartenverwaltung' -> Suche eingeben: {query}"
        }

    url = "http://127.0.0.1:8765"
    payload = json.dumps({
        "action": "guiBrowse",
        "version": 6,
        "params": {"query": query}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("error"):
                return {"success": False, "error": data["error"], "query": query}
            return {
                "success": True,
                "message": f"Anki-Kartenbrowser für '{query}' erfolgreich geöffnet!",
                "query": query
            }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "query": query,
            "manual_instruction": f"Öffne Anki -> 'Kartenverwaltung' -> Suche eingeben: {query}"
        }


def _invoke_ankiconnect(action: str, **params) -> Dict[str, Any]:
    """Helper to invoke AnkiConnect action."""
    url = "http://127.0.0.1:8765"
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=2.5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def prepare_temporary_struggle_deck(
    deck_name: str = "⚡ Problem-Karten Heute",
    tag_name: str = "⚡_Heute_Problemkarten",
    query_date: Optional[date] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """Prepares a temporary study session in Anki Desktop for today's struggle cards.
    
    1. Identifies today's struggle cards (acute lapses + high friction).
    2. Tags them with tag_name in Anki via AnkiConnect (clearing old tags first).
    3. Opens Anki Browser directly focused on these cards.
    4. Provides foolproof instructions for creating a native Filtered Deck in Anki:
       Filtered decks (Taste F) are 100% safe: When deleted at the end of the day,
       Anki automatically returns all cards back into their original home decks!
    """
    health = check_ankiconnect_health()
    struggle_res = get_today_struggle_analysis(query_date=query_date, limit=limit)
    cards = struggle_res.get("cards", [])

    if not cards:
        return {
            "success": True,
            "card_count": 0,
            "tag": tag_name,
            "search_query": f"tag:{tag_name}",
            "deck_name": deck_name,
            "message": "Heute wurden keine Problem-Karten festgestellt! Alle Wiederholungen waren fehlerfrei. 🎉",
            "instructions": []
        }

    cids = [c["cid"] for c in cards]

    if not health.get("available"):
        return {
            "success": False,
            "card_count": len(cards),
            "deck_name": deck_name,
            "tag": tag_name,
            "search_query": f"tag:{tag_name}",
            "message": "Anki Desktop ist nicht geöffnet oder AnkiConnect ist inaktiv. Bitte öffne Anki Desktop.",
            "instructions": [
                "1. Öffne Anki Desktop.",
                f"2. Manuelle Suche: cid:{','.join(str(c) for c in cids[:10])}",
                "3. Drücke 'F' (Gefilterter Stapel), um die Karten gezielt zu wiederholen."
            ]
        }

    try:
        # Step A: Clean up previous cards with this tag to prevent mixing days
        old_cards_res = _invoke_ankiconnect("findCards", query=f"tag:{tag_name}")
        old_cids = old_cards_res.get("result", [])
        if old_cids:
            old_notes_res = _invoke_ankiconnect("cardsToNotes", cards=old_cids)
            old_nids = old_notes_res.get("result", [])
            if old_nids:
                _invoke_ankiconnect("removeTags", notes=old_nids, tags=tag_name)

        # Step B: Tag current struggle cards
        notes_res = _invoke_ankiconnect("cardsToNotes", cards=cids)
        nids = notes_res.get("result", [])
        if nids:
            _invoke_ankiconnect("addTags", notes=nids, tags=tag_name)

        # Step C: Open card browser in Anki
        _invoke_ankiconnect("guiBrowse", query=f"tag:{tag_name}")

        return {
            "success": True,
            "card_count": len(cards),
            "deck_name": deck_name,
            "tag": tag_name,
            "search_query": f"tag:{tag_name}",
            "message": f"⚡ {len(cards)} Problemkarten in Anki getaggt (`tag:{tag_name}`) und Browser geöffnet!",
            "instructions": [
                f"1. Drücke in Anki Desktop einfach die Taste 'F' (Gefilterten Stapel erstellen).",
                f"2. Gib als Stapelname '{deck_name}' und als Filter 'tag:{tag_name}' ein (bereits kopiert).",
                "3. 🛡️ 100% Sicher: Sobald du den Stapel heute Abend löschst, wandern alle Karten automatisch & unberührt in ihre Original-Heimatdecks zurück!"
            ]
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "card_count": len(cards),
            "deck_name": deck_name,
            "tag": tag_name,
            "search_query": f"tag:{tag_name}",
            "message": f"Fehler beim Erstellen des temporären Decks: {str(exc)}"
        }


def cleanup_struggle_deck_tags(tag_name: str = "⚡_Heute_Problemkarten") -> Dict[str, Any]:
    """Removes the temporary struggle tag from all notes in Anki Desktop."""
    health = check_ankiconnect_health()
    if not health.get("available"):
        return {"success": False, "message": "Anki Desktop nicht erreichbar."}

    try:
        cards_res = _invoke_ankiconnect("findCards", query=f"tag:{tag_name}")
        cids = cards_res.get("result", [])
        if not cids:
            return {"success": True, "message": f"Keine Karten mit Tag '{tag_name}' gefunden.", "removed_count": 0}

        notes_res = _invoke_ankiconnect("cardsToNotes", cards=cids)
        nids = notes_res.get("result", [])
        if nids:
            _invoke_ankiconnect("removeTags", notes=nids, tags=tag_name)

        return {
            "success": True,
            "message": f"Tag '{tag_name}' von {len(nids)} Notizen entfernt.",
            "removed_count": len(nids)
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}

