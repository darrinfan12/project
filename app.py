from datetime import date
from pathlib import Path
from html import escape
import math
import hashlib
import json
import os
import pandas as pd
import altair as alt
import streamlit as st
import streamlit.components.v1 as components
from engine import *
from views import funnel_html,heatmap_html,timeline_html,demo_html,rate_text
from sourcing_ui import discovery_ui,outreach_ui
from strategy import strategy_ui

st.set_page_config(page_title='Expert Pipeline | Darrin Fan',page_icon='◈',layout='wide')
st.markdown(Path(__file__).with_name('style.html').read_text(),unsafe_allow_html=True)
PAGES=['Overview','Follow-up queue','Pipeline performance','Channel strategy','Capacity planner','Experiment plan','Data quality','Expert discovery','Outreach drafts']
def slug(s):return s.lower().replace(' ','-')
def jump(label,destination):st.markdown(f'<a class="section-link" href="#{slug(destination)}" target="_self">{escape(label)}</a>',unsafe_allow_html=True)
def section(name,title,line):st.markdown(f'<section id="{slug(name)}" class="chapter-heading"><div class="eyebrow">{escape(name)}</div><h2>{title}</h2><p>{line}</p></section>',unsafe_allow_html=True)
def csv(data):
    # Spreadsheet exports should not execute untrusted text as formulas.
    safe=data.copy()
    for col in safe.select_dtypes(include=['object','string']).columns:
        safe[col]=safe[col].map(lambda v: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v)
    return safe.to_csv(index=False)
with st.sidebar:
    st.markdown('<div class="brand">◈ <span>Expert Pipeline</span></div><p class="workspace">DARRIN FAN · WORK SAMPLE</p>',unsafe_allow_html=True)
    nav=st.empty()
    st.divider()
    threshold=st.radio('Flag qualified records after', [7,14,30],index=1,horizontal=True,format_func=lambda n:f'{n} days',key='threshold')
    effect=st.empty()
    with st.expander('Change data source'):
        mode=st.radio('Pipeline source',['Dummy data','Upload CSV'])
        as_of=st.date_input('Analysis date',SAMPLE_DATE)
        uploaded=st.file_uploader('Choose pipeline CSV',type='csv') if mode=='Upload CSV' else None
        st.download_button('Download sample CSV',csv(demo_data()),'dummy_pipeline.csv','text/csv')
        st.caption('Required: '+', '.join(COLUMNS)+'. Optional: acquisition_cost_usd. Use IDs, not contact details.')
raw=demo_data();data_error=None
if mode=='Upload CSV':
    if uploaded is None:data_error='Choose a CSV under Change data source. The dummy pipeline remains visible until a valid file is loaded.'
    else:
        try:raw=pd.read_csv(uploaded,dtype=str,keep_default_na=False)
        except Exception:data_error='This file could not be read as CSV. Export a UTF-8 CSV using the sample columns and try again.'
try:
    clean,issues=validate(raw,as_of)
except ValueError as exc:
    data_error=str(exc)+'. The dummy pipeline remains visible.'
    raw=demo_data();clean,issues=validate(raw,as_of)
dummy=mode=='Dummy data' or data_error is not None
if data_error:
    raw=demo_data();clean,issues=validate(raw,as_of)
fingerprint=hashlib.sha256(raw.to_csv(index=False).encode()).hexdigest()
if st.session_state.get('fingerprint')!=fingerprint:
    st.session_state.update(fingerprint=fingerprint,reviewed=[],notes={})
