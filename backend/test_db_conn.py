import psycopg2

def test_conn(url):
    print(f"Testing {url}...")
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("SUCCESS")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

if __name__ == "__main__":
    urls = [
        "postgresql://postgres:password@127.0.0.1:5432/adcom_standalone",
        "postgresql://postgres:postgres@127.0.0.1:5432/adcom_standalone",
        "postgresql://postgres:password@localhost:5432/adcom_standalone",
        "postgresql://postgres:postgres@localhost:5432/adcom_standalone",
    ]
    for url in urls:
        if test_conn(url):
            print(f"Working URL: {url}")
            break
