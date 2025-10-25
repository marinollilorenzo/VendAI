import sqlite3

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
        prezzo_suggerito TEXT,
        id_stato INTEGER,
        id_piattaforma INTEGER,
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_pubblicazione TIMESTAMP,
        prezzo_vendita REAL,
        data_vendita TIMESTAMP,
        id_categoria INTEGER,
        FOREIGN KEY (id_stato) REFERENCES stato (id),
        FOREIGN KEY (id_categoria) REFERENCES categoria (id),
        FOREIGN KEY (id_piattaforma) REFERENCES piattaforma (id)
        FOREIGN KEY (id_utente) REFERENCES utente (id)
    );
    """)
    stati_iniziali = [
        ('bozza',),          # 1
        ('programmato',),    # 2 (impostato dal bot)
        ('pre-notificato',), # 3 (impostato dal notifier)
        ('notificato',),     # 4 (impostato dal notifier)
        ('venduto',)         # 5 (da implementare)
    ]
    categorie_iniziali = [('Abbigliamento',), ('elettronica',), ('libri/hobby',), ('casa',), ('altro',)]
    piattaforme_iniziali = [('Vinted',), ('Subito',), ('Wallapop',), ('Vestaire Collection',)]
    
    cursor.executemany("INSERT OR IGNORE INTO stato (nome) VALUES (?)", stati_iniziali)
    cursor.executemany("INSERT OR IGNORE INTO categoria (nome) VALUES (?)", categorie_iniziali)
    cursor.executemany("INSERT OR IGNORE INTO piattaforma (nome) VALUES (?)", piattaforme_iniziali)

    connection.commit()
    connection.close()
    
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
    
    print(f"Annuncio salvato con successo nel database. ID: {nuovo_id}")
    return nuovo_id


def aggiorna_annuncio_con_programmazione(id_annuncio, id_categoria, data_pubblicazione):
    """
    Aggiorna un annuncio esistente con la categoria scelta e la data di programmazione.
    Imposta lo stato a 2 ('pubblicato').
    """
    connessione = sqlite3.connect("annunci.db")
    cursore = connessione.cursor()

    # Per ora impostiamo la piattaforma a 1 (Vinted)
    id_piattaforma_default = 1 
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
        id_piattaforma_default, 
        data_pubblicazione, 
        id_annuncio
    )
    
    cursore.execute(sql_aggiorna, dati)
    connessione.commit()
    connessione.close()
    
    print(f"Annuncio {id_annuncio} aggiornato. Programmazione: {data_pubblicazione}.")


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
      AND a.data_pubblicazione >= datetime('now', '-5 minutes');
    """
    
    cursore.execute(sql_query)
    annunci = cursore.fetchall()
    connessione.close()
    
    return [dict(annuncio) for annuncio in annunci]

def aggiorna_stato_annuncio(id_annuncio, id_nuovo_stato):
    """Aggiorna la colonna id_stato per un annuncio specifico."""
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    sql_aggiorna = "UPDATE annuncio SET id_stato = ? WHERE id = ?;"
    
    cursore.execute(sql_aggiorna, (id_nuovo_stato, id_annuncio))
    connessione.commit()
    connessione.close()
    
    print(f"Annuncio {id_annuncio} aggiornato allo stato {id_nuovo_stato}.")


def ottieni_statistiche_stati(id_utente):
    """
    Conta quanti annunci ci sono per ogni stato,
    restituendo il nome dello stato e il conteggio.
    """
    connessione = sqlite3.connect('annunci.db')
    connessione.row_factory = sqlite3.Row # Per avere risultati come dizionari
    cursore = connessione.cursor()

    # Questa query SQL unisce le tabelle 'annuncio' e 'stati',
    # raggruppa per nome dello stato e conta gli annunci per gruppo.
    sql_query = """
    SELECT 
        s.nome AS nome_stato,
        COUNT(a.id) AS conteggio
    FROM 
        annuncio a
    JOIN 
        stato s ON a.id_stato = s.id
    WHERE a.id_utente = ?
    GROUP BY 
        s.nome
    ORDER BY 
        conteggio DESC;
    """
    
    cursore.execute(sql_query, (id_utente,))
    statistiche = cursore.fetchall()
    connessione.close()
    
    # Ritorna una lista di dizionari, es: [{'nome_stato': 'programmato', 'conteggio': 5}, ...]
    return [dict(riga) for riga in statistiche]

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
    WHERE id_utente = ? AND (id_stato != 5 OR id_stato IS NULL)
    ORDER BY data_creazione DESC
    LIMIT 10; -- Mostriamo solo i 10 più recenti per non intasare la chat
    """
    
    cursore.execute(sql_query, (id_utente,))
    annunci = cursore.fetchall()
    connessione.close()
    
    return [dict(riga) for riga in annunci]

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
            print(f"Tentativo di vendita fallito per annuncio {id_annuncio} dall'utente {id_utente}. Annuncio non trovato o non autorizzato.")
            connessione.close()
            return False
        
        connessione.close()
        print(f"Annuncio {id_annuncio} segnato come venduto per l'utente {id_utente} a {prezzo_vendita}€.")
        return True

    except Exception as e:
        print(f"Errore in segna_come_venduto: {e}")
        connessione.close()
        return False

def elimina_annuncio(id_utente, id_annuncio):
    """
    Elimina un annuncio specifico, controllando che appartenga all'utente.
    Restituisce True se l'eliminazione ha successo, False altrimenti.
    """
    connessione = sqlite3.connect('annunci.db')
    cursore = connessione.cursor()

    sql_elimina = "DELETE FROM annuncio WHERE id = ? AND id_utente = ?;"
    
    try:
        cursore.execute(sql_elimina, (id_annuncio, id_utente))
        connessione.commit()
        
        # Controlliamo se è stata eliminata effettivamente una riga
        if cursore.rowcount > 0:
            print(f"Annuncio {id_annuncio} eliminato correttamente per utente {id_utente}.")
            connessione.close()
            return True
        else:
            print(f"Tentativo di eliminazione fallito per annuncio {id_annuncio}, utente {id_utente}. Annuncio non trovato o non autorizzato.")
            connessione.close()
            return False
            
    except Exception as e:
        print(f"Errore in elimina_annuncio: {e}")
        connessione.close()
        return False
    
if __name__ == '__main__':
    db_initialization()