reviewed=st.session_state['reviewed'];notes=st.session_state['notes']
all_actions=action_queue(clean,as_of,threshold)
queue=all_actions[all_actions.stage=='qualified'].copy()
queue['Urgency']=queue.days_waiting.map(lambda d:'High · >30d' if d>30 else 'Watch · 14–30d' if d>=14 else 'Early · 7–13d')
queue['Review']=queue.record_id.map(lambda rid:'Reviewed' if rid in reviewed else 'Open')
queue['Reason']=queue.record_id.map(lambda rid:notes.get(rid,{}).get('reason','Not investigated'))
queue['Note']=queue.record_id.map(lambda rid:notes.get(rid,{}).get('note',''))
counts=[int(clean[c].notna().sum()) for c in DATES]
summary=channel_metrics(clean)
rates=observed_rates(clean)
effect.caption(' · '.join(f'{days}d → {int((action_queue(clean,as_of,days).stage=="qualified").sum())}' for days in [7,14,30]))
nav.markdown('<nav class="chapter-nav" aria-label="Sections">'+''.join(f'<a href="#{slug(p)}" target="_self">{p}'+(f'<span class="nav-count">{len(queue)}</span>' if p=='Follow-up queue' else '')+'</a>' for p in PAGES)+'</nav>',unsafe_allow_html=True)
st.markdown('<div class="data-chip">'+('ILLUSTRATIVE · DUMMY DATA' if dummy else 'UPLOADED DATA · UNVERIFIED')+f'<span>As of {as_of:%b %d, %Y}</span></div>',unsafe_allow_html=True)
if data_error:st.warning(data_error)

st.markdown(f'<div id="overview" class="chapter-heading hero"><div class="eyebrow">A WEEK-ONE GROWTH OPERATIONS APPROACH</div><h1>{len(queue):,} qualified experts<br><span>waiting {threshold}+ days.</span></h1><p>{rate_text(len(queue),counts[2])} qualified records have no activation event. Inspect the queue, record a reason, and test a fix.</p></div>',unsafe_allow_html=True)
st.markdown('<p class="pitch">“The data is invented, but this is how I’d find stalled experts, size the prize and test a fix on your real export.”</p>',unsafe_allow_html=True)
st.caption('How to use: 1. Inspect the qualified queue. 2. Compare channel strategies and staffing. 3. Export a pilot with explicit assumptions.')
jump('Choose the next experiment →','Channel strategy')
with st.expander('Run a 90-second interview walkthrough'):
    st.markdown('**0–20s · Problem:** How should a growth team allocate limited recruiting resources? This is an illustrative model, not company performance.\n\n**20–45s · Decision:** Open Channel strategy. Compare the entered-volume optimum with the 100-per-week referral ceiling. Explain which constraint changes the allocation.\n\n**45–65s · Uncertainty:** Review numeric conservative/base/optimistic results for the same allocation. These are sensitivity cases, not confidence intervals.\n\n**65–90s · Validation:** Show the experiment fields and PDF. First verify definitions, sourcing capacity, costs, and quality on an authorized export, then run a feasibility pilot.')
with st.expander('Assumptions and questions to prepare'):
    st.markdown('**Why build it?** To explore resource allocation and expert activation as an operational problem.\n\n**Where do the rates come from?** Seeded invented records; planning starts from that sample. Validate with cohort-specific real data before deciding.\n\n**Why referrals?** They have favorable entered unit economics. That result depends on supply ceilings, labor and stable rates; the constrained example shows when it changes.\n\n**What changes with real data?** Agree on stage definitions, reconcile missing events, compare equally mature cohorts, and measure full costs and task quality.\n\n**Why not Excel?** Excel can perform these calculations. This app standardizes validation, review, scenario comparison and reporting in a reusable workflow; adoption depends on actual team needs.\n\n**Development disclosure:** Built with AI-assisted coding. Darrin should personally understand the formulas, optimizer constraints, limitations and tests before presenting them. Automated tests and visual checks do not prove business impact.\n\n**After team feedback:** Record the observed problem, evidence and decision it changes before building another feature.')
with st.expander('Watch the 30-second walkthrough',expanded=False):
    st.caption('Fixed illustrative example · October 28, 2026 · 14-day threshold. The animation does not change with uploads or planner settings. Command text illustrates the workflow; it is not an executable CLI.')
    components.html(Path(__file__).with_name('walkthrough.html').read_text(),height=790,scrolling=True)
left,right=st.columns([1.3,1])
with left:
    st.subheader('From contact to first task')
    st.markdown(funnel_html(clean),unsafe_allow_html=True)
