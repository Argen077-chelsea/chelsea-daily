import json
B = json.load(open("tools/bounds.json"))
CSS = """
html,body{margin:0;background:#021a45}
#root{position:relative;overflow:hidden;background:radial-gradient(120% 90% at 50% 40%,#0a4aa8 0%,#034694 38%,#021a45 88%);font-family:"Prompt",sans-serif;color:#fff}
.sc{position:absolute;left:0;top:0;width:1920px;height:1080px}
.a{position:absolute;white-space:nowrap}
.c{left:0;right:0;text-align:center}
.tag{left:120px;top:80px}.tag span,.pill span{display:inline-block;background:#f2b705;color:#0b1a3a;font-weight:800;font-size:44px;line-height:1.4;padding:8px 40px;border-radius:60px}
.pill{left:0;right:0;text-align:center}
.h1{font-size:150px;font-weight:800;line-height:1.4;padding:8px 0}
.h2{font-size:92px;font-weight:800;line-height:1.4;padding:6px 0}
.h3{font-size:66px;font-weight:800;line-height:1.4;padding:4px 0}
.p{font-size:54px;font-weight:500;line-height:1.5;opacity:.88}
.g{color:#f2b705}.bl{color:#6cabdd}.rd{color:#ff5d5d}
.panel{background:rgba(2,26,69,.78);border:4px solid rgba(255,255,255,.25);border-radius:32px;box-sizing:border-box;display:flex;align-items:center;justify-content:center;text-align:center;font-weight:800;line-height:1.4}
.row{height:140px;border-radius:26px;display:flex;align-items:center;padding:0 44px;box-sizing:border-box;font-size:58px;font-weight:800;line-height:1.4;background:rgba(255,255,255,.16)}
.row.hl{background:#f2b705;color:#0b1a3a}.row .r{width:90px}.row .st{margin-left:auto;font-size:44px;font-weight:500}
.big{font-weight:800;line-height:1.2;color:#f2b705}
.stripe{position:absolute;left:-200px;width:2400px;height:110px;background:rgba(255,255,255,.05);transform:rotate(-8deg)}
"""
ENGINE = """
const $=s=>document.querySelector(s);
const tl=gsap.timeline({paused:true});
SCENES.forEach((S,i)=>{
  const el=document.getElementById(S.k); gsap.set(el,{autoAlpha:0});
  tl.set(el,{autoAlpha:1},S.t0);
  el.querySelectorAll('[data-d]').forEach(x=>{
    tl.from(x,{opacity:0,y:50,scale:.94,duration:.55,ease:'expo.out'},S.t0+parseFloat(x.dataset.d));
  });
  el.querySelectorAll('[data-count]').forEach(x=>{
    const [f,t,d,pre,suf,at]=x.dataset.count.split('|'); const o={v:+f}; x.textContent=pre+Math.round(+f)+suf;
    tl.to(o,{v:+t,duration:+d,ease:'power2.out',onUpdate:()=>{x.textContent=pre+Math.round(o.v)+suf}},S.t0+parseFloat(at));
  });
  el.querySelectorAll('[data-sw]').forEach(x=>{
    const [nt,d]=x.dataset.sw.split('|'); const old=x.textContent; const o={v:0};
    tl.to(o,{v:1,duration:.01,onUpdate:()=>{x.textContent=o.v>=.5?nt:old}},S.t0+parseFloat(d));
    tl.fromTo(x,{scale:1},{scale:1.35,duration:.18,yoyo:true,repeat:1,ease:'expo.out'},S.t0+parseFloat(d));
  });
  el.querySelectorAll('[data-swap]').forEach(x=>{
    const [dy,d]=x.dataset.swap.split('|'); gsap.set(x,{y:+dy});
    tl.to(x,{y:0,duration:.7,ease:'power2.inOut'},S.t0+parseFloat(d));
  });
  el.querySelectorAll('[data-pulse]').forEach(x=>{
    const [d,n]=x.dataset.pulse.split('|');
    tl.to(x,{scale:1.06,duration:.45,ease:'power2.inOut',yoyo:true,repeat:+n},S.t0+parseFloat(d));
  });
  el.querySelectorAll('.fl').forEach(x=>{tl.to(x,{y:'-=14',duration:Math.max(1,S.t1-S.t0-.8),ease:'none'},S.t0+.6)});
  if(!S.last){tl.to(el,{autoAlpha:0,y:-50,duration:.25,ease:'expo.in'},S.t1-.25); tl.set(el,{y:0},S.t1+.01)}
});
tl.fromTo('#bgs',{x:-60},{x:60,duration:DUR,ease:'none'},0);
tl.set({},{},DUR);
window.__timelines[ID]=tl;
"""
def T(text,d,cls="h2",style="",extra=""):
    return f'<div class="a c {cls}" style="{style}" data-d="{d}" {extra}>{text}</div>'
