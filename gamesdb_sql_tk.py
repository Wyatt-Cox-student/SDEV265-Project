# gamesdb_sql_tk.py
# Tkinter app with SQLite cache for TheGamesDB searches and details.
# Python 3.10+, install requests: pip install requests
# Replace THEGAMESDB_API_KEY with your key.

import tkinter as tk
from tkinter import ttk, messagebox
import requests, threading, sqlite3, time, webbrowser, os, datetime, json

THEGAMESDB_API_KEY = "7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830"  # replace
BASE = "https://api.thegamesdb.net"
DB_FILE = "gamesdb_cache.db"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ----- Database helpers -----
def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        data TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS search_index (
        q TEXT PRIMARY KEY,
        results TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS images (
        game_id INTEGER,
        url TEXT,
        PRIMARY KEY(game_id, url)
    )
    """)
    con.commit()
    con.close()

def db_get_game(game_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT data, updated_at FROM games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    data = json.loads(row[0])
    updated_at = row[1]
    return {"data": data, "updated_at": updated_at}

def db_save_game(game_id, game_data, images):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    now = int(time.time())
    cur.execute("INSERT OR REPLACE INTO games(id, data, updated_at) VALUES (?, ?, ?)",
                (game_id, json.dumps(game_data), now))
    cur.execute("DELETE FROM images WHERE game_id = ?", (game_id,))
    for im in images:
        url = im.get("url") or im.get("filename") or im.get("thumb") or im.get("url")
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
    if not row:
        return None
    return {"results": json.loads(row[0]), "updated_at": row[1]}

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
        imgs = game["images"]
        box = imgs.get("boxart")
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

# ----- Worker wrappers (threaded) -----
def threaded(func):
    def wrapper(*a, **kw):
        threading.Thread(target=lambda: func(*a, **kw), daemon=True).start()
    return wrapper

# ----- Tkinter GUI -----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GamesDB Search (NES / SNES / Genesis)")
        self.geometry("900x650")
        init_db()
        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Search:").pack(side="left")
        self.qvar = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.qvar, width=50)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: self.search())
        ttk.Button(top, text="Search", command=self.search).pack(side="left")
        self.status = ttk.Label(top, text="", foreground="gray")
        self.status.pack(side="left", padx=10)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0,8))

        left = ttk.Frame(main, width=320)
        main.add(left, weight=1)
        ttk.Label(left, text="Results").pack(anchor="w")
        self.results_list = tk.Listbox(left)
        self.results_list.pack(fill="both", expand=True, pady=(4,0))
        self.results_list.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(main)
        main.add(right, weight=3)
        self.title_lbl = ttk.Label(right, text="", font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w", pady=(4,2))
        self.meta_lbl = ttk.Label(right, text="", foreground="gray")
        self.meta_lbl.pack(anchor="w", pady=(0,6))
        self.overview = tk.Text(right, wrap="word", height=18)
        self.overview.pack(fill="both", expand=True)
        self.overview.config(state="disabled")
        imgs_frame = ttk.Frame(right)
        imgs_frame.pack(fill="x", pady=(6,0))
        ttk.Label(imgs_frame, text="Images (double-click to open):").pack(anchor="w")
        self.images_list = tk.Listbox(imgs_frame, height=6)
        self.images_list.pack(fill="x", expand=True)
        self.images_list.bind("<Double-Button-1>", self.open_image)

        # store current search results
        self.results = []

    @threaded
    def search(self):
        q = self.qvar.get().strip()
        if not q:
            return
        self.set_status("Searching...")
        self.results_list.delete(0, 'end')
        # check cache
        cached = db_get_search(q)
        now = int(time.time())
        use_cache = False
        if cached and (now - cached["updated_at"] < CACHE_TTL_SECONDS):
            results = cached["results"]
            use_cache = True
        else:
            try:
                results = search_remote(q)
                db_save_search(q, results)
            except Exception as e:
                if cached:
                    results = cached["results"]
                else:
                    self.error(e)
                    return
        self.after(0, lambda: self.populate_results(results, from_cache=use_cache))

    def populate_results(self, results, from_cache=False):
        self.results = results
        self.results_list.delete(0, 'end')
        for g in results:
            title = g.get("game_title") or g.get("title") or "Untitled"
            platform = g.get("platform") or g.get("platforms") or ""
            display = f"{title} ({platform})" if platform else title
            self.results_list.insert('end', display)
        self.set_status(f"{len(results)} result(s) {'(cache)' if from_cache else ''}")

    def set_status(self, text):
        self.status.config(text=text)

    def error(self, exc):
        self.after(0, lambda: messagebox.showerror("Error", str(exc)))
        self.set_status("Error")

    def on_select(self, evt):
        sel = self.results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        g = self.results[idx]
        game_id = g.get("id") or g.get("game_id") or g.get("gameId")
        if not game_id:
            messagebox.showinfo("Info", "Selected item has no ID.")
            return
        # try DB first
        cached = db_get_game(game_id)
        now = int(time.time())
        if cached and (now - cached["updated_at"] < CACHE_TTL_SECONDS):
            # use cached
            game_data = cached["data"]
            images = db_get_images(game_id)
            self.show_detail(game_data, images)
            # also refresh in background asynchronously but do not block UI
            threading.Thread(target=self.refresh_game_if_needed, args=(game_id,), daemon=True).start()
        else:
            # fetch remote and cache
            self.set_status("Loading details...")
            threading.Thread(target=self.fetch_and_show, args=(game_id,), daemon=True).start()

    def fetch_and_show(self, game_id):
        try:
            game, images = get_game_remote(game_id)
            db_save_game(game_id, game, images)
            images_urls = [im.get("url") for im in images if im.get("url")]
            self.after(0, lambda: self.show_detail(game, images_urls))
        except Exception as e:
            self.error(e)

    def refresh_game_if_needed(self, game_id):
        # fetch fresh in background and update DB if changed
        try:
            game, images = get_game_remote(game_id)
            db_save_game(game_id, game, images)
        except Exception:
            pass  # silent background refresh

    def show_detail(self, game, images):
        title = game.get("game_title") or game.get("title") or "Untitled"
        platform = game.get("platform") or game.get("platforms") or ""
        release = game.get("release_date") or game.get("released") or ""
        players = game.get("players") or ""
        self.title_lbl.config(text=title)
        meta = []
        if platform: meta.append(f"Platform: {platform}")
        if release: meta.append(f"Release: {release}")
        if players: meta.append(f"Players: {players}")
        self.meta_lbl.config(text=" • ".join(meta))
        overview = game.get("overview") or game.get("description") or ""
        self.overview.config(state="normal")
        self.overview.delete("1.0", "end")
        self.overview.insert("1.0", overview)
        self.overview.config(state="disabled")
        self.images_list.delete(0, 'end')
        for url in (images or []):
            self.images_list.insert('end', url or "(no-url)")
        self.set_status("Ready")

    def open_image(self, evt):
        sel = self.images_list.curselection()
        if not sel:
            return
        url = self.images_list.get(sel[0])
        if url and url != "(no-url)":
            webbrowser.open(url)

if __name__ == "__main__":
    # ensure DB file in same dir as script
    init_db()
    app = App()
    app.mainloop()
