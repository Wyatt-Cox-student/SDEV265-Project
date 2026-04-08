import tkinter as tk
from tkinter import messagebox
import requests

# --- Configuration ---
API_KEY = '7a5185043b9c80de440a54ba097dd8d7977990b1be306a3e830'
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

def fetch_game_data_by_name():
    game_name = entry_name.get()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name")
        return

    url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={game_name}"

    try:
        response = requests.get(url)
        data = response.json()

        # Clear previous results
        for widget in results_inner_frame.winfo_children():
            widget.destroy()

        if 'data' in data and 'games' in data['data'] and data['data']['games']:
            games = data['data']['games']
            for game in games:
                game_id = game.get('id')
                title = game.get('game_title', 'N/A')
                btn = tk.Button(results_inner_frame, text=title, anchor="w",
                                command=lambda g_id=game_id: fetch_game_details(g_id))
                btn.pack(fill="x", pady=2)
            results_canvas.update_idletasks()
            results_canvas.config(scrollregion=results_canvas.bbox("all"))
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

            detail_text = f"Title: {title}\nPlatform: {platform_name}\nRelease Date: {release_date}\n\nOverview:\n{overview}"
            result_text.config(state="normal")
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, detail_text)
            result_text.config(state="disabled")
        else:
            result_text.config(state="normal")
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "Game details not found.")
            result_text.config(state="disabled")
            
    except Exception as e:
        messagebox.showerror("Error", str(e))


# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Game Browser")
root.geometry("900x600")

# Top search entry
top_frame = tk.Frame(root)
top_frame.pack(fill="x", pady=5, padx=10)

tk.Label(top_frame, text="Search:").pack(side="left")
entry_name = tk.Entry(top_frame, width=50)
entry_name.pack(side="left", padx=5)
btn_search = tk.Button(top_frame, text="Search", command=fetch_game_data_by_name)
btn_search.pack(side="left", padx=5)

# Main content frame: left results, right details
content_frame = tk.Frame(root)
content_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Left: Scrollable Frame for Search Results
results_frame = tk.Frame(content_frame, width=300)
results_frame.pack(side="left", fill="y", padx=(0,10), expand=False)

results_canvas = tk.Canvas(results_frame, width=300)
results_scrollbar = tk.Scrollbar(results_frame, orient="vertical", command=results_canvas.yview)
results_inner_frame = tk.Frame(results_canvas)

results_inner_frame.bind(
    "<Configure>",
    lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all"))
)

results_canvas.create_window((0,0), window=results_inner_frame, anchor="nw")
results_canvas.configure(yscrollcommand=results_scrollbar.set)

results_canvas.pack(side="left", fill="both", expand=True)
results_scrollbar.pack(side="right", fill="y")

# Right: Scrollable Text for Game Details
result_text_frame = tk.Frame(content_frame)
result_text_frame.pack(side="left", fill="both", expand=True)

result_text = tk.Text(result_text_frame, wrap="word", state="disabled")
result_text.pack(side="left", fill="both", expand=True)

result_scrollbar = tk.Scrollbar(result_text_frame, command=result_text.yview)
result_scrollbar.pack(side="right", fill="y")
result_text.config(yscrollcommand=result_scrollbar.set)

root.mainloop()