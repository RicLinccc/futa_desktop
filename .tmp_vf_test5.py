import sys, time
sys.path.insert(0, r"E:\CppProject\futa_desktop\src")
import futa_pet

app = futa_pet.FutaPet()
app.moving.set(False)
app.open_viewfinder()
app.root.update()
win = app._viewfinder
win.geometry("+80+120")
app.root.update(); time.sleep(0.2); app.root.update()
canvas = win.winfo_children()[0]
w, h = win.winfo_width(), win.winfo_height()
target = None
for item in canvas.find_all():
    c = canvas.coords(item)
    if len(c) == 4 and abs(c[0] - (w - 17)) < 3 and abs(c[1] - (h - 17)) < 3:
        target = item; break
print("before", win.winfo_width(), win.winfo_height(), "handle", target)
if target:
    c = canvas.coords(target)
    cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
    rx, ry = win.winfo_x() + cx, win.winfo_y() + cy
    canvas.event_generate("<ButtonPress-1>", x=int(cx), y=int(cy), rootx=int(rx), rooty=int(ry), when="now")
    canvas.event_generate("<B1-Motion>", x=int(cx + 90), y=int(cy + 70), rootx=int(rx + 90), rooty=int(ry + 70), when="now")
    app.root.update()
print("after", win.winfo_width(), win.winfo_height())
img = app.grab_region(60, 100, 880, 940)
img.convert("RGB").save(r"E:\CppProject\futa_desktop\.tmp_vf_resize.png")
app.close()
print("OK")
