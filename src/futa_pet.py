import datetime
import json
import math
import time
import os
import random
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ctypes
from ctypes import wintypes
import winreg
import subprocess
import traceback
from pathlib import Path

from PIL import Image, ImageTk, ImageDraw, ImageChops, ImageEnhance, ImageFont, ImageGrab


APP_NAME = "福塔桌宠 3.1"
TRANSPARENT_COLOR = "#010203"
FRAME_COUNT = 60
TARGET_FPS = 60

# 3.0 行为参数
SLEEP_IDLE = 600.0          # 空闲 10 分钟：睡着
SLEEPY_IDLE = 180.0         # 空闲 3 分钟：犯困
NIGHT_SLEEP_IDLE = 300.0    # 夜间空闲 5 分钟：睡着
NIGHT_START_HOUR = 23       # 夜间模式开始
NIGHT_END_HOUR = 7
PET_HOLD = 1.5              # 悬停多久算摸头
BITE_COOLDOWN = 180.0       # 咬人冷却
BITE_ESCAPE_PRESSES = 3     # 被叼住时连点几次可挣脱

SAYINGS = (
    "比我萌的没我坏\n比我坏的不存在~",
    "就把我的吉他带走吧~\n就把我的歌也带走吧~",
)

SPEECH = {
    "night": (
        "十二点了。\n你还不睡，我就替你睡。",
        "这个点还亮着屏幕，\n你是在等我睡着吗？",
        "别关我。\n关了我也在，只是你看不见。",
    ),
    "sleepy": (
        "我先眯一会儿。\n有事……明天再说。",
        "困了。\n你也早点睡。",
    ),
    "asleep": (
        "zzz……\n（抱紧自己）",
        "梦到柠檬了。\n别抢。",
    ),
    "wake": (
        "我、我没睡。\n我在思考。",
        "你动静小点。\n我刚梦到柠檬。",
    ),
    "pet": (
        "再摸就收费。",
        "算了。\n你摸吧。",
        "嗯……\n就一下。",
    ),
    "poke": (
        "再戳我就咬你了。\n（已经咬了）",
        "别戳脸。\n脸是租来的。",
    ),
    "photo": (
        "站好，别动。\n我数三下——三。",
        "这张不许删。\n删了我也记得。",
    ),
    "bite": (
        "咬到了。\n味道一般。",
        "跑啊。\n怎么不跑了。",
    ),
    "escape": (
        "……哦，你挣开了。",
        "算你跑得快。",
    ),
    "dizzy": (
        "别晃了……\n我看见两个你。",
    ),
    "tail": (
        "转圈圈。\n抓到你了——我自己。",
    ),
    "build_ok": (
        "构建成功！\n不愧是你。",
    ),
    "build_fail": (
        "又失败了？\n……我什么都没看见。",
    ),
}


# 桌面宠物主题：同一套行为，不同立绘。
THEMES = {
    "futa": {
        "name": "福塔",
        "asset": "futa-subject.png",
        "wings": True,
        "mouth": (123, 188),
    },
    "girl": {
        "name": "睡衣女孩",
        "asset": "pajama-girl.png",
        "wings": False,
        "mouth": (94, 256),
    },
}


# 拍立得样式：预留多种边框，新增一种只需要加一条。
PHOTO_TEMPLATES = {
    "fuji": {
        "name": "富士白边",
        "canvas": (560, 700),
        "border": (36, 36, 36, 128),
        "bg": (252, 251, 247),
        "text": (128, 112, 116),
        "line": (226, 222, 214),
        "caption": True,
    },
    "wide": {
        "name": "宽幅白边",
        "canvas": (700, 540),
        "border": (32, 32, 32, 104),
        "bg": (253, 252, 249),
        "text": (128, 112, 116),
        "line": (226, 222, 214),
        "caption": True,
    },
    "classic": {
        "name": "经典方片",
        "canvas": (600, 640),
        "border": (52, 52, 52, 140),
        "bg": (249, 248, 243),
        "text": (120, 104, 108),
        "line": (228, 224, 216),
        "caption": True,
    },
    "dark": {
        "name": "黑边",
        "canvas": (560, 700),
        "border": (36, 36, 36, 128),
        "bg": (26, 24, 27),
        "text": (214, 204, 208),
        "line": (60, 56, 60),
        "caption": True,
    },
    "minimal": {
        "name": "无边框",
        "canvas": (560, 560),
        "border": (10, 10, 10, 10),
        "bg": (255, 255, 255),
        "text": (0, 0, 0),
        "line": None,
        "caption": False,
    },
}


def pictures_dir() -> Path:
    root = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Pictures"
    return root / "福塔相册"


def ui_font_file() -> str:
    for name in ("msyhbd.ttc", "msyh.ttc", "simhei.ttf"):
        path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
        if path.exists():
            return str(path)
    return ""


