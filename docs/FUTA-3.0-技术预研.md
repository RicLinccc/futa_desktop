# 福塔桌宠 3.0 技术分析笔记

> 本期口径：3.0 先做好玩，不做渲染重写；本文留作 3.1 / 4.0 的技术储备，当前不执行。
> 范围：渲染方案、皮肤包格式、新玩法实现要点、性能预算与风险；玩法与美术约束见 [FUTA-3.0-玩法美术规格.md](FUTA-3.0-玩法美术规格.md)。
> 分析对象：E:\CppProject\futa_desktop（Python + Tkinter + Pillow，PyInstaller onefile）
> 分析方式：只读阅读源码 + 本机实测基准，未修改 src/、dist/、.build/ 下任何文件
> 配套产物：本文件（docs/FUTA-3.0-技术预研.md）；主文档见 [FUTA-3.0-灵感.md](FUTA-3.0-灵感.md)
> 结论时间：2026-11-07

本文中所有 `L###` 均指 [src/futa_pet.py](../src/futa_pet.py) 的行号；性能数字均为本机实测（Python 3.12.4 / Pillow / Tk 8.6，单显示器 1707x1019 工作区），标注「估算」的除外。

---

## 0. 结论速览

| 问题 | 现状 | 3.0 结论 |
|---|---|---|
| 透明实现 | Tk `-transparentcolor` 色键，1-bit alpha（L46、L164） | 必须换逐像素 alpha，否则毛绒软边无法实现 |
| 渲染管线 | 每帧 LANCZOS 缩放 + `ImageTk.PhotoImage`，缓存上限 24 < 60 帧 | 预烘焙 + 两级缓存；渲染后端抽成接口 |
| 命中测试 | 整个矩形窗口都吃鼠标 | alpha 掩码 + WM_NCHITTEST 阈值 |
| DPI | Tk 系统级 DPI 感知，混合 DPI 下发虚 | PerMonitorV2，坐标统一用物理像素 |
| 推荐方案 | — | **B：Python + ctypes UpdateLayeredWindow**，保留 Tk 做设置/气泡壳 |
| 迁移节奏 | — | P0 spike → P1 渲染后端 → P2 皮肤包 → P3 玩法 → P4（可选）原生渲染器 |

五条硬结论：

1. **色键方案没有中间地带。** 半透明像素会与键色 `#010203` 混合成第三种颜色，既不是键色也无法半透明；抖动只能伪造 25%/50%/75% 三档，且在 300px 角色上移动时明显闪烁。3.0 的「毛绒软边」是 alpha 连续渐变，A 方案直接出局。
2. **当前每帧成本约 5.0 ms，其中 3.84 ms 是缩放、1.20 ms 是 PhotoImage 转换。** 而缓存上限 24 小于 `FRAME_COUNT=60`，动画时几乎 100% miss——这笔钱一直在白花。
3. **B 方案的增量成本远小于重写。** 只替换「窗口 + 呈现」这一层，飞行、多屏、咬光标、设置、自启都能原样保留；实测 ULW 数据通路每帧约 0.8 ms（预乘 + 拷贝）。
4. **C（WebView2/Electron）在「逐像素命中 + 常驻低内存」这两点上反而退化**，透明窗口的点击穿透基本是整窗开关，且内存从 ~50 MB 涨到 200 MB 量级。
5. **D（C++/Direct2D）上限最高，但现在做等于把 700 行已验证逻辑推倒重来。** 目录名 `CppProject` 只是工作区命名，不能当作技术意向的证据；是否走 D 要看团队产能和是否真的需要 120fps/GPU 粒子。

---

## 1. 现状盘点

### 1.1 文件与构建事实

| 项 | 值 | 说明 |
|---|---|---|
| 主源码 | `src/futa_pet.py`，700 行 | 单文件，无模块拆分 |
| 素材 | `assets/futa-subject.png`，290x436 RGBA | 不透明像素 75,287（59.5%），**半透明像素 0 个** |
| 打包 | `福塔桌宠.spec` + `build.ps1`，onefile + windowed + UPX | 产物 `dist/福塔桌宠.exe` = 17,853,515 B（17.0 MiB） |
| 运行时依赖 | 仅 Pillow | 没有 numpy（spec 里显式 exclude） |
| 配置 | `%LOCALAPPDATA%\FutaDesktopPet\settings.json`（L33-L36） | 6 个字段，无版本号 |
| 自启 | `HKCU\...\Run` 值名 `FutaDesktopPet`（L487-L500） | 非 frozen 时用 python.exe，会闪控制台 |

基线内存实测：裸 Python 23.8 MB → 创建 Tk 后 30.8 MB → 再放 24 张 300x467 的 `PhotoImage` 后 47.0 MB。也就是说**每张 300x467 的 Tk 图像约 0.67 MB**，60 帧约 40 MB，双朝向 120 帧约 80 MB。这是后面所有缓存策略的硬约束。

### 1.2 窗口与 1-bit 透明（L40-L47、L83-L94）

窗口创建链路：

```
L41  self.root = tk.Tk()
L42  timeBeginPeriod(1)                 # 全局定时器精度 1ms
L44  self.root.overrideredirect(True)   # 无边框、无任务栏
L45  self.root.attributes("-topmost", True)
L46  self.root.wm_attributes("-transparentcolor", "#010203")
L47  self.root.configure(bg=TRANSPARENT_COLOR)
```

- `-transparentcolor` 在 Windows 上走 `SetLayeredWindowAttributes(hwnd, key, 0, LWA_COLORKEY)`：**只有精确等于键色的像素被挖空**，其余像素完全不透明。
- Canvas 背景与画布底色都用 `#010203`（L87、L164），角色以外区域因此透出桌面。
- 窗口尺寸不是角色包围盒，而是 `size x pet_height`（300x467，L180-L184），四周留了 16px 余量和居中 padding（L165 的 `((self.size-width)//2, 5)`）。**透明区域仍然接收鼠标**，所以宠物旁边 40px 的空白也能拖动窗口——这是当前「点不到桌面图标」的根因。
- 没有 `WS_EX_TOOLWINDOW` / `WS_EX_NOACTIVATE` 的显式设置，`overrideredirect` 的 Tk 顶层窗口在 Alt+Tab 里的行为依赖 Tk 实现；点击宠物会把焦点从用户当前应用抢走。

半透明为什么不行（数学上）：

设像素颜色 C、alpha a，Tk 先把它合成到窗口背景 K=`#010203` 上，得到 `C' = a*C + (1-a)*K`。色键只认 `C' == K`：

| alpha | 结果 | 色键判定 |
|---|---|---|
| 0 | 正好 K | 透明 ✅ |
| 255 | 正好 C | 不透明 ✅ |
| 128 | (C+K)/2，第三种颜色 | **既不透也不软，变成深色描边** ❌ |

当前素材实测半透明像素为 0，说明美术一直按硬边交付，问题被掩盖了。3.0 的绒毛边缘需要 40-200 的 alpha 渐变，一旦接入就会暴露成一圈脏边。

### 1.3 渲染管线

整条链路只有四级，全部集中在 4 个方法里：

```
base_image (290x436)
  └─ prepare_wings()      L113-L151  启动时预生成 60 帧 source_frames（仍是 290x436）
       └─ render_frame()  L153-L173  取帧 → 缩放 → 贴到 size x pet_height → 翻转 → PhotoImage
            └─ canvas.itemconfigure(sprite)  L173
                 └─ render_cache  L52 / L169-L171
```

#### 1.3.1 坐标系与尺寸

- 原始画布 290x436；`pet_height = round(436*size/290)+16`（L180），size=300 时是 467。
- 角色在窗口内水平居中、垂直偏移 5px（L165）。
- 所有交互坐标都是窗口坐标（event.x/event.y），嘴部坐标是硬编码的美术坐标再按 `size/290` 缩放（L384-L387）：`mouth = (123 或 167, 188)`。这是 3.0 要替换成「部件锚点」的第一个硬编码点。
- 没有 DPI 缩放因子：size 是逻辑像素，Windows 在 150% 缩放下会把窗口整体位图拉伸（Tk 为 system-DPI-aware），所以高分屏上角色是糊的。

#### 1.3.2 prepare_wings（L113-L151）

启动时一次性做三件事：

1. 用两个手绘多边形（L119-L120）从底图抠出左右翅膀，得到带 alpha 的独立图层（L121-L126），同时记录 `wing_mask`（L128）和去掉翅膀的身体 `wingless`（L129-L130）。
2. 生成 60 帧：每帧按 `flap = 0.58 + 0.42*cos(2π*i/60*4)` 纵向缩放翅膀（L134-L138），`alpha_composite` 到身体上（L139）。
3. 把 `hip=350` 以下整段做纵向缩放 + 斜切（L142-L150），模拟呼吸/摆动；先清空下半区（L149）再贴回（L150），避免出现残影。

实测：60 帧共 **112 ms**（约 1.9 ms/帧），可以接受；但它是「启动时一次性 + 尺寸无关」的，尺寸变化不会重算——因为它输出的是 290x436 的源帧，缩放留给了 render_frame。这个分层其实是对的，3.0 应保留。

