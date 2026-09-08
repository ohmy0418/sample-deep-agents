"""
목적: PostgresStore(store 테이블)의 데이터를 dict 형태로 조회한다.

psql로 조회하면 결과가 단순 텍스트로 찍히지만, psycopg로 조회하면
value(jsonb) 컬럼이 실제 Python dict로 파싱되어 넘어온다.

python3 query_store.py                    # 전체 조회
python3 query_store.py --prefix skills-test   # 특정 namespace만 조회
다른 코드에서 함수로 불러쓰기


from query_store import fetch_store_rows

rows = fetch_store_rows(prefix="skills-test")
rows[0]["value"]["content"]   # SKILL.md 내용 바로 접근 가능
"""

import argparse
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def get_conn_string() -> str:
    return (
        f"host={os.environ['PG_HOST']} "
        f"port={os.environ['PG_PORT']} "
        f"dbname={os.environ['PG_DB']} "
        f"user={os.environ['PG_USER']} "
        f"password={os.environ['PG_PASSWORD']}"
    )


def fetch_store_rows(prefix: str | None = None) -> list[dict]:
    """store 테이블의 행을 dict 리스트로 반환한다.

    Args:
        prefix: 지정하면 해당 namespace(prefix)만 필터링한다.

    Returns:
        각 행이 {"prefix": str, "key": str, "value": dict, ...} 형태인 리스트.
        value는 jsonb 컬럼이 psycopg에 의해 자동으로 dict로 변환된 것이다.
    """
    query = "SELECT prefix, key, value, created_at, updated_at FROM store"
    params: tuple = ()
    if prefix is not None:
        query += " WHERE prefix = %s"
        params = (prefix,)

    with psycopg.connect(get_conn_string(), row_factory=dict_row) as conn:
        with conn.execute(query, params) as cur:
            return cur.fetchall()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="store 테이블을 dict로 조회한다.")
    parser.add_argument("--prefix", default=None, help="조회할 namespace(prefix). 미지정시 전체 조회.")
    args = parser.parse_args()

    rows = fetch_store_rows(prefix=args.prefix)
    print(f"총 {len(rows)}건 조회됨\n")
    for row in rows:
        print(f"type(row) = {type(row)}")
        print(f"type(row['value']) = {type(row['value'])}")
        print(row)
        print("---")
