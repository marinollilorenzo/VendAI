# 🤖 VendAI Bot

🇬🇧 [Read this document in English](README.md)

**VendAI** è un assistente personale su Telegram progettato per "power seller" che vendono su piattaforme come Vinted, Subito, Wallapop ed eBay.

Automatizza la parte noiosa della vendita: genera titoli e descrizioni accattivanti partendo da una foto grazie all'IA, suggerisce il prezzo, gestisce un inventario privato e ti ricorda quando pubblicare gli annunci per massimizzare la visibilità.

## ✨ Funzionalità Principali

* 🧠 **Intelligenza Artificiale Multimodale:** Invia una foto e il bot genererà titolo, descrizione dettagliata e un prezzo suggerito ottimizzati per la vendita.
* 📝 **Wizard di Modifica Interattivo:** Rivedi e perfeziona i testi generati dall'IA prima di salvarli, con un'interfaccia intuitiva a pulsanti.
* 📅 **Programmazione Intelligente:** Imposta una data futura (es. "domani alle 18:30") e ricevi notifiche precise (30 minuti prima e all'ora esatta) per pubblicare manualmente.
* 🗂️ **Inventario Multi-Utente:** Ogni utente ha il suo database privato di annunci, isolato dagli altri.
* 📊 **Dashboard Analitica:** Visualizza grafici e statistiche sui tuoi guadagni, le tue performance di vendita e il valore del tuo inventario.
* 🗑️ **Soft Delete:** Non perdi mai i tuoi dati. Gli annunci eliminati possono essere recuperati dal database se necessario.

## 📸 Demo

*(Sostituisci questa sezione con i tuoi screenshot o GIF)*

| Menu Principale | Creazione con IA | Dashboard Analisi |
| :---: | :---: | :---: |
| ![Menu](assets/screenshot_menu.png) | ![Creazione](assets/screenshot_crea.png) | ![Analisi](assets/screenshot_analisi.png) |

## 🛠️ Installazione

### Prerequisiti
* Python 3.9 o superiore
* Un bot Telegram (creato tramite [@BotFather](https://t.me/BotFather))
* Una chiave API di Google Gemini (ottenibile gratuitamente da [Google AI Studio](https://aistudio.google.com/))

### Setup Passo-Passo

1.  **Clona il repository:**
    ```bash
    git clone [https://github.com/marinollilorenzo/VendAI.git](https://github.com/marinollilorenzo/VendAI.git)
    cd VendAI
    ```

2.  **Crea e attiva l'ambiente virtuale (raccomandato):**
    ```bash
    # Su macOS/Linux:
    python3 -m venv venv
    source venv/bin/activate

    # Su Windows:
    python -m venv venv
    venv\Scripts\activate
    ```

3.  **Installa le dipendenze:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configura le variabili d'ambiente:**
    Crea un file chiamato `.env` nella cartella principale del progetto e inserisci le tue chiavi segrete:
    ```env
    TOKEN=il_tuo_token_bot_telegram
    GEMINI_API_KEY=la_tua_chiave_google_ai_studio
    ```

## 🚀 Avvio

Il bot è composto da due processi che devono essere eseguiti contemporaneamente (in due terminali separati, o usando un process manager).

1.  **Il Bot Interattivo (gestisce i comandi utente):**
    ```bash
    python3 main.py
    ```

2.  **Il Guardiano delle Notifiche (gestisce gli orari):**
    ```bash
    python3 notifier.py
    ```

## 🤝 Contribuire

I contributi sono benvenuti! Sentiti libero di aprire una "Issue" per segnalare bug o proporre nuove funzionalità, oppure invia una "Pull Request".

## 📄 Licenza

Questo progetto è distribuito sotto licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.

---
**Nota:** Questo è un progetto indipendente e non è affiliato, associato, autorizzato, approvato da, o in alcun modo ufficialmente connesso con Vinted, Subito.it, Wallapop, o qualsiasi altra piattaforma menzionata.