缺点：翅膀和下半身之外没有可动部件；帧数固定 60；动作只有一种「飘」。兜帽、面具、柠檬都需要新的部件层，靠改这段代码会迅速失控。

#### 1.3.3 render_frame（L153-L173）

```
L154  index = frame_index if moving and not biting else -1
L155  key = (index, self.facing_right)
L157  source = source_frames[index] if index >= 0 else base_image
L159  scale = 0.9925 + 0.0075*sin(phase) if index >= 0 else 1.0
L162  quality = BILINEAR if right_press else LANCZOS
L163  resized = source.resize((width, height), quality)
L164  frame = Image.new("RGBA", (size, pet_height), (1,2,3,255))
L165  frame.alpha_composite(resized, ((size-width)//2, 5))
L166  if facing_right: frame = frame.transpose(FLIP_LEFT_RIGHT)
L171  render_cache[key] = ImageTk.PhotoImage(frame)
```

行为要点与问题：

- **biting 时回退到静态底图**（L154 的 `not self.biting`）：咬光标全程没有咬合/前倾动作，只有位移。3.0 的状态机必须覆盖 chase/carry/bite/return 四个状态。
- 呼吸缩放只作用于「索引帧」，静止时完全不动（L159 的 else 分支），所以宠物站着像贴纸。
- 每帧新建 `Image.new`（L164），即使缓存命中也会在 miss 时分配 560 KB；GC 压力不大但没必要。
- `render_cache` 的 key 不含 `size`（L155），靠 `build_frames`（L179）和 `finish_resize`（L357）里的 `clear()` 兜底。任何忘记 clear 的新路径都会拿到错误尺寸的缓存——3.0 加皮肤/DPI 后这种隐式约定很容易炸。
- 缓存上限 24（L169-L171），而动画一圈有 60 个 index、再乘 2 个朝向 = 120 个 key。LRU 在 24 个插入后就淘汰，而同一 index 要 1.65 s 后才复用 → **稳态 miss 率接近 100%**。

#### 1.3.4 缓存账本（实测）

| 尺寸 | 单帧字节 | 24 帧 | 60 帧 | 120 帧（双朝向） |
|---|---|---|---|---|
| 300x467 | 560,400 B (547 KiB) | 12.8 MiB（Tk 实际 ~16 MB） | 32.8 MiB | 65.6 MiB |
| 700x1068 | 2,990,400 B (2.85 MiB) | 68.5 MiB | 171 MiB | 342 MiB |

结论：**上限 24 是内存妥协，但它换来的不是命中率，而是 0 命中**。要么把上限提到 120（内存不可接受），要么把「缓存单位」从 PhotoImage 改成「预乘后的字节缓冲 + 一张复用的 DIB」，后者正是 B 方案。

### 1.4 动画循环与帧率（L295-L312）

```
L297  dt = min(0.05, max(0.001, now - last_tick))
L299  if pending_drag_size: set_size(...)      # 右拖缩放在这里落地，避免拖动中重建
L303  self.roam(dt)
L304  if not paused: animation_phase += dt/1.65; frame_index = int(phase*60)
L307  self.render_frame()
L308  next_tick += 1/60
L310  if next_tick < finished: next_tick = finished + 1/60
L312  root.after(max(1, round((next_tick - finished)*1000)), self.animate)
```

- 自校正的固定步长调度：落后就丢弃欠账（L310-L311），不会出现「补帧风暴」，这点是对的。
- `dt` 上限 0.05 s（L297）：系统卡顿 200 ms 时动画只前进 50 ms，表现为整体变慢而不是跳变，可接受。
- `timeBeginPeriod(1)`（L42）把系统定时器精度拉到 1 ms，代价是**整机功耗上升**（Win10 2004 后按进程生效，但仍是笔记本续航杀手）。3.0 应改为：只有动画/拖拽期间 `timeBeginPeriod(1)`，静止 3 s 后 `timeEndPeriod(1)`。
- **异常会杀死循环**：`after` 的注册在函数末尾（L312），`roam` / `render_frame` 任何未捕获异常都会导致下一帧不再调度，宠物永久卡死；`bite_approach` 同理（L458），且 `biting` 会停在 True，之后连左键都被吞掉（L315）。这是 3.0 必须加的顶层 try/except + 自愈重启。
- 60fps 对桌宠是过剩的：静止 30fps、快速运动/咬合 60fps 足够，直接省一半 CPU 与唤醒次数。

### 1.5 交互事件（L96-L102、L314-L372）

| 事件 | 处理 | 行为 |
|---|---|---|
| `<ButtonPress-1>` | L314 | 记录按下点、窗口原点、drag_origin；biting 时直接 return |
| `<B1-Motion>` | L321 | 超过 4px 判定为拖动，`move_inside` 夹到屏内 |
| `<ButtonRelease-1>` | L329 | 未拖动 → `show_dialog`（气泡）；每次释放都写配置 |
| `<ButtonPress-3>` / Motion / Release | L336-L361 | 右键拖拽缩放，`(dx+dy)/2`，夹在 140-700；未移动则开设置 |
| `<Double-Button-1>` | L363 | 躯干硬编码比例框（0.18-0.82 x 0.45-0.83）内 50% 概率触发咬 |
| `<Configure>` | L561 | 仅用于气泡跟随 |

缺口：

- 没有 hover / 滚轮 / 键盘 / 托盘菜单；右键单击=设置、右键拖=缩放，两个语义挤在一个键上。
- 双击的命中框是比例硬编码（L370），换皮肤/换尺寸就会错位；3.0 应由「部件命中掩码」回答「点到的是不是躯干/兜帽/柠檬」。
- 透明区域也响应拖动（见 1.2），这是体感问题不是 bug，但 3.0 做 alpha 命中后要保留「边缘 8px 可拖」的宽容度，否则小部件很难点。
- `toggle_pause`（L631-L633）是死代码，没有任何绑定；README 写「双击切换静止/自由飞行」，实现里双击是咬（L363-L372）——文档与代码已漂移。

### 1.6 飞行与多屏（L187-L293）

`monitor_areas`（L187-L204）用 `EnumDisplayMonitors` + Python 回调收集每个显示器的 `rcWork`（已避开任务栏）。实测单屏 **4.4 µs/次**，跨屏漫游时每帧调用（L279）完全可接受。

`covered`（L212-L227）用矩形差集判断「宠物矩形是否完全落在显示器并集内」。注意命名与语义相反：返回 True 表示**完全可见**。它处理了跨屏接缝（L224-L225 把剩余块继续切分），逻辑正确但读起来费劲，3.0 建议改名 `fully_on_desktop`。

`flight_step`（L229-L274）：

1. 每 45-110 逻辑帧随机转向 ±1.3 rad（L234-L237），叠加 0.28 rad 的正弦摆动（L237）；
2. 速度 3.4±0.7 px/帧（L238），按 `1-0.91**step` 做指数趋近（L253-L255）；
3. 碰撞用「前瞻探测」：沿 4 个距离（8/24/48/80）各测一次（L244-L245），被挡就在 ±180° 内以 15° 为步长找 25 个候选角，取最近的可行方向（L246-L251）；
4. 仍然撞上时按轴归零并 +90°（L258-L268），避免穿墙；
5. 朝向由 vx 符号决定（L270-L273）。

实测：一次被挡帧的 100 次 `covered` 调用约 **108 µs**（0.65% 帧预算），性能没问题。

设计问题：

- `step = dt/0.033`（L231）再在末尾乘回（L269），把速度隐式和 30Hz 绑定；dt 抖动时会轻微改变实际速度，建议改成显式 `velocity += accel*dt`。
- 只有「探测-拒绝」，没有反弹/软边界，贴着屏幕边缘飞时会反复触发转向（每帧 +90°），观感是抖。
- 没有「停靠」「绕窗口飞」「跟随光标」的概念，只有全屏随机游走。
- 显示器热插拔/分辨率变化靠每帧重枚举自然兜底，但窗口尺寸不会跟着 DPI 变。

### 1.7 咬光标状态机（L374-L464）

```
chase  (L412-L432): 每 16ms 读真实光标，速度 5-13 px/帧，距离 <= max(18, size*0.08) 转 carry，10s 超时转 return
carry  (L433-L445): 0.55s smoothstep 把窗口拖到随机角，同时 SetCursorPos 让光标始终咬在嘴上
return (L446-L457): 7 px/帧 回到 bite_return_position，距离 <=3 结束
```

- ESC 通过 `GetAsyncKeyState(0x1B)` 轮询（L406），因为此时焦点在别的应用，收不到 Tk 键盘事件——这个处理是对的。
- `SetCursorPos`（L442）会**直接搬走用户的鼠标**：无开关、无首次提示、无「按住任意键挣脱」。这是可访问性风险，也容易被安全软件标记。3.0 建议改为「咬住贴纸/柠檬」或加显式开关 + 双击 ESC 释放。
- carry 的目标角是四个屏幕角（L423-L424），没有检查 `pet_height` 是否放得下；小屏 + 大尺寸时会算出负坐标，靠 `move_inside` 兜底但会瞬移。
- 整个状态机没有「咬合」帧，也没有音效/粒子；3.0 的 `bite` 状态需要 3-5 帧的口部动画 + 命中特效。
- 异常未捕获（见 1.4），`bite_job` 链断掉后 `biting` 永久为 True。

