import tkinter as tk
from tkinter import messagebox
import requests

# --- Configuration ---
API_KEY = '7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830'
BASE_URL = 'https://api.thegamesdb.net/'

def fetch_game_data():
    game_id = entry_id.get()
    if not game_id:
        messagebox.showwarning("Input Error", "Please enter a Game ID")
        return

    # API Endpoint: Get Game by ID
    url = f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}"

    try:
        response = requests.get(url)
        data = response.json()
        
        if 'data' in data and data['data']['games']:
            game_info = data['data']['games'][0]
            title = game_info.get('game_title', 'N/A')
            
            # Update GUI
            result_label.config(text=f"Game Title: {title}")
        else:
            result_label.config(text="Game not found.")
            
    except Exception as e:
        messagebox.showerror("Error", str(e))

# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Lookup")
root.geometry("300x200")

tk.Label(root, text="Enter Game ID:").pack(pady=5)
entry_id = tk.Entry(root)
entry_id.pack(pady=5)

btn_fetch = tk.Button(root, text="Fetch Game", command=fetch_game_data)
btn_fetch.pack(pady=10)

result_label = tk.Label(root, text="", wraplength=250)
result_label.pack(pady=10)

root.mainloop()
