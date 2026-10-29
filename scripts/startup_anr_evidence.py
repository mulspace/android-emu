"""Retain only owned-emulator startup ANR evidence; never root or replay input."""
from datetime import datetime
import json
import re

PACKAGE = 'com.guotai.dazhihui'
EVENT = re.compile(r'(?P<date>\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}\.\d{3}).*?\bam_anr\s*:\s*\[(?P<user>\d+),(?P<pid>\d+),(?P<package>[^,]+),(?P<flags>[^,]*),(?P<reason>.*)\]$')
HEADER = re.compile(r'^----- pid (?P<pid>\d+) at (?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:.*?) -----$', re.M)
THREAD = re.compile(r'^"[^"\n]+"[^\n]*$', re.M)


def parse_event(line, year):
    match = EVENT.search(line)
    if not match or match['package'] != PACKAGE:
        raise ValueError('Expected the exact public Junhong main-process ANR')
    moment = datetime.strptime(str(year)+'-'+match['date']+' '+match['time'], '%Y-%m-%d %H:%M:%S.%f')
    return {'pid': int(match['pid']), 'package': match['package'], 'time': moment.isoformat()}


def match_main_trace(text, event):
    """No name-only thread match, PID-only stale match or implicit last-block pick."""
    wanted = datetime.fromisoformat(event['time'])
    headers = list(HEADER.finditer(text))
    matches = []
    reasons = set()
    for index, header in enumerate(headers):
        if int(header['pid']) != event['pid']:
            continue
        stamp = datetime.strptime(header['time'], '%Y-%m-%d %H:%M:%S')
        age = (stamp-wanted).total_seconds()
        # Android ANR gathering can take time, but yesterday's/reused PID cannot pass.
        if not -2 <= age <= 120:
            reasons.add('trace_timestamp_outside_event_window'); continue
        block = text[header.end():headers[index+1].start() if index+1 < len(headers) else len(text)]
        if not re.search(r'^Cmd line: '+re.escape(event['package'])+r'$', block, re.M):
            reasons.add('process_name_mismatch'); continue
        if not re.search(r'^----- end '+str(event['pid'])+r' -----$', block, re.M):
            reasons.add('incomplete_process_block'); continue
        starts = list(THREAD.finditer(block))
        mains = []
        for n, entry in enumerate(starts):
            chunk = block[entry.start():starts[n+1].start() if n+1<len(starts) else len(block)]
            if re.search(r'\bsysTid='+str(event['pid'])+r'\b', chunk):
                mains.append(chunk)
        if len(mains) != 1:
            reasons.add('main_tid_missing_or_ambiguous'); continue
        chunk=mains[0]
        sched = re.search(r'schedstat=\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)',chunk)
        state = re.search(r'\| state=([A-Z])\b',chunk)
        frames = re.findall(r'^\s+at ([A-Za-z0-9_.$<>!-]+)\(',chunk,re.M)
        matches.append({'pid':event['pid'],'trace_time':stamp.isoformat(),
            'event_delta_seconds':age,'main_tid':event['pid'],
            'state':state[1] if state else None,
            'cpu_seconds':int(sched[1])/1e9 if sched else None,
            'runnable_wait_seconds':int(sched[2])/1e9 if sched else None,
            'java_methods':frames[:40]})
    return {'matched':len(matches)==1, 'matches':matches if len(matches)==1 else [],
        'reason':None if len(matches)==1 else 'ambiguous_matching_blocks' if len(matches)>1
            else ','.join(sorted(reasons)) or 'exact_process_block_missing'}


def collect(call, output, events, year):
    """call remains the prewarm helper's owned-AVD, original-deadline transport."""
    parsed=[]
    for line in sorted(events):
        try: parsed.append(parse_event(line,year))
        except ValueError: pass
    result={'root_requested':False,'account_access':False,'events':parsed,'reads':{}}
    text=None
    for name,args in (
        ('anr-traces',['shell','cat','/data/anr/traces.txt']),
        ('anr-processes',['shell','ps']),
        ('anr-events',['logcat','-b','events','-d','-s','am_anr:I','am_crash:I','*:S'])):
        try:
            value=call(args)
            (output/(name+'.txt')).write_text(value)
            result['reads'][name]={'ok':True,'bytes':len(value.encode())}
            if name=='anr-traces':text=value
        except Exception as error:
            result['reads'][name]={'ok':False,'error_type':type(error).__name__}
    result['analysis']=[{'event':event,**match_main_trace(text,event)} for event in parsed] if text is not None else []
    (output/'anr-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
