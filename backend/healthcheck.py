import asyncio
import os

from llm_provider import verify_gemini_api_key, verify_groq_api_key
from neo4j_connection import get_neo4j_driver_with_fallback


def _postgres_probe() -> tuple[bool, str]:
    """Config-only Postgres probe: reports bridge-derived host/db, never connects."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    user = os.getenv("POSTGRES_USER", "").strip()
    password = os.getenv("POSTGRES_PASSWORD", "").strip()
    database = os.getenv("POSTGRES_DATABASE", "").strip()
    if database_url and not (user and password and database):
        try:
            from urllib.parse import urlparse

            parsed = urlparse(database_url)
            host = parsed.hostname or "unknown"
            db = (parsed.path or "").lstrip("/") or "unknown"
            return True, f"bridged from DATABASE_URL host={host} db={db} (POSTGRES_* unset, bridge fills at boot)"
        except ValueError as exc:
            return False, f"DATABASE_URL unparseable: {exc}"
    if user and password and database:
        host = os.getenv("POSTGRES_HOST", "localhost").strip() or "localhost"
        ssl_mode = os.getenv("POSTGRES_SSL_MODE", "require").strip() or "require"
        return True, f"host={host} db={database} sslmode={ssl_mode}"
    return False, "Postgres not configured (POSTGRES_USER/PASSWORD/DATABASE or DATABASE_URL)"


async def main() -> None:
    print("=== Provider checks ===")

    groq_ok, groq_message = await verify_groq_api_key()
    print(f"Groq: {'OK' if groq_ok else 'FAIL'} - {groq_message}")

    gemini_ok, gemini_message = await verify_gemini_api_key()
    print(f"Gemini: {'OK' if gemini_ok else 'FAIL'} - {gemini_message}")

    print("\n=== Neo4j check (cloud -> local fallback) ===")
    try:
        driver, target = get_neo4j_driver_with_fallback()
        try:
            print(f"Neo4j target selected: {target.name} ({target.uri})")

            # Connectivity probe without forcing database, to isolate auth/network issues.
            records, _, _ = driver.execute_query("RETURN 1 AS ok")
            value = records[0]["ok"] if records else None
            print(f"Neo4j connectivity: OK - probe={value}")

            # Database probe with configured name, to validate database setup.
            try:
                db_records, _, _ = driver.execute_query(
                    "RETURN 1 AS ok",
                    database_=target.database,
                )
                db_value = db_records[0]["ok"] if db_records else None
                print(f"Neo4j database '{target.database}': OK - probe={db_value}")
            except Exception as db_exc:
                print(f"Neo4j database '{target.database}': FAIL - {db_exc}")
        finally:
            driver.close()
    except Exception as exc:
        print(f"Neo4j: FAIL - {exc}")

    print("\n=== Postgres check (config-only, no connection) ===")
    pg_ok, pg_message = _postgres_probe()
    print(f"Postgres: {'OK' if pg_ok else 'SKIP'} - {pg_message}")


if __name__ == "__main__":
    asyncio.run(main())