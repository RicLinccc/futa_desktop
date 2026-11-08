# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"E:\CppProject\futa_desktop\src\futa_pet.py")
src = p.read_text(encoding="utf-8")

NEW_VIEWFINDER = '''    def open_viewfinder(self) -> None:
        """取景框：中间透明看到实时桌面，拖动移动，拖四角自由改大小。"""
        self.hide_bubble()
        if getattr(self, "_viewfinder", None) is not None:
            try:
                self._viewfinder.destroy()
            except tk.TclError:
                pass
            self._viewfinder = None
        tpl = PHOTO_TEMPLATES["fuji"]
        card_w, card_h = tpl["canvas"]
        bl, bt, br, bb = tpl["border"]
        aspect = (card_w - bl - br) / (card_h - bt - bb)
        cap_w = 560
        cap_h = int(round(cap_w / aspect))
        border = 34
        bar = 56
        win_w = cap_w + border * 2
        win_h = bar + cap_h + border
        dark = "#1E1A1D"
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg=TRANSPARENT_COLOR)
        window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        canvas = tk.Canvas(window, bg=TRANSPARENT_COLOR, highlightthickness=0,
                           bd=0, width=win_w, height=win_h)
        canvas.pack()
        state = {"w": win_w, "h": win_h}

        def shoot():
            self.shoot_viewfinder(window, border, bar,
                                  max(80, state["w"] - border * 2),
                                  max(80, state["h"] - bar - border))

        def cancel():
            try:
                window.destroy()
            except tk.TclError:
                pass
            self._viewfinder = None

        title = tk.Label(canvas, text="取景框 · 拖边框移动 · 拖四角改大小", bg=dark,
                         fg="#F2E9EC", font=("Microsoft YaHei UI", 10, "bold"))
        hint = tk.Label(canvas, text="中间就是实时桌面", bg=dark, fg="#8C7B82",
                        font=("Microsoft YaHei UI", 9))
        title_item = canvas.create_window(36, 10, window=title, anchor="nw")
        hint_item = canvas.create_window(36, 32, window=hint, anchor="nw")
        shot_btn = tk.Button(canvas, text="快门", command=shoot, relief="flat", bd=0,
                             bg="#EA7BAC", fg="#FFFFFF", activebackground="#D46698",
                             activeforeground="#FFFFFF", padx=16, pady=3,
                             font=("Microsoft YaHei UI", 9, "bold"))
        cancel_btn = tk.Button(canvas, text="取消", command=cancel, relief="flat", bd=0,
                               bg="#3A3034", fg="#F2E9EC", activebackground="#4A3C42",
                               activeforeground="#FFFFFF", padx=10, pady=3,
                               font=("Microsoft YaHei UI", 9))
        shot_item = canvas.create_window(0, 0, window=shot_btn, anchor="center")
        cancel_item = canvas.create_window(0, 0, window=cancel_btn, anchor="center")
        strips = [canvas.create_rectangle(0, 0, 1, 1, fill=dark, outline="") for _ in range(4)]
        handles = {}
        for name, (hx, hy) in {"nw": (8, 8), "ne": (win_w - 8, 8),
                               "sw": (8, win_h - 8), "se": (win_w - 8, win_h - 8)}.items():
            item = canvas.create_rectangle(hx - 9, hy - 9, hx + 9, hy + 9,
                                           fill="#EA7BAC", outline="#FFFFFF", width=2)
            handles[name] = item

        move = {"dx": 0, "dy": 0}
        def start_move(event):
            move["dx"] = event.x_root - window.winfo_x()
            move["dy"] = event.y_root - window.winfo_y()
        def do_move(event):
            window.geometry(f"+{event.x_root - move['dx']}+{event.y_root - move['dy']}")

        resize = {"left": 0, "top": 0, "w": 0, "h": 0, "px": 0, "py": 0}
        def make_resize_start(corner):
            def handler(event):
                resize.update(left=window.winfo_x(), top=window.winfo_y(),
                              w=state["w"], h=state["h"],
                              px=event.x_root, py=event.y_root)
            return handler
        def make_resize_drag(corner):
            def handler(event):
                dx = event.x_root - resize["px"]
                dy = event.y_root - resize["py"]
                x, y = resize["left"], resize["top"]
                w, h = resize["w"], resize["h"]
                if "e" in corner:
                    w = w + dx
                if "s" in corner:
                    h = h + dy
                if "w" in corner:
                    w = w - dx
                if "n" in corner:
                    h = h - dy
                left, top, right, bottom = self.work_area()
                w = max(320, min(w, right - left))
                h = max(300, min(h, bottom - top))
                if "w" in corner:
                    x = resize["left"] + resize["w"] - w
                if "n" in corner:
                    y = resize["top"] + resize["h"] - h
                x = max(left, min(x, right - w))
                y = max(top, min(y, bottom - h))
                state["w"], state["h"] = w, h
                window.geometry(f"{w}x{h}+{x}+{y}")
                draw()
            return handler

        for item in strips:
            canvas.tag_bind(item, "<ButtonPress-1>", start_move)
            canvas.tag_bind(item, "<B1-Motion>", do_move)
        cursors = {"nw": "size_nw_se", "se": "size_nw_se",
                   "ne": "size_ne_sw", "sw": "size_ne_sw"}
        for name, item in handles.items():
            canvas.tag_bind(item, "<ButtonPress-1>", make_resize_start(name))
            canvas.tag_bind(item, "<B1-Motion>", make_resize_drag(name))
            canvas.tag_bind(item, "<Enter>", lambda _e, c=cursors[name]: canvas.configure(cursor=c))
            canvas.tag_bind(item, "<Leave>", lambda _e: canvas.configure(cursor=""))

        def draw():
            w, h = state["w"], state["h"]
            canvas.configure(width=w, height=h)
            canvas.coords(strips[0], 0, 0, w, bar)
            canvas.coords(strips[1], 0, bar, border, h - border)
            canvas.coords(strips[2], w - border, bar, w, h - border)
            canvas.coords(strips[3], 0, h - border, w, h)
            for name, (hx, hy) in {"nw": (8, 8), "ne": (w - 8, 8),
                                   "sw": (8, h - 8), "se": (w - 8, h - 8)}.items():
                canvas.coords(handles[name], hx - 9, hy - 9, hx + 9, hy + 9)
            canvas.coords(title_item, 36, 10)
            canvas.coords(hint_item, 36, 32)
            canvas.coords(shot_item, w - 84, 28)
            canvas.coords(cancel_item, w - 168, 28)

        draw()
        self._viewfinder = window
        window.update_idletasks()
        left, top, right, bottom = self.work_area()
        x = left + max(0, (right - left - win_w) // 2)
        y = top + max(0, (bottom - top - win_h) // 2)
        window.geometry(f"{win_w}x{win_h}+{x}+{y}")

'''

