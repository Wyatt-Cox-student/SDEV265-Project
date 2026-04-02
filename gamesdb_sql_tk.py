# gamesdb_sql_tk.py
# Tkinter app with SQLite cache for TheGamesDB searches and details.
# Python 3.10+, install requests: pip install requests
# Replace THEGAMESDB_API_KEY with your key.

import tkinter as tk
from tkinter import ttk, messagebox
import requests, threading, sqlite3, time, webbrowser, json

#GamesDB.net information stuff
THEGAMESDB_API_KEY = "7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830"
BASE = "https://api.thegamesdb.net"
DB_FILE = "gamesdb_cache.db"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# ----- Example static games list (NES/SNES/Genesis) -----
STATIC_GAMES = [
    ("Rayman", "SNES", 2017, "Adventure"),
    ("Shanghai II: Dragon's Eye", "SNES", 1992, "Puzzle"),
    ("San Goku Shi III", "SNES", 1993, "Strategy"),
    ("The Legend of Zelda: Mirror of Worlds", "NES", 2025, "Adventure"),
    ("Splatterworld", "NES", 1993, "Role-Playing"),
    ("Snow Bros.", "NES", 1990, "Platform"),
    ("Sonic 1 Remastered", "SEGA Genesis", 2007, "Platform"),
    ("Addams Family Values", "SEGA Genesis", 1994, "Role-Playing"),
    ("Aero the Acro-Bat", "SEGA Genesis", 1993, "Platform")
]