with right:
    st.subheader('First five to review')
    if queue.empty:st.info('No qualified records meet this threshold. Try 7 days or inspect another cohort.')
    else:st.dataframe(queue.head(5)[['record_id','channel','days_waiting']].rename(columns={'record_id':'Record','channel':'Channel','days_waiting':'Days waiting'}),hide_index=True,width='stretch',height=212)
    jump(f'Review all {len(queue)} stalled experts →','Follow-up queue')
st.caption(f'{len(issues)}/{len(raw)} rows excluded ({len(issues)/max(1,len(raw)):.1%}). Counts are illustrative when dummy data is selected; a larger fictional dataset is still not evidence of impact.')
st.markdown(heatmap_html(summary),unsafe_allow_html=True)

section('Follow-up queue','Review the record. <span>Capture the reason.</span>','Qualified records only, ordered by days waiting. Review marks and notes are session-only—export them before leaving.')
a,b,c=st.columns([2,1,1])
channel_filter=a.multiselect('Filter channels',sorted(clean.channel.unique()))
status=b.selectbox('Review status',['Open','Reviewed','All'])
search=c.text_input('Find record',placeholder='DEMO-…')
shown=queue.copy()
if channel_filter:shown=shown[shown.channel.isin(channel_filter)]
if status!='All':shown=shown[shown.Review==status]
if search:shown=shown[shown.record_id.str.contains(search,case=False,regex=False)]
st.download_button('Export queue, reasons & notes',csv(queue),'review_queue.csv','text/csv',key='export_queue_top')
selected_context={'dummy':dummy}
list_col,detail_col=st.columns([1.35,1],gap='medium')
with list_col:
    if shown.empty:st.info('No records match. Clear the search or switch to All review statuses.')
    else:
        table=shown[['record_id','channel','days_waiting','Urgency','Review']].rename(columns={'record_id':'Record','channel':'Channel','days_waiting':'Days'})
        def urgency_style(v):return 'color:#973222;background-color:#fcebe7' if str(v).startswith('High') else 'color:#775014;background-color:#fff2d5' if str(v).startswith('Watch') else ''
        event=st.dataframe(table.style.map(urgency_style,subset=['Urgency']),hide_index=True,width='stretch',height=420,on_select='rerun',selection_mode='single-row',key='queue_table')
        st.caption('Select a row to inspect its timeline. Urgency includes a text label as well as color.')
with detail_col:
    if not shown.empty:
        selected_rows=event.selection.rows
        index=selected_rows[0] if selected_rows and selected_rows[0]<len(shown) else 0
        item=shown.iloc[index];rid=item.record_id;record=clean[clean.record_id==rid].iloc[0]
        selected_context={'dummy':dummy,'record_id':rid,'channel':item.channel,'days':int(item.days_waiting)}
        st.markdown(f'<div class="record-title"><b>{escape(rid)}</b><span>{escape(item.channel)} · {item.days_waiting}d waiting</span></div>',unsafe_allow_html=True)
        st.markdown(timeline_html(record,as_of),unsafe_allow_html=True)
        reasons=['Not investigated','Onboarding confusion','Missing event','No longer interested','Scheduling','Other']
        saved=notes.get(rid,{})
        with st.form('review_'+fingerprint[:8]+'_'+rid):
            reason=st.selectbox('Verified reason',reasons,index=reasons.index(saved.get('reason','Not investigated')))
            note=st.text_input('Short note',saved.get('note',''),placeholder='What did you verify?')
            if st.form_submit_button('Save reason & note'):
                notes[rid]={'reason':reason,'note':note};st.rerun()
        if rid not in reviewed:
            if st.button('Mark record reviewed',type='primary'):reviewed.append(rid);st.rerun()
        elif st.button('Reopen record'):reviewed.remove(rid);st.rerun()
        jump('Prepare a follow-up draft →','Outreach drafts')
if notes:
    st.info(f'{len(notes)} records have session notes. Export now to retain them; refreshing or leaving may discard this session.')
    st.download_button('Save notes before leaving',csv(queue),'review_notes.csv','text/csv')

