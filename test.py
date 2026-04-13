import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
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
active_filter = None
filter_buttons = {}

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

def set_filter_button_styles():
    normal_bg = "#000000"
    normal_fg = "white"
    selected_bg = "#4A4A4A"
    selected_fg = "yellow"

    for filter_name, button in filter_buttons.items():
        if filter_name == active_filter:
            button.config(bg=selected_bg, fg=selected_fg)
        else:
            button.config(bg=normal_bg, fg=normal_fg)


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
    global is_showing_detail, active_filter
    is_showing_detail = False
    active_filter = "All"

    back_button.pack_forget()

    for w in results_inner_frame.winfo_children():
        w.destroy()

    for game in last_search_results:
        build_result_row(game)

    set_filter_button_styles()

# ------------------ CLEAR ------------------

def clear_search():
    global active_filter
    entry_name.delete(0, tk.END)
    active_filter = None

    for w in results_inner_frame.winfo_children():
        w.destroy()

    back_button.pack_forget()
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
                               bg_color=BG, fg_color=BG, 
                               text_color="red", font=("TkDefaultFont", 13, "bold"),  
                               border_width=2, border_color="black", 
                               width=100, height=30)
search_button.grid(row=0, column=0, padx=5, pady=5)

# Clear Button
clear_button = ctk.CTkButton(buttons_container, text="Clear",
                              command=clear_search,
                              bg_color=BG, fg_color=BG, 
                              text_color="red", font=("TkDefaultFont", 13, "bold"), 
                              border_width=2, border_color="black",  
                              width=100, height=30)  
clear_button.grid(row=0, column=1, padx=5, pady=5)

# ------------------ MAIN ------------------

main_frame = tk.Frame(root, bg=BG)
main_frame.pack(fill="both", expand=True)

filter_frame = tk.Frame(main_frame, bg=BG, width=150, bd=1, relief="solid")
filter_frame.pack(side="left", fill="y", padx = 10, pady =5)

tk.Label(filter_frame, text="Filters", bg="#000000", fg="white",
         font=("TkDefaultFont", 12, "bold"), width=15, height = 2).pack(pady=10, padx = 10)

# Filter Buttons
nes_button = tk.Button(
    filter_frame,
    text="NES",
    command=lambda: filter_by_platform("NES", "Nintendo Entertainment System"),
    bg="#000000",
    fg="white",
    bd=0,
    width=15
)
nes_button.pack(pady=5, padx=10)

sega_button = tk.Button(
    filter_frame,
    text="SEGA",
    command=lambda: filter_by_platform("SEGA", "Genesis"),
    bg="#000000",
    fg="white",
    bd=0,
    width=15
)
sega_button.pack(pady=5, padx=10)

snes_button = tk.Button(
    filter_frame,
    text="SNES",
    command=lambda: filter_by_platform("SNES", "Super Nintendo"),
    bg="#000000",
    fg="white",
    bd=0,
    width=15
)
snes_button.pack(pady=5, padx=10)

all_button = tk.Button(
    filter_frame,
    text="All",
    command=lambda: apply_filter("All"),
    bg="#000000",
    fg="white",
    bd=0,
    width=15
)
all_button.pack(pady=5, padx=10)

filter_buttons["NES"] = nes_button
filter_buttons["SEGA"] = sega_button
filter_buttons["SNES"] = snes_button
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

# create window and keep a reference
inner_window = results_canvas.create_window((0, 0), window=results_inner_frame, anchor="nw")

# ensure inner frame always matches canvas width
def _on_canvas_configure(event):
    results_canvas.itemconfig(inner_window, width=event.width)

results_canvas.bind("<Configure>", _on_canvas_configure)

results_canvas.configure(yscrollcommand=scrollbar.set)

results_canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# ------------------ INIT ------------------

load_platforms()
load_genres()

root.mainloop()