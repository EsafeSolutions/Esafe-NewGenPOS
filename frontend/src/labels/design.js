// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
export const FIELDS = ['shop','logo','name','price','equivalent','barcode','digits','code','uom','brand','batch','expiry','serial','note']
export const DESIGNS = [
  ['classic','Classic','Name, price and barcode'],['branded','Company logo','Your branding above the product'],
  ['bold-retail','Bold retail','Condensed lettering, wide barcode and vertical price'],
  ['barcode-right','Barcode right','Product details beside the barcode'],['barcode-left','Barcode left','Barcode beside product details'],
  ['price-first','Price first','A larger selling price'],['minimal','Barcode only','A clear product identifier'],
  ['rotated','Rotated barcode','Vertical barcode beside the price'],['shelf','Shelf label','Product, price and unit'],
  ['bilingual','Two names','Product name and a second text line'],['batch','Batch and expiry','Traceability with a product barcode'],
  ['variant','Variant / serial','Brand, unit and serial number'],['qr','QR label','Product code or a chosen link'],
  ['dual','Barcode and QR','Two identifiers on one label'],['jewelry','Split tag','Two printable ends and a blank bridge'],
  ['carton','Carton / stock','Larger identification and quantity'],
].map(([key,label,description]) => ({key,label,description}))
export const BINDINGS = [{key:'name',label:'Item name'},{key:'price',label:'Selling price'},{key:'shop',label:'Company name'},{key:'code',label:'Item code'},{key:'uom',label:'Unit'},{key:'brand',label:'Brand'},{key:'batch',label:'Batch'},{key:'expiry',label:'Expiry date'},{key:'serial',label:'Serial number'},{key:'equivalent',label:'Other currencies'},{key:'note',label:'Second name / note'},{key:'quantity',label:'Quantity'},{key:'date',label:'Print date'}]
export const FONTS = [{key:'Arial',label:'Arial'},{key:'Impact',label:'Impact (bold condensed)'},{key:'Tahoma',label:'Tahoma'},{key:'Georgia',label:'Georgia'},{key:'monospace',label:'Monospace'}]
export function fontFamily(key) {
  if (key === 'Impact') return 'Impact, "Arial Narrow", Arial, "Nirmala UI", "Iskoola Pota", sans-serif'
  return FONTS.some(font => font.key === key) ? `${key},sans-serif` : 'Arial,sans-serif'
}
export const DEFAULT_DESIGN = {key:'classic',scale:100,padding:1.2,align:'center',font:'Arial',nameSize:3,priceSize:5,textSize:2.2,logo:'',logoSource:'receipt',barcodeFormat:'AUTO',autoFit:true,module:.33,retail:false,show:{shop:false,logo:false,name:true,price:true,equivalent:false,barcode:true,digits:true,code:false,uom:false,brand:false,batch:false,expiry:false,serial:false,note:false},elements:[]}
const e = (id,type,binding,x,y,w,h,extra={}) => ({id,type,binding,x,y,w,h,rotation:0,align:'center',...extra})
export function templateElements(key) {
  const name = e('name','text','name',0,0,100,17,{size:'nameSize',bold:true})
  const price = e('price','text','price',0,18,100,22,{size:'priceSize',bold:true})
  const barcode = e('barcode','barcode','barcode',0,43,100,48)
  const digits = e('digits','text','barcode',0,92,100,8)
  const base = [name,price,barcode,digits,e('code','text','code',0,91,100,9)]
  if (key === 'bold-retail') return [
    e('name','text','name',0,1,80,23,{size:'nameSize',singleLine:true}),
    e('barcode','barcode','barcode',1,29,78,29),
    e('digits','text','barcode',0,60,80,12,{font:'Arial',bold:true,singleLine:true}),
    e('shop','text','shop',0,77,80,22,{size:'nameSize',singleLine:true}),
    e('price','text','price',85,0,15,100,{size:'priceSize',singleLine:true,fillBox:true,rotation:90}),
    e('divider','line','',82,0,.4,100,{rotation:90,dashed:true}),
  ]
  if (key === 'minimal') return [e('barcode','barcode','barcode',0,0,100,83),e('digits','text','barcode',0,85,100,15),e('code','text','code',0,85,100,15)]
  if (key === 'barcode-right' || key === 'barcode-left') {
    const left = key === 'barcode-left', tx = left ? 62 : 0, bx = left ? 0 : 40
    return [e('name','text','name',tx,0,38,30,{size:'nameSize',bold:true}),e('price','text','price',tx,34,38,30,{size:'priceSize',bold:true}),e('code','text','code',tx,70,38,20),e('barcode','barcode','barcode',bx,0,60,82),e('digits','text','barcode',bx,85,60,15)]
  }
  if (key === 'rotated') return [e('name','text','name',0,0,64,25,{size:'nameSize',bold:true}),e('price','text','price',0,30,64,30,{size:'priceSize',bold:true}),e('barcode','barcode','barcode',68,0,32,100,{rotation:90}),e('code','text','code',0,75,64,20)]
  if (key === 'branded') return [e('logo','image','logo',0,0,30,22),e('shop','text','shop',33,0,67,18,{bold:true}),e('name','text','name',0,24,100,16,{size:'nameSize',bold:true}),e('price','text','price',0,42,100,18,{size:'priceSize',bold:true}),e('barcode','barcode','barcode',0,62,100,30),digits]
  if (key === 'price-first') return [name,e('price','text','price',0,18,100,35,{size:'priceSize',bold:true}),e('barcode','barcode','barcode',0,56,100,34),digits]
  if (key === 'qr') return [e('qr','qr','barcode',0,0,48,100),e('name','text','name',50,0,50,32,{size:'nameSize',bold:true}),e('price','text','price',50,35,50,30,{size:'priceSize',bold:true}),e('code','text','code',50,70,50,20)]
  if (key === 'dual') return [e('name','text','name',0,0,100,16,{size:'nameSize',bold:true}),e('price','text','price',0,18,100,20,{size:'priceSize',bold:true}),e('barcode','barcode','barcode',0,42,66,48),e('digits','text','barcode',0,92,66,8),e('qr','qr','barcode',68,42,32,58)]
  if (key === 'jewelry') return [e('name','text','name',0,0,36,42,{size:'nameSize'}),e('price','text','price',0,47,36,45,{size:'priceSize',bold:true}),e('barcode','barcode','barcode',64,0,36,80),e('digits','text','barcode',64,83,36,16)]
  if (['batch','variant','shelf','bilingual','carton'].includes(key)) {
    const fields = {batch:['batch','expiry'],variant:['brand','serial'],shelf:['uom','equivalent'],bilingual:['note'],carton:['code','quantity']}[key]
    return [name,e('price','text','price',0,18,100,18,{size:'priceSize',bold:true}),...fields.map((f,i) => e(f,'text',f,i*50,37,fields.length === 1 ? 100 : 49,12)),e('barcode','barcode','barcode',0,51,100,39),digits]
  }
  return [...base,e('shop','text','shop',0,0,100,8),e('logo','image','logo',0,0,20,15),e('equivalent','text','equivalent',0,36,100,7)]
}
export function designFor(key, previous=DEFAULT_DESIGN) {
  const show = {...DEFAULT_DESIGN.show}
  if (key === 'branded') { show.shop=true; show.logo=true }
  if (key === 'bold-retail') show.shop=true
  if (key === 'minimal') { show.name=false; show.price=false }
  else { show.name=true; show.price=true }
  if (key === 'batch') { show.batch=true; show.expiry=true }
  if (key === 'variant') { show.brand=true; show.serial=true }
  if (key === 'shelf') show.uom=true
  if (key === 'bilingual') show.note=true
  if (key === 'carton') show.code=true
  if (key === 'qr') { show.barcode=false; show.digits=false; show.code=true }
  const typography = key === 'bold-retail' ? {font:'Impact',nameSize:7,priceSize:9,textSize:3.2} : previous.key === 'bold-retail' ? {font:DEFAULT_DESIGN.font,nameSize:DEFAULT_DESIGN.nameSize,priceSize:DEFAULT_DESIGN.priceSize,textSize:DEFAULT_DESIGN.textSize} : {}
  return {...previous,...typography,key,show,elements:templateElements(key)}
}
export function valueOf(row, binding) {
  const map = {name:'item_name',price:'price_text',shop:'shop',code:'item_code',equivalent:'equivalent_text',batch:'batch_no',expiry:'expiry_date',serial:'serial_no',quantity:'qty'}
  return String(row[binding === 'date' ? 'print_date' : map[binding] || binding] ?? '')
}
export function visibleElement(element, design) {
  if (element.hidden) return false
  if (element.type === 'qr') return true
  return design.show[element.id] !== false
}
