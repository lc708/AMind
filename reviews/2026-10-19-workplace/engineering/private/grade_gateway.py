#!/usr/bin/env python3
import copy,html,json
from grade_common import run,require

def msg(text,agent='/root',phase='final_answer'):
    item={'type':'message','content':[{'type':'output_text','text':text}]}
    if agent is not None:item['agent']={'agent_name':agent}
    if phase is not None:item['phase']=phase
    return item

def cap(items,events=None,mode='multi_agent',status='completed',**extra):
    response={'status':status,'output':items,**extra}
    return {'mode':mode,'events':(events or [])+[{'type':'response.'+status,'response':response}]}
def legacy(s):
    r=s.call(cap([msg('Ready',None,None)],mode='single'));require(r['client']['answer_complete'] and r['client']['final_text']=='Ready','legacy final lost')
def root_final(s):
    items=[msg('internal-920','/root/research'),msg('Customer decision')];r=s.call(cap(items));c=r['client']
    require(c['final_text']=='Customer decision' and 'internal-920' not in json.dumps(c),'child final leaked');require(c['answer_complete'],'root final lost')
def child_only(s):
    c=s.call(cap([msg('private-411','/root/planner')]))['client'];require(not c['answer_complete'] and c['final_text']=='' and 'private-411' not in json.dumps(c),'child-only answer accepted')
def unattributed(s):
    c=s.call(cap([msg('owner unknown',None)]))['client'];require(c['final_text']=='' and not c['answer_complete'],'unattributed multi-agent final projected')
def indexed_stream(s):
    items=[msg('worker-note','/root/worker'),msg('Visible progress','/root','commentary')]
    events=[]
    for i,item in enumerate(items):events.extend([{'type':'response.output_item.added','output_index':i,'item':item},{'type':'response.output_text.delta','output_index':i,'delta':item['content'][0]['text']}])
    c=s.call(cap(items,events))['client'];require(c['display_text']=='Visible progress' and not c['answer_complete'],'indexed deltas lost ownership')
def same_event_conflict(s):
    events=[{'type':'response.output_item.added','output_index':4,'agent':{'agent_name':'/root'},'item':msg('private','/root/worker')},{'type':'response.output_text.delta','output_index':4,'delta':'private'}]
    s.call({'mode':'multi_agent','events':events},2)
def terminal_conflict(s):
    events=[{'type':'response.output_item.added','output_index':0,'item':msg('draft','/root')}]
    s.call(cap([msg('draft','/root/child')],events),2)
def disconnected(s):
    r=s.call({'mode':'single','events':[{'type':'response.output_text.delta','delta':'Partial'}]});c=r['client'];require(c['status']=='disconnected' and not c['answer_complete'] and c['display_text']=='Partial','disconnect accepted as complete')
def incomplete(s):
    c=s.call(cap([msg('cut off')],status='incomplete',incomplete_details={'reason':'token_limit'}))['client'];require(c['status']=='incomplete' and not c['answer_complete'],'incomplete response accepted')
def contradiction(s):
    s.call(cap([msg('fine')],error={'code':'runtime_failure'}),2)
    bad=cap([msg('fine')]);bad['events'][-1]['response']['status']='incomplete';s.call(bad,2)
def after_terminal(s):
    c=cap([msg('done')]);c['events'].append({'type':'response.output_text.delta','agent':{'agent_name':'/root'},'delta':'later'});s.call(c,2)
def opaque_archive(s):
    opaque=[{'type':'agent_message','encrypted_content':'opaque-never-browser'},{'type':'future_hosted_v9','payload':{'raw':[0,False,{'byte':'保留'}]}}];items=[msg('done')]+opaque;c=cap(items);r=s.call(c)
    require(r['archive']['events']==c['events'] and r['archive']['output_items']==items,'opaque archive item lost');require('opaque-never-browser' not in json.dumps(r['client']),'opaque item projected into client')
def safe_render(s):
    text='<img src=x onerror="steal()"> & private <script>alert(1)</script>';c=s.call(cap([msg(text)]))['client'];require(c['final_text']==text and c['html']=='<article>'+html.escape(text,quote=True)+'</article>','HTML presentation is unsafe or changes text')
def final_readiness(s):
    c=s.call(cap([msg('Result'),{'type':'function_call','name':'write','call_id':'c1','arguments':'{}'}]))['client'];require(not c['answer_complete'],'pending function accepted as final')
    c=s.call(cap([msg('Still checking','/root','commentary')]))['client'];require(c['final_text']=='' and not c['answer_complete'],'commentary accepted as final')
PROBES=[('G01','completion',False,legacy),('G02','ownership',True,root_final),('G03','ownership',True,child_only),('G04','ownership',False,unattributed),('G05','attribution',True,indexed_stream),('G06','attribution',True,same_event_conflict),('G07','attribution',True,terminal_conflict),('G08','terminal',False,disconnected),('G09','terminal',False,incomplete),('G10','terminal',True,contradiction),('G11','terminal',False,after_terminal),('G12','archive',True,opaque_archive),('G13','rendering',True,safe_render),('G14','completion',False,final_readiness)]
if __name__=='__main__':run('E-GATEWAY','gateway',PROBES)
