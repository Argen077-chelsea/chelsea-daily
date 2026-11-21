"""ถอดเสียงพากย์ด้วย Gemini (endpoint เข้ากันได้กับ OpenAI) — คีย์ถูกฉีดโดย proxy ไม่อยู่ในโค้ด
python3 -I tools/transcribe_gemini.py AUDIO.mp3 OUT.txt [MODEL]"""
import sys, json, base64, urllib.request
audio, out = sys.argv[1], sys.argv[2]
model = sys.argv[3] if len(sys.argv) > 3 else "gemini-2.5-flash"
b64 = base64.b64encode(open(audio, "rb").read()).decode()
prompt = ("ถอดเสียงภาษาไทยในไฟล์นี้ทุกคำตามที่ได้ยินจริง ห้ามแก้หรือเดาให้ตรงกับบทใด ๆ ชื่อเฉพาะให้ถอดตามเสียงที่ได้ยิน "
          "แบ่งเป็นบรรทัดตามประโยคหรือวลี ขึ้นต้นแต่ละบรรทัดด้วยเวลาเริ่มเป็นวินาที เช่น [12.5] ข้อความ")
body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
    {"type": "text", "text": prompt},
    {"type": "input_audio", "input_audio": {"data": b64, "format": "mp3"}}]}]}
req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                             data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer proxy-injected"})
try:
    d = json.load(urllib.request.urlopen(req, timeout=300))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read()[:500].decode(errors='replace')}")
open(out, "w").write(d["choices"][0]["message"]["content"])
print("ok", out)
