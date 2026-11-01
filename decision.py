"""Decision support with explicit linear and scenario assumptions."""
import io
from html import escape
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from scipy.optimize import milp, Bounds, LinearConstraint
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def allocate(r,limits,budget,hours):
    n=len(r)
    if not n:return None
    volume=r.Contacts.to_numpy(float)
    unit_cost=np.divide(r['Modeled cost $'],volume,out=np.zeros(n),where=volume>0)
    unit_hours=np.divide(r['Labor hours'],volume,out=np.zeros(n),where=volume>0)
    yield_=np.divide(r['Modeled activations'],volume,out=np.zeros(n),where=volume>0)
    cap=np.where(volume>0,np.array(limits,float),0)
    answer=milp(-yield_,integrality=np.ones(n),bounds=Bounds(np.zeros(n),cap),constraints=LinearConstraint(np.vstack([unit_cost,unit_hours]),[-np.inf,-np.inf],[budget,hours]),options={'time_limit':5})
    if not answer.success:return None
    x=np.rint(answer.x).astype(int)
    return pd.DataFrame({'Channel':r.Channel.to_list(),'Allocated contacts':x,'Expected activations':x*yield_,'Cost $':x*unit_cost,'Hours':x*unit_hours})

def report_pdf(persona,ranking,budget,hours,allocation,recommendation,range_text,assumptions):
    buf=io.BytesIO();styles=getSampleStyleSheet();styles['Normal'].fontSize=9;styles['Normal'].leading=12
    doc=SimpleDocTemplate(buf,pagesize=(612,792),leftMargin=40,rightMargin=40,topMargin=32,bottomMargin=30)
    def p(t):return Paragraph(escape(str(t)),styles['Normal'])
    story=[Paragraph('Growth strategy | Decision brief',styles['Title']),p('Darrin Fan · Illustrative model · Not AfterQuery operating data'),Spacer(1,10),p('Target: maximize modeled first-task completions. Persona: '+persona),p(f'Allocation window: one week. Budget: ${budget:,.0f}. Staff capacity: {hours:,.1f} hours.'),Spacer(1,10)]
    rows=[[p(x) for x in ['Channel','Activations','Cost / activation','Qualified yield']]]
    for _,r in ranking.head(6).iterrows():rows.append([p(str(r.Channel)[:55]),p(f'{r["Modeled activations"]:.1f}'),p('Undefined' if pd.isna(r['Cost / activation $']) else f'${r["Cost / activation $"]:.1f}'),p(f'{r["Qualified yield"]:.1%}')])
    table=Table(rows,colWidths=[210,75,115,132]);table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2fa')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),.3,colors.lightgrey)]));story+=[table,Spacer(1,10)]
    if len(ranking)>6:story.append(p('Top six by modeled cost efficiency shown; full comparison is available in the app.'))
    if allocation is not None:
        story.append(p(f'Constrained allocation: {allocation["Allocated contacts"].sum():,} contacts; {allocation["Expected activations"].sum():.1f} expected activations; ${allocation["Cost $"].sum():,.0f}; {allocation.Hours.sum():.1f} hours.'))
        story.append(p('Contacts by channel: '+'; '.join(f'{str(r.Channel)[:45]}: {r["Allocated contacts"]}' for _,r in allocation.iterrows() if r['Allocated contacts']>0)))
    else:story.append(p('No optimal allocation available. Review inputs before using this report.'))
    for heading,text in [('Stress test',range_text),('Recommended validation experiment',recommendation),('Assumptions and limitations',assumptions),('Next actions','Validate cohort definitions and costs; audit task quality; verify channel ceilings and staff effort; pre-register the experiment and guardrails before allocating real spend.')]:
        story +=[Spacer(1,9),Paragraph(heading,styles['Heading3']),p(text)]
    doc.build(story);return buf.getvalue()

