import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ItemsView from './src/views/ItemsView.vue'
import { useSessionStore } from './src/stores/session'
import './src/styles.css'
const pinia = createPinia()
const session = useSessionStore(pinia)
session.posProfile = 'Main till'
session.permissions = { edit_items: true }
session.notify = (message) => { document.getElementById('status').textContent = message }
let quantity = 24
let created = false
const options = { can_create_items: true, can_view_stock: true, can_adjust_stock: true, item_groups: ['Home & Living'], brands: ['Esafe'], stock_uoms: ['Nos'], price_lists: [] }
const product = { name: 'FLOWER-01', item_name: 'Roses flower', stock_uom: 'Nos', item_group: 'Home & Living' }
window.fetch = async (url, init) => {
  const method = String(url).split('.').pop()
  const args = JSON.parse(init?.body || '{}')
  let message = []
  if (method === 'editor_options') message = options
  if (method === 'search_items') message = created ? [product, { ...product, name: 'NEW-01', item_name: 'New ceramic plate' }] : [product]
  if (method === 'item_details') message = { ...product, item_code: args.item_code, item_name: args.item_code === 'NEW-01' ? 'New ceramic plate' : product.item_name, can_edit_item: true, units: [], can_edit_prices: false }
  if (method === 'warehouse_stock') message = { stock_uom: 'Nos', can_adjust: true, rows: [{ warehouse: 'Finished Goods - Shop', actual_qty: quantity, reserved_qty: 3, available_qty: quantity - 3 }, { warehouse: 'Main Stores - Shop', actual_qty: 0, reserved_qty: 0, available_qty: 0 }] }
  if (method === 'adjust_stock') { quantity = Number(args.qty); message = { name: 'REC-TEST-1' } }
  if (method === 'create_item') { created = true; message = { item_code: 'NEW-01' } }
  return { ok: true, json: async () => ({ message }) }
}
const status = document.createElement('p'); status.id = 'status'; status.setAttribute('role', 'status'); document.body.append(status)
document.body.style.cssText = 'margin:0; overflow:auto;'
createApp(ItemsView).use(pinia).mount('#app')