def tag(t,d=.2): return f'<div class="a tag" data-d="{d}"><span>{t}</span></div>'
def pill(t,top,d): return f'<div class="a pill" style="top:{top}px" data-d="{d}"><span>{t}</span></div>'
def panel(x,y,w,h,inner,d,fs=60,extra="",cls=""):
    return f'<div class="a panel {cls}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;font-size:{fs}px;{extra}" data-d="{d}">{inner}</div>'
def row(y,txt,st,d,hl=False,x=260,w=1400,extra=""):
    return f'<div class="a row{" hl" if hl else ""}" style="left:{x}px;top:{y}px;width:{w}px;{extra}" data-d="{d}"><span>{txt}</span><span class="st">{st}</span></div>'

def build(cid, start, dur, scenes, final=False):
    html=['<!doctype html><html lang="th"><head><meta charset="UTF-8"/><meta name="viewport" content="width=1920, height=1080"/>',
    '<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@500;800&display=block" rel="stylesheet"/>',
    '<script src="cards/gsap.min.js"></script><style>'+CSS+'</style></head><body>',
    f'<div id="root" data-composition-id="{cid}" data-start="0" data-width="1920" data-height="1080" data-duration="{dur}" data-at="{start}">',
    '<div id="bgs" data-deco><div class="stripe" style="top:160px"></div><div class="stripe" style="top:760px"></div></div>']
    spec=[]
    for i,(k,t0,t1,inner) in enumerate(scenes):
        html.append(f'<div class="sc" id="{k}">{inner}</div>')
        spec.append({"k":k,"t0":round(t0-start,2),"t1":round(t1-start,2),"last":(i==len(scenes)-1)})
    html.append('</div><script>')
    html.append(f'const SCENES={json.dumps(spec)};const DUR={dur};const ID="{cid}";')
    html.append(ENGINE+'</script></body></html>')
    open(f"cards/{cid}.html","w").write("\n".join(html))

b=B
# ===== BEAT 1 intro 0–21.0 =====
S1=[("i1",0,b["i2"],
  tag("ข่าวเชลซีประจำวัน",.0)+T("สวัสดีแฟนบอล",.3,"h2","top:300px")+T("สิงห์บลูส์",.8,"h1 g fl","top:440px;font-size:190px")+T("15 พฤศจิกายน 2026",2.6,"p","top:720px")),
 ("i2",b["i2"],21.0,
  tag("วันนี้มีอะไรบ้าง",.0)+
  panel(220,260,1480,170,'<span style="color:#f2b705;margin-right:30px">1</span> ข่าวดีระดับแชมป์ ทีมหญิง',.4,70,"justify-content:flex-start;padding-left:60px")+
  panel(220,470,1480,170,'<span style="color:#f2b705;margin-right:30px">2</span> นักเตะเราในเบรกทีมชาติ',b["i3"]-b["i2"]-.2,70,"justify-content:flex-start;padding-left:60px")+
  panel(220,680,1480,170,'<span style="color:#f2b705;margin-right:30px">3</span> ตลาดนักเตะ ชาบี ต้องตัดสินใจ',b["i4"]-b["i2"]-.2,70,"justify-content:flex-start;padding-left:60px")+
  pill("ไปลุยกันเลย!",900,13.6))]
