import tkinter as tk
from tkinter import ttk

# ----- STATIC DATA (YOUR SOURCE OF TRUTH) -----
STATIC_GAMES = [
    (47693, "Rayman", "SNES", 2017, "Adventure", "1", "Classic platformer.", []),
    (5835, "Shanghai II: Dragon's Eye", "SNES", 1992, "Puzzle", "1", "Tile-matching puzzle.", []),
    (53023, "San Goku Shi III", "SNES", 1993, "Strategy", "1-2", "Strategy game.", []),
    (134985, "The Legend of Zelda: Mirror of Worlds", "NES", 2025, "Adventure", "1", "Zelda-like adventure.", []),
    (134260, "Splatterworld", "NES", 1993, "Role-Playing", "1", "RPG.", []),
    (109954, "Snow Bros.", "NES", 1990, "Platform", "1-2", "Arcade platformer.", []),
    (124463, "Sonic 1 Remastered", "SEGA Genesis", 2007, "Platform", "1", "Remaster of Sonic 1.", []),
    (9414, "Addams Family Values", "SEGA Genesis", 1994, "Role-Playing", "1-4", "RPG in Addams Family world.", []),
    (4237, "Aero the Acro-Bat", "SEGA Genesis", 1993, "Platform", "1", "Platform action game.", [])
]

# ----- APP -----
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Classic Game Database")
        self.geometry("1000x700")
        self.create_widgets()
        self.populate_static_games()

    # UI
    def create_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Search:").pack(side="left")

        self.qvar = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.qvar, width=40)
        entry.pack(side="left", padx=6)

        entry.bind("<Return>", lambda e: self.search())
        entry.bind("<Escape>", lambda e: self.clear_search())

        ttk.Button(top, text="Search", command=self.search).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear_search).pack(side="left", padx=6)

        self.status = ttk.Label(top, text="", foreground="gray")
        self.status.pack(side="left", padx=10)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # LEFT
        left = ttk.Frame(main, width=400)
        main.add(left, weight=1)

        ttk.Label(left, text="Games").pack(anchor="w")

        self.results_list = tk.Listbox(left)
        self.results_list.pack(fill="both", expand=True)
        self.results_list.bind("<<ListboxSelect>>", self.on_select)

        # RIGHT
        right = ttk.Frame(main)
        main.add(right, weight=2)

        self.title_lbl = ttk.Label(right, font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w")

        self.meta_lbl = ttk.Label(right, foreground="gray")
        self.meta_lbl.pack(anchor="w")

        self.back_btn = ttk.Button(right, text="Back", command=self.reset_detail)
        self.back_btn.pack(anchor="w")
        self.back_btn.pack_forget()

        self.detail = tk.Text(right, height=20, wrap="word")
        self.detail.pack(fill="both", expand=True)

        self.results = []

    # LOAD STATIC
    def populate_static_games(self):
        self.results = []
        self.results_list.delete(0, "end")

        for g in STATIC_GAMES:
            gid, name, platform, year, genre, players, overview, images = g

            item = {
                "id": gid,
                "game_title": name,
                "platform": platform,
                "release_date": year,
                "genre": genre,
                "players": players,
                "overview": overview,
                "images": images
            }

            self.results.append(item)
            self.results_list.insert("end", f"{name} — {gid}")

    # SEARCH (STATIC FILTER ONLY)
    def search(self):
        q = self.qvar.get().strip().lower()

        if not q:
            self.populate_static_games()
            return

        filtered = []

        for g in STATIC_GAMES:
            gid, name, platform, year, genre, players, overview, images = g

            if q in name.lower():
                filtered.append({
                    "id": gid,
                    "game_title": name,
                    "platform": platform,
                    "release_date": year,
                    "genre": genre,
                    "players": players,
                    "overview": overview,
                    "images": images
                })

        self.results = filtered
        self.results_list.delete(0, "end")

        for g in filtered:
            self.results_list.insert("end", f"{g['game_title']} — {g['id']}")

        self.status.config(text=f"{len(filtered)} result(s)")

    def clear_search(self):
        self.qvar.set("")
        self.populate_static_games()
        self.status.config(text="")

    # SELECT
    def on_select(self, evt):
        sel = self.results_list.curselection()
        if not sel:
            return

        g = self.results[sel[0]]

        self.back_btn.pack(anchor="w")

        self.title_lbl.config(text=g["game_title"])
        self.meta_lbl.config(
            text=f"{g['platform']} • {g['release_date']} • Players: {g['players']}"
        )

        self.detail.delete("1.0", "end")
        self.detail.insert("1.0",
            f"ID: {g['id']}\n\n"
            f"Genre: {g['genre']}\n\n"
            f"{g['overview']}"
        )

    def reset_detail(self):
        self.back_btn.pack_forget()
        self.title_lbl.config(text="")
        self.meta_lbl.config(text="")
        self.detail.delete("1.0", "end")

# RUN
if __name__ == "__main__":
    app = App()
    app.mainloop()