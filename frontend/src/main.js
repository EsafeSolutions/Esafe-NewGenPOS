// Copyright (c) 2026 Esafe (PVT) LTD
// SPDX-License-Identifier: AGPL-3.0-only
// "EsafePOS" is a trademark of Esafe (PVT) LTD. See TRADEMARKS.md.
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'

import './theme' // applies saved/OS theme before first paint
import { ready } from './i18n' // applies saved/browser language + RTL direction before first paint
import App from './App.vue'
import SellView from './views/SellView.vue'
import HistoryView from './views/HistoryView.vue'
import CustomersView from './views/CustomersView.vue'
import MessagesView from './views/MessagesView.vue'
import HoldsView from './views/HoldsView.vue'
import RegisterView from './views/RegisterView.vue'
import InsightsView from './views/InsightsView.vue'
import SettingsView from './views/SettingsView.vue'
import PrintingView from './views/PrintingView.vue'
import StockManagerView from './views/StockManagerView.vue'
import InvoicesView from './views/InvoicesView.vue'
import BuyingView from './views/BuyingView.vue'
import CustomerDisplayView from './views/CustomerDisplayView.vue'
import './styles.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', component: SellView },
    { path: '/history', component: HistoryView },
    { path: '/customers', component: CustomersView },
    { path: '/messages', component: MessagesView },
    { path: '/invoices', component: InvoicesView },
    { path: '/buying', component: BuyingView },
    { path: '/holds', component: HoldsView },
    { path: '/register', component: RegisterView },
    { path: '/insights', component: InsightsView },
    { path: '/settings', component: SettingsView },
    { path: '/printing', component: PrintingView },
    { path: '/labels', redirect: { path: '/printing', query: { section: 'labels' } } },
    { path: '/items', component: StockManagerView },
    { path: '/count', redirect: to => ({ path: '/items', query: { ...to.query, section: 'count' } }) },
    // Second-screen customer-facing display, chrome-free, no bootstrap.
    { path: '/display', component: CustomerDisplayView },
  ],
})

// A language outside the main bundle is fetched first, so the first screen is
// already in it (English and Arabic resolve at once).
ready.finally(() => createApp(App).use(createPinia()).use(router).mount('#app'))
