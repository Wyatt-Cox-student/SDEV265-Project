import tkinter as tk  # Import tkinter for GUI
from tkinter import messagebox  # For pop-up messages
import requests  # For HTTP API calls

# --- API Configuration ---
API_KEY = '7a5185043b9c80de440a54ba097dd8a107de762bdd7d7977990b1be306a3e830'  # Your TheGamesDB API key
BASE_URL = 'https://api.thegamesdb.net/'  # Base URL for API requests

# --- Global Caches and State ---
platform_cache = {}  # Cache to store platform id → name mapping
genre_cache = {}  # Cache to store genre id → name mapping
last_search_results = []  # Stores last search results for back navigation
is_showing_detail = False  # Flag to track if detail view is shown

# --- Load Platforms from API ---
def load_platforms():
    global platform_cache
    try:
        resp = requests.get(f"{BASE_URL}v1/Platforms?apikey={API_KEY}")  # Get all platforms
        data = resp.json()
        for pid, pdata in data.get("data", {}).get("platforms", {}).items():
            platform_cache[int(pid)] = pdata.get("name", "Unknown")  # Store id → name
    except Exception as e:
        print("Error loading platforms:", e)  # Handle errors gracefully

# Helper to get platform name by id
def get_platform_name(platform_id):
    return platform_cache.get(platform_id, "Unknown")  # Return "Unknown" if not found

# --- Load Genres from API ---
def load_genres():
    global genre_cache
    try:
        resp = requests.get(f"{BASE_URL}v1/Genres?apikey={API_KEY}")  # Get all genres
        data = resp.json()
        for gid, gdata in data.get("data", {}).get("genres", {}).items():
            genre_cache[int(gid)] = gdata.get("name", "Unknown")  # Store id → name
    except Exception as e:
        print("Error loading genres:", e)

# Helper to convert list of genre IDs to readable string
def get_genres_text(raw):
    if not raw:
        return "Unknown"
    if isinstance(raw, list):
        names = []
        for g in raw:
            try:
                gid = int(g)
                names.append(genre_cache.get(gid, f"Unknown({gid})"))
            except:
                names.append(str(g))
        return ", ".join(names) if names else "Unknown"
    return str(raw)

# --- Build a search result row in the GUI ---
def build_result_row(game):
    game_id = game.get("id")  # Unique game ID
    title = game.get("game_title", "N/A")  # Game title
    release_date = game.get("release_date", "Unknown")  # Release date
    platform_name = get_platform_name(game.get("platform")) if game.get("platform") else "Unknown"

    # Create a frame for each game row
    row = tk.Frame(results_inner_frame, padx=4, pady=6)
    row.pack(fill="x", pady=2)

    # Game title label (clickable)
    title_lbl = tk.Label(row, text=title, fg="blue", cursor="hand2",
                         font=("TkDefaultFont", 10, "underline"))
    title_lbl.pack(fill="x")

    # Game metadata (platform and release date)
    meta_lbl = tk.Label(row, text=f"{platform_name} • {release_date}", fg="gray")
    meta_lbl.pack(fill="x")

    # Click event to show game details
    def on_click(event=None, g_id=game_id):
        fetch_game_details(g_id)

    title_lbl.bind("<Button-1>", on_click)  # Bind click
    meta_lbl.bind("<Button-1>", on_click)

# --- Fetch Games by Name ---
def fetch_game_data_by_name():
    global last_search_results, is_showing_detail
    name = entry_name.get().strip()  # Get input from user
    if not name:
        messagebox.showwarning("Input Error", "Enter a game name")
        return
    try:
        url = f"{BASE_URL}v1/Games/ByGameName?apikey={API_KEY}&name={name}"
        resp = requests.get(url)
        data = resp.json()
        games = data.get("data", {}).get("games", [])
        last_search_results = games  # Save results for back button
        is_showing_detail = False

        # Clear previous results
        for widget in results_inner_frame.winfo_children():
            widget.destroy()

        # Display results or "No games found"
        if games:
            for game in games:
                build_result_row(game)
        else:
            tk.Label(results_inner_frame, text="No games found.").pack()
    except Exception as e:
        messagebox.showerror("Error", str(e))