section('Pipeline performance','See the pattern. <span>Keep the denominator.</span>','Compare channel conversion, weekly cohorts, time to activation, and modeled acquisition cost. Recent cohorts have had less time to convert.')
if clean.empty:st.info('No valid records are available. Correct the CSV or load the dummy sample.')
else:
    cols=st.columns(3)
    for i,(_,r) in enumerate(summary.iterrows()):
        color=CHANNEL_COLORS.get(r.Channel,'#526a86')
        values=[int(r[s]) for s in STAGES]
        with cols[i%3]:
            st.markdown('<div class="channel-card"><b style="border-left:3px solid '+color+'">'+escape(r.Channel)+'</b>'+''.join(f'<div class="channel-rate"><span>{STAGES[j+1].title()}</span><strong>{rate_text(values[j+1],values[j])}</strong><div class="bar"><i style="background:{color};width:{100*values[j+1]/max(1,values[j])}%"></i></div></div>' for j in range(3))+'</div>',unsafe_allow_html=True)
    st.caption('“Small n” flags denominators below 30; it is not a significance test. Channel mix, maturity, and invented outcomes prevent causal conclusions.')
    st.subheader('Weekly contact cohorts')
    cohort=clean.copy();cohort['Week']=cohort.contacted_at.dt.to_period('W-SUN').dt.start_time
    selected_channels=st.multiselect('Channels in cohort chart',list(CHANNEL_COLORS),default=list(CHANNEL_COLORS),key='cohort_channels')
    cohort=cohort[cohort.channel.isin(selected_channels)]
    weekly_rows=[]
    for (week,ch),g in cohort.groupby(['Week','channel']):
        weekly_rows.append({'Week':week,'Channel':ch,'Contacts':len(g),'Activated':int(g.activated_at.notna().sum()),'Activation share':g.activated_at.notna().mean()})
    weeks=pd.DataFrame(weekly_rows)
    if weeks.empty:st.info('Choose at least one channel to view weekly cohorts.')
    else:
        chart=alt.Chart(weeks).mark_line(point=True).encode(x=alt.X('Week:T',title='Contact week'),y=alt.Y('Activation share:Q',axis=alt.Axis(format='%'),title='Activated / contacts'),color=alt.Color('Channel:N',scale=alt.Scale(domain=list(CHANNEL_COLORS),range=list(CHANNEL_COLORS.values()))),tooltip=['Channel','Week:T','Contacts','Activated',alt.Tooltip('Activation share:Q',format='.0%')]).properties(height=240)
        st.altair_chart(chart,use_container_width=True)
        with st.expander('Read cohort counts'):
            view=weeks.copy();view['Activation share']=view.apply(lambda r:rate_text(r.Activated,r.Contacts),axis=1)
            st.dataframe(view,hide_index=True,width='stretch')
    st.subheader('Time and cost to activate')
    metrics=[]
    for _,r in summary.iterrows():
        metrics.append({'Channel':r.Channel,'Activated / contacted':rate_text(int(r.activated),int(r.contacted)),'Median contact → activation':f'{r["Median days to activation"]:.1f} days' if pd.notna(r['Median days to activation']) else '—','Cost / activated expert':f'${r["Cost per activation"]:,.0f}' if pd.notna(r['Cost per activation']) else 'Not supplied'})
    st.dataframe(pd.DataFrame(metrics),hide_index=True,width='stretch')
    st.caption('Time includes completed activations only (survivorship bias). Cost = all recorded acquisition cost in the channel / activations, not incremental recovery cost. Sample costs are invented; missing uploaded costs remain unavailable.')
    st.download_button('Export channel analysis',csv(summary),'channel_analysis.csv','text/csv')

section('Channel strategy','Compare strategies. <span>Choose what to test.</span>','Model channel allocation for a target persona, inspect tradeoffs, and export a testable proposal.')
strategy_ui(summary)

