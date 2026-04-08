# gamesdb_sql_tk.py
# Tkinter app with SQLite cache for TheGamesDB searches and details.
# Python 3.10+, install requests: pip install requests
# Replace THEGAMESDB_API_KEY with your key.

import tkinter as tk
from tkinter import ttk, messagebox
import requests, threading, sqlite3, time, webbrowser, json

# --- Config ---
THEGAMESDB_API_KEY = "7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830"
BASE = "https://api.thegamesdb.net"
DB_FILE = "gamesdb_cache.db"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ----- Example static games list (NES/SNES/Genesis) -----
STATIC_GAMES = [
    (47693, "Rayman", "SNES", 2017, "Adventure", "1", "Classic platformer.", []),
    (5835, "Shanghai II: Dragon's Eye", "SNES", 1992, "Puzzle", "1", "Tile-matching puzzle.", []),
    (53023, "San Goku Shi III", "SNES", 1993, "Strategy", "1-2", "Strategy game.", []),
    (134985, "The Legend of Zelda: Mirror of Worlds", "NES", 2025, "Adventure", "1", "Zelda-like adventure.", []),
    (134260, "Splatterworld", "NES", 1993, "Role-Playing", "1", "RPG.", []),
    (109954, "Snow Bros.", "NES", 1990, "Platform", "1-2", "Arcade platformer.", []),
    (124463, "Sonic 1 Remastered", "SEGA Genesis", 2007, "Platform", "1", "Remaster of Sonic 1.", []),
    (9414, "Addams Family Values", "SEGA Genesis", 1994, "Role-Playing", "1-4", "RPG in Addams Family world.", []),
    (4237, "Aero the Acro-Bat", "SEGA Genesis", 1993, "Platform", "1", "Platform action game.", [])
]

