import tkinter as tk
from tkinter import messagebox
import requests

# --- Configuration ---
API_KEY = '7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830'
BASE_URL = 'https://api.thegamesdb.net/'

def fetch_game_data():
    game_name = entry_name.get()
    if not game_name:
        messagebox.showwarning("Input Error", "Please enter a Game Name")
        return

    # API Endpoint: Search Games by Name
    url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={game_name}"

    try:
        response = requests.get(url)
        data = response.json()
        
        if 'data' in data and 'games' in data['data'] and data['data']['games']:
            games = data['data']['games']
            titles = [game.get('game_title', 'N/A') for game in games]
            result_text = "Search Results:\n" + "\n".join(titles)
            
            result_label.config(text=result_text)
        else:
            result_label.config(text="No games found.")
            
    except Exception as e:
        messagebox.showerror("Error", str(e))

# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Name Lookup")
root.geometry("400x300")

tk.Label(root, text="Enter Game Name:").pack(pady=5)
entry_name = tk.Entry(root)
entry_name.pack(pady=5)

btn_fetch = tk.Button(root, text="Search Game", command=fetch_game_data)
btn_fetch.pack(pady=10)

result_label = tk.Label(root, text="", wraplength=350, justify="left")
result_label.pack(pady=10)

root.mainloop()