import re
from datetime import datetime, timedelta

def parse_date_text(text: str) -> datetime | None:
    """
    Parses Italian natural language date/time expressions into a future datetime object.
    Supports patterns like "Domani alle 15", "Tra 30 minuti", "Lunedì prossimo alle 10",
    "Il 25 dicembre alle 12", handling common errors and always returning a future date.
    """
    now = datetime.now()
    text_lower = text.lower().strip()
    target_date = None

    giorni_settimana_map = {
        "lunedì": 0, "martedì": 1, "mercoledì": 2, "giovedì": 3,
        "venerdì": 4, "sabato": 5, "domenica": 6
    }
    mesi_map = {
        "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
        "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
        "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
    }

    # Helper to ensure target_date is in the future
    def get_future_datetime(dt: datetime) -> datetime:
        if dt > now:
            return dt
        # If the parsed datetime is in the past, assume next occurrence
        # This logic needs to be careful for specific patterns, especially "today" scenarios.
        # For week days or specific dates, if it's in the past, move to next year/week.
        return dt

    # Pattern 1: "tra X minuti/ore/giorni"
    match = re.search(r"tra\s+(\d+)\s+(minut[oi]|or[ae]|giorn[oi])", text_lower)
    if match:
        quantita = int(match.group(1))
        unita = match.group(2)
        if unita.startswith("minut"):
            target_date = now + timedelta(minutes=quantita)
        elif unita.startswith("or"):
            target_date = now + timedelta(hours=quantita)
        else: # giorni
            target_date = now + timedelta(days=quantita)
        return target_date # Already in future

    # Pattern 2: "domani [alle] HH[:MM]"
    match = re.search(r"domani\s+(?:alle\s+)?(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        ora = int(match.group(1))
        minuti = int(match.group(2) or 0)
        if 0 <= ora <= 23 and 0 <= minuti <= 59:
            domani = now.date() + timedelta(days=1)
            parsed_dt = datetime(domani.year, domani.month, domani.day, ora, minuti)
            return get_future_datetime(parsed_dt) # Ensure it's not past midnight of "tomorrow" due to timedelta

    # Pattern 3: "giorno_settimana prossimo [alle] HH[:MM]" (e.g., "lunedì prossimo alle 10")
    match = re.search(r"([a-zì]+)\s+prossim[oa]\s*(?:alle\s+)?(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        nome_giorno = match.group(1)
        ora = int(match.group(2))
        minuti = int(match.group(3) or 0)
        if nome_giorno in giorni_settimana_map and 0 <= ora <= 23 and 0 <= minuti <= 59:
            giorno_target_num = giorni_settimana_map[nome_giorno]
            days_until = (giorno_target_num - now.weekday() + 7) % 7
            if days_until == 0: # If today, and time has passed, or if it's actually next week
                temp_dt = datetime(now.year, now.month, now.day, ora, minuti)
                if temp_dt <= now: # Time has passed today for this day, so it must be next week
                    days_until = 7
            
            future_date = now.date() + timedelta(days=days_until)
            target_date = datetime(future_date.year, future_date.month, future_date.day, ora, minuti)
            return target_date

    # Pattern 4: "[il] GG mese [alle] HH[:MM]" (e.g., "il 25 dicembre alle 12", "25 marzo 10:30")
    match = re.search(r"(?:il\s+)?(\d{1,2})\s+([a-z]+)\s*(?:alle\s+)?(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        giorno = int(match.group(1))
        nome_mese = match.group(2)
        ora = int(match.group(3))
        minuti = int(match.group(4) or 0)
        if nome_mese in mesi_map and 1 <= giorno <= 31 and 0 <= ora <= 23 and 0 <= minuti <= 59:
            mese = mesi_map[nome_mese]
            anno = now.year
            try:
                parsed_dt = datetime(anno, mese, giorno, ora, minuti)
                if parsed_dt < now: # If date is in the past, try next year
                    parsed_dt = datetime(anno + 1, mese, giorno, ora, minuti)
                return parsed_dt
            except ValueError:
                pass # Invalid date (e.g., Feb 30), continue to next pattern

    # Pattern 5: "alle HH[:MM]" (today or tomorrow)
    match = re.search(r"alle\s+(\d{1,2})(?:[:\.](\d{2}))?", text_lower)
    if match:
        ora = int(match.group(1))
        minuti = int(match.group(2) or 0)
        if 0 <= ora <= 23 and 0 <= minuti <= 59:
            temp_dt_today = datetime(now.year, now.month, now.day, ora, minuti)
            if temp_dt_today > now: # If time is in the future today
                return temp_dt_today
            else: # If time has passed today, assume tomorrow
                domani = now.date() + timedelta(days=1)
                return datetime(domani.year, domani.month, domani.day, ora, minuti)

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