build("long1",0,21.0,S1)
# ===== BEAT 2 women 21.0–69.3 =====
W=[("w1",21.0,b["w2"],
  tag("WSL · ทีมหญิง",.0)+T("ไฮไลท์เมื่อคืน",.3,"h3 g","top:210px")+
  panel(160,330,640,330,'<span class="bl">เชลซี</span>',.9,100)+T("VS",1.7,"h1 g","top:395px;font-size:130px")+
  panel(1120,330,640,330,'<span style="color:#9fd0f5">แมนฯ ซิตี้</span>',1.3,100)+
  T("สแตมฟอร์ด บริดจ์",3.0,"p","top:760px")),
 ("w2",b["w2"],b["w4"],
  tag("ครึ่งแรก",.0)+
  panel(360,170,1200,220,'<span class="bl" style="font-size:54px;margin-right:40px">CHELSEA</span><span id="sc1" data-sw="1|6.3" style="font-size:130px">0</span><span style="font-size:100px;margin:0 24px;opacity:.6">-</span><span style="font-size:130px;opacity:.6">0</span><span style="font-size:54px;margin-left:40px;opacity:.7">MAN CITY</span>',.3,60,"padding:0 40px")+
  f'<div class="a c big" style="top:440px;font-size:260px" data-d=".6" data-count="0|45|2.3|||0.9" data-sw="45+4\'|{b["w3"]-b["w2"]+0.1}" id="clk">0</div>'+
  T("แซนดี บัลติมอร์ ประตูชัย!",b["w3"]-b["w2"]+.9,"h2","top:760px")),
 ("w4",b["w4"],b["w5"],
  tag("นาทีที่ 75",.0)+
  panel(200,260,340,470,'',.4,60,"background:#e0262d;border:6px solid #fff;transform:rotate(-8deg)")+
  T("ซิตี้เหลือ 10 คน",.8,"h1","left:600px;right:0;text-align:left;top:280px;font-size:130px")+
  T("ยามาชิตะ โดนใบแดง",1.5,"h2 rd","left:600px;right:0;text-align:left;top:480px")+T("ผู้รักษาประตูแมนฯ ซิตี้",2.2,"p","left:600px;right:0;text-align:left;top:640px")),
 ("w5",b["w5"],b["w6"]-.36,
  tag("จบเกม",.0)+T("เชลซี 1-0 ซิตี้",.3,"h1 g","top:170px;font-size:140px")+
  pill("ซิตี้แพ้นัดแรกของซีซัน",360,1.2)+
  row(500,"เชลซี","+1",2.0,True,x=260,w=1400,extra="")+
  '<div class="a row" id="rb" style="left:260px;top:660px;width:1400px" data-swap="-160|5.0"><span class="r">2</span><span>แมนฯ ซิตี้</span></div>'+
  '<div class="a row hl" id="ra" style="left:260px;top:660px;width:1400px;display:none"></div>'),
 ]
# simpler table for w5: two rows with swap
W[3]=("w5",b["w5"],b["w6"]-.36,
  tag("จบเกม",.0)+T("เชลซี 1-0 ซิตี้",.3,"h1 g","top:150px;font-size:140px")+
  pill("ซิตี้แพ้นัดแรกของซีซัน",340,1.0)+
  '<div class="a" style="left:160px;top:520px;font-size:70px;font-weight:800;line-height:2" data-d="2.0">1</div>'+
  '<div class="a" style="left:160px;top:700px;font-size:70px;font-weight:800;line-height:2" data-d="2.0">2</div>'+
  '<div class="a" style="left:260px;top:700px;width:1400px;height:140px" data-d="2.0"><div class="row" style="width:100%" data-swap="-180|5.0"><span>แมนฯ ซิตี้</span></div></div>'+
  '<div class="a" style="left:260px;top:520px;width:1400px;height:140px" data-d="2.0"><div class="row hl" style="width:100%" data-swap="180|5.0"><span>เชลซี</span><span class="st" style="color:#0b1a3a">+1 แต้ม</span></div></div>'+
  T("แซงขึ้นจ่าฝูง WSL!",6.2,"h2 g","top:880px"))
