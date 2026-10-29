"""Local daily batch: CSV in, newly-stalled digest out. No Slack/email transport."""
import argparse,json
from datetime import date
from pathlib import Path
import pandas as pd
from engine import validate,action_queue

def build_digest(raw,as_of,threshold,previous):
    clean,issues=validate(raw,as_of)
    actions=action_queue(clean,as_of,threshold)
    stalled=actions[actions.stage=='qualified']
    old=set(previous.get('qualified_stalled_ids',[]))
    newly=stalled[~stalled.record_id.isin(old)]
    lines=[f'# Qualified expert review — {as_of}',f'{len(newly)} newly stalled records at the {threshold}-day threshold.',f'{len(issues)} input rows held for correction.','']
    for _,r in newly.iterrows():
        lines.append(f'- {r.record_id}: {r.channel}; {r.days_waiting} days waiting. Review onboarding history.')
    if newly.empty:lines.append('No newly stalled records since the previous run.')
    return '\n'.join(lines)+'\n',{'as_of':str(as_of),'threshold_days':threshold,'qualified_stalled_ids':stalled.record_id.tolist()}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv');p.add_argument('--as-of',required=True,type=date.fromisoformat);p.add_argument('--threshold',type=int,choices=[7,14,30],default=14)
    p.add_argument('--previous');p.add_argument('--state-out',required=True);p.add_argument('--digest-out',required=True)
    args=p.parse_args()
    previous=json.loads(Path(args.previous).read_text()) if args.previous else {}
    raw=pd.read_csv(args.csv,dtype=str,keep_default_na=False)
    digest,state=build_digest(raw,args.as_of,args.threshold,previous)
    Path(args.digest_out).write_text(digest);Path(args.state_out).write_text(json.dumps(state,indent=2))
    print('Digest and run state written. No message was sent.')
if __name__=='__main__':main()
