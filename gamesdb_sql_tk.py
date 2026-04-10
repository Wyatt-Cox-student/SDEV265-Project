import tkinter as tk
from tkinter import messagebox
import requests

# --- COLORS ---
BG = "#BCBCBC"
FG = "black"

# --- API CONFIG ---
API_KEY = '7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830'
BASE_URL = 'https://api.thegamesdb.net/'

# --- GLOBAL STATE ---
platform_cache = {}
genre_cache = {}
last_search_results = []
is_showing_detail = False

# ------------------ DATA ------------------

def load_platforms():
    global platform_cache
    try:
        resp = requests.get(f"{BASE_URL}v1/Platforms?apikey={API_KEY}")
        data = resp.json()
        for pid, pdata in data.get("data", {}).get("platforms", {}).items():
            platform_cache[int(pid)] = pdata.get("name", "Unknown")
    except Exception as e:
        print("Error loading platforms:", e)

def get_platform_name(platform_id):
    return platform_cache.get(platform_id, "Unknown")

def load_genres():
    global genre_cache
    try:
        resp = requests.get(f"{BASE_URL}v1/Genres?apikey={API_KEY}")
        data = resp.json()
        for gid, gdata in data.get("data", {}).get("genres", {}).items():
            genre_cache[int(gid)] = gdata.get("name", "Unknown")
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
    for pid, name in platform_cache.items():
        if search_name.lower() in name.lower():
            return pid
    return None

def filter_by_platform(platform_keyword):
    for w in results_inner_frame.winfo_children():
        w.destroy()

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

# ------------------ UI ROW ------------------

def build_result_row(game):
    game_id = game.get("id")
    title = game.get("game_title", "N/A")
    release_date = game.get("release_date", "Unknown")
    platform_name = get_platform_name(game.get("platform"))

    row = tk.Frame(results_inner_frame, bg=BG, padx=4, pady=6)
    row.pack(fill="x", pady=2)

    title_lbl = tk.Label(row, text=title, fg="blue", bg=BG,
                         cursor="hand2",
                         font=("TkDefaultFont", 10, "underline"))
    title_lbl.pack(fill="x")

    meta_lbl = tk.Label(row, text=f"{platform_name} • {release_date}",
                        fg="gray", bg=BG)
    meta_lbl.pack(fill="x")

    def on_click(e=None):
        fetch_game_details(game_id)

    title_lbl.bind("<Button-1>", on_click)
    meta_lbl.bind("<Button-1>", on_click)

# ------------------ SEARCH ------------------

def fetch_game_data_by_name():
    global last_search_results, is_showing_detail

    name = entry_name.get().strip()
    if not name:
        messagebox.showwarning("Input Error", "Enter a game name")
        return

    back_button.pack_forget()

    try:
        url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={name}"
        resp = requests.get(url)
        data = resp.json()
        games = data.get("data", {}).get("games", [])

        last_search_results = games
        is_showing_detail = False

        for w in results_inner_frame.winfo_children():
            w.destroy()

        if games:
            for game in games:
                build_result_row(game)
        else:
            tk.Label(results_inner_frame, text="No games found.", bg=BG, fg=FG).pack()

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ------------------ DETAILS ------------------

def fetch_game_details(game_id):
    global is_showing_detail
    is_showing_detail = True

    for w in results_inner_frame.winfo_children():
        w.destroy()

    back_button.pack_forget()
    back_button.pack(side="left")

    try:
        url = f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}&fields=overview,players,genres,release_date,platform,game_title"
        resp = requests.get(url)
        data = resp.json()
        game = data.get("data", {}).get("games", [])[0]

        fields = [
            ("Name", game.get("game_title")),
            ("Platform", get_platform_name(game.get("platform"))),
            ("Genre", get_genres_text(game.get("genres"))),
            ("Release Date", game.get("release_date")),
            ("Players", game.get("players")),
            ("Description", game.get("overview") or "No description")
        ]

        for i, (label, value) in enumerate(fields, start=1):
            tk.Label(results_inner_frame, text=label + ":",
                     bg=BG, fg=FG,
                     font=("TkDefaultFont", 10, "bold")).grid(row=i, column=0, sticky="w")

            tk.Label(results_inner_frame, text=value,
                     bg=BG, fg=FG,
                     wraplength=500).grid(row=i, column=1, sticky="w")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# ------------------ BACK ------------------

