import json
import math
import time
import os
import random
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
from ctypes import wintypes
import winreg
import subprocess
from pathlib import Path

from PIL import Image, ImageTk, ImageDraw, ImageChops


APP_NAME = "Futa Desktop Pet"
TRANSPARENT_COLOR = "#010203"
FRAME_COUNT = 60
TARGET_FPS = 60
SAYINGS = (
    "比我萌的没我坏\n比我坏的不存在~",
    "就把我的吉他带走吧~\n就把我的歌也带走吧~",
)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent / "assets"))
    return base / name


def config_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FutaDesktopPet"
    root.mkdir(parents=True, exist_ok=True)
    return root / "settings.json"


class FutaPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.precise_timer = ctypes.windll.winmm.timeBeginPeriod(1) == 0
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)

        self.base_image = Image.open(resource_path("futa-subject.png")).convert("RGBA")
        self.facing_right = False
        self.prepare_wings()
        self.render_cache = {}
        self.display_image = None
        self.size = 300
        self.always_on_top = tk.BooleanVar(value=True)
        self.paused = tk.BooleanVar(value=True)
        self.moving = tk.BooleanVar(value=False)
        self.cross_screen = tk.BooleanVar(value=True)
        self.autostart = tk.BooleanVar(value=self.autostart_enabled())
        self.settings_window = None
        self.resize_timer = None
        self.roam_target = None
        self.roam_position = None
        self.flight_velocity = (0.0, 0.0)
        self.flight_phase = 0.0
        self.flight_heading = random.uniform(-math.pi, math.pi)
        self.flight_turn_ticks = 0
        self.biting = False
        self.bite_job = None
        self.drag_origin = None
        self.pending_drag_size = None
        self.right_press = None
        self.left_press = None
        self.did_drag = False
        self.frame_index = 0
        self.frames = []
        self.right_frames = []
        self.animation_phase = 0.0
        self.bubble = None
        self.bubble_timer = None
        self.pet_height = 0

        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size + 80,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        # Frames already contain their own centering padding. Pin the entire
        # frame to the canvas origin so resizing cannot move it outside it.
        self.sprite = self.canvas.create_image(0, 0, anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self.start_left_action)
        self.canvas.bind("<B1-Motion>", self.left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.finish_left_action)
        self.canvas.bind("<ButtonPress-3>", self.start_resize)
        self.canvas.bind("<B3-Motion>", self.resize_by_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.finish_resize)
        self.canvas.bind("<Double-Button-1>", self.double_click)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.bind("<Configure>", self.on_configure)
        self.load_settings()
        self.root.update_idletasks()
        self.build_frames()
        self.last_tick = time.perf_counter()
        self.next_tick = self.last_tick
        self.animate()

    def prepare_wings(self):
        # The small white wings behind the shoulders are independent layers.
        self.wings = []
        mask = Image.new("L", self.base_image.size)
        # Trace only the exposed white feathers, staying outside the arm seam.
        # The foreground arm pixels remain untouched and cover the wing roots.
        for polygon in ([(0,211),(30,211),(43,220),(19,237),(0,242)],
                        [(244,218),(270,201),(289,201),(289,246),(276,242)]):
            part = Image.new("L", self.base_image.size)
            ImageDraw.Draw(part).polygon(polygon, fill=255)
            layer = self.base_image.copy()
            layer.putalpha(ImageChops.multiply(layer.getchannel("A"), part))
            box = layer.getbbox()
            self.wings.append((box, layer.crop(box)))
            mask = ImageChops.lighter(mask, part)
        self.wing_mask = mask
        self.wingless = self.base_image.copy()
        self.wingless.putalpha(ImageChops.subtract(self.base_image.getchannel("A"), mask))
        self.source_frames = []
        for index in range(FRAME_COUNT):
            frame = Image.new("RGBA", self.base_image.size)
            flap = 0.58 + 0.42 * math.cos(2 * math.pi * index / FRAME_COUNT * 4)
            for box, wing in self.wings:
                height = max(3, round(wing.height * (0.65 + 0.35 * flap)))
                warped = wing.resize((wing.width, height), Image.Resampling.BICUBIC)
                frame.alpha_composite(warped, (box[0], box[3]-height))
            frame.alpha_composite(self.wingless)
            # Deform the whole lower section with a fixed hip seam. No cutout
            # holes or duplicate stationary legs remain beneath the animation.
            hip = 350
            lower = frame.crop((0, hip, frame.width, frame.height))
            height = round(lower.height * (0.78 + 0.025 * math.sin(2*math.pi*index/FRAME_COUNT*2)))
            lower = lower.resize((lower.width, height), Image.Resampling.BICUBIC)
            lean = 0.30 + 0.035 * math.sin(2*math.pi*index/FRAME_COUNT*2)
            lower = lower.transform(lower.size, Image.Transform.AFFINE,
                                    (1, -lean, 0, 0, 1, 0), Image.Resampling.BICUBIC)
            frame.paste((0,0,0,0), (0,hip,frame.width,frame.height))
            frame.alpha_composite(lower, (0,hip))
            self.source_frames.append(frame)

    def render_frame(self):
        index = self.frame_index if self.moving.get() and not self.biting else -1
        key = (index, self.facing_right)
        if key not in self.render_cache:
            source = self.source_frames[index] if index >= 0 else self.base_image
            phase = 2 * math.pi * self.frame_index / FRAME_COUNT
            scale = 0.9925 + 0.0075 * math.sin(phase) if index >= 0 else 1.0
            width = max(1, round(self.size * scale))
            height = max(1, round(source.height * width / source.width))
            quality = Image.Resampling.BILINEAR if self.right_press else Image.Resampling.LANCZOS
            resized = source.resize((width, height), quality)
            frame = Image.new("RGBA", (self.size, self.pet_height), (1,2,3,255))
            frame.alpha_composite(resized, ((self.size-width)//2, 5))
            if self.facing_right:
                frame = frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            # Bounded lazy cache: resizing creates only the frame on screen.
            if len(self.render_cache) >= 24:
                self.render_cache.pop(next(iter(self.render_cache)))
            self.render_cache[key] = ImageTk.PhotoImage(frame)
        self.display_image = self.render_cache[key]
        self.canvas.itemconfigure(self.sprite, image=self.display_image)

    def build_frames(self) -> None:
        left, top, right, bottom = self.work_area()
        limit = min(700, right-left, int((bottom-top-16)*self.base_image.width/self.base_image.height))
        self.size = max(min(140,limit), min(self.size,limit))
        self.render_cache.clear()
        self.pet_height = int(self.base_image.height*self.size/self.base_image.width)+16
        self.canvas.configure(width=self.size, height=self.pet_height)
        x = max(left,min(self.root.winfo_x(),right-self.size))
        y = max(top,min(self.root.winfo_y(),bottom-self.pet_height))
        self.root.geometry(f"{self.size}x{self.pet_height}+{x}+{y}")
        self.render_frame()

    def monitor_areas(self):
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        user32 = ctypes.windll.user32
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE,
                                          wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        areas = []
        def collect(handle, dc, rect, data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                r = info.rcWork
                areas.append((r.left, r.top, r.right, r.bottom))
            return True
        user32.EnumDisplayMonitors(None, None, callback_type(collect), 0)
        return areas or [(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())]

    def work_area(self):
        x = self.root.winfo_x() + self.size // 2
        y = self.root.winfo_y() + self.pet_height // 2
        return min(self.monitor_areas(), key=lambda a:
                   max(a[0]-x, 0, x-a[2])**2 + max(a[1]-y, 0, y-a[3])**2)

    @staticmethod
    def covered(rect, areas):
        # Subtract each monitor from the pet rectangle: no remaining pieces
        # means the pet is visible even while straddling a shared screen edge.
        pieces = [rect]
        for l, t, r, b in areas:
            remaining = []
            for x, y, right, bottom in pieces:
                il, it, ir, ib = max(x,l), max(y,t), min(right,r), min(bottom,b)
                if il >= ir or it >= ib:
                    remaining.append((x,y,right,bottom))
                else:
                    remaining.extend(q for q in ((x,y,right,it), (x,ib,right,bottom),
                        (x,it,il,ib), (ir,it,right,ib)) if q[0]<q[2] and q[1]<q[3])
            pieces = remaining
        return not pieces

    def flight_step(self, x, y, areas, dt=1 / TARGET_FPS):
        """Steer with inertia, probing the desktop union before each move."""
        step = dt / 0.033
        self.flight_phase += dt
        self.flight_turn_ticks -= step
        if self.flight_turn_ticks <= 0:
            self.flight_heading += random.uniform(-1.3, 1.3)
            self.flight_turn_ticks = random.randint(45, 110)
        angle = self.flight_heading + 0.28 * math.sin(self.flight_phase * 1.8)
        speed = 3.4 + 0.7 * math.sin(self.flight_phase * 0.7)
        def fits(px, py):
            px, py = round(px), round(py)
            return self.covered((px, py, px+self.size, py+self.pet_height), areas)
        # Look ahead at several distances, including seams and desktop gaps.
        def clear(direction):
            return all(fits(x+math.cos(direction)*d, y+math.sin(direction)*d)
                       for d in (8, 24, 48, 80))
        if not clear(angle):
            candidates = [angle + n*math.pi/12 for n in range(-12,13)]
            safe = [a for a in candidates if clear(a)]
            if safe:
                angle = min(safe, key=lambda a: abs(a-angle))
                self.flight_heading = angle
        vx,vy = self.flight_velocity
        blend = 1 - 0.91 ** step
        vx += (math.cos(angle)*speed-vx)*blend
        vy += (math.sin(angle)*speed-vy)*blend
        vx *= step
        vy *= step
        if not fits(x+vx,y+vy):
            # A tight corner may not leave enough room to complete a turn.
            # Stop the blocked component; never jump across an unseen region.
            if fits(x+vx,y):
                vy = 0.0
            elif fits(x,y+vy):
                vx = 0.0
            else:
                vx = vy = 0.0
            self.flight_heading += math.pi/2
            self.flight_turn_ticks = 0
        self.flight_velocity = (vx / step, vy / step) if step > 0 else (0.0, 0.0)
        if vx > 0.15:
            self.facing_right = True
        elif vx < -0.15:
            self.facing_right = False
        return x+vx, y+vy

    def roam(self, dt=1 / TARGET_FPS):
        busy = self.biting or self.drag_origin or self.right_press or self.settings_window is not None
        if self.moving.get() and not busy:
            areas = self.monitor_areas() if self.cross_screen.get() else [self.work_area()]
            if self.roam_target is None:
                self.roam_position = (self.root.winfo_x(), self.root.winfo_y())
                self.flight_velocity = (0.0, 0.0)
                self.roam_target = True
            x,y = self.roam_position
            if not self.covered((round(x),round(y),round(x)+self.size,round(y)+self.pet_height), areas):
                self.move_inside(round(x),round(y),areas)
                self.roam_target = None
            else:
                self.roam_position = self.flight_step(x,y,areas,dt)
                x,y = self.roam_position
                self.root.geometry(f"+{round(x)}+{round(y)}")
        else:
            self.roam_target = None

    def animate(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self.last_tick))
        self.last_tick = now
        if self.pending_drag_size is not None:
            size = self.pending_drag_size
            self.pending_drag_size = None
            self.set_size(size, save=False)
        self.roam(dt)
        if not self.paused.get():
            self.animation_phase = (self.animation_phase + dt / 1.65) % 1.0
            self.frame_index = int(self.animation_phase * FRAME_COUNT)
        self.render_frame()
        self.next_tick += 1 / TARGET_FPS
        finished = time.perf_counter()
        if self.next_tick < finished:
            self.next_tick = finished + 1 / TARGET_FPS
        self.root.after(max(1, round((self.next_tick - finished) * 1000)), self.animate)

    def start_left_action(self, event: tk.Event) -> None:
        if self.biting:
            return
        self.left_press = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.did_drag = False
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def left_drag(self, event: tk.Event) -> None:
        if self.drag_origin:
            if abs(event.x_root - self.left_press[0]) > 4 or abs(event.y_root - self.left_press[1]) > 4:
                self.did_drag = True
            x = event.x_root - self.drag_origin[0]
            y = event.y_root - self.drag_origin[1]
            self.move_inside(x, y)

    def finish_left_action(self, _event: tk.Event) -> None:
        self.drag_origin = None
        if self.left_press and not self.did_drag:
            self.show_dialog()
        self.left_press = None
        self.save_settings()

    def start_resize(self, event: tk.Event) -> None:
        if self.biting:
            return
        self.right_press = (event.x_root, event.y_root, self.size)

    def resize_by_right_drag(self, event: tk.Event) -> None:
        if self.right_press:
            dx = event.x_root - self.right_press[0]
            dy = event.y_root - self.right_press[1]
            new_size = max(140, min(700, self.right_press[2] + int((dx + dy) / 2)))
            if new_size != self.size:
                self.pending_drag_size = new_size

    def finish_resize(self, event: tk.Event) -> None:
        if self.right_press:
            moved = abs(event.x_root - self.right_press[0]) > 4 or abs(event.y_root - self.right_press[1]) > 4
            self.right_press = None
            if self.pending_drag_size is not None:
                size = self.pending_drag_size
                self.pending_drag_size = None
                self.set_size(size, save=False)
            self.render_cache.clear()
            if moved:
                self.save_settings()
            else:
                self.show_settings()

    def double_click(self, event: tk.Event) -> None:
        self.drag_origin = None
        self.left_press = None
        self.hide_bubble()
        if self.biting:
            return
        # Only the torso triggers the playful attack.
        if 0.18*self.size <= event.x <= 0.82*self.size and 0.45*self.pet_height <= event.y <= 0.83*self.pet_height:
            if random.random() < 0.5:
                self.start_bite()

    @staticmethod
    def cursor_position():
        point = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    @staticmethod
    def set_cursor_position(x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def mouth_offset(self):
        # Original mouth center: (123, 188) on the 290 x 436 artwork.
        x = 167 if self.facing_right else 123
        return round(x*self.size/290), round(5+188*self.size/290)

    def start_bite(self):
        self.biting = True
        self.roam_target = None
        self.flight_velocity = (0.0, 0.0)
        self.hide_bubble()
        self.bite_area = self.work_area()
        self.bite_origin = (self.root.winfo_x(), self.root.winfo_y())
        self.bite_return_position = self.bite_origin
        self.bite_started = time.perf_counter()
        self.bite_phase = "chase"
        self.bite_job = self.root.after(16, self.bite_approach)

    def bite_approach(self):
        self.bite_job = None
        if not self.biting:
            return
        # Escape releases the cursor immediately, even while another app has focus.
        if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
            self.bite_phase = "return"
            self.bite_started = time.perf_counter()
        left,top,right,bottom = self.bite_area
        mx,my = self.mouth_offset()
        elapsed = time.perf_counter() - self.bite_started
        if self.bite_phase == "chase":
            # Read the real cursor every tick. The cursor is never moved by
            # the pet, so the user has a chance to run away.
            cx, cy = self.cursor_position()
            target = (cx - mx, cy - my)
            x, y = self.root.winfo_x(), self.root.winfo_y()
            dx, dy = target[0] - x, target[1] - y
            distance = math.hypot(dx, dy)
            if distance <= max(18, self.size * 0.08):
                self.bite_phase = "carry"
                self.bite_origin = (x, y)
                self.bite_target = random.choice(((left, top), (left, bottom-self.pet_height),
                            (right-self.size, top), (right-self.size, bottom-self.pet_height)))
                self.bite_started = time.perf_counter()
            else:
                speed = min(13.0, 5.0 + distance * 0.018)
                step = min(speed, distance)
                self.move_inside(round(x + dx / distance * step), round(y + dy / distance * step))
            if elapsed >= 10.0:
                self.bite_phase = "return"
                self.bite_started = time.perf_counter()
        elif self.bite_phase == "carry":
            # Once caught, quickly drag the cursor to a random corner while
            # keeping it attached to the mouth.
            duration = 0.55
            t = min(1.0, (time.perf_counter() - self.bite_started) / duration)
            ease = t * t * (3 - 2 * t)
            x = round(self.bite_origin[0] + (self.bite_target[0] - self.bite_origin[0]) * ease)
            y = round(self.bite_origin[1] + (self.bite_target[1] - self.bite_origin[1]) * ease)
            self.root.geometry(f"+{x}+{y}")
            self.set_cursor_position(x + mx, y + my)
            if t >= 1.0:
                self.bite_phase = "return"
                self.bite_started = time.perf_counter()
        elif self.bite_phase == "return":
            x, y = self.root.winfo_x(), self.root.winfo_y()
            dx = self.bite_return_position[0] - x
            dy = self.bite_return_position[1] - y
            distance = math.hypot(dx, dy)
            if distance <= 3:
                self.root.geometry(f"+{self.bite_return_position[0]}+{self.bite_return_position[1]}")
                self.bite_release()
                return
            # After catching the cursor, return with a calmer, slower motion.
            step = min(7.0, distance)
            self.move_inside(round(x + dx / distance * step), round(y + dy / distance * step))
        self.bite_job = self.root.after(16, self.bite_approach)

    def bite_release(self):
        self.biting = False
        self.bite_job = None
        self.roam_target = None
        self.save_settings()

    def move_inside(self, x: int, y: int, areas=None) -> None:
        areas = areas or self.monitor_areas()
        if not self.covered((x,y,x+self.size,y+self.pet_height), areas):
            fitting = [a for a in areas if a[2]-a[0]>=self.size and a[3]-a[1]>=self.pet_height]
            if not fitting:
                self.build_frames()
                return
            positions = [(max(l,min(x,r-self.size)), max(t,min(y,b-self.pet_height)))
                         for l,t,r,b in fitting]
            x,y = min(positions, key=lambda q: (q[0]-x)**2+(q[1]-y)**2)
        self.root.geometry(f"+{x}+{y}")

    @staticmethod
    def autostart_enabled():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "FutaDesktopPet")
                return True
        except OSError:
            return False

    def set_autostart(self):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                if self.autostart.get():
                    args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve())]
                    winreg.SetValueEx(key, "FutaDesktopPet", 0, winreg.REG_SZ, subprocess.list2cmdline(args))
                else:
                    try:
                        winreg.DeleteValue(key, "FutaDesktopPet")
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            self.autostart.set(self.autostart_enabled())
            messagebox.showerror("开机自启", str(exc), parent=self.settings_window)

    def preferences_changed(self):
        self.roam_target = None
        self.paused.set(not self.moving.get())
        self.save_settings()

    def show_settings(self):
        if self.settings_window is not None:
            self.settings_window.lift()
            return
        self.hide_bubble()
        window = self.settings_window = tk.Toplevel(self.root)
        window.title("福塔 · 设置")
        window.resizable(False, False)
        window.attributes("-topmost", True)
        panel = ttk.Frame(window, padding=22)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="福塔桌宠", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", pady=(0,16))
        ttk.Checkbutton(panel, text="开机自启", variable=self.autostart, command=self.set_autostart).pack(anchor="w", pady=5)
        ttk.Label(panel, text="桌宠大小").pack(anchor="w", pady=(14,0))
        self.size_label = ttk.Label(panel, text=str(self.size))
        self.size_label.pack(anchor="e")
        self.size_slider = ttk.Scale(panel, from_=140, to=700, orient="horizontal", length=300)
        self.size_slider.set(self.size)
        self.size_slider.configure(command=self.queue_size)
        self.size_slider.pack(fill="x")
        ttk.Checkbutton(panel, text="允许跨屏游荡", variable=self.cross_screen, command=self.preferences_changed).pack(anchor="w", pady=(18,5))
        ttk.Label(panel, text="关闭后仅在当前屏幕游荡；仍可手动拖到扩展屏。").pack(anchor="w")
        ttk.Radiobutton(panel, text="静止", variable=self.moving, value=False, command=self.preferences_changed).pack(anchor="w", pady=(14,5))
        ttk.Radiobutton(panel, text="运动（自由飞行）", variable=self.moving, value=True, command=self.preferences_changed).pack(anchor="w")
        ttk.Checkbutton(panel, text="始终置顶", variable=self.always_on_top, command=self.set_topmost).pack(anchor="w", pady=14)
        ttk.Button(panel, text="恢复到当前屏幕右下角", command=self.move_home).pack(fill="x", pady=4)
        ttk.Button(panel, text="退出福塔", command=self.close).pack(fill="x", pady=4)
        window.protocol("WM_DELETE_WINDOW", self.close_settings)
        window.update_idletasks()
        l,t,r,b = self.work_area()
        x=max(l,min(self.root.winfo_x(),r-window.winfo_width()))
        y=max(t,min(self.root.winfo_y(),b-window.winfo_height()))
        window.geometry(f"+{x}+{y}")

    def queue_size(self, value):
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
        size = round(float(value))
        self.size_label.configure(text=str(size))
        def apply():
            self.resize_timer = None
            self.set_size(size)
            self.size_label.configure(text=str(self.size))
        self.resize_timer = self.root.after(100, apply)

    def close_settings(self):
        if self.resize_timer is not None:
            self.root.after_cancel(self.resize_timer)
            self.resize_timer = None
            self.set_size(round(self.size_slider.get()))
        self.settings_window.destroy()
        self.settings_window = None
        self.save_settings()

    def on_configure(self, event: tk.Event) -> None:
        if event.widget == self.root and self.bubble is not None:
            self.position_bubble()

    def hide_bubble(self) -> None:
        if self.bubble_timer is not None:
            self.root.after_cancel(self.bubble_timer)
            self.bubble_timer = None
        if self.bubble is not None:
            self.bubble.destroy()
            self.bubble = None

    def show_dialog(self) -> None:
        self.hide_bubble()
        self.bubble = tk.Toplevel(self.root)
        self.bubble.withdraw()
        self.bubble.overrideredirect(True)
        self.bubble.transient(self.root)
        self.bubble.attributes("-topmost", self.always_on_top.get())
        self.bubble.configure(bg=TRANSPARENT_COLOR)
        self.bubble.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.bubble_canvas = tk.Canvas(self.bubble, bg=TRANSPARENT_COLOR,
                                       highlightthickness=0, bd=0)
        self.bubble_canvas.pack()
        self.bubble_text = self.bubble_canvas.create_text(
            0, 0, text=random.choice(SAYINGS), fill="white",
            font=("Microsoft YaHei UI", 12), justify="center", anchor="nw",
            width=min(300, self.work_area()[2] - self.work_area()[0] - 48))
        box = self.bubble_canvas.bbox(self.bubble_text)
        self.bubble_width = box[2] - box[0] + 36
        self.bubble_body_height = box[3] - box[1] + 28
        self.bubble_canvas.bind("<Button-1>", lambda event: self.hide_bubble())
        self.position_bubble()
        self.bubble.deiconify()
        self.bubble_timer = self.root.after(5000, self.hide_bubble)

    def position_bubble(self) -> None:
        if self.bubble is None:
            return
        left, top, right, bottom = self.work_area()
        w, body = self.bubble_width, self.bubble_body_height
        h = body + 18
        # Point to the head. Near the screen top the tail flips upward.
        head_x = self.root.winfo_x() + self.size // 2
        head_y = self.root.winfo_y() + int(self.pet_height * 0.12)
        above = head_y - h >= top
        x = max(left, min(head_x - w // 2, right - w))
        y = head_y - h if above else head_y + 4
        y = max(top, min(y, bottom - h))
        tail_x = max(26, min(head_x - x, w - 26))
        c = self.bubble_canvas
        c.configure(width=w, height=h)
        c.delete("shape")
        y0 = 0 if above else 18
        y1 = y0 + body
        radius = 16
        c.create_polygon(
            radius, y0, w-radius, y0, w, y0, w, y0+radius,
            w, y1-radius, w, y1, w-radius, y1, radius, y1,
            0, y1, 0, y1-radius, 0, y0+radius, 0, y0,
            smooth=True, splinesteps=24, fill="#111111", tags="shape")
        if above:
            points = (tail_x-12, body-2, tail_x, h, tail_x+12, body-2)
        else:
            points = (tail_x-12, 20, tail_x, 0, tail_x+12, 20)
        c.create_polygon(*points, fill="#111111", tags="shape")
        c.coords(self.bubble_text, 18, y0 + 14)
        c.tag_raise(self.bubble_text)
        self.bubble.geometry(f"{w}x{h}+{x}+{y}")

    def toggle_pause(self, _event: tk.Event) -> None:
        self.moving.set(not self.moving.get())
        self.preferences_changed()

    def set_topmost(self) -> None:
        self.root.attributes("-topmost", self.always_on_top.get())
        if self.bubble is not None:
            self.bubble.attributes("-topmost", self.always_on_top.get())
        self.save_settings()

    def set_size(self, size: int, save: bool = True) -> None:
        self.roam_target = None
        self.size = size
        self.build_frames()
        if save:
            self.save_settings()

    def move_home(self) -> None:
        self.root.update_idletasks()
        left, top, right, bottom = self.work_area()
        self.move_inside(right - self.size - 28, bottom - self.pet_height)
        self.save_settings()

    def load_settings(self) -> None:
        try:
            settings = json.loads(config_path().read_text(encoding="utf-8"))
            self.size = int(settings.get("size", self.size))
            self.moving.set(bool(settings.get("moving", False)))
            self.cross_screen.set(bool(settings.get("cross_screen", True)))
            self.always_on_top.set(bool(settings.get("always_on_top", True)))
            self.paused.set(not self.moving.get())
            self.root.attributes("-topmost", self.always_on_top.get())
            x = int(settings["x"])
            y = int(settings["y"])
            self.root.geometry(f"+{x}+{y}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            self.root.update_idletasks()
            self.move_home()

    def save_settings(self) -> None:
        data = {"x": self.root.winfo_x(), "y": self.root.winfo_y(), "size": self.size,
                "moving": self.moving.get(), "cross_screen": self.cross_screen.get(),
                "always_on_top": self.always_on_top.get()}
        try:
            config_path().write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def close(self) -> None:
        self.biting = False
        if self.bite_job is not None:
            self.root.after_cancel(self.bite_job)
            self.bite_job = None
        self.hide_bubble()
        self.save_settings()
        if self.precise_timer:
            ctypes.windll.winmm.timeEndPeriod(1)
            self.precise_timer = False
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    FutaPet().run()