### 1.8 配置、自启与生命周期（L478-L500、L654-L689）

- 配置路径 `%LOCALAPPDATA%\FutaDesktopPet\settings.json`（L33-L36），字段：x、y、size、moving、cross_screen、always_on_top（L670-L673）。
- `save_settings` 直接 `write_text`（L675），**非原子**：写入过程中断电/崩溃会留下半截 JSON；下次启动走 `except` 分支（L666）→ `move_home`，表现为「位置和大小全丢」。
- 没有 schema 版本号，3.0 加 `skin`、`hood`、`lemon` 等字段后无法做迁移。
- 没有单实例互斥：双击两次 exe 会有两只宠物，各自读写同一份配置，互相覆盖。
- 自启写 `HKCU\...\Run`（L487-L500），非 frozen 时命令是 `python.exe script.py`（L491），会闪黑框；应换 `pythonw.exe` 或仅在 frozen 时允许开启。
- `close`（L679-L689）会取消 bite_job、关气泡、保存、`timeEndPeriod`，收尾是完整的；但没有处理 `WM_QUERYENDSESSION`/ 注销，系统关机时可能来不及保存（概率低）。

### 1.9 代码级问题清单

| # | 位置 | 问题 | 影响 | 3.0 处置 |
|---|---|---|---|---|
| 1 | L46 / L164 | 色键 1-bit 透明 | 软边不可能 | 换 ULW（方案 B） |
| 2 | L155 | 缓存 key 不含 size | 依赖隐式 clear，易错 | key 含 (size, dpi, facing, state, frame) |
| 3 | L169-L171 | 上限 24 < 60 帧 | 稳态 0 命中，每帧 5 ms | 两级缓存 + 字节预算 |
| 4 | L163 | 每帧 LANCZOS | 3.84 ms/帧 | 尺寸稳定后预烘焙 |
| 5 | L154 | biting 回静态图 | 咬合无动画 | 状态机接管 |
| 6 | L164 | 每帧 new Image | 560 KB/次分配 | 复用画布缓冲 |
| 7 | L297 | dt 上限 0.05 | 卡顿后整体变慢 | 保留，但加追帧上限 |
| 8 | L312 / L458 | after 链无异常保护 | 一次异常永久卡死 | 顶层 try/except + 重启调度 |
| 9 | L370 | 双击命中框硬编码比例 | 换皮错位 | 部件命中掩码 |
| 10 | L384-L387 | 嘴坐标硬编码 290 基准 | 同上 | skin.json 锚点 |
| 11 | L406 | 全局轮询 ESC | 可接受，但无提示 | 保留 + UI 提示 |
| 12 | L442 | SetCursorPos 无同意 | 可访问性/安全软件 | 开关 + 替代交互 |
| 13 | L675 | 非原子写配置 | 崩溃丢配置 | 临时文件 + os.replace |
| 14 | L631 | 死代码 toggle_pause | 维护误导 | 删除或接上 |
| 15 | L491 | 非 frozen 用 python.exe | 控制台闪窗 | pythonw / 仅 frozen |
| 16 | 全局 | 无 DPI 处理 | 高分屏模糊 | PerMonitorV2 |
| 17 | 全局 | 无单实例 | 双开互相覆盖 | CreateMutex |
| 18 | L279 | 每帧枚举显示器 | 4.4 µs，可接受 | 缓存 2 s + 事件失效 |

### 1.10 实测基线（本机，单次采样均值）

| 操作 | 耗时 | 备注 |
|---|---|---|
| prepare_wings 60 帧 | 112 ms | 启动一次性 |
| LANCZOS 缩放 290x436→300x451 + 合成 | 3.84 ms | 当前每帧主成本 |
| BILINEAR 同上 | 2.59 ms | 右拖缩放时用 |
| NEAREST 同上 | 0.83 ms | 可作低功耗档 |
| `ImageTk.PhotoImage` 300x467 | 1.20 ms | 缓存 miss 时 |
| 水平翻转 | 0.047 ms | 可忽略 |
| 预乘 + 转 BGRA bytes | 0.77 ms | ULW 上传前处理 |
| 裸 BGRA tobytes | 0.13 ms | 不含预乘 |
| memmove 560,400 B | 0.012 ms | 拷进 DIB |
| CreateDIBSection | 0.028 ms | 只创建一次 |
| alpha_composite 单层 300x467 | 0.64 ms | 每多一层 +0.64 ms |
| GaussianBlur r=6 / r=2 | 2.88 / 2.82 ms | 毛绒烘焙用 |
| alpha 阈值 point() | 0.10 ms | 命中掩码生成 |
| EnumDisplayMonitors | 4.4 µs | 单屏 |
| covered() 一次 | 1.1 µs | 被挡帧 100 次 = 108 µs |
| PNG 编码 300x467 | 25.8 ms / 155 KB | 拍照保存 |
| WebP q90 同上 | 14.9 ms / 33 KB | 可选 |
| import tkinter / PIL | 16 / 60 ms | 冷启动 |
| Tk() 创建 | 148 ms | 冷启动 |

当前稳态成本（缓存 miss）：3.84 + 1.20 ≈ **5.04 ms/帧**，占 60fps 预算的 30%，再加 Tk canvas 重绘与 after 调度，单核实测常驻 25-35%。

---


## 2. 3.0 渲染方案对比与推荐

### 2.1 先把「软边」量化

3.0 的视觉需求可以拆成四层 alpha：

| 层 | alpha 范围 | 尺寸 | 是否每帧变化 |
|---|---|---|---|
| 投影 | 0-90 | 角色轮廓外扩 8-20px | 随位置/呼吸微动 |
| 绒毛外缘 | 20-180 | 轮廓外 2-6px | 强风时抖动 |
| 兜帽内阴影 | 60-160 | 脸周围 | 兜帽升降时 |
| 睡衣布面高光 | 30-80 | 布料内部 | 呼吸/光照 |

只要存在 20-180 这一档，色键方案就不可能通过「调参」绕过。A 方案唯一能做的是 2x2 棋盘抖动（25%/50%/75% 三档），在 300px 角色上等价于可见的网点，且宠物移动时网点跟着动，观感比硬边更差。

### 2.2 方案 A：Tkinter + 色键（维持现状）

| 维度 | 评价 |
|---|---|
| 软边/阴影 | ❌ 只有 0/255；抖动有网点；阴影只能画成硬矩形或干脆不画 |
| 60fps CPU | 缓存 miss 时 5.04 ms/帧（实测），命中时约 0.05 ms；但现缓存 0 命中 |
| 内存 | 24 帧 ≈ 16 MB，60 帧 ≈ 40 MB，120 帧 ≈ 80 MB |
| 开发量 | 0（已经在了） |
| 打包体积 | 17.0 MiB onefile，无外部依赖 |
| 点击穿透 | ❌ 整窗矩形；透明区也吃鼠标 |
| 命中测试 | 只能按矩形/比例硬编码（L370） |
| 多屏 DPI | Tk 8.6 为 system-DPI-aware，混合 DPI 下被系统位图拉伸，发虚 |
| 风险 | 低，但产品目标不可达 |

**结论：A 只能作为 P1 的回退档保留，不能作为 3.0 的交付形态。** 如果 3.0 砍掉毛绒软边，那 A 够用；但那就不是 3.0 了。

### 2.3 方案 B：Python + ctypes + UpdateLayeredWindow（推荐）

#### 2.3.1 原理

Windows 的 layered window 支持逐像素 alpha：窗口用 `WS_EX_LAYERED` 创建，内容通过 `UpdateLayeredWindow` 一次性提交一张 32bpp 的顶-down DIB，格式是**预乘 BGRA**，混合参数 `AC_SRC_OVER + AC_SRC_ALPHA`。DWM 负责把它和桌面合成，硬件加速，不需要每帧 BitBlt。

关键 API 链：

```
CreateWindowExW(WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE,
                "FutaPetLayer", L"福塔", WS_POPUP, x, y, w, h, 0, 0, hinst, 0)
GetDC(NULL)                       -> hdcScreen
CreateCompatibleDC(hdcScreen)     -> hdcMem
CreateDIBSection(hdcMem, &bmi, DIB_RGB_COLORS, &bits, NULL, 0)  # biHeight 为负 = top-down
SelectObject(hdcMem, hbmp)
memmove(bits, premultiplied_bgra, w*h*4)
UpdateLayeredWindow(hwnd, hdcScreen, &ptDst, &size, hdcMem, &ptSrc, 0, &blend, ULW_ALPHA)
```

`ptDst` 直接指定屏幕位置，**移动窗口和换内容可以合并成一次调用**，没有 SetWindowPos 的中间态闪烁。这也是它比「先 SetWindowPos 再刷内容」流畅的原因。

#### 2.3.2 必须知道的三个坑