W+= [
 ("w6",b["w6"]-.36,b["w8"]-.3,
  tag("ห่วงอาการบาดเจ็บ",.0)+
  panel(160,230,780,560,'<div><div class="h3 g">คาเดชา บูคานัน</div><div class="p">กระทบกระเทือนศีรษะ</div><div class="h2">ออกนาทีที่ 12</div></div>',.5,60)+
  panel(980,230,780,560,'<div><div class="h3 g">เมลวีน มาลาร์ด</div><div class="p">เจ็บแฮมสตริง</div><div class="h2">ออกนาทีที่ 35</div></div>',b["w7"]-b["w6"]+.36+.1,60)),
 ("w8",b["w8"]-.3,69.3,
  tag("ก้าวต่อไป",.0)+T("โซเนีย บอมปาสเตอร์ เช็กอาการอีกครั้ง",.4,"h3","top:300px")+
  panel(360,440,1200,300,'<div><div class="p">ก่อนเกมหนัก</div><div class="h1 g" style="font-size:120px">เปแอสเช</div><div class="p">แชมเปียนส์ลีก · คืนวันพุธ</div></div>',1.3,60))]
build("long2",21.0,48.3,W)
# ===== BEAT 3 national 69.3–118.3 =====
N=[("n1",69.3,b["n2"],
  tag("ทีมชาติ · เนชันส์ ลีก",.0)+T("เปโดร เนโต ตัวจริง",.4,"h2 g","top:220px")+
  panel(260,360,1400,300,'<span style="font-size:80px">โปรตุเกส</span><span class="big" style="font-size:150px;margin:0 60px">1 - 4</span><span style="font-size:80px">เดนมาร์ก</span>',1.3,60)+
  T("พ่ายแพ้ในเนชันส์ ลีก",3.2,"p","top:720px")),
 ("n2",b["n2"],b["n3"],
  tag("ม้านั่งสำรอง",.0)+T("เจโอวานี เควนดา",.4,"h1 g","top:260px;font-size:140px")+T("ฟิลิป ยอร์เกนเซน",1.0,"h1 g","top:430px;font-size:140px")+T("ไม่ได้ลงสนาม",2.0,"h2","top:650px")),
 ("n3",b["n3"],b["n4"]-.5,
  tag("เกมอุ่นเครื่อง · สิงคโปร์",.0)+T("เอสเตเวา วิลเลียน ตัวจริง",.4,"h2 g","top:220px")+
  panel(260,360,1400,280,'<span style="font-size:80px">บราซิล</span><span class="big" style="font-size:150px;margin:0 60px">2 - 3</span><span style="font-size:80px">ญี่ปุ่น</span>',1.2,60)+
  T("ยิงเกือบเข้า แต่ติดเซฟ",4.0,"p","top:720px")),
 ("n4",b["n4"]-.5,b["n5"],
  tag("ข่าวดีชุดเยาวชน",.0)+T("อังกฤษ U19",.3,"h2","top:200px")+
  panel(260,330,1400,260,'<span class="big" style="font-size:170px">5 - 0</span><span style="font-size:80px;margin-left:50px">เบลารุส</span>',1.0,60)+
  T("เอเซนวาทา ยิงจุดโทษ",3.0,"h3 g","top:640px")+
  T("เบอร์นัล · เอเมนาโล · วอลช์ ตัวจริงครบ",5.0,"h3","top:790px")),
 ("n5",b["n5"],118.3,
  tag("คืนวันอาทิตย์ · ตามเชียร์ต่อ",.0)+
  row(230,"อังกฤษ  vs  สเปน","มอร์แกน โรเจอร์ส",1.0,False,x=160,w=1600)+
  row(420,"ฝรั่งเศส  vs  ตุรกี","มาโล กุสโต",5.0,False,x=160,w=1600)+
  row(610,"เบลเยียม  vs  อิตาลี","ลาเวีย · เพนเดอร์ส | ปาเลสตรา",9.0,False,x=160,w=1600))]
