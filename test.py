import tkinter as tk
from tkinter import ttk

# ----- STATIC DATA -----
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
        self.geometry("1100x750")
        self.create_widgets()
        self.populate_static_games()

    def create_widgets(self):
        # TOP BAR
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

        # MAIN SPLIT
        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # LEFT LIST
        left = ttk.Frame(main, width=400)
        main.add(left, weight=1)

        ttk.Label(left, text="Games").pack(anchor="w")

        self.results_list = tk.Listbox(left)
        self.results_list.pack(fill="both", expand=True)
        self.results_list.bind("<<ListboxSelect>>", self.on_select)

        # RIGHT PANEL
        right = ttk.Frame(main)
        main.add(right, weight=2)

        self.title_lbl = ttk.Label(right, font=("TkDefaultFont", 14, "bold"))
        self.title_lbl.pack(anchor="w", pady=(4,2))

        self.meta_lbl = ttk.Label(right, foreground="gray")
        self.meta_lbl.pack(anchor="w", pady=(0,6))

        self.back_btn = ttk.Button(right, text="Back", command=self.reset_detail)
        self.back_btn.pack(anchor="w")
        self.back_btn.pack_forget()

        # TABLE FRAME (white background)
        self.detail_frame = tk.Frame(right, bg="white", padx=10, pady=10, relief="groove", borderwidth=2)
        self.detail_frame.pack(fill="both", expand=True)

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

    # SEARCH (STATIC FILTER)
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
        self.back_btn.pack(anchor="w", pady=(0,4))
        self.show_table(g)

    # TABLE DISPLAY
    def show_table(self, d):
        for child in self.detail_frame.winfo_children():
            child.destroy()

        self.title_lbl.config(text=d["game_title"])

        meta = []
        if d.get("platform"): meta.append(d["platform"])
        if d.get("release_date"): meta.append(str(d["release_date"]))
        if d.get("players"): meta.append(f"Players: {d['players']}")
        self.meta_lbl.config(text=" • ".join(meta))

        fields = [
            ("Game ID ", d.get("id")), #(for coding and debug only remove or hide when project is done)
            ("Name", d.get("game_title")),
            ("Platform", d.get("platform")),
            ("Release Date", d.get("release_date")),
            ("Players", d.get("players")),
            ("Description", d.get("overview")),
            ("Images", ", ".join(d.get("images") or []) or "link.jpg")
        ]

        self.detail_frame.columnconfigure(0, minsize=250)
        self.detail_frame.columnconfigure(1, weight=1)

        for r, (label, value) in enumerate(fields):
            tk.Label(self.detail_frame, text=label, anchor="w", bg="white").grid(row=r, column=0, sticky="nw", padx=6, pady=6)
            tk.Label(self.detail_frame, text=str(value), anchor="w", wraplength=600, bg="white").grid(row=r, column=1, sticky="nw", padx=6, pady=6)

    def reset_detail(self):
        self.back_btn.pack_forget()
        self.title_lbl.config(text="")
        self.meta_lbl.config(text="")
        for child in self.detail_frame.winfo_children():
            child.destroy()

# RUN
if __name__ == "__main__":
    app = App()
    app.mainloop()