// Orchestration tests: fake transports exist only in this test file.
import assert from 'node:assert/strict'
import { createEsafeService, recoveryMessage } from './src/printing/esafe.js'
import { EsafeClient } from '@esafe/printer-manager'
import { validateReceiptLayout, receiptHtmlOptions } from './src/receiptLayout.js'
assert.equal(typeof new EsafeClient().printers.capabilities, 'function')
function memoryJournal() {
  const settings=new Map(),intents=new Map(),clone=(v)=>v===undefined ? undefined : structuredClone(v)
  return {setting:async(k)=>clone(settings.get(k)),saveSetting:async(k,v)=>settings.set(k,clone(v)),settings:async()=>[...settings.values()].map(clone),
    get:async(k)=>clone(intents.get(k)),put:async(v)=>intents.set(v.key,clone(v)),list:async()=>[...intents.values()].map(clone)}
}
class Client {
  isConnected=true;isPaired=true;calls=[];pairings=[];events=new Map();accepted=[];lost=false;hidden=false;revoked=false;printError=null
  printers={list:async()=>{if(this.revoked)throw Object.assign(new Error('Revoked'),{code:'PERMISSION_DENIED'});return [{id:'receipt',name:'Receipt',isDefault:true},{id:'label',name:'Label'},{id:'office',name:'Office'}]},getDefault:async()=>({id:'receipt',name:'Receipt'}),capabilities:async(id)=>({printerId:id,maxCopies:99})}
  jobs={list:async()=>this.hidden ? [] : this.accepted,get:async(id)=>this.accepted.find((j)=>j.id===id),cancel:async(id)=>({...this.accepted.find((j)=>j.id===id),state:'cancelled'}),reprint:async(id,key)=>{const job={...this.accepted.find((j)=>j.id===id),id:key,state:'queued'};this.accepted.push(job);return job}}
  async connect(){this.isConnected=true;return {paired:this.isPaired,port:17651}}
  async pair(scopes){this.pairings.push(scopes);this.isPaired=true;this.revoked=false}
  disconnect(){this.isConnected=false}
  on(name,fn){const set=this.events.get(name)||new Set();set.add(fn);this.events.set(name,set);return()=>set.delete(fn)}
  async print(request){this.calls.push(structuredClone(request));if(this.printError)throw this.printError;let job=this.accepted.find((j)=>j.key===request.idempotencyKey);if(!job){job={id:crypto.randomUUID(),key:request.idempotencyKey,printerId:request.printerId,title:request.title,format:request.format,state:'queued',certainty:'accepted',error:null};this.accepted.push(job)}if(this.lost)throw Object.assign(new Error('Lost response'),{code:'DISCONNECTED'});return job}
}
function harness(options={}){
  const journal=options.journal || memoryJournal(),client=options.client || new Client(),locks=new Map(),authorizations=[]
  const lock=(key,fn)=>{const run=(locks.get(key)||Promise.resolve()).then(fn);locks.set(key,run.catch(()=>{}));return run}
  const service=createEsafeService({journal,client,lock,device:async()=>'workstation',authorize:async(r)=>authorizations.push(structuredClone(r)),report:async()=>{},wait:async()=>{},...options})
  return {journal,client,service,authorizations,lock}
}
const request={key:'sale-1',profile:'Till',role:'receipt',format:'html',data:'<p>සිංහල தமிழ்</p>',options:{copies:1},title:'Receipt INV-1',reference:{doctype:'POS Invoice',name:'INV-1'},user:'cashier'}
async function prepare(h){await h.journal.saveSetting('approved',true);await h.journal.saveSetting('binding:Till',{profile:'Till',receipt:'receipt',labels:'label',document:'office',report:'receipt'})}
{
  const h=harness();await prepare(h)
  const rows=await Promise.all(Array.from({length:8},()=>h.service.dispatch(request)))
  assert.equal(h.client.calls.length,1);assert.equal(new Set(rows.map((r)=>r.intentId)).size,1)
  assert.equal(h.authorizations.length,1)
  const reloaded=harness({journal:h.journal,client:h.client});await reloaded.service.dispatch(request);assert.equal(h.client.calls.length,1)
  const anotherTab=harness({journal:h.journal,client:h.client});await anotherTab.service.dispatch(request);assert.equal(h.client.calls.length,1)
  const parallelTab=harness({journal:h.journal,client:h.client,lock:h.lock})
  await Promise.all([h.service.dispatch({...request,key:'parallel-tabs'}),parallelTab.service.dispatch({...request,key:'parallel-tabs'})])
  assert.equal(h.client.calls.length,2,'Two concurrent tabs share the browser Web Lock and one persisted request')
  const stored=await h.journal.get(request.key);assert.equal(stored.request,undefined);assert.ok(stored.payloadHash);assert.ok(stored.agentJobId)
  console.log('PASS rapid callbacks, reload, shared browser journal and immutable original intent')
}
{
  const h=harness();await prepare(h);h.client.lost=true
  const result=await h.service.dispatch(request)
  assert.equal(result.state,'queued','Lost acceptance should reconcile by unique title and job ID')
  assert.equal(h.client.calls.length,1)
  console.log('PASS lost acceptance reconciles without retransmission')
}
{
  const h=harness();await prepare(h);h.client.lost=true;h.client.hidden=true
  const original=await h.service.dispatch(request);assert.equal(original.state,'unknown')
  await h.service.resume();assert.equal(h.client.calls.length,1,'Resume must not replay unknown jobs')
  h.client.lost=false
  const retry=await h.service.retry(request.key)
  assert.equal(retry.agentJobId,h.client.accepted[0].id)
  assert.equal(h.client.accepted.length,1)
  assert.deepEqual(h.client.calls[0],h.client.calls[1],'Explicit transport retry must preserve every byte, option, title and key')
  console.log('PASS unknown stays manual and identical retry deduplicates native acceptance')
}
{
  const h=harness();await prepare(h)
  await h.journal.saveSetting('binding:Other',{profile:'Other',document:'office'})
  await h.service.saveBinding('Till',{receipt:'receipt',labels:'label'},async()=>{})
  assert.deepEqual(h.client.pairings[0],[{action:'printers.list',resources:['printers']},{action:'print',resources:['label','office','receipt']}])
  await h.service.saveBinding('Till',{receipt:'receipt'},async()=>{})
  assert.deepEqual(h.client.pairings[1][1].resources,['office','receipt'])
  let denied=false
  await assert.rejects(h.service.saveBinding('Till',{receipt:'receipt'},async()=>{denied=true;throw new Error('Denied')}))
  assert.ok(denied);assert.equal(h.client.pairings.length,2)
  console.log('PASS pairing replaces the complete exact-resource union, and ERP permission guards changes')
}
{
  const h=harness();await prepare(h);h.client.isConnected=false;h.client.isPaired=false;await h.journal.saveSetting('approved',false)
  await h.service.resume();assert.equal(h.client.isConnected,false)
  await h.service.connect({explicit:true});assert.equal(h.client.pairings.length,1)
  assert.equal(h.service.state.connection,'connected')
  await h.service.resume();await h.service.resume();assert.equal(h.client.events.get('job.changed').size,1)
  h.service.dispose();assert.equal(h.client.events.get('job.changed').size,0)
  console.log('PASS explicit first connection, native approval and listener cleanup')
}
{
  const h=harness();await prepare(h);await h.journal.saveSetting('binding:Till',{profile:'Till',receipt:'missing'})
  await assert.rejects(h.service.dispatch(request),/missing or renamed/);assert.equal(h.client.calls.length,0)
  const raw=harness();await prepare(raw);await raw.service.dispatch({...request,format:'raw',options:{copies:2,size:{width:80,height:100},duplex:'long-edge'}})
  assert.deepEqual(raw.client.calls[0].options,{copies:2})
  const copied=await raw.service.reprint(request.key);assert.notEqual(copied.intentId,raw.client.calls[0].idempotencyKey);assert.equal(copied.reprintOf,raw.client.calls[0].idempotencyKey)
  console.log('PASS missing queue rejection, raw copies-only options and deliberate reprint identity')
}
{
  const h=harness();await prepare(h);h.client.revoked=true
  await assert.rejects(h.service.refreshPrinters(),/Revoked/)
  assert.equal(h.service.state.connection,'approval-required');assert.equal(await h.journal.setting('approved'),false)
  await h.service.connect({explicit:true});assert.equal(h.service.state.connection,'connected');assert.equal(h.client.pairings.length,1)
  assert.match(recoveryMessage({code:'AGENT_UNAVAILABLE',message:'PROTOCOL_MISMATCH'}),/protocols differ/)
  await assert.rejects(h.service.dispatch({...request,options:{copies:0}}),/copy count/)
  await assert.rejects(h.service.dispatch({...request,options:{color:true}}),/does not support/)
  console.log('PASS revoked approval repair, incompatible protocol guidance and driver option validation')
}
{
  const delays=[],h=harness({wait:async(ms)=>delays.push(ms)});await prepare(h)
  await h.service.resume()
  let attempts=0
  h.client.isConnected=false
  h.client.connect=async()=>{attempts++;throw Object.assign(new Error('Unavailable'),{code:'AGENT_UNAVAILABLE'})}
  h.client.events.get('connection.closed').forEach((fn)=>fn())
  for(let i=0;i<40;i++)await new Promise((r)=>setTimeout(r,0))
  assert.deepEqual(delays,[1000,2500,5000]);assert.equal(attempts,3);assert.equal(h.client.calls.length,0)
  h.service.dispose()
  console.log('PASS bounded unavailable-manager reconnect without automatic print replay')
}
{
  const h=harness();await prepare(h)
  const original=await h.service.dispatch(request)
  h.client.hidden=true;await h.service.refreshJobs()
  assert.equal((await h.journal.get(request.key)).state,'queued','Known ID is queried even outside the native recent list')
  h.client.jobs.get=async()=>undefined
  await h.service.refreshJobs()
  const missing=await h.journal.get(request.key)
  assert.equal(missing.state,'unknown');assert.equal(missing.agentJobId,original.agentJobId)
  await assert.rejects(h.service.retry(request.key),/accepted job/)
  assert.equal(h.client.calls.length,1)
  console.log('PASS native history loss is unknown and never authorizes automatic original replay')
}
{
  const h=harness();await prepare(h)
  const wide=validateReceiptLayout({paperWidth:72,printableWidth:68,margins:{left:2,right:6,top:1,bottom:8}},80),narrow=validateReceiptLayout({paperWidth:48,printableWidth:48,inset:2},58)
  assert.deepEqual(validateReceiptLayout({},58),{paperWidth:48,printableWidth:48,margins:{top:3,right:3,bottom:3,left:3}})
  assert.equal(validateReceiptLayout({},80).paperWidth,72)
  assert.equal(validateReceiptLayout({paperWidth:80,printableWidth:80},80).printableWidth,80,'Explicit calibrated full-width geometry is preserved')
  for(const value of [{paperWidth:81},{paperWidth:72,printableWidth:80},{inset:-1},{inset:11},{paperWidth:10,inset:3},{paperWidth:'72'},{paperWidth:NaN},{margins:{left:-1}},{margins:{bottom:21}},{margins:{right:'3'}},{margins:{top:NaN}},{margins:{left:20,right:20},paperWidth:48},{margins:null}])assert.throws(()=>validateReceiptLayout(value,80))
  await assert.rejects(h.service.saveReceiptLayout('Till',80,wide,async()=>{throw new Error('Denied')}),/Denied/)
  assert.equal((await h.service.binding('Till')).receiptLayout,undefined)
  await h.service.saveReceiptLayout('Till',80,wide,async()=>{})
  await h.service.saveReceiptLayout('Till',58,narrow,async()=>{})
  assert.deepEqual((await h.service.binding('Till')).receiptLayout,{58:narrow,80:wide})
  assert.equal((await h.service.binding('Another outlet')).receiptLayout,undefined)
  assert.equal(h.client.calls.length,0);assert.equal(h.client.pairings.length,0,'Layout save does not print or change scopes')
  await h.service.saveBinding('Till',{receipt:'receipt'},async()=>{})
  assert.deepEqual((await h.service.binding('Till')).receiptLayout,{58:narrow,80:wide})
  await h.service.saveBinding('Till',{receipt:'label'},async()=>{})
  assert.equal((await h.service.binding('Till')).receiptLayout,undefined,'A different queue requires its own measurements')
  await assert.rejects(h.service.saveReceiptLayout('Unassigned',80,wide,async()=>{}),/Save a receipt printer/)
  assert.deepEqual(receiptHtmlOptions({width:72,height:195},2),{copies:2,size:{width:72,height:195},margins:0,orientation:'portrait',scale:'fit'})
  console.log('PASS receipt layout bounds, server authorization, per-roll/outlet storage, queue changes and exact HTML options')
}
{
  let clock=0,scans=0,caps=0,release,auditReleased=false
  const auditGate=new Promise(resolve=>{release=resolve}),h=harness({now:()=>clock,report:()=>auditGate})
  await prepare(h)
  h.client.printers.list=async()=>{scans++;return [{id:'receipt',name:'Receipt'}]}
  h.client.printers.capabilities=async()=>{caps++;return {maxCopies:99}}
  h.client.jobs.list=async()=>{throw Error('Accepted printing must not scan old native jobs')}
  const timeout=setTimeout(()=>{auditReleased=true;release()},2000)
  try {
    const first=await h.service.dispatch(request)
    assert.ok(first.agentJobId)
    assert.equal(auditReleased,false,'The first print must return before the blocked audit is released')
    // A blocked ERP audit cannot hold the accepted print response.
    let returned=false
    const next=h.service.dispatch({...request,key:'next-sale'}).then(()=>{returned=true})
    for(let i=0;i<30&&!returned;i++)await new Promise(resolve=>setTimeout(resolve,0))
    assert.equal(returned,true,'Native acceptance returns while ERP reporting is blocked')
    await next
    assert.equal(scans,1);assert.equal(caps,1)
    clock=30001
    await h.service.dispatch({...request,key:'after-cache-expiry'})
    assert.equal(scans,2);assert.equal(caps,2)
    await h.service.refreshPrinters()
    await h.service.dispatch({...request,key:'after-explicit-refresh'})
    assert.equal(scans,3);assert.equal(caps,3)
    assert.equal(h.service.state.jobs.length,4,'Accepted jobs appear immediately without a full queue scan')
    assert.equal((await h.service.dispatch(request)).intentId,first.intentId)
    assert.equal(h.client.calls.length,4,'Duplicate original does not rescan or resend')
  } finally {release();clearTimeout(timeout)}
  console.log('PASS fast acceptance independent of audit/history, bounded discovery/capability cache and explicit refresh')
}
{
  const h=harness();await prepare(h);await h.service.resume()
  const record=await h.service.dispatch(request)
  const job=h.client.accepted[0]
  for(const state of ['submitted','queued'])for(const fn of h.client.events.get('job.changed'))fn({...job,state})
  for(let i=0;i<20;i++)await new Promise(resolve=>setTimeout(resolve,0))
  assert.equal((await h.journal.get(record.key)).state,'submitted','Late queued events cannot erase submission')
  h.service.dispose()
  console.log('PASS serialized status observations preserve confirmed receipt submission')
}
console.log('All Esafe printing orchestration checks passed')