section('Capacity planner','Match the target <span>to the available hours.</span>','Defaults use the same observed sample funnel above. Compare scenarios without confusing assumptions with measured results.')
results_slot=st.container()
control_a,control_b,control_c=st.columns(3)
preset=control_a.selectbox('Rate preset',['Observed','Conservative','Optimistic','Custom assumptions'])
target=control_b.number_input('Target activations',1,50000,100)
weekly_hours=control_c.number_input('Team hours / week',0.0,10000.0,30.0)
deadline=st.date_input('Planning deadline',date(2026,12,9))
modeled_rates=rates.copy()
if preset=='Conservative':modeled_rates=[r*.8 for r in rates]
elif preset=='Optimistic':modeled_rates=[min(1,r*1.2) for r in rates]
elif preset=='Custom assumptions':
    rc=st.columns(3)
    modeled_rates=[rc[i].slider(label,0,100,int(round(r*100)))/100 for i,(label,r) in enumerate(zip(['Response (%)','Qualification (%)','Activation (%)'],rates))]
st.caption(' · '.join(f'{label}: {value:.1%}' for label,value in zip(['Response','Qualification','Activation'],modeled_rates))+f' · End-to-end: {math.prod(modeled_rates):.1%}')
if preset in ['Conservative','Optimistic']:st.caption('Illustrative sensitivity only: −20% or +20% relative change at every stage, capped at 100%.')
with st.expander('Adjust effort and cost assumptions'):
    cols=st.columns(4)
    minutes=[cols[i].number_input(label,0.0,10000.0,value) for i,(label,value) in enumerate([('Minutes / contact',2.0),('Minutes / reply',8.0),('Minutes / qualified',20.0),('Minutes / activation',10.0)])]
    a,b=st.columns(2);hourly=a.number_input('Labor $ / hour',0.0,10000.0,35.0);tools=b.number_input('Tools $ / contact',0.0,10000.0,.30)
base=plan(target,modeled_rates,minutes,hourly,tools)
budget=max(0,(deadline-as_of).days)/7*weekly_hours
with results_slot:
    st.markdown('<div class="results-marker"></div>',unsafe_allow_html=True)
    if base is None:st.warning('The target cannot be reached with a zero conversion stage. Choose a nonzero custom rate or load a pipeline with completed stages.')
    else:
        cols=st.columns(3)
        for col,label,val in zip(cols,['Contacts needed','Staff hours needed','Modeled cost'],[f'{base["Contacts"]:,}',f'{base["Hours"]:,.1f}',f'${base["Cost"]:,.0f}']):col.metric(label,val)
        total=max(base['Hours'],budget,1)
        st.markdown(f'<div class="capacity-bars"><span>Required · {base["Hours"]:.1f}h</span><div class="bar"><i style="width:{base["Hours"]/total*100}%"></i></div><span>Available · {budget:.1f}h</span><div class="bar"><i style="background:#267e70;width:{budget/total*100}%"></i></div></div>',unsafe_allow_html=True)
        st.write(f'**{max(0,base["Hours"]-budget):.1f}-hour gap**' if base['Hours']>budget else f'**{budget-base["Hours"]:.1f} hours of modeled headroom**')
if deadline<=as_of:st.warning('Choose a deadline after the analysis date; available capacity is zero.')
st.caption('Observed means observed in the selected dataset, including dummy data. Staff effort and cost inputs are still assumptions. Calendar capacity excludes response lag, expert compensation, and fixed overhead.')

section('Experiment plan','Size the prize. <span>Then choose a pilot.</span>','Rank illustrative levers, inspect recorded reasons, and compare the proposed pilot with the sample needed for a powered test.')
a,b,c=st.columns(3)
prize_targets=[a.slider('Response target (%)',1,100,45)/100,b.slider('Qualification target (%)',1,100,70)/100,c.slider('Activation target (%)',1,100,65)/100]
prizes=prize_table(clean,prize_targets)
if prizes.empty:st.info('No positive lift under these targets. Increase a target to explore a scenario.')
else:
    display=prizes.copy();display['Baseline']=display.apply(lambda r:f'{r.Baseline:.0%} · n={r.Denominator}',axis=1);display['Target']=display.Target.map(lambda x:f'{x:.0%}');display['Illustrative added activations']=display['Illustrative added activations'].map(lambda x:f'+{x:.1f}')
    st.dataframe(display.drop(columns='Denominator'),hide_index=True,width='stretch',height=260)
