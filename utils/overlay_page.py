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
</style></head><body><div id="wrap"></div><script>
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
function poll(){fetch("/overlay/state").then(function(r){return r.json()}).then(function(d){items=d.items||[];at=Date.now();render()}).catch(function(){})}
setInterval(poll,2000);setInterval(render,1000);poll();
</script></body></html>"""