def decision_ui(results,wage,persona,recommendation):
    if results.empty:return
    r=results.copy();r['Qualified yield']=r['Modeled qualified']/r.Contacts.replace(0,float('nan'))
    st.subheader('Efficiency versus scale')
    rank=r.sort_values('Cost / activation $',na_position='last')
    metric=st.selectbox('Rank channels by',['Cost / activation $','Qualified yield','Modeled activations'])
    chart=r.dropna(subset=[metric])
    st.altair_chart(alt.Chart(chart).mark_bar().encode(x=alt.X(metric+':Q',title=metric,axis=alt.Axis(format='.0%' if metric=='Qualified yield' else ',.1f')),y=alt.Y('Channel:N',sort='x' if metric=='Cost / activation $' else '-x'),tooltip=['Channel',alt.Tooltip(metric+':Q',format='.1%' if metric=='Qualified yield' else ',.1f')]).properties(height=220),use_container_width=True)
    st.altair_chart(alt.Chart(r.dropna(subset=['Cost / activation $'])).mark_circle(size=140).encode(x=alt.X('Cost / activation $:Q',title='Cost per activation ($; lower is better)'),y=alt.Y('Modeled activations:Q',title='Activation volume (higher is better)'),color='Channel:N',tooltip=['Channel','Modeled activations','Cost / activation $']).properties(height=230),use_container_width=True)
    valid=rank.dropna(subset=['Cost / activation $'])
    if not valid.empty:
        efficient=valid.iloc[0];scale=r.loc[r['Modeled activations'].idxmax()]
        st.write(f'**Efficiency leader: {efficient.Channel}** (${efficient["Cost / activation $"]:.1f}/activation). **Volume leader: {scale.Channel}** ({scale["Modeled activations"]:.1f} activations). Compare quality and channel capacity before shifting resources; volume depends on entered outreach.')
    cost_median=r['Cost / activation $'].median();yield_median=(r['Modeled activations']/r.Contacts.replace(0,float('nan'))).median()
    flags=[]
    for _,row in r.iterrows():
        if row['Cost / activation $']>cost_median:flags.append(f'{row.Channel}: above scenario median cost per activation.')
        if row.Contacts and row['Modeled activations']/row.Contacts<yield_median:flags.append(f'{row.Channel}: below scenario median end-to-end conversion.')
    with st.expander('Relative diagnostic flags'):
        st.write('\n\n'.join(flags) or 'No channels flagged against this scenario median.')
        st.caption('Relative comparisons within your inputs, not external benchmarks or evidence of a real bottleneck.')
    st.subheader('Stress-test each channel')
    st.caption('Edit percentage-point changes relative to each channel’s base rates. Rates are clipped to 0–100%. These are sensitivity cases, not probabilities or confidence intervals. Cost and volume remain fixed.')
    assumptions=st.data_editor(pd.DataFrame([{'Case':'Conservative','Response Δpp':-5.,'Qualification Δpp':-5.,'Activation Δpp':-5.},{'Case':'Base','Response Δpp':0.,'Qualification Δpp':0.,'Activation Δpp':0.},{'Case':'Optimistic','Response Δpp':5.,'Qualification Δpp':5.,'Activation Δpp':5.}]),hide_index=True,disabled=['Case'],key='decision_sensitivity')
    deltas=assumptions[['Response Δpp','Qualification Δpp','Activation Δpp']].to_numpy(float)
    if not np.isfinite(deltas).all():st.error('Sensitivity inputs must be finite numbers.');return
    rows=[]
    for _,case in assumptions.iterrows():
        for _,row in r.iterrows():
            rates=[np.clip((row[k]+case[d])/100,0,1) for k,d in zip(['Response %','Qualification %','Activation %'],['Response Δpp','Qualification Δpp','Activation Δpp'])]
            output=row.Contacts*np.prod(rates)
            rows.append({'Channel':row.Channel,'Case':case.Case,'Expected activations':output,'Cost / activation':row['Modeled cost $']/output if output else np.nan})
    stress=pd.DataFrame(rows)
    st.altair_chart(alt.Chart(stress).mark_bar().encode(x=alt.X('Expected activations:Q',title='Expected activations (modeled)'),y='Channel:N',yOffset=alt.YOffset('Case:N',sort=['Conservative','Base','Optimistic']),color='Case:N',tooltip=['Channel','Case','Expected activations','Cost / activation']).properties(height=380),use_container_width=True)
    winners={}
    for case,g in stress.groupby('Case'):
        finite=g.dropna(subset=['Cost / activation']);winners[case]=finite.loc[finite['Cost / activation'].idxmin()].Channel if not finite.empty else 'None (zero activations)'
    range_text='Cost-efficiency leader by case: '+'; '.join(f'{k}: {v}' for k,v in winners.items())+'. Rankings assume comparable quality and unchanged costs.'
    st.write(range_text)
    st.subheader('Allocate a weekly budget')
    st.caption('Integer optimization maximizes expected first-task completions within budget, hours and channel ceilings. Costs and labor scale linearly per contact from your strategy inputs; no fixed costs, diminishing returns, or guaranteed outcomes. Zero-volume channels cannot be allocated until unit economics are defined.')
    a,b=st.columns(2);budget=a.number_input('Weekly acquisition budget ($)',0.,10000000.,5000.);hours=b.number_input('Weekly recruiter capacity (hours)',0.,100000.,40.)
    caps=st.data_editor(pd.DataFrame({'Channel':r.Channel,'Maximum weekly contacts':r.Contacts.astype(int)}),disabled=['Channel'],hide_index=True,key='decision_caps')
    limits=pd.to_numeric(caps['Maximum weekly contacts'],errors='coerce').to_numpy(float)
    if not np.isfinite(limits).all() or (limits<0).any() or (limits%1!=0).any():st.error('Channel ceilings must be nonnegative whole numbers.');return
    allocation=allocate(r,limits,budget,hours)
    if allocation is None:st.warning('The optimizer did not produce a verified optimum. Revise constraints; no recommendation is shown.')
    else:
        st.dataframe(allocation.round(2),hide_index=True)
        st.write(f'**{allocation["Expected activations"].sum():.1f} modeled activations** · ${allocation["Cost $"].sum():,.0f} / ${budget:,.0f} · {allocation.Hours.sum():.1f} / {hours:.1f} hours.')
    st.subheader('Quality and continuing contribution')
    st.caption('Separate editable assumptions, not observed outcomes. Activated already means first task completed. Accepted tasks = activations × [1 + retention × additional tasks per retained expert] × task acceptance. Retention refers to participation in the next 30 days.')
    q=st.data_editor(pd.DataFrame({'Channel':r.Channel,'Task acceptance %':80.,'30-day retention %':60.,'Additional tasks / retained expert':3.}),disabled=['Channel'],hide_index=True,key='decision_quality')
    nums=q.iloc[:,1:].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    if not np.isfinite(nums).all() or (nums<0).any() or (nums[:,:2]>100).any():st.error('Use rates from 0–100 and nonnegative finite task counts.');return
    quality=pd.DataFrame({'Channel':r.Channel,'Modeled accepted tasks':r['Modeled activations'].to_numpy()*(1+nums[:,1]/100*nums[:,2])*nums[:,0]/100})
    quality['Acquisition cost / accepted task $']=r['Modeled cost $'].to_numpy()/quality['Modeled accepted tasks'].replace(0,np.nan)
    st.dataframe(quality.round(2),hide_index=True)
    st.caption('Acquisition spend only: excludes expert task pay and delivery/review costs. These quality outputs use the entered channel plan, not the optimizer allocation.')
    st.subheader('Executive decision report')
    limitations='All outcomes are illustrative. Linear unit economics; integer contacts; no causal evidence, confidence intervals or quality equivalence. Channel rates come from the selected dataset; effort, costs and lifts are assumptions. Validate ceilings, cohort maturity, response quality and full delivery costs.'
    pdf=report_pdf(persona,rank,budget,hours,allocation,recommendation,range_text,limitations)
    st.download_button('Download executive strategy report (PDF)',pdf,'growth_strategy_report.pdf','application/pdf')
    st.download_button('Export sensitivity results',stress.to_csv(index=False),'channel_sensitivity.csv','text/csv')
    st.caption('PDF is a concise decision brief; the strategy JSON export preserves detailed experiment fields and base assumptions.')
