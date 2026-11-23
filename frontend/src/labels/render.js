// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
import qrcode from 'qrcode-generator'
import { barcodeMetrics, barcodeBox, symbolMarkup } from './symbols.js'
export { barcodeMetrics } from './symbols.js'
import { DEFAULT_DESIGN, templateElements, valueOf, visibleElement } from './design.js'
import { DEFAULT_PRINTER, layoutJob, round } from './stock.js'
// The upstream encoder's default byte conversion truncates non-Latin text.
qrcode.stringToBytes = (value) => Array.from(new TextEncoder().encode(value))
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g,(c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c])
export function safeImage(value) {
  const s = String(value || '')
  return /^data:image\/(png|jpeg|webp);base64,[a-z0-9+/=]+$/i.test(s) || /^\/(?!\/)[^<>"\s]+$/.test(s) || /^https:\/\/[^<>"\s]+$/i.test(s) ? s : ''
}
let measureContext
function textWidth(text,size,font,bold) {
  if (typeof document !== 'undefined') {
    measureContext ||= document.createElement('canvas').getContext('2d')
    measureContext.font = `${bold ? 'bold ' : ''}${size*96/25.4}px ${font}`
    return measureContext.measureText(text).width*25.4/96
  }
  return [...text].length*size*.56
}
function textLines(value,w,h,size,font,bold) {
  let lines = []
  for (let trial=size;trial>=1;trial=round(trial-.1)) {
    lines=[]
    for (const paragraph of String(value).split('\n')) {
      let line=''
      for (const word of paragraph.split(/\s+/)) {
        if (line && textWidth(`${line} ${word}`,trial,font,bold)>w) { lines.push(line); line=word }
        else line = line ? `${line} ${word}` : word
      }
      lines.push(line)
    }
    if (lines.length*trial*1.15<=h && lines.every((line) => textWidth(line,trial,font,bold)<=w)) return {lines,size:trial,fits:true}
  }
  return {lines,size:1,fits:false}
}
export function elementBox(el,stock,design) {
  const padding = +design.padding, iw = stock.w-2*padding, ih=stock.h-2*padding, scale=+design.scale/100
  const w=+el.w/100*iw*scale,h=+el.h/100*ih*scale
  const x=stock.w/2+(padding+ +el.x/100*iw-stock.w/2)*scale
  const y=stock.h/2+(padding+ +el.y/100*ih-stock.h/2)*scale
  return {x,y,w,h}
}
export function labelScene(row,stock,input={},printerInput={}) {
  const d={...DEFAULT_DESIGN,...input,show:{...DEFAULT_DESIGN.show,...input.show}},p={...DEFAULT_PRINTER,...printerInput}
  const errors=[],warnings=[],parts=[]
  if (![d.scale,d.padding,d.module,d.nameSize,d.priceSize,d.textSize].every((v) => Number.isFinite(+v)) || +d.scale<10 || +d.scale>300 || +d.padding<0 || +d.padding*2>=Math.min(stock.w,stock.h) || +d.module<.1 || +d.module>2 || [d.nameSize,d.priceSize,d.textSize].some((v) => +v<1 || +v>30)) return {svg:'',errors:['Check the design scale, padding, font sizes and barcode module width.'],warnings:[]}
  if (!Number.isFinite(+p.dpi) || +p.dpi<100 || +p.dpi>1200) return {svg:'',errors:['Printer resolution must be between 100 and 1,200 DPI.'],warnings:[]}
  const elements=d.elements?.length ? d.elements : templateElements(d.key)
  if (elements.length>80) return {svg:'',errors:['Use at most 80 elements per design.'],warnings:[]}
  const font=['Arial','Tahoma','Georgia','monospace'].includes(d.font) ? d.font : 'Arial'
  for (const el of elements) {
    if (!visibleElement(el,d)) continue
    const code=String(row.barcode || row.item_code || '')
    const b=barcodeBox(el,stock,d,elementBox(el,stock,d),code,p)
    if (![b.x,b.y,b.w,b.h].every(Number.isFinite) || b.w<=0 || b.h<=0 || b.x<-.001 || b.y<-.001 || b.x+b.w>stock.w+.001 || b.y+b.h>stock.h+.001) { errors.push('A design element extends outside the label.'); continue }
    if (![0,90,180,270].includes(+el.rotation)) { errors.push('Element rotation must be 0, 90, 180 or 270 degrees.'); continue }
    const rotated=+el.rotation === 90 || +el.rotation === 270, w=rotated ? b.h : b.w,h=rotated ? b.w : b.h
    const value=el.type === 'static' ? String(el.text || '') : valueOf(row,el.binding)
    let content=''
    if (el.type === 'barcode') {
      const m=barcodeMetrics(code,d,p,{w,h})
      if (m.error) { errors.push(m.error); continue }
      if (!m.fits) { errors.push(`Barcode needs ${round(m.width)} mm width${m.matrix ? ` and ${round(m.height)} mm height` : ''}; its box has ${round(w)} × ${round(h)} mm. Try Make barcode fit or a 2D format.`); continue }
      if (!m.matrix && h<5) { errors.push('The barcode height must be at least 5 mm.'); continue }
      if (m.retail && h<18.28) (d.retail ? errors : warnings).push('Retail EAN/UPC bars are below 18.28 mm. Use a taller barcode for standard retail scanning.')
      if (m.matrix) warnings.push('This barcode format requires a 2D scanner. The encoded item value is unchanged.')
      if (m.format==='CODE93') warnings.push('Enable Code 93 on your scanner before using this format.')
      content=symbolMarkup(m,w,h,round)
    } else if (el.type === 'qr') {
      try {
        const payload=String(row.qr || row.barcode || row.item_code || '')
        if (!payload || payload.length>1000) throw new Error()
        const qr=qrcode(0,'M'); qr.addData(payload); qr.make()
        const count=qr.getModuleCount(),dot=Math.floor(Math.min(w,h)*p.dpi/25.4/(count+8))
        if (dot<2) { errors.push('The QR code needs more space at this printer resolution.'); continue }
        const unit=dot*25.4/p.dpi,side=(count+8)*unit,dx=(w-side)/2+4*unit,dy=(h-side)/2+4*unit
        for (let y=0;y<count;y++) for (let x=0;x<count;x++) if (qr.isDark(y,x)) content+=`<rect x="${round(dx+x*unit)}" y="${round(dy+y*unit)}" width="${round(unit)}" height="${round(unit)}"/>`
      } catch { errors.push('The QR value is empty or too long.'); continue }
    } else if (el.type === 'image') {
      const image=safeImage(row.logo || d.logo)
      if (!image) { errors.push('Choose a company logo or turn off the logo field.'); continue }
      content=`<image href="${esc(image)}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet"/>`
    } else if (el.type === 'line' || el.type === 'box') {
      content=el.type === 'line' ? `<path d="M0 ${h/2}H${w}" stroke="black" stroke-width="0.2"/>` : `<rect x="0.1" y="0.1" width="${Math.max(0,w-.2)}" height="${Math.max(0,h-.2)}" fill="none" stroke="black" stroke-width="0.2"/>`
    } else {
      const text=el.binding === 'barcode' ? String(row.barcode || row.item_code || '') : value
      if (!text) continue
      const fit=textLines(text,w,h,+(el.fontSize || d[el.size] || d.textSize)*d.scale/100,font,el.bold)
      if (!fit.fits) { errors.push(`Text does not fit: ${el.binding || 'custom text'}. Enlarge its box or reduce the font.`); continue }
      const align=el.align || d.align,x=align === 'left' ? 0 : align === 'right' ? w : w/2,anchor=align === 'left' ? 'start' : align === 'right' ? 'end' : 'middle'
      const y=(h-fit.lines.length*fit.size*1.15)/2+fit.size*.9
      content=`<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="${font},sans-serif" font-size="${fit.size}" font-weight="${el.bold ? 700 : 400}">${fit.lines.map((line,i) => `<tspan x="${x}" dy="${i ? fit.size*1.15 : 0}">${esc(line)}</tspan>`).join('')}</text>`
    }
    if (stock.shape === 'oval' && ['barcode','qr'].includes(el.type)) {
      if ([[b.x,b.y],[b.x+b.w,b.y],[b.x,b.y+b.h],[b.x+b.w,b.y+b.h]].some(([x,y]) => ((x-stock.w/2)/(stock.w/2))**2+((y-stock.h/2)/(stock.h/2))**2>1)) errors.push('Move the barcode fully inside the oval label.')
    }
    parts.push(`<g data-element="${esc(el.id)}" transform="translate(${round(b.x+b.w/2)} ${round(b.y+b.h/2)}) rotate(${+el.rotation}) translate(${-w/2} ${-h/2})">${content}</g>`)
  }
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${stock.w}mm" height="${stock.h}mm" viewBox="0 0 ${stock.w} ${stock.h}" role="img" aria-label="${esc(row.item_name || 'Label')}"><rect width="100%" height="100%" fill="white"/><g fill="black" shape-rendering="crispEdges">${parts.join('')}</g></svg>`
  return {svg,errors:[...new Set(errors)],warnings:[...new Set(warnings)]}
}
export function validateJob(rows,stock,design,printer) {
  const layout=layoutJob(rows,stock),errors=[...layout.errors],warnings=[]
  const p={...DEFAULT_PRINTER,...printer},g=layout.geometry
  if (![p.offsetX,p.offsetY,p.scaleX,p.scaleY,p.maxWidth].every((v) => Number.isFinite(+v)) || Math.abs(p.offsetX)>50 || Math.abs(p.offsetY)>50 || p.scaleX<90 || p.scaleX>110 || p.scaleY<90 || p.scaleY>110 || p.maxWidth<1 || p.maxWidth>2000) errors.push('Check printer offsets, usable width and correction scales (90–110%).')
  if (!g.sheet && g.usedW>+p.maxWidth) errors.push('The layout exceeds the printer usable width.')
  if (!errors.length) for (const row of rows.filter((r) => +r.qty>0)) {
    const result=labelScene(row,g,design,p)
    errors.push(...result.errors); warnings.push(...result.warnings)
  }
  return {...layout,errors:[...new Set(errors)],warnings:[...new Set(warnings)]}
}
export function pageSvg(slots,stock,design,printer={},guides=false) {
  const p={...DEFAULT_PRINTER,...printer},sx=p.scaleX/100,sy=p.scaleY/100
  const labels=slots.map((slot) => {
    // Nested SVG lengths are already in the parent millimetre coordinate system.
    const svg=labelScene(slot.row,stock,design,p).svg.replace(/width="[^"]+mm" height="[^"]+mm"/,`width="${stock.w}" height="${stock.h}"`)
    const guide=stock.shape === 'oval' ? `<ellipse cx="${stock.w/2}" cy="${stock.h/2}" rx="${stock.w/2}" ry="${stock.h/2}" fill="none" stroke="#9aa7b1" stroke-width="0.12"/>` : `<rect width="${stock.w}" height="${stock.h}" rx="${stock.shape === 'rounded' ? 2 : 0}" fill="none" stroke="#9aa7b1" stroke-width="0.12"/>`
    const ticks=Array.from({length:Math.floor(stock.w/5)},(_,i) => `<path d="M${(i+1)*5} 0v0.7" stroke="#000" stroke-width="0.1"/>`).join('')
    return `<g transform="translate(${slot.x} ${slot.y})">${svg}${guides ? guide+ticks+`<text x="0.5" y="0.9" font-family="Arial" font-size="0.7">${slot.slot+1} / ${stock.w} x ${stock.h} mm</text>` : ''}</g>`
  }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${stock.pageW}mm" height="${stock.pageH}mm" viewBox="0 0 ${stock.pageW} ${stock.pageH}"><rect width="100%" height="100%" fill="white"/><g transform="translate(${+p.offsetX} ${+p.offsetY}) scale(${sx} ${sy})">${labels}</g></svg>`
}
export function documentHtml(svgs,width,height,title='Labels') {
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>@page{size:${width}mm ${height}mm;margin:0}*{box-sizing:border-box}html,body{padding:0;margin:0;background:white}section{width:${width}mm;height:${height}mm;overflow:hidden;break-after:page;page-break-after:always}section:last-child{break-after:auto;page-break-after:auto}svg{display:block}@media screen{body{background:#edf2f3}section{margin:8px auto;box-shadow:0 1px 4px #0002}}</style></head><body>${svgs.map((svg) => `<section>${svg}</section>`).join('')}</body></html>`
}
export function pageHtml(rows,show,size,options={}) {
  const d={...DEFAULT_DESIGN,show},job=layoutJob(rows,size)
  return documentHtml(job.pages.map((page) => pageSvg(page,job.geometry,d)),job.geometry.pageW,job.geometry.pageH,options.title)
}
