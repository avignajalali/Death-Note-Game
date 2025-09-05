import pygame
import random
import sys
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

WIDTH, HEIGHT = 1280, 760
FPS = 60

DAYS_LIMIT = 40
START_INTEL = 3
JUSTICE_WIN = 140
MAX_SUSPICION = 100
DAILY_ACTION_POINTS = 3
MAX_WRITES_PER_DAY = 3

CAUSES = [
    "heart attack", "accident", "illness", "fall", "stroke",
    "cardiac arrest", "overdose", "drowning", "unknown"
]
TIMES = ["07:00", "12:00", "16:00", "20:00", "23:59", "random"]
CITIES = ["Tokyo","Osaka","Sapporo","Sendai","Nagoya","Kyoto","Yokohama","Fukuoka"]

BG = (15,18,24)
PANEL = (26,32,44)
TEXT = (232,236,242)
DIM = (165,174,188)
GOOD = (70,200,120)
BAD = (238,70,96)
WARN = (255,192,90)
OUT = (55,62,76)
BTN = (40,48,64)
BTN_H = (56,66,88)

pygame.init()

@dataclass
class Person:
    name: str
    city: str
    crime: Optional[str]
    guilt: int
    notoriety: int
    has_alias: bool
    intel_req: int
    real_name_known: bool = False
    alive: bool = True

    def is_criminal(self):
        return self.crime is not None and self.guilt >= 5

@dataclass
class Investigator:
    suspicion: int = 15

    def add_suspicion(self, amt: int):
        self.suspicion = max(0, min(MAX_SUSPICION, self.suspicion + amt))

    def game_over(self) -> bool:
        return self.suspicion >= MAX_SUSPICION

@dataclass
class GameState:
    day: int = 1
    phase: str = "Day"
    justice: float = 0.0
    intel_points: int = START_INTEL
    entries_today: int = 0
    action_points: int = DAILY_ACTION_POINTS
    have_eyes: bool = False
    city_people: List[Person] = field(default_factory=list)
    inv: Investigator = field(default_factory=Investigator)
    news: List[str] = field(default_factory=list)
    pattern_memory: List[Tuple[str,str,str]] = field(default_factory=list)
    confidants: dict = field(default_factory=lambda: {"Ryuk":1, "Misa":0})
    stats: dict = field(default_factory=lambda: {"Intelligence":1, "Charisma":1, "Courage":1})

    def add_news(self, s: str):
        self.news.append(s)
        if len(self.news)>50: self.news.pop(0)

def japanese_name_pool():
    surnames = ["Yagami","Amane","Aizawa","Matsuda","Takada","Sato","Suzuki","Tanaka","Watanabe","Takahashi","Ito","Yamada","Nakamura","Kobayashi"]
    given = ["Light","Sachiko","Kenji","Naoki","Haruka","Ryo","Yumi","Shinji","Aya","Takuya","Rei","Kenta","Naomi","Akira"]
    pool = [f"{s} {g}" for s in surnames for g in random.sample(given,k=6)]
    random.shuffle(pool)
    return pool

CRIMES = ["armed robbery","extortion","assault","kidnapping","arson","drug trafficking","embezzlement","murder","cyberfraud"]

def gen_population(n=42):
    names = japanese_name_pool()
    people=[]
    for i in range(n):
        name = names.pop() if names else f"Person{i}"
        city = random.choice(CITIES)
        is_crim = random.random()<0.55
        has_alias = random.random()<0.45
        guilt = random.randint(0,10) if is_crim else random.randint(0,6)
        notor = random.randint(0,10)
        intel = random.randint(1,3)
        crime = random.choice(CRIMES) if is_crim else None
        people.append(Person(name, city, crime, guilt, notor, has_alias, intel))
    return people

def justice_score(p: Person, have_eyes: bool)->float:
    base = max(0, p.guilt-2)*(1+p.notoriety/20)
    if have_eyes: base *= 0.85
    return base

