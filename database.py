import sqlite3

#INIZIALIZZAZIONE DATABASE
def db_initialization():
    connection = sqlite3.connect("annunci.db")
    cursor = connection.cursor()
    
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stato(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categoria(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS piattaforma(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER NOT NULL UNIQUE,
        nome_utente TEXT
    );
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS annuncio(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_utente INTEGER NOT NULL,
        descrizione_input TEXT NOT NULL,
        titolo_generato TEXT,
        descrizione_generata TEXT,
        prezzo_suggerito REAL,
        id_stato INTEGER,
        id_piattaforma INTEGER,
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_pubblicazione TIMESTAMP,
        prezzo_vendita REAL,
        data_vendita TIMESTAMP,
        id_categoria INTEGER,
        is_cancellato INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (id_stato) REFERENCES stato (id),
        FOREIGN KEY (id_categoria) REFERENCES categoria (id),
        FOREIGN KEY (id_piattaforma) REFERENCES piattaforma (id)
        FOREIGN KEY (id_utente) REFERENCES utente (id)
    );
    """)
    stati_iniziali = [
        ('bozza',),           # ID 1
        ('programmato',),     # ID 2
        ('pre-notificato',),  # ID 3
        ('notificato',),      # ID 4 (Pronto per la pubblicazione manuale)
        ('venduto',)          # ID 5
    ]
    piattaforme_iniziali = [
        ('Vinted',),
        ('Subito',),
        ('Wallapop',),
        ('eBay',),
        ('Facebook Marketplace',),
        ('Depop',),
        ('Vestiaire Collective',)
    ]
    categorie_iniziali = [
        ('Abbigliamento Uomo',),
        ('Abbigliamento Donna',),
        ('Scarpe',),
        ('Accessori/Borse',),
        ('Elettronica/Tech',),
        ('Collezionismo/Vintage',),
        ('Casa/Arredamento',),
        ('Libri/Media',),
        ('Altro',)
    ]
    cursor.executemany("INSERT OR IGNORE INTO stato (nome) VALUES (?)", stati_iniziali)
    cursor.executemany("INSERT OR IGNORE INTO categoria (nome) VALUES (?)", categorie_iniziali)
    cursor.executemany("INSERT OR IGNORE INTO piattaforma (nome) VALUES (?)", piattaforme_iniziali)

    connection.commit()
    connection.close()

#UTENTE
def get_or_create_user(telegram_user_id, nome_utente):
    """
    Controlla se un utente esiste in base al suo ID Telegram.
    Se non esiste, lo crea.
    Restituisce l'ID del database interno (non l'ID Telegram).
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()
    
    # 1. Prova a trovare l'utente
    cursore.execute("SELECT id FROM utente WHERE telegram_user_id = ?", (telegram_user_id,))
    utente = cursore.fetchone()
    
    if utente:
        # Utente trovato, restituisce il suo ID interno
        id_utente_db = utente[0]
    else:
        # Utente non trovato, lo crea
        cursore.execute(
            "INSERT INTO utente (telegram_user_id, nome_utente) VALUES (?, ?)",
            (telegram_user_id, nome_utente)
        )
        connessione.commit()
        id_utente_db = cursore.lastrowid # Ottiene l'ID appena creato
        print(f"Nuovo utente creato con ID database: {id_utente_db}")
        
    connessione.close()
    return id_utente_db

#MODIFICHE ALL'ANNUNCIO
def add_annuncement(id_utente, descrizione_input, titolo_generato, descrizione_generata, prezzo_suggerito, id_categoria):
    connection = sqlite3.connect('annunci.db')
    cursor = connection.cursor()

    id_stato_iniziale = 1

    sql_inserisci_annuncio = """
    INSERT INTO annuncio (
        id_utente,
        descrizione_input,
        titolo_generato,
        descrizione_generata,
        prezzo_suggerito,
        id_stato,
        id_categoria
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
    """

    # Dati da inserire, in ordine
    dati_annuncio = (
        id_utente,
        descrizione_input,
        titolo_generato,
        descrizione_generata,
        prezzo_suggerito,
        id_stato_iniziale,
        id_categoria
    )

    # Eseguiamo il comando in modo sicuro
    cursor.execute(sql_inserisci_annuncio, dati_annuncio)
    
    # Otteniamo l'ID dell'ultima riga inserita
    nuovo_id = cursor.lastrowid
    
    connection.commit()
    connection.close()
    return nuovo_id

def completa_annuncio_senza_data(id_utente, id_annuncio, id_categoria, id_piattaforma):
    """
    Salva categoria e piattaforma, ma lascia l'annuncio in stato 'bozza' (1)
    e senza data di pubblicazione.
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    # Lasciamo id_stato = 1 (bozza)
    sql_aggiorna = """
    UPDATE annuncio
    SET 
        id_categoria = ?,
        id_piattaforma = ?,
        data_pubblicazione = NULL
    WHERE id = ? AND id_utente = ?;
    """
    
    try:
        cursore.execute(sql_aggiorna, (id_categoria, id_piattaforma, id_annuncio, id_utente))
        connessione.commit()
        connessione.close()
        return True
    except Exception as e:
        print(f"Errore in completa_annuncio_senza_data: {e}")
        connessione.close()
        return False
    
def aggiorna_annuncio_con_programmazione(id_annuncio, id_categoria, id_piattaforma, data_pubblicazione):
    """
    Aggiorna un annuncio esistente con la categoria scelta e la data di programmazione.
    Imposta lo stato a 2 ('pubblicato').
    """
    connessione = sqlite3.connect("annunci.db")
    cursore = connessione.cursor()
 
    id_stato_pubblicato = 2 # Lo stato 'pubblicato'

    sql_aggiorna = """
    UPDATE annuncio
    SET 
        id_stato = ?,
        id_categoria = ?,
        id_piattaforma = ?,
        data_pubblicazione = ?
    WHERE id = ?;
    """

    dati = (
        id_stato_pubblicato, 
        id_categoria, 
        id_piattaforma, 
        data_pubblicazione, 
        id_annuncio
    )
    
    cursore.execute(sql_aggiorna, dati)
    connessione.commit()
    connessione.close()
    
def aggiorna_stato_annuncio(id_annuncio, id_nuovo_stato):
    """Aggiorna la colonna id_stato per un annuncio specifico."""
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    sql_aggiorna = "UPDATE annuncio SET id_stato = ? WHERE id = ?;"
    
    cursore.execute(sql_aggiorna, (id_nuovo_stato, id_annuncio))
    connessione.commit()
    connessione.close()

def segna_come_venduto(id_utente, id_annuncio, prezzo_vendita):
    """
    Aggiorna un annuncio come 'venduto'.
    Controlla che l'annuncio appartenga all'utente prima di aggiornarlo.
    Restituisce True se l'aggiornamento ha successo, False altrimenti.
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    # Lo stato 'venduto' ha id = 5 (in base alla nostra ultima logica)
    id_stato_venduto = 5

    sql_aggiorna = """
    UPDATE annuncio
    SET 
        id_stato = ?,
        prezzo_vendita = ?,
        data_vendita = CURRENT_TIMESTAMP
    WHERE 
        id = ? AND id_utente = ?; -- Controllo di sicurezza!
    """
    
    try:
        cursore.execute(sql_aggiorna, (
            id_stato_venduto, 
            prezzo_vendita, 
            id_annuncio, 
            id_utente
        ))
        
        connessione.commit()
        
        # 'rowcount' ci dice quante righe sono state modificate.
        # Se è 0, significa che l'annuncio non è stato trovato O non apparteneva all'utente.
        if cursore.rowcount == 0:
            connessione.close()
            return False
        
        connessione.close()
        return True

    except Exception as e:
        print(f"Errore in segna_come_venduto: {e}")
        connessione.close()
        return False

def disattiva_annuncio(id_utente, id_annuncio):
    """
    Esegue un 'soft delete' impostando is_cancellato = 1.
    Controlla che l'annuncio appartenga all'utente.
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    sql_disattiva = """
    UPDATE annuncio
    SET 
        is_cancellato = 1
    WHERE 
        id = ? AND id_utente = ?;
    """
    try:
        cursore.execute(sql_disattiva, (id_annuncio, id_utente))
        connessione.commit()
        
        if cursore.rowcount == 0:
            connessione.close()
            return False
        
        connessione.close()
        return True

    except Exception as e:
        print(f"Errore in disattiva_annuncio: {e}")
        connessione.close()
        return False

def aggiorna_campo_annuncio(id_utente, id_annuncio, campo, valore):
    """
    Aggiorna un singolo campo di un annuncio, controllando l'autorizzazione.
    ATTENZIONE: Questa funzione è sicura solo se 'campo' è
    controllato dal nostro codice e non dall'input dell'utente.
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    # Usiamo un f-string per il nome della colonna (sicuro, perché lo decidiamo noi)
    # e un '?' per il valore (per prevenire SQL injection)
    sql_aggiorna = f"""
    UPDATE annuncio
    SET {campo} = ?
    WHERE id = ? AND id_utente = ?;
    """
    
    try:
        cursore.execute(sql_aggiorna, (valore, id_annuncio, id_utente))
        connessione.commit()
        
        if cursore.rowcount == 0:
            connessione.close()
            return False
        
        connessione.close()
        return True

    except Exception as e:
        print(f"Errore in aggiorna_campo_annuncio: {e}")
        connessione.close()
        return False
    
#SELECT
def ottieni_annunci_attivi():
    """
    Recupera tutti gli annunci che sono 'programmati' (2) o 'pre-notificati' (3)
    e la cui data di pubblicazione è futura (o molto vicina).
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row 
    cursore = connessione.cursor()

    # Cerchiamo solo annunci che devono ancora essere gestiti (stato 2 o 3)
    # e la cui data è nel futuro (con un margine di 5 min nel passato
    # per sicurezza, se lo script si blocca)
    sql_query = """
    SELECT a.*, u.telegram_user_id
    FROM annuncio a
    JOIN utente u ON a.id_utente = u.id
    WHERE a.id_stato IN (2, 3)
      AND a.data_pubblicazione >= datetime('now', '-5 minutes')
      AND a.is_cancellato = 0;
    """
    
    cursore.execute(sql_query)
    annunci = cursore.fetchall()
    connessione.close()
    
    return [dict(annuncio) for annuncio in annunci]

def ottieni_statistiche_avanzate(id_utente):
    """
    Esegue una query complessa per calcolare tutte le statistiche
    per un utente specifico. Restituisce un singolo dizionario con i risultati.
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row # Per avere risultati come dizionari
    cursore = connessione.cursor()

    # Query SQL che calcola tutto in un colpo solo
    # Usiamo COALESCE(SUM(...), 0) per trasformare i NULL (se non ci sono vendite) in 0
    sql_query = """
    SELECT
        COUNT(a.id) AS totale_annunci,
        
        SUM(CASE WHEN s.nome = 'venduto' THEN 1 ELSE 0 END) AS totale_vendite,
        
        SUM(CASE WHEN s.nome IN ('programmato', 'pre-notificato') THEN 1 ELSE 0 END) AS totale_programmati,
        
        COALESCE(SUM(CASE WHEN s.nome = 'venduto' THEN a.prezzo_vendita ELSE 0 END), 0) AS guadagno_totale,
        
        COALESCE(SUM(CASE WHEN s.nome = 'venduto' AND a.data_vendita >= datetime('now', '-1 month') THEN a.prezzo_vendita ELSE 0 END), 0) AS guadagno_mese,
        
        COALESCE(SUM(CASE WHEN s.nome = 'venduto' AND a.data_vendita >= datetime('now', '-1 year') THEN a.prezzo_vendita ELSE 0 END), 0) AS guadagno_anno,

        COALESCE(SUM(CASE WHEN s.nome != 'venduto' THEN a.prezzo_suggerito ELSE 0 END), 0) AS stima_guadagno_futuro
        
    FROM 
        annuncio a
    LEFT JOIN 
        stato s ON a.id_stato = s.id
    WHERE 
        a.id_utente = ?
        AND a.is_cancellato = 0;
    """
    
    try:
        cursore.execute(sql_query, (id_utente,))
        # fetchone() perché ci aspettiamo una sola riga di risultati
        risultati = cursore.fetchone() 
        connessione.close()
        
        if risultati:
            return dict(risultati)
        else:
            # Se l'utente non esiste o non ha annunci, restituisce zero
            return {
                "totale_annunci": 0, "totale_vendite": 0, "totale_programmati": 0,
                "guadagno_totale": 0, "guadagno_mese": 0, "guadagno_anno": 0,
                "stima_guadagno_futuro": 0
            }
            
    except Exception as e:
        print(f"Errore in ottieni_statistiche_avanzate: {e}")
        connessione.close()
        return None

def ottieni_annunci_utente(id_utente):
    """
    Recupera tutti gli annunci per un utente specifico,
    ordinati per data di creazione (dal più recente).
    Include il nome dello stato.
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row # Per avere risultati come dizionari
    cursore = connessione.cursor()

    # Query SQL che unisce 'annuncio' e 'stati'
    # e filtra per uno specifico 'id_utente'
    sql_query = """
    SELECT 
        a.id,
        a.titolo_generato,
        a.data_creazione,
        s.nome AS nome_stato,
        a.data_pubblicazione
    FROM 
        annuncio a
    LEFT JOIN 
        stato s ON a.id_stato = s.id
    WHERE 
        a.id_utente = ?
        AND a.is_cancellato = 0
    ORDER BY 
        a.data_creazione DESC;
    """
    
    cursore.execute(sql_query, (id_utente,))
    annunci = cursore.fetchall()
    connessione.close()
    
    return [dict(riga) for riga in annunci]

def ottieni_annunci_non_venduti(id_utente):
    """
    Recupera tutti gli annunci per un utente che NON sono
    nello stato 'venduto' (id_stato = 5).
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row
    cursore = connessione.cursor()

    # Lo stato 'venduto' è 5 (nella nostra logica)
    sql_query = """
    SELECT id, titolo_generato
    FROM annuncio
    WHERE id_utente = ?
     AND (id_stato != 5 OR id_stato IS NULL)
     AND is_cancellato = 0
    ORDER BY data_creazione DESC
    LIMIT 10; -- Mostriamo solo i 10 più recenti per non intasare la chat
    """
    
    cursore.execute(sql_query, (id_utente,))
    annunci = cursore.fetchall()
    connessione.close()
    
    return [dict(riga) for riga in annunci]

def ottieni_categorie_attive():
    """Recupera tutte le categorie dalla tabella 'stati'."""
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row
    cursore = connessione.cursor()
    
    # Ordiniamo per nome
    cursore.execute("SELECT id, nome FROM categoria ORDER BY nome;")
    
    categorie = cursore.fetchall()
    connessione.close()
    return [dict(cat) for cat in categorie]

def ottieni_piattaforme_attive():
    """Recupera tutte le piattaforme dalla tabella 'piattaforme'."""
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row
    cursore = connessione.cursor()
    
    cursore.execute("SELECT id, nome FROM piattaforma ORDER BY nome;")
    
    piattaforme = cursore.fetchall()
    connessione.close()
    return [dict(p) for p in piattaforme]

def ottieni_dettagli_annuncio(id_utente, id_annuncio):
    """
    Recupera TUTTI i dettagli di un annuncio, unendo le tabelle
    per avere i nomi leggibili di stato e piattaforma.
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row
    cursore = connessione.cursor()

    sql_query = """
    SELECT 
        a.*,
        s.nome AS nome_stato,
        p.nome AS nome_piattaforma,
        c.nome AS categoria
    FROM annuncio a
    LEFT JOIN stato s ON a.id_stato = s.id
    LEFT JOIN categoria c ON a.id_categoria = c.id 
    LEFT JOIN piattaforma p ON a.id_piattaforma = p.id
    WHERE a.id = ? AND a.id_utente = ?;
    """
    # Nota: non filtriamo per is_cancellato=0 perché potremmo voler
    # vedere i dettagli anche di un annuncio nel cestino in futuro.
    
    cursore.execute(sql_query, (id_annuncio, id_utente))
    annuncio = cursore.fetchone()
    connessione.close()
    
    return dict(annuncio) if annuncio else None

#GRAFICI
def ottieni_dati_grafico_categorie(id_utente):
    """
    Restituisce i dati per un grafico a torta:
    Categoria -> Numero di vendite
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    # Conta gli annunci VENDUTI (id_stato=5) raggruppati per categoria
    sql = """
    SELECT c.nome AS categoria, COUNT(a.id) as conteggio
    FROM annuncio a
    LEFT JOIN categoria c ON a.id_categoria = c.id
    WHERE a.id_utente = ? AND a.id_stato = 5 AND a.is_cancellato = 0
    GROUP BY categoria;
    """
    cursore.execute(sql, (id_utente,))
    dati = cursore.fetchall()
    connessione.close()
    return dati # Ritorna una lista di tuple: [('Elettronica', 5), ('Abiti', 3)]

if __name__ == '__main__':
    db_initialization()
