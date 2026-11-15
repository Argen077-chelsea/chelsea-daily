"""director skill — ช็อตสินค้า 3D แบบพรีเมียม (Blender Cycles) → MP4 พร้อมใช้เป็นบีต หรือเป็น <video> ในการ์ด

    blender -b -P scripts/product_shot.py -- OUT.mp4 --shot macro-pull|detail|orbit|hero [ตัวเลือก]

สินค้า (เลือกหนึ่ง):
  (ไม่ใส่)            แหวนอัจฉริยะในตัว — ปรับด้วย --finish --seam --led
  --model FILE         โมเดลของผู้ใช้ .glb/.gltf/.obj/.fbx (จัดกลาง + ย่อให้พอดีเอง) · ไลเซนส์ต้องใช้ได้ → จดใน CREDITS

ช็อต (กล้องคำนวณจากขนาดสินค้า ใช้ได้กับทุกโมเดล):
  macro-pull   เริ่มมาโครชิดผิว ไหลตามโค้ง → ถอยออกเห็นทั้งชิ้นหน้าตรง (ช่องกลางว่างให้วางคำ) — ฮุก/เปิดตัว
  detail       จากหน้าตรง ดันเข้าไปที่จุดเด่น (แหวน: เซนเซอร์ด้านใน ไฟเขียวเต้น 2 ครั้งแล้วบาน) — ส่งต่อไปการ์ดตัวเลข
  orbit        หน้าตรง → หมุนรอบตัว 1 รอบ → หน้าตรง (ขนาดเท่าเดิม = ต่อการ์ดถัดไปแบบ match cut ได้)
  hero         สามส่วนสี่ ดันเข้าช้า 2%/วิ — ช็อตค้าง/พื้นหลังตัวหนังสือ

ตัวเลือก:
  --s 2.5            ความยาว (วิ) · 30 fps
  --fill 0.6         ตอนจบ สินค้ากว้างกี่ส่วนของความกว้างเฟรม (ใช้จับคู่ขนาดกับวงเกจ/โลโก้ในการ์ดถัดไป)
  --size-mm 24       ขนาดจริงของสินค้า (มม.) — มีผลกับระยะชัด: ของเล็ก = ชัดตื้นแบบมาโคร
  --finish titanium|black|silver|gold|ceramic   วัสดุแหวนในตัว (โมเดลของผู้ใช้ใช้วัสดุของมันเอง)
  --seam "#ffc890"   เส้นไฟที่ขอบแหวน ("" = ไม่มี) · --led "#22ff66" ไฟเซนเซอร์ ("" = ไม่มี)
  --bg "#3e4249"     สีกลางของฉากหลัง (ขอบมืดลงเอง) · --aspect 9:16|16:9|1:1|4:5
  --exposure 0       EV ทั้งภาพ — ไฟตั้งมาสำหรับโลหะเข้ม: ของสีสว่าง/พลาสติก/ผ้า มักต้อง -1 ถึง -2 (ดูจาก --stills)
  --res 0.5          สัดส่วนความละเอียด (ร่าง 0.35–0.5 · ตัวจริง 1) · --samples 24 (ร่าง 16–24 · ตัวจริง 64–128)
  --stills           render แค่ 3 เฟรม (ต้น กลาง จบ) เป็น OUT-still-N.png — ดูทิศทางก่อน render ทั้งช็อต (~10–30 วิ)

เวลา (M1, 9:16): ร่าง --res 0.35 --samples 16 ≈ 1–2 วิ/เฟรม · ตัวจริง --res 1 --samples 64 ≈ 10–20 วิ/เฟรม
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv or argv[0].startswith("--"):
    sys.exit(__doc__)
OUT = os.path.abspath(argv[0])


def opt(k, d):
    return argv[argv.index(k) + 1] if k in argv else d


SHOT = opt("--shot", "macro-pull")
SECS = float(opt("--s", "2.5")); FPS = 30; N = max(2, round(SECS * FPS))
FILL = float(opt("--fill", "0.6")); SIZE = float(opt("--size-mm", "24")) / 1000.0
RES = float(opt("--res", "0.5")); SAMPLES = int(opt("--samples", "24"))
ASPECT = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}[opt("--aspect", "9:16")]
MODEL = opt("--model", "")


def hex2lin(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, N
rig = bpy.data.objects.new("rig", None); sc.collection.objects.link(rig)      # สินค้าทั้งชิ้นอยู่ใต้ rig — หมุน rig = หมุนสินค้า


def mat(name, col, metal=0.0, rough=0.3, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat; b.inputs["Coat Roughness"].default_value = 0.05
    return m


def emit(name, col, s):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs["Color"].default_value = (*col, 1); e.inputs["Strength"].default_value = s
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(e.outputs[0], o.inputs[0]); return m, e


def key(o, path, f, v):
    setattr(o, path, v); o.keyframe_insert(path, frame=f)


def kval(sock, f, v):
    sock.default_value = v; sock.keyframe_insert("default_value", frame=f)


# --- สินค้า: ขนาดรวม (เส้นผ่านศูนย์กลางนอก / ด้านยาวสุด) = 1 หน่วย แล้วย่อ rig ให้เท่าขนาดจริง (SIZE เมตร)
seam_e = led_e = None
DETAIL = (0.0, 0.0, 0.0)          # จุดที่ช็อต detail ดันเข้าไป (หน่วยสินค้า)
if MODEL:
    ext = os.path.splitext(MODEL)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=os.path.abspath(MODEL))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=os.path.abspath(MODEL))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=os.path.abspath(MODEL))
    else:
        sys.exit(f"ไม่รู้จักไฟล์โมเดล {ext} — ใช้ .glb .gltf .obj .fbx")
    objs = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in objs if o.type == "MESH" for v in o.data.vertices]
    if not pts:
        sys.exit("โมเดลไม่มี mesh")
    lo = [min(p[i] for p in pts) for i in range(3)]; hi = [max(p[i] for p in pts) for i in range(3)]
    c = [(lo[i] + hi[i]) / 2 for i in range(3)]; s = 1.0 / max(hi[i] - lo[i] for i in range(3))
    holder = bpy.data.objects.new("model", None); sc.collection.objects.link(holder)
    holder.location = (-c[0] * s, -c[1] * s, -c[2] * s); holder.scale = (s, s, s); holder.parent = rig
    for o in objs:
        if o.parent is None:
            o.parent = holder
    t = opt("--target", "0,0,0").split(","); DETAIL = tuple(float(x) * 0.5 for x in t)   # --target -1..1 ต่อแกน (ขอบกล่องโมเดล)
else:
    RO = 0.5; WALL = 0.105; W = 0.33; RI = RO - WALL          # ส่วนของแหวนจริง: กว้าง 24 มม. ผนัง 2.6 มม. หน้ากว้าง 8 มม.
    finish = {"titanium": ((0.045, 0.045, 0.05), 1.0, 0.16, 0.7), "black": ((0.012, 0.012, 0.014), 0.9, 0.22, 1.0),
              "silver": ((0.6, 0.6, 0.62), 1.0, 0.12, 0.3), "gold": ((0.85, 0.55, 0.25), 1.0, 0.14, 0.3),
              "ceramic": ((0.8, 0.8, 0.78), 0.0, 0.2, 1.0)}[opt("--finish", "titanium")]
    bpy.ops.mesh.primitive_torus_add(major_radius=RI + WALL / 2, minor_radius=WALL / 2, major_segments=200, minor_segments=48,
                                     rotation=(math.radians(90), 0, 0))
    band = bpy.context.object; band.scale = (1, 1, W / WALL); bpy.ops.object.shade_smooth(); band.parent = rig
    band.data.materials.append(mat("finish", finish[0], finish[1], finish[2], finish[3]))
    if opt("--seam", "#ffc890"):
        bpy.ops.mesh.primitive_torus_add(major_radius=RI + WALL * 0.5, minor_radius=0.009, major_segments=200, minor_segments=12,
                                         location=(0, -W / 2 + 0.005, 0), rotation=(math.radians(90), 0, 0))
        seam = bpy.context.object; sm, seam_e = emit("seam", hex2lin(opt("--seam", "#ffc890")), 3.5); seam.data.materials.append(sm); seam.parent = rig
    if opt("--led", "#22ff66"):
        glass = mat("sensor", (0.01, 0.012, 0.015), 0.0, 0.05, 1.0)
        lm, led_e = emit("led", hex2lin(opt("--led", "#22ff66")), 30)
        for k, ang in enumerate((-115, -90, -65)):
            a = math.radians(ang); r = RI - 0.008
            bpy.ops.mesh.primitive_cube_add(size=1, location=(r * math.cos(a), 0, r * math.sin(a)), rotation=(0, -a + math.pi / 2, 0))
            w = bpy.context.object; w.scale = (0.115 if k == 1 else 0.075, 0.17, 0.03); w.parent = rig
            bv = w.modifiers.new("b", "BEVEL"); bv.width = 0.014; bv.segments = 8; w.modifiers.new("s", "SUBSURF").levels = 2
            w.data.materials.append(glass)
            if k == 1:
                for dy in (-0.045, 0.045):
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.017, location=((r - 0.016) * math.cos(a), dy, (r - 0.016) * math.sin(a)))
                    o = bpy.context.object; o.data.materials.append(lm); o.parent = rig
    DETAIL = (0.0, 0.0, -RI + 0.03)
rig.scale = (SIZE, SIZE, SIZE)

# --- ฉาก: โลกเกือบดำ + ฉากหลังไล่สีวงกลม (กลางสว่าง ขอบมืด) + ไฟสตูดิโอ 3 ดวง (แถบยาว = เส้นสว่างเส้นเดียวบนโลหะ)
wd = bpy.data.worlds.new("w"); sc.world = wd; wd.use_nodes = True
wd.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.0035, 0.005, 1)
bpy.ops.mesh.primitive_plane_add(size=25 * SIZE, location=(0, 5 * SIZE, 0), rotation=(math.radians(90), 0, 0))
bg = bpy.context.object; m = bpy.data.materials.new("bg"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / (13 * SIZE),) * 3
gr = nt.nodes.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
cr = nt.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = (0, 0, 0, 1); cr.color_ramp.elements[1].color = (*hex2lin(opt("--bg", "#3e4249")), 1)
em = nt.nodes.new("ShaderNodeEmission"); ou = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(tc.outputs["Object"], mp.inputs[0])
nt.links.new(mp.outputs[0], gr.inputs[0]); nt.links.new(gr.outputs[0], cr.inputs[0]); nt.links.new(cr.outputs[0], em.inputs[0])
nt.links.new(em.outputs[0], ou.inputs[0]); bg.data.materials.append(m)


def area(name, loc, energy, size, sy=None, col=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA"); d.energy = energy * (SIZE / 0.024) ** 2; d.color = col
    if sy:
        d.shape = "RECTANGLE"; d.size = size * SIZE / 0.024; d.size_y = sy * SIZE / 0.024
    else:
        d.size = size * SIZE / 0.024
    o = bpy.data.objects.new(name, d); o.location = tuple(x * SIZE / 0.024 for x in loc); sc.collection.objects.link(o)
    o.constraints.new("TRACK_TO").target = rig


area("strip", (-0.08, -0.10, 0.12), 3.0, 0.006, 0.25)                 # key: แถบยาวบาง = ไฮไลต์เส้นเดียวพาดโลหะ
area("rim", (0.10, 0.08, 0.06), 2.0, 0.08, col=(0.75, 0.85, 1.0))    # ขอบหลังสีเย็น แยกของออกจากฉาก
area("under", (0.02, -0.06, -0.12), 0.4, 0.15)                       # เติมเงาล่างนิดเดียว

# --- กล้อง: sensor_fit แนวนอน → ความกว้างภาพที่ระยะ d = 36/lens·d · จบที่สินค้ากว้าง FILL ของเฟรม
cd = bpy.data.cameras.new("cam"); cd.sensor_fit = "HORIZONTAL"; cd.sensor_width = 36; cd.clip_start = SIZE * 0.02; cd.clip_end = SIZE * 100
cd.dof.use_dof = True
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
aim = bpy.data.objects.new("aim", None); sc.collection.objects.link(aim); cd.dof.focus_object = aim
cam.constraints.new("TRACK_TO").target = aim
U = lambda *v: tuple(x * SIZE for x in v)                               # noqa: E731 — หน่วยสินค้า → เมตร
D_END = 1.0 / FILL * 85 / 36                                           # ระยะกล้อง (หน่วยสินค้า) ที่เลนส์ 85 ให้กว้าง FILL
END_ROT = (math.radians(6), 0, math.radians(-12))
M = N // 2 + 1
if SHOT == "macro-pull":
    key(rig, "rotation_euler", 1, (math.radians(8), 0, math.radians(-58))); key(rig, "rotation_euler", N, END_ROT)
    key(cam, "location", 1, U(0.5, -0.83, 1.07)); key(cam, "location", M, U(0.17, -1.32, 0.79)); key(cam, "location", N, U(0, -D_END, 0))
    key(aim, "location", 1, U(0.17, -0.08, 0.49)); key(aim, "location", M, U(0.06, -0.04, 0.33)); key(aim, "location", N, U(0, 0, 0))
    key(cd, "lens", 1, 100); key(cd, "lens", N, 85)
    key(cd.dof, "aperture_fstop", 1, 11.0); key(cd.dof, "aperture_fstop", N, 8.0)
    if seam_e:                                                          # เส้นไฟติดขึ้นระหว่างกล้องไหล
        kval(seam_e.inputs["Strength"], 1, 0.0); kval(seam_e.inputs["Strength"], max(2, N // 3), 3.0)
elif SHOT == "detail":
    key(rig, "rotation_euler", 1, END_ROT); key(rig, "rotation_euler", N, (0, 0, math.radians(-10)))
    tx, ty, tz = DETAIL
    key(cam, "location", 1, U(0, -D_END, 0)); key(cam, "location", M, U(tx * 0.5, -1.24, tz * 0.5)); key(cam, "location", N, U(tx, -0.29, tz + 0.22))
    key(aim, "location", 1, U(0, 0, 0)); key(aim, "location", M, U(tx * 0.6, 0.04, tz * 0.6)); key(aim, "location", N, U(tx, 0.0, tz))
    key(cd, "lens", 1, 85); key(cd, "lens", N, 32)
    key(cd.dof, "aperture_fstop", 1, 8.0); key(cd.dof, "aperture_fstop", N, 2.8)
    if led_e:                                                           # ไฟเต้น 2 ครั้ง แล้วบาน (ส่งต่อไปการ์ดตัวเลข)
        q = N / 60
        for f, v in ((1, 30), (16, 30), (20, 160), (25, 8), (32, 8), (36, 160), (41, 8), (48, 8), (60, 260)):
            kval(led_e.inputs["Strength"], max(1, round(f * q)), v)
elif SHOT == "orbit":
    cam.location = U(0, -D_END, 0); aim.location = (0, 0, 0); cd.lens = 85; cd.dof.aperture_fstop = 8.0
    key(rig, "rotation_euler", 1, (0, 0, 0)); key(rig, "rotation_euler", M, (math.radians(-14), 0, math.radians(-180)))
    key(rig, "rotation_euler", N, (0, 0, math.radians(-360)))
elif SHOT == "hero":
    rig.rotation_euler = (math.radians(-18), 0, math.radians(-38)); cd.lens = 70; cd.dof.aperture_fstop = 4.0
    d0 = D_END * 70 / 85
    key(cam, "location", 1, U(0.3, -d0, 0.25)); key(cam, "location", N, U(0.3 * 0.98, -d0 * (1 - 0.02 * SECS), 0.25 * 0.98))
    aim.location = (0, 0, 0)
else:
    sys.exit(f"ไม่รู้จักช็อต {SHOT} — macro-pull | detail | orbit | hero")

sc.render.engine = "CYCLES"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.use_persistent_data = True                                   # ไม่สร้างฉากใหม่ทุกเฟรม — เร็วขึ้นมาก
try:
    sc.cycles.denoising_use_gpu = True                                 # ลดนอยส์บน GPU (CPU คือคอขวดเดิม ~3 วิ/เฟรม)
except Exception:
    pass
sc.render.use_motion_blur = SHOT != "hero"
try:                                                                    # GPU ถ้ามี (Mac = METAL) — ไม่มีก็ใช้ CPU
    pr = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("METAL", "OPTIX", "CUDA"):
        try:
            pr.compute_device_type = dev; pr.get_devices()
            gpus = [d for d in pr.devices if d.type == dev]
            if not gpus:
                continue
            for d in pr.devices:
                d.use = True
            sc.cycles.device = "GPU"; print("Cycles GPU:", dev); break
        except Exception:
            continue
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = ASPECT; sc.render.resolution_percentage = max(10, int(RES * 100))
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = float(opt("--exposure", "0"))
sc.render.image_settings.file_format = "PNG"

if "--stills" in argv:
    for i, f in enumerate((1, M, N), 1):
        sc.frame_set(f); sc.render.filepath = OUT.rsplit(".", 1)[0] + f"-still-{i}.png"; bpy.ops.render.render(write_still=True)
        print("still", sc.render.filepath)
    sys.exit(0)

tmp = tempfile.mkdtemp(prefix="shot-")
for f in range(1, N + 1):
    sc.frame_set(f); sc.render.filepath = f"{tmp}/f_{f:04d}.png"; bpy.ops.render.render(write_still=True)
ff = shutil.which("ffmpeg") or next((p for p in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if os.path.exists(p)), "ffmpeg")
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
w, h = ASPECT
subprocess.run([ff, "-v", "error", "-y", "-framerate", str(FPS), "-i", f"{tmp}/f_%04d.png", "-vf", f"scale={w}:{h}:flags=lanczos",
                "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", OUT], check=True)
shutil.rmtree(tmp, ignore_errors=True)
print(f"{OUT}  ({N} เฟรม · {SECS:g} วิ · {SHOT})")
