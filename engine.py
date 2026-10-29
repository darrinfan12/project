"""Deterministic pipeline validation and planning. No external services."""
from datetime import date, timedelta
import math
import random
from statistics import NormalDist
import pandas as pd

STAGES = ['contacted', 'responded', 'qualified', 'activated']
DATES = [s + '_at' for s in STAGES]
COLUMNS = ['record_id', 'channel'] + DATES

SAMPLE_DATE = date(2026, 10, 28)
CHANNEL_COLORS = {'Professional communities':'#5970dc','University partnerships':'#008476','Direct outreach':'#b47516','LinkedIn sourcing':'#2878b8','Conferences':'#a05aa1','Referrals':'#577d35'}

def demo_data():
    rng=random.Random(4927)
    rows=[]
    profiles=[('Professional communities',400,.34,.62,.43,1.8),('University partnerships',300,.46,.54,.68,1.1),('Direct outreach',350,.28,.70,.60,2.5),('LinkedIn sourcing',280,.38,.49,.56,3.2),('Conferences',250,.42,.65,.57,8.0),('Referrals',220,.59,.77,.74,1.4)]
    start=date(2026,7,6)
    for channel,n,response,qualification,activation,contact_cost in profiles:
        weekly=[rng.gauss(0,.055) for _ in range(17)]
        for _ in range(n):
            offset=rng.randrange(113);contact=start+timedelta(days=offset)
            week=offset//7
            dates=[contact,None,None,None]
            for stage,base in enumerate([response,qualification,activation],1):
                prior=dates[stage-1]
                if prior is None: break
                chance=max(.05,min(.95,base+weekly[week]+rng.gauss(0,.045)))
                if rng.random()>chance: break
                delay=max(1,int(rng.expovariate(1/[3.4,4.8,10.5][stage-1])))
                event=prior+timedelta(days=delay)
                if event>SAMPLE_DATE: break
                dates[stage]=event
            cost=contact_cost*rng.uniform(.7,1.5)+2/60*35
            if dates[1]:cost+=rng.uniform(5,12)/60*35
            if dates[2]:cost+=rng.uniform(12,30)/60*35
            if dates[3]:cost+=rng.uniform(5,16)/60*35
            rows.append({'record_id':f'DEMO-{len(rows)+1:04d}','channel':channel,**{field:value.isoformat() if value else '' for field,value in zip(DATES,dates)},'acquisition_cost_usd':round(cost,2)})
    # Deliberate input errors, separate from random cohort behavior.
    rows.append(dict(rows[0]))
    rows.append({'record_id':'DEMO-BAD-1','channel':'',**dict(zip(DATES,['2026-09-01','','',''])),'acquisition_cost_usd':3})
    rows.append({'record_id':'DEMO-BAD-2','channel':'Direct outreach',**dict(zip(DATES,['2026-09-10','2026-09-09','',''])),'acquisition_cost_usd':5})
    return pd.DataFrame(rows)

