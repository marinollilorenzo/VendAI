import re
from datetime import datetime, timedelta

import re
from datetime import datetime, timedelta

def parse_date_text(text: str) -> datetime | None:
    """
    Analizza testo naturale in italiano e restituisce un oggetto datetime futuro.
    Corregge il bug "Lunedì = Oggi" proiettando sempre nel futuro.
    """
    now = datetime.now()
    text_lower = text.lower().strip()
    target_date = None

    # Mappe
    giorni_map = {
        "lunedì": 0, "lunedi": 0, "martedì": 1, "martedi": 1, 
        "mercoledì": 2, "mercoledi": 2, "giovedì": 3, "giovedi": 3,
        "venerdì": 4, "venerdi": 4, "sabato": 5, "domenica": 6
    }
    mesi_map = {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
        "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
    }

    # 1. Pattern RELATIVO: "tra X minuti/ore/giorni"
    # (Questo era perfetto, lo teniamo uguale)
    match = re.search(r"tra\s+(\d+)\s+(minut[oi]|or[ae]|giorn[oi])", text_lower)
    if match:
        quantita = int(match.group(1))
        unita = match.group(2)
        if unita.startswith("minut"):
            return now + timedelta(minutes=quantita)
        elif unita.startswith("or"):
            return now + timedelta(hours=quantita)
        else:
            return now + timedelta(days=quantita)

    # 2. Pattern DOMANI / DOPODOMANI
    # Ho unito i due casi e reso l'orario opzionale (default 12:00)
    match = re.search(r"(domani|dopodomani)(?:\s+alle\s+)?(\d{1,2})?(?:[:\.](\d{2}))?", text_lower)
    if match:
        tipo = match.group(1)
        ora = int(match.group(2)) if match.group(2) else 12 # Default mezzogiorno se non specifica ora
        minuti = int(match.group(3) or 0)
        
        days_add = 2 if "dopo" in tipo else 1
        target = now + timedelta(days=days_add)
        return target.replace(hour=ora, minute=minuti, second=0, microsecond=0)

    # 3. Pattern GIORNO SETTIMANA (Es. "Lunedì alle 15" oppure "Lunedì prossimo")
    # FIX: La parola "prossimo" ora è opzionale (?:...)?
    giorni_regex = r"(" + "|".join(giorni_map.keys()) + r")" # Crea (lunedì|martedì|...)
    match = re.search(giorni_regex + r"\s*(?:prossim[oa])?(?:\s+alle\s+)?(\d{1,2})?(?:[:\.](\d{2}))?", text_lower)
    
    if match:
        nome_giorno = match.group(1)
        ora = int(match.group(2)) if match.group(2) else 12
        minuti = int(match.group(3) or 0)
        
        target_day_index = giorni_map[nome_giorno]
        today_index = now.weekday()
        
        # Calcolo quanti giorni mancano
        days_ahead = target_day_index - today_index
        
        # Se il giorno è oggi o è passato (in questa settimana), andiamo alla prossima
        # Es: Oggi è Giovedì (3), scrivo Lunedì (0) -> days_ahead = -3 -> Diventa 4 (tra 4 giorni)
        if days_ahead <= 0:
            days_ahead += 7
            
        # Caso speciale: Se scrivo "Lunedì" ed è Lunedì, ma l'ora è passata?
        # Se days_ahead era 0 e l'abbiamo fatto diventare 7, va bene (settimana prox).
        # Ma se l'utente intendeva "oggi più tardi", dobbiamo controllare l'ora.
        # Qui per sicurezza, se uno scrive il giorno della settimana, assumiamo sempre futuro/prossimo.
        
        future_date = now + timedelta(days=days_ahead)
        return future_date.replace(hour=ora, minute=minuti, second=0, microsecond=0)

    # 4. Pattern DATA SPECIFICA: "25 dicembre" o "il 25/12"
    match = re.search(r"(?:il\s+)?(\d{1,2})\s+([a-z]+)\s*(?:alle\s+)?(\d{1,2})?(?:[:\.](\d{2}))?", text_lower)
    if match and match.group(2) in mesi_map:
        giorno = int(match.group(1))
        mese = mesi_map[match.group(2)]
        ora = int(match.group(3)) if match.group(3) else 12
        minuti = int(match.group(4) or 0)
        
        try:
            parsed_dt = datetime(now.year, mese, giorno, ora, minuti)
            # Se la data è passata (es. scrivo "20 Gennaio" ed è Marzo), metti anno prossimo
            if parsed_dt < now:
                parsed_dt = parsed_dt.replace(year=now.year + 1)
            return parsed_dt
        except ValueError:
            pass # Data non valida (es. 30 febbraio)

    # 5. Pattern SOLO ORA: "alle 15" (Oggi o Domani)
    match = re.search(r"alle\s+(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        ora = int(match.group(1))
        minuti = int(match.group(2) or 0)
        
        target = now.replace(hour=ora, minute=minuti, second=0, microsecond=0)
        if target <= now: # Se l'ora è passata, intendo domani
            target += timedelta(days=1)
        return target

    return None

if __name__ == "__main__":
    # Test cases for parse_date_text function
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_cases = [
        # "Tra X" patterns
        ("tra 5 minuti", "should be ~5 minutes from now"),
        ("tra 2 ore", "should be ~2 hours from now"),
        ("tra 3 giorni", "should be ~3 days from now"),
        ("tra 1 giorno", "should be ~1 day from now"),

        # "Domani" patterns
        ("domani alle 10", "should be tomorrow at 10:00"),
        ("domani 15:30", "should be tomorrow at 15:30"),
        ("domani alle 8", "should be tomorrow at 08:00"),

        # Weekday patterns
        ("lunedì prossimo alle 9", "should be next Monday at 09:00"),
        ("mercoledì prossimo alle 14:00", "should be next Wednesday at 14:00"),
        ("domenica alle 23", "should be next Sunday at 23:00 (if today is Sunday and time passed, or this Sunday if time is in future)"),

        # Specific date patterns
        ("il 15 agosto alle 18:00", "should be Aug 15th at 18:00 (this or next year)"),
        ("25 dicembre 12:00", "should be Dec 25th at 12:00 (this or next year)"),
        ("1 gennaio alle 00:00", "should be Jan 1st at 00:00 (this or next year)"),

        # "Alle HH:MM" patterns
        ("alle 23:59", "should be today at 23:59 if in future, else tomorrow"),
        ("alle 08:00", "should be today at 08:00 if in future, else tomorrow"),
        ("alle 10", "should be today at 10:00 if in future, else tomorrow"),

        # Edge cases and errors
        ("domani alle 25", "should return None (invalid hour)"),
        ("il 30 febbraio alle 10", "should return None (invalid date)"),
        ("invalid text", "should return None"),
        ("domani", "should return None (no time specified)"),
    ]

    for text, description in test_cases:
        result = parse_date_text(text)
        print(f"'{text}' ({description}): {result.strftime('%Y-%m-%d %H:%M:%S') if result else 'None'}")
