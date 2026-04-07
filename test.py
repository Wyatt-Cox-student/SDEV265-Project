import tkinter as tk
from tkinter import ttk, messagebox
import requests, threading, sqlite3, time, webbrowser, json

THEGAMESDB_API_KEY = "7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830"
BASE = "https://api.thegamesdb.net"
DB_FILE = "gamesdb_cache.db"
CACHE_TTL_SECONDS = 7 * 24 * 3600

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

def threaded(func):
    def wrapper(*a, **kw):
        threading.Thread(target=lambda: func(*a, **kw), daemon=True).start()
    return wrapper

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Classic Game Database")
        self.geometry("1200x800")
        init_db()
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('White.TFrame', background='white')
        style.configure('White.TLabel', background='white')
        self.create_widgets()

    def create_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Search:").pack(side="left")
        self.qvar = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.qvar, width=50)
        entry.pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: self.search())
        entry.bind("<Escape>", lambda e: self.clear_search())
        ttk.Button(top, text="Search", command=lambda: self.search()).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_search).pack(side="left", padx=(6,0))
        self.status = ttk.Label(top, text="", foreground="gray")
        self.status.pack(side="left", padx=10)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0,8))

        left = ttk.Frame(main, width=400)
        main.add(left, weight=1)
        ttk.Label(left, text="Games in Database").pack(anchor="w")
        self.results_list = tk.Listbox(left, bg='white', fg='black', activestyle='dotbox', highlightthickness=1)
        self.results_list.pack(fill="both", expand=True, pady=(4,0))
        self.results_list.bind("<<ListboxSelect>>", self.on_select)
        self.results_list.bind("<Double-Button-1>", lambda e: self.on_select(e))
        self.results_list.bind("<ButtonRelease-1>", lambda e: self.on_select(e))

        right = ttk.Frame(main)
        main.add(right, weight=2)
        self.title_lbl = ttk.Label(right, text="", font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w", pady=(4,2))
        self.meta_lbl = ttk.Label(right, text="", foreground="gray")
        self.meta_lbl.pack(anchor="w", pady=(0,6))

        self.back_btn = ttk.Button(right, text="Back", command=self.reset_detail)
        self.back_btn.pack(anchor="w", pady=(0,4))
        self.back_btn.pack_forget()

        self.detail_frame = ttk.Frame(right, padding=10, relief="groove", style='White.TFrame')
        self.detail_frame.pack(fill="both", expand=True)

        self.images_list = tk.Listbox(right, height=6, bg='white', fg='black', activestyle='dotbox', highlightthickness=1)
        self.images_list.pack(fill="x", expand=True, pady=(6,0))
        self.images_list.bind("<Double-Button-1>", self.open_image)

        self.results = []
        self.populate_static_games()

    def populate_static_games(self):
        self.results_list.delete(0, 'end')
        self.results = []
        for s in STATIC_GAMES:
            gid, name, platform, year, genre, players, overview, images = s
            item = {
                "static": True,
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
            self.results_list.insert('end', f"{name} — {gid}")

    def clear_search(self):
        self.qvar.set("")
        self.results_list.delete(0, 'end')
        self.populate_static_games()

    def reset_detail(self):
        self.back_btn.pack_forget()
        self.title_lbl.config(text="")
        self.meta_lbl.config(text="")
        for child in self.detail_frame.winfo_children():
            child.destroy()
        self.images_list.delete(0, 'end')

    @threaded
    def search(self):
        q = self.qvar.get().strip()
        if not q:
            self.after(0, self.populate_static_games)
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
        unified = []
        for g in results:
            unified.append({
                "static": False,
                "id": int(g.get("id") or g.get("game_id") or 0),
                "game_title": g.get("game_title") or g.get("title"),
                "platform": g.get("platform"),
                "release_date": g.get("release_date") or g.get("released"),
                "players": g.get("players"),
                "overview": g.get("overview") or g.get("description")
            })
        self.after(0, lambda: self.populate_results(unified, from_cache=use_cache))

    def populate_results(self, results, from_cache=False):
        self.results = results
        self.results_list.delete(0, 'end')
        for g in results:
            title = g.get("game_title") or "Untitled"
            gid = g.get("id") or ""
            self.results_list.insert('end', f"{title} — {gid}")
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
        if idx < 0 or idx >= len(self.results):
            return
        g = self.results[idx]
        self.back_btn.pack(anchor="w", pady=(0,4))
        if g.get("static"):
            self.show_table(g)
        else:
            game_id = g.get("id")
            cached = db_get_game(game_id)
            now = int(time.time())
            if cached and (now - cached["updated_at"] < CACHE_TTL_SECONDS):
                game = cached["data"]
                images = db_get_images(game_id)
                self.show_table_from_remote(game, images)
            else:
                self.show_table(g)
                threading.Thread(target=self.fetch_and_show, args=(game_id,), daemon=True).start()

    def fetch_and_show(self, game_id):
        try:
            game, images = get_game_remote(game_id)
            db_save_game(game_id, game, images)
            images_urls = [im.get("url") for im in images if im.get("url")]
            self.after(0, lambda: self.show_table_from_remote(game, images_urls))
        except Exception as e:
            self.error(e)

    def show_table(self, d):
        for child in self.detail_frame.winfo_children():
            child.destroy()
        title = d.get("game_title") or d.get("title") or "Example Game"
        self.title_lbl.config(text=title)
        meta = []
        if d.get("platform"): meta.append(d.get("platform"))
        if d.get("release_date"): meta.append(str(d.get("release_date")))
        if d.get("players"): meta.append(f"Players: {d.get('players')}")
        self.meta_lbl.config(text=" • ".join(meta))

        fields = [
            ("Game ID (for coding and debug only remove or hide when project is done)", d.get("id") or ""),
            ("Name", title),
            ("Platform", d.get("platform") or "NES"),
            ("Release Date", str(d.get("release_date") or "2017")),
            ("Players", d.get("players") or "1-4"),
            ("Description", d.get("overview") or d.get("description") or "Sample overview"),
            ("Images", ", ".join(d.get("images") or []) or "link.jpg")
        ]

        self.detail_frame.columnconfigure(0, minsize=220, weight=0)
        self.detail_frame.columnconfigure(1, weight=1)

        for r, (fld, val) in enumerate(fields):
            lbl_f = ttk.Label(self.detail_frame, text=fld, anchor="w", style='White.TLabel')
            lbl_v = ttk.Label(self.detail_frame, text=str(val), anchor="w", wraplength=700, style='White.TLabel')
            lbl_f.grid(row=r, column=0, sticky="nw", padx=(4,8), pady=6)
            lbl_v.grid(row=r, column=1, sticky="nw", padx=(0,12), pady=6)

        self.images_list.delete(0, 'end')
        imgs = d.get("images") or []
        if imgs:
            for u in imgs:
                self.images_list.insert('end', u)
        else:
            self.images_list.insert('end', "link.jpg")
        self.set_status("Ready")

    def show_table_from_remote(self, game, images):
        for child in self.detail_frame.winfo_children():
            child.destroy()
        title = game.get("game_title") or game.get("title") or "Example Game"
        self.title_lbl.config(text=title)
        platform = game.get("platform") or game.get("platforms") or ""
        release = game.get("release_date") or game.get("released") or ""
        players = game.get("players") or ""
        self.meta_lbl.config(text=" • ".join(x for x in [platform, str(release), (f'Players: {players}' if players else "")] if x))

        imgs = images or []

        fields = [
            ("Game ID (for coding and debug only remove or hide when project is done)", game.get("id") or game.get("game_id") or ""),
            ("Name", title),
            ("Platform", platform or "NES"),
            ("Release Date", release or "2017"),
            ("Players", players or "1-4"),
            ("Description", game.get("overview") or game.get("description") or "Sample overview"),
            ("Images", ", ".join(imgs) or "link.jpg")
        ]

        self.detail_frame.columnconfigure(0, minsize=220, weight=0)
        self.detail_frame.columnconfigure(1, weight=1)

        for r, (fld, val) in enumerate(fields):
            lbl_f = ttk.Label(self.detail_frame, text=fld, anchor="w", style='White.TLabel')
            lbl_v = ttk.Label(self.detail_frame, text=str(val), anchor="w", wraplength=700, style='White.TLabel')
            lbl_f.grid(row=r, column=0, sticky="nw", padx=(4,8), pady=6)
            lbl_v.grid(row=r, column=1, sticky="nw", padx=(0,12), pady=6)

        self.images_list.delete(0, 'end')
        if imgs:
            for u in imgs:
                if isinstance(u, str) and "/" in u:
                    fname = u.split("/")[-1]
                else:
                    fname = u
                self.images_list.insert('end', fname or "link.jpg")
        else:
            self.images_list.insert('end', "link.jpg")
        self.set_status("Ready")

    def open_image(self, evt):
        sel = self.images_list.curselection()
        if not sel:
            return
        idx = sel[0]
        try:
            val = self.images_list.get(idx)
            if isinstance(val, str) and (val.startswith("http://") or val.startswith("https://")):
                webbrowser.open(val)
        except Exception:
            pass

if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()
