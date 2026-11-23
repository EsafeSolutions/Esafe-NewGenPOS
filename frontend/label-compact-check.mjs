import assert from 'node:assert/strict'
import { DEFAULT_STOCK,DEFAULT_PRINTER } from './src/labels/stock.js'
import { DEFAULT_DESIGN,designFor } from './src/labels/design.js'
import { labelScene,elementBox } from './src/labels/render.js'
import { barcodeMetrics,barcodeBox,symbolData } from './src/labels/symbols.js'
const stock={...DEFAULT_STOCK,w:38,h:25}
const row={item_code:'O1D34340021',barcode:'O1D34340021',item_name:'Albertis solution (UPL) 200g',price_text:'LKR 510.00'}
const manual={...designFor('classic'),autoFit:false}
assert.equal(barcodeMetrics(row.barcode,manual,DEFAULT_PRINTER).width,53.625)
assert.ok(labelScene(row,stock,manual).errors.length)
const auto=designFor('classic'),element=auto.elements.find((e)=>e.type==='barcode')
const box=barcodeBox(element,stock,auto,elementBox(element,stock,auto),row.barcode,DEFAULT_PRINTER)
assert.equal(box.x,.5);assert.equal(box.w,37)
const fitted=barcodeMetrics(row.barcode,auto,DEFAULT_PRINTER,box)
assert.equal(fitted.width,35.75);assert.equal(fitted.dots,2);assert.equal(fitted.text,row.barcode)
assert.deepEqual(labelScene(row,stock,auto).errors,[])
for(const format of ['DATAMATRIX','QRCODE']){
  const design={...auto,barcodeFormat:format}
  assert.deepEqual(labelScene(row,stock,design).errors,[],format)
  assert.equal(symbolData(row.barcode,format).text,row.barcode)
}
assert.ok(labelScene(row,stock,{...auto,barcodeFormat:'CODE93'}).errors.length,'Code 93 cannot drop its two mandatory checksums to fit')
assert.deepEqual(labelScene(row,{...stock,w:50},{...auto,barcodeFormat:'CODE93'}).errors,[])
assert.ok(labelScene(row,stock,{...auto,barcodeFormat:'DATAMATRIX'}).warnings.some((m)=>m.includes('2D scanner')))
assert.ok(symbolData('abc-தமிழ்','CODE93').error)
assert.ok(symbolData(row.barcode,'EAN13').error)
assert.ok(symbolData(row.barcode,'UNSUPPORTED').error)
assert.ok(symbolData(' LP1 ','CODE128').error)
assert.equal(symbolData(' LP1 ','DATAMATRIX').text,' LP1 ')
for(const value of ['01D34340021','000012345678901234567890','A'.repeat(70)]){
  for(const format of ['DATAMATRIX','QRCODE'])assert.equal(symbolData(value,format).text,value)
}
const small={...stock,w:8,h:8}
assert.ok(labelScene(row,small,{...auto,barcodeFormat:'QRCODE',padding:.5}).errors.length)
const ean=barcodeMetrics('4006381333931',auto,DEFAULT_PRINTER,{w:35.6,h:12})
assert.equal(ean.format,'EAN13');assert.ok(ean.module>=.264);assert.equal(ean.dots,3);assert.equal(ean.fits,false)
for(const dpi of [203,203.2,300,600])for(const format of ['CODE128','CODE93','DATAMATRIX','QRCODE']){
  const m=barcodeMetrics(row.barcode,{...auto,barcodeFormat:format},{...DEFAULT_PRINTER,dpi},{w:37,h:10.848})
  assert.ok(Number.isInteger(m.dots));assert.ok(m.dots>=2);assert.ok(m.module>=.19)
}
assert.equal(DEFAULT_DESIGN.autoFit,true)
console.log('PASS screenshot reproduction, 53.625→35.75 mm Code 128 fitting, unchanged values, compact formats, scanner warnings, DPI and retail limits')
