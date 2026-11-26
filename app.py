import sqlite3
from flask import Flask, jsonify, request
app = Flask(__name__)
DB = "seats.db"
def db():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
def setup():
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS seats (seat_no INTEGER PRIMARY KEY, booked_by TEXT)")
    for n in range(1, 11):
        conn.execute("INSERT OR IGNORE INTO seats (seat_no) VALUES (?)", (n,))
    conn.commit()
    conn.close()
@app.route("/seats")
def list_seats():
    conn = db()
    rows = conn.execute("SELECT seat_no, booked_by FROM seats ORDER BY seat_no").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
@app.route("/book", methods=["POST"])
def book():
    data = request.get_json(silent=True) or {}
    seat_no = data.get("seat_no")
    name = data.get("name")
    if not isinstance(seat_no, int) or not name:
        return jsonify(error="seat_no (number) and name are required"), 400
    conn = db()
    cur = conn.execute(
        "UPDATE seats SET booked_by = ? WHERE seat_no = ? AND booked_by IS NULL",
        (name, seat_no),
    )
    conn.commit()
    booked = cur.rowcount == 1
    conn.close()
    if booked:
        return jsonify(message="Seat booked", seat_no=seat_no), 201
    return jsonify(error="Seat not available or does not exist"), 409
setup()
if __name__ == "__main__":
    app.run(debug=True)