from html import escape
import json
import pandas as pd
from engine import DATES,STAGES,CHANNEL_COLORS

def rate_text(n,d):
    return f'{n/d:.0%} · {n:,}/{d:,}'+(' · small n' if d<30 else '') if d else '— · 0/0'

def funnel_html(clean):
    counts=[int(clean[c].notna().sum()) for c in DATES]
    return '<div class="funnel">'+''.join(f'<div><span>{stage.title()}</span><b>{count:,}</b><small>{rate_text(count,counts[i-1]) if i else "Initial contacts"}</small><div class="bar"><i style="width:{100*count/max(1,counts[0])}%"></i></div></div>' for i,(stage,count) in enumerate(zip(STAGES,counts)))+'</div>'

def heatmap_html(summary):
    if summary.empty:return '<p>No valid channel records.</p>'
    html='<div class="table-scroll"><table class="heatmap"><caption>Conditional conversion · percentage and count</caption><thead><tr><th>Channel</th><th>Response</th><th>Qualification</th><th>Activation</th></tr></thead><tbody>'
    for _,r in summary.iterrows():
        color=CHANNEL_COLORS.get(r.Channel,'#526a86');counts=[int(r[s]) for s in STAGES]
        html+=f'<tr><th><span class="channel-dot" style="background:{color}"></span>{escape(r.Channel)}</th>'
        for n,d in zip(counts[1:],counts[:-1]):
            html+=f'<td style="background:color-mix(in srgb,{color} {round(8+18*n/max(1,d))}%,white)">{rate_text(n,d)}</td>'
        html+='</tr>'
    return html+'</tbody></table></div>'

def timeline_html(row,as_of):
    html='<ol class="timeline">';previous=None
    for stage,field in zip(STAGES,DATES):
        value=row[field]
        if pd.isna(value):
            gap=(as_of-previous.date()).days if previous is not None else 0
            html+=f'<li class="pending"><b>{stage.title()}</b><span>No event recorded</span><em>{gap}d waiting</em></li>';break
        gap=f'{(value-previous).days}d after previous step' if previous is not None else 'First contact'
        html+=f'<li><b>{stage.title()}</b><span>{value:%b %d}</span><em>{gap}</em></li>';previous=value
    return html+'</ol>'

def demo_html(total,invalid,qualified,active,stalled,threshold=14,dummy=True):
    slides=[['The job','Find qualified experts who have not started working. Decide what to investigate next.'],['Check the export',f'{total:,} input rows ({"dummy" if dummy else "uploaded"} data). {invalid} rows need correction before the funnel can be trusted.'],['Find the opportunity',f'{stalled} illustrative qualified records have waited {threshold}+ days without activation. The queue shows timelines and next actions.'],['Record the reason','Choose onboarding confusion, missing event, no longer interested, scheduling, or another verified reason. Export notes before leaving.'],['Size and test',f'{active} illustrative activations are the current baseline. Compare potential improvements, estimate capacity, and design a pilot. No real impact is claimed.']]
    data=json.dumps(slides).replace('<','\\u003c')
    return '''<html><style>*{box-sizing:border-box}body{margin:0;font:15px Arial;color:#253244}.demo{border:1px solid #dfe5ef;border-radius:10px;padding:24px;background:#f8faff;min-height:235px}.top{display:flex;justify-content:space-between;align-items:center;gap:12px}small{color:#566980;font-size:12px}h3{font-size:23px;font-weight:500;margin:25px 0 12px}p{line-height:1.6;margin:0;max-width:780px}button{padding:9px 12px;border-radius:6px;background:white;border:1px solid #c7d4e6;color:#285ca7;cursor:pointer}button:focus-visible{outline:3px solid #9fbbef}.track{height:3px;background:#dde5f0;margin-top:24px}.fill{height:100%;background:#2e65cf;transition:width .2s}.bottom{display:flex;gap:8px;margin-top:12px}input{flex:1;min-width:80px;accent-color:#2e65cf}.story{animation:slide .35s ease}@keyframes slide{from{transform:translateX(12px);opacity:0}to{transform:none;opacity:1}}@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}@media(max-width:500px){.demo{padding:16px}h3{font-size:20px}.top{flex-wrap:wrap}}</style><div class="demo"><div class="top"><small>GUIDED · 30-SECOND WALKTHROUGH</small><button id="play">Play walkthrough</button></div><div id="story"></div><div class="track"><div class="fill" id="fill"></div></div><div class="bottom"><button id="prev" aria-label="Previous chapter">←</button><input type="range" id="range" min="0" max="4" value="0" aria-label="Walkthrough chapter"><button id="next" aria-label="Next chapter">→</button><button id="reset">Replay</button></div></div><script>const slides='''+data+''';let i=0,playing=false,elapsed=0,last=performance.now();function show(){story.innerHTML='<div class="story"><h3>'+slides[i][0]+'</h3><p>'+slides[i][1]+'</p></div>';range.value=i;play.textContent=playing?'Pause':'Play walkthrough';fill.style.width=((i+elapsed/6000)/5*100)+'%'}play.onclick=()=>{if(i===4&&elapsed>=6000){i=0;elapsed=0}playing=!playing;show()};range.oninput=()=>{i=+range.value;elapsed=0;playing=false;show()};prev.onclick=()=>{i=Math.max(0,i-1);elapsed=0;show()};next.onclick=()=>{i=Math.min(4,i+1);elapsed=0;show()};reset.onclick=()=>{i=0;elapsed=0;playing=true;show()};function tick(t){if(playing&&!document.hidden){elapsed+=Math.min(t-last,100);if(elapsed>=6000){if(i<4){i++;elapsed=0}else{elapsed=6000;playing=false}show()}fill.style.width=((i+elapsed/6000)/5*100)+'%'}last=t;requestAnimationFrame(tick)}show();requestAnimationFrame(tick);</script></html>'''

def clipboard_html(text):
    data=json.dumps(text).replace('<','\\u003c')
    return '''<html><style>body{margin:0;font:14px Arial}button{font:inherit;border:1px solid #becce0;border-radius:6px;padding:9px 14px;background:white;color:#285ca7;cursor:pointer}span{margin-left:10px;color:#586779}</style><button id="copy">Copy draft</button><span id="status" role="status"></span><script>const text='''+data+''';const status=document.getElementById('status');document.getElementById('copy').onclick=async()=>{try{await navigator.clipboard.writeText(text);status.textContent='Copied'}catch(e){const box=document.createElement('textarea');box.value=text;document.body.appendChild(box);box.select();const ok=document.execCommand('copy');box.remove();status.textContent=ok?'Copied':'Use the text download instead'}};</script></html>'''