# ----- Database helpers -----
#creates or opens the SQLite DB and ensure tables exist.
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
# fetch cached game JSON and updated timestamp for a game id, or None if missing.
def db_get_game(game_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT data, updated_at FROM games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {"data": json.loads(row[0]), "updated_at": row[1]}
#store/replace a game's JSON and updated timestamp and replace its image rows.
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
#return a list of image URLs for a given game_id from the images table.
def db_get_images(game_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT url FROM images WHERE game_id = ?", (game_id,))
    rows = cur.fetchall()
    con.close()
    return [r[0] for r in rows]
#fetch cached search results JSON and updated timestamp for query q, or None if missing.
def db_get_search(q):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT results, updated_at FROM search_index WHERE q = ?", (q,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    return {"results": json.loads(row[0]), "updated_at": row[1]}
#store/replace search results JSON and updated timestamp for query q.
def db_save_search(q, results):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    now = int(time.time())
    cur.execute("INSERT OR REPLACE INTO search_index(q, results, updated_at) VALUES (?, ?, ?)",
                (q, json.dumps(results), now))
    con.commit()
    con.close()

# ----- TheGamesDB API calls -----
#perform an HTTP GET to TheGamesDB API endpoint with API key, 
#return parsed JSON (raises on HTTP error)
def call_tgdb(endpoint, params=None):
    headers = {"Accept": "application/json"}
    if params is None:
        params = {}
    params["apikey"] = THEGAMESDB_API_KEY
    resp = requests.get(f"{BASE}{endpoint}", params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()
# call the Games/ByGameName endpoint 
#and return a list of game dicts (handles dict or list shape).
def search_remote(q):
    data = call_tgdb("/Games/ByGameName", params={"name": q})
    games = data.get("data", {}).get("games") or []
    if isinstance(games, dict):
        games = [v for v in games.values()]
    return games
#call Games/ByGameId, extract the single game dict and 
#build a list of full image URLs 
#(returns (game, images_list) where images_list items are {"url": ...}).
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
#decorator that runs the wrapped function in a daemon Thread (fire-and-forget).
def threaded(func):
    def wrapper(*a, **kw):
        threading.Thread(target=lambda: func(*a, **kw), daemon=True).start()
    return wrapper

# ----- Tkinter GUI -----
#main Tkinter application window that initializes UI, DB and holds state and methods
class App(tk.Tk):
    #set window, init DB and create widgets.
    def __init__(self):
        super().__init__()
        self.title("GamesDB Search (NES / SNES / Genesis)")
        self.geometry("1200x800")
        init_db()
        self.create_widgets()
#build the search entry, buttons, status, results list, detail pane, and bind events.
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

        left = ttk.Frame(main, width=500)
        main.add(left, weight=1)
        ttk.Label(left, text="Results").pack(anchor="w")
        self.results_list = tk.Listbox(left)
        self.results_list.pack(fill="both", expand=True, pady=(4,0))
        self.results_list.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.Frame(main)
        main.add(right, weight=2)
        self.title_lbl = ttk.Label(right, text="", font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w", pady=(4,2))
        self.meta_lbl = ttk.Label(right, text="", foreground="gray")
        self.meta_lbl.pack(anchor="w", pady=(0,6))
        self.overview = tk.Text(right, wrap="word", height=18)
        self.overview.pack(fill="both", expand=True)
        self.overview.config(state="disabled")
        self.images_list = tk.Listbox(right, height=6)
        self.images_list.pack(fill="x", expand=True)
        self.images_list.bind("<Double-Button-1>", self.open_image)

        self.results = []
        self.populate_static_games()
 # ----- Populate static games -----
    #populate results with the bundled STATIC_GAMES 
    # and show a placeholder detail for the games.
    def populate_static_games(self):
        self.results_list.delete(0, 'end')
        self.results = [{"game_title": g[0], "platform": g[1]} for g in STATIC_GAMES]
        for g in STATIC_GAMES:
            self.results_list.insert('end', g[0])
        if self.results:
            self.overview.config(state="normal")
            self.overview.delete("1.0", "end")
            self.overview.insert("1.0", "Data goes here")
            self.overview.config(state="disabled")
 # ----- Search -----
 # (Clear search/filter not added yet)
#(search/filter by console, year, genre and other info not added yet)
    @threaded
        #perform a search: 
    #use cache if fresh, otherwise call search_remote and save to DB, then populate results.
    def search(self):
        q = self.qvar.get().strip()
        if not q:
            return
        self.set_status("Searching...")
        self.results_list.delete(0, 'end')
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
#update the results Listbox and status text from a results list.
    def populate_results(self, results, from_cache=False):
        self.results = results
        self.results_list.delete(0, 'end')
        for g in results:
            title = g.get("game_title") or g.get("title") or "Untitled"
            platform = g.get("platform") or g.get("platforms") or ""
            display = f"{title} ({platform})" if platform else title
            self.results_list.insert('end', display)
        self.set_status(f"{len(results)} result(s) {'(cache)' if from_cache else ''}")
# update the status label.
    def set_status(self, text):
        self.status.config(text=text)
# if something goes wrong show an error dialog and set status to "Error".
    def error(self, exc):
        self.after(0, lambda: messagebox.showerror("Error", str(exc)))
        self.set_status("Error")
# handle selecting a result: (in progress)
#if static (no id) show placeholder;
#else use cached game if fresh or start fetch_and_show thread.
    def on_select(self, evt):
        sel = self.results_list.curselection()
        if not sel:
            return
        idx = sel[0]
        g = self.results[idx]
        game_id = g.get("id") or g.get("game_id") or g.get("gameId")

        if not game_id:
            self.overview.config(state="normal")
            self.overview.delete("1.0", "end")
            self.overview.insert("1.0", "Data goes here")
            self.overview.config(state="disabled")
            self.images_list.delete(0, 'end')
            return

        cached = db_get_game(game_id)
        now = int(time.time())
        if cached and (now - cached["updated_at"] < CACHE_TTL_SECONDS):
            game_data = cached["data"]
            images = db_get_images(game_id)
            self.show_detail(game_data, images)
            threading.Thread(target=self.refresh_game_if_needed, args=(game_id,), daemon=True).start()
        else:
            self.set_status("Loading details...")
            threading.Thread(target=self.fetch_and_show, args=(game_id,), daemon=True).start()
#fetch game and images remotely, save to DB, then show detail on main thread.
    def fetch_and_show(self, game_id):
        try:
            game, images = get_game_remote(game_id)
            db_save_game(game_id, game, images)
            images_urls = [im.get("url") for im in images if im.get("url")]
            self.after(0, lambda: self.show_detail(game, images_urls))
        except Exception as e:
            self.error(e)
#background refresh of a game's remote data and save to DB (errors ignored).
    def refresh_game_if_needed(self, game_id):
        try:
            game, images = get_game_remote(game_id)
            db_save_game(game_id, game, images)
        except Exception:
            pass
#populate title, meta, overview text and images list with provided game dict and image URLs.
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
#open the selected image URL in the default web browser.
    def open_image(self, evt):
        sel = self.images_list.curselection()
        if not sel:
            return
        url = self.images_list.get(sel[0])
        if url and url != "(no-url)":
            webbrowser.open(url)

if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()