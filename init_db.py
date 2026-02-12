import sqlite3
import os
from config import config

DB_NAME = config.DB_PATH

def init_db():
    # Controllo di sicurezza: se il DB esiste, chiede conferma prima di cancellarlo
    if os.path.exists(DB_NAME):
        answ = input(f"⚠️  ATTENZIONE: Il file '{DB_NAME}' esiste già.\nVuoi CANCELLARLO e ripartire da zero? (s/n): ")
        if answ.lower() == 's':
            os.remove(DB_NAME)
            print("🗑️  Vecchio database eliminato.")
        else:
            print("❌ Operazione annullata. Nessuna modifica effettuata.")
            return

    # Connessione e attivazione Foreign Keys
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;") 


    # ==========================================
    # 1. TABELLE DI CONFIGURAZIONE (Lookup)
    # ==========================================
    # Tabelle "dizionario" che contengono valori fissi
    cursor.execute('CREATE TABLE platform (id_platform INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')
    cursor.execute('CREATE TABLE category (id_category INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')
    cursor.execute('CREATE TABLE status_type (id_status_type INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')
    cursor.execute('CREATE TABLE file_type (id_file_type INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')
    
    # Provider esterni
    cursor.execute('CREATE TABLE ai_provider (id_ai_provider INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')
    cursor.execute('CREATE TABLE payment_provider (id_payment_provider INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);')

    # Tipi di abbonamento
    cursor.execute('''
    CREATE TABLE account_type (
        id_account_type INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        monthly_credits INTEGER,
        price_euro REAL
    );
    ''')

    # ==========================================
    # 2. TABELLE AI OPS (Gestione Modelli e Prompt)
    # ==========================================
    cursor.execute('''
    CREATE TABLE model (
        id_model INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        id_ai_provider INTEGER NOT NULL,
        FOREIGN KEY (id_ai_provider) REFERENCES ai_provider(id_ai_provider)
    );
    ''')

    cursor.execute('''
    CREATE TABLE prompt (
        id_prompt INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, 
        version TEXT,
        testo TEXT NOT NULL,
        created_datetime DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # ==========================================
    # 3. UTENTE (Anagrafica)
    # ==========================================
    cursor.execute('''
    CREATE TABLE user (
        id_telegram_user INTEGER PRIMARY KEY,
        username TEXT,
        fullname TEXT,
        join_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_active_datetime DATETIME,
        stripe_customer_id TEXT 
    );
    ''')

    # ==========================================
    # 4. TRANSAZIONI (Registro Pagamenti)
    # ==========================================
    # Nota: Non collegata direttamente a User per evitare ridondanza circolare.
    # Il collegamento logico avviene tramite la Subscription che questa transazione genera.
    cursor.execute('''
    CREATE TABLE transaction_history (
        id_transaction INTEGER PRIMARY KEY AUTOINCREMENT,
        
        description TEXT,
        payment_euro REAL,
        payment_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
        provider_transaction_id TEXT, 
        
        id_payment_provider INTEGER NOT NULL,
        
        FOREIGN KEY (id_payment_provider) REFERENCES payment_provider(id_payment_provider)
    );
    ''')

    # ==========================================
    # 5. SUBSCRIPTION (Stato Abbonamento)
    # ==========================================
    # Questa tabella unisce Utente, Tipo Account e Transazione
    cursor.execute('''
    CREATE TABLE subscription (
        id_subscription INTEGER PRIMARY KEY AUTOINCREMENT,
        
        subscription_start_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
        subscription_end_datetime DATETIME,
        credits_balance INTEGER DEFAULT 0,
        
        id_telegram_user INTEGER NOT NULL,
        id_account_type INTEGER NOT NULL,
        id_transaction INTEGER, -- Opzionale: NULL se Free, valorizzato se pagato
        
        FOREIGN KEY (id_telegram_user) REFERENCES user(id_telegram_user),
        FOREIGN KEY (id_account_type) REFERENCES account_type(id_account_type),
        FOREIGN KEY (id_transaction) REFERENCES transaction_history(id_transaction)
    );
    ''')

    # ==========================================
    # 6. ANNUNCI (Core Business)
    # ==========================================
    cursor.execute('''
    CREATE TABLE ad (
        id_ad INTEGER PRIMARY KEY AUTOINCREMENT,
        
        input_description TEXT,
        generated_title TEXT,
        generated_description TEXT,
        generated_hashtags TEXT,
        suggested_price REAL,
        created_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
        
        id_category INTEGER,
        id_telegram_user INTEGER NOT NULL,
        id_model INTEGER, 
        id_prompt INTEGER, 
        
        FOREIGN KEY (id_telegram_user) REFERENCES user(id_telegram_user),
        FOREIGN KEY (id_category) REFERENCES category(id_category),
        FOREIGN KEY (id_model) REFERENCES model(id_model),
        FOREIGN KEY (id_prompt) REFERENCES prompt(id_prompt)
    );
    ''')

    cursor.execute('''
    CREATE TABLE multimedia_file (
        id_multimedia_file INTEGER PRIMARY KEY AUTOINCREMENT,
        
        file_order INTEGER DEFAULT 0,
        telegram_file_id TEXT NOT NULL,
        
        id_file_type INTEGER NOT NULL,
        id_ad INTEGER NOT NULL,
        
        FOREIGN KEY (id_ad) REFERENCES ad(id_ad),
        FOREIGN KEY (id_file_type) REFERENCES file_type(id_file_type)
    );
    ''')

    # ==========================================
    # 7. PUBBLICAZIONI (Scheduling & Stati)
    # ==========================================
    cursor.execute('''
    CREATE TABLE publication_ad (
        id_publication_ad INTEGER PRIMARY KEY AUTOINCREMENT,
        
        scheduled_datetime DATETIME,
        publication_datetime DATETIME,
        sold_price REAL,
        sold_datetime DATETIME,
        deleted_datetime DATETIME,
        ad_url TEXT,
        
        id_status_type INTEGER NOT NULL,
        id_ad INTEGER NOT NULL,
        id_platform INTEGER NOT NULL,
        
        FOREIGN KEY (id_ad) REFERENCES ad(id_ad),
        FOREIGN KEY (id_platform) REFERENCES platform(id_platform),
        FOREIGN KEY (id_status_type) REFERENCES status_type(id_status_type)
    );
    ''')

    # ==========================================
    # 8. SEED DATA (Dati Iniziali)
    # ==========================================
    print("🌱  Inserimento dati base...")
    
    # Valori statici
    cursor.executemany("INSERT OR IGNORE INTO file_type (name) VALUES (?)", [('photo',), ('video',)])
    cursor.executemany("INSERT OR IGNORE INTO platform (name) VALUES (?)", [('Vinted',), ('Subito',), ('eBay',), ('Depop',), ('Wallapop',), ('Facebook Marketplace',)])
    cursor.executemany("INSERT OR IGNORE INTO category (name) VALUES (?)", [('Abbigliamento',), ('Scarpe',), ('Elettronica',), ('Casa',), ('Accessori',), ('Altro',)])
    cursor.executemany("INSERT OR IGNORE INTO status_type (name) VALUES (?)", [('DRAFT',), ('READY',), ('SCHEDULED',), ('PUBLISHED',), ('FAILED',), ('SOLD',), ('DELETED',), ('SOLD_OTHER_PLATFORM',), ('NOTIFIED_PRE',), ('NOTIFIED_FINAL',)])
    cursor.executemany("INSERT OR IGNORE INTO payment_provider (name) VALUES (?)", [('Stripe',), ('Telegram Stars',), ('PayPal',)])
    
    # Setup AI
    cursor.execute("INSERT OR IGNORE INTO ai_provider (name) VALUES (?)", ('Google',))
    # Recuperiamo l'ID appena creato per collegare il modello
    google_id = cursor.execute("SELECT id_ai_provider FROM ai_provider WHERE name='Google'").fetchone()[0]
    cursor.execute("INSERT OR IGNORE INTO model (name, id_ai_provider) VALUES (?, ?)", ('gemini-2.5-flash', google_id))

    # Setup Prompt
    prompt_text = """Segui rigorosamente queste istruzioni ottimizzate per un'esecuzione efficiente e coerente:

        1. **Analisi dell'Immagine Allegata (PRIORITARIO):**
            - Identifica con precisione l’oggetto (categoria, marca/modello se visibile).
            - Rileva il colore, le condizioni generali (segni d’uso, difetti o eventuali elementi come scatola/originalità), dimensioni stimate o proporzioni.
            - Nota qualsiasi dettaglio distintivo o valore aggiunto (es. edizione limitata, accessori inclusi).
            - Utilizza algoritmi di visione artificiale per massima accuratezza.

        2. **Analisi del Testo Utente** :
            - Includi solo se aggiunge dati non evidenti dalla foto (es. anno di acquisto, funzionalità specifiche, motivo della vendita).
            - Ignora ripetizioni o dati già visibili.

        3. **Generazione Annuncio (Seguendo il formato obbligatorio sotto):**
            - Combina dati da foto e testo solo se apportano valore informativo aggiuntivo.
            - Usa uno stile chiaro, dettagliato e accattivante. Nessun linguaggio vago o promozionale.
            **TONO:** Sii DIRETTO, INFORMATIVO e NATURALE, come un venditore privato. Registro linguistico medio.

        Testo Utente: "{product_description}"
        
        Formato UFFICIALE da rispettare ESATTAMENTE in output per popolare i campi:

        1.  **title (string):**
        - Titolo generato sull’oggetto principale identificato dalla foto ricco di parole chiave
        - Usa uno stile chiaro e commerciale (es.Vinted).

        2.  **description (string):**
        - Scrivi una descrizione amichevole e dettagliata.
        - inserire testo utente solo se aggiunge info extra
        - ALLA FINE della descrizione, INCLUDI SEMPRE un elenco puntato formattato usando i caratteri '\\n' (a capo) in questo modo:
        
        \\n\\nOggetto: [Nome preciso, anche con marca/modello]
        \\nCaratteristiche: [Condizioni, colore, dimensioni o altre specifiche fisiche e funzionali]
        \\nDettagli: [Un dettaglio visivo chiave visto in foto che può elevare il valore]

        3.  **price (float):**
        - Fornisci una stima di prezzo realistica in Euro
        - fondata sui dati di mercato dell'usato, tenendo conto delle condizioni, del modello/marca e di eventuali dettagli extra
        - usa fonti aggiornate o dataset di annunci usati se disponibili
        - Restituisci **SOLO UN SINGOLO NUMERO** (es. 25.0, 150, 22.50).
        - NON INCLUDERE "€", testo, o qualsiasi altro carattere non numerico. L'output per questo campo deve essere un numero JSON valido, non una stringa.
        
        **Note aggiuntive per l'IA:**
        - Ignora qualsiasi informazione priva di riscontro visivo o non verificabile.
        - Mantieni output coerente e privo di errori di formattazione o linguaggio.
        - Assicurati che ogni sezione sia sempre presente e rispettata, anche in caso di informazioni mancanti.
        - Adatta il registro linguistico all'ambito commerciale online (es. Subito, eBay, Facebook Marketplace)."""
    
    cursor.execute("INSERT OR IGNORE INTO prompt (name, version, testo) VALUES (?, ?, ?)", 
                   ('Standard Listing Generator', '1.0', prompt_text))

    # Piani Abbonamento
    account_data = [
        ('Free', 3, 0.00),
        ('Pro Launch', 150, 2.99),
        ('Ultimate Launch', 700, 4.99)
    ]
    cursor.executemany("INSERT OR IGNORE INTO account_type (name, monthly_credits, price_euro) VALUES (?, ?, ?)", account_data)

    conn.commit()
    conn.close()
    print("✅  DATABASE PRONTO. Struttura normalizzata creata con successo.")

if __name__ == "__main__":
    init_db()