def show_previous_results():
    global is_showing_detail
    is_showing_detail = False

    back_button.pack_forget()

    for w in results_inner_frame.winfo_children():
        w.destroy()

    for game in last_search_results:
        build_result_row(game)

# ------------------ CLEAR ------------------

def clear_search():
    entry_name.delete(0, tk.END)
    for w in results_inner_frame.winfo_children():
        w.destroy()
    back_button.pack_forget()

# ------------------ GUI ------------------

root = tk.Tk()
root.title("TheGamesDB Browser")
root.geometry("800x800")
root.configure(bg=BG)

# ================= TOP BAR (FIXED CLEAN SPLIT) =================

top_frame = tk.Frame(root, bg=BG)
top_frame.pack(fill="x", padx=10, pady=5)

# LEFT SIDE ONLY BACK BUTTON
left_bar = tk.Frame(top_frame, bg=BG)
left_bar.pack(side="left")

back_button = tk.Button(
    left_bar,
    text="← Back",
    command=show_previous_results,
    bg=BG,
    fg="red",
    bd=1.5,
    relief="solid",
    width= 7
)

# DO NOT PACK HERE (only in detail view)

# RIGHT SIDE SEARCH AREA
# RIGHT SIDE SEARCH AREA
right_bar = tk.Frame(top_frame, bg=BG)
right_bar.pack(side="left", fill="x", expand=True)

# CENTER CONTAINER
search_container = tk.Frame(right_bar, bg=BG)
search_container.pack(side="right")  # this centers it horizontally

tk.Label(search_container, text="Search:", bg=BG, fg=FG).pack(side="left")

entry_name = tk.Entry(search_container, width=30)
entry_name.pack(side="left", padx=5)

tk.Button(search_container, text="Search",
          command=fetch_game_data_by_name,
          bg=BG, fg="red", bd=1.5, relief="solid", width=10).pack(side="left", padx=5)

tk.Button(search_container, text="Clear",
          command=clear_search,
          bg=BG, fg="red", bd=1.5, relief="solid", width=10).pack(side="left", padx=5)

# ------------------ MAIN ------------------

main_frame = tk.Frame(root, bg=BG)
main_frame.pack(fill="both", expand=True)

filter_frame = tk.Frame(main_frame, bg=BG, width=150, bd=1, relief="solid")
filter_frame.pack(side="left", fill="y")

tk.Label(filter_frame, text="Filters", bg="#000000", fg="white",
         font=("TkDefaultFont", 12, "bold"), width=15, height = 2).pack(pady=10)

tk.Button(filter_frame, text="NES",
          command=lambda: filter_by_platform("Nintendo Entertainment System"),
          bg="#000000", fg="white", bd=0, width=15).pack(pady=10)

tk.Button(filter_frame, text="SEGA",
          command=lambda: filter_by_platform("Genesis"),
          bg="#000000", fg="white", bd=0, width=15).pack(pady=10)

tk.Button(filter_frame, text="SNES",
          command=lambda: filter_by_platform("Super Nintendo"),
          bg="#000000", fg="white", bd=0, width=15).pack(pady=10)

tk.Button(filter_frame, text="All",
          command=show_previous_results,
          bg="#000000", fg="white", bd=0, width=15).pack(pady=10)

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

results_canvas.create_window((0, 0), window=results_inner_frame, anchor="nw")
results_canvas.configure(yscrollcommand=scrollbar.set)

results_canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# ------------------ INIT ------------------

load_platforms()
load_genres()

root.mainloop()