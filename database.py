import aiosqlite
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages all database operations for the application.
    Provides asynchronous methods for interacting with the SQLite database.
    Ensures a single database connection per instance and handles error logging.
    """
    def __init__(self, db_path="annunci.db"):
        """
        Initializes the DatabaseManager with the path to the SQLite database.
        The database connection is established lazily upon the first query.
        """
        self.db_path = db_path
        self.conn = None # Initialize connection to None

    async def _get_connection(self):
        """
        Establishes and returns an asynchronous database connection.
        Ensures PRAGMA foreign_keys = ON and PRAGMA journal_mode = WAL are set.
        The connection is reused for subsequent calls within the same instance.
        """
        if self.conn is None:
            try:
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row # To get results as dictionary-like objects
                await self.conn.execute("PRAGMA foreign_keys = ON;")
                await self.conn.execute("PRAGMA journal_mode = WAL;") # Ensures Write-Ahead Logging for better concurrency
                logger.info(f"Database connection established to {self.db_path} with WAL mode.")
            except Exception as e:
                logger.error(f"Failed to establish database connection: {e}")
                raise # Re-raise the exception after logging
        return self.conn

    async def close(self):
        """
        Closes the database connection if it is open.
        This should be called when the application is shutting down.
        """
        if self.conn:
            try:
                await self.conn.close()
                self.conn = None
                logger.info("Database connection closed.")
            except Exception as e:
                logger.error(f"Failed to close database connection: {e}")
                raise # Re-raise the exception after logging

    async def _execute_query(self, query, params=()):
        """
        Executes an SQL query with optional parameters and commits the transaction.
        Logs any errors and re-raises them.
        Returns the row ID of the last inserted row.
        """
        conn = await self._get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                await conn.commit()
                return cursor.lastrowid # Returns the row ID of the last INSERT
        except Exception as e:
            logger.error(f"Error executing query: {query} with params {params} - {e}")
            raise # Re-raise the exception after logging

    async def _fetch_one(self, query, params=()):
        """
        Executes an SQL query and fetches a single row.
        Logs any errors and re-raises them.
        Returns the row as a dictionary-like object, or None if no result.
        """
        conn = await self._get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching one row: {query} with params {params} - {e}")
            raise # Re-raise the exception after logging

    async def _fetch_all(self, query, params=()):
        """
        Executes an SQL query and fetches all rows.
        Logs any errors and re-raises them.
        Returns a list of dictionary-like objects, or an empty list if no results.
        """
        conn = await self._get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                results = await cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching all rows: {query} with params {params} - {e}")
            raise # Re-raise the exception after logging

    # --- USER FUNCTIONS ---
    async def get_or_create_user(self, telegram_user_id: int, username: str = None, fullname: str = None):
        """
        Checks if a user exists by their Telegram ID. If not, a new user is created.
        The `last_active_datetime` is set upon creation or updated if the user exists.
        Returns the user's `id_telegram_user`.
        """
        user = await self._fetch_one(
            "SELECT id_telegram_user FROM user WHERE id_telegram_user = ?",
            (telegram_user_id,)
        )
        if user:
            logger.info(f"User {telegram_user_id} found.")
            await self.update_user_last_active(telegram_user_id) # UPDATE LAST ACTIVE (Automazione)
            return user['id_telegram_user']
        else:
            now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await self._execute_query(
                "INSERT INTO user (id_telegram_user, username, fullname, join_datetime, last_active_datetime) VALUES (?, ?, ?, ?, ?)",
                (telegram_user_id, username, fullname, now_iso, now_iso)
            )
            logger.info(f"New user {telegram_user_id} created.")
            return telegram_user_id

    async def update_user_last_active(self, telegram_user_id: int):
        """
        Updates the `last_active_datetime` for a specific user.
        The datetime is converted to an ISO 8601 string for SQLite compatibility.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_count = await self._execute_query(
            "UPDATE user SET last_active_datetime = ? WHERE id_telegram_user = ?",
            (now_iso, telegram_user_id)
        )
        if row_count > 0:
            logger.info(f"User {telegram_user_id} last active time updated.")
        else:
            logger.warning(f"User {telegram_user_id} not found for last active update.")

    # --- AD FUNCTIONS ---
    async def add_ad(self, id_telegram_user: int, input_description: str,
                     generated_title: str = None, generated_description: str = None,
                     suggested_price: float = None, id_category: int = None,
                     id_model: int = None, id_prompt: int = None):
        """
        Adds a new advertisement entry to the `ad` table.
        The `created_datetime` is explicitly generated in Python.
        Returns the `id_ad` of the newly created advertisement.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        INSERT INTO ad (
            id_telegram_user, input_description, generated_title,
            generated_description, suggested_price, id_category,
            id_model, id_prompt, created_datetime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            id_telegram_user, input_description, generated_title,
            generated_description, suggested_price, id_category,
            id_model, id_prompt, now_iso
        )
        new_ad_id = await self._execute_query(query, params)
        logger.info(f"New ad {new_ad_id} added for user {id_telegram_user}.")
        await self.update_user_last_active(id_telegram_user) # UPDATE LAST ACTIVE (Automazione)
        return new_ad_id

    async def update_ad_details(self, id_ad: int, id_telegram_user: int,
                                generated_title: str = None, generated_description: str = None,
                                generated_hashtags: str = None, suggested_price: float = None,
                                id_category: int = None, id_model: int = None, id_prompt: int = None):
        """
        Updates specific fields of an existing advertisement in the `ad` table.
        Ensures the ad belongs to the specified user before updating.
        """
        set_clauses = []
        params = []
        if generated_title is not None:
            set_clauses.append("generated_title = ?")
            params.append(generated_title)
        if generated_description is not None:
            set_clauses.append("generated_description = ?")
            params.append(generated_description)
        if generated_hashtags is not None:
            set_clauses.append("generated_hashtags = ?")
            params.append(generated_hashtags)
        if suggested_price is not None:
            set_clauses.append("suggested_price = ?")
            params.append(suggested_price)
        if id_category is not None:
            set_clauses.append("id_category = ?")
            params.append(id_category)
        if id_model is not None:
            set_clauses.append("id_model = ?")
            params.append(id_model)
        if id_prompt is not None:
            set_clauses.append("id_prompt = ?")
            params.append(id_prompt)

        if not set_clauses:
            logger.info(f"No details to update for ad {id_ad}.")
            return 0 # No fields to update

        query = f"UPDATE ad SET {', '.join(set_clauses)} WHERE id_ad = ? AND id_telegram_user = ?"
        params.extend([id_ad, id_telegram_user])
        
        row_count = await self._execute_query(query, params)
        if row_count > 0:
            logger.info(f"Ad {id_ad} details updated for user {id_telegram_user}.")
            await self.update_user_last_active(id_telegram_user) # UPDATE LAST ACTIVE (Automazione)
        else:
            logger.warning(f"Ad {id_ad} not found or not owned by user {id_telegram_user} for update.")
        return row_count

    async def get_ad_details(self, id_ad: int, id_telegram_user: int):
        """
        Retrieves all details of a specific advertisement, including associated category,
        status, and platform names. It joins with the latest publication entry to avoid duplicates.
        """
        query = """
        SELECT
            a.id_ad, a.input_description, a.generated_title, a.generated_description,
            a.generated_hashtags, a.suggested_price, a.created_datetime,
            c.name AS category_name,
            pa.id_publication_ad, pa.scheduled_datetime, pa.publication_datetime,
            pa.sold_price, pa.sold_datetime, pa.deleted_datetime, pa.ad_url,
            st.name AS status_name,
            p.name AS platform_name
        FROM ad AS a
        LEFT JOIN category AS c ON a.id_category = c.id_category
        LEFT JOIN (
            SELECT *,
                   ROW_NUMBER() OVER(PARTITION BY id_ad ORDER BY scheduled_datetime DESC, id_publication_ad DESC) as rn
            FROM publication_ad
        ) AS pa ON a.id_ad = pa.id_ad AND pa.rn = 1
        LEFT JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        LEFT JOIN platform AS p ON pa.id_platform = p.id_platform
        WHERE a.id_ad = ? AND a.id_telegram_user = ?
        """
        result = await self._fetch_one(query, (id_ad, id_telegram_user))
        if result:
            logger.info(f"Fetched details for ad {id_ad} for user {id_telegram_user}.")
        else:
            logger.info(f"Ad {id_ad} not found for user {id_telegram_user}.")
        return result

    async def get_user_ads(self, id_telegram_user: int, limit: int = 10, offset: int = 0):
        """
        Retrieves a paginated list of advertisements for a specific user,
        ordered by creation date. Includes details from the latest publication if available.
        """
        query = """
        SELECT
            a.id_ad, a.generated_title, a.created_datetime,
            st.name AS status_name,
            pa.scheduled_datetime, pa.publication_datetime
        FROM ad AS a
        LEFT JOIN (
            SELECT *,
                   ROW_NUMBER() OVER(PARTITION BY id_ad ORDER BY scheduled_datetime DESC, id_publication_ad DESC) as rn
            FROM publication_ad
        ) AS pa ON a.id_ad = pa.id_ad AND pa.rn = 1
        LEFT JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        WHERE a.id_telegram_user = ?
        ORDER BY a.created_datetime DESC
        LIMIT ? OFFSET ?
        """
        results = await self._fetch_all(query, (id_telegram_user, limit, offset))
        logger.info(f"Fetched {len(results)} ads for user {id_telegram_user}.")
        return results

    async def get_active_ads_for_scheduling(self):
        """
        Retrieves advertisements that are currently scheduled or ready for publication.
        Considers ads with a `scheduled_datetime` in the near past or future
        and that have not been deleted.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        SELECT
            a.id_ad, a.generated_title, a.generated_description, a.generated_hashtags,
            a.suggested_price, a.input_description,
            u.id_telegram_user,
            pa.id_publication_ad, pa.scheduled_datetime, pa.publication_datetime,
            pa.ad_url, p.name AS platform_name
        FROM ad AS a
        JOIN user AS u ON a.id_telegram_user = u.id_telegram_user
        JOIN publication_ad AS pa ON a.id_ad = pa.id_ad
        JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        JOIN platform AS p ON pa.id_platform = p.id_platform
        WHERE st.name IN ('SCHEDULED', 'READY')
        AND pa.scheduled_datetime <= ?
        AND pa.deleted_datetime IS NULL
        """
        results = await self._fetch_all(query, (now_iso,))
        logger.info(f"Fetched {len(results)} active ads for scheduling.")
        return results
    
    async def get_non_sold_ads(self, id_telegram_user: int, limit: int = 10):
        """
        Retrieves a paginated list of advertisements for a user that are not in 'SOLD' status.
        Includes details from the latest publication and excludes deleted ads.
        """
        query = """
        SELECT
            a.id_ad, a.generated_title,
            pa.id_publication_ad, st.name AS status_name
        FROM ad AS a
        LEFT JOIN (
            SELECT *,
                   ROW_NUMBER() OVER(PARTITION BY id_ad ORDER BY scheduled_datetime DESC, id_publication_ad DESC) as rn
            FROM publication_ad
        ) AS pa ON a.id_ad = pa.id_ad AND pa.rn = 1
        LEFT JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        WHERE a.id_telegram_user = ?
        AND (st.name != 'SOLD' OR st.name IS NULL)
        AND pa.deleted_datetime IS NULL
        ORDER BY a.created_datetime DESC
        LIMIT ?
        """
        results = await self._fetch_all(query, (id_telegram_user, limit))
        logger.info(f"Fetched {len(results)} non-sold ads for user {id_telegram_user}.")
        return results

    # --- PUBLICATION FUNCTIONS ---
    async def add_publication_entry(self, id_ad: int, id_platform: int, id_status_type: int,
                                    scheduled_datetime: datetime = None):
        """
        Adds a new publication entry for an advertisement to the `publication_ad` table.
        The `scheduled_datetime` is converted to an ISO 8601 string.
        Returns the `id_publication_ad` of the new entry.
        """
        scheduled_datetime_iso = scheduled_datetime.strftime("%Y-%m-%d %H:%M:%S") if scheduled_datetime else None
        query = """
        INSERT INTO publication_ad (
            id_ad, id_platform, id_status_type, scheduled_datetime
        ) VALUES (?, ?, ?, ?)
        """
        params = (id_ad, id_platform, id_status_type, scheduled_datetime_iso)
        new_publication_id = await self._execute_query(query, params)
        logger.info(f"New publication entry {new_publication_id} added for ad {id_ad}.")
        return new_publication_id

    async def update_publication_status(self, id_publication_ad: int, status_name: str,
                                        publication_datetime: datetime = None, ad_url: str = None):
        """
        Updates the status, publication datetime, and URL for a specific publication entry.
        The new `id_status_type` is retrieved based on `status_name`.
        """
        status = await self._fetch_one("SELECT id_status_type FROM status_type WHERE name = ?", (status_name,))
        if not status:
            logger.error(f"Status '{status_name}' not found for updating publication {id_publication_ad}.")
            raise ValueError(f"Status '{status_name}' not found.")
        id_status_type = status['id_status_type']

        set_clauses = ["id_status_type = ?"]
        params = [id_status_type]

        if publication_datetime is not None:
            publication_datetime_iso = publication_datetime.strftime("%Y-%m-%d %H:%M:%S")
            set_clauses.append("publication_datetime = ?")
            params.append(publication_datetime_iso)
        if ad_url is not None:
            set_clauses.append("ad_url = ?")
            params.append(ad_url)

        query = f"UPDATE publication_ad SET {', '.join(set_clauses)} WHERE id_publication_ad = ?"
        params.append(id_publication_ad)
        
        row_count = await self._execute_query(query, params)
        if row_count > 0:
            logger.info(f"Publication {id_publication_ad} status updated to {status_name}.")
        else:
            logger.warning(f"Publication {id_publication_ad} not found for status update.")
        return row_count

    async def mark_publication_as_sold(self, id_publication_ad: int, sold_price: float):
        """
        Marks a specific publication entry as 'SOLD', recording the sold price and sale datetime.
        The sale datetime is converted to an ISO 8601 string.
        """
        status = await self._fetch_one("SELECT id_status_type FROM status_type WHERE name = 'SOLD'")
        if not status:
            logger.error("Status 'SOLD' not found in status_type table.")
            raise ValueError("Status 'SOLD' not found.")
        id_status_type = status['id_status_type']

        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        UPDATE publication_ad
        SET id_status_type = ?, sold_price = ?, sold_datetime = ?
        WHERE id_publication_ad = ?
        """
        params = (id_status_type, sold_price, now_iso, id_publication_ad)
        
        row_count = await self._execute_query(query, params)
        if row_count > 0:
            logger.info(f"Publication {id_publication_ad} marked as SOLD with price {sold_price}.")
        else:
            logger.warning(f"Publication {id_publication_ad} not found for marking as sold.")
        return row_count

    async def mark_publication_as_deleted(self, id_publication_ad: int):
        """
        Marks a specific publication entry as deleted by setting its `deleted_datetime`.
        The deletion datetime is converted to an ISO 8601 string.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        UPDATE publication_ad
        SET deleted_datetime = ?
        WHERE id_publication_ad = ?
        """
        params = (now_iso, id_publication_ad)
        
        row_count = await self._execute_query(query, params)
        if row_count > 0:
            logger.info(f"Publication {id_publication_ad} marked as deleted.")
        else:
            logger.warning(f"Publication {id_publication_ad} not found for marking as deleted.")
        return row_count

    # --- LOOKUP/CONFIG FUNCTIONS ---
    async def get_all_categories(self):
        """
        Retrieves a list of all active categories from the `category` table.
        Returns a list of dictionaries, each representing a category.
        """
        results = await self._fetch_all("SELECT id_category, name FROM category ORDER BY name")
        logger.info(f"Fetched {len(results)} categories.")
        return results

    async def get_all_platforms(self):
        """
        Retrieves a list of all active platforms from the `platform` table.
        Returns a list of dictionaries, each representing a platform.
        """
        results = await self._fetch_all("SELECT id_platform, name FROM platform ORDER BY name")
        logger.info(f"Fetched {len(results)} platforms.")
        return results

    async def get_status_id_by_name(self, status_name: str):
        """
        Retrieves the `id_status_type` for a given status name.
        Returns the ID as an integer, or None if the status is not found.
        """
        status = await self._fetch_one("SELECT id_status_type FROM status_type WHERE name = ?", (status_name,))
        if status:
            logger.info(f"Status '{status_name}' ID is {status['id_status_type']}.")
        else:
            logger.warning(f"Status '{status_name}' not found.")
        return status['id_status_type'] if status else None

    async def get_platform_id_by_name(self, platform_name: str):
        """
        Retrieves the `id_platform` for a given platform name.
        Returns the ID as an integer, or None if the platform is not found.
        """
        platform = await self._fetch_one("SELECT id_platform FROM platform WHERE name = ?", (platform_name,))
        if platform:
            logger.info(f"Platform '{platform_name}' ID is {platform['id_platform']}.")
        else:
            logger.warning(f"Platform '{platform_name}' not found.")
        return platform['id_platform'] if platform else None

    async def get_category_id_by_name(self, category_name: str):
        """
        Retrieves the `id_category` for a given category name.
        Returns the ID as an integer, or None if the category is not found.
        """
        category = await self._fetch_one("SELECT id_category FROM category WHERE name = ?", (category_name,))
        if category:
            logger.info(f"Category '{category_name}' ID is {category['id_category']}.")
        else:
            logger.warning(f"Category '{category_name}' not found.")
        return category['id_category'] if category else None

    # --- STATISTICS FUNCTIONS ---
    async def get_advanced_stats(self, id_telegram_user: int):
        """
        Calculates and retrieves advanced statistics for a specific user,
        including total ads, sales, scheduled ads, total earnings, and future earning estimates.
        Date comparisons are done using ISO 8601 strings.
        """
        now = datetime.now()
        one_month_ago_iso = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        one_year_ago_iso = (now - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")

        query = """
        SELECT
            COUNT(DISTINCT a.id_ad) AS totale_annunci,
            
            SUM(CASE WHEN st.name = 'SOLD' THEN 1 ELSE 0 END) AS totale_vendite,
            
            SUM(CASE WHEN st.name IN ('SCHEDULED', 'READY') THEN 1 ELSE 0 END) AS totale_programmati,
            
            COALESCE(SUM(CASE WHEN st.name = 'SOLD' THEN pa.sold_price ELSE 0 END), 0) AS guadagno_totale,
            
            COALESCE(SUM(CASE WHEN st.name = 'SOLD' AND pa.sold_datetime >= ? THEN pa.sold_price ELSE 0 END), 0) AS guadagno_mese,
            
            COALESCE(SUM(CASE WHEN st.name = 'SOLD' AND pa.sold_datetime >= ? THEN pa.sold_price ELSE 0 END), 0) AS guadagno_anno,

            -- Estima guadagno futuro: Suggested price of ads not yet sold and not deleted
            COALESCE(SUM(CASE WHEN st.name != 'SOLD' AND pa.deleted_datetime IS NULL THEN a.suggested_price ELSE 0 END), 0) AS stima_guadagno_futuro
            
        FROM
            ad AS a
        LEFT JOIN
            publication_ad AS pa ON a.id_ad = pa.id_ad
        LEFT JOIN
            status_type AS st ON pa.id_status_type = st.id_status_type
        WHERE
            a.id_telegram_user = ?
        """
        result = await self._fetch_one(query, (one_month_ago_iso, one_year_ago_iso, id_telegram_user,))
        if result:
            logger.info(f"Fetched advanced statistics for user {id_telegram_user}.")
            return result
        else:
            logger.info(f"No advanced statistics found for user {id_telegram_user}.")
            return {
                "totale_annunci": 0, "totale_vendite": 0, "totale_programmati": 0,
                "guadagno_totale": 0, "guadagno_mese": 0, "guadagno_anno": 0,
                "stima_guadagno_futuro": 0
            }
            
    async def get_category_chart_data(self, id_telegram_user: int):
        """
        Retrieves data for a pie chart showing sales count per category for a user.
        Only considers ads marked as 'SOLD' and not deleted.
        """
        query = """
        SELECT c.name AS category, COUNT(DISTINCT a.id_ad) AS count
        FROM ad AS a
        LEFT JOIN category AS c ON a.id_category = c.id_category
        LEFT JOIN publication_ad AS pa ON a.id_ad = pa.id_ad
        LEFT JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        WHERE a.id_telegram_user = ? AND st.name = 'SOLD' AND pa.deleted_datetime IS NULL
        GROUP BY c.name
        ORDER BY count DESC
        """
        results = await self._fetch_all(query, (id_telegram_user,))
        logger.info(f"Fetched category chart data for user {id_telegram_user}.")
        return results

    # --- SUBSCRIPTION / CREDIT FUNCTIONS ---
    async def get_user_credits(self, id_telegram_user: int) -> int:
        """
        Retrieves the current credits balance for a user from their active subscription.
        An active subscription is identified by a `subscription_end_datetime` in the future.
        Returns the credit balance as an integer, or 0 if no active subscription or no credits.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        SELECT s.credits_balance
        FROM subscription AS s
        WHERE s.id_telegram_user = ? AND s.subscription_end_datetime > ?
        ORDER BY s.subscription_start_datetime DESC
        LIMIT 1
        """
        result = await self._fetch_one(query, (id_telegram_user, now_iso))
        credits = result['credits_balance'] if result else 0
        logger.info(f"User {id_telegram_user} has {credits} credits.")
        return credits

    async def deduct_credits(self, id_telegram_user: int, amount: int) -> bool:
        """
        Atomically deducts a specified amount of credits from the user's active subscription.
        Ensures that the user has sufficient credits and an active subscription before deduction.
        Returns True if successful, False if not enough credits or no active subscription.
        """
        conn = await self._get_connection()
        try:
            async with conn.cursor() as cursor:
                now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Get the active subscription ID
                sub_query = """
                SELECT id_subscription
                FROM subscription
                WHERE id_telegram_user = ? AND subscription_end_datetime > ?
                ORDER BY subscription_start_datetime DESC
                LIMIT 1
                """
                await cursor.execute(sub_query, (id_telegram_user, now_iso))
                subscription = await cursor.fetchone()

                if not subscription:
                    logger.warning(f"No active subscription found for user {id_telegram_user} to deduct credits.")
                    return False # No active subscription

                # Atomically update credits_balance
                update_query = """
                UPDATE subscription
                SET credits_balance = credits_balance - ?
                WHERE id_subscription = ? AND credits_balance >= ? AND subscription_end_datetime > ?
                """
                await cursor.execute(update_query, (amount, subscription['id_subscription'], amount, now_iso))
                await conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Deducted {amount} credits from subscription {subscription['id_subscription']} for user {id_telegram_user}.")
                    return True
                else:
                    logger.warning(f"Failed to deduct {amount} credits from subscription {subscription['id_subscription']} for user {id_telegram_user}. Insufficient credits or subscription expired.")
                    return False
        except Exception as e:
            logger.error(f"Error deducting credits for user {id_telegram_user}: {e}")
            raise # Re-raise the exception after logging

    # --- EXTRA FUNCTIONS SUGGERITE DA GEMINI ---
    # Ho aggiunto queste funzioni perché:
    # 1. Permettono di ottenere il nome di un lookup entity dato il suo ID, il che è utile per la visualizzazione.
    # 2. Forniscono un modo per gestire la chiusura della connessione nel ciclo di vita dell'applicazione.
    # 3. La classe DatabaseManager ora gestisce un'unica connessione per istanza, migliorando l'efficienza.
    # 4. Aggiunti metodi per ottenere l'ID della pubblicazione più recente per un annuncio specifico,
    #    utile per le operazioni che riguardano la pubblicazione corrente di un annuncio.
    # 5. Implementate funzioni per la gestione dei file multimediali, delle transazioni e delle sottoscrizioni,
    #    che erano assenti ma fondamentali per la piena operatività del sistema secondo il nuovo schema.

    async def get_status_name_by_id(self, id_status_type: int):
        """
        Retrieves the name of a status type given its ID.
        Returns the name as a string, or None if the ID is not found.
        """
        status = await self._fetch_one("SELECT name FROM status_type WHERE id_status_type = ?", (id_status_type,))
        return status['name'] if status else None

    async def get_platform_name_by_id(self, id_platform: int):
        """
        Retrieves the name of a platform given its ID.
        Returns the name as a string, or None if the ID is not found.
        """
        platform = await self._fetch_one("SELECT name FROM platform WHERE id_platform = ?", (id_platform,))
        return platform['name'] if platform else None
    
    async def get_category_name_by_id(self, id_category: int):
        """
        Retrieves the name of a category given its ID.
        Returns the name as a string, or None if the ID is not found.
        """
        category = await self._fetch_one("SELECT name FROM category WHERE id_category = ?", (id_category,))
        return category['name'] if category else None

    async def get_ad_publication_details(self, id_ad: int):
        """
        Retrieves all publication details for a given advertisement ID.
        An ad can have multiple publication entries, and this function returns all of them.
        """
        query = """
        SELECT
            pa.id_publication_ad, pa.scheduled_datetime, pa.publication_datetime,
            pa.sold_price, pa.sold_datetime, pa.deleted_datetime, pa.ad_url,
            st.name AS status_name,
            p.name AS platform_name
        FROM publication_ad AS pa
        JOIN status_type AS st ON pa.id_status_type = st.id_status_type
        JOIN platform AS p ON pa.id_platform = p.id_platform
        WHERE pa.id_ad = ?
        ORDER BY pa.scheduled_datetime DESC
        """
        return await self._fetch_all(query, (id_ad,))

    async def get_ad_by_publication_id(self, id_publication_ad: int):
        """
        Retrieves advertisement details given a publication ID.
        Includes basic details from the ad itself and some publication data.
        """
        query = """
        SELECT
            a.*,
            pa.id_platform, pa.id_status_type, pa.scheduled_datetime, pa.publication_datetime
        FROM ad AS a
        JOIN publication_ad AS pa ON a.id_ad = pa.id_ad
        WHERE pa.id_publication_ad = ?
        """
        return await self._fetch_one(query, (id_publication_ad,))

    async def get_latest_publication_id_for_ad(self, id_ad: int):
        """
        Retrieves the `id_publication_ad` for the most recent publication of a given advertisement.
        Returns the ID as an integer, or None if no publication is found.
        """
        query = """
        SELECT id_publication_ad
        FROM publication_ad
        WHERE id_ad = ?
        ORDER BY scheduled_datetime DESC, id_publication_ad DESC
        LIMIT 1
        """
        result = await self._fetch_one(query, (id_ad,))
        return result['id_publication_ad'] if result else None

    # --- NEWLY ADDED FUNCTIONS ---
    async def save_multimedia(self, telegram_file_id: str, id_ad: int, id_file_type: int, file_order: int = 0):
        """
        Saves details of a multimedia file associated with an advertisement.
        Returns the `id_multimedia_file` of the newly created entry.
        """
        query = """
        INSERT INTO multimedia_file (telegram_file_id, id_ad, id_file_type, file_order)
        VALUES (?, ?, ?, ?)
        """
        params = (telegram_file_id, id_ad, id_file_type, file_order)
        new_file_id = await self._execute_query(query, params)
        logger.info(f"Multimedia file {new_file_id} saved for ad {id_ad}.")
        return new_file_id

    async def log_transaction(self, id_payment_provider: int, payment_euro: float,
                              description: str = None, provider_transaction_id: str = None):
        """
        Logs a financial transaction in the `transaction_history` table.
        The `payment_datetime` is automatically set to the current time (ISO 8601).
        Returns the `id_transaction` of the newly created entry.
        """
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        INSERT INTO transaction_history (description, payment_euro, payment_datetime,
                                         provider_transaction_id, id_payment_provider)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (description, payment_euro, now_iso, provider_transaction_id, id_payment_provider)
        new_transaction_id = await self._execute_query(query, params)
        logger.info(f"Transaction {new_transaction_id} logged for {payment_euro} EUR.")
        return new_transaction_id

    async def add_subscription(self, id_telegram_user: int, id_account_type: int,
                               id_transaction: int = None, duration_days: int = 30):
        """
        Adds a new subscription for a user, fetching initial credits from the `account_type`.
        Calculates the `subscription_end_datetime` based on a given `duration_days`.
        Returns the `id_subscription` of the newly created entry.
        """
        account_type_details = await self._fetch_one(
            "SELECT monthly_credits FROM account_type WHERE id_account_type = ?",
            (id_account_type,)
        )
        if not account_type_details:
            logger.error(f"Account type {id_account_type} not found for new subscription for user {id_telegram_user}.")
            raise ValueError(f"Account type {id_account_type} not found.")

        initial_credits = account_type_details['monthly_credits']
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)

        start_date_iso = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_date_iso = end_date.strftime("%Y-%m-%d %H:%M:%S")

        query = """
        INSERT INTO subscription (subscription_start_datetime, subscription_end_datetime, credits_balance,
                                  id_telegram_user, id_account_type, id_transaction)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (start_date_iso, end_date_iso, initial_credits, id_telegram_user, id_account_type, id_transaction)
        new_subscription_id = await self._execute_query(query, params)
        logger.info(f"New subscription {new_subscription_id} added for user {id_telegram_user} with {initial_credits} credits, ending on {end_date_iso}.")
        return new_subscription_id
