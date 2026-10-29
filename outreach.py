"""Public publication discovery and export-only email drafts."""
import hashlib
import json
import re
from email.message import EmailMessage
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

RESULT_COLUMNS=['name','affiliation','publication','year','source_url','orcid','evidence_id']

def extract_authors(items):
    results=[]; seen=set()
    for work in items:
        doi=work.get('DOI','')
        if not doi: continue
        title=(work.get('title') or ['Untitled publication'])[0]
        parts=work.get('published',{}).get('date-parts', [[]])
        year=parts[0][0] if parts and parts[0] else ''
        for author in work.get('author',[])[:15]:
            name=' '.join(filter(None,[author.get('given',''),author.get('family','')])).strip()
            if not name: continue
            # Dedupe evidence rows, not identities inferred from matching names.
            key=(doi.casefold(),name.casefold())
            if key in seen: continue
            seen.add(key)
            orcid=author.get('ORCID','')
            if not re.match(r'^https?://orcid.org/[0-9X-]+$',orcid): orcid=''
            results.append(dict(name=name,affiliation='; '.join(a.get('name','') for a in author.get('affiliation',[]) if a.get('name')) or 'Not supplied',publication=title,year=str(year),source_url='https://doi.org/'+quote(doi,safe='/'),orcid=orcid,evidence_id=hashlib.sha256((doi+'|'+name).encode()).hexdigest()[:16]))
    return results[:100]

def discover(query):
    query=query.strip()
    if not 3<=len(query)<=200: raise ValueError('Use a topic between 3 and 200 characters.')
    params=urlencode({'query.bibliographic':query,'rows':12,'filter':'type:journal-article','select':'DOI,title,author,published'})
    req=Request('https://api.crossref.org/works?'+params,headers={'User-Agent':'ExpertAcquisitionPortfolio/1.0 (public research metadata)','Accept':'application/json'})
    with urlopen(req,timeout=20) as response:
        payload=json.loads(response.read(5_000_000))
    return extract_authors(payload.get('message',{}).get('items',[]))

def valid_email(value):
    return bool(re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}',value.strip())) and '\n' not in value and '\r' not in value

def message_bytes(sender, recipient, subject, body):
    if not valid_email(sender) or not valid_email(recipient): raise ValueError('Enter a valid sender and one recipient email address.')
    if not subject.strip() or any(c in subject for c in '\r\n'): raise ValueError('Subject must be one nonempty line.')
    if not body.strip(): raise ValueError('Message body is required.')
    msg=EmailMessage();msg['From']=sender.strip();msg['To']=recipient.strip();msg['Subject']=subject.strip();msg.set_content(body)
    return msg