st.caption('Each row changes one stage, holds the others constant, and applies to that channel’s whole contact cohort. These are invented opportunities, not forecasts; overlapping gains cannot be added.')
reasons_count=pd.Series([v['reason'] for v in notes.values() if v.get('reason')!='Not investigated']).value_counts()
if reasons_count.empty:st.info('No reasons recorded yet. Review records above before attributing the delay to onboarding.')
else:st.bar_chart(reasons_count.rename('Operator-reviewed records'),color='#3c6fd1',height=180)
channel_options=sorted(clean.channel.unique()) or ['No valid channel']
activation_prizes=prizes[prizes.Lever=='Activation'] if not prizes.empty else prizes
focus=activation_prizes.iloc[0].Channel if not activation_prizes.empty else channel_options[0]
chosen=st.selectbox('Channel for onboarding pilot',channel_options,index=channel_options.index(focus))
g=clean[clean.channel==chosen];q=int(g.qualified_at.notna().sum());ac=int(g.activated_at.notna().sum());stalled=int((queue.channel==chosen).sum());baseline=ac/q if q else 0
recovery=st.slider('Illustrative share of stalled experts reactivated (%)',0,100,50)/100
extra=stalled*recovery
st.write(f'**Illustrative recovery opportunity:** {stalled} stalled × {recovery:.0%} = **+{extra:.1f} activations**'+(f' (**+{extra/counts[3]:.0%}** vs {counts[3]} current activations).' if counts[3] else '.'))
st.caption('These records have already incurred acquisition effort in the model. Recovery still requires staff time; zero new outreach does not mean zero cost. Do not add this recovery estimate to the whole-cohort scenario table.')
st.write('**Why pilot onboarding?** The queue identifies an existing qualified cohort and gives the operator a concrete intervention to investigate. The ranked table may favor another lever on volume; this choice prioritizes access to a reviewable cohort, not proven ROI.')
test_target=max(baseline,min(.95,prize_targets[2]))
n=sample_size_per_arm(baseline,test_target)
st.info(f'Power reference: 37% → 55% requires about 120 people per arm (80% power, two-sided α=5%, equal groups; normal approximation). For {baseline:.0%} → {test_target:.0%} here: '+(f'about {n} per arm.' if n else 'choose a distinct nonzero baseline and target.')+f' This channel has {stalled} currently stalled qualified records. Treat the initial work as a feasibility pilot, not a powered win.')
with st.expander('Edit the pilot proposal'):
    hypothesis=st.text_area('Hypothesis','A clearer checklist and one timely reminder may improve first-task completion among eligible qualified experts.')
    criterion=st.text_area('Decision rule','Use the pilot to validate event tracking, message clarity, and staff effort. Plan a larger randomized test only after agreeing on a baseline, meaningful lift, sample size, and quality guardrails.')
