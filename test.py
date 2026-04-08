import tkinter as tk
from tkinter import messagebox
import requests

API_KEY = '7a5185043b9c80de440a54ba097dd8d7977990b1be306a3e8'
BASE_URL = 'https://api.thegamesdb.net/'

platform_cache = {}
last_search_results = []
is_showing_detail = False  # track if panel is showing detail

def get_platform_name(platform_id):
    if platform_id in platform_cache:
        return platform_cache[platform_id]
    try:
        response = requests.get(f"{BASE_URL}v1/Platforms?apikey={API_KEY}")
        data = response.json()
        for pid, pdata in data.get('data', {}).get('platforms', {}).items():
            platform_cache[int(pid)] = pdata.get('name', 'Unknown')
    except Exception as e:
        print("Error fetching platforms:", e)
    return platform_cache.get(platform_id, "Unknown")

def build_result_row(game):
    game_id = game.get('id')
    title = game.get('game_title', 'N/A')
    release_date = game.get('release_date', 'Unknown')
    platform_name = get_platform_name(game.get('platform')) if game.get('platform') else "Unknown"

    row = tk.Frame(results_inner_frame, padx=4, pady=6)
    row.pack(fill="x", pady=2)

    title_lbl = tk.Label(row, text=title, fg="blue", cursor="hand2", font=("TkDefaultFont", 10, "underline"))
    title_lbl.pack(fill="x")

    meta_lbl = tk.Label(row, text=f"{platform_name} • {release_date}", fg="gray")
    meta_lbl.pack(fill="x")

    def on_click(event=None, g_id=game_id):
        fetch_game_details(g_id)

    title_lbl.bind("<Button-1>", on_click)
    meta_lbl.bind("<Button-1>", on_click)

def fetch_game_data_by_name():
    global last_search_results, is_showing_detail
    name = entry_name.get().strip()
    if not name:
        messagebox.showwarning("Input Error", "Enter a game name")
        return

    try:
        response = requests.get(f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={name}")
        data = response.json()
        games = data.get('data', {}).get('games', [])
        last_search_results = games
        is_showing_detail = False

        for widget in results_inner_frame.winfo_children():
            widget.destroy()

        if games:
            for game in games:
                build_result_row(game)
        else:
            tk.Label(results_inner_frame, text="No games found.").pack()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def fetch_game_details(game_id):
    global is_showing_detail
    is_showing_detail = True

    for widget in results_inner_frame.winfo_children():
        widget.destroy()

    try:
        response = requests.get(f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}")
        data = response.json()
        games = data.get('data', {}).get('games', [])
        if not games:
            tk.Label(results_inner_frame, text="Game details not found.").pack()
            return
        game = games[0]

        title = game.get('game_title', 'N/A')
        overview = game.get('overview', 'No description available.')
        release_date = game.get('release_date', 'Unknown')
        platform_name = get_platform_name(game.get('platform')) if game.get('platform') else "Unknown"

        back_btn = tk.Button(results_inner_frame, text="← Back", command=show_previous_results)
        back_btn.pack(anchor="w", pady=5)

        detail_text = (
            f"Title: {title}\n"
            f"Platform: {platform_name}\n"
            f"Release Date: {release_date}\n\n"
            f"Overview:\n{overview}"
        )
        tk.Label(results_inner_frame, text=detail_text, justify="left", wraplength=500).pack(fill="both", expand=True, padx=5, pady=5)
    except Exception as e:
        messagebox.showerror("Error", str(e))

def show_previous_results():
    global is_showing_detail
    is_showing_detail = False

    for widget in results_inner_frame.winfo_children():
        widget.destroy()
    for game in last_search_results:
        build_result_row(game)

def clear_search():
    entry_name.delete(0, tk.END)
    if not is_showing_detail:
        # only clear results if showing search results
        for widget in results_inner_frame.winfo_children():
            widget.destroy()

# --- GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Browser")
root.geometry("700x800")

top_frame = tk.Frame(root)
top_frame.pack(fill="x", pady=5, padx=10)

tk.Label(top_frame, text="Search:").pack(side="left")
entry_name = tk.Entry(top_frame, width=30)
entry_name.pack(side="left", padx=5)

tk.Button(top_frame, text="Search", command=fetch_game_data_by_name).pack(side="left", padx=5)
tk.Button(top_frame, text="Clear", command=clear_search).pack(side="left", padx=5)

# Single clean scrollable panel (no outline)
results_canvas = tk.Canvas(root)
results_scrollbar = tk.Scrollbar(root, orient="vertical", command=results_canvas.yview)
results_inner_frame = tk.Frame(results_canvas)

results_inner_frame.bind("<Configure>", lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all")))
results_canvas.create_window((0,0), window=results_inner_frame, anchor="nw")
results_canvas.configure(yscrollcommand=results_scrollbar.set)

results_canvas.pack(side="left", fill="both", expand=True)
results_scrollbar.pack(side="right", fill="y")

root.mainloop()