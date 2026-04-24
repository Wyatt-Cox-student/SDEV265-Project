import json
import os
import time
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import requests
import sqlite3
from PIL import Image, ImageTk, UnidentifiedImageError
from io import BytesIO

# --- COLORS ---
BG = "#BCBCBC"
FG = "black"
# --- API CONFIG ---
# Current API key: Teresa's
#API_KEY = '1b2b1e65b282ff78c4345dfc6dccc509bd50baeeb7b00abfb7533c23f15a962c' #<- change the number between the '' to your API Key
BASE_URL = 'https://api.thegamesdb.net/'
DB_PATH = "gamesdb_cache.db"
THIRTY_DAYS = 60 * 60 * 24 * 30


SEARCH_TTL = THIRTY_DAYS
DETAIL_TTL = THIRTY_DAYS
LOOKUP_TTL = THIRTY_DAYS

API_TTL = THIRTY_DAYS
IMAGE_CACHE_DIR = "image_cache"
current_detail_image = None
current_gallery_images = []
current_gallery_items = []
current_gallery_index = 0
current_gallery_label = None
current_gallery_caption = None
current_gallery_after_id = None

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
    CREATE TABLE IF NOT EXISTS api_key_cache (
        key TEXT NOT NULL,
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

def get_cached_api_key():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, updated_at FROM api_key_cache LIMIT 1")
    row = cur.fetchone()
    conn.close()


    if row and is_fresh(row[1], API_TTL):
        return row[0]
    return None

def save_api_key(key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM api_key_cache")
    cur.execute(
        "INSERT INTO api_key_cache (key, updated_at) VALUES (?, ?)",
        (key, int(time.time()))
    )
    conn.commit()
    conn.close()
   
def prompt_for_api_key():
    popup = tk.Toplevel(root)
    popup.title("API Key Required")
    popup.geometry("400x150")
    popup.configure(bg=BG)
    popup.grab_set()


    tk.Label(popup, text="Enter API Key:", bg=BG, fg=FG).pack(pady=10)


    entry = tk.Entry(popup, width=50)
    entry.pack(pady=5)


    def submit():
        global API_KEY
        key = entry.get().strip()


        if not key:
            messagebox.showwarning("Error", "API key cannot be empty")
            return


        API_KEY = key
        save_api_key(key)
        popup.destroy()


    tk.Button(popup, text="Save", command=submit).pack(pady=10)

def require_api_key():
    if not API_KEY:
        messagebox.showerror("API Key Missing", "Please enter API key first")
        return False
    return True

def clear_api_key():
    global API_KEY

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM api_key_cache")
    conn.commit()
    conn.close()

    API_KEY = None

    messagebox.showinfo("API Key", "API key cleared. Please enter a new one.")

    root.after(100, prompt_for_api_key)


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


def remove_cached_image(image_path):
    try:
        if os.path.exists(image_path):
            os.remove(image_path)
    except OSError:
        pass


def load_photo_image_from_path(image_path, max_size):
    try:
        with Image.open(image_path) as pil_image:
            pil_image.thumbnail(max_size, Image.LANCZOS)
            return ImageTk.PhotoImage(pil_image.copy())
    except (FileNotFoundError, OSError, UnidentifiedImageError):
        remove_cached_image(image_path)
        return None


def load_photo_image_from_bytes(image_bytes, max_size):
    try:
        with Image.open(BytesIO(image_bytes)) as pil_image:
            pil_image.thumbnail(max_size, Image.LANCZOS)
            return ImageTk.PhotoImage(pil_image.copy())
    except (OSError, UnidentifiedImageError):
        return None




def stop_detail_slideshow():
    global current_gallery_images, current_gallery_items, current_gallery_index
    global current_gallery_label, current_gallery_caption, current_gallery_after_id


    if current_gallery_after_id:
        try:
            root.after_cancel(current_gallery_after_id)
        except Exception:
            pass


    current_gallery_images = []
    current_gallery_items = []
    current_gallery_index = 0
    current_gallery_label = None
    current_gallery_caption = None
    current_gallery_after_id = None




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
    if not require_api_key():
        return


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
def build_image_url(base_url, image_path):
    if not image_path:
        return None


    if image_path.startswith("http"):
        return image_path


    return f"{base_url}{image_path}" if base_url else None




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
    return build_image_url(base_url, image_path)




def get_game_media_urls(game_id):
    url = f"{BASE_URL}v1/Games/Images"
    resp = requests.get(
        url,
        params={
            "apikey": API_KEY,
            "games_id": game_id
        },
        timeout=15
    )
    resp.raise_for_status()


    data = resp.json()
    base_url = data.get("data", {}).get("base_url", "")
    if isinstance(base_url, dict):
        base_url = (
            base_url.get("original")
            or base_url.get("large")
            or base_url.get("medium")
            or base_url.get("small")
            or ""
        )


    image_items = []
    seen = set()


    def collect_urls(node, parent_key=""):
        if isinstance(node, dict):
            image_path = node.get("filename") or node.get("url")
            image_type = (node.get("type") or parent_key or "").lower()
            side = (node.get("side") or "").lower()
            lowered_path = (image_path or "").lower()


            is_gallery_image = (
                image_path
                and image_type != "boxart"
                and not any(part in lowered_path for part in ("boxart/", "/boxart", "boxart\\"))
            )


            if is_gallery_image:
                full_url = build_image_url(base_url, image_path)
                if full_url and full_url not in seen:
                    seen.add(full_url)
                    label_parts = []
                    if image_type:
                        label_parts.append(image_type.replace("_", " ").title())
                    if side:
                        label_parts.append(side.title())


                    image_items.append({
                        "url": full_url,
                        "label": " - ".join(label_parts) if label_parts else "Image"
                    })


            for key, value in node.items():
                collect_urls(value, str(key).lower())
        elif isinstance(node, list):
            for item in node:
                collect_urls(item, parent_key)


    collect_urls(data)
    return image_items




def should_refresh_media_items(media_items):
    if not media_items:
        return True


    labels = " ".join(
        (item.get("label") or "").lower()
        for item in media_items
        if isinstance(item, dict)
    )


    has_title_screen = any(
        keyword in labels
        for keyword in ("title", "titlescreen", "title screen")
    )


    return len(media_items) < 4 or not has_title_screen




def load_boxart_image(game_id, image_url, max_size=(300, 420)):
    if not game_id or not image_url:
        return None




    ensure_image_cache_dir()
    image_path = os.path.join(IMAGE_CACHE_DIR, f"{game_id}.jpg")




    if os.path.exists(image_path):
        cached_image = load_photo_image_from_path(image_path, max_size)
        if cached_image:
            return cached_image




    try:
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None
        return None
    except requests.RequestException:
        return None




    with open(image_path, "wb") as image_file:
        image_file.write(resp.content)

    image = load_photo_image_from_bytes(resp.content, max_size)
    if image:
        return image

    remove_cached_image(image_path)
    return None




def load_cached_detail_image(game_id, image_url, cache_name, max_size):
    if not game_id or not image_url:
        return None


    ensure_image_cache_dir()
    game_cache_dir = os.path.join(IMAGE_CACHE_DIR, str(game_id))
    os.makedirs(game_cache_dir, exist_ok=True)


    image_path = os.path.join(game_cache_dir, cache_name)


    if os.path.exists(image_path):
        cached_image = load_photo_image_from_path(image_path, max_size)
        if cached_image:
            return cached_image


    try:
        resp = requests.get(image_url, timeout=15)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None
        return None
    except requests.RequestException:
        return None


    with open(image_path, "wb") as image_file:
        image_file.write(resp.content)

    image = load_photo_image_from_bytes(resp.content, max_size)
    if image:
        return image

    remove_cached_image(image_path)
    return None




def start_detail_slideshow(parent, game_id, image_items, row_num, max_size=(450, 300), delay_ms=2200):
    global current_gallery_images, current_gallery_items, current_gallery_index
    global current_gallery_label, current_gallery_caption, current_gallery_after_id


    stop_detail_slideshow()


    if not image_items:
        return


    gallery_images = []
    gallery_items = []
    for index, item in enumerate(image_items[:30], start=1):
        image = load_cached_detail_image(game_id, item.get("url"), f"media_{index}.jpg", max_size)
        if image:
            gallery_images.append(image)
            gallery_items.append(item)


    if not gallery_images:
        return


    tk.Label(
        parent,
        text="Game Images:",
        bg=BG,
        fg=FG,
        font=("TkDefaultFont", 10, "bold")
    ).grid(row=row_num, column=0, sticky="n", padx=(0, 10), pady=(14, 4))


    gallery_frame = tk.Frame(parent, bg=BG)
    gallery_frame.grid(row=row_num, column=1, sticky="n", pady=(14, 4))


    current_gallery_label = tk.Label(gallery_frame, bg=BG)
    current_gallery_label.pack(anchor="center")


    current_gallery_caption = tk.Label(gallery_frame, bg=BG, fg=FG, justify="left")
    current_gallery_caption.pack(anchor="center", pady=(6, 4))


    nav_frame = tk.Frame(gallery_frame, bg=BG)
    nav_frame.pack(anchor="center")


    current_gallery_images = gallery_images
    current_gallery_items = gallery_items


    def show_image(index):
        global current_gallery_index, current_gallery_after_id


        if not current_gallery_label or not current_gallery_label.winfo_exists():
            current_gallery_after_id = None
            return


        current_gallery_index = index % len(current_gallery_images)
        current_gallery_label.configure(image=current_gallery_images[current_gallery_index])
        current_gallery_label.image = current_gallery_images[current_gallery_index]


        item = current_gallery_items[current_gallery_index]
        current_gallery_caption.configure(
            text=f"{item.get('label', 'Image')} ({current_gallery_index + 1}/{len(current_gallery_images)})"
        )
        current_gallery_after_id = root.after(delay_ms, lambda: show_image(current_gallery_index + 1))


    show_image(0)




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
    stop_detail_slideshow()
    if not require_api_key():
        return




    for w in results_inner_frame.winfo_children():
        w.destroy()




    back_button.pack_forget()
    back_button.pack(side="left")


    try:
        game, has_details = get_cached_game(game_id)


        needs_boxart_lookup = game and has_details and not game.get("boxart_url") and not has_cached_boxart_image(game_id)
        needs_media_lookup = not game or not has_details or not game.get("media_image_items")


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


        if needs_media_lookup:
            try:
                game["media_image_items"] = get_game_media_urls(game_id)
            except Exception as media_error:
                print(f"Skipping slideshow images for game {game_id}: {media_error}")
                game["media_image_items"] = game.get("media_image_items", [])


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


        start_detail_slideshow(
            results_inner_frame,
            game_id,
            game.get("media_image_items", []),
            len(fields) + 1
        )


    except Exception as e:
        messagebox.showerror("Error", str(e))




def apply_sort(option):
    global last_search_results


    if not last_search_results:
        return


    if option == "Sort by":
        fetch_game_data_by_name()
        return


    if option == "A → Z":
        last_search_results.sort(key=lambda g: g.get("game_title", "").lower())


    elif option == "Z → A":
        last_search_results.sort(key=lambda g: g.get("game_title", "").lower(), reverse=True)


    elif option == "Oldest → Newest":
        last_search_results.sort(key=lambda g: g.get("release_date") or "")


    elif option == "Newest → Oldest":
        last_search_results.sort(key=lambda g: g.get("release_date") or "", reverse=True)


    rebuild_results_only()




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
        elif active_filter == "Atari 2600":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Atari 2600")]
        elif active_filter == "Sega MS":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Sega Master System")]
        elif active_filter == "TurboGrafx-16":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("TurboGrafx-16")]
        elif active_filter == "GameCube":
            filtered = [g for g in last_search_results if g.get("platform") == find_platform_id_by_name("Nintendo GameCube")]
        else:
            filtered = last_search_results




        for game in filtered:
            build_result_row(game)


def show_previous_results():
    global is_showing_detail


    is_showing_detail = False
    stop_detail_slideshow()
    back_button.pack_forget()


    rebuild_results_only()
# ------------------ CLEAR ------------------


def clear_search():
    global active_filter


    entry_name.delete(0, tk.END)
    stop_detail_slideshow()
    for w in results_inner_frame.winfo_children():
        w.destroy()
    back_button.pack_forget()
    active_filter = None
    set_filter_button_styles()








# ------------------ GUI ------------------


root = tk.Tk()
root.title("Classic Games Browser")
root.geometry("900x900")
root.configure(bg=BG)


# ================= TOP BAR =================


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
search_container = tk.Frame(
    right_bar,
    bg=BG,
    bd=1,
    relief="solid",
    padx=5, pady=20
)
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
clear_button = ctk.CTkButton(buttons_container, text="Reset",
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


ctk.CTkLabel(filter_frame, text="Filters", bg_color="#000000", fg_color="#000000", text_color= "red",
         font=("TkDefaultFont", 20, "bold"), width=180, height = 40).pack(pady=10, padx = 10)








# Filter Buttons
atari2600_button= ctk.CTkButton(
    filter_frame,
    text="Atari2600",
    command=lambda: filter_by_platform("Atari 2600", "Atari 2600"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=35
)
atari2600_button.pack(pady=5, padx=10)


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
    height=35
)




nes_button.pack(pady=5, padx=10)


sms_button = ctk.CTkButton(
    filter_frame,
    text="Sega MS",
    command=lambda: filter_by_platform("Sega MS", "Sega Master System"),
    bg_color="#000000",
    fg_color="#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color="white",
    font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=35
)
sms_button.pack(pady=5, padx=10)


tg16_button = ctk.CTkButton(
    filter_frame,
    text="TG16",
    command=lambda: filter_by_platform("TG16", "TurboGrafx 16"),
    bg_color="#000000",
    fg_color="#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color="white",
    font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=35
)
tg16_button.pack(pady=5, padx=10)


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
    height=35
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
    height=35
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
    height=35
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
    height=35
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
    height=35
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
    height=35
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
    height=35
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
    height=35
)
ps2_button.pack(pady=5, padx=10)




all_button= ctk.CTkButton(
    filter_frame,
    text="Remove",
    command=lambda: apply_filter("All"),
    bg_color= "#000000",
    fg_color= "#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color= "white", font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=35
)
all_button.pack(pady=5, padx=10)


ctk.CTkLabel(filter_frame, text="Tools", bg_color="#000000", fg_color="#000000", text_color= "red",
         font=("TkDefaultFont", 20, "bold"), width=180, height = 40).pack(pady=10, padx = 10)


sort_var = tk.StringVar(value="Sort by")


sort_dropdown = ctk.CTkOptionMenu(
    filter_frame,
    values=[
        "Sort by",
        "A → Z",
        "Z → A",
        "Oldest → Newest",
        "Newest → Oldest"
    ],
    command=apply_sort,
    variable=sort_var,
    bg_color="#000000",
    fg_color="#000000",
    corner_radius=0,
    button_color="#000000",
    button_hover_color="#585858",
    text_color="white",
    font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=35,
    anchor="center"
)


sort_dropdown.pack(pady=5, padx=10)


clear_api_button = ctk.CTkButton(
    filter_frame,
    text="Reset API",
    command=clear_api_key,
    bg_color="#000000",
    fg_color="#000000",
    hover_color="#585858",
    corner_radius=0,
    text_color="white",
    font=("TkDefaultFont", 15, "bold"),
    width=180,
    height=30
)


clear_api_button.pack(pady=5, padx=10)


filter_buttons["NES"] = nes_button
filter_buttons["SEGA GEN."] = sega_button
filter_buttons["SNES"] = snes_button
filter_buttons["N64"] = n64_button
filter_buttons["PS"] = ps_button
filter_buttons["PS2"] = ps2_button
filter_buttons["Dreamcast"] = Dreamcast_button
filter_buttons["Saturn"] = Saturn_button
filter_buttons["GameCube"] = GameCube_button
filter_buttons["Atari 2600"] = atari2600_button
filter_buttons["Sega MS"] = sms_button
filter_buttons["TG16"] = tg16_button
filter_buttons["All"] = all_button
filter_buttons["Reset API"] = clear_api_button


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


API_KEY = get_cached_api_key()


if not API_KEY:
    root.after(100, prompt_for_api_key)


root.mainloop()