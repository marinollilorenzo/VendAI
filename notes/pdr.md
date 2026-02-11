PRD: VendAI Bot 2.0 (MVP Launch)
1. Introduction
VendAI è un bot Telegram che assiste gli utenti nella vendita di oggetti usati su piattaforme second-hand (Vinted, Subito, ecc.). Utilizzando l'AI (Google Gemini), analizza le foto degli oggetti e genera automaticamente titoli, descrizioni e stime di prezzo ottimizzate. Il servizio opera con un modello "Freemium" (crediti limitati gratuiti) e piani "Pro" in abbonamento gestiti tramite Stripe.

2. Goals
Automazione: Ridurre il tempo di creazione di un annuncio da 5 minuti a <30 secondi.

Monetizzazione: Implementare un sistema di crediti e abbonamenti funzionante (Stripe) per rendere il progetto sostenibile.

Semplicità: Mantenere l'interazione basata su tasti/percorsi predefiniti (come da versione 1.0) ma con backend potenziato.

Affidabilità: Gestire il flusso su un server con risorse limitate (1GB RAM) usando SQLite e codice asincrono.

3. User Stories
US-001: Creazione Annuncio (Singola Foto)
Description: Come utente, voglio inviare una foto del mio oggetto e ottenere subito titolo, descrizione e prezzo senza dover scrivere nulla.
Acceptance Criteria:

[ ] L'utente invia una foto (compresso o file).

[ ] Il bot mostra stato "Analisi in corso...".

[ ] Il bot restituisce un messaggio formattato con Titolo, Descrizione, Prezzo e Hashtag.

[ ] I crediti dell'utente vengono decrementati di 1.

US-002: Gestione Crediti & Paywall
Description: Come utente Free, voglio sapere quanti crediti ho e venire bloccato se li esaurisco.
Acceptance Criteria:

[ ] Comando/Tasto 👤 Profilo mostra il saldo crediti attuale.

[ ] Se il saldo è 0, al tentativo di analisi il bot risponde con messaggio di blocco e invito all'upgrade.

[ ] Reset automatico mensile per utenti Free (3 crediti).

US-003: Upgrade a Pro (Pagamento Reale)
Description: Come utente, voglio acquistare l'abbonamento Pro per avere più crediti.
Acceptance Criteria:

[ ] Tasto 💎 Diventa Pro genera un link di pagamento Stripe (Checkout).

[ ] Dopo il pagamento, il bot riceve conferma (Polling/Webhook) e aggiorna lo stato utente a "Pro".

[ ] L'utente riceve notifica di avvenuta attivazione.

US-004: Scheduling (Promemoria "Ready-to-Post")
Description: Come utente, voglio programmare la pubblicazione di un annuncio per un momento migliore.
Acceptance Criteria:

[ ] Dopo la generazione, tasto ⏰ Programma.

[ ] L'utente sceglie l'orario.

[ ] All'ora X, il bot invia un messaggio con: Foto dell'oggetto + Testo dell'annuncio + Dati piattaforma (es. categoria suggerita).

[ ] Messaggio include invito "Copia e pubblica ora".

4. Functional Requirements
Core Logic
FR-1: Il sistema deve accettare solo 1 foto per annuncio in questa fase (MVP).

FR-2: L'integrazione AI deve usare gemini-1.5-flash per bilanciare velocità/costo.

FR-3: Il prompt di sistema deve seguire rigorosamente il template definito nel database (Tabella prompt).

Database & State
FR-4: Ogni operazione di analisi deve creare un record in ad e collegare il telegram_file_id in multimedia_file.

FR-5: Lo stato dell'abbonamento deve essere verificato tramite le date (subscription_end_datetime) prima di ogni operazione critica.

Payments
FR-6: Integrazione Stripe in modalità "Checkout Session".

FR-7: Salvataggio della transazione in transaction_history con provider_transaction_id per audit.

5. Non-Goals (Out of Scope)
Nessun supporto per album fotografici o video (v2.1).

Nessuna pubblicazione automatica su Vinted/Subito (API non disponibili).

Nessun pannello di amministrazione grafico (solo SQL diretto).

Nessun supporto per provider AI diversi da Google per ora.

6. Technical Considerations
Resource Cap: Il bot non deve mai superare 600MB di RAM occupata.

Concurrency: Utilizzo di asyncio per gestire attese I/O (Stripe/Gemini) senza bloccare il thread principale.

Database: SQLite con WAL mode (Write-Ahead Logging) abilitato per migliori performance concorrenti.

Scheduling: Loop di controllo interno (apscheduler o loop asyncio semplice) che controlla il DB ogni minuto.

7. Success Metrics
Tempo medio di risposta (Analisi) < 10 secondi.

0 Crash per "Out of Memory" con 50 utenti attivi/giorno.

Funzionamento corretto del flusso di pagamento Stripe (User -> Pro -> DB aggiornato).

🗺️ Roadmap di Sviluppo (Piano di Lavoro)
Ecco come procederemo per costruire il codice, modulo per modulo:

Fase 1: Setup & Configurazione (FATTO ✅)

Database inizializzato (init_db.py).

Struttura file definita.

Fase 2: Lo Scheletro del Bot (Prossimo Step)

Creazione main.py e config.py.

Connessione al DB SQLite.

Setup dei comandi base (/start, /help, 👤 Profilo).

Obiettivo: Il bot si accende e risponde ai comandi base.

Fase 3: Il Cuore AI (Analisi Foto)

Gestione ricezione foto.

Chiamata API a Gemini.

Salvataggio dati nel DB (ad, multimedia_file).

Risposta formattata all'utente.

Obiettivo: Mandi foto -> Ricevi annuncio.

Fase 4: Il Business (Sistema Crediti)

Middleware che controlla i crediti prima di chiamare l'AI.

Logica di decremento crediti.

Gestione utenti Free vs Pro.

Fase 5: I Pagamenti (Stripe)

Generazione Link Pagamento.

Gestione conferma (tramite polling sulle API Stripe o webhook semplificato).

Upgrade dell'utente nel DB.

Fase 6: Lo Scheduler

Sistema per salvare la data di programmazione.

Processo in background che controlla ogni minuto se ci sono annunci da "notificare".