1. **`SetLayeredWindowAttributes` 与 `UpdateLayeredWindow` 互斥。** MSDN 明确：一旦对某个 hwnd 调用过 `SetLayeredWindowAttributes`，后续 `UpdateLayeredWindow` 会失败，直到清除并重新设置 `WS_EX_LAYERED`。Tk 的 `-transparentcolor` 正是前者，所以**绝不能在 Tk 的 root 窗口上直接改 ULW**，必须新建独立 hwnd。
2. **预乘。** 上传的每个像素必须是 `(R*A/255, G*A/255, B*A/255, A)`。忘了预乘 → 边缘发白/发光；重复预乘 → 边缘发黑。PIL 侧只在「上传前」做一次，缓存里保存直通 alpha 的 RGBA。
3. **alpha=0 天然穿透，alpha=1-23 不穿透。** MSDN 原文：layered window 的命中测试基于形状与透明度，alpha 为 0 的区域鼠标消息会穿透到下层；但 1-23 这种「几乎看不见」的绒毛像素仍会挡住桌面图标。需要 `WM_NCHITTEST` 里按阈值（建议 24-32）返回 `HTTRANSPARENT`，跨进程兜底再叠加「光标在 fringe 时动态加 `WS_EX_TRANSPARENT`」的 60Hz 轮询（掩码在内存里，查询 O(1)）。

#### 2.3.3 与 Tk 共存（这是 B 方案能否低成本落地的关键）

Tk 的 `mainloop` 在 Windows 上就是 `GetMessage` / `DispatchMessage` 循环，**同线程内所有窗口的消息都会被派发**，包括我们自建的 hwnd。因此可以：

- `root.withdraw()` 把 Tk root 变成「设置窗口宿主 + 定时器源」；
- 自建 layered hwnd 负责宠物本体，WndProc 处理 `WM_NCHITTEST`、`WM_LBUTTONDOWN`、`WM_MOUSEMOVE`、`WM_DPICHANGED`；
- 动画仍由 `root.after` 驱动（现有 `animate` 结构不用动），每帧调 `presenter.present(frame)`；
- 设置窗口继续用 Tk `Toplevel`。

风险点：Tk 的 event loop 是否 100% 派发非 Tk 窗口消息、以及焦点/激活顺序（`WS_EX_NOACTIVATE` 下点击不抢焦点）。这两条必须在 P0 spike 用 30 行 demo 验证，不能假设。

#### 2.3.4 成本与性能

| 维度 | 评价 |
|---|---|
| 软边/阴影 | ✅ 完整 8-bit alpha，可做柔光投影、绒毛渐变 |
| 60fps CPU | 实测预乘 0.77 ms + memmove 0.012 ms + ULW（估 1-2 ms，需 spike 实测）→ 约 1.8-2.8 ms；若帧已预烘焙，可压到 1 ms 级 |
| 内存 | 一张 300x467 DIB = 547 KiB，可复用；帧缓存按字节预算控制 |
| 开发量 | 渲染层 3-5 人日，命中/DPI/拖动 3-5 人日，合计 1.5-2.5 人周；业务逻辑复用 |
| 打包体积 | 不变，约 17-18 MiB（ctypes 是标准库） |
| 点击穿透 | ✅ alpha=0 原生；阈值 + NCHITTEST 精细控制 |
| 命中测试 | ✅ 直接用 alpha 掩码，支持「兜帽/柠檬」部件级命中 |
| 多屏 DPI | ✅ 可开 PerMonitorV2；`WM_DPICHANGED` 里按新 DPI 重建 surface |
| 风险 | 预乘错误、Tk 消息共存、无 UI 设计器；均可控 |

#### 2.3.5 最小可用骨架（约 40 行，P0 直接抄）

```python
import ctypes
from ctypes import wintypes
from PIL import Image, ImageChops

user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
WS_EX_LAYERED, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x80, 0x08000000
WS_POPUP, ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 0x80000000, 0x02, 0x00, 0x01

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

def premultiplied_bgra(im: Image.Image) -> bytes:
    r, g, b, a = im.split()
    pm = Image.merge("RGBA", (ImageChops.multiply(r, a), ImageChops.multiply(g, a),
                              ImageChops.multiply(b, a), a))
    return pm.tobytes("raw", "BGRA")

class LayerWindow:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, "FutaPetLayer",
            "FutaPet", WS_POPUP, 0, 0, w, h, None, None, self.hinst, None)
        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h   # top-down
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        self.bits = ctypes.c_void_p()
        self.hbmp = gdi32.CreateDIBSection(self.hdc_mem, ctypes.byref(bmi), 0,
                                           ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.hdc_mem, self.hbmp)
        self.blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

    def present(self, im: Image.Image, x: int, y: int):
        data = premultiplied_bgra(im)
        ctypes.memmove(self.bits, data, len(data))
        size = wintypes.SIZE(self.w, self.h)
        src, dst = wintypes.POINT(0, 0), wintypes.POINT(x, y)
        ok = user32.UpdateLayeredWindow(self.hwnd, self.hdc_screen, ctypes.byref(dst),
                                        ctypes.byref(size), self.hdc_mem,
                                        ctypes.byref(src), 0, ctypes.byref(self.blend),
                                        ULW_ALPHA)
        if not ok:
            raise ctypes.WinError()
```

注意 `CreateWindowExW` 的返回值和 `UpdateLayeredWindow` 的参数都需要显式 `argtypes/restype`（64 位下默认 `c_int` 会截断 HWND）。上面的骨架为了可读性省略了这一步，落地时必须补。

### 2.4 方案 C：WebView2 / Electron

| 维度 | 评价 |
|---|---|
| 软边/阴影 | ✅ CSS/CSS filter 都能做，视觉上限接近 D |
| 透明度实现 | Electron 的 `transparent:true` 在 Windows 上可用（DirectComposition 路径）；WebView2 窗口化控制器的透明背景长期受限，社区常用 `WS_EX_LAYERED + SetLayeredWindowAttributes` 色键兜底——又绕回 1-bit |
| 点击穿透 | ❌ 基本是整窗开关（`setIgnoreMouseEvents(true, {forward:true})`）；逐像素命中要 60Hz 轮询光标再转发，边缘手感差 |
| 60fps CPU | GPU 合成，主进程开销低；但 3-5 个进程常驻，内存 200-400 MB |
| 打包体积 | WebView2 依赖系统 Evergreen Runtime（Win11 自带，Win10 多数已装）；Electron 直接 +150-200 MB |
| 开发量 | 视觉 1-2 人周；但 IPC、窗口生命周期、打包、签名、崩溃恢复另算，且需要 JS/TS 能力 |
| 多屏 DPI | ✅ Chromium 处理得很好 |
| 风险 | 运行时依赖、内存、Python↔JS 状态同步、安全面（本地 HTTP/WS） |

**结论：C 适合做「设置面板 / 相册 / 皮肤编辑器」这类富 UI，不适合做宠物本体。** 如果团队本来就是前端栈，可以把 C 作为「宠物本体 + Python 后端」的组合，但要接受内存和穿透精度的退化。

### 2.5 方案 D：C++ / Direct2D

| 维度 | 评价 |
|---|---|
| 架构 | Win32 窗口 + D2D1 渲染 + WIC 解码 + DirectWrite + DirectComposition（或仍用 ULW） |
| 软边/阴影 | ✅✅ 最好；可做高斯阴影、模糊、粒子、120fps |
| 60fps CPU | ✅✅ GPU 合成，主线程 <1 ms |
| 内存 | ✅ 30-60 MB（无 Python 运行时） |
| 打包体积 | ✅ 1.5-4 MB 单 exe（静态链接 CRT 略大） |
| 开发量 | ❌ 4-8 人周重写；JSON 解析、图集、状态机、配置、自启、设置 UI 全要重来 |
| 点击穿透 | ✅ 完全可控（NCHITTEST + alpha 掩码） |
| 多屏 DPI | ✅ PerMonitorV2 原生 |
| 风险 | 重写风险、团队技能、构建/签名/崩溃上报基建、迭代速度变慢 |

**D 的真正优势不是「快」，而是「没有 Python 运行时」和「GPU 特效上限」。** 对一只 300x450、60fps、帧率需求稳定的桌宠来说，B 已经过剩；D 的收益要等到「毛发粒子 / 4K / 视频导出」才显现。

### 2.6 对比矩阵

评分 1-5，5 最好；「开发量」「体积」「风险」为反向分（5 = 最省）。

| 维度 | A 色键 | B ULW | C Web | D C++/D2D |
|---|---|---|---|---|
| 软边/半透明阴影 | 1 | 5 | 5 | 5 |
| 60fps CPU | 2（5 ms/帧且抖动） | 4（约 2 ms） | 3（GPU 但多进程） | 5（<1 ms） |
| 常驻内存 | 4（~50 MB） | 4（~60-90 MB） | 2（200-400 MB） | 5（30-60 MB） |
| 开发量（省为 5） | 5 | 4 | 3 | 1 |
| 打包体积（小为 5） | 5（17 MB） | 5（17-18 MB） | 2（+150 MB 或依赖运行时） | 5（1.5-4 MB） |
| 点击穿透/alpha 命中 | 1 | 5 | 2 | 5 |
| 多屏 DPI | 2 | 5 | 5 | 5 |
| 与现有代码复用 | 5 | 5 | 2 | 1 |
| 团队上手成本（低为 5） | 5 | 4 | 3 | 2 |
| 综合 | 2.6 | **4.4** | 3.0 | 3.8 |