def idle_seconds() -> float:
    """系统空闲秒数（鼠标/键盘无输入）。"""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    tick = ctypes.windll.kernel32.GetTickCount()
    return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000.0


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

        self.theme = self.read_saved_theme()
        self.theme_var = tk.StringVar(value=self.theme)
        self.photo_dir = self.default_photo_dir()
        self.photo_dir_var = tk.StringVar(value=self.photo_dir)
        self.base_image = Image.open(resource_path(THEMES[self.theme]["asset"])).convert("RGBA")
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

        # ---- 3.0 状态：作息 / 互动 / 拍照 / 彩蛋 ----
        self.sleep_state = "awake"           # awake / sleepy / asleep / startled
        self.started_at = time.perf_counter()
        self.next_activity_check = 0.0
        self.allow_bite = tk.BooleanVar(value=True)
        self.next_bite_time = 0.0
        self.bite_press_count = 0
        self.bite_press_time = 0.0
        self.last_frame_rgba = None
        self.breath_phase = 0.0
        self.blink_until = 0.0
        self.next_blink = time.perf_counter() + random.uniform(2.5, 5.5)
        self.squish_until = 0.0
        self.startled_until = 0.0
        self.dizzy_until = 0.0
        self.pet_hover_since = None
        self.next_pet_time = 0.0
        self.pet_count = 0
        self.poke_times = []
        self.drag_speed = 0.0
        self.last_drag_sample = 0.0
        self.drag_last_pos = None
        self.tail_chase_until = 0.0
        self.next_tail_chase = time.perf_counter() + 300.0
        self.zzz_job = None
        self.zzz_count = 0
        self.flash_until = 0.0
        self.flash_item = None
        self.photo_windows = []
        self.build_event_mtime = 0.0
        self.next_build_check = 0.0
        self.animation_job = None

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
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.root.bind("<Configure>", self.on_configure)
        self.load_settings()
        self.root.update_idletasks()
        self.build_frames()
        self.last_tick = time.perf_counter()
        self.next_tick = self.last_tick
        self.animate()

    def read_saved_theme(self) -> str:
        try:
            data = json.loads(config_path().read_text(encoding="utf-8"))
            theme = data.get("theme", "futa")
            return theme if theme in THEMES else "futa"
        except (OSError, ValueError, json.JSONDecodeError):
            return "futa"

    def prepare_sway_frames(self) -> None:
        # 没有翅膀的主题：用整体轻微摇摆代替飞行帧，飞行时仍然有生命感。
        self.wings = []
        self.wing_mask = None
        self.wingless = self.base_image
        self.source_frames = []
        width, height = self.base_image.size
        center = (width / 2.0, height - 6)
        for index in range(FRAME_COUNT):
            phase = 2 * math.pi * index / FRAME_COUNT
            angle = 1.8 * math.sin(phase)
            frame = self.base_image.rotate(angle, resample=Image.Resampling.BICUBIC,
                                           center=center, expand=False)
            self.source_frames.append(frame)

    def load_theme_assets(self) -> None:
        self.base_image = Image.open(resource_path(THEMES[self.theme]["asset"])).convert("RGBA")
        self.prepare_wings()
        self.render_cache.clear()
        self.build_frames()

    def set_theme(self, theme: str) -> None:
        if theme not in THEMES:
            theme = "futa"
        if theme == self.theme:
            self.theme_var.set(self.theme)
            return
        self.theme = theme
        self.theme_var.set(theme)
        self.load_theme_assets()
        self.save_settings()

    def prepare_wings(self):
        if not THEMES[self.theme].get("wings", False):
            self.prepare_sway_frames()
            return
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

    def pose(self):
        """当前姿态：缩放、位移、亮度、旋转。全部由状态推导，便于缓存。"""
        now = time.perf_counter()
        breath = math.sin(self.breath_phase * 2 * math.pi)
        step = int(round(breath * 5))          # 量化成 11 档，保证缓存可命中
        sx = 1.0 + 0.006 * step / 5.0
        sy = 1.0 + 0.014 * step / 5.0
        dy = 1.5 * step / 5.0
        dim = 1.0
        rot = 0.0
        if self.sleep_state == "sleepy":
            dim = 0.93
        elif self.sleep_state == "asleep":
            dim = 0.78
            sx *= 0.94
            sy *= 0.94
            dy += 2.0
        if self.startled_until > now:
            k = max(0.0, min(1.0, (self.startled_until - now) / 0.5))
            dy -= 14.0 * k
            sx *= 1.0 + 0.05 * k
            sy *= 1.0 + 0.05 * k
        if self.squish_until > now:
            sx *= 1.04
            sy *= 0.94
        if self.dizzy_until > now:
            rot = 4.5 * math.sin(now * 24.0)
        if self.blink_until > now:
            sy *= 0.965
        return sx, sy, dy, dim, rot

    def cache_limit(self) -> int:
        # 按内存预算而不是帧数限制缓存：大尺寸时少存几帧。
        per_entry = max(1, int(self.size * self.pet_height * 4 * 2.2))
        return max(6, min(48, int(48 * 1024 * 1024 / per_entry)))

    def render_frame(self):
        flying = self.moving.get() and not self.biting and self.sleep_state != "asleep"
        index = self.frame_index if flying else -1
        sx, sy, dy, dim, rot = self.pose()
        key = (index, self.facing_right, self.size, round(sx, 3), round(sy, 3),
               round(dy), round(dim, 2), round(rot, 1))
        value = self.render_cache.get(key)
        if value is None:
            source = self.source_frames[index] if index >= 0 else self.base_image
            quality = Image.Resampling.BILINEAR if self.right_press else Image.Resampling.LANCZOS
            width = max(1, min(self.size - 2, round(self.size * sx)))
            height = max(1, min(self.pet_height - 4,
                                round(source.height * width / source.width * sy)))
            sprite = source.resize((width, height), quality)
            if dim < 1.0:
                sprite = ImageEnhance.Brightness(sprite).enhance(dim)
            if abs(rot) > 0.1:
                sprite = sprite.rotate(rot, resample=Image.Resampling.BICUBIC, expand=False)
            frame = Image.new("RGBA", (self.size, self.pet_height), (1, 2, 3, 255))
            x = (self.size - sprite.width) // 2
            y = max(0, min(self.pet_height - sprite.height, 14 + int(round(dy))))
            frame.alpha_composite(sprite, (x, y))
            if self.facing_right:
                frame = frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if len(self.render_cache) >= self.cache_limit():
                self.render_cache.pop(next(iter(self.render_cache)))
            value = (ImageTk.PhotoImage(frame), frame)
            self.render_cache[key] = value
        self.display_image, self.last_frame_rgba = value
        self.canvas.itemconfigure(self.sprite, image=self.display_image)
        if self.flash_item is not None:
            self.canvas.tag_raise(self.flash_item)


    def build_frames(self) -> None:
        left, top, right, bottom = self.work_area()
        limit = min(700, right-left, int((bottom-top-16)*self.base_image.width/self.base_image.height))
        self.size = max(min(140,limit), min(self.size,limit))
        self.render_cache.clear()
        self.pet_height = int(self.base_image.height*self.size/self.base_image.width)+28
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
        busy = (self.biting or self.drag_origin is not None or self.right_press is not None
                or self.settings_window is not None or self.sleep_state == "asleep")
        now = time.perf_counter()
        if not busy and self.tail_chase_active(now):
            # 彩蛋：绕着自己转圈（追尾巴）
            self.tail_phase = getattr(self, "tail_phase", 0.0) + dt * 5.0
            cx, cy = getattr(self, "tail_center",
                             (self.root.winfo_x(), self.root.winfo_y()))
            x = cx + math.cos(self.tail_phase) * 40
            y = cy + math.sin(self.tail_phase * 2.0) * 12
            self.move_inside(round(x), round(y))
            return
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
        try:
            now = time.perf_counter()
            dt = min(0.05, max(0.001, now - self.last_tick))
            self.last_tick = now
            if self.pending_drag_size is not None:
                size = self.pending_drag_size
                self.pending_drag_size = None
                self.set_size(size, save=False)
            self.breath_phase = (self.breath_phase + dt * 0.33) % 1.0
            if now >= self.next_blink:
                self.blink_until = now + 0.12
                self.next_blink = now + random.uniform(2.5, 6.0)
            if now >= self.next_activity_check:
                self.next_activity_check = now + 0.5
                self.check_activity(now)
            self.update_build_event(now)
            self.roam(dt)
            if not self.paused.get() or self.tail_chase_active(now):
                self.animation_phase = (self.animation_phase + dt / 1.65) % 1.0
                self.frame_index = int(self.animation_phase * FRAME_COUNT)
            self.render_frame()
        except Exception:
            self.safe_reschedule()
            return
        self.next_tick += 1 / TARGET_FPS
        finished = time.perf_counter()
        if self.next_tick < finished:
            self.next_tick = finished + 1 / TARGET_FPS
        self.animation_job = self.root.after(max(1, round((self.next_tick - finished) * 1000)), self.animate)

    def safe_reschedule(self) -> None:
        # 任何一帧出错都不允许让桌宠永久卡死，同时留下可查的日志。
        try:
            log_dir = config_path().parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "runtime.log").open("a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S\n"))
                fh.write(traceback.format_exc() + "\n")
        except OSError:
            pass
        try:
            self.root.after(500, self.animate)
        except tk.TclError:
            pass

    def tail_chase_active(self, now):
        return now < self.tail_chase_until

    # ---------- 3.0 作息：困 / 睡 / 惊醒 ----------
    def check_activity(self, now: float) -> None:
        hour = datetime.datetime.now().hour
        night = hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR
        if self.biting or self.drag_origin is not None or self.right_press is not None:
            return
        idle = idle_seconds()
        if self.sleep_state == "asleep":
            if idle < 0.6:
                self.wake_up()
            return
        if idle >= SLEEP_IDLE or (night and idle >= NIGHT_SLEEP_IDLE):
            self.fall_asleep()
            return
        if idle >= SLEEPY_IDLE or night:
            self.sleep_state = "sleepy"
        else:
            self.sleep_state = "awake"
        if (self.sleep_state == "awake" and idle >= 240
                and now >= self.next_tail_chase and not self.moving.get()):
            self.start_tail_chase(now)

    def fall_asleep(self) -> None:
        if self.sleep_state == "asleep":
            return
        self.sleep_state = "asleep"
        self.roam_target = None
        self.flight_velocity = (0.0, 0.0)
        left, top, right, bottom = self.work_area()
        self.move_inside(right - self.size - 16, bottom - self.pet_height)
        self.save_settings()
        self.start_zzz()

    def wake_up(self) -> None:
        if self.sleep_state != "asleep":
            return
        self.sleep_state = "awake"
        self.stop_zzz()
        self.startled_until = time.perf_counter() + 0.9
        self.show_bubble("！", 900)
        self.root.after(650, lambda: self.show_bubble(random.choice(SPEECH["wake"]), 3500))

    def start_zzz(self) -> None:
        if self.zzz_job is not None:
            return
        self.zzz_job = self.root.after(300, self.zzz_tick)

    def stop_zzz(self) -> None:
        if self.zzz_job is not None:
            self.root.after_cancel(self.zzz_job)
            self.zzz_job = None

    def zzz_tick(self) -> None:
        self.zzz_job = None
        if self.sleep_state != "asleep":
            return
        x = self.size // 2 + random.randint(8, 42)
        y = int(self.pet_height * 0.16) + random.randint(0, 18)
        self.float_text(random.choice(("z", "Z", "zz")), x, y, "#FFFFFF",
                        random.choice((11, 13, 15)), 36, 1500)
        self.zzz_job = self.root.after(900, self.zzz_tick)

    def float_text(self, text, x, y, color="#FFFFFF", size=12, rise=30, duration=1200) -> None:
        # 色键窗口不能做 alpha 淡出，所以文字只上浮后直接消失。
        item = self.canvas.create_text(x, y, text=text, fill=color,
                                       font=("Microsoft YaHei UI", size, "bold"))
        steps = 18
        interval = max(16, duration // steps)
        def step(i: int = 0) -> None:
            if i >= steps or not self.canvas.winfo_exists():
                self.canvas.delete(item)
                return
            self.canvas.coords(item, x, y - rise * (i + 1) / steps)
            self.root.after(interval, lambda: step(i + 1))
        self.root.after(interval, step)

    def start_tail_chase(self, now: float) -> None:
        self.tail_chase_until = now + 5.0
        self.tail_center = (self.root.winfo_x(), self.root.winfo_y())
        self.tail_phase = 0.0
        self.next_tail_chase = now + random.uniform(420, 700)
        if random.random() < 0.7:
            self.show_bubble(random.choice(SPEECH["tail"]), 2600)

    # ---------- 3.0 彩蛋：构建联动 ----------
    def update_build_event(self, now: float) -> None:
        if now < self.next_build_check:
            return
        self.next_build_check = now + 2.0
        path = config_path().parent / "build-event.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if mtime <= self.build_event_mtime:
            return
        self.build_event_mtime = mtime
        try:
            ok = bool(json.loads(path.read_text(encoding="utf-8")).get("ok"))
        except (OSError, ValueError):
            return
        if ok:
            for i in range(5):
                self.root.after(i * 120, lambda: self.float_text(
                    "★", random.randint(20, self.size - 20),
                    random.randint(20, self.pet_height // 2), "#FFE45C", 14, 40, 1100))
            self.show_bubble(random.choice(SPEECH["build_ok"]), 4000)
        else:
            self.dizzy_until = time.perf_counter() + 1.2
            self.show_bubble(random.choice(SPEECH["build_fail"]), 4000)

    def start_left_action(self, event: tk.Event) -> None:
        if self.biting:
            return
        self.left_press = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.left_press_local = (event.x, event.y)
        self.did_drag = False
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        self.drag_peak = 0.0
        self.drag_last_pos = (event.x_root, event.y_root)
        self.drag_last_time = time.perf_counter()

    def left_drag(self, event: tk.Event) -> None:
        if self.drag_origin:
            if abs(event.x_root - self.left_press[0]) > 4 or abs(event.y_root - self.left_press[1]) > 4:
                self.did_drag = True
            now = time.perf_counter()
            dt = max(0.001, now - self.drag_last_time)
            speed = math.hypot(event.x_root - self.drag_last_pos[0],
                               event.y_root - self.drag_last_pos[1]) / dt
            self.drag_peak = max(getattr(self, "drag_peak", 0.0), speed)
            self.drag_last_pos = (event.x_root, event.y_root)
            self.drag_last_time = now
            x = event.x_root - self.drag_origin[0]
            y = event.y_root - self.drag_origin[1]
            self.move_inside(x, y)

    def finish_left_action(self, _event: tk.Event) -> None:
        was_drag = self.did_drag
        local = getattr(self, "left_press_local", (0, 0))
        self.drag_origin = None
        if self.left_press and not was_drag:
            if self.sleep_state == "asleep":
                self.wake_up()
            elif self.head_hit(*local):
                self.poke_head()
            else:
                self.register_click()
                self.show_dialog()
        elif was_drag and getattr(self, "drag_peak", 0.0) > 2600:
            self.dizzy_until = time.perf_counter() + 1.2
            self.float_text("× ×", self.size // 2, int(self.pet_height * 0.2),
                            "#FFFFFF", 14, 24, 900)
            self.show_bubble(random.choice(SPEECH["dizzy"]), 2200)
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
                self.show_menu(event)

    def double_click(self, event: tk.Event) -> None:
        self.drag_origin = None
        self.left_press = None
        self.hide_bubble()
        if self.biting:
            return
        if self.sleep_state == "asleep":
            self.wake_up()
            return
        if self.head_hit(event.x, event.y):
            self.start_pet()
            return
        if not self.allow_bite.get() or time.perf_counter() < self.next_bite_time:
            self.show_bubble("今天不咬人。\n心情好。", 2000)
            return
        # Only the torso triggers the playful attack.
        if 0.18*self.size <= event.x <= 0.82*self.size and 0.45*self.pet_height <= event.y <= 0.83*self.pet_height:
            if random.random() < 0.6:
                self.start_bite()

    def head_hit(self, x: float, y: float) -> bool:
        return (0.20 * self.size <= x <= 0.80 * self.size
                and 0.02 * self.pet_height <= y <= 0.42 * self.pet_height)

    def on_motion(self, event: tk.Event) -> None:
        if self.biting or self.drag_origin is not None:
            return
        now = time.perf_counter()
        if self.head_hit(event.x, event.y):
            if self.pet_hover_since is None:
                self.pet_hover_since = now
            elif now - self.pet_hover_since >= PET_HOLD and now >= self.next_pet_time:
                self.start_pet()
        else:
            self.pet_hover_since = None

    def on_leave(self, _event: tk.Event) -> None:
        self.pet_hover_since = None

    def start_pet(self) -> None:
        now = time.perf_counter()
        self.pet_hover_since = None
        self.next_pet_time = now + 2.0
        self.squish_until = now + 0.7
        self.pet_count += 1
        self.float_text(random.choice(("♥", "★")), self.size // 2,
                        int(self.pet_height * 0.18), "#FF8AB8", 14, 26, 900)
        if self.pet_count in (5, 12, 25) or random.random() < 0.3:
            self.show_bubble(random.choice(SPEECH["pet"]), 2600)

    def poke_head(self) -> None:
        now = time.perf_counter()
        self.squish_until = now + 0.45
        self.pet_count += 1
        self.poke_times = [t for t in self.poke_times if now - t <= 2.5]
        self.poke_times.append(now)
        if len(self.poke_times) >= 3:
            self.poke_times = []
            self.hide_bubble()
            away = 1 if self.root.winfo_x() < self.work_area()[0] + self.size else -1
            self.move_inside(self.root.winfo_x() + away * 36, self.root.winfo_y())
            self.show_bubble(random.choice(SPEECH["poke"]), 2600)
            if self.allow_bite.get() and random.random() < 0.6:
                self.root.after(650, self.start_bite)
        else:
            self.float_text("!", self.size // 2, int(self.pet_height * 0.2),
                            "#FFFFFF", 13, 20, 700)

    def register_click(self) -> None:
        now = time.perf_counter()
        self.click_times = getattr(self, "click_times", [])
        self.click_times = [t for t in self.click_times if now - t <= 4.0]
        self.click_times.append(now)
        if len(self.click_times) >= 10:
            self.click_times = []
            self.dizzy_until = now + 1.4
            self.show_bubble(random.choice(SPEECH["dizzy"]), 2600)

    def _left_click_edge(self) -> bool:
        down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        clicked = down and not getattr(self, "_prev_left_down", False)
        self._prev_left_down = down
        return clicked

    @staticmethod
    def cursor_position():
        point = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    @staticmethod
    def set_cursor_position(x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def mouth_offset(self):
        # 每个主题在自己的 290 x 436 画布上给出嘴部锚点。
        anchor = THEMES[self.theme].get("mouth", (123, 188))
        art_width = self.base_image.width
        x = (art_width - anchor[0]) if self.facing_right else anchor[0]
        scale = self.size / art_width
        return round(x * scale), round(14 + anchor[1] * scale)

    def start_bite(self):
        if self.biting:
            return
        if not self.allow_bite.get() or time.perf_counter() < self.next_bite_time:
            return
        self.biting = True
        self.next_bite_time = time.perf_counter() + BITE_COOLDOWN
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
            # 被叼住时连点鼠标可以挣脱。
            if self._left_click_edge():
                now = time.perf_counter()
                if now - self.bite_press_time > 1.8:
                    self.bite_press_count = 0
                self.bite_press_count += 1
                self.bite_press_time = now
                if self.bite_press_count >= BITE_ESCAPE_PRESSES:
                    self.bite_press_count = 0
                    self.bite_phase = "return"
                    self.bite_started = time.perf_counter()
                    self.show_bubble(random.choice(SPEECH["escape"]), 2400)
                    self.bite_job = self.root.after(16, self.bite_approach)
                    return
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
        self.squish_until = time.perf_counter() + 0.5
        if random.random() < 0.75:
            self.show_bubble(random.choice(SPEECH["bite"]), 2600)
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

    @staticmethod
    def default_photo_dir() -> str:
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
        if desktop.exists():
            return str(desktop)
        return str(Path.home() / "Desktop")

    def photo_folder(self) -> Path:
        folder = Path(self.photo_dir) if self.photo_dir else Path(self.default_photo_dir())
        return folder

    def choose_photo_dir(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.photo_folder(),
                                         title="选择照片保存目录", parent=self.settings_window)
        if folder:
            self.photo_dir = folder
            self.photo_dir_var.set(folder)
            self.save_settings()

    def reset_photo_dir(self) -> None:
        self.photo_dir = self.default_photo_dir()
        self.photo_dir_var.set(self.photo_dir)
        self.save_settings()

    def show_menu(self, event: tk.Event) -> None:
        self.hide_bubble()
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="拍一张", command=self.take_photo)
        menu.add_separator()
        menu.add_command(label="设置", command=self.show_settings)
        menu.add_command(label="退出福塔", command=self.close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def take_photo(self) -> None:
        self.open_viewfinder()

    def current_sprite(self):
        sprite = (self.last_frame_rgba or self.base_image).copy()
        if sprite.mode != "RGBA":
            sprite = sprite.convert("RGBA")
        diff = ImageChops.difference(sprite.convert("RGB"),
                                     Image.new("RGB", sprite.size, (1, 2, 3)))
        mask = diff.convert("L").point(lambda v: 0 if v <= 8 else 255)
        sprite.putalpha(mask)
        return sprite

    def grab_region(self, x: int, y: int, w: int, h: int):
        scale = self.screen_scale()
        img = ImageGrab.grab(bbox=(int(x * scale), int(y * scale),
                                   int((x + w) * scale), int((y + h) * scale)),
                             all_screens=True)
        if scale != 1.0:
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        return img.convert("RGBA")

    def open_viewfinder(self) -> None:
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

        title = tk.Label(canvas, text="取景框", bg=dark,
                         fg="#F2E9EC", font=("Microsoft YaHei UI", 10, "bold"))
        hint = tk.Label(canvas, text="拖边框移动 · 拖四角缩放", bg=dark, fg="#8C7B82",
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
                w = max(420, min(w, right - left))
                h = max(320, min(h, bottom - top))
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

    def shoot_viewfinder(self, window, border: int, bar: int, cap_w: int, cap_h: int) -> None:
        gx = window.winfo_x() + border
        gy = window.winfo_y() + bar
        try:
            self.root.attributes("-alpha", 0.0)
            window.attributes("-alpha", 0.0)
            self.root.update_idletasks()
            self.root.update()
            scene = self.grab_region(gx, gy, cap_w, cap_h)
        except Exception:
            return
        finally:
            try:
                window.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
            self.root.attributes("-alpha", 1.0)
            self.root.update_idletasks()
            self.root.update()
        sprite = self.current_sprite()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        inside = (gx <= px and gy <= py
                  and px + self.size <= gx + cap_w
                  and py + self.pet_height <= gy + cap_h)
        if inside:
            ox, oy = px - gx, py - gy
        else:
            ox, oy = (cap_w - sprite.width) // 2, (cap_h - sprite.height) // 2
        scene.alpha_composite(sprite, (ox, oy))
        try:
            window.destroy()
        except tk.TclError:
            pass
        self._viewfinder = None
        self.flash(0.12)
        self.root.after(120, lambda: self.show_photo_preview(scene))

    def screen_scale(self) -> float:
        """逻辑像素 -> 物理像素的比例（高分屏下 Tk 坐标与截图坐标不一致）。"""
        if getattr(self, "_screen_scale", None) is None:
            try:
                probe = ImageGrab.grab(all_screens=True)
                self._screen_scale = max(1.0, probe.width / max(1, self.root.winfo_screenwidth()))
                del probe
            except Exception:
                self._screen_scale = 1.0
        return self._screen_scale

    def grab_scene(self):
        """截图：隐藏桌宠后抓整个工作区，返回(场景, 桌宠中心在场景中的坐标)。"""
        left, top, right, bottom = self.work_area()
        x, y = self.root.winfo_x(), self.root.winfo_y()
        focus = (x + self.size // 2 - left, y + self.pet_height // 2 - top)
        scale = self.screen_scale()
        bbox = (int(left * scale), int(top * scale), int(right * scale), int(bottom * scale))
        try:
            self.root.attributes("-alpha", 0.0)
            self.root.update_idletasks()
            self.root.update()
            scene = ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGBA")
            if scale != 1.0:
                scene = scene.resize((right - left, bottom - top), Image.Resampling.LANCZOS)
        finally:
            self.root.attributes("-alpha", 1.0)
            self.root.update_idletasks()
            self.root.update()
        sprite = (self.last_frame_rgba or self.base_image).copy()
        if sprite.mode != "RGBA":
            sprite = sprite.convert("RGBA")
        diff = ImageChops.difference(sprite.convert("RGB"),
                                     Image.new("RGB", sprite.size, (1, 2, 3)))
        mask = diff.convert("L").point(lambda v: 0 if v <= 8 else 255)
        sprite.putalpha(mask)
        return scene, sprite

    @staticmethod
    def cover_crop(image, target_w: int, target_h: int, focus=None):
        src_w, src_h = image.size
        ratio = target_w / target_h
        if src_w / src_h > ratio:
            crop_w = max(1, int(src_h * ratio))
            crop_h = src_h
        else:
            crop_w = src_w
            crop_h = max(1, int(src_w / ratio))
        if focus is None:
            left = (src_w - crop_w) // 2
            top = (src_h - crop_h) // 2
        else:
            left = int(focus[0] - crop_w / 2)
            top = int(focus[1] - crop_h / 2)
            left = max(0, min(left, src_w - crop_w))
            top = max(0, min(top, src_h - crop_h))
        return image.crop((left, top, left + crop_w, top + crop_h)).resize(
            (target_w, target_h), Image.Resampling.LANCZOS)

    def build_polaroid(self, scene, template_key: str = "fuji", sprite=None, caption: bool = False):
        tpl = PHOTO_TEMPLATES.get(template_key, PHOTO_TEMPLATES["fuji"])
        card_w, card_h = tpl["canvas"]
        bl, bt, br, bb = tpl["border"]
        photo_w = max(1, card_w - bl - br)
        photo_h = max(1, card_h - bt - bb)
        if sprite is not None:
            # 取屏幕中央一块背景，把桌宠放在照片正中：主角永远居中。
            region_h = min(scene.height, max(int(self.pet_height * 2.3), 480))
            region_w = int(region_h * photo_w / photo_h)
            if region_w > scene.width:
                region_w = scene.width
                region_h = max(1, int(region_w * photo_h / photo_w))
            left = (scene.width - region_w) // 2
            top = (scene.height - region_h) // 2
            photo = scene.crop((left, top, left + region_w, top + region_h)).resize(
                (photo_w, photo_h), Image.Resampling.LANCZOS)
            factor = photo_w / region_w
            pet_w = max(1, int(sprite.width * factor))
            pet_h = max(1, int(sprite.height * factor))
            pet = sprite.resize((pet_w, pet_h), Image.Resampling.LANCZOS)
            photo.alpha_composite(pet, ((photo_w - pet_w) // 2, (photo_h - pet_h) // 2))
        else:
            photo = self.cover_crop(scene, photo_w, photo_h)
        card = Image.new("RGB", (card_w, card_h), tpl["bg"])
        card.paste(photo.convert("RGB"), (bl, bt))
        draw = ImageDraw.Draw(card)
        if tpl.get("line"):
            draw.rectangle((bl - 1, bt - 1, bl + photo_w, bt + photo_h),
                           outline=tpl["line"], width=2)
        if caption and tpl.get("caption") and bb >= 70:
            font_path = ui_font_file()
            try:
                font_small = ImageFont.truetype(font_path, 17) if font_path else ImageFont.load_default()
                font_big = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
            except OSError:
                font_small = font_big = ImageFont.load_default()
            now = datetime.datetime.now()
            draw.text((bl, bt + photo_h + 26), now.strftime("%Y-%m-%d  %H:%M"),
                      fill=tpl["text"], font=font_small)
            caption = "福塔 3.1" if self.theme == "futa" else "福塔 3.1 · " + THEMES[self.theme]["name"]
            draw.text((bl, bt + photo_h + 58), caption, fill=tpl["text"], font=font_big)
        return card

    def show_photo_preview(self, scene, sprite=None) -> None:
        window = tk.Toplevel(self.root)
        window.title("拍立得预览")
        window.attributes("-topmost", True)
        window.resizable(False, False)
        window.configure(bg="#1E1A1D")
        state = {"key": "fuji"}
        image_label = tk.Label(window, bd=0, bg="#1E1A1D")
        image_label.pack(padx=16, pady=(16, 10))
        style_row = tk.Frame(window, bg="#1E1A1D")
        style_row.pack(fill="x", padx=16)
        choice = tk.StringVar(value="fuji")
        for key, tpl in PHOTO_TEMPLATES.items():
            tk.Radiobutton(style_row, text=tpl["name"], value=key, variable=choice,
                           command=lambda: render(), bg="#1E1A1D", fg="#F2E9EC",
                           selectcolor="#3A3034", activebackground="#1E1A1D",
                           activeforeground="#FFFFFF", highlightthickness=0,
                           bd=0, font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 10))
        option_row = tk.Frame(window, bg="#1E1A1D")
        option_row.pack(fill="x", padx=16)
        caption_var = tk.BooleanVar(value=False)
        tk.Checkbutton(option_row, text="写日期/文字", variable=caption_var,
                       command=lambda: render(), bg="#1E1A1D", fg="#F2E9EC",
                       selectcolor="#3A3034", activebackground="#1E1A1D",
                       activeforeground="#FFFFFF", highlightthickness=0,
                       bd=0, font=("Microsoft YaHei UI", 9)).pack(side="left")
        action_row = tk.Frame(window, bg="#1E1A1D")
        action_row.pack(fill="x", padx=16, pady=(10, 16))
        status = tk.StringVar(value="选好样式后点保存，照片会存到「图片\\福塔相册」")
        tk.Label(action_row, textvariable=status, bg="#1E1A1D", fg="#C9B8BE",
                 font=("Microsoft YaHei UI", 9)).pack(side="left")
        def render():
            key = choice.get()
            card = self.build_polaroid(scene, key, sprite, caption_var.get())
            photo = ImageTk.PhotoImage(card)
            image_label.configure(image=photo)
            image_label.image = photo
            state["key"] = key
        def save():
            card = self.build_polaroid(scene, choice.get(), sprite, caption_var.get())
            try:
                folder = self.photo_folder()
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / ("Futa_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3] + ".png")
                card.save(path, "PNG")
            except OSError as exc:
                status.set("保存失败：" + str(exc))
                return
            window.destroy()
            self.show_saved_toast(path)
        def cancel():
            window.destroy()
        tk.Button(action_row, text="保存", command=save, relief="flat", bd=0,
                  bg="#EA7BAC", fg="#FFFFFF", activebackground="#D46698",
                  activeforeground="#FFFFFF", padx=16, pady=5,
                  font=("Microsoft YaHei UI", 9, "bold")).pack(side="right")
        tk.Button(action_row, text="取消", command=cancel, relief="flat", bd=0,
                  bg="#3A3034", fg="#F2E9EC", activebackground="#4A3C42",
                  activeforeground="#FFFFFF", padx=12, pady=5,
                  font=("Microsoft YaHei UI", 9)).pack(side="right", padx=(0, 8))
        render()
        window.update_idletasks()
        w, h = window.winfo_width(), window.winfo_height()
        left, top, right, bottom = self.work_area()
        pos_x = min(max(left + 40, self.root.winfo_x() + self.size + 24), right - w - 20)
        pos_y = max(top + 40, min(self.root.winfo_y(), bottom - h - 40))
        window.geometry(f"+{pos_x}+{pos_y}")
        window.bind("<Escape>", lambda _event: window.destroy())
        self.photo_windows.append(window)

    def show_saved_toast(self, path) -> None:
        window = tk.Toplevel(self.root)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        frame = tk.Frame(window, bg="#1E1A1D", padx=20, pady=16)
        frame.pack()
        tk.Label(frame, text="截图已保存到", bg="#1E1A1D", fg="#C9B8BE",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        tk.Label(frame, text=str(path.parent), bg="#1E1A1D", fg="#FFFFFF",
                 font=("Microsoft YaHei UI", 10, "bold"), wraplength=420).pack(anchor="w", pady=(2, 12))
        row = tk.Frame(frame, bg="#1E1A1D")
        row.pack(fill="x")
        def open_file():
            try:
                os.startfile(str(path))
            except OSError:
                pass
        def open_folder():
            try:
                os.startfile(str(path.parent))
            except OSError:
                pass
        tk.Button(row, text="立即打开", command=open_file, relief="flat", bd=0,
                  bg="#EA7BAC", fg="#FFFFFF", activebackground="#D46698",
                  activeforeground="#FFFFFF", padx=14, pady=4,
                  font=("Microsoft YaHei UI", 9, "bold")).pack(side="right")
        tk.Button(row, text="打开文件夹", command=open_folder, relief="flat", bd=0,
                  bg="#3A3034", fg="#F2E9EC", activebackground="#4A3C42",
                  activeforeground="#FFFFFF", padx=10, pady=4,
                  font=("Microsoft YaHei UI", 9)).pack(side="right", padx=(0, 8))
        window.update_idletasks()
        w, h = window.winfo_width(), window.winfo_height()
        left, top, right, bottom = self.work_area()
        window.geometry(f"+{right - w - 24}+{bottom - h - 24}")
        window.bind("<Escape>", lambda _event: window.destroy())
        self.photo_windows.append(window)
        def auto_close():
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass
        self.root.after(12000, auto_close)

    def flash(self, duration: float = 0.12) -> None:
        if self.flash_item is not None:
            self.canvas.delete(self.flash_item)
        self.flash_item = self.canvas.create_rectangle(
            0, 0, self.size, self.pet_height, fill="#FFFFFF", outline="")
        self.canvas.tag_raise(self.flash_item)

        def end():
            if self.flash_item is not None:
                try:
                    self.canvas.delete(self.flash_item)
                except tk.TclError:
                    pass
                self.flash_item = None
        self.root.after(int(duration * 1000), end)

    def show_settings(self):
        if self.settings_window is not None:
            self.settings_window.lift()
            return
        self.hide_bubble()
        window = self.settings_window = tk.Toplevel(self.root)
        window.title("福塔 3.1 · 设置")
        window.resizable(False, False)
        window.attributes("-topmost", True)
        panel = ttk.Frame(window, padding=22)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="福塔桌宠", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", pady=(0,16))
        ttk.Checkbutton(panel, text="开机自启", variable=self.autostart, command=self.set_autostart).pack(anchor="w", pady=5)
        ttk.Checkbutton(panel, text="允许咬人", variable=self.allow_bite, command=self.save_settings).pack(anchor="w", pady=5)
        ttk.Label(panel, text="桌宠主题").pack(anchor="w", pady=(12, 0))
        for key, info in THEMES.items():
            ttk.Radiobutton(panel, text=info["name"], value=key, variable=self.theme_var,
                            command=lambda k=key: self.set_theme(k)).pack(anchor="w", pady=2)
        ttk.Label(panel, text="照片保存目录").pack(anchor="w", pady=(12, 0))
        dir_row = ttk.Frame(panel)
        dir_row.pack(fill="x")
        ttk.Entry(dir_row, textvariable=self.photo_dir_var, width=30).pack(side="left", fill="x", expand=True)
        ttk.Button(dir_row, text="选择", command=self.choose_photo_dir).pack(side="left", padx=(6, 0))
        ttk.Button(panel, text="恢复默认（桌面）", command=self.reset_photo_dir).pack(anchor="w", pady=(4, 0))
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
        ttk.Button(panel, text="拍一张拍立得", command=self.take_photo).pack(fill="x", pady=4)
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
        self.show_bubble(self.dialogue_for_state())

    def dialogue_for_state(self) -> str:
        if self.sleep_state == "asleep":
            return random.choice(SPEECH["asleep"])
        if self.sleep_state == "sleepy":
            return random.choice(SPEECH["sleepy"])
        hour = datetime.datetime.now().hour
        if (hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR) and random.random() < 0.5:
            return random.choice(SPEECH["night"])
        return random.choice(SAYINGS)

    def show_bubble(self, text: str, duration: int = 5000) -> None:
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
            0, 0, text=text, fill="white",
            font=("Microsoft YaHei UI", 12), justify="center", anchor="nw",
            width=min(300, self.work_area()[2] - self.work_area()[0] - 48))
        box = self.bubble_canvas.bbox(self.bubble_text)
        self.bubble_width = box[2] - box[0] + 36
        self.bubble_body_height = box[3] - box[1] + 28
        self.bubble_canvas.bind("<Button-1>", lambda event: self.hide_bubble())
        self.position_bubble()
        self.bubble.deiconify()
        self.bubble_timer = self.root.after(duration, self.hide_bubble)

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
            self.allow_bite.set(bool(settings.get("allow_bite", True)))
            theme = settings.get("theme", self.theme)
            if theme in THEMES and theme != self.theme:
                self.theme = theme
                self.theme_var.set(theme)
                self.load_theme_assets()
            self.photo_dir = str(settings.get("photo_dir") or self.default_photo_dir())
            self.photo_dir_var.set(self.photo_dir)
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
                "always_on_top": self.always_on_top.get(),
                "allow_bite": self.allow_bite.get(),
                "theme": self.theme,
                "photo_dir": self.photo_dir}
        try:
            config_path().write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass

    def close(self) -> None:
        self.biting = False
        self.stop_zzz()
        if self.animation_job is not None:
            try:
                self.root.after_cancel(self.animation_job)
            except tk.TclError:
                pass
            self.animation_job = None
        for window in list(self.photo_windows):
            try:
                window.destroy()
            except tk.TclError:
                pass
        self.photo_windows.clear()
        if getattr(self, "_viewfinder", None) is not None:
            try:
                self._viewfinder.destroy()
            except tk.TclError:
                pass
            self._viewfinder = None
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