start = src.index("    def open_viewfinder(self) -> None:")
end = src.index("    def shoot_viewfinder(self, window", start)
src = src[:start] + NEW_VIEWFINDER + src[end:]

def rep(old, new):
    global src
    if old not in src:
        raise SystemExit("NOT FOUND: " + old[:90])
    src = src.replace(old, new, 1)

# caption is opt-in, off by default
rep('''    def build_polaroid(self, scene, template_key: str = "fuji", sprite=None):''',
    '''    def build_polaroid(self, scene, template_key: str = "fuji", sprite=None, caption: bool = False):''')
rep('''        if tpl.get("caption") and bb >= 70:''',
    '''        if caption and tpl.get("caption") and bb >= 70:''')

# preview: add caption checkbox, pass through
rep('''        action_row = tk.Frame(window, bg="#1E1A1D")''',
'''        option_row = tk.Frame(window, bg="#1E1A1D")
        option_row.pack(fill="x", padx=16)
        caption_var = tk.BooleanVar(value=False)
        tk.Checkbutton(option_row, text="写日期/文字", variable=caption_var,
                       command=lambda: render(), bg="#1E1A1D", fg="#F2E9EC",
                       selectcolor="#3A3034", activebackground="#1E1A1D",
                       activeforeground="#FFFFFF", highlightthickness=0,
                       bd=0, font=("Microsoft YaHei UI", 9)).pack(side="left")
        action_row = tk.Frame(window, bg="#1E1A1D")''')
rep('''            card = self.build_polaroid(scene, key, sprite)''',
    '''            card = self.build_polaroid(scene, key, sprite, caption_var.get())''')
rep('''            card = self.build_polaroid(scene, choice.get(), sprite)''',
    '''            card = self.build_polaroid(scene, choice.get(), sprite, caption_var.get())''')

p.write_text(src, encoding="utf-8")
print("patched", len(src))