### 2.7 推荐

**3.0 采用 B：Python + ctypes UpdateLayeredWindow，保留 Tk 作为设置/气泡宿主。**

理由按重要性排序：

1. **只有 B 能同时满足「软边」和「复用现有 700 行」。** 飞行、多屏、咬光标、设置、自启的 bug 已经踩平，重写等于把这些坑再踩一遍。
2. **B 的性能余量足够。** 预烘焙后每帧只有「预乘 + 拷贝 + ULW」，实测数据通路 0.78 ms，即使 ULW 本身花 2 ms，也只用掉 16.7 ms 预算的 17%。
3. **B 让「数据驱动皮肤」成为可能。** 逐像素 alpha 才能把「毛绒边缘/兜帽/面具/柠檬」作为图层叠加；色键方案下这些只能是整张图硬切。
4. **C/D 的收益要等到产品规模变化才兑现。** 现在换 C 是拿内存和穿透精度换开发体验；换 D 是拿 4-8 周换一个当前用不上的上限。

配套的架构约束（很重要，否则 B 会变成另一坨耦合）：

```python
class Presenter(Protocol):
    def set_bounds(self, x: int, y: int, w: int, h: int) -> None: ...
    def present(self, frame: Image.Image) -> None: ...      # 直通 alpha RGBA
    def hit_test(self, x: int, y: int, threshold: int = 24) -> bool: ...

class TkPresenter:      # P1 回退档
    ...
class LayeredPresenter: # P1 主力
    ...
```

业务层只产出 `Image`、只消费 `(x, y) -> bool`，不 import tkinter，也不 import ctypes。这样 P4 想换 C++ 渲染器时，Python 侧可以整体替换成进程间协议。

### 2.8 分阶段迁移路径

#### P0：可行性 spike（1-2 人日）

目标：证明「Tk mainloop + 自建 layered hwnd」能跑，且 60fps 不掉帧。

步骤：

1. 30 行 demo：Tk root withdraw + 自建 hwnd + 一张 300x467 的半透明圆角矩形，`root.after(16)` 里 ULW。
2. 验证四件事：WndProc 能收到 `WM_NCHITTEST` / `WM_LBUTTONDOWN`；alpha=0 区域点击能穿透到桌面图标；`WS_EX_NOACTIVATE` 下不抢焦点；连续 10 分钟 CPU 与帧间隔。
3. 用 `QueryPerformanceCounter` 记录 `UpdateLayeredWindow` 的单次耗时（当前未实测，是本文唯一的估算项）。

退出标准：60fps 下 `present` P99 < 4 ms；点击穿透符合预期；无 GDI 泄漏（`GetGuiResources` 稳定）。
回退：若 Tk 不派发自建窗口消息，改用「独立线程跑 Win32 消息循环 + 队列传帧」，成本 +3 人日。

#### P1：渲染后端抽象（3-5 人日）

- 抽 `Presenter` 接口；`TkPresenter` 包住现有 canvas 逻辑（保持现状可回退）；`LayeredPresenter` 新写。
- 用环境变量 `FUTA_RENDERER=tk|layered` 切换，默认 layered，出问题一键回退。
- `animate` 只改「present」一行；飞行/咬/设置不动。
- 加顶层 `try/except` + 300 ms 后自愈重启，解决 1.4 的「一次异常永久卡死」。

验收：同一份业务代码在两种后端下行为一致；layered 下 CPU 比 tk 低 40% 以上；拖动/缩放/双击/咬全部回归通过。

#### P2：皮肤包与部件合成（1-2 人周）

- 定义 `skin.json`（第 3 节）、图集加载器、部件合成器、声明式状态机。
- 旧素材走 `legacy` 适配器：把现有 60 帧 `source_frames` 包成一个隐式皮肤，保证 P2 期间外观不变。
- 离线烘焙：毛绒层、命中掩码、各尺寸预缩放，全部在「尺寸稳定 200 ms」后做一次。

验收：新增一套皮肤 = 新增一个目录，不改 Python；切换皮肤不掉帧；内存 < 120 MB。

#### P3：3.0 玩法（2-3 人周）

- 兜帽升降、面具、柠檬物理、停靠窗口、空闲作息、拍立得。
- 每条玩法都先落 `skin.json` 的字段与状态，再写引擎逻辑；引擎不认识具体皮肤。

验收：四个玩法都能通过 JSON 开关；关掉某玩法不报错；夜间模式不打扰用户。

#### P4（可选）：原生渲染器

- 只有出现「4K/120fps/GPU 粒子/单 exe 无 Python」硬需求时才启动。
- 复用 P2 的 `skin.json` 与图集；C++ 侧只实现 Presenter + 状态机 + 物理。
- 在此之前，B 方案的维护成本远低于双栈。

### 2.9 明确不建议的做法

| 做法 | 为什么不行 |
|---|---|
| 在 Tk root 上直接 `UpdateLayeredWindow` | 与 `-transparentcolor` 的 `SetLayeredWindowAttributes` 互斥，调用必失败 |
| 整窗 `LWA_ALPHA` 半透明 | 宠物整体变灰，不是软边 |
| 常开 `WS_EX_TRANSPARENT` | 所有点击都穿透，宠物点不到 |
| 每帧 `CreateDIBSection` / 每帧 PNG 编解码 | 分配与编解码成本吞掉预算 |
| 用 `PhotoImage` 缓存 60-120 帧 | 每张 0.67 MB，Tk 内部还有一份拷贝，80-160 MB 起步 |
| 用 `pywin32` 替代 ctypes | 多一个依赖、多 5-8 MB，收益为零 |

---


## 3. 3.0 数据驱动皮肤包格式草案

### 3.1 设计目标

1. **新增一套皮肤 = 新增一个目录**，不改 Python；换装不重启（设置页切换）。
2. **玩法可组合**：兜帽升起时仍可戴面具、拿柠檬；状态机不写死组合。
3. **渲染器无关**：同一份 `skin.json` 既能给 P1 的 Python 渲染器，也能给 P4 的 C++ 渲染器。
4. **失败可回退**：JSON 坏了/图集缺了 → 记日志 + 回退内置皮肤，绝不让主程序崩。
5. **向后兼容**：旧素材通过 `legacy` 适配器进入同一套管线，P2 期间外观零变化。

### 3.2 目录约定

```
skins/
  futa_pajama_pink/            # 目录名 = id，[a-z0-9_]{2,32}
    skin.json                  # 唯一入口，UTF-8 无 BOM
    preview.png                # 256x256，设置页缩略图
    LICENSE.txt                # 素材授权，必填
    atlas/
      body.png                 # RGBA8，建议 1024x1024 或 2048x2048
      props.png                # 512x512
    audio/
      cloth.wav                # 16-bit PCM，<= 2s
      chomp.wav
    photo/
      polaroid.png             # 420x520 相框模板（含 alpha）
```

查找顺序（后者被前者覆盖，便于用户改皮肤）：内置 `assets/skins/<id>` → exe 同级 `skins/<id>` → `%LOCALAPPDATA%\FutaDesktopPet\skins\<id>`。

硬性约束：

- PNG 一律 RGBA8、直通 alpha（**不要预乘**，预乘在渲染器上传前做一次）。
- 图集建议 2 的幂、留 2px padding，避免采样渗色；同时为 P4 的 GPU 上传留余地。
- 路径只能是相对路径、不得含 `..`；文件名大小写敏感（打包到 zip 后也会一致）。

### 3.3 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `format` | int | ✅ | 当前 1；未来不兼容升 2，加载器只认 1 |
| `id` | string | ✅ | 唯一 id，与目录名一致 |
| `name` | string | ✅ | 展示名（中文） |
| `version` | semver | ✅ | 皮肤版本 |
| `author` | string | ✅ | 作者/团队 |
| `engine` | object | ✅ | `{ "min": "3.0" }`，低于此版本拒绝加载 |
| `canvas` | object | ✅ | 设计空间 `{w,h,anchor:[x,y]}`，推荐 300x450、anchor 底部中心 |
| `palette` | object | ⭕ | 命名色，供 `tint` 与描边引用 |
| `materials` | object | ⭕ | 毛绒/布料等材质参数（见 4.1） |
| `atlases` | array | ✅ | `[{id,file,w,h}]` |
| `parts` | object | ✅ | 部件表，见 3.4 |
| `attach` | object | ✅ | 命名锚点（设计空间像素），如 head/face/mouth/hand_r |
| `states` | object | ✅ | 状态机，见 3.5 |
| `transitions` | array | ✅ | 状态迁移规则 |
| `physics` | object | ⭕ | 道具物理参数 |
| `hit` | object | ⭕ | 命中掩码参数，缺省 `{mode:"alpha",threshold:24,downsample:4}` |
| `audio` | object | ⭕ | 事件 → 音频文件 + 音量 |
| `schedule` | array | ⭕ | 作息时间段与对应状态/色调 |
| `photo` | object | ⭕ | 拍立得模板与保存目录 |
| `behavior` | object | ⭕ | 眨眼/空闲超时/拖拽宽容度等引擎参数 |