def resolve_write(gs: GameState, p: Person, cause: str, time_str: str):
    if not p.alive:
        return "Already dead"
    if gs.entries_today>=MAX_WRITES_PER_DAY:
        return "Notebook resists"

    if p.has_alias and not (p.real_name_known or gs.have_eyes):
        gs.inv.add_suspicion(3)
        gs.entries_today+=1
        gs.add_news("Strange episode, no fatality.")
        return "Alias suspected. Suspicion +3"
    if time_str=="random":
        time_str = random.choice([t for t in TIMES if t!="random"])
    p.alive=False
    gs.entries_today+=1
    gs.add_news(f"Death reported in {p.city}: {p.name} — {cause} @ {time_str}")
    gs.justice += justice_score(p, gs.have_eyes)
    gs.pattern_memory.append((cause,time_str,p.city))
    if len(gs.pattern_memory)>7:
        gs.pattern_memory.pop(0)

    if p.guilt<=1:
        gs.inv.add_suspicion(18)
        gs.add_news("Outrage: possible innocent victim")
    elif p.guilt<=3:
        gs.inv.add_suspicion(8)
    gs.inv.add_suspicion(max(0,p.notoriety-4)//2)
    return "Name written."

def research(gs: GameState, p: Person):
    if gs.intel_points<=0:
        return "No intel today"
    cost = 1 if gs.have_eyes else p.intel_req
    if gs.intel_points < cost:
        return "Not enough intel"
    gs.intel_points -= cost
    if p.has_alias and not p.real_name_known:
        if random.random() < (1.0 if gs.have_eyes else 0.8):
            p.real_name_known=True
            gs.add_news(f"Intel: {p.name} confirmed")
            return "Real name confirmed"
        return "Trail cold"
    p.real_name_known=True
    gs.add_news(f"Background check: {p.name}")
    return "Verified"

def end_of_day(gs: GameState):
    causes={}; times={}; cities={}
    for c,t,ci in gs.pattern_memory:
        causes[c]=causes.get(c,0)+1; times[t]=times.get(t,0)+1; cities[ci]=cities.get(ci,0)+1
    if causes:
        cmax=max(causes,key=causes.get); n=causes[cmax]
        if n>=3:
            gs.inv.add_suspicion(3)
            gs.add_news(f"Investigators note cause pattern: {cmax}")
    if times:
        tmax=max(times,key=times.get); n=times[tmax]
        if n>=3:
            gs.inv.add_suspicion(3)
            gs.add_news(f"Investigators note time pattern: {tmax}")
    if cities:
        city=max(cities,key=cities.get); n=cities[city]
        if n>=3:
            gs.inv.add_suspicion(3)
            gs.add_news(f"Cluster of deaths in {city}")

    base = 4
    if gs.entries_today == 0:
        gs.inv.add_suspicion(-5)
        base = 0
    elif gs.entries_today >= 2:
        base += 2
    gs.inv.add_suspicion(base)

    if gs.action_points > 0:
        gs.inv.add_suspicion(6)

    gs.day += 1
    gs.entries_today = 0
    gs.intel_points = START_INTEL + (1 if gs.have_eyes else 0)
    gs.action_points = DAILY_ACTION_POINTS

class Button:
    def __init__(self, rect, label, cb):
        self.rect = pygame.Rect(rect); self.label = label; self.cb = cb; self.hover=False
    def draw(self,surf,font):
        col = BTN_H if self.hover else BTN
        pygame.draw.rect(surf,col,self.rect,border_radius=10)
        pygame.draw.rect(surf,OUT,self.rect,1,border_radius=10)
        txt = font.render(self.label,True,TEXT)
        surf.blit(txt, txt.get_rect(center=self.rect.center))
    def handle(self,event):
        if event.type==pygame.MOUSEMOTION:
            self.hover=self.rect.collidepoint(event.pos)
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self.rect.collidepoint(event.pos):
            self.cb()

class ScrollList:
    def __init__(self, rect, row_h=52):
        self.rect=pygame.Rect(rect); self.row_h=row_h; self.items=[]; self.scroll=0
    def set_items(self,items): self.items=items; self.scroll=0
    def draw(self,surf,font,font_small):
        pygame.draw.rect(surf,PANEL,self.rect,border_radius=12); pygame.draw.rect(surf,OUT,self.rect,1,border_radius=12)
        clip=surf.get_clip(); surf.set_clip(self.rect.inflate(-6,-6))
        y=self.rect.y+6-self.scroll; mx,my=pygame.mouse.get_pos()
        for i,(drawfn,_) in enumerate(self.items):
            r=pygame.Rect(self.rect.x+6,y,self.rect.w-12,self.row_h-6)
            hover=r.collidepoint((mx,my))
            pygame.draw.rect(surf,PANEL if not hover else (32,40,54),r,border_radius=8)
            pygame.draw.rect(surf,OUT,r,1,border_radius=8)
            drawfn(surf,r)
            y+=self.row_h
        surf.set_clip(clip)
    def handle(self,event):
        if event.type==pygame.MOUSEWHEEL:
            self.scroll=max(0,self.scroll-event.y*(self.row_h//2))
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1 and self.rect.collidepoint(event.pos):
            idx=(event.pos[1]-(self.rect.y+6)+self.scroll)//self.row_h
            if 0<=idx<len(self.items):
                _,cb=self.items[idx]; cb()

class Modal:
    def __init__(self,size): self.size=size; self.visible=False; self.title=""; self.lines=[]; self.buttons=[]
    def open(self,title,lines,actions):
        self.visible=True; self.title=title; self.lines=lines;
        self.buttons=[Button((0,0,140,36),lbl,cb) for lbl,cb in actions]
    def close(self): self.visible=False
    def draw(self,surf,font_big,font):
        if not self.visible: return
        sw,sh=surf.get_size(); ov=pygame.Surface((sw,sh),pygame.SRCALPHA); ov.fill((0,0,0,180)); surf.blit(ov,(0,0))
        w,h=self.size; rect=pygame.Rect((sw-w)//2,(sh-h)//2,w,h)
        pygame.draw.rect(surf,PANEL,rect,border_radius=12); pygame.draw.rect(surf,OUT,rect,2,border_radius=12)
        surf.blit(font_big.render(self.title,True,TEXT),(rect.x+18,rect.y+14))
        y=rect.y+56
        for ln in self.lines: surf.blit(font.render(ln,True,TEXT),(rect.x+18,y)); y+=26
        bx=rect.x+18; by=rect.bottom-56
        for b in self.buttons: b.rect.topleft=(bx,by); b.draw(surf,font); bx+=b.rect.w+12
    def handle(self,event):
        if not self.visible: return
        for b in self.buttons: b.handle(event)

class Game:
    def __init__(self):
        self.screen=pygame.display.set_mode((WIDTH,HEIGHT)); pygame.display.set_caption("Death Note: Persona Edition")
        self.clock=pygame.time.Clock();
        self.font=pygame.font.Font(None,26); self.font_small=pygame.font.Font(None,20); self.font_big=pygame.font.Font(None,34)
        self.gs=GameState(); self.modal=Modal((700,380)); self.toast=""; self.toast_t=0

        self.list_news=ScrollList((20,100,600,360),row_h=64)
        self.list_people=ScrollList((640,100,600,360),row_h=60)

        self.btn_research=Button((820,540,140,40),"Research",self._btn_research_cb)
        self.btn_write=Button((980,540,140,40),"Write Name",self._btn_write_cb)

        self.btn_study=Button((20,700-40,120,36),"Study",self.on_study)
        self.btn_family=Button((150,700-40,120,36),"Family",self.on_family)
        self.btn_social=Button((280,700-40,120,36),"Socialize",self.on_social)
        self.btn_patrol=Button((410,700-40,120,36),"Patrol",self.on_patrol)
        self.btn_eyes=Button((540,700-40,140,36),"Shinigami Eyes",self.on_eyes)
        self.btn_rules=Button((690,700-40,100,36),"Rules",self.on_rules)
        self.btn_end=Button((810,700-40,140,36),"End Day",self.on_end_day)

        self.gs.city_people=gen_population(50); self.refresh_lists(); self.selected=None

        self.light_portrait = self._load_or_make_light()
        self.light_flash = self._make_tinted(self.light_portrait, (200,40,40))
        self.anim_active = False
        self.anim_data = None
        self.anim_overlay_alpha = 0

    def _load_or_make_light(self):
        TARGET = (180, 180)
        SMALL = (64, 64)
        for fname in ("light.png",):
            try:
                img = pygame.image.load(fname).convert_alpha()
                small = pygame.transform.scale(img, SMALL)
                pix = pygame.transform.scale(small, TARGET)
                return pix
            except Exception:
                pass
        return self._make_light_pixel()

    def _make_light_pixel(self):
        s = pygame.Surface((180,180), pygame.SRCALPHA)
        s.fill((14,14,18))
        pygame.draw.rect(s,(240,220,190),(54,10,72,100))
        pygame.draw.polygon(s,(40,30,30),[(20,20),(160,10),(130,70),(100,40),(60,50),(40,40)])
        pygame.draw.rect(s,(30,30,30),(82,60,12,8))
        pygame.draw.rect(s,(30,30,30),(106,60,12,8))
        pygame.draw.rect(s,(255,255,255),(85,62,4,4))
        pygame.draw.rect(s,(255,255,255),(109,62,4,4))
        pygame.draw.rect(s,(80,40,40),(90,100,20,6))
        pygame.draw.rect(s,(20,20,30),(64,120,72,36))
        pygame.draw.line(s,(255,230,200),(64,20),(154,20),1)
        pygame.draw.line(s,(40,40,40),(64,60),(154,60),1)
        return s

    def _make_tinted(self, surf, tint_rgb):
        w,h = surf.get_size()
        tmp = surf.copy()
        overlay = pygame.Surface((w,h))
        overlay.fill(tint_rgb)
        tmp.blit(overlay, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
        return tmp

    def toast_msg(self,msg):
        self.toast=msg; self.toast_t=pygame.time.get_ticks()

    def refresh_lists(self):
        alive=[p for p in self.gs.city_people if p.alive]
        items=[]
        for p in alive:
            def make_draw(pp=p):
                def draw(surf,r):
                    surf.blit(self.font.render(f"{pp.name} — {pp.city}",True,TEXT),(r.x+8,r.y+6))
                    surf.blit(self.font_small.render(f"{pp.crime if pp.crime else 'civilian'} | G{pp.guilt} N{pp.notoriety}",True,DIM),(r.x+8,r.y+32))
                return draw
            def make_click(pp=p):
                def cb(): self.selected=pp
                return cb
            items.append((make_draw(),make_click()))
        self.list_news.set_items(items)
        shortlist=sorted(alive,key=lambda x:(not x.is_criminal(),-x.notoriety))[:18]
        items2=[]
        for p in shortlist:
            def make_draw(pp=p):
                def draw(surf,r):
                    nm=pp.name if (not pp.has_alias or pp.real_name_known or self.gs.have_eyes) else f"(Alias) {pp.name}"
                    surf.blit(self.font.render(nm,True,TEXT),(r.x+8,r.y+6))
                    surf.blit(self.font_small.render(f"{pp.city} | {'criminal' if pp.is_criminal() else 'civilian'} | G{pp.guilt}",True,DIM),(r.x+8,r.y+30))
                return draw
            def make_click(pp=p):
                def cb(): self.selected=pp
                return cb
            items2.append((make_draw(),make_click()))
        self.list_people.set_items(items2)

    def _btn_research_cb(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if not self.selected: self.toast_msg("Select someone first"); return
        if self.gs.phase != "Day": self.toast_msg("Research works best during the day. End Night to research."); return
        msg=research(self.gs,self.selected)
        self.toast_msg(msg); self.refresh_lists()

    def _btn_write_cb(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if not self.selected: self.toast_msg("Select someone first"); return
        if self.gs.phase != "Night": self.toast_msg("You can only write in the Death Note at Night. Press End Day to switch."); return
        cause_i=0; time_i=0
        def set_cause():
            nonlocal cause_i
            cause_i=(cause_i+1)%len(CAUSES)
            self.modal.lines=self._compose(self.selected,CAUSES[cause_i],TIMES[time_i])
        def set_time():
            nonlocal time_i
            time_i=(time_i+1)%len(TIMES)
            self.modal.lines=self._compose(self.selected,CAUSES[cause_i],TIMES[time_i])
        def confirm():
            self.start_kill_animation(self.selected, CAUSES[cause_i], TIMES[time_i])
            self.modal.close()
        def cancel(): self.modal.close()
        self.modal.open("Write in Death Note", self._compose(self.selected,CAUSES[cause_i],TIMES[time_i]),
                        [("Cause",set_cause),("Time",set_time),("Confirm",confirm),("Cancel",cancel)])

    def on_rules(self):
        rules = [
            "Death Note Rules (game summary):",
            "• Write a real name (research aliases) at Night to kill.",
            "• If you write a cause/time it will occur as specified.",
            "• Writes per day limited; too many patterns raise suspicion.",
            "• Research costs intel; Eyes make intel cheap but cost you.",
            "• Build stats by daytime actions to help avoid suspicion.",
            "",
            "Game controls: Select a person, Research (Day), End Day to switch to Night, then Write (Night).",
        ]
        self.modal.open("Rules", rules, [("Close", lambda: self.modal.close())])

    def _compose(self,p,cause,time_str):
        return [f"Target: {p.name if (not p.has_alias or p.real_name_known or self.gs.have_eyes) else '(Alias) '+p.name}",
                f"Cause: {cause}", f"Time: {time_str}",
                ("(Alias suspected)" if (p.has_alias and not (p.real_name_known or self.gs.have_eyes)) else "Name confidence OK")]

    def on_study(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.phase != "Day": self.toast_msg("You can't study at night. End Night first."); return
        if self.gs.action_points<=0: self.toast_msg("No actions left"); return
        self.gs.action_points-=1; self.gs.stats["Intelligence"]+=1; self.gs.inv.add_suspicion(-3); self.toast_msg("Studied (+Int)")

    def on_family(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.phase != "Day": self.toast_msg("You can't visit family at night."); return
        if self.gs.action_points<=0: self.toast_msg("No actions left"); return
        self.gs.action_points-=1; self.gs.stats["Charisma"]+=1; self.gs.inv.add_suspicion(-2); self.toast_msg("Family time (+Cha)")

    def on_social(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.phase != "Day": self.toast_msg("Social stuff happens in daytime."); return
        if self.gs.action_points<=0: self.toast_msg("No actions left"); return
        self.gs.action_points-=1; self.gs.stats["Courage"]+=1; self.gs.inv.add_suspicion(-2); self.toast_msg("Socialized (+Courage)")

    def on_patrol(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.phase != "Day": self.toast_msg("Patrol is a day activity."); return
        if self.gs.action_points<=0: self.toast_msg("No actions left"); return
        self.gs.action_points-=1
        hints=random.sample([p for p in self.gs.city_people if p.alive],k=min(3,len([p for p in self.gs.city_people if p.alive])))
        for h in hints:
            if h.is_criminal() and random.random()<0.6:
                h.notoriety=min(10,h.notoriety+1)
        self.toast_msg("Patrolled forums. Leads hotter.")

    def on_eyes(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.have_eyes: self.toast_msg("You already have the Eyes"); return
        if self.gs.phase != "Day": self.toast_msg("The pact is sealed by day, not at midnight."); return
        def accept():
            self.gs.have_eyes=True; self.gs.intel_points+=1; self.modal.close(); self.toast_msg("Shinigami Eyes accepted — price unknown.")
        def cancel(): self.modal.close()
        self.modal.open("Shinigami Eyes", ["Trade lifespan for Eyes (stylized).","Intel easier, justice slightly reduced."], [("Accept",accept),("Cancel",cancel)])

    def on_end_day(self):
        if self.anim_active:
            self.toast_msg("Animation in progress.")
            return
        if self.gs.phase == "Day":
            self.gs.phase = "Night"
            self.gs.entries_today = 0
            self.toast_msg("Night falls — you may write in the Death Note.")
            return
        end_of_day(self.gs)
        self.gs.phase = "Day"
        self.refresh_lists()
        self.toast_msg(f"Day {self.gs.day}. Intel:{self.gs.intel_points} AP:{self.gs.action_points}")

    def start_kill_animation(self, target: Person, cause: str, time_str: str):
        if self.anim_active:
            return
        duration = 1800
        anim_type = "fade"
        if cause == "heart attack":
            anim_type = "heart"
            duration = 1600
        elif cause == "accident":
            anim_type = "accident"
            duration = 2000
        else:
            anim_type = "fade"
            duration = 1400
        self.anim_active = True
        self.anim_data = {
            "start": pygame.time.get_ticks(),
            "duration": duration,
            "type": anim_type,
            "target": target,
            "cause": cause,
            "time_str": time_str
        }
        self.toast_msg(f"Writing {target.name}...")

    def update_kill_animation(self):
        if not self.anim_active or not self.anim_data:
            return
        now = pygame.time.get_ticks()
        elapsed = now - self.anim_data["start"]
        dur = self.anim_data["duration"]
        if elapsed >= dur:
            t = self.anim_data["target"]
            msg = resolve_write(self.gs, t, self.anim_data["cause"], self.anim_data["time_str"])
            self.toast_msg(msg)
            if self.selected == t:
                self.selected = None
            self.refresh_lists()
            self.anim_active = False
            self.anim_data = None
            self.anim_overlay_alpha = 0
            return
        progress = elapsed / dur
        self.anim_overlay_alpha = int(min(220, 220 * (0.6 + 0.4*progress)))

    def draw_kill_animation_overlay(self, surf):
        if not self.anim_active or not self.anim_data:
            return
        typ = self.anim_data["type"]
        elapsed = pygame.time.get_ticks() - self.anim_data["start"]
        dur = self.anim_data["duration"]
        center = (WIDTH//2, HEIGHT//2)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        def flash_center():
            big = pygame.transform.scale(
                self.light_flash,
                (int(self.light_flash.get_width()*1.5), int(self.light_flash.get_height()*1.5))
            )
            surf.blit(big, big.get_rect(center=center))

        if typ == "heart":
            pulse = 120 + int(100*math.sin(elapsed/80))
            overlay.fill((pulse,20,20, min(200, int(180 * (elapsed/dur + 0.2)))))
            font = self.font_big
            skull = font.render("💀", True, (255,240,240))
            surf.blit(skull, skull.get_rect(center=(center[0], center[1]-20)))
            txt = self.font.render("They collapse.", True, (255,220,220))
            surf.blit(txt, txt.get_rect(center=(center[0], center[1]+60)))
            if elapsed < 600:
                flash_center()
        elif typ == "accident":
            shake = int(6 * math.sin(elapsed/30))
            overlay.fill((255, 80, 40, min(200, int(200 * (elapsed/dur)))))
            font = self.font_big
            crash = font.render("💥", True, (255,240,220))
            surf.blit(crash, crash.get_rect(center=(center[0]+shake, center[1]-10)))
            txt = self.font.render("An accident.", True, (255,240,220))
            surf.blit(txt, txt.get_rect(center=(center[0]+shake, center[1]+60)))
            if elapsed < 900:
                flash_center()
        else:
            alpha = int(200 * (elapsed/dur))
            overlay.fill((20,20,30, alpha))
            skull = self.font_big.render("💀", True, (220,220,220))
            surf.blit(skull, skull.get_rect(center=(center[0], center[1])))
            if elapsed < 600:
                flash_center()
        surf.blit(overlay, (0,0))

    def draw_top(self):
        pygame.draw.rect(self.screen,PANEL,(0,0,WIDTH,84)); pygame.draw.line(self.screen,OUT,(0,84),(WIDTH,84),1)
        self.screen.blit(self.font_big.render(f"Day {self.gs.day} — {self.gs.phase}",True,TEXT),(20,20))
        self.screen.blit(self.font.render(f"Intel: {self.gs.intel_points}",True,TEXT),(420,20))
        self.screen.blit(self.font.render(f"AP: {self.gs.action_points}",True,TEXT),(520,20))
        self.screen.blit(self.font.render(f"Int:{self.gs.stats['Intelligence']} Cha:{self.gs.stats['Charisma']} Crg:{self.gs.stats['Courage']}",True,TEXT),(640,20))
        self.screen.blit(self.font.render(f"Suspicion: {self.gs.inv.suspicion}",True,BAD),(960,20))
        if self.gs.news:
            preview = self.gs.news[-1]
            self.screen.blit(self.font.render(preview,True,DIM),(20,86))

    def draw_columns(self):
        self.screen.fill(BG)
        self.draw_top()
        self.list_news.draw(self.screen,self.font,self.font_small)
        self.list_people.draw(self.screen,self.font,self.font_small)
        right=pygame.Rect(20,480,1220,200); pygame.draw.rect(self.screen,PANEL,right,border_radius=12); pygame.draw.rect(self.screen,OUT,right,1,border_radius=12)
        if self.selected:
            self.screen.blit(self.font_big.render(self.selected.name,True,TEXT),(right.x+20,right.y+14))
            self.screen.blit(self.font.render(f"{self.selected.city} | {'criminal' if self.selected.is_criminal() else 'civilian'} | G{self.selected.guilt} N{self.selected.notoriety}",True,DIM),(right.x+20,right.y+54))
        else:
            self.screen.blit(self.font.render("Select a person to inspect/write/research.",True,DIM),(right.x+20,right.y+20))
        for b in (self.btn_research,self.btn_write,self.btn_study,self.btn_family,self.btn_social,self.btn_patrol,self.btn_eyes,self.btn_rules,self.btn_end):
            b.draw(self.screen,self.font)
        if self.toast and pygame.time.get_ticks()-self.toast_t<2500:
            t=self.font.render(self.toast,True,TEXT); box=t.get_rect(); box.inflate_ip(18,12); box.midbottom=(WIDTH//2,HEIGHT-70); pygame.draw.rect(self.screen,PANEL,box,border_radius=10); pygame.draw.rect(self.screen,OUT,box,1,border_radius=10); self.screen.blit(t,t.get_rect(center=box.center))

    def loop(self):
        running=True
        while running:
            dt=self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type==pygame.QUIT: running=False
                if event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE: running=False
                if self.modal.visible:
                    self.modal.handle(event); continue
                if self.anim_active:
                    continue
                self.list_news.handle(event); self.list_people.handle(event)
                for b in (self.btn_research,self.btn_write,self.btn_study,self.btn_family,self.btn_social,self.btn_patrol,self.btn_eyes,self.btn_rules,self.btn_end):
                    b.handle(event)

            if self.anim_active:
                self.update_kill_animation()

            self.draw_columns()
            if self.modal.visible: self.modal.draw(self.screen,self.font_big,self.font)
            if self.anim_active:
                self.draw_kill_animation_overlay(self.screen)
            if self.gs.inv.game_over():
                self.modal.open("Game Over", ["L connected the dots.","You are arrested."], [("OK",lambda: self.quit())])
            pygame.display.flip()
        self.quit()

    def quit(self):
        print(f"Final Justice:{int(self.gs.justice)} Suspicion:{self.gs.inv.suspicion}")
        pygame.quit(); sys.exit()

if __name__=="__main__":
    random.seed()
    Game().loop()