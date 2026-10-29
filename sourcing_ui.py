from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from outreach import discover, valid_email, message_bytes
import streamlit.components.v1 as components
from views import clipboard_html
from html import escape

def discovery_ui():
    st.write('Crossref finds publication authors, not a directory of practicing accountants, compliance officers, or engineers. Use this to find research leads; verify practitioner experience separately.')
    st.caption('Best for research-oriented expertise. It will not cover every industry practitioner, verify availability, or find contact email addresses. Your topic query is sent to Crossref only when you search.')
    with st.form('public_search'):
        topic=st.text_input('What expertise are you looking for?',value='civil engineering structural inspection',max_chars=200)
        submitted=st.form_submit_button('Search public publications')
    if submitted:
        try:
            with st.spinner('Searching publication metadata…'): found=discover(topic)
            st.session_state['public_results']=found
            st.session_state['search_status']='results' if found else 'empty'
            st.session_state['searched_topic']=topic
            st.session_state['searched_at']=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        except Exception:
            st.session_state['public_results']=[]
            st.session_state['search_status']='error'
            st.error('Search could not complete. Check your connection and try again. No sample results were substituted.')
    results=st.session_state.get('public_results',[])
    if not results:
        st.info('No author records matched. Try a broader term such as civil engineering or compliance.' if st.session_state.get('search_status')=='empty' else 'Enter a domain and search to see public source evidence.' if st.session_state.get('search_status')!='error' else 'Your shortlist is unchanged. Retry the search when the service is available.')
    else:
        st.caption(f"{len(results)} author-publication records · {st.session_state.get('searched_topic','')} · retrieved {st.session_state.get('searched_at','')}. The same author may appear on multiple publications.")
        table=pd.DataFrame(results)
        st.dataframe(table[['name','affiliation','publication','year','source_url']].rename(columns={'name':'Author','affiliation':'Reported affiliation','publication':'Publication','year':'Year','source_url':'Evidence'}),column_config={'Evidence':st.column_config.LinkColumn('Evidence')},hide_index=True,width='stretch')
        chosen=st.selectbox('Inspect a research lead',range(len(results)),format_func=lambda i:f"{results[i]['name']} — {results[i]['publication'][:80]}")
        lead=results[chosen]
        st.write('**Publication evidence:** '+lead['publication'])
        st.link_button('Open source publication',lead['source_url'])
        st.caption('Confirm identity, current role, relevant experience, and a legitimate contact route before reaching out. Publication authorship alone does not establish project fit.')
        if st.button('Add to research shortlist'):
            shortlist=st.session_state.setdefault('shortlist',{})
            shortlist[lead['evidence_id']]=lead
            st.success('Added to your session shortlist. Available in Outreach workspace below.')
        st.download_button('Export search results',table.to_csv(index=False),'public_research_leads.csv','text/csv')
    shortlist=st.session_state.setdefault('shortlist',{})
    if shortlist:
        st.caption(f'{len(shortlist)} evidence records in your session shortlist.')
        st.download_button('Export research shortlist',pd.DataFrame(shortlist.values()).to_csv(index=False),'research_shortlist.csv','text/csv')
    st.markdown('[Source and API documentation: Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)')


def outreach_ui(context=None):
    context=context or {}
    kind=st.radio('Draft for',['Selected pipeline record','Research shortlist','Manual contact'],horizontal=True)
    lead=None
    if kind=='Research shortlist':
        shortlist=st.session_state.get('shortlist',{})
        if not shortlist:
            st.info('Add a research lead above, or choose a pipeline record.');return
        key=st.selectbox('Choose research evidence',list(shortlist),format_func=lambda k:shortlist[k]['name'])
        lead=shortlist[key]
    rid=context.get('record_id','Expert')
    default_name=lead['name'] if lead else rid if kind=='Selected pipeline record' else 'Recipient'
    a,b=st.columns(2)
    name=a.text_input('Recipient name',value=default_name,key='draft_name_'+kind+default_name)
    sender=b.text_input('Your name',value='Darrin Fan')
    if kind=='Selected pipeline record':
        default_subject='Can I help with the next onboarding step?'
        default_body=f'Hi {name},\n\nI am checking in on your onboarding. Is there anything in the next steps that needs clarification, or would a different time work better?\n\nBest,\n{sender}'
        if context.get('dummy',True):default_body+='\n\nIllustrative draft for a fictional record. Not a real campaign.'
    else:
        default_subject='Question about your domain expertise'
        evidence=f'I came across your publication, "{lead["publication"]}" ({lead["source_url"]}).\n\n' if lead else ''
        default_body=f'Hi {name},\n\n{evidence}Would you be open to a short conversation about your experience and whether a future expert project might be relevant? If not, let me know and I will not follow up.\n\nBest,\n{sender}'
    token=kind+default_name+name+sender
    edit,preview=st.columns(2,gap='medium')
    with edit:
        subject=st.text_input('Subject',default_subject,key='draft_subject_'+token)
        body=st.text_area('Edit draft',default_body,height=260,key='draft_body_'+token)
    with preview:
        st.markdown('<div class="draft-preview"><div class="eyebrow">LIVE PREVIEW</div><b>'+escape(subject)+'</b><p>'+escape(body).replace('\n','<br>')+'</p></div>',unsafe_allow_html=True)
    components.html(clipboard_html(subject+'\n\n'+body),height=48)
    st.download_button('Export draft as text',subject+'\n\n'+body,'outreach_draft.txt','text/plain')
    st.caption('Export only. No email credentials, send button, or delivery integration. Review facts and contact permissions in your normal workflow.')