### 3.4 部件、锚点与图层

`parts` 的每个条目：

```json
{
  "hood": {
    "atlas": "body",
    "frames": [[0, 900, 300, 300], [300, 900, 300, 300]],
    "pivot": [150, 40],
    "z": 30,
    "attach": "head",
    "material": "fluff",
    "visible": true,
    "hit": true,
    "mirror": true,
    "opacity": 1.0
  }
}
```

- `frames`：图集矩形数组 `[x,y,w,h]`，索引即状态关键帧里的 `frame`。
- `pivot`：部件自身的旋转/缩放中心（局部像素）。
- `attach`：贴到哪个命名锚点；未指定则按 `pivot` 直接落在设计空间。
- `z`：合成顺序。建议 shadow(0) < body(10) < hair(25) < hood(30) < mask(35) < lemon(50) < fx(90)。
- `mirror`：朝向翻转时是否镜像；文字、单侧徽章设 false。
- `material`：引用 `materials`，离线烘焙毛绒边缘/布料高光时使用。

坐标约定：设计空间左上角原点，单位 px；`anchor` 是角色脚底中心。运行时 `scale = window_h / canvas.h`，物理量（速度/重力）也在设计空间计算，渲染时再乘 scale，这样换尺寸不需要改参数。

### 3.5 状态机

状态字段：

| 字段 | 说明 |
|---|---|
| `loop` | true 时按 `duration` 循环；采样动画用 `fps` 控制节奏 |
| `fps` | 采样动画的采样率（如 idle 30、sleep 15） |
| `duration` | 一次性状态的时长（秒）；与 `loop` 二选一 |
| `ease` | 默认缓动：`linear/step/easeInOut/easeOutBack/spring` |
| `tracks` | 部件 → 关键帧数组 |
| `sound` | 进入状态时播放的音效 key |
| `onEnd` | 一次性状态结束后的目标状态 |
| `priority` | 数值大优先，用于抢占（如 wake 抢 sleep） |

关键帧字段：`t`（秒）、`frame`（帧索引）、`dx/dy`、`rot`、`scale`、`alpha`、`visible`、`ease`（覆盖默认）。

两条必须写进引擎的语义：

1. **进入状态时，未被该状态 track 的部件重置为部件声明的初始值**（frame 0、visible、alpha 1、offset 0）。需要保留时在状态上写 `"keep": true`，或在该状态里显式给一个单关键帧。否则「兜帽升起后切 idle」会残留偏移。
2. **迁移条件**：`on` 是引擎发出的事件名，不是代码回调。引擎内置事件：click、double_click、drag_start/drag_end、cursor_near/cursor_far、idle_5min/wake、schedule_enter/exit、dock/undock、bite_start/bite_end、lemon_throw。皮肤只能映射，不能新增（新增要改引擎，属于版本升级）。

过渡混合：`blend` 秒（缺省 0.15），实现为「进入时把前后两个状态的合成结果交叉淡化」。因为已经预烘焙，混合只是两张图的 `alpha_composite`，成本 0.64 ms/帧，持续 0.15 s 可接受；超过 0.5 s 的过渡改成逐帧烘焙。

### 3.6 变体、调色板与夜间模式

- `palette` 里的颜色名可以被 `tint` 引用；部件若提供灰度 mask，加载时用 `ImageOps.colorize(mask, black, color)` 重着色，**同一套线稿可以出粉/蓝/夜间三套配色**，不必画三遍。
- 夜间模式不新画素材：`schedule` 命中时叠加一层 `night` 色的半透明层（alpha 0.12-0.20）+ 切到 `sleep` 状态。
- 真正的换装（睡衣/常服）走 `variants`：`[{ "id":"pajama", "when":{...}, "parts":{...} }]`，加载时浅合并，不改变状态机。

### 3.7 命中掩码

- `hit.mode`：`alpha`（默认，按合成结果 alpha 阈值）、`rects`（显式矩形，兼容旧行为）、`both`。
- 掩码在「尺寸/朝向/状态变化」后重建：`alpha.point(lambda v: 255 if v >= 24 else 0)`（实测 0.10 ms），再按 `downsample=4` 缩成 75x113 的 1bpp 位图（约 8.5 KB），查询 O(1)。
- 毛绒外缘的 alpha 通常 20-80，阈值取 24-32 可以做到「看着软、点着准」；阈值本身放进 `skin.json`，方便按皮肤调。
- 部件级命中（兜帽/柠檬）用「部件掩码 ∩ 部件包围盒」，这样双击躯干不会误触兜帽。

### 3.8 最小示例（可直接 `json.loads`）

```json
{
  "format": 1,
  "id": "futa_pajama_pink",
  "name": "粉色毛绒连帽睡衣·福塔",
  "version": "1.0.0",
  "author": "art-team",
  "engine": { "min": "3.0" },
  "canvas": { "w": 300, "h": 450, "anchor": [150, 438] },
  "palette": {
    "fur": "#F6C6D6", "fur_hi": "#FFE9F0", "fur_sh": "#D897AC",
    "cloth": "#F3A9BF", "skin": "#F7D9C4", "lemon": "#F4D44D", "night": "#5A6FA8"
  },
  "materials": {
    "fluff": { "edge": "fur", "length": [2, 6], "density": 0.55,
               "softness": 2, "hi": "fur_hi", "shadow": "fur_sh" }
  },
  "atlases": [
    { "id": "body",  "file": "atlas/body.png",  "w": 1024, "h": 1024 },
    { "id": "props", "file": "atlas/props.png", "w": 512,  "h": 512 }
  ],
  "parts": {
    "shadow": { "atlas": "props", "frames": [[0, 0, 240, 60]],
                "pivot": [120, 30], "z": 0, "opacity": 0.35, "hit": false },
    "body":   { "atlas": "body",  "frames": [[0, 0, 600, 900], [600, 0, 600, 900]],
                "pivot": [300, 860], "z": 10, "material": "fluff" },
    "hood":   { "atlas": "body",  "frames": [[0, 900, 300, 300], [300, 900, 300, 300]],
                "pivot": [150, 40], "z": 30, "attach": "head", "material": "fluff" },
    "mask":   { "atlas": "props", "frames": [[0, 0, 200, 160]],
                "pivot": [100, 80], "z": 35, "attach": "face", "visible": false },
    "lemon":  { "atlas": "props", "frames": [[200, 0, 96, 96]],
                "pivot": [48, 48], "z": 50, "attach": "hand_r", "visible": false }
  },
  "attach": { "head": [150, 96], "face": [150, 128],
              "mouth": [128, 196], "hand_r": [232, 300] },
  "states": {
    "idle": { "loop": true, "fps": 30,
      "tracks": { "body": { "keys": [
        { "t": 0.0, "frame": 0 }, { "t": 0.6, "frame": 1 }, { "t": 1.2, "frame": 0 } ] } } },
    "idle_hooded": { "loop": true, "fps": 30,
      "tracks": { "hood": { "keys": [ { "t": 0, "frame": 1, "dy": -14 } ] },
                  "body": { "keys": [ { "t": 0, "frame": 0 }, { "t": 1.2, "frame": 1 } ] } } },
    "hood_up": { "loop": false, "duration": 0.55, "ease": "easeOutBack",
      "tracks": { "hood": { "keys": [
        { "t": 0.0, "frame": 0, "dy": 0 }, { "t": 0.55, "frame": 1, "dy": -14 } ] } },
      "sound": "cloth", "onEnd": "idle_hooded" },
    "hood_down": { "loop": false, "duration": 0.45,
      "tracks": { "hood": { "keys": [
        { "t": 0.0, "frame": 1, "dy": -14 }, { "t": 0.45, "frame": 0, "dy": 0 } ] } },
      "sound": "cloth", "onEnd": "idle" },
    "mask_on": { "loop": false, "duration": 0.30,
      "tracks": { "mask": { "keys": [
        { "t": 0.0, "visible": true, "alpha": 0.0 }, { "t": 0.3, "alpha": 1.0 } ] } },
      "onEnd": "idle_hooded" },
    "lemon_hold": { "loop": true, "fps": 30,
      "tracks": { "lemon": { "keys": [
        { "t": 0.0, "visible": true, "dy": 0 }, { "t": 0.8, "dy": 2 } ] } } },
    "sleep": { "loop": true, "fps": 15,
      "tracks": { "body": { "keys": [
        { "t": 0.0, "frame": 0, "dy": 0 }, { "t": 2.0, "frame": 1, "dy": 3 } ] } } }
  },
  "transitions": [
    { "from": "idle",         "to": "hood_up",   "on": "click_hood", "priority": 10 },
    { "from": "idle_hooded",  "to": "hood_down", "on": "click_hood", "priority": 10 },
    { "from": "*",            "to": "mask_on",   "on": "menu_mask",  "priority": 20 },
    { "from": "*",            "to": "sleep",     "on": "schedule_enter", "priority": 5 },
    { "from": "sleep",        "to": "idle",      "on": "wake",       "priority": 30,
      "interrupt": true }
  ],
  "physics": {
    "lemon": { "gravity": 1800, "damping": 0.12, "restitution": 0.35,
               "radius": 18, "grip": 60 }
  },
  "hit": { "mode": "alpha", "threshold": 24, "downsample": 4 },
  "audio": { "cloth": "audio/cloth.wav", "chomp": "audio/chomp.wav", "volume": 0.6 },
  "schedule": [
    { "from": "23:00", "to": "07:00", "state": "sleep", "tint": "night", "tintAlpha": 0.18 }
  ],
  "photo": { "frame": "photo/polaroid.png", "caption": true,
             "dir": "Pictures/福塔相册" }
}
```

