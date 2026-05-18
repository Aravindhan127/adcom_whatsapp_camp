import sqlite3

def check_users():
    conn = sqlite3.connect('adcom.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, email, role FROM agents")
        users = cursor.fetchall()
        print("Users in Database:")
        for user in users:
            print(f"ID: {user[0]} | Username: {user[1]} | Email: {user[2]} | Role: {user[3]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_users()
