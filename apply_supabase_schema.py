import psycopg2
from pathlib import Path

CONN_INFO = {
    'host': 'db.bqddltikebycgcmesnxf.supabase.co',
    'port': 5432,
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'ahmed1A@',
    'sslmode': 'require',
}

def main():
    sql_path = Path('supabase_schema_setup.sql')
    if not sql_path.exists():
        raise FileNotFoundError(f"Schema file not found: {sql_path}")

    sql_text = sql_path.read_text(encoding='utf-8')
    if not sql_text.strip():
        raise ValueError('Schema file is empty.')

    print('Connecting to Supabase Postgres...')
    conn = psycopg2.connect(**CONN_INFO)
    conn.autocommit = True

    with conn:
        with conn.cursor() as cur:
            print('Executing schema script (this may take a moment)...')
            cur.execute(sql_text)
            print('Schema script executed successfully.')

    conn.close()
    print('Connection closed.')

if __name__ == '__main__':
    main()