这段 JSON 覆盖了「睡衣本体 / 兜帽升降 / 面具 / 柠檬手里拿 / 夜间睡眠」五个玩法，引擎侧不需要任何 if-skin 分支。

### 3.9 加载器与校验

```python
def load_skin(dir: Path) -> Skin:
    raw = json.loads((dir / "skin.json").read_text("utf-8"))
    if raw.get("format") != 1:
        raise SkinError("unsupported format")
    check_required(raw, ["id", "canvas", "atlases", "parts", "states", "transitions"])
    check_atlas_bounds(raw)                 # 每个 rect 必须落在图集内
    check_refs(raw)                         # attach/state/onEnd 引用必须存在
    check_paths(dir, raw)                   # 禁止 .. 与绝对路径
    skin = Skin(raw, base=dir)
    skin.prewarm()                          # 预乘、预缩放、烘焙毛绒
    return skin
```

- 校验失败 → 记录到 `%LOCALAPPDATA%\FutaDesktopPet\logs\skin.log`，回退 `default`，设置页显示「皮肤 xxx 加载失败」。
- 热重载：只在打开设置页时检查 `skin.json` 的 mtime，避免运行中每帧 stat。
- 版本兼容：未知字段一律忽略（前向兼容），未知 `format` 直接拒绝（后向不兼容）。
- 内存：图集懒加载，只解码当前皮肤用到的图集；切换皮肤时 `del` 旧 Skin 并 `gc.collect()`。

### 3.10 旧资源兼容（P2 的护城河）

`legacy` 适配器把现有资产包成隐式皮肤：

- `parts.body.frames` = `prepare_wings()` 产出的 60 帧（原 290x436）；
- `canvas` = 290x436，`anchor` = 底部中心；
- `attach.mouth` = (123,188)（对应 L384-L387 的硬编码）；
- `states.fly` = 60 帧循环，`states.idle` = 单帧；
- `hit.mode` = `rects`，矩形沿用 L370 的比例框。

这样 P2 可以先上「皮肤框架 + 新渲染器」，外观与行为完全不变；P3 再逐套替换成新美术。迁移期出问题，删掉新皮肤目录就能回到 2.0 观感。

---

## 4. 新技术点实现要点

### 4.1 程序化毛绒边缘

**目标**：不手绘每根毛，沿 alpha 轮廓生成 2-6px 的绒条，做出「软边绒毛」的实拍感。

**烘焙流程（只在尺寸/皮肤变化后做一次）**：

1. 取部件 alpha，阈值 32 得到二值轮廓；用 4 邻域判断提取边界像素（300x467 约 4-6k 个）。
2. 对 alpha 做 `GaussianBlur(3)`，用「原图 − 右移 1px / 下移 1px」的 `ImageChops.difference` 估梯度，得到每个边界点的外法线（比 Sobel 省事，实测一次模糊 2.8 ms）。
3. 沿法线撒 1-2 根短线：长度 `length=[2,6]`、角度 ±25°、alpha 60-160，颜色取 `hi` 向 `fur` 渐变；用固定种子（`random.Random(seed)`）保证同一尺寸下可复现。
4. 叠加「软边层」：`blur(alpha, 1.5) − alpha` 得到的 1-2px 半透明内描边，压住锯齿。
5. 结果是一张与角色同尺寸的 RGBA `fur` 层，合成时 `alpha_composite` 到 body 之上（+0.64 ms/帧，可缓存）。

**动画**：不要每帧重算（30-80 ms，直接卡死）。预烘 4 个「风相位」变体，8fps 轮播 + 0.1s 交叉淡化；或整层做 ±1px 的正弦偏移（约 0.01 ms），远看足够。

**关键 API**：`ImageFilter.GaussianBlur`、`ImageChops.difference/lighter`、`ImageDraw.line(width=1)`、`Image.point`。上传前统一预乘。

**命中**：绒毛 alpha 低，掩码阈值取 32，避免「点空气也算点中」。

### 4.2 兜帽升降

**推荐做法：两帧替换 + 位移插值 + 交叉淡化**，而不是实时遮罩。美术只需交付「戴帽 / 摘帽」两张（可选一张中间帧），引擎在 0.45-0.6 s 内完成：

- `hood` 部件 `frames[0]=down`、`frames[1]=up`，关键帧 `dy: 0 → -14`，缓动 `easeOutBack` 给出毛绒的回弹感。
- 图层顺序 `hair(25) < hood(30)`，兜帽天然盖住头发；兜帽开口在美术里挖透明洞，露脸不需要运行时裁剪。若必须裁剪，再给 hood 配一张 `clip` 灰度图，逐帧 `Image.composite`。
- 过渡在进入状态时预烘 12-15 帧（22-25fps），成本约 17 ms，一次性；之后只是查表。
- 中间帧的「翻折」用 `alpha` 交叉 + `dy` 插值即可；两帧直接硬切会在 0.2 s 处跳变，务必淡化。
- 触发：点击 hood 部件的命中掩码（不是整窗），300 ms 冷却；状态写入 settings 的 `hood: "up"|"down"`，下次启动保持。
- 音效：`cloth.wav` 在 t=0.05 播放，音量 0.5；与状态机 `sound` 字段绑定。

### 4.3 手持柠檬的简易物理

数据（`physics.lemon`）：`gravity=1800 px/s²`、`damping=0.12/s`、`restitution=0.35`、`radius=18`、`grip=60`。

- **积分**：固定子步 1/120 s，累加器最多补 4 步（防 spiral of death）；`v += g*dt`、`v *= exp(-damping*dt)`、`p += v*dt`。
- **手持**：弹簧拉向 `hand_r` 锚点，`a = k*(anchor-p) - c*v`，`k=60`、`c=12`（接近临界阻尼），走动时自然摆动；`grip` 控制跟随强度。
- **抛出**：记录手部最近 3 帧位移求速度，`v_throw = hand_v*1.2 + random(-80,80)`，角速度 `ω = vx/radius`，落地 `restitution` 反弹、`|v|<20` 休眠。
- **咬住**：柠檬中心到 `mouth` 锚点 < 24px 时切 `lemon_bitten`，钉在嘴上 3 s 后吐出；与 `chase/carry` 状态机共用同一套锚点。
- **碰撞**：只和显示器工作区并集（复用 `covered` 的矩形集合）碰撞；若已停靠某窗口，把该窗口矩形也加入碰撞集。
- 所有量在设计空间计算，渲染时乘 `scale`；换尺寸不需要重调参数。

### 4.4 停靠在窗口边缘

- **枚举**：`EnumWindows` + 过滤 `IsWindowVisible`、`!IsIconic`、标题非空、`!(exstyle & WS_EX_TOOLWINDOW)`、非本进程、排除 `Progman/WorkerW/Shell_TrayWnd`。
- **真实边框**：`DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS=9, &rect, 16)`。Win10 1607+ 返回「可见边框」，比 `GetWindowRect` 少了四周不可见的 resize 边，吸附不会留缝。
- **吸附**：宠物矩形外扩 24px 与窗口四边求最近距离，<24px 则贴边并留 6-8px 间隙；记录 `hwnd + edge`。
- **重评估**：拖动结束、前台窗口变化、每 500 ms 轮询 `IsWindow`/`GetWindowRect`；`IsIconic` → 解除停靠并播「掉落」动画；窗口销毁 → 静默解除。
- **可选实时**：`SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE=0x800B, WINEVENT_OUTOFCONTEXT)`，但 Tk 循环对 WinEvent 回调的投递没有保证，**以轮询为主、hook 为辅**。
- 坐标一律物理像素（PMv2），停靠到副屏时让现有 `flight_step` 负责飞过去。

### 4.5 空闲检测与作息

- **空闲**：`LASTINPUTINFO{cbSize=8, dwTime}` + `GetLastInputInfo`；`idle = (GetTickCount64() & 0xFFFFFFFF) - dwTime`，按 32 位取模再算，避免 49.7 天回绕；1 s 轮询一次。
- **作息**：本地时间落在 `schedule` 窗口（如 23:00-07:00）→ 切 `sleep` + 夜间 tint；早晨首次唤醒播「早安」并写 `last_greet`，一天一次。
- **全屏/演示**：`SHQueryUserNotificationState` 返回 `QUNS_RUNNING_D3D_FULL_SCREEN(3)` 或 `QUNS_PRESENTATION_MODE(4)` 时暂停动画并隐藏，避免盖住游戏/PPT。
- **锁屏**：`WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)` 收 `WM_WTSSESSION_CHANGE`；不想引 wtsapi32 就轮询 `OpenInputDesktop`。
- **唤醒**：从 sleep 出来先伸懒腰（1.2 s 一次性状态）再回 idle，不要瞬间跳回；`behavior.idle_timeout` 可配（默认 300 s）。

