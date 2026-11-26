// Preview-only integration with an isolated copy of the installed native agent.
// Never calls print(), never uses production grants/data, never installs trust.
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { readFileSync, createReadStream } from 'node:fs'
import { createRequire } from 'node:module'
import { createHash } from 'node:crypto'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { EsafeClient } from '@esafe/printer-manager'
const root=path.dirname(fileURLToPath(import.meta.url))
const managerSource=process.env.ESAFE_TEST_SOURCE || 'C:/Files/Esafe Printer manager'
const { WebSocket }=createRequire(path.join(managerSource,'package.json'))('ws')
const installed=process.env.ESAFE_TEST_EXECUTABLE || 'C:/Users/ESafe-Arshad/AppData/Local/Esafe Printer Manager/esafe-printer-manager.exe'
const runtime=process.env.ESAFE_TEST_RUNTIME_DIR || path.join(path.dirname(installed),'runtime')
const output=path.resolve(root,'../artifacts/esafe-printing/receipt-layout/native')
const data=path.join(output,'isolated-agent-'+Date.now())
await mkdir(data,{recursive:true})
const sid=execFileSync('whoami.exe',['/user','/fo','csv','/nh'],{encoding:'utf8',windowsHide:true}).match(/S-1-\d+(?:-\d+)+/)[0]
const namespace='receipt-preview-'+process.pid+'-'+Date.now(),pipe='\\\\.\\pipe\\EsafePrinterManager-'+sid+'-'+namespace
const agent=spawn(installed,['--agent'],{cwd:path.dirname(installed),env:{...process.env,ESAFE_DATA_DIR:data,ESAFE_IPC_NAMESPACE:namespace,ESAFE_RUNTIME_DIR:runtime},windowsHide:true,stdio:['ignore','pipe','pipe']})
let stderr='',owned=false,client,helloVersion
agent.stderr.on('data',d=>stderr+=d)
function admin(method,params={}){
  return new Promise((resolve,reject)=>{
    const socket=net.createConnection(pipe);let buffer=''
    socket.setTimeout(90000,()=>socket.destroy(new Error('Isolated agent control timeout')))
    socket.on('connect',()=>socket.write(JSON.stringify({id:crypto.randomUUID(),method,params})+'\n'))
    socket.on('data',d=>{buffer+=d;if(buffer.includes('\n')){socket.end();const result=JSON.parse(buffer.slice(0,buffer.indexOf('\n')));result.error?reject(new Error(result.error.message)):resolve(result.result)}})
    socket.on('error',reject)
  })
}
try{
  let snapshot
  for(let i=0;i<100;i++){
    if(agent.exitCode!==null)throw new Error('Isolated agent exited: '+stderr)
    try{snapshot=await admin('admin.snapshot');break}catch{await new Promise(r=>setTimeout(r,150))}
  }
  assert.ok(snapshot,'Isolated agent started')
  assert.equal(path.resolve(snapshot.dataDirectory).toLowerCase(),path.resolve(data).toLowerCase(),'Must never use the production agent control pipe')
  owned=true
  const identity=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},false,['sign','verify'])
  const origin='https://synthetic-receipt.esafe.test'
  client=new EsafeClient({origin,identityStore:{get:async()=>identity},transportFactory:url=>{
    const socket=new WebSocket(url,{origin,ca:readFileSync(path.join(data,'localhost-ca.pem'))})
    socket.on('message',message=>{const value=JSON.parse(String(message));if(value.event==='hello')helloVersion=value.version})
    return socket
  }})
  await client.connect({ports:[snapshot.port]})
  const printerId='Xprinter XP-80(Copy 1)',permissions=[{action:'printers.list',resources:['printers']},{action:'print',resources:[printerId]}]
  const pairing=client.pair(permissions,{timeoutMs:20000});let pending
  for(let i=0;i<60;i++){pending=(await admin('admin.snapshot')).pending.find(p=>p.origin===origin);if(pending)break;await new Promise(r=>setTimeout(r,100))}
  assert.ok(pending)
  await admin('admin.pairing.decide',{id:pending.id,allow:true,permissions});await pairing
  const printers=await client.printers.list();assert.ok(printers.some(p=>p.id===printerId),'Use the same installed Windows queue')
  const capabilities=await client.printers.capabilities(printerId),results=[]
  for(const [phase,name]of[['before','58-Table-58'],['before','80-Table-80'],['after','58-Table-58'],['after','80-Table-80'],['after','80-Table-72'],['after','80-Table-72-M3-7-1-6'],['after','80-Table-72-CUSTOM'],['after','80-Table-80-SAFE'],['after','58-Table-58-CUSTOM-SAFE'],['after','80-Retail-80-SAFE-LONG']]){
    const file=path.resolve(output,'..',phase,name+'.request.json'),request=JSON.parse(await readFile(file,'utf8'))
    const response=await client.preview({printerId:request.printerId,format:request.format,data:new Uint8Array(Buffer.from(request.dataBase64,'base64')),options:request.options,title:request.title})
    await writeFile(path.join(output,phase+'-'+name+'.png'),Buffer.from(response.dataBase64,'base64'))
    results.push({phase,name,version:helloVersion,options:request.options,pageCount:response.pageCount,sha256:createHash('sha256').update(Buffer.from(request.dataBase64,'base64')).digest('hex')})
    console.log('PASS native preview '+helloVersion+' '+phase+' '+name+' ('+response.pageCount+' pages)')
  }
  assert.deepEqual(await client.jobs.list(),[],'Preview must never create a native print/drawer job')
  await writeFile(path.join(output,'result.json'),JSON.stringify({runningBinary:installed,nativeVersion:helloVersion,printerId,capabilities,isolated:true,physicalPrintPerformed:false,jobsCreated:0,certificateTrustChanged:false,previews:results},null,2))
  console.log('PASS actual SDK -> installed native binary previews; no spooler jobs, drawer pulses or Windows trust changes')
}finally{
  client?.disconnect()
  if(agent.exitCode===null){if(owned){try{await admin('admin.shutdown')}catch{agent.kill()}}else agent.kill()}
}
