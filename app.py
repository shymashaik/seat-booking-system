import json
import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)
DB = "seats.db"
TOTAL_SEATS = 10

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Seat Booking</title>
<style>
body{font-family:Arial;max-width:600px;margin:20px auto;padding:0 10px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}
button{padding:14px;border:0;border-radius:6px;background:#2e7d32;color:#fff;font-size:16px}
button.taken{background:#999}
</style></head><body>
<h2>Seat Booking</h2>
<input id="name" placeholder="Your name"><p id="msg"></p>
<div class="grid" id="grid"></div>
<script>
function uid(){return Date.now().toString(36)+Math.random().toString(36).slice(2)}
function msg(t){document.getElementById('msg').textContent=t}
async function load(){
  const r=await fetch('/seats');const seats=await r.json();
  const g=document.getElementById('grid');g.innerHTML='';
  seats.forEach(function(s){
    const b=document.createElement('button');
    b.textContent=s.seat_no+(s.booked_by?' ('+s.booked_by+')':'');
    if(s.booked_by){b.className='taken';b.disabled=true}
    else{b.onclick=function(){book(s.seat_no)}}
    g.appendChild(b);
  });
}
async function book(n){
  const name=document.getElementById('name').value.trim();
  if(!name){msg('Enter your name first');return}
  const r=await fetch('/book',{method:'POST',
    headers:{'Content-Type':'application/json','Idempotency-Key':uid()},
    body:JSON.stringify({seat_no:n,name:name})});
  const d=await r.json();
  msg(d.message||d.error);
  load();
}
load();
</script></body></html>"""

def db():
    conn = sqlite3.connect(DB, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn

def setup():
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS seats (seat_no INTEGER PRIMARY KEY, booked_by TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, status INTEGER, body TEXT)")
    for n in range(1, TOTAL_SEATS + 1):
        conn.execute("INSERT OR IGNORE INTO seats (seat_no) VALUES (?)", (n,))
    conn.close()

@app.route("/")
def home():
    return PAGE

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
    request_id = request.headers.get("Idempotency-Key") or data.get("request_id")
    if not isinstance(seat_no, int) or isinstance(seat_no, bool) or not name or not request_id:
        return jsonify(error="seat_no (number), name and a request id are required"), 400
    conn = db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute("SELECT status, body FROM requests WHERE request_id = ?", (request_id,)).fetchone()
        if old:
            conn.execute("COMMIT")
            return app.response_class(old["body"], status=old["status"], mimetype="application/json")
        cur = conn.execute(
            "UPDATE seats SET booked_by = ? WHERE seat_no = ? AND booked_by IS NULL",
            (name, seat_no),
        )
        if cur.rowcount == 1:
            status, body = 201, {"message": "Seat booked", "seat_no": seat_no}
        else:
            status, body = 409, {"error": "Seat not available or does not exist"}
        text = json.dumps(body)
        conn.execute("INSERT INTO requests (request_id, status, body) VALUES (?, ?, ?)", (request_id, status, text))
        conn.execute("COMMIT")
        return app.response_class(text, status=status, mimetype="application/json")
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return jsonify(error="Server busy, please retry"), 503
    finally:
        conn.close()

setup()

if __name__ == "__main__":
    app.run(debug=True)