// Real SDK encoder + print service/controller; native I/O is mocked only here.
import assert from 'node:assert/strict'
import { encodeCashDrawerPulse } from '@esafe/printer-manager'
import { createEsafeService } from './src/printing/esafe.js'
import { createDrawerController, validateDrawer } from './src/printing/drawer.js'
assert.deepEqual([...encodeCashDrawerPulse()], [27,112,0,50,250])
assert.deepEqual([...encodeCashDrawerPulse({pin:1,onMs:2,offMs:510})], [27,112,1,1,255])
assert.equal(validateDrawer().enabled,false);assert.equal(validateDrawer().automatic,false)
for(const value of [{pin:2},{pin:true},{onMs:3},{onMs:0},{offMs:512},{onMs:2.5},{onMs:'100'}]) assert.throws(()=>validateDrawer(value))
function harness(shared={}) {
  const settings=shared.settings || new Map(),rows=shared.rows || new Map(),locks=shared.locks || new Map(),events=new Map(),calls=[],jobs=[]
  const clone=(v)=>v===undefined ? undefined : structuredClone(v)
  const journal={setting:async(k)=>clone(settings.get(k)),saveSetting:async(k,v)=>settings.set(k,clone(v)),settings:async()=>[...settings.values()].map(clone),get:async(k)=>clone(rows.get(k)),put:async(v)=>rows.set(v.key,clone(v)),list:async()=>[...rows.values()].map(clone)}
  const client={isConnected:true,isPaired:true,lost:false,hide:false,printers:{list:async()=>[{id:'receipt',name:'Receipt'}],getDefault:async()=>null,capabilities:async()=>({maxCopies:99})},
    jobs:{list:async()=>client.hide ? [] : jobs,get:async(id)=>jobs.find((j)=>j.id===id),reprint:async()=>{throw new Error('Pulse reprint must never reach SDK')}},
    print:async(request)=>{calls.push(clone(request));let job=jobs.find((j)=>j.key===request.idempotencyKey);if(!job){job={id:crypto.randomUUID(),key:request.idempotencyKey,title:request.title,format:request.format,printerId:request.printerId,state:'queued'};jobs.push(job)}if(client.lost)throw new Error('Lost acknowledgement');return job},
    connect:async()=>({paired:true,port:17651}),disconnect:()=>{},pair:async()=>{},preview:async()=>({dataBase64:'',pageCount:1}),
    on:(name,fn)=>{const set=events.get(name)||new Set();set.add(fn);events.set(name,set);return()=>set.delete(fn)}}
  const lock=(key,fn)=>{const task=(locks.get(key)||Promise.resolve()).then(fn);locks.set(key,task.catch(()=>{}));return task}
  const authorized=[],service=createEsafeService({client,journal,lock,device:async()=>'device',authorize:async(r)=>authorized.push(clone(r))})
  service.state.printGrants=['receipt']
  const drawer=createDrawerController(service,async()=>({eligible:true}))
  return {service,drawer,journal,client,calls,jobs,events,authorized,shared:{settings,rows,locks}}
}
async function setup(h,extra={}){await h.journal.saveSetting('approved',true);await h.journal.saveSetting('print-grants',['receipt']);await h.journal.saveSetting('binding:Till',{profile:'Till',receipt:'receipt',drawer:{enabled:true,automatic:true,pin:0,onMs:100,offMs:500,printerId:'receipt',...extra}})}
const sale={receipt:{doctype:'POS Invoice',name:'SALE-1'},profile:'Till',user:'cashier'}
const open={profile:'Till',user:'cashier',reference:{doctype:'POS Profile',name:'Till'},mode:'test'}
const tick=()=>new Promise((r)=>setTimeout(r,0))
{
  const h=harness();await setup(h)
  const all=await Promise.all(Array.from({length:8},()=>h.drawer.afterSale(sale)))
  assert.equal(h.calls.length,1);assert.equal(new Set(all.map((r)=>r.intentId)).size,1)
  assert.deepEqual([...h.calls[0].data],[27,112,0,50,250]);assert.deepEqual(h.calls[0].options,{copies:1})
  const other=harness(h.shared);await other.drawer.afterSale(sale);assert.equal(other.calls.length,0)
  await assert.rejects(h.service.reprint(all[0].key),/cannot be reprinted/)
  console.log('PASS pulse vectors, default-off policy, automatic dedupe, reload/shared journal and blocked pulse reprint')
}
{
  const h=harness();await setup(h);const other=harness(h.shared)
  await Promise.all([h.drawer.afterSale(sale),other.drawer.afterSale(sale)])
  assert.equal(h.calls.length+other.calls.length,1,'Concurrent tabs share one pulse intent')
  for(const flags of [{offline:true},{reprint:true},{receipt:{...sale.receipt,offline:true}},{receipt:{...sale.receipt,is_return:true}},{receipt:{...sale.receipt,on_account:{amount:10}}}]) await h.drawer.afterSale({...sale,...flags})
  assert.equal(h.calls.length+other.calls.length,1)
  console.log('PASS concurrent tabs and offline/return/on-account/historical-reprint exclusions')
}
{
  const h=harness();await setup(h)
  const receipt=await h.service.dispatch({key:'receipt',profile:'Till',role:'receipt',format:'pdf',data:new Uint8Array([1,2]),options:{copies:3},title:'Receipt',reference:sale.receipt,user:'cashier'})
  const result=h.drawer.afterSale({...sale,receiptJob:receipt})
  for(let i=0;i<10;i++)await tick()
  assert.equal(h.calls.length,1,'Queued acceptance must not pulse')
  h.jobs[0].state='submitted';h.events.get('job.changed').forEach((fn)=>fn(h.jobs[0]))
  await result
  assert.equal(h.calls.length,2);assert.equal(h.calls[0].options.copies,3);assert.equal(h.calls[1].options.copies,1)
  assert.equal(h.calls[1].printerId,h.calls[0].printerId)
  assert.equal(h.authorized[1].drawer.receiptIntent,receipt.intentId)
  console.log('PASS three receipt copies followed by one separate same-queue pulse only after submission')
}
{
  const h=harness();await setup(h)
  await assert.rejects(h.drawer.afterSale({...sale,receiptJob:{key:'failed',agentJobId:'bad',state:'failed',intentId:'failed'}}),/not confirmed/)
  assert.equal(h.calls.length,0)
  await h.service.preview('Till','receipt','html','test')
  await h.service.resume();await h.service.refreshJobs();h.service.dispose()
  assert.equal(h.calls.length,0,'Preview, resume, reconnect and refresh must never pulse')
  console.log('PASS failed receipt blocks attached pulse and preview/resume/status never open the drawer')
}
{
  const h=harness();await setup(h);h.client.lost=true;h.client.hide=true
  const row=await h.drawer.open({...open,key:'lost'})
  assert.equal(row.state,'unknown');const before=cloneRequest(h.calls[0])
  await h.service.resume();assert.equal(h.calls.length,1)
  h.client.lost=false
  await h.service.retry('lost');assert.deepEqual(cloneRequest(h.calls[1]),before);assert.equal(h.jobs.length,1)
  await h.drawer.open({...open,key:'new-intent'});assert.equal(h.jobs.length,2)
  console.log('PASS lost acknowledgement remains manual; identical retry preserves bytes/title/key; new opening gets a new intent')
}
function cloneRequest(r){return {...r,data:[...r.data]}}
console.log('All cash drawer software checks passed; no hardware was opened')
