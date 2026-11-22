// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
import { documentHtml, pageSvg, safeImage } from './render.js'

export function download(blob,name) {
  const url=URL.createObjectURL(blob),a=document.createElement('a')
  a.href=url; a.download=name; a.click()
  setTimeout(() => URL.revokeObjectURL(url),10000)
}
export async function imageData(url) {
  if (!safeImage(url)) throw new Error('Choose a valid PNG, JPEG or WebP logo.')
  const response=await fetch(url,{credentials:'same-origin'})
  if (!response.ok) throw new Error('The company logo could not be loaded.')
  const blob=await response.blob()
  if (blob.size>5000000) throw new Error('Choose a logo smaller than 5 MB.')
  return resizeLogo(blob)
}
export async function resizeLogo(blob) {
  if (!['image/png','image/jpeg','image/webp','image/svg+xml'].includes(blob.type)) throw new Error('Choose a PNG, JPEG, WebP or SVG logo.')
  const bitmap=new Image(),url=URL.createObjectURL(blob)
  try {
    bitmap.src=url;await bitmap.decode()
    if(!bitmap.naturalWidth || !bitmap.naturalHeight)throw new Error('The logo has no readable dimensions.')
    const ratio=Math.min(1,400/bitmap.width,160/bitmap.height),canvas=document.createElement('canvas')
    canvas.width=Math.max(1,Math.round(bitmap.width*ratio)); canvas.height=Math.max(1,Math.round(bitmap.height*ratio))
    const ctx=canvas.getContext('2d'); ctx.fillStyle='white'; ctx.fillRect(0,0,canvas.width,canvas.height); ctx.drawImage(bitmap,0,0,canvas.width,canvas.height)
    const result=canvas.toDataURL('image/png')
    if (result.length>80000) throw new Error('This logo is too detailed. Use a simpler or smaller logo.')
    return result
  } finally { URL.revokeObjectURL(url) }
}
export async function browserPrint(svgs,g,title='Labels') {
  const frame=document.createElement('iframe')
  frame.title=title; frame.setAttribute('aria-hidden','true')
  frame.style.cssText=`position:fixed;left:-10000px;width:${g.pageW}mm;height:${g.pageH}mm;border:0`
  frame.setAttribute('sandbox','allow-same-origin allow-modals')
  try {
    await new Promise((resolve,reject) => {
      const timer=setTimeout(() => reject(new Error('The label print window could not be prepared.')),10000)
      frame.onload=() => { clearTimeout(timer); resolve() }
      frame.srcdoc=documentHtml(svgs,g.pageW,g.pageH,title); document.body.appendChild(frame)
    })
    await frame.contentDocument.fonts.ready
    await Promise.all([...frame.contentDocument.images].map((img) => img.decode()))
    frame.contentWindow.addEventListener('afterprint',() => setTimeout(() => frame.remove(),0),{once:true})
    frame.contentWindow.focus(); frame.contentWindow.print()
    setTimeout(() => frame.remove(),60000)
  } catch (error) { frame.remove(); throw error }
}
async function raster(svg,g,dpi) {
  const width=Math.round(g.pageW*dpi/25.4),height=Math.round(g.pageH*dpi/25.4)
  if (width*height>20000000 || !width || !height) throw new Error('This page is too large at the chosen resolution. Reduce DPI or page size.')
  const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'})),img=new Image()
  try {
    img.src=url; await img.decode()
    const canvas=document.createElement('canvas'); canvas.width=width; canvas.height=height
    const ctx=canvas.getContext('2d',{willReadFrequently:true}); ctx.fillStyle='white';ctx.fillRect(0,0,width,height)
    ctx.imageSmoothingEnabled=false;ctx.drawImage(img,0,0,width,height)
    return {canvas,ctx,width,height}
  } finally { URL.revokeObjectURL(url) }
}
const bytes=(s) => new TextEncoder().encode(s)
function concat(arrays) { const result=new Uint8Array(arrays.reduce((n,a) => n+a.length,0));let i=0;for(const a of arrays){result.set(a,i);i+=a.length}return result }
export async function pdfDocument(svgs,g,dpi=203.2,monochrome=true) {
  const objects=[null,null],kids=[]
  for (const svg of svgs) {
    const {ctx,width,height}=await raster(svg,g,dpi),rgba=ctx.getImageData(0,0,width,height).data,gray=new Uint8Array(width*height)
    for(let i=0;i<gray.length;i++) { const v=Math.round(rgba[i*4]*.299+rgba[i*4+1]*.587+rgba[i*4+2]*.114);gray[i]=monochrome ? (v<160 ? 0 : 255) : v }
    const stream=new Blob([gray]).stream().pipeThrough(new CompressionStream('deflate'))
    const compressed=new Uint8Array(await new Response(stream).arrayBuffer()),image=objects.length+1
    objects.push(concat([bytes(`<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Interpolate false /Length ${compressed.length} >>\nstream\n`),compressed,bytes('\nendstream')]))
    const pw=g.pageW*72/25.4,ph=g.pageH*72/25.4,commands=`q ${pw} 0 0 ${ph} 0 0 cm /Im0 Do Q`,content=objects.length+1
    objects.push(bytes(`<< /Length ${commands.length} >>\nstream\n${commands}\nendstream`))
    const page=objects.length+1;kids.push(`${page} 0 R`)
    objects.push(bytes(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw} ${ph}] /Resources << /XObject << /Im0 ${image} 0 R >> >> /Contents ${content} 0 R >>`))
  }
  objects[0]=bytes('<< /Type /Catalog /Pages 2 0 R >>')
  objects[1]=bytes(`<< /Type /Pages /Kids [${kids.join(' ')}] /Count ${kids.length} >>`)
  const chunks=[bytes('%PDF-1.4\n')],offsets=[0];let length=chunks[0].length
  objects.forEach((object,i) => {offsets.push(length);const data=concat([bytes(`${i+1} 0 obj\n`),object,bytes('\nendobj\n')]);chunks.push(data);length+=data.length})
  const xref=length
  chunks.push(bytes(`xref\n0 ${objects.length+1}\n0000000000 65535 f\r\n${offsets.slice(1).map((n) => `${String(n).padStart(10,'0')} 00000 n\r\n`).join('')}trailer\n<< /Size ${objects.length+1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`))
  return new Blob(chunks,{type:'application/pdf'})
}
export async function nativeDocument(svgs,g,printer,language) {
  if (g.kind === 'sheet' || g.kind === 'black-mark' || g.feedMode === 'pitch') throw new Error('Native files require a die-cut or continuous roll with the printer advancing the gap.')
  const chunks=[]
  for (const svg of svgs) {
    const {ctx,width,height}=await raster(svg,g,printer.dpi),rgba=ctx.getImageData(0,0,width,height).data,rowBytes=Math.ceil(width/8),bitmap=new Uint8Array(rowBytes*height)
    for(let y=0;y<height;y++) for(let x=0;x<width;x++) {const i=(y*width+x)*4;if(rgba[i]*.299+rgba[i+1]*.587+rgba[i+2]*.114<160)bitmap[y*rowBytes+(x>>3)]|=128>>(x%8)}
    if (language === 'zpl') {
      chunks.push(bytes(`^XA^PW${width}^LL${height}`))
      // ZPL ^GF counts are limited to 99,999 bytes; emit bounded vertical bands.
      const bandRows=Math.max(1,Math.floor(99999/rowBytes))
      for(let y=0;y<height;y+=bandRows){
        const band=bitmap.subarray(y*rowBytes,Math.min(height,y+bandRows)*rowBytes)
        const hex=Array.from(band,(b) => b.toString(16).padStart(2,'0').toUpperCase()).join('')
        chunks.push(bytes(`^FO0,${y}^GFA,${band.length},${band.length},${rowBytes},${hex}^FS`))
      }
      chunks.push(bytes('^XZ\n'))
    } else {
      chunks.push(bytes(`SIZE ${g.pageW} mm,${g.h} mm\r\nGAP ${g.kind === 'continuous' ? 0 : g.gapY} mm,0 mm\r\nDIRECTION 1\r\nCLS\r\nBITMAP 0,0,${rowBytes},${height},0,`),bitmap.map((b) => b^255),bytes('\r\nPRINT 1,1\r\n'))
    }
  }
  return new Blob(chunks,{type:'application/octet-stream'})
}
export function jobSvgs(job,design,printer,guides=false) {return job.pages.map((page) => pageSvg(page,job.geometry,design,printer,guides))}
