
import tkinter as tk
from tkinter import messagebox
import requests

# --- Configuration ---
API_KEY = '7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e8'
BASE_URL = 'https://api.thegamesdb.net/'

# Cache platform ID -> name
platform_cache = {}

def get_platform_name(platform_id):
    if platform_id in platform_cache:
        return platform_cache[platform_id]

    url = f"{BASE_URL}v1/Platforms?apikey={API_KEY}"
    try:
        response = requests.get(url)
        data = response.json()
        if 'data' in data and 'platforms' in data['data']:
            for pid, pdata in data['data']['platforms'].items():
                platform_cache[int(pid)] = pdata.get('name', 'Unknown')
    except Exception as e:
        print("Error fetching platforms:", e)

    return platform_cache.get(platform_id, "Unknown")

def render_detail_in_panel(detail_text):
    # Clear results panel
    for widget in results_inner_frame.winfo_children():
        widget.destroy()

    # Back button
    back_btn = tk.Button(results_inner_frame, text="← Back to Results", command=fetch_game_data_by_name)
    back_btn.pack(anchor="w", pady=5)

    # Detail text
    detail_lbl = tk.Label(results_inner_frame, text=detail_text, justify="left", wraplength=280)
    detail_lbl.pack(fill="both", expand=True, padx=5, pady=5)

def build_result_row(game):
    game_id = game.get('id')
    title = game.get('game_title', 'N/A')
    release_date = game.get('release_date', 'Unknown')
    platform_id = game.get('platform')
    platform_name = get_platform_name(platform_id) if platform_id else "Unknown"

    row = tk.Frame(results_inner_frame, padx=4, pady=6)
    row.pack(fill="x", pady=2)

    title_lbl = tk.Label(
        row,
        text=title,
        anchor="w",
        fg="blue",
        cursor="hand2",
        font=("TkDefaultFont", 10, "underline")
    )
    title_lbl.pack(fill="x")

    meta_lbl = tk.Label(
        row,
        text=f"{platform_name} • {release_date}",
        anchor="w",
        fg="gray"
    )
    meta_lbl.pack(fill="x")

    def on_click(event=None, g_id=game_id):
        fetch_game_details(g_id)

    title_lbl.bind("<Button-1>", on_click)
    meta_lbl.bind("<Button-1>", on_click)

def fetch_game_data_by_name():
    game_name = entry_name.get().strip()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name")
        return

    url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={game_name}"

    try:
        response = requests.get(url)
        data = response.json()

        # Clear panel
        for widget in results_inner_frame.winfo_children():
            widget.destroy()

        if 'data' in data and 'games' in data['data'] and data['data']['games']:
            games = data['data']['games']

            for game in games:
                build_result_row(game)
        else:
            tk.Label(results_inner_frame, text="No games found.").pack()

    except Exception as e:
        messagebox.showerror("Error", str(e))

def fetch_game_details(game_id):
    url = f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}"

    try:
        response = requests.get(url)
        data = response.json()

        if 'data' in data and 'games' in data['data'] and data['data']['games']:
            game = data['data']['games'][0]

            title = game.get('game_title', 'N/A')
            overview = game.get('overview', 'No description available.')
            release_date = game.get('release_date', 'Unknown')

            platform_id = game.get('platform')
            platform_name = get_platform_name(platform_id) if platform_id else "Unknown"

            detail_text = (
                f"Title: {title}\n"
                f"Platform: {platform_name}\n"
                f"Release Date: {release_date}\n\n"
                f"Overview:\n{overview}"
            )

            render_detail_in_panel(detail_text)
        else:
            render_detail_in_panel("Game details not found.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

def clear_search():
    # Clear the search entry
    entry_name.delete(0, tk.END)

    # Clear the results panel
    for widget in results_inner_frame.winfo_children():
        widget.destroy()
# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Game Browser")
root.geometry("600x800")

# Top search
top_frame = tk.Frame(root)
top_frame.pack(fill="x", pady=5, padx=10)

tk.Label(top_frame, text="Search:").pack(side="left")
entry_name = tk.Entry(top_frame, width=30)
entry_name.pack(side="left", padx=5)

btn_search = tk.Button(top_frame, text="Search", command=fetch_game_data_by_name)
btn_search.pack(side="left", padx=5)

btn_clear = tk.Button(top_frame, text="Clear", command=clear_search)
btn_clear.pack(side="left", padx=5)

# Single content panel
results_frame = tk.Frame(root)
results_frame.pack(fill="both", expand=True, padx=10, pady=10)

results_canvas = tk.Canvas(results_frame)
results_scrollbar = tk.Scrollbar(results_frame, orient="vertical", command=results_canvas.yview)
results_inner_frame = tk.Frame(results_canvas)

results_inner_frame.bind(
    "<Configure>",
    lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all"))
)

results_canvas.create_window((0, 0), window=results_inner_frame, anchor="nw")
results_canvas.configure(yscrollcommand=results_scrollbar.set)

results_canvas.pack(side="left", fill="both", expand=True)
results_scrollbar.pack(side="right", fill="y")

root.mainloop()

