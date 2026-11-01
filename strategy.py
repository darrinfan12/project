"""Editable strategy scenarios; separate from the record-level review queue."""
import json
import math
import pandas as pd
import streamlit as st
from engine import sample_size_per_arm
from decision import decision_ui

PERSONAS={
 'Finance / credit analysis':('Investment and credit practitioners','Relevant credit analysis experience; assess a sample of written reasoning.','Finance associations, alumni networks, referrals'),
 'Software engineering':('Practicing software engineers','Recent production experience; assess a task in the relevant language.','Technical communities, developer networks, referrals'),
 'Civil engineering':('Practicing civil engineers','Relevant project experience and jurisdiction-specific credentials where needed.','Engineering associations, conferences, referrals'),
 'Legal':('Practitioners in the required practice area','Verify jurisdiction, practice-area experience, and applicable credentials.','Bar associations, practice-area networks, referrals'),
}

def aggregate_validate(df):
    cols=['channel','contacts','responses','qualified','activated','cost']
    if not set(cols)<=set(df):raise ValueError('Required columns: '+', '.join(cols))
    d=df[cols].copy()
    if d.empty:raise ValueError('The file has no rows.')
    if d.channel.isna().any() or d.channel.astype(str).str.strip().eq('').any() or d.channel.duplicated().any():raise ValueError('Use a unique, nonempty channel name per row.')
    for c in cols[1:]:
        d[c]=pd.to_numeric(d[c],errors='coerce')
        if not d[c].map(lambda x:pd.notna(x) and math.isfinite(x) and x>=0).all():raise ValueError(c+' must contain finite nonnegative numbers.')
        if c!='cost' and (d[c]%1!=0).any():raise ValueError('Stage counts must be whole numbers.')
    if not ((d.contacts>=d.responses)&(d.responses>=d.qualified)&(d.qualified>=d.activated)).all():raise ValueError('Counts must satisfy contacts ≥ responses ≥ qualified ≥ activated.')
    return d

def model(df):
    d=df.copy()
    for c in ['Contacts','Response %','Qualification %','Activation %','Labor hours','Nonlabor cost $']:
        d[c]=pd.to_numeric(d[c],errors='coerce')
        if not d[c].map(lambda x:pd.notna(x) and math.isfinite(x) and x>=0).all():raise ValueError('Complete every numeric assumption with a finite, nonnegative value.')
    if d.Channel.isna().any() or d.Channel.astype(str).str.strip().eq('').any() or d.Channel.duplicated().any():raise ValueError('Give every scenario a unique channel name.')
    if (d[['Response %','Qualification %','Activation %']]>100).any().any():raise ValueError('Conversion rates cannot exceed 100%.')
    d['Modeled responses']=d.Contacts*d['Response %']/100
    d['Modeled qualified']=d['Modeled responses']*d['Qualification %']/100
    d['Modeled activations']=d['Modeled qualified']*d['Activation %']/100
    return d

