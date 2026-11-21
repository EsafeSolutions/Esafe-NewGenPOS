// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
export const MAX_LABELS = 10000
const sizes = [[50,25],[40,30],[58,40],[38,25],[20,10],[22,12],[25,15],[30,15],[30,20],[32,25],[35,25],[40,20],[40,25],[45,30],[50,30],[50,40],[50,50],[58,30],[60,30],[60,40],[70,30],[70,40],[80,40],[80,50],[100,50],[100,75],[100,100],[100,150]]
export const PRESETS = [
  ...sizes.map(([w,h]) => ({ key: `${w}x${h}`, label: `${w} × ${h} mm`, w, h })),
  ...[[1,.5],[1.25,1],[2,1],[2,1.25],[2,2],[4,2],[4,6]].map(([w,h]) => ({ key: `in-${w}x${h}`, label: `${w} × ${h} in`, w: w*25.4, h: h*25.4 })),
  { key: 'a4-3x8', label: 'A4 sheet, 3 × 8', kind: 'sheet', w: 70, h: 37, columns: 3, rows: 8, pageW: 210, pageH: 297, top: .5 },
  { key: 'a4-4x10', label: 'A4 sheet, 4 × 10', kind: 'sheet', w: 52.5, h: 29.7, columns: 4, rows: 10, pageW: 210, pageH: 297 },
  { key: 'custom', label: 'Custom size', w: 50, h: 30, custom: true },
]
export const PAPERS = [{ key:'a4',label:'A4',w:210,h:297 },{ key:'a5',label:'A5',w:148,h:210 },{ key:'letter',label:'Letter',w:215.9,h:279.4 },{ key:'legal',label:'Legal',w:215.9,h:355.6 }]
export const DEFAULT_STOCK = { kind:'roll',w:58,h:40,columns:1,rows:1,gapX:2,gapY:3,left:0,right:0,top:0,bottom:0,pageW:58,pageH:40,autoWidth:true,feedMode:'driver',shape:'rectangle',order:'row',start:0,skip:'',units:'mm' }
export const DEFAULT_PRINTER = { route:'browser',name:'',dpi:203.2,maxWidth:108,offsetX:0,offsetY:0,scaleX:100,scaleY:100,monochrome:true }
export const clone = (value) => JSON.parse(JSON.stringify(value))
export const round = (value) => Math.round(value*10000)/10000
export const mm = (value, units='mm') => round(Number(value)*(units === 'in' ? 25.4 : 1))
export const displayUnit = (value, units='mm') => round(Number(value)/(units === 'in' ? 25.4 : 1))
export function stockForPreset(key, previous=DEFAULT_STOCK) {
  const p = PRESETS.find((p) => p.key === key)
  if (!p || p.custom) return {...clone(previous)}
  return {...clone(previous),...p,kind:p.kind || previous.kind,start:0,skip:'',...(p.kind === 'sheet' ? {gapX:0,gapY:0,left:0,right:0,top:p.top || 0,bottom:0,autoWidth:false} : {})}
}
export function sizeOf(key, custom={}) { return {...stockForPreset(key),...custom} }
export function migrateOptions(saved={}) {
  if (saved.version === 2) return saved
  return {version:2,stock:stockForPreset(saved.size || '58x40',{...DEFAULT_STOCK,...(saved.size === 'custom' ? {w:saved.w || 50,h:saved.h || 30} : {})}),design:{show:saved.show || {}}}
}
export function geometry(stock) {
  const s = {...DEFAULT_STOCK,...stock}, errors = []
  const positive = ['w','h','columns','rows','pageW','pageH']
  for (const k of positive) if (!Number.isFinite(+s[k]) || +s[k] <= 0 || +s[k] > (k === 'columns' || k === 'rows' ? 100 : 2000)) errors.push('Dimensions and row/column counts must be positive and within supported limits.')
  for (const k of ['gapX','gapY','left','right','top','bottom']) if (!Number.isFinite(+s[k]) || +s[k] < 0 || +s[k] > 500) errors.push('Gaps and margins must be between 0 and 500 mm.')
  if (![s.columns,s.rows].every((v) => Number.isInteger(+v))) errors.push('Rows and columns must be whole numbers.')
  if (!['roll','sheet','continuous','black-mark'].includes(s.kind)) errors.push('Choose a supported stock format.')
  if (!['driver','pitch'].includes(s.feedMode)) errors.push('Choose how the printer handles the feed gap.')
  if (errors.length) return {errors:[...new Set(errors)],capacity:0}
  for (const k of [...positive,'gapX','gapY','left','right','top','bottom']) s[k] = +s[k]
  const usedW = s.left+s.columns*s.w+(s.columns-1)*s.gapX+s.right
  const usedH = s.top+s.rows*s.h+(s.rows-1)*s.gapY+s.bottom
  const sheet = s.kind === 'sheet', pageW = sheet || !s.autoWidth ? s.pageW : usedW
  // Gap-sensing drivers normally advance the feed gap themselves.
  const pageH = sheet ? s.pageH : s.h+(s.feedMode === 'pitch' ? s.gapY : 0)
  if (usedW > pageW+.0001) errors.push('Labels and horizontal gaps exceed the page or liner width.')
  if (sheet && usedH > pageH+.0001) errors.push('Labels and vertical gaps exceed the sheet height.')
  if (!Number.isInteger(+s.start) || +s.start < 0 || +s.start >= (sheet ? s.columns*s.rows : s.columns)) errors.push('Starting slot must be inside the first page or roll row.')
  if (s.skip instanceof Set) s.skip=[...s.skip].map((n) => n+1).join(',')
  const skip = new Set()
  if (String(s.skip || '').length > 10000) errors.push('The skipped-slot list is too long.')
  else for (const token of String(s.skip || '').split(/[,\s]+/).filter(Boolean)) {
    const match = token.match(/^(\d+)(?:-(\d+))?$/)
    const a = match ? +match[1] : 0, b = match ? +(match[2] || match[1]) : 0
    if (!a || b < a || b > MAX_LABELS) { errors.push('Skipped slots must be numbers or ranges, for example 1, 3-5.'); continue }
    for (let i=a;i<=b;i++) skip.add(i-1)
  }
  return {...s,pageW:round(pageW),pageH:round(pageH),usedW:round(usedW),usedH:round(usedH),capacity:sheet ? s.columns*s.rows : s.columns,sheet,skip,errors:[...new Set(errors)]}
}
export function layoutJob(rows, stock) {
  const g = geometry(stock), errors = [...g.errors]
  let total = 0
  for (const r of rows) {
    if (!Number.isInteger(+r.qty) || +r.qty < 0 || +r.qty > MAX_LABELS) errors.push('Copies must be whole numbers from 0 to 10,000.')
    else total += +r.qty
  }
  if (total > MAX_LABELS) errors.push('Print at most 10,000 labels per job.')
  if (errors.length) return {geometry:g,errors:[...new Set(errors)],pages:[],total,blanks:0}
  const pages = [], capacity = g.capacity
  let position = +g.start
  for (const row of rows) for (let copy=0;copy<+row.qty;copy++) {
    while (g.skip.has(position)) position++
    if (position >= MAX_LABELS*2) return {geometry:g,errors:['Too many empty slots before the labels.'],pages:[],total,blanks:0}
    const pageIndex = Math.floor(position/capacity), slot = position%capacity
    while (pages.length<=pageIndex) pages.push([])
    const col = g.sheet && g.order === 'column' ? Math.floor(slot/g.rows) : slot%g.columns
    const rowIndex = g.sheet ? (g.order === 'column' ? slot%g.rows : Math.floor(slot/g.columns)) : 0
    pages[pageIndex].push({row,copy,slot,index:position,x:round(g.left+col*(g.w+g.gapX)),y:round((g.sheet ? g.top : 0)+rowIndex*(g.h+g.gapY))})
    position++
  }
  return {geometry:g,errors:[],pages,total,blanks:pages.length*capacity-total,length:g.sheet ? 0 : round(pages.length*(g.h+g.gapY))}
}
export function calibrationKey(stock, printer) {
  const {units,key,label,custom,...physical} = stock
  delete physical.start; delete physical.skip; delete physical.order
  return JSON.stringify([physical,printer.name,printer.route,printer.dpi])
}