memo=f'''# Illustrative expert acquisition pilot

Built by Darrin Fan · darrinfan@gmail.com

The data is invented, but this is how I would find stalled experts, size the prize and test a fix on your real export.

Data source: {'DUMMY DATA — all numbers below are illustrative' if dummy else 'User-uploaded, unverified records; projections remain illustrative'}. Analysis date: {as_of}.

## Illustrative diagnosis
{len(clean):,} valid records; {counts[2]} qualified; {counts[3]} activated; {len(queue)} qualified records waiting {threshold}+ days. Validation held {len(issues)} of {len(raw)} input rows ({len(issues)/max(1,len(raw)):.1%}).

## Illustrative opportunity and choice
{chosen}: {stalled} stalled qualified records. An assumed {recovery:.0%} recovery implies +{extra:.1f} activations. This is not a measured result or cost-free recovery. Compare alternative levers in the ranked scenario export. Onboarding is chosen for an inspectable qualified cohort, not a proven highest ROI.

## Hypothesis
{hypothesis}

## Pilot design
Review event history and operator reasons first. Define eligible qualified experts. For a later randomized test, compare current onboarding with a clear checklist and one reminder; follow all randomized participants for a full 14 days. Primary metric: first-task completion within 14 days / all randomized eligible experts. Track task quality, opt-outs, and operator minutes.

## Power and decision rule
A 37% to 55% change needs about 120 participants per arm at 80% power and two-sided 5% alpha under a normal approximation. The available stalled cohort is not automatically representative of newly qualified experts. Establish a cohort-specific baseline and sample size. The first pilot tests feasibility, not efficacy.
{criterion}

## Illustrative capacity
Preset: {preset}. End-to-end conversion: {math.prod(modeled_rates):.1%}. Target: {target}. Required hours: {base['Hours'] if base else 'unreachable'}; available hours: {budget:.1f}. Effort and cost are assumptions. No measured business impact is claimed.

## How this plugs in
ATS or Airtable CSV export → scheduled daily validation and stall check → human-reviewed digest of newly stalled records → existing Slack workflow. This app supplies the local calculation and digest, not a live ATS or Slack connection.
'''
st.download_button('Export illustrative pilot brief',memo,'illustrative_pilot.md','text/markdown')
st.download_button('Export ranked opportunities',csv(prizes),'illustrative_opportunities.csv','text/csv')

section('Data quality','Check the inputs.','Resolve duplicate IDs, missing stages, invalid dates, and costs before interpreting the funnel.')
if issues.empty:st.success('All rows passed the structural checks.')
else:st.dataframe(issues.rename(columns={'csv_row':'CSV row','record_id':'Record','issue':'Issue'}),hide_index=True,width='stretch',height=210)
st.download_button('Export validation issues',csv(issues),'validation_issues.csv','text/csv')
with st.expander('Read definitions and data contract'):
    st.write('Contacted = invitation sent; responded = any reply; qualified = meets a documented project rubric; activated = first task completed. Required columns: '+', '.join(COLUMNS)+'. Dates: YYYY-MM-DD. Optional acquisition_cost_usd: nonnegative cost accrued for the record. All copies of duplicate IDs are held.')
    st.write('Dummy generator: 1,800 intended records across six channels and 17 contact weeks, seeded randomness, channel/week variation, delayed events, and three added error rows. It demonstrates analysis, not inference about AfterQuery. No private company data is used.')

section('Expert discovery','Find evidence to investigate.','Start with a practitioner domain such as civil engineering; publication authorship alone does not verify professional experience or project fit.')
discovery_ui()

section('Outreach drafts','Prepare the follow-up.','Use the selected record or research lead to draft a message. Copy or export it—this shared app cannot send email.')
outreach_ui(selected_context)

st.divider()
st.subheader('How this plugs in')
st.markdown('<div class="integration">ATS / Airtable export <span>→</span> Daily validation + stall check <span>→</span> Digest of newly stalled experts <span>→</span> Existing Slack workflow</div>',unsafe_allow_html=True)
st.caption('The included daily_digest.py creates a local digest and previous-run state. Scheduling, ATS export, and Slack delivery are integration steps, not connected services in this demo.')
repo=os.getenv('PUBLIC_REPO_URL','https://github.com/darrinfan12/project')
if repo:st.link_button('Inspect the source repository',repo)
else:
    source_files=['decision.py','strategy.py','app.py','engine.py','views.py','sourcing_ui.py','outreach.py','daily_digest.py','requirements.txt','README.md','style.html','scroll.html','walkthrough.html','.streamlit/config.toml']
    import io,zipfile
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in source_files:
            path=Path(__file__).parent/file
            if path.exists():archive.writestr(file,path.read_bytes())
    st.download_button('Download the source code',buffer.getvalue(),'expert_pipeline_source.zip','application/zip')
st.markdown('<footer><b>Built by Darrin Fan</b><p>Drawing on my Deloitte experience building Alteryx data pipelines.</p><a href="mailto:darrinfan@gmail.com">darrinfan@gmail.com</a><span>Independent work sample · Illustrative analysis, not measured business impact.</span></footer>',unsafe_allow_html=True)
components.html(Path(__file__).with_name('scroll.html').read_text(),height=0)