def strategy_ui(summary):
    st.caption('1. Choose a persona. 2. Compare editable channel assumptions. 3. Specify a test. These scenarios do not change the record-level queue.')
    category=st.selectbox('Target expert category',list(PERSONAS))
    persona,qualification,sources=PERSONAS[category]
    st.write(f'**Target persona:** {persona}. **Qualification check:** {qualification}')
    st.caption('Potential sourcing routes: '+sources+'. Illustrative strategy only; no assumed industry conversion advantage or claim about AfterQuery priorities.')
    seed=[]
    for _,r in summary.iterrows():
        seed.append({'Channel':r.Channel,'Contacts':1000.,'Response %':100*r.responded/max(1,r.contacted),'Qualification %':100*r.qualified/max(1,r.responded),'Activation %':100*r.activated/max(1,r.qualified),'Labor hours':40.,'Nonlabor cost $':500.})
    version=st.session_state.get('strategy_version',0)
    if st.button('Reset channel demo assumptions'):
        st.session_state['strategy_version']=version+1
        st.rerun()
    st.caption('Rates start from the loaded record-level funnel. Volume, labor and nonlabor costs are illustrative editable assumptions. Reset restores these starting values; review notes remain intact.')
    edited=st.data_editor(pd.DataFrame(seed,columns=['Channel','Contacts','Response %','Qualification %','Activation %','Labor hours','Nonlabor cost $']),num_rows='dynamic',hide_index=True,key=f'strategy_editor_{version}')
    a,b=st.columns(2)
    wage=a.number_input('Scenario labor cost / hour ($)',0.,10000.,35.,key=f'strategy_wage_{version}')
    capacity=b.number_input('Scenario staff hours available',0.,100000.,180.,key=f'strategy_capacity_{version}')
    try:results=model(edited)
    except ValueError as e:st.error(str(e));return
    results['Modeled cost $']=results['Labor hours']*wage+results['Nonlabor cost $']
    results['Cost / activation $']=results['Modeled cost $']/results['Modeled activations'].replace(0,float('nan'))
    st.dataframe(results[['Channel','Modeled responses','Modeled qualified','Modeled activations','Modeled cost $','Cost / activation $']].round(2),hide_index=True)
    st.caption('Undefined cost per activation means zero modeled activations. Labor is a fixed budget assumption, not inferred from response volume; revise it when screening demand changes.')
    st.write(f'Combined workload: **{results["Labor hours"].sum():,.1f}h / {capacity:,.1f}h available**. Gap: **{max(0,results["Labor hours"].sum()-capacity):,.1f}h**.')
    st.subheader('Recommended next experiment')
    lift=st.slider('Equal stage improvement to compare (percentage points)',1,30,5)
    options=[]
    for _,r in results.iterrows():
        rates=[r['Response %']/100,r['Qualification %']/100,r['Activation %']/100]
        for i,stage in enumerate(['Response','Qualification','Activation']):
            changed=rates.copy();changed[i]=min(1,changed[i]+lift/100)
            gain=r.Contacts*(math.prod(changed)-math.prod(rates))
            options.append((gain,r.Channel,stage,rates[i],changed[i],int(r.Contacts if i==0 else r['Modeled responses'] if i==1 else r['Modeled qualified'])))
    if not options:st.info('Add a channel to compare opportunities.');return
    gain,channel,stage,p0,p1,eligible=max(options,key=lambda x:x[0])
    tests={'Response':('Generic invitation','Domain-specific invitation','Responses / delivered invitations','More replies require screening time; track qualified response share and opt-outs.'),'Qualification':('Current intake','Clearer eligibility rubric and intake questions','Qualified / all respondents assigned','Do not lower the quality bar to improve this rate; independently audit qualification decisions.'),'Activation':('Current onboarding','Checklist plus one timely reminder','First task within 14 days / all qualified experts assigned','Track task quality, opt-outs and staff minutes; confirm missing events before contacting anyone.')}
    control,treatment,metric,tradeoff=tests[stage]
    st.write(f'**{channel} · {stage}: +{gain:.1f} modeled activations** for {p0:.0%} → {p1:.0%}. This is the largest sensitivity under an equal-point lift, not an observed bottleneck or a proven investment recommendation.')
    st.write('**Tradeoff:** '+tradeoff)
    if gain<=0:st.info('No positive modeled gain under these assumptions. Revisit the target or test operational effort rather than claiming conversion upside.')
    with st.expander('Define and export this experiment',expanded=True):
        hypothesis=st.text_area('Strategy hypothesis',f'{treatment} improves {stage.lower()} for {persona.lower()} through {channel}.')
        c,t=st.columns(2)
        ctrl=c.text_area('Control',control);trt=t.text_area('Treatment',treatment)
        primary=st.text_input('Primary metric and denominator',metric)
        secondary=st.text_input('Secondary metric','Cost per activated expert; operator minutes per participant')
        guardrail=st.text_area('Quality guardrails',tradeoff)
        duration=st.number_input('Enrollment duration (days)',1,365,14)
        followup=st.number_input('Outcome follow-up per participant (days)',1,365,14)
        available=st.number_input('Available eligible participants (total)',0,1000000,eligible)
        constraints=st.text_area('Operational constraints','Confirm consent/contact permissions, event completeness, staffing, and qualification rubric before enrollment.')
        decision=st.text_area('Decision rule for scale / continue / stop','Scale only if a prespecified worthwhile lift is supported and quality guardrails hold; continue if evidence is inconclusive and recruitment is feasible; stop if quality or opt-out limits are breached.')
        n=sample_size_per_arm(p0,p1)
        st.info((f'Approximate requirement: {n} per arm ({2*n} total); available: {available}. '+('Underpowered for the assumed lift; treat as a feasibility pilot.' if available<2*n else 'Enough nominal sample under these assumptions; validate the baseline and design before enrollment.')) if n else 'No valid normal-approximation power estimate at this boundary. Use a suitable exact or simulation-based design before a confirmatory test.')
        st.caption('80% power, two-sided 5% alpha, equal allocation; excludes attrition and multiple comparisons. Modeled rates do not establish statistical significance. Randomize eligible participants, preserve assignment, and follow the last enrollee for the full outcome window.')
        payload={'label':'Illustrative scenario, not measured impact','category':category,'qualification':qualification,'assumptions':edited.to_dict('records'),'hourly_cost':wage,'capacity_hours':capacity,'recommended_channel':channel,'stage':stage,'assumed_baseline':p0,'assumed_target':p1,'modeled_added_activations':gain,'hypothesis':hypothesis,'control':ctrl,'treatment':trt,'primary_metric':primary,'secondary_metric':secondary,'guardrails':guardrail,'enrollment_days':duration,'followup_days':followup,'available_sample':available,'required_per_arm_approx':n,'constraints':constraints,'decision_rule':decision,'limitations':'Invented or unverified inputs; mathematical sensitivity is not causality. Costs exclude expert compensation unless added. No automated outreach.'}
        st.download_button('Export current strategy and experiment',json.dumps(payload,indent=2,allow_nan=False),'strategy_experiment.json','application/json')
    decision_ui(results,wage,category,f'{channel}: test {trt} against {ctrl}. Metric: {primary}. Modeled upside: +{gain:.1f} activations; validate quality and staffing before scaling.',payload)
    with st.expander('Compare an aggregate CSV export'):
        st.caption('Separate channel-level comparison only. Aggregates cannot identify stalled people or power the record-level queue. Counts must share a cohort and observation window.')
        sample=pd.DataFrame([{'channel':'Example channel','contacts':1000,'responses':350,'qualified':200,'activated':100,'cost':5000}])
        st.download_button('Download aggregate CSV template',sample.to_csv(index=False),'aggregate_template.csv','text/csv')
        upload=st.file_uploader('Upload aggregate channel metrics',type='csv',key='strategy_aggregate')
        if upload:
            try:
                d=aggregate_validate(pd.read_csv(upload))
                for name,num,den in [('Response','responses','contacts'),('Qualification','qualified','responses'),('Activation','activated','qualified')]:
                    d[name]=d.apply(lambda r:f'{r[num]/r[den]:.0%} · {int(r[num])}/{int(r[den])}' if r[den] else 'Not estimable · 0/0',axis=1)
                d['Cost / activation']=d.cost/d.activated.replace(0,float('nan'))
                st.dataframe(d,hide_index=True)
                st.caption('Uploaded counts are unverified; missing ratios stay undefined. Compare with the modeled table above only when cohorts, costs and definitions align.')
            except Exception as e:st.error('Could not use the aggregate CSV: '+str(e))