### 4.6 拍立得拍照

- **截取**：渲染管线保留最近一帧「直通 alpha」的 `Image`（预乘前的引用，不拷贝），拍照时直接拿来合成——只包含宠物图层，**绝不截桌面**。
- **合成**：`photo.polaroid.png` 模板 + 宠物缩放 0.8 + 白边 + 2-4° 随机旋转 + 日期文字；字体用 `C:\Windows\Fonts\msyh.ttc`（实测存在），字号随模板缩放。
- **保存**：`SHGetKnownFolderPath(FOLDERID_Pictures)`（GUID `{33E28130-4E1E-4676-835A-98395C3BC3BB}`）→ 子目录 `福塔相册`；PNG 实测 25.8 ms / 155 KB，放后台线程；要更小可 WebP q90（14.9 ms / 33 KB）。
- **展示**：独立的 layered 小窗，从宠物旁 120 ms 滑出 + 淡入；点击用 `ShellExecuteW` 打开资源管理器并选中文件。
- **命名**：`Futa_20261107_215612.png`，冲突时加 `_1`。

---


## 5. 性能预算与风险

### 5.1 帧预算（300x467，60fps，16.67 ms）

| 阶段 | 2.0 现状 | 3.0 目标 | 说明 |
|---|---|---|---|
| 状态机 + 输入 | ~0.02 ms | 0.1 ms | 纯 Python，可忽略 |
| 道具物理 | 0 | 0.1 ms | 固定子步，最多 4 次 |
| 图层合成 | 0.64-2.5 ms | 0-0.64 ms | 预烘焙后 0；仅道具/兜帽变化时合成 |
| 缩放 | 3.84 ms | 0 | 尺寸稳定后预缩放 |
| 预乘 + 转 BGRA | 0 | 0.77 ms | 实测 |
| 上传/present | 1.20 ms（PhotoImage） | 1.5-2.0 ms（ULW，估算） | P0 spike 必须实测 |
| **合计** | **5.0-6.5 ms（30-39%）** | **2.4-3.6 ms（14-22%）** | 单核占用 |

结论：3.0 的预算目标是「稳态 ≤ 4 ms/帧、P99 ≤ 8 ms」，剩下 8 ms 留给 DWM 合成、GC 和系统抖动。如果 P0 实测 ULW 超过 4 ms，就退回「每 2 帧上传一次 + 中间帧只移动 ptDst」，视觉上仍是 60fps 的位置更新。

### 5.2 缓存策略

| 层 | 内容 | 容量 | 失效条件 |
|---|---|---|---|
| L0 | 图集解码结果（只读） | 4-16 MB | 换皮肤 |
| L1 | 设计尺寸源帧（60 帧） | ~30 MB | 换皮肤/换动作集 |
| L2 | 当前 size/DPI/朝向的合成帧 | 字节预算 48 MB，LRU | 尺寸/DPI/朝向/状态变化 |
| L3 | 预乘 BGRA 上传缓冲 | 1 张 DIB（547 KB） | 尺寸变化 |

- **预烘焙时机**：尺寸拖动结束 200 ms 后，分片烘焙（每片 4 帧，`root.after(1)` 让出事件循环），避免 60×3.84 ≈ 230 ms 的卡顿。烘焙期间继续用最近邻放大顶替。
- **朝向**：左右翻转各一份会让 L2 翻倍。实测翻转只要 0.047 ms，建议只缓存当前朝向，转身时重建（或只预烘「静止 + 飞行」两套关键帧）。
- **降频**：静止 30fps、睡眠 15fps、被遮挡/全屏 0fps；`timeBeginPeriod(1)` 只在 ≥30fps 时开启，静止 3 s 后 `timeEndPeriod(1)`。
- **禁止**：每帧 `CreateDIBSection`、每帧 PNG 编解码、每帧重新 `ImageTk.PhotoImage`、无上限的 dict 缓存。

### 5.3 主要风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | Tk 主循环不派发自建 hwnd 消息 | 低 | 高（B 方案要改线程模型） | P0 30 行 spike 先验证；失败则独立线程 + 队列 |
| 2 | 预乘/色彩空间错误 | 中 | 中（边缘发白/发黑） | 单元测试：已知 alpha 的 4x4 图，断言像素值 |
| 3 | 软边 alpha 1-23 挡住桌面点击 | 高 | 中 | NCHITTEST 阈值 24 + 动态 WS_EX_TRANSPARENT 兜底 |
| 4 | 混合 DPI 下坐标错位 | 中 | 高 | 全链路物理像素；WM_DPICHANGED 重建；双屏 125%+150% 必测 |
| 5 | 预烘焙造成 200 ms 卡顿 | 中 | 中 | 分片 + 占位帧；尺寸拖动时用 BILINEAR/NEAREST |
| 6 | 内存随尺寸膨胀（700px 时 2.85 MB/帧） | 中 | 中 | L2 按 MB 预算而非帧数；超过 96 MB 降级为 30 帧 |
| 7 | 全屏游戏/演示被遮挡 | 中 | 高 | SHQueryUserNotificationState + 前台窗口全屏检测，自动隐藏 |
| 8 | 皮肤 JSON 错误导致启动崩溃 | 中 | 高 | 严格校验 + 回退 default + 日志；启动路径 try/except |
| 9 | 毛绒烘焙在低端机超时 | 中 | 中 | 后台线程 + 超时降级为硬边；缓存到磁盘（按 size 命名） |
| 10 | PyInstaller onefile 被杀软误报 | 中 | 中 | 3.0 建议改 onedir；或换 Nuitka；签名 |
| 11 | GetLastInputInfo 在 RDP/服务会话失真 | 低 | 低 | 叠加 WTS 会话状态；失败时按时间表走 |
| 12 | 移动用户光标引发投诉 | 中 | 中 | 默认关闭「咬光标拖动」，首次弹提示 |

### 5.4 验收清单

- [ ] 60fps 下 `present` P99 < 4 ms，整帧 P99 < 8 ms（`QueryPerformanceCounter` 采样 10 分钟）。
- [ ] 300x467 与 700x1068 两档内存 < 150 MB；切换尺寸 3 次无泄漏（`GetGuiResources` 稳定）。
- [ ] 双屏 100%+150% 混合 DPI：宠物跨屏不模糊、不跳位、不缩放错。
- [ ] alpha=0 区域点击可穿透到桌面图标；绒毛边缘 24 阈值内可点中。
- [ ] 皮肤加载失败自动回退，主程序不崩；日志有可读原因。
- [ ] 兜帽/面具/柠檬/停靠/作息/拍照六项各有一条自动化或半自动回归脚本。
- [ ] 异常自愈：人为在 `animate` 里抛异常，300 ms 内恢复渲染。

---

## 附录 A：Win32 / Python API 速查

| 用途 | API | 备注 |
|---|---|---|
| 逐像素透明窗口 | `CreateWindowExW(WS_EX_LAYERED, ...)` + `UpdateLayeredWindow(ULW_ALPHA)` | 预乘 BGRA；与 SetLayeredWindowAttributes 互斥 |
| 独立 DIB | `CreateDIBSection`（biHeight 取负） | 一次创建，复用 bits |
| 命中穿透 | `WM_NCHITTEST` → `HTTRANSPARENT` | alpha 阈值 24；跨进程兜底 WS_EX_TRANSPARENT |
| DPI | `SetProcessDpiAwarenessContext(-4)`、`GetDpiForWindow`、`WM_DPICHANGED` | 必须在创建任何窗口前调用 |
| 显示器工作区 | `EnumDisplayMonitors` + `GetMonitorInfoW` | 已在用，4.4 µs/次 |
| 窗口真实边框 | `DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS)` | 9；排除 cloaked(14) |
| 空闲 | `GetLastInputInfo` + `GetTickCount64` | 32 位回绕处理 |
| 全屏/演示 | `SHQueryUserNotificationState` | 3/4 时隐藏 |
| 锁屏 | `WTSRegisterSessionNotification` | 需 wtsapi32 |
| 图片目录 | `SHGetKnownFolderPath(FOLDERID_Pictures)` | 再拼 `福塔相册` |
| 光标 | `GetCursorPos` / `SetCursorPos` | 后者慎用，需用户同意 |

## 附录 B：待确认问题

1. 3.0 是否必须保留 60fps？如果接受 30fps，预算直接翻倍，很多优化可以不写。
2. 参考照片的版权/角色授权是否清晰？毛绒造型需要重新绘制，不能直接描照片。
3. 「咬光标」是否保留？如果保留，是否接受默认关闭 + 首次提示？
4. 皮肤是否需要用户可安装（下载 zip）？如果要，得加签名/校验与沙箱路径检查。
5. 是否要求单 exe 无 Python 运行时？如果是，P4 的优先级要提前。

---

*本文所有性能数字来自本机单次采样（40 次均值），生产前需在目标机型（低端核显笔记本 + 4K 屏）复测。*