def validate(raw, as_of):
    missing = set(COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
    df = raw[COLUMNS + (['acquisition_cost_usd'] if 'acquisition_cost_usd' in raw.columns else [])].copy().fillna('').astype(str)
    df=df.reset_index(drop=True)
    for c in COLUMNS:
        df[c] = df[c].str.strip()
    parsed = {c: pd.to_datetime(df[c], errors='coerce', format='%Y-%m-%d') for c in DATES}
    issues, good = [], []
    # All instances of a duplicated ID are held for review; don't choose a winner silently.
    duplicates = df.record_id.duplicated(keep=False) & df.record_id.ne('')
    for ix in range(len(df)):
        row = df.iloc[ix]
        reasons = []
        if 'acquisition_cost_usd' in df and row.acquisition_cost_usd:
            try:
                cost=float(row.acquisition_cost_usd)
                if not math.isfinite(cost) or cost<0: reasons.append('Cost must be a nonnegative finite number')
            except ValueError: reasons.append('Invalid acquisition cost')
        if not row.record_id: reasons.append('Missing record ID')
        if not row.channel: reasons.append('Missing channel')
        if duplicates.iloc[ix]: reasons.append('Duplicate ID: reconcile all copies')
        if not row.contacted_at: reasons.append('Missing contact date')
        for j, c in enumerate(DATES):
            value = parsed[c].iloc[ix]
            if row[c] and pd.isna(value): reasons.append('Invalid date: ' + c)
            if not pd.isna(value) and value.date() > as_of: reasons.append('Future date: ' + c)
            if j and row[c]:
                prev = parsed[DATES[j-1]].iloc[ix]
                if pd.isna(prev): reasons.append('Missing prior stage for ' + c)
                elif not pd.isna(value) and value < prev: reasons.append('Out-of-order date: ' + c)
        if reasons:
            issues.append({'csv_row': ix + 2, 'record_id': row.record_id, 'issue': '; '.join(reasons)})
        else: good.append(ix)
    clean = df.iloc[good].copy()
    for c in DATES: clean[c] = parsed[c].iloc[good]
    clean['acquisition_cost_usd']=pd.to_numeric(clean['acquisition_cost_usd'],errors='coerce') if 'acquisition_cost_usd' in clean else float('nan')
    return clean, pd.DataFrame(issues, columns=['csv_row', 'record_id', 'issue'])

def channel_summary(clean):
    rows = []
    for channel, group in clean.groupby('channel'):
        counts = [int(group[c].notna().sum()) for c in DATES]
        row = {'Channel': channel, **dict(zip(STAGES, counts))}
        for label, num, den in [('Response rate', counts[1], counts[0]), ('Qualification rate', counts[2], counts[1]), ('Activation rate', counts[3], counts[2])]:
            row[label] = num / den if den else None
        rows.append(row)
    return pd.DataFrame(rows)

def action_queue(clean, as_of, threshold):
    actions = []
    for _, row in clean.iterrows():
        if pd.notna(row.activated_at): continue
        current = max(i for i, c in enumerate(DATES) if pd.notna(row[c]))
        age = (as_of - row[DATES[current]].date()).days
        if age < threshold: continue
        actions.append({'record_id': row.record_id, 'channel': row.channel,
            'stage': STAGES[current], 'days_waiting': age,
            'next_action': ['Review outreach history; consider one follow-up', 'Review response and record qualification decision', 'Check onboarding status and offer assistance'][current],
            'reason': f'No next-stage event after {age} days; review threshold is {threshold} days'})
    return pd.DataFrame(actions, columns=['record_id', 'channel', 'stage', 'days_waiting', 'next_action', 'reason']).sort_values('days_waiting', ascending=False)

def plan(target, rates, minutes, hourly, per_contact):
    conversion = math.prod(rates)
    if target > 0 and conversion <= 0: return None
    contacts = math.ceil(target / conversion) if target else 0
    counts = [float(contacts)]
    for rate in rates: counts.append(counts[-1] * rate)
    hours = sum(count * effort for count, effort in zip(counts, minutes)) / 60
    cost = hours * hourly + contacts * per_contact
    return {'Contacts': contacts, 'Expected activations': counts[-1], 'Hours': hours, 'Cost': cost}


def observed_rates(clean):
    counts=[int(clean[c].notna().sum()) for c in DATES]
    return [counts[i+1]/counts[i] if counts[i] else 0.0 for i in range(3)]

def channel_metrics(clean):
    summary=channel_summary(clean)
    if summary.empty: return summary
    for i,row in summary.iterrows():
        group=clean[clean.channel==row.Channel]
        days=(group.activated_at-group.contacted_at).dt.days.dropna()
        summary.loc[i,'Median days to activation']=days.median() if len(days) else float('nan')
        summary.loc[i,'Cost per activation']=group.acquisition_cost_usd.sum()/row.activated if row.activated and group.acquisition_cost_usd.notna().all() else float('nan')
    return summary

def prize_table(clean,targets=(.45,.70,.65)):
    rows=[]
    for _,r in channel_summary(clean).iterrows():
        n=[r.contacted,r.responded,r.qualified,r.activated]
        rates=[n[i+1]/n[i] if n[i] else 0 for i in range(3)]
        for stage in range(3):
            adjusted=rates.copy();adjusted[stage]=max(rates[stage],targets[stage])
            gain=n[0]*math.prod(adjusted)-n[3]
            if gain>1e-9:
                rows.append({'Channel':r.Channel,'Lever':['Response','Qualification','Activation'][stage],'Baseline':rates[stage],'Target':adjusted[stage],'Denominator':int(n[stage]),'Illustrative added activations':gain})
    return pd.DataFrame(rows,columns=['Channel','Lever','Baseline','Target','Denominator','Illustrative added activations']).sort_values('Illustrative added activations',ascending=False)

def sample_size_per_arm(p1,p2,alpha=.05,power=.8):
    if not 0<p1<1 or not 0<p2<1 or p1==p2: return None
    z=NormalDist().inv_cdf(1-alpha/2);zb=NormalDist().inv_cdf(power);avg=(p1+p2)/2
    return math.ceil(((z*math.sqrt(2*avg*(1-avg))+zb*math.sqrt(p1*(1-p1)+p2*(1-p2)))**2)/(p2-p1)**2)
