import json
import os
import time
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import requests
import sqlite3
from PIL import Image, ImageTk
from io import BytesIO

# --- COLORS ---
BG = "#BCBCBC"
FG = "black"
# --- API CONFIG ---
# Current API key: Teresa's
API_KEY = '1b2b1e65b282ff78c4345dfc6dccc509bd50baeeb7b00abfb7533c23f15a962c' #<- change the number between the '' to your API Key
BASE_URL = 'https://api.thegamesdb.net/'
DB_PATH = "gamesdb_cache.db"
THIRTY_DAYS = 60 * 60 * 24 * 30

SEARCH_TTL = THIRTY_DAYS
DETAIL_TTL = THIRTY_DAYS
LOOKUP_TTL = THIRTY_DAYS
IMAGE_CACHE_DIR = "image_cache"
current_detail_image = None


# --- GLOBAL STATE ---
platform_cache = {}
genre_cache = {}
last_search_results = []
is_showing_detail = False
active_filter = None
filter_buttons = {}


# ------------------ DATA ------------------


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()


    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_index (
            q TEXT PRIMARY KEY,
            results TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            has_details INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS platforms (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)


    cur.execute("PRAGMA table_info(games)")
    game_columns = {row[1] for row in cur.fetchall()}
    if "has_details" not in game_columns:
        cur.execute("ALTER TABLE games ADD COLUMN has_details INTEGER NOT NULL DEFAULT 0")


    conn.commit()
    conn.close()


def is_fresh(updated_at, ttl):
    return (int(time.time()) - updated_at) < ttl


def get_cached_search(query):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT results, updated_at FROM search_index WHERE q = ?", (query,))
    row = cur.fetchone()
    conn.close()


    if row and is_fresh(row[1], SEARCH_TTL):
        return json.loads(row[0])
    return None


def save_search(query, games):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO search_index (q, results, updated_at)
        VALUES (?, ?, ?)
    """, (query, json.dumps(games), int(time.time())))
    conn.commit()
    conn.close()


def get_cached_game(game_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data, has_details, updated_at FROM games WHERE id = ?", (game_id,))
    row = cur.fetchone()
    conn.close()


    if row and is_fresh(row[2], DETAIL_TTL):
        return json.loads(row[0]), bool(row[1])
    return None, False


def save_game(game, has_details=False):
    game_id = game.get("id")
    if game_id is None:
        return


    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data, has_details FROM games WHERE id = ?", (game_id,))
    existing = cur.fetchone()


    if existing and existing[1]:
        if not has_details:
            game = json.loads(existing[0])
        has_details = True


    cur.execute("""
        INSERT OR REPLACE INTO games (id, data, has_details, updated_at)
        VALUES (?, ?, ?, ?)
    """, (
        game_id,
        json.dumps(game),
        1 if has_details else 0,
        int(time.time())
    ))
    conn.commit()
    conn.close()


def get_cached_lookup(table_name, ttl):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id, name, updated_at FROM {table_name}")
    rows = cur.fetchall()
    conn.close()


    if not rows:
        return None


    newest = max(row[2] for row in rows)
    if not is_fresh(newest, ttl):
        return None


    return {int(row[0]): row[1] for row in rows}


def save_lookup(table_name, data_dict):
    conn = get_db_connection()
    cur = conn.cursor()
    now = int(time.time())


    for item_id, name in data_dict.items():
        cur.execute(
            f"INSERT OR REPLACE INTO {table_name} (id, name, updated_at) VALUES (?, ?, ?)",
            (int(item_id), name, now)
        )


    conn.commit()
    conn.close()


def ensure_image_cache_dir():
    os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)


def load_platforms():
    global platform_cache


    cached = get_cached_lookup("platforms", LOOKUP_TTL)
    if cached:
        platform_cache = cached
        return


    try:
        resp = requests.get(f"{BASE_URL}v1/Platforms?apikey={API_KEY}")
        data = resp.json()
        platform_cache = {}
        for pid, pdata in data.get("data", {}).get("platforms", {}).items():
            platform_cache[int(pid)] = pdata.get("name", "Unknown")
        save_lookup("platforms", platform_cache)
    except Exception as e:
        print("Error loading platforms:", e)


def get_platform_name(platform_id):
    return platform_cache.get(platform_id, "Unknown")


def load_genres():
    global genre_cache


    cached = get_cached_lookup("genres", LOOKUP_TTL)
    if cached:
        genre_cache = cached
        return


    try:
        resp = requests.get(f"{BASE_URL}v1/Genres?apikey={API_KEY}")
        data = resp.json()
        genre_cache = {}
        for gid, gdata in data.get("data", {}).get("genres", {}).items():
            genre_cache[int(gid)] = gdata.get("name", "Unknown")
        save_lookup("genres", genre_cache)
    except Exception as e:
        print("Error loading genres:", e)


def get_genres_text(raw):
    if not raw:
        return "Unknown"
    if isinstance(raw, list):
        return ", ".join(genre_cache.get(int(g), str(g)) for g in raw)
    return str(raw)


# ------------------ FILTER ------------------


def find_platform_id_by_name(search_name):
    search_lower = search_name.lower().strip()

    # try exact match first
    for pid, name in platform_cache.items():
        if name.lower().strip() == search_lower:
            return pid

    # If there is no exact match, fall back to partial match
    for pid, name in platform_cache.items():
        if search_lower in name.lower():
            return pid

    return None


def set_filter_button_styles():
    normal_fg = "#000000"
    normal_text = "white"
    normal_hover = "#585858"

    selected_fg = "#8B0000"
    selected_text = "white"
    selected_hover = "#A00000"

    for filter_name, button in filter_buttons.items():
        if filter_name == active_filter:
            button.configure(
                fg_color=selected_fg,
                text_color=selected_text,
                hover_color=selected_hover
            )
        else:
            button.configure(
                fg_color=normal_fg,
                text_color=normal_text,
                hover_color=normal_hover
            )

def apply_filter(filter_name, platform_keyword=None):
    global active_filter


    if active_filter == filter_name:
        active_filter = None


        for w in results_inner_frame.winfo_children():
            w.destroy()


        for game in last_search_results:
            build_result_row(game)


        set_filter_button_styles()
        return


    active_filter = filter_name
    set_filter_button_styles()


    for w in results_inner_frame.winfo_children():
        w.destroy()


    if filter_name == "All":
        for game in last_search_results:
            build_result_row(game)
        return


    pid = find_platform_id_by_name(platform_keyword)


    if not pid:
        tk.Label(results_inner_frame, text="Platform not found.", bg=BG, fg=FG).pack()
        return


    filtered = [g for g in last_search_results if g.get("platform") == pid]


    if filtered:
        for game in filtered:
            build_result_row(game)
    else:
        tk.Label(results_inner_frame, text="No games match this filter.", bg=BG, fg=FG).pack()


def filter_by_platform(filter_name, platform_keyword):
    apply_filter(filter_name, platform_keyword)


# ------------------ UI ROW ------------------


def build_result_row(game):
    game_id = game.get("id")
    title = game.get("game_title", "N/A")
    release_date = game.get("release_date", "Unknown")
    platform_name = get_platform_name(game.get("platform"))


    normal_bg = BG
    hover_bg = "#A8A8A8"


    row = tk.Frame(results_inner_frame, bg=normal_bg, padx=4, pady=6)
    row.pack(fill="x", pady=2)


    title_lbl = tk.Label(
        row,
        text=title,
        fg="blue",
        bg=normal_bg,
        cursor="hand2",
        font=("TkDefaultFont", 10, "underline")
    )
    title_lbl.pack(fill="x")


    meta_lbl = tk.Label(
        row,
        text=f"{platform_name} • {release_date}",
        fg="gray",
        bg=normal_bg
    )
    meta_lbl.pack(fill="x")


    def on_click(e=None):
        fetch_game_details(game_id)


    def on_enter(e=None):
        row.config(bg=hover_bg)
        title_lbl.config(bg=hover_bg)
        meta_lbl.config(bg=hover_bg)


    def on_leave(e=None):
        row.config(bg=normal_bg)
        title_lbl.config(bg=normal_bg)
        meta_lbl.config(bg=normal_bg)


    row.bind("<Button-1>", on_click)
    title_lbl.bind("<Button-1>", on_click)
    meta_lbl.bind("<Button-1>", on_click)


    row.bind("<Enter>", on_enter)
    title_lbl.bind("<Enter>", on_enter)
    meta_lbl.bind("<Enter>", on_enter)


    row.bind("<Leave>", on_leave)
    title_lbl.bind("<Leave>", on_leave)
    meta_lbl.bind("<Leave>", on_leave)


# ------------------ SEARCH ------------------


def fetch_game_data_by_name():
    global last_search_results, is_showing_detail, active_filter


    name = entry_name.get().strip()
    if not name:
        messagebox.showwarning("Input Error", "Enter a game name")
        return


    query = name.lower()
    back_button.pack_forget()


    try:
        games = get_cached_search(query)


        if games is None:
            url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={name}"
            resp = requests.get(url)
            data = resp.json()
            games = data.get("data", {}).get("games", [])


            save_search(query, games)


            for game in games:
                save_game(game, has_details=False)


        last_search_results = games
        is_showing_detail = False
        active_filter = None
        set_filter_button_styles()


        for w in results_inner_frame.winfo_children():
            w.destroy()


        if games:
            for game in games:
                build_result_row(game)
        else:
            tk.Label(results_inner_frame, text="No games found.", bg=BG, fg=FG).pack()


    except Exception as e:
        messagebox.showerror("Error", str(e))


# Box art pull
def get_boxart_url(api_data, game_id):
    include = api_data.get("include", {}) or api_data.get("data", {}).get("include", {})
    boxart = include.get("boxart", {})


    base_url = boxart.get("base_url", "")
    if isinstance(base_url, dict):
        base_url = base_url.get("original") or base_url.get("small") or ""


    art_items = []
    data_block = boxart.get("data", {})


    if isinstance(data_block, dict):
        art_items = data_block.get(str(game_id), []) or data_block.get(game_id, [])
    elif isinstance(data_block, list):
        art_items = data_block


    front_art = next((item for item in art_items if item.get("side") == "front"), None)
    art = front_art or (art_items[0] if art_items else None)


    if not art:
        return None


    image_path = art.get("filename") or art.get("url")
    if not image_path:
        return None


    if image_path.startswith("http"):
        return image_path


    return f"{base_url}{image_path}" if base_url else None




def load_boxart_image(game_id, image_url, max_size=(300, 420)):
    if not game_id or not image_url:
        return None


    ensure_image_cache_dir()
    image_path = os.path.join(IMAGE_CACHE_DIR, f"{game_id}.jpg")


    if os.path.exists(image_path):
        pil_image = Image.open(image_path)
        pil_image.thumbnail(max_size, Image.LANCZOS)
        return ImageTk.PhotoImage(pil_image)


    try:
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None
        raise


    with open(image_path, "wb") as image_file:
        image_file.write(resp.content)


    pil_image = Image.open(BytesIO(resp.content))
    pil_image.thumbnail(max_size, Image.LANCZOS)
    return ImageTk.PhotoImage(pil_image)


def has_cached_boxart_image(game_id):
    if not game_id:
        return False
    image_path = os.path.join(IMAGE_CACHE_DIR, f"{game_id}.jpg")
    return os.path.exists(image_path)


# ------------------ DETAILS ------------------


def fetch_game_details(game_id):
    global is_showing_detail, current_detail_image
    is_showing_detail = True
    current_detail_image = None


    for w in results_inner_frame.winfo_children():
        w.destroy()


    back_button.pack_forget()
    back_button.pack(side="left")


    try:
        game, has_details = get_cached_game(game_id)


        needs_boxart_lookup = game and has_details and not game.get("boxart_url") and not has_cached_boxart_image(game_id)


        if not game or not has_details or needs_boxart_lookup:
            url = f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}&fields=overview,players,genres,release_date,platform,game_title&include=boxart"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            games = data.get("data", {}).get("games", [])


            if not games:
                raise ValueError("Game details not found.")


            game = games[0]
            game["boxart_url"] = get_boxart_url(data, game_id)
            save_game(game, has_details=True)


        current_detail_image = load_boxart_image(game_id, game.get("boxart_url"))


        if current_detail_image:
            tk.Label(
                results_inner_frame,
                image=current_detail_image,
                bg=BG
            ).grid(row=0, column=0, columnspan=2, pady=(0, 12))


        fields = [
            ("Name", game.get("game_title")),
            ("Platform", get_platform_name(game.get("platform"))),
            ("Genre", get_genres_text(game.get("genres"))),
            ("Release Date", game.get("release_date")),
            ("Players", game.get("players")),
            ("Description", game.get("overview") or "No description")
        ]


        for i, (label, value) in enumerate(fields, start=1):
            tk.Label(
                results_inner_frame,
                text=label + ":",
                bg=BG,
                fg=FG,
                font=("TkDefaultFont", 10, "bold")
            ).grid(row=i, column=0, sticky="nw", padx=(0, 10), pady=2)


            tk.Label(
                results_inner_frame,
                text=value,
                bg=BG,
                fg=FG,
                wraplength=500,
                justify="left"
            ).grid(row=i, column=1, sticky="w", pady=2)


    except Exception as e:
        messagebox.showerror("Error", str(e))




# ------------------ BACK ------------------

def rebuild_results_only():
    for w in results_inner_frame.winfo_children():
        w.destroy()

    if active_filter == "All" or active_filter is None:
        for game in last_search_results:
            build_result_row(game)
    else:
        # filter names for back button to reffer to 
        # add to when other filters get added
        if active_filter == "NES":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Nintendo Entertainment System")]
        elif active_filter == "SEGA GEN.":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Genesis")]
        elif active_filter == "SNES":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Super Nintendo")]
        elif active_filter == "N64":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Nintendo 64")]
        elif active_filter == "PS":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Sony Playstation")]
        elif active_filter == "PS2":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Sony Playstation 2")]
        elif active_filter == "Dreamcast":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Sega Dreamcast")]
        elif active_filter == "Saturn":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Sega Saturn")]
        elif active_filter == "GameCube":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Nintendo GameCube")]
        else:
            filtered = last_search_results

        for game in filtered:
            build_result_row(game)
def show_previous_results():
    global is_showing_detail

    is_showing_detail = False
    back_button.pack_forget()

    rebuild_results_only()
# ------------------ CLEAR ------------------


def clear_search():
    global active_filter


    entry_name.delete(0, tk.END)
    for w in results_inner_frame.winfo_children():
        w.destroy()
    back_button.pack_forget()
    active_filter = None
    set_filter_button_styles()


# ------------------ GUI ------------------


root = tk.Tk()
root.title("TheGamesDB Browser")
root.geometry("850x810")
root.configure(bg=BG)


# ================= TOP BAR (FIXED CLEAN SPLIT) =================


top_frame = tk.Frame(root, bg=BG)
top_frame.pack(fill="x", padx=10, pady=5)


# BACK BUTTON
left_bar = tk.Frame(top_frame, bg=BG, width=160)
left_bar.pack(side="left", fill="y",padx=(25, 3))
left_bar.pack_propagate(False)


back_button = tk.Button(
    left_bar,
    text="← Back",
    command=show_previous_results,
    bg="#9F9F9F",
    fg="white",
    bd=1.5,
    relief="solid",
    width= 12
)




# SEARCH AREA
right_bar = tk.Frame(top_frame, bg=BG)
right_bar.pack(side="left", fill="x", expand=True)


# Search CONTAINER
search_container = tk.Frame(right_bar, bg=BG)
search_container.pack(anchor="center")


tk.Label(search_container, text="Search:", bg=BG, fg=FG).pack(side="left")


entry_name = tk.Entry(search_container, width=30)
entry_name.pack(side="left", padx=5)


# ----------------- BUTTON CONTAINER -----------------
buttons_container = tk.Frame(search_container, bg=BG)
buttons_container.pack(side="left", padx=5)


buttons_container.grid_columnconfigure(0, minsize=90)
buttons_container.grid_columnconfigure(1, minsize=90)


buttons_container.grid_rowconfigure(0, weight=1, minsize=30)


# Search Button
search_button = ctk.CTkButton(buttons_container, text="Search",
                               command=fetch_game_data_by_name,
                               bg_color=BG, fg_color=BG, hover_color="#585858",
                               text_color="red", font=("TkDefaultFont", 13, "bold"),  
                               border_width=2, border_color="black",
                               width=100, height=30)
search_button.grid(row=0, column=0, padx=5, pady=5)


# Clear Button
clear_button = ctk.CTkButton(buttons_container, text="Clear",
                              command=clear_search,
                              bg_color=BG, fg_color=BG, hover_color="#585858",
                              text_color="red", font=("TkDefaultFont", 13, "bold"),
                              border_width=2, border_color="black",  
                              width=100, height=30)  
clear_button.grid(row=0, column=1, padx=5, pady=5)


# ------------------ MAIN ------------------


main_frame = tk.Frame(root, bg=BG)
main_frame.pack(fill="both", expand=True)


filter_frame = tk.Frame(main_frame, bg=BG, width=150, bd=1, relief="solid")
filter_frame.pack(side="left", fill="y", padx = 10, pady =5)


ctk.CTkLabel(filter_frame, text="Filters", bg_color="#000000", fg_color="#000000", text_color= "white", 
         font=("TkDefaultFont", 15, "bold"), width=180, height = 40).pack(pady=10, padx = 10)


# Filter Buttons
nes_button = ctk.CTkButton(
    filter_frame, 
    text="NES",
    command=lambda: filter_by_platform("NES", "Nintendo Entertainment System"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 

nes_button.pack(pady=5, padx=10)

snes_button= ctk.CTkButton(
    filter_frame, 
    text="SNES",
    command=lambda: filter_by_platform("SNES", "Super Nintendo"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
snes_button.pack(pady=5, padx=10)

sega_button= ctk.CTkButton(
    filter_frame, 
    text="SEGA GEN.",
    command=lambda: filter_by_platform("SEGA GEN.", "Genesis"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
sega_button.pack(pady=5, padx=10)

ps_button= ctk.CTkButton(
    filter_frame, 
    text="PS",
    command=lambda: filter_by_platform("PS", "Sony Playstation"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
ps_button.pack(pady=5, padx=10)

n64_button= ctk.CTkButton(
    filter_frame, 
    text="N64",
    command=lambda: filter_by_platform("N64", "Nintendo 64"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
n64_button.pack(pady=5, padx=10)

Saturn_button= ctk.CTkButton(
    filter_frame, 
    text="Saturn",
    command=lambda: filter_by_platform("Saturn", "Sega Saturn"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
Saturn_button.pack(pady=5, padx=10)

Dreamcast_button= ctk.CTkButton(
    filter_frame, 
    text="Dreamcast",
    command=lambda: filter_by_platform("Dreamcast", "Sega Dreamcast"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
Dreamcast_button.pack(pady=5, padx=10)

GameCube_button= ctk.CTkButton(
    filter_frame, 
    text="GameCube",
    command=lambda: filter_by_platform("GameCube", "Nintendo GameCube"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
GameCube_button.pack(pady=5, padx=10)

ps2_button= ctk.CTkButton(
    filter_frame, 
    text="PS2",
    command=lambda: filter_by_platform("PS2", "Sony Playstation 2"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
ps2_button.pack(pady=5, padx=10)

all_button= ctk.CTkButton(
    filter_frame, 
    text="All",
    command=lambda: apply_filter("All"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180, 
    height=40
) 
all_button.pack(pady=5, padx=10)

filter_buttons["NES"] = nes_button
filter_buttons["SEGA GEN."] = sega_button
filter_buttons["SNES"] = snes_button
filter_buttons["N64"] = n64_button
filter_buttons["PS"] = ps_button
filter_buttons["PS2"] = ps2_button
filter_buttons["Dreamcast"] = Dreamcast_button
filter_buttons["Saturn"] = Saturn_button
filter_buttons["GameCube"] = GameCube_button
filter_buttons["All"] = all_button

set_filter_button_styles()
# ------------------ RESULTS ------------------


results_container = tk.Frame(main_frame, bg=BG)
results_container.pack(side="right", fill="both", expand=True)


results_canvas = tk.Canvas(results_container, bg=BG, highlightthickness=0)
scrollbar = tk.Scrollbar(results_container, command=results_canvas.yview)


results_inner_frame = tk.Frame(results_canvas, bg=BG)


results_inner_frame.bind(
    "<Configure>",
    lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all"))
)



inner_window = results_canvas.create_window((0, 0), window=results_inner_frame, anchor="nw")



def _on_canvas_configure(event):
    results_canvas.itemconfig(inner_window, width=event.width)


results_canvas.bind("<Configure>", _on_canvas_configure)


results_canvas.configure(yscrollcommand=scrollbar.set)


results_canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")


# ------------------ INIT ------------------


init_db()
load_platforms()
load_genres()


root.mainloop()