# --- Fetch Game Details ---
def fetch_game_details(game_id):
    global is_showing_detail
    is_showing_detail = True
    # Clear previous search results
    for widget in results_inner_frame.winfo_children():
        widget.destroy()
    try:
        url = f"{BASE_URL}v1/Games/ByGameID?apikey={API_KEY}&id={game_id}&fields=overview,players,genres,release_date,platform,game_title"
        resp = requests.get(url)
        data = resp.json()
        games = data.get("data", {}).get("games", [])
        if not games:
            tk.Label(results_inner_frame, text="Game details not found.").pack()
            return
        game = games[0]

        # Extract detailed fields
        name = game.get("game_title", "Unknown")
        overview = game.get("overview") or "No description available."
        players = game.get("players") or "Unknown"
        release_date = game.get("release_date") or "Unknown"
        platform_name = get_platform_name(game.get("platform")) if game.get("platform") else "Unknown"
        genres_raw = game.get("genres", [])
        genres = get_genres_text(genres_raw)

        # Back button
        back_btn = tk.Button(results_inner_frame, text="← Back", command=show_previous_results)
        back_btn.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)

        # Display fields in grid
        fields = [
            ("Name", name),
            ("Platform", platform_name),
            ("Genre", genres),
            ("Release Date", release_date),
            ("Players", players),
            ("Description", overview)
        ]

        for i, (label_text, value_text) in enumerate(fields, start=1):
            tk.Label(results_inner_frame, text=f"{label_text}:", font=("TkDefaultFont", 10, "bold"),
                     anchor="w").grid(row=i, column=0, sticky="w", padx=5, pady=2)
            tk.Label(results_inner_frame, text=value_text, wraplength=500, justify="left",
                     anchor="w").grid(row=i, column=1, sticky="w", padx=5, pady=2)
    except Exception as e:
        messagebox.showerror("Error", str(e))

# --- Show Previous Search Results ---
def show_previous_results():
    global is_showing_detail
    is_showing_detail = False
    # Clear detail view
    for widget in results_inner_frame.winfo_children():
        widget.destroy()
    # Rebuild previous results
    for game in last_search_results:
        build_result_row(game)

# --- Clear Search Input ---
def clear_search():
    entry_name.delete(0, tk.END)  # Clear input field
    if not is_showing_detail:
        for widget in results_inner_frame.winfo_children():
            widget.destroy()  # Clear results if not in detail view

# --- GUI Setup ---
root = tk.Tk()
root.title("TheGamesDB Browser")  # Window title
root.geometry("700x800")  # Window size

# Top search frame
top_frame = tk.Frame(root)
top_frame.pack(fill="x", pady=5, padx=10)
tk.Label(top_frame, text="Search:").pack(side="left")
entry_name = tk.Entry(top_frame, width=30)
entry_name.pack(side="left", padx=5)
tk.Button(top_frame, text="Search", command=fetch_game_data_by_name).pack(side="left", padx=5)
tk.Button(top_frame, text="Clear", command=clear_search).pack(side="left", padx=5)

# Scrollable results frame
results_canvas = tk.Canvas(root)
results_scrollbar = tk.Scrollbar(root, orient="vertical", command=results_canvas.yview)
results_inner_frame = tk.Frame(results_canvas)
results_inner_frame.bind("<Configure>", lambda e: results_canvas.configure(scrollregion=results_canvas.bbox("all")))
results_canvas.create_window((0,0), window=results_inner_frame, anchor="nw")
results_canvas.configure(yscrollcommand=results_scrollbar.set)
results_canvas.pack(side="left", fill="both", expand=True)
results_scrollbar.pack(side="right", fill="y")

# --- Load caches at startup ---
load_platforms()
load_genres()

# Start GUI main loop
root.mainloop()