# --- Database helpers ---
def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS search_index (
        q TEXT PRIMARY KEY,
        results TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS images (
        game_id INTEGER,
        url TEXT,
        PRIMARY KEY(game_id, url)
    )""")
    con.commit()
    con.close()

def db_get_game(game_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT data, updated_at FROM games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    con.close()
    return None if not row else {"data": json.loads(row[0]), "updated_at": row[1]}

def db_save_game(game_id, game_data, images):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    now = int(time.time())
    cur.execute("INSERT OR REPLACE INTO games(id, data, updated_at) VALUES (?, ?, ?)",
                (game_id, json.dumps(game_data), now))
    cur.execute("DELETE FROM images WHERE game_id = ?", (game_id,))
    for im in images:
        url = im.get("url")
        if url:
            cur.execute("INSERT OR IGNORE INTO images(game_id, url) VALUES (?, ?)", (game_id, url))
    con.commit()
    con.close()

def db_get_images(game_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT url FROM images WHERE game_id = ?", (game_id,))
    rows = cur.fetchall()
    con.close()
    return [r[0] for r in rows]

def db_get_search(q):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT results, updated_at FROM search_index WHERE q = ?", (q,))
    row = cur.fetchone()
    con.close()
    return None if not row else {"results": json.loads(row[0]), "updated_at": row[1]}

def db_save_search(q, results):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    now = int(time.time())
    cur.execute("INSERT OR REPLACE INTO search_index(q, results, updated_at) VALUES (?, ?, ?)",
                (q, json.dumps(results), now))
    con.commit()
    con.close()

# ----- TheGamesDB API calls -----
def call_tgdb(endpoint, params=None):
    headers = {"Accept": "application/json"}
    if params is None:
        params = {}
    params["apikey"] = THEGAMESDB_API_KEY
    resp = requests.get(f"{BASE}{endpoint}", params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()

def search_remote(q):
    data = call_tgdb("/Games/ByGameName", params={"name": q})
    games = data.get("data", {}).get("games") or []
    if isinstance(games, dict):
        games = [v for v in games.values()]
    return games

def get_game_remote(game_id):
    data = call_tgdb("/Games/ByGameId", params={"id": game_id})
    games = data.get("data", {}).get("games", {}) or {}
    game = games.get(str(game_id)) or {}
    images = []
    if "images" in game:
        box = game["images"].get("boxart")
        if isinstance(box, dict):
            images = [box]
        elif isinstance(box, list):
            images = box
    base = data.get("data", {}).get("base_url", {}) or {}
    images_full = []
    for img in images:
        url = img.get("filename") or img.get("thumb") or img.get("url")
        if url and base:
            if "thumb" in base and isinstance(base["thumb"], str):
                url = base["thumb"].rstrip("/") + "/" + url.lstrip("/")
            elif "original" in base and isinstance(base["original"], str):
                url = base["original"].rstrip("/") + "/" + url.lstrip("/")
        images_full.append({"url": url})
    return game, images_full

# ----- Worker wrappers -----
def threaded(func):
    def wrapper(*a, **kw):
        threading.Thread(target=lambda: func(*a, **kw), daemon=True).start()
    return wrapper

# ----- Tkinter GUI -----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Classic Game Database")
        self.geometry("1200x800")
        init_db()
        self.create_widgets()

    def create_widgets(self):
        # TOP BAR
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Search:").pack(side="left")

        self.qvar = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.qvar, width=40)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: self.search())
        entry.bind("<Escape>", lambda e: self.clear_search())

        ttk.Button(top, text="Search", command=self.search).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_search).pack(side="left", padx=6)

        self.status = ttk.Label(top, text="", foreground="gray")
        self.status.pack(side="left", padx=10)

        # MAIN SPLIT
        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # LEFT LIST
        left = ttk.Frame(main, width=400)
        main.add(left, weight=1)

        ttk.Label(left, text="Games").pack(anchor="w")

        self.results_list = tk.Listbox(left)
        self.results_list.pack(fill="both", expand=True)
        self.results_list.bind("<<ListboxSelect>>", self.on_select)

        # RIGHT PANEL
        right = ttk.Frame(main)
        main.add(right, weight=2)

        self.title_lbl = ttk.Label(right, font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w", pady=(4,2))

        self.meta_lbl = ttk.Label(right, foreground="gray")
        self.meta_lbl.pack(anchor="w", pady=(0,6))

        self.back_btn = ttk.Button(right, text="Back", command=self.reset_detail)
        self.back_btn.pack(anchor="w")
        self.back_btn.pack_forget()

        # TABLE FRAME
        self.detail_frame = tk.Frame(right, bg="white", padx=10, pady=10, relief="groove", borderwidth=2)
        self.detail_frame.pack(fill="both", expand=True)

        self.results = []
        self.populate_static_games()

    # ----- Populate static games -----
    def populate_static_games(self):
        self.results = []
        self.results_list.delete(0, "end")
        for g in STATIC_GAMES:
            gid, name, platform, year, genre, players, overview, images = g
            item = {
                "id": gid,
                "game_title": name,
                "platform": platform,
                "release_date": year,
                "genre": genre,
                "players": players,
                "overview": overview,
                "images": images
            }
            self.results.append(item)
            self.results_list.insert("end", name)  # <-- only name
    # update the status label.
    def set_status(self, text):
        self.status.config(text=text)
# if something goes wrong show an error dialog and set status to "Error".
    def error(self, exc):
        self.after(0, lambda: messagebox.showerror("Error", str(exc)))
        self.set_status("Error")
    # Clear search
    def clear_search(self):
        self.qvar.set("")
        self.populate_static_games()
        self.status.config(text="")

    # Reset detail panel
    def reset_detail(self):
        self.back_btn.pack_forget()
        self.title_lbl.config(text="")
        self.meta_lbl.config(text="")
        for child in self.detail_frame.winfo_children():
            child.destroy()

    # ----- Search -----
    @threaded
    def search(self):
        q = self.qvar.get().strip().lower()
        if not q:
            self.populate_static_games()
            return

        filtered = []
        for g in STATIC_GAMES:
            gid, name, platform, year, genre, players, overview, images = g
            if q in name.lower():
                filtered.append({
                    "id": gid,
                    "game_title": name,
                    "platform": platform,
                    "release_date": year,
                    "genre": genre,
                    "players": players,
                    "overview": overview,
                    "images": images
                })

        self.results = filtered
        self.results_list.delete(0, "end")
        for g in filtered:
            self.results_list.insert("end", g['game_title'])  # <-- only name
        self.status.config(text=f"{len(filtered)} result(s)")

    # Result selection
    def on_select(self, evt):
        sel = self.results_list.curselection()
        if not sel:
            return
        g = self.results[sel[0]]
        self.back_btn.pack(anchor="w", pady=(0,4))
        self.show_table(g)

    def show_table(self, d):
        for child in self.detail_frame.winfo_children():
            child.destroy()

        self.title_lbl.config(text=d["game_title"])

        meta = []
        if d.get("platform"): meta.append(d["platform"])
        if d.get("release_date"): meta.append(str(d["release_date"]))
        if d.get("players"): meta.append(f"Players: {d['players']}")
        self.meta_lbl.config(text=" • ".join(meta))

        fields = [
            ("Game ID ", d.get("id")),
            ("Name", d.get("game_title")),
            ("Platform", d.get("platform")),
            ("Release Date", d.get("release_date")),
            ("Genre", d.get("genre")),
            ("Players", d.get("players")),
            ("Description", d.get("overview")),
            ("Images", ", ".join(d.get("images") or []) or "link.jpg")
    ]

        self.detail_frame.columnconfigure(0, minsize=250)
        self.detail_frame.columnconfigure(1, weight=1)

        for r, (label, value) in enumerate(fields):
            tk.Label(self.detail_frame, text=label, anchor="w", bg="white").grid(row=r, column=0, sticky="nw", padx=6, pady=6)
            tk.Label(self.detail_frame, text=str(value), anchor="w", wraplength=600, bg="white").grid(row=r, column=1, sticky="nw", padx=6, pady=6)
    
    def open_image(self, evt):
        sel = self.images_list.curselection()
        if not sel:
            return
        url = self.images_list.get(sel[0])
        if url and url != "(no-url)":
            webbrowser.open(url)
# --- Run app ---
if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()