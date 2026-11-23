// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
import { datamatrix, code93, drawingSVG } from '@bwip-js/generic'
import qrcode from 'qrcode-generator'
import { encode, formatOf } from '../barcode.js'

qrcode.stringToBytes = (value) => Array.from(new TextEncoder().encode(value))
export const BARCODE_FORMATS = [
  {key:'AUTO',label:'Automatic'},
  {key:'CODE128',label:'Code 128 (standard scanner)'},
  {key:'CODE93',label:'Code 93 (enable on scanner)'},
  {key:'EAN13',label:'EAN-13'},
  {key:'UPCA',label:'UPC-A'},
  {key:'DATAMATRIX',label:'Data Matrix (2D scanner)'},
  {key:'QRCODE',label:'QR Code (2D scanner)'},
]
export const matrixFormat = (format) => format === 'DATAMATRIX' || format === 'QRCODE'
const cache = new Map()
function cacheValue(key,create) {
  if (cache.has(key)) return cache.get(key)
  const value=create()
  if (cache.size>=100) cache.delete(cache.keys().next().value)
  cache.set(key,value)
  return value
}
function bwipSymbol(value,format) {
  const encoder=format === 'DATAMATRIX' ? datamatrix : code93
  const svg=encoder({text:value,scale:1,padding:0,height:10,includecheck:true,parse:false,parsefnc:false},drawingSVG())
  const box=svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)
  if (!box) throw new Error('Missing symbol dimensions')
  const inner=svg.replace(/^<svg[^>]*>/,'').replace(/<\/svg>\s*$/,'')
  if (format === 'CODE93') return {format,text:value,columns:+box[1],rows:1,inner,sourceW:+box[1],sourceH:+box[2],quiet:[10,10],matrix:false}
  // The pinned encoder emits Data Matrix edges on a two-unit module grid.
  // Normalize that grid before snapping it to the printer's physical dots.
  return {format,text:value,columns:+box[1]/2,rows:+box[2]/2,inner,sourceW:+box[1],sourceH:+box[2],quiet:[1,1],matrix:true}
}
export function symbolData(code,requested='AUTO') {
  const value=String(code ?? '')
  if (!value || value.length>1000) return {error:'The barcode value is empty or too long.'}
  if (!BARCODE_FORMATS.some((f) => f.key===requested)) return {error:'Choose a supported barcode format.'}
  try {
    return cacheValue(JSON.stringify([requested,value]),() => {
      if (requested === 'DATAMATRIX' || requested === 'CODE93') return bwipSymbol(value,requested)
      if (requested === 'QRCODE') {
        const qr=qrcode(0,'M');qr.addData(value);qr.make()
        return {format:requested,text:value,columns:qr.getModuleCount(),rows:qr.getModuleCount(),qr,quiet:[4,4],matrix:true}
      }
      const detected=formatOf(value)
      if (!detected || (requested!=='AUTO' && requested!=='CODE128' && detected!==requested)) return {error:'The barcode value is invalid for the selected format.'}
      const data=encode(value,{code128:requested==='CODE128'})
      if(data.text!==value)return {error:'This linear format would change surrounding spaces. Choose a 2D format to preserve the full value.'}
      const quiet=data.format==='EAN13' ? [11,7] : data.format==='UPCA' ? [9,9] : [10,10]
      return {...data,columns:data.modules.length,rows:1,quiet,matrix:false}
    })
  } catch {
    return {error:requested==='CODE93' ? 'Code 93 supports uppercase letters, numbers and its punctuation set. Use Code 128 or a 2D format for this value.' : 'This value cannot be encoded in the selected barcode format.'}
  }
}

export function barcodeMetrics(code,design,printer,box={w:Infinity,h:Infinity}) {
  const data=symbolData(code,design.barcodeFormat || 'AUTO')
  if (data.error) return data
  const dpmm=+printer.dpi/25.4
  if (!Number.isFinite(dpmm) || dpmm<=0) return {error:'Choose a valid printer resolution.'}
  const preferredWidth=Number(design.module ?? .33)
  if (!Number.isFinite(preferredWidth) || preferredWidth<.1 || preferredWidth>2) return {error:'Choose a barcode module width between 0.1 and 2 mm.'}
  const retail=['EAN13','UPCA'].includes(data.format),minimum=retail ? .264 : .19
  const minDots=Math.max(2,Math.ceil(minimum*dpmm-.00001))
  const preferred=Math.max(minDots,Math.ceil(preferredWidth*dpmm-.00001))
  const widthModules=data.columns+data.quiet[0]+data.quiet[1]
  const heightModules=data.matrix ? data.rows+data.quiet[0]+data.quiet[1] : 0
  const fitDots=Math.min(Math.floor(box.w*dpmm/widthModules+.00001),data.matrix ? Math.floor(box.h*dpmm/heightModules+.00001) : Infinity)
  const dots=design.autoFit===false ? preferred : Math.max(minDots,Math.min(preferred,fitDots))
  const module=dots/dpmm,width=widthModules*module,height=data.matrix ? heightModules*module : box.h
  return {...data,module,dots,minDots,dpmm,retail,width,height,minWidth:widthModules*minDots/dpmm,minHeight:data.matrix ? heightModules*minDots/dpmm : 5,adjusted:dots<preferred,fits:width<=box.w+.001 && (!data.matrix || height<=box.h+.001)}
}

export function barcodeBox(element,stock,design,base,code,printer) {
  if (design.autoFit===false || matrixFormat(design.barcodeFormat) || element.type!=='barcode') return base
  if (+element.x!==0 || +element.w!==100 || +design.scale!==100 || ![0,180].includes(+element.rotation)) return base
  const metrics=barcodeMetrics(code,design,printer,base)
  if (metrics.error || metrics.fits) return base
  // Quiet zones already supply clear space beside the bars. A full-width
  // barcode may borrow unused design padding, retaining 0.5 mm edge clearance.
  const x=Math.min(+design.padding,.5),w=stock.w-2*x
  return metrics.minWidth<=w+.001 ? {...base,x,w} : base
}

export function symbolMarkup(metrics,w,h,round) {
  const m=metrics
  if (m.matrix) {
    const x=(w-m.width)/2+m.quiet[0]*m.module,y=(h-m.height)/2+m.quiet[0]*m.module
    if (m.inner) return `<g transform="translate(${round(x)} ${round(y)}) scale(${m.module/2})">${m.inner}</g>`
    let content=''
    for(let row=0;row<m.rows;row++) for(let col=0;col<m.columns;col++) if(m.qr.isDark(row,col)) content+=`<rect x="${round(x+col*m.module)}" y="${round(y+row*m.module)}" width="${round(m.module)}" height="${round(m.module)}"/>`
    return content
  }
  const start=Math.floor((w-m.width)/2*m.dpmm)/m.dpmm+m.quiet[0]*m.module
  if (m.inner) return `<g transform="translate(${round(start)} 0) scale(${m.module} ${h/m.sourceH})">${m.inner}</g>`
  let content=''
  for(let i=0;i<m.modules.length;) {
    if(m.modules[i]==='0'){i++;continue}
    let n=1;while(m.modules[i+n]==='1')n++
    content+=`<rect x="${round(start+i*m.module)}" width="${round(n*m.module)}" height="${round(h)}"/>`;i+=n
  }
  return content
}
