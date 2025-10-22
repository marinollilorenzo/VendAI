import sqlite3

def db_initialization():
    connection = sqlite3.connect("annunci.db")
    cursor = connection.cursor
    
    cursor.execute("PRAGMA foreign_keys = ON;");
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stato(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    
    CREATE TABLE IF NOT EXISTS piattaforma(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE
    );
    
    CREATE TABLE IF NOT EXIST annuncio(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descrizione_input TEXT NOT NULL,
        titolo_generato TEXT,
        prezzo_suggerito TEXT,
        id_stato INTEGER,
        id_piattaforma INTEGER,
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_pubblicazione TIMESTAMP,
        prezzo_vendita REAL,
        data_vendita TIMESTAMP,
        categoria TEXT,
        FOREIGN KEY (id_stato) REFERENCES stato (id),
        FOREIGN KEY (id_piattaforma) REFERENCES piattaforma (id)
    );
    """)
    stati_iniziali = [('bozza'), ('pubblicato'), ('venduto')]
    piattaforme_iniziali = [('Vinted'), ('Subito'), ('Wallapop'), ('Vestaire Collection')]
    
    cursor.executemany("INSERT OR IGNORE INTO stato (nome) VALUES (?)", stati_iniziali)
    cursor.executemany("INSERT OR IGNORE INTO piattaforma (nome) VALUES (?)", piattaforme_iniziali)

    connection.commit()
    connection.close()


def add_annuncement(descrizione_input, titolo_generato, descrizione_generata, prezzo_suggerito, categoria):
    connection = sqlite3.connect('annunci.db')
    cursor = connection.cursor()

    id_stato_iniziale = 1

    sql_inserisci_annuncio = """
    INSERT INTO annuncio (
        descrizione_input,
        titolo_generato,
        descrizione_generata,
        prezzo_suggerito,
        id_stato,
        categoria
    ) VALUES (?, ?, ?, ?, ?, ?);
    """

    # Dati da inserire, in ordine
    dati_annuncio = (
        descrizione_input,
        titolo_generato,
        descrizione_generata,
        prezzo_suggerito,
        id_stato_iniziale,
        categoria
    )

    # Eseguiamo il comando in modo sicuro
    cursor.execute(sql_inserisci_annuncio, dati_annuncio)
    
    # Otteniamo l'ID dell'ultima riga inserita
    nuovo_id = cursor.lastrowid
    
    connection.commit()
    connection.close()
    
    print(f"Annuncio salvato con successo nel database. ID: {nuovo_id}")
    return nuovo_id


if __name__ == '__main__':
    db_initialization()
