// Test-only native bridge. Production imports the real private SDK.
export function installEsafeTestBridge() {
  const NativeSocket=window.WebSocket
  const bridge=window.testBridge={approved:false,revoked:false,down:false,scopes:[],pairings:[],prints:[],jobs:[],sockets:[],signed:0,connections:[],printers:[{id:'receipt-id',name:'Counter receipt',isDefault:true},{id:'label-id',name:'Label printer'},{id:'office-id',name:'Office A4'}]}
  const encode=(bytes)=>btoa(String.fromCharCode(...new Uint8Array(bytes))),decode=(text)=>Uint8Array.from(atob(text),(c)=>c.charCodeAt(0))
  const canonical=(v)=>v===null || typeof v!=='object' ? JSON.stringify(v) : Array.isArray(v) ? '['+v.map(canonical).join(',')+']' : '{'+Object.keys(v).sort().map((k)=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}'
  class Socket {
    constructor(url,...args){
      if(!String(url).startsWith('wss://localhost:'))return new NativeSocket(url,...args)
      bridge.sockets.push(this);bridge.connections.push(String(url));this.url=String(url);this.readyState=0;this.seq=0;this.session=crypto.randomUUID();this.challenge='test-native-challenge';this.incoming=Promise.resolve()
      setTimeout(()=>{if(bridge.down || new URL(url).port!=='17651'){this.onerror?.({});this.close();return}this.readyState=1;this.message({event:'hello',sessionId:this.session,challenge:this.challenge,protocol:1,version:'0.2.1'})},0)
    }
    message(value){this.onmessage?.({data:JSON.stringify(value)})}
    send(value){this.incoming=this.incoming.then(()=>this.handle(JSON.parse(value))).catch((e)=>{window.nativeMockError=e.message;this.close()})}
    async handle(req){
      const respond=(result)=>this.message({jsonrpc:'2.0',id:req.id,result}),deny=()=>this.message({id:req.id,error:{code:'PERMISSION_DENIED',message:'Approve printer access in Esafe'}})
      if(req.method==='session.authenticate'){
        this.key=await crypto.subtle.importKey('raw',decode(req.params.publicKey),{name:'ECDSA',namedCurve:'P-256'},false,['verify'])
        if(!await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},this.key,decode(req.params.signature),new TextEncoder().encode('esafe-v1\n'+this.session+'\n'+this.challenge+'\n'+location.origin)))throw new Error('Invalid SDK authentication signature')
        respond({authenticated:bridge.approved&&!bridge.revoked});return
      }
      const {signature,...envelope}=req
      if(req.seq!==++this.seq || !await crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'},this.key,decode(signature),new TextEncoder().encode(canonical(envelope))))throw new Error('Invalid signed SDK request or sequence')
      bridge.signed++
      if(req.method==='pair.request'){bridge.scopes=req.params.permissions;bridge.pairings.push(req.params.permissions);respond({pairingId:'pair'});return}
      if(req.method==='pair.status'){bridge.approved=true;bridge.revoked=false;respond({state:'approved'});return}
      if(bridge.revoked){deny();return}
      if(req.method==='events.subscribe'){respond({subscribed:true});return}
      if(req.method==='printers.list'){respond(bridge.printers);return}
      if(req.method==='printers.capabilities'){respond({printerId:req.params.printerId,driver:'Test Windows driver',port:'USB001',maxCopies:99,color:false,duplex:false,physicalCompletionAvailable:false});return}
      if(req.method==='jobs.list'){respond(bridge.jobs);return}
      if(req.method==='jobs.get'){respond(bridge.jobs.find((j)=>j.id===req.params.jobId));return}
      if(req.method==='print'){
        if(!bridge.scopes.some((s)=>s.action==='print'&&s.resources.includes(req.params.printerId))){deny();return}
        bridge.prints.push(req.params)
        const job={id:crypto.randomUUID(),printerId:req.params.printerId,format:req.params.format,title:req.params.title,state:'queued',certainty:'durable acceptance',error:null,spoolId:null,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()}
        bridge.jobs.push(job);respond(job);setTimeout(()=>this.message({event:'job.changed',data:job}),0);return
      }
      if(req.method==='print.preview'){respond({format:'png',dataBase64:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1cAAAAASUVORK5CYII=',pageCount:1});return}
      respond({})
    }
    close(){this.readyState=3;setTimeout(()=>this.onclose?.({}),0)}
  }
  window.WebSocket=Socket
}