build("long3",69.3,49.0,N)
# ===== BEAT 4 transfer 118.3–161.85 =====
Tt=[("t1",118.3,b["t2"],
  tag("ตลาดนักเตะ · Sky Sports News",.0)+T("อนาคตของ",.4,"h2","top:250px")+T("มาโล กุสโต",.9,"h1 g fl","top:380px;font-size:200px")+T("กำลังทบทวน ก่อนตลาดเดือนมกราคม",2.8,"p","top:700px")),
 ("t2",b["t2"],b["t4"]-.3,
  tag("พรีเมียร์ลีก",.0)+
  f'<div class="a big" style="left:140px;top:170px;width:620px;text-align:center;font-size:520px" data-d=".2">0</div>'+
  T("ตัวจริงในลีก",.7,"h3","left:140px;width:620px;right:auto;top:760px")+T("นาน 2 เดือนเต็ม",1.2,"h3 g","left:140px;width:620px;right:auto;top:860px")+
  row(210,"รีซ เจมส์","บาดเจ็บ",b["t3"]-b["t2"]-.8,False,x=880,w=900)+
  row(380,"จอช อาเชียมปง","ตัวจริง",b["t3"]-b["t2"]+.8,True,x=880,w=900)+
  row(550,"มาร์โก ปาเลสตรา","ตัวจริง",b["t3"]-b["t2"]+1.6,True,x=880,w=900)+
  row(720,"มาโล กุสโต","ม้านั่ง",b["t3"]-b["t2"]+2.8,False,x=880,w=900,extra="opacity:.55")),
 ("t4",b["t4"]-.3,b["t5"],
  tag("ซิเนอดีน ซีดาน",.0)+T("กุนซือทีมชาติฝรั่งเศส",.4,"h3","top:230px")+T("ออกมาปกป้องกุสโต",1.2,"h1 g","top:340px;font-size:140px")+T("หลังโดนวิจารณ์ในเกมแพ้อิตาลี",3.2,"p","top:620px")),
 ("t5",b["t5"],b["t6"],
  tag("มุมมองของผม",.0)+T("ถ้ากุสโตยังไม่ได้โอกาส",.4,"h2","top:280px")+T("โอกาสย้ายออก ม.ค.",1.6,"h1 g","top:430px;font-size:150px")+T("เปิดกว้างมาก",3.0,"h2","top:650px")),
 ("t6",b["t6"],161.85,
  tag("ข่าวลือ · The Hard Tackle",.0)+T("มาร์ติน บาตูรินา",.4,"h2","top:200px")+
  T("เพลย์เมกเกอร์ เซเรีย อา",1.0,"p","top:330px")+
  f'<div class="a c big" style="top:410px;font-size:200px" data-d="1.6" data-count="0|80|1.2|| M€|1.6">0 M€</div>'+
  panel(300,700,520,240,'<span class="bl">เชลซี</span>',4.0,80)+T("VS",4.6,"h1 g","top:730px;font-size:110px;left:820px;right:820px")+panel(1100,700,520,240,'<span class="rd">แมนฯ ยูไนเต็ด</span>',4.3,70))]
build("long4",118.3,43.55,Tt)
# ===== BEAT 5 close 161.85–181.2 =====
C=[("c1",161.85,b["c2"],
  tag("สรุปข่าววันนี้",.0)+T("ข่าวเชลซี",.3,"h1 g","top:280px;font-size:190px")+T("15 พฤศจิกายน 2026",1.4,"p","top:560px")),
 ("c2",b["c2"],b["c3"],
  tag("ถึงแฟนๆ",.0)+T("ควรเก็บหรือขาย กุสโต?",.3,"h1","top:180px;font-size:130px")+
  panel(260,420,640,300,'เก็บไว้สู้ต่อ',1.4,70,"background:#f2b705;color:#0b1a3a;border-color:#f2b705","")+
  panel(1020,420,640,300,'ขายแล้วเสริมตำแหน่งอื่น',1.8,56,"")),
 ("c3",b["c3"],181.2,
  T("คอมเมนต์เลย!",.2,"h1","top:210px;font-size:150px;color:#0b1a3a;background:#f2b705;left:360px;right:360px;border-radius:120px;",'data-pulse="1.2|13"')+
  T("กดไลก์ + กดติดตาม",1.0,"h2 g","top:520px")+T("ไม่พลาดข่าวเชลซีทุกเช้า",1.6,"p","top:680px")+T("เจอกันใหม่คลิปหน้า",2.2,"p","top:780px"))]
build("long5",161.85,19.35,C)
print("ok")
