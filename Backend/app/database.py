
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    options = {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10"))}
    if os.getenv("DB_SSLMODE"):
        options["sslmode"] = os.environ["DB_SSLMODE"]
    if os.getenv("DB_SSLROOTCERT"):
        options["sslrootcert"] = os.environ["DB_SSLROOTCERT"]
    if os.getenv("DATABASE_URL"):
        return psycopg.connect(os.environ["DATABASE_URL"], **options)
    connection = psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        **options,
    )
    return connection
