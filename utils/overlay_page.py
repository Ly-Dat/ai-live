"""HTML for the on-screen overlay (a transparent page for a TikTok LIVE Studio / OBS browser source).

All text goes in with textContent (never innerHTML): poll questions, prizes and winner names are user text."""

OVERLAY_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>ai-live overlay</title><style>
html,body{margin:0;background:transparent;font-family:"Segoe UI",system-ui,sans-serif;color:#fff;overflow:hidden}
#wrap{position:fixed;left:20px;bottom:24px;width:340px;display:flex;flex-direction:column;gap:12px}
.card{background:rgba(20,16,36,.82);border-radius:16px;padding:12px 14px;border:1px solid rgba(255,255,255,.14);
  box-shadow:0 6px 24px rgba(0,0,0,.35);animation:in .3s ease}
@keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.tag{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.75;display:flex;justify-content:space-between}
.t{font-size:17px;font-weight:700;margin:4px 0 8px;line-height:1.25}
.row{margin:6px 0}.lab{display:flex;justify-content:space-between;font-size:14px;margin-bottom:3px}
.bar{height:8px;background:rgba(255,255,255,.16);border-radius:6px;overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,#8b5cf6,#ec4899);transition:width .5s}
.big{font-size:14px;opacity:.92}.hot{color:#fbbf24;font-weight:700}
#nv{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;width:min(760px,92vw);text-align:center;display:none;
  background:rgba(20,16,36,.78);border:1px solid rgba(255,255,255,.14);border-radius:16px;padding:12px 18px;box-shadow:0 6px 24px rgba(0,0,0,.35)}
#nv .nt{font-size:12px;letter-spacing:.06em;text-transform:uppercase;opacity:.7}
#nv .nprev,#nv .nnext{font-size:15px;opacity:.5;margin:3px 0}
#nv .ncur{font-size:21px;font-weight:600;line-height:1.35;margin:6px 0;transition:opacity .3s}
#nv .ncur.d{color:#7ee0ff}
#nv.light{background:rgba(255,255,255,.93);color:#1d1b2b;border-color:rgba(0,0,0,.15)}
#nv.sepia{background:rgba(244,236,216,.95);color:#4a3b2a;border-color:rgba(74,59,42,.25)}
#nv.light .ncur.d{color:#0b6aa8}#nv.sepia .ncur.d{color:#8a4b12}
#nv.s .ncur{font-size:17px}#nv.l .ncur{font-size:28px}#nv.l .nprev,#nv.l .nnext{font-size:19px}
#nv .ncr{font-size:11px;opacity:.6;margin-top:4px}
#sp{position:fixed;left:50%;transform:translateX(-50%);top:16px;width:min(520px,60vw);display:none;text-align:center}
#sp img{max-width:100%;max-height:68vh;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.5);transition:opacity .35s}
#sp .spc{margin-top:10px;background:rgba(20,16,36,.82);border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:10px 16px;font-size:21px;font-weight:600;line-height:1.35}
#sp .spt{font-size:12px;letter-spacing:.06em;text-transform:uppercase;opacity:.75;margin-top:6px;text-shadow:0 1px 4px rgba(0,0,0,.7)}
#np{position:fixed;right:20px;bottom:20px;max-width:300px;text-align:right;font-size:13px;opacity:.88;text-shadow:0 1px 4px rgba(0,0,0,.7)}
#cr{font-size:11px;opacity:.7}
#av{position:fixed;bottom:56px;display:none;pointer-events:none;text-align:center}
#av.right{right:24px}#av.left{left:24px}#av.center{left:50%;margin-left:-15vh}
#av img{height:62vh;display:block;margin:0 auto;filter:drop-shadow(0 6px 14px rgba(0,0,0,.45))}
#av.m-bob img{animation:bob 3.4s ease-in-out infinite}
#av.m-breathe img{animation:breathe 4s ease-in-out infinite;transform-origin:50% 100%}
#av.m-sway img{animation:sway 5s ease-in-out infinite;transform-origin:50% 100%}
#av.m-float img{animation:float 6s ease-in-out infinite}
#av.rest img{animation:none;opacity:.85}
#av.f-glow img{filter:drop-shadow(0 0 14px rgba(255,255,255,.75))}
#av.f-neon img{filter:drop-shadow(0 0 6px #22d3ee) drop-shadow(0 0 18px #8b5cf6)}
#av.f-sakura img{filter:drop-shadow(0 0 14px #f9a8d4)}
#av.f-gold img{filter:drop-shadow(0 0 10px #fbbf24) drop-shadow(0 0 22px #f59e0b)}
#avn{margin-top:6px;display:inline-block;background:rgba(20,16,36,.82);border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:4px 12px;font-size:14px;font-weight:700}
#avb{font-size:11px;opacity:.8;font-weight:600;margin-left:8px}
#avt{display:none;margin:6px auto 0;max-width:260px;background:rgba(255,255,255,.93);color:#1d1b2b;border-radius:12px;padding:6px 12px;font-size:13px}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes breathe{0%,100%{transform:scale(1)}50%{transform:scale(1.025)}}
@keyframes sway{0%,100%{transform:rotate(-1.2deg)}50%{transform:rotate(1.2deg)}}
@keyframes float{0%,100%{transform:translateY(0)}25%{transform:translateY(-10px)}75%{transform:translateY(4px)}}
</style></head><body><div id="wrap"></div><div id="nv"><div class="nt" id="nvt"></div><div class="nprev" id="nvp"></div><div class="ncur" id="nvc"></div><div class="nnext" id="nvn"></div><div class="ncr" id="nvr"></div></div><div id="sp"><img id="spi" alt=""><div class="spc" id="spc"></div><div class="spt" id="spt"></div></div><div id="np"><div id="npt"></div><div id="cr"></div></div><div id="av"><img id="avi" alt=""><div id="avnw"><span id="avn"></span><span id="avb"></span></div><div id="avt"></div></div><audio id="bgm"></audio><script>
var items=[],at=Date.now();
function mmss(s){s=Math.max(0,s);return Math.floor(s/60)+":"+("0"+(s%60)).slice(-2)}
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
function head(c,name,right){var h=el("div","tag");h.appendChild(el("span","",name));h.appendChild(el("span","",right));c.appendChild(h)}
function render(){var w=document.getElementById("wrap");w.textContent="";var dt=Math.floor((Date.now()-at)/1000);
 items.forEach(function(it){var c=el("div","card"),left=Math.max(0,it.left-dt);
  if(it.kind==="poll"){head(c,"Poll",it.ended?"Final":mmss(left));c.appendChild(el("div","t",it.title));
   it.options.forEach(function(o){var r=el("div","row"),l=el("div","lab");l.appendChild(el("span","",o.n+". "+o.label));l.appendChild(el("span","",o.count+" ("+o.pct+"%)"));
    var b=el("div","bar"),f=el("div","fill");f.style.width=o.pct+"%";b.appendChild(f);r.appendChild(l);r.appendChild(b);c.appendChild(r)});
   c.appendChild(el("div","big",it.total+" vote"+(it.total===1?"":"s")+(it.ended?"":" - comment the number to vote")))}
  else if(it.kind==="giveaway"){head(c,"Giveaway",it.drawn?"Drawn":mmss(left));c.appendChild(el("div","t",it.prize));
   if(it.drawn){c.appendChild(el("div","big",it.entries+" entered"));
    if(it.winners&&it.winners.length)c.appendChild(el("div","big hot","Winner: "+it.winners.join(", ")))}
   else{var k=el("div","big");k.appendChild(document.createTextNode("Comment "));k.appendChild(el("span","hot",'"'+it.keyword+'"'));k.appendChild(document.createTextNode(" to enter - "+it.entries+" in so far"));c.appendChild(k)}}
  else{head(c,"Flash sale",mmss(left));c.appendChild(el("div","t",it.product||"Flash sale"));
   var m=[];if(it.price)m.push(it.price);if(it.stock)m.push(it.stock+" left");if(m.length)c.appendChild(el("div","big hot",m.join(" - ")))}
  w.appendChild(c)})}
function poll(){fetch("/overlay/state").then(function(r){return r.json()}).then(function(d){items=d.items||[];at=Date.now();render();setMusic(d.music);setNovel(d.novel);setStory(d.story);setAvatar(d.avatar)}).catch(function(){})}
var bgm=document.getElementById("bgm"),mt=[],mi=0,mkey="",mtarget=0;
function playCur(){var t=mt[mi%mt.length];bgm.src=t.url;
 document.getElementById("npt").textContent="\u266A "+t.title+(t.artist?" - "+t.artist:"");document.getElementById("cr").textContent=t.credit||"";
 var pr=bgm.play();if(pr&&pr.catch)pr.catch(function(){document.getElementById("cr").textContent="Click once to start the music"})}
bgm.onended=function(){mi++;playCur()};
bgm.onerror=function(){mi++;if(mt.length>1)setTimeout(playCur,500)};
document.addEventListener("click",function(){if(mt.length&&bgm.paused)playCur()});
function setNovel(n){var b=document.getElementById("nv");
 if(!n){b.style.display="none";return}
 b.style.display="block";b.className=(n.theme||"dark")+" "+(n.size||"m");
 document.getElementById("nvt").textContent=(n.title||"")+(n.chapter?" - "+n.chapter:"")+(n.paused?" (paused)":"");
 document.getElementById("nvp").textContent=n.prev||"";
 var c=document.getElementById("nvc");c.textContent=n.text||"";c.className="ncur"+(n.role==="dialogue"?" d":"");
 document.getElementById("nvn").textContent=n.next||"";
 document.getElementById("nvr").textContent=[n.hint,n.credit].filter(Boolean).join("  |  ")}
var spKey="";
function setStory(n){var b=document.getElementById("sp");
 if(!n){b.style.display="none";spKey="";return}
 b.style.display="block";var im=document.getElementById("spi");
 if(n.image!==spKey){spKey=n.image;im.style.opacity=0;im.onload=function(){im.style.opacity=1};im.src=n.image+"?t="+Date.now()}
 var c=document.getElementById("spc");c.textContent=n.text||"";c.style.display=n.text?"block":"none";
 document.getElementById("spt").textContent=(n.title||"")+" - "+n.index+"/"+n.total+(n.paused?" (paused)":"")+(n.credit?"  |  "+n.credit:"")+(n.hint?"  |  "+n.hint:"")}
var avImgs={},avState=null,avTick=0;
function showAv(open){var a=avState;if(!a)return;var k=(open&&a.images.talking)?"talking":a.mood;var u=a.images[k]||a.images.idle;
 var im=document.getElementById("avi");if(im.getAttribute("data-u")!==u){im.setAttribute("data-u",u);im.src=u}}
function setAvatar(a){var b=document.getElementById("av");
 if(!a){b.style.display="none";avState=null;return}
 b.style.display="block";b.className=a.side+" m-"+a.motion+" f-"+a.frame+(a.paused?" rest":"");
 document.getElementById("avi").style.height=a.height+"vh";avState=a;
 document.getElementById("avn").textContent=a.name||"";document.getElementById("avn").style.display=a.name?"inline-block":"none";
 document.getElementById("avb").textContent=a.badge||"";
 Object.keys(a.images).forEach(function(k){if(avImgs[k]!==a.images[k]){avImgs[k]=a.images[k];(new Image()).src=a.images[k]}});showAv(false);tipTick()}
function tipTick(){var a=avState,t=document.getElementById("avt");
 if(!a||!a.tips||!a.tips.length||a.paused){t.style.display="none";return}
 t.style.display="block";t.textContent=a.tips[Math.floor(Date.now()/(a.tip_seconds*1000))%a.tips.length]}
setInterval(tipTick,1000);
setInterval(function(){if(avState&&avState.talking){avTick++;showAv(avTick%2===0)}},170);
function setMusic(m){if(!m||!m.enabled||!m.tracks||!m.tracks.length){bgm.pause();mkey="";mt=[];
  document.getElementById("npt").textContent="";document.getElementById("cr").textContent="";return}
 var key=m.tracks.map(function(t){return t.url}).join("|");mtarget=m.volume;
 if(key!==mkey){mkey=key;mt=m.tracks;mi=0;bgm.volume=mtarget;playCur()}}
setInterval(function(){var d=mtarget-bgm.volume;if(Math.abs(d)<0.02)bgm.volume=Math.min(1,Math.max(0,mtarget));else bgm.volume=Math.min(1,Math.max(0,bgm.volume+(d>0?0.03:-0.03)))},100);
setInterval(poll,2000);setInterval(render,1000);poll();
</script></body></html>"""
