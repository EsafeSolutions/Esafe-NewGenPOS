<!-- Copyright (c) 2026 Esafe (PVT) LTD. SPDX-License-Identifier: AGPL-3.0-only -->
<template>
  <section class="hr-workspace" :aria-label="t('Human resources')">
    <header class="hr-heading">
      <div><h1>{{ t('Human resources') }}</h1><p class="muted">{{ t('Attendance, employee expenses and approved payroll earnings.') }}</p></div>
      <div class="hr-heading-actions"><span>{{ session.company }}<small>{{ context.currency || session.currency }}</small></span><button class="btn btn-outline" :disabled="locked" @click="refresh">{{ t('Refresh') }}</button></div>
    </header>
    <p v-if="!allowed" class="hr-notice" role="alert">{{ t('HR is disabled or your account does not have HR access. Ask an administrator to review Modules & Features and your HR permissions.') }}</p>
    <template v-else>
      <p v-if="session.offline" class="hr-notice hr-error" role="alert">{{ t('Connect to the server to use HR. Attendance, claims and payroll cannot be queued offline.') }}</p>
      <p v-if="error" class="hr-notice hr-error" role="alert">{{ error }}</p>
      <p v-if="success" class="hr-notice" role="status">{{ success }}</p>
      <p v-if="loading" class="hr-notice" role="status">{{ t('Loading HR configuration…') }}</p>
      <template v-if="ready">
        <nav class="hr-tabs" :aria-label="t('HR sections')">
          <button v-for="item in tabs" :key="item.key" type="button" :aria-pressed="tab === item.key" :class="{ active: tab === item.key }" :disabled="busy" @click="selectTab(item.key)">{{ t(item.label) }}</button>
        </nav>
        <div v-if="tab !== 'overview'" class="hr-filters">
          <label>{{ t('Employee') }}<select :aria-label="t('Employee')" v-model="employee" :disabled="locked" @change="selectionChanged"><option value="">{{ t('Select employee') }}</option><option v-for="person in context.employees" :key="person.name" :value="person.name">{{ person.employee_name }} ({{ person.name }})</option></select></label>
          <label v-if="tab !== 'claims'">{{ t('Month') }}<input v-model="month" type="month" required :disabled="locked" @change="selectionChanged" /></label>
          <span class="muted hr-refreshed">{{ t('Refreshed') }} {{ context.refreshed_at }}</span>
        </div>
        <div v-if="tab === 'overview'" class="hr-overview">
          <article class="card hr-panel hr-intro"><Icon name="person" :size="28" /><h2>{{ t('Your HR workspace') }}</h2><p>{{ t('Choose an employee to review attendance, record an expense or prepare monthly earnings. Frappe HR controls document validation, approvals and salary processing.') }}</p><p v-if="!context.schema_ready" class="hr-error">{{ t('Run bench migrate to enable safe attendance and expense recording.') }}</p><div class="hr-links"><a href="/app/employee" target="_blank" rel="noopener">{{ t('Employees in Frappe HR') }}</a><a v-if="context.can_payroll" href="/app/payroll-entry" target="_blank" rel="noopener">{{ t('Payroll entries') }}</a><a v-if="context.can_payroll" href="/app/salary-slip" target="_blank" rel="noopener">{{ t('Salary slips') }}</a></div></article>
          <article class="card hr-panel"><h2>{{ t('Configuration') }}</h2><dl class="hr-configuration"><div v-for="[key, label] in featureLabels" :key="key"><dt>{{ t(label) }}</dt><dd>{{ context.features[key] ? t('On') : t('Off') }}</dd></div></dl><p class="muted">{{ t('Each feature is enabled separately in Settings → Features.') }}</p><div class="hr-versions"><span v-for="(version, app) in context.versions" :key="app">{{ app }} {{ version }}</span></div></article>
        </div>
        <template v-else-if="tab === 'attendance'">
          <p v-if="!employee" class="hr-empty">{{ t('Select an employee to review attendance.') }}</p>
          <div v-else class="hr-content-grid">
            <article class="card hr-panel"><div class="hr-section-heading"><h2>{{ t('Attendance records') }}</h2><a :href="nativeList('attendance')" target="_blank" rel="noopener">{{ t('Open Frappe HR') }}</a></div><div class="hr-table-wrap"><table><thead><tr><th>{{ t('Date') }}</th><th>{{ t('Status') }}</th><th>{{ t('Document') }}</th></tr></thead><tbody><tr v-for="row in attendance" :key="row.name"><td>{{ row.attendance_date }}</td><td>{{ t(row.status) }} <small v-if="row.docstatus !== 1">({{ row.docstatus === 2 ? t('Cancelled') : t('Draft') }})</small></td><td><a :href="nativeDoc('Attendance', row.name)" target="_blank" rel="noopener">{{ row.name }}</a></td></tr></tbody></table></div><p v-if="!attendance.length" class="hr-empty">{{ t('No attendance recorded for this month.') }}</p></article>
            <form v-if="context.can_attendance" class="card hr-panel" @submit.prevent="recordAttendance"><fieldset :disabled="locked || !context.schema_ready"><h2>{{ t('Record attendance exception') }}</h2><p class="muted">{{ t('This creates submitted attendance. Review existing entries, leave and shift conflicts in Frappe HR.') }}</p><label>{{ t('Attendance date') }}<input v-model="attendanceForm.date" type="date" :max="context.today" required /></label><label>{{ t('Attendance status') }}<select v-model="attendanceForm.status"><option v-for="status in ['Present', 'Absent', 'Half Day', 'Work From Home']" :key="status">{{ status }}</option></select></label><label>{{ t('Reason') }}<textarea v-model="attendanceForm.reason" required maxlength="1000" rows="3"></textarea></label><button type="submit" class="btn btn-primary">{{ t('Record attendance') }}</button></fieldset></form>
          </div>
        </template>
        <template v-else-if="tab === 'claims'">
          <p v-if="!employee" class="hr-empty">{{ t('Select an employee to review expense claims.') }}</p>
          <div v-else class="hr-content-grid">
            <article class="card hr-panel"><div class="hr-section-heading"><h2>{{ t('Expense claims') }}</h2><a :href="nativeList('expense-claim')" target="_blank" rel="noopener">{{ t('Open Frappe HR') }}</a></div><div class="hr-table-wrap"><table><thead><tr><th>{{ t('Claim') }}</th><th>{{ t('Approval') }}</th><th>{{ t('Claimed') }}</th><th>{{ t('Reimbursed') }}</th></tr></thead><tbody><tr v-for="row in claims" :key="row.name"><td><a :href="nativeDoc('Expense Claim', row.name)" target="_blank" rel="noopener">{{ row.name }}</a><small>{{ row.posting_date }}</small></td><td>{{ t(row.approval_status) }}<small>{{ t(row.status) }}</small></td><td>{{ money(row.total_claimed_amount, context.currency) }}</td><td>{{ money(row.total_amount_reimbursed, context.currency) }}</td></tr></tbody></table></div><p v-if="!claims.length" class="hr-empty">{{ t('No expense claims yet. Record an employee-paid business expense to begin.') }}</p><p class="muted">{{ t('Showing the latest 100 claims. Use Frappe HR for the complete history.') }}</p></article>
            <form v-if="context.permissions['Expense Claim']?.create" class="card hr-panel" @submit.prevent="recordClaim"><fieldset :disabled="locked || !context.schema_ready"><h2>{{ t('New expense claim') }}</h2><p class="muted">{{ t('Save a draft, then attach receipts and submit it in Frappe HR. Approval and reimbursement stay separate from salary.') }}</p><label>{{ t('Expense date') }}<input v-model="claimForm.date" type="date" :max="context.today" required /></label><label>{{ t('Expense type') }}<select :aria-label="t('Expense type')" v-model="claimForm.type" required><option value="">{{ t('Select expense type') }}</option><option v-for="type in context.expense_types" :key="type">{{ type }}</option></select></label><label>{{ t('Amount') }} ({{ context.currency }})<input v-model.number="claimForm.amount" type="number" min="0.000001" step="any" required /></label><label>{{ t('Description') }}<textarea v-model="claimForm.description" maxlength="2000" rows="3" required></textarea></label><button type="submit" class="btn btn-primary">{{ t('Save claim draft') }}</button><a v-if="createdClaim" :href="nativeDoc('Expense Claim', createdClaim)" target="_blank" rel="noopener">{{ t('Attach receipts and submit claim') }} · {{ createdClaim }}</a></fieldset></form>
          </div>
        </template>
        <template v-else-if="tab === 'salary'">
          <article class="card hr-panel"><div class="hr-section-heading"><h2>{{ t('Frappe HR salary calculation') }}</h2><a href="/app/payroll-settings" target="_blank" rel="noopener">{{ t('Payroll Settings') }}</a></div><p>{{ t('Uses your existing Salary Structure, assignment, Payroll Settings, attendance, holidays, leave, component formulas and deductions. Change payroll rules in Frappe HR.') }}</p><dl class="hr-configuration"><div v-for="(value, key) in context.payroll_settings" :key="key"><dt>{{ t(payrollSettingLabels[key] || key) }}</dt><dd>{{ value }}</dd></div></dl><div class="hr-links"><a href="/app/salary-structure-assignment" target="_blank" rel="noopener">{{ t('Salary structure assignments') }}</a><a href="/app/payroll-entry" target="_blank" rel="noopener">{{ t('Process payroll') }}</a></div><button class="btn btn-primary" :disabled="locked || !employee || !month || !context.permissions['Salary Slip']?.create" @click="previewSalary">{{ t('Preview native salary') }}</button></article>
          <article v-if="salaryPreview" class="card hr-panel"><div class="hr-section-heading"><div><h2>{{ t('Native Salary Slip preview') }}</h2><p>{{ salaryPreview.employee_name }} · {{ salaryPreview.start_date }} – {{ salaryPreview.end_date }}</p><p>{{ salaryPreview.salary_structure }}</p></div><strong class="hr-total">{{ money(salaryPreview.net_pay, salaryPreview.currency) }}</strong></div><p>{{ t('Payment days') }}: <b>{{ salaryPreview.payment_days }}</b> / {{ salaryPreview.total_working_days }}</p><p>{{ t('Gross pay') }}: {{ money(salaryPreview.gross_pay, salaryPreview.currency) }} · {{ t('Deductions') }}: {{ money(salaryPreview.total_deduction, salaryPreview.currency) }}</p><div class="hr-table-wrap"><table><thead><tr><th>{{ t('Salary component') }}</th><th>{{ t('Type') }}</th><th>{{ t('Amount') }}</th></tr></thead><tbody><template v-for="table in ['earnings', 'deductions']" :key="table"><tr v-for="row in salaryPreview[table]" :key="row.salary_component"><td>{{ row.salary_component }}</td><td>{{ t(table === 'earnings' ? 'Earning' : 'Deduction') }}</td><td>{{ money(row.amount, salaryPreview.currency) }}</td></tr></template></tbody></table></div><p class="hr-notice">{{ t('Preview does not save or submit payroll. Save a native draft, then review, approve, submit and pay it in Frappe HR. The native rules calculate the final amounts.') }}</p><button class="btn btn-primary" :disabled="locked || !context.schema_ready" @click="saveSalaryDraft">{{ t('Save native Salary Slip draft') }}</button></article>
          <article class="card hr-panel"><h2>{{ t('Salary Slips for this month') }}</h2><p v-if="!salarySlips.length" class="hr-empty">{{ t('No Salary Slips found for this employee and month.') }}</p><div v-for="slip in salarySlips" :key="slip.name" class="hr-batch"><a :href="nativeDoc('Salary Slip', slip.name)" target="_blank" rel="noopener">{{ slip.name }}</a><span>{{ t(slip.docstatus === 0 ? 'Draft' : slip.docstatus === 1 ? 'Submitted' : 'Cancelled') }}</span><strong>{{ money(slip.net_pay, slip.currency) }}</strong></div></article>
        </template>
        <template v-else-if="tab === 'payroll'">
          <div class="hr-payroll-toolbar"><label>{{ t('Commission component') }}<select :aria-label="t('Commission component')" v-model="component" :disabled="locked" @change="selectionChanged"><option value="">{{ t('Select native earning component') }}</option><option v-for="item in context.components" :key="item">{{ item }}</option></select></label><button class="btn btn-primary" :disabled="locked || !employee || !month || !component" @click="previewPayroll">{{ t('Preview earnings') }}</button><a href="/app/sales-person" target="_blank" rel="noopener">{{ t('Salesperson employee links') }}</a></div>
          <p class="muted">{{ t('Prepare a completed calendar month. Review the sources, save the period, approve it, then post its earning to payroll. Each employee, month and earning type can be posted once.') }}</p>
          <article v-if="preview" class="card hr-panel"><div class="hr-section-heading"><div><h2>{{ t('Earnings preview') }}</h2><p>{{ preview.employee_name }} · {{ preview.month }} · {{ t(preview.kind) }}</p></div><strong class="hr-total">{{ money(preview.amount, preview.currency) }}</strong></div><p v-if="preview.payable_days !== undefined">{{ t('Payable days') }}: <b>{{ preview.payable_days }}</b></p><p class="hr-notice">{{ t(preview.warning) }}</p><div class="hr-table-wrap"><table><thead><tr><th>{{ t('Source document') }}</th><th>{{ t('Date / salesperson') }}</th><th>{{ t('Days / allocation') }}</th><th>{{ t('Earning') }}</th></tr></thead><tbody><tr v-for="(row, index) in preview.sources" :key="index"><td><a :href="nativeDoc(row.doctype || 'Attendance', row.name)" target="_blank" rel="noopener">{{ row.name }}</a></td><td>{{ row.attendance_date || row.sales_person }}</td><td>{{ row.payable_days ?? `${row.allocated_percentage}%` }}</td><td>{{ money(row.amount ?? row.incentives, preview.currency) }}</td></tr></tbody></table></div><button class="btn btn-primary" :disabled="locked || preview.amount <= 0" @click="preparePayroll">{{ t('Save payroll period') }}</button></article>
          <article class="card hr-panel"><h2>{{ t('Payroll periods') }}</h2><p v-if="!batches.length" class="hr-empty">{{ t('No prepared earnings for this employee and month.') }}</p><div v-for="batch in batches" :key="batch.name" class="hr-batch"><div><strong>{{ t(batch.kind) }} · {{ money(batch.amount, batch.currency) }}</strong><p>{{ t(batch.status) }}<span v-if="batch.approved_by"> · {{ batch.approved_by }}</span></p><a :href="nativeDoc('EsafePOS HR Payroll Batch', batch.name)" target="_blank" rel="noopener">{{ t('Review source snapshot') }}</a><a v-if="batch.additional_salary" :href="nativeDoc('Additional Salary', batch.additional_salary)" target="_blank" rel="noopener">{{ batch.additional_salary }}</a></div><div v-if="context.can_approve" class="hr-batch-actions"><button v-if="batch.status === 'Draft'" type="button" class="btn btn-outline" :disabled="locked || !context.permissions['Additional Salary']?.submit" @click="batchAction('approve_payroll', batch)">{{ t('Approve period') }}</button><button v-if="batch.status === 'Approved'" type="button" class="btn btn-outline" :disabled="locked" @click="batchAction('reopen_payroll', batch)">{{ t('Reopen for review') }}</button><button v-if="batch.status === 'Approved'" type="button" class="btn btn-primary" :disabled="locked || !context.permissions['Additional Salary']?.create || !context.permissions['Additional Salary']?.submit" @click="batchAction('post_payroll', batch)">{{ t('Post to payroll') }}</button></div></div><p class="muted">{{ t('Posting creates a submitted Additional Salary earning. Process Salary Slips and payment in Frappe HR. Posted periods remain locked after cancellation; use native payroll adjustments.') }}</p></article>
        </template>
      </template>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { call } from '../api'
import { t } from '../i18n'
import { money } from '../format'
import Icon from '../components/Icon.vue'

const session = useSessionStore()
const context = ref({}), loading = ref(false), ready = ref(false), busy = ref(false), error = ref(''), success = ref('')
const tab = ref('overview'), employee = ref(''), month = ref(''), kind = ref('Commission'), component = ref('')
const attendance = ref([]), claims = ref([]), batches = ref([]), preview = ref(null), createdClaim = ref('')
const attendanceForm = ref({ date: '', status: 'Present', reason: '' }), claimForm = ref({ date: '', type: '', amount: '', description: '' })
const attendanceKey = ref(''), claimKey = ref(''), salaryKey = ref('')
const salaryPreview = ref(null), salarySlips = ref([])
const payrollSettingLabels = { payroll_based_on: 'Working days based on', daily_wages_fraction_for_half_day: 'Native half-day fraction', include_holidays_in_total_working_days: 'Include holidays in working days', consider_unmarked_attendance_as: 'Unmarked attendance' }
const allowed = computed(() => Boolean(session.settings.enable_hr_integration && session.permissions.hr))
const locked = computed(() => busy.value || loading.value || session.offline)
const featureLabels = [['enable_attendance', 'Attendance'], ['enable_expense_claims', 'Expense claims'], ['enable_day_salary', 'Daily salary'], ['enable_sales_commissions', 'Salesperson commissions'], ['enable_commission_payroll', 'Commission payroll payout']]
const tabs = computed(() => [{ key: 'overview', label: 'Overview' },
  ...(context.value.features?.enable_attendance && context.value.permissions?.Attendance?.read ? [{ key: 'attendance', label: 'Attendance' }] : []),
  ...(context.value.features?.enable_expense_claims && context.value.permissions?.['Expense Claim']?.read ? [{ key: 'claims', label: 'Expense claims' }] : []),
  ...(context.value.can_payroll && context.value.features?.enable_day_salary && context.value.permissions?.['Salary Slip']?.read ? [{ key: 'salary', label: 'Daily salary' }] : []),
  ...(context.value.can_payroll && context.value.features?.enable_commission_payroll ? [{ key: 'payroll', label: 'Commission payroll' }] : [])])
const nativeDoc = (doctype, name) => `/app/${doctype.toLowerCase().replaceAll(' ', '-')}/${encodeURIComponent(name)}`
const nativeList = doctype => `/app/${doctype}?employee=${encodeURIComponent(employee.value)}&company=${encodeURIComponent(session.company)}`
async function api(method, args = {}) {
  const company = session.company
  const result = await call(`esafepos.api.hr.${method}`, { company, ...args }, { timeout: /payroll|salary/.test(method) ? 60000 : 20000 })
  if (company !== session.company) throw new Error(t('Company changed. Refresh the HR workspace.'))
  return result
}
const identity = () => crypto.randomUUID()
async function run(action) {
  if (locked.value) return
  const company = session.company
  busy.value = true; error.value = ''; success.value = ''
  try { await action() } catch (e) { error.value = e.message } finally { busy.value = false; if (company !== session.company) refresh() }
}
async function refresh() {
  if (!allowed.value || locked.value) return
  const company = session.company
  loading.value = true; error.value = ''; preview.value = null; salaryPreview.value = null
  try {
    context.value = await api('get_context'); ready.value = true; if (!context.value.components.includes(component.value)) component.value = context.value.components[0] || ''
    if (!context.value.employees.some(row => row.name === employee.value)) employee.value = context.value.employees[0]?.name || ''
    if (!month.value) month.value = context.value.today.slice(0, 7)
    attendanceForm.value.date ||= context.value.today; claimForm.value.date ||= context.value.today
    if (!tabs.value.some(item => item.key === tab.value)) tab.value = 'overview'
    await loadSection()
  } catch (e) { error.value = e.message; ready.value = false } finally { loading.value = false; if (company !== session.company) refresh() }
}
async function loadSection() {
  attendance.value = []; claims.value = []; batches.value = []; salarySlips.value = []
  if (!employee.value) return
  const args = { employee: employee.value, month: month.value }
  if (tab.value === 'attendance') attendance.value = await api('list_attendance', args)
  if (tab.value === 'claims') claims.value = await api('list_claims', { employee: employee.value })
  if (tab.value === 'payroll') batches.value = await api('list_payroll', args)
  if (tab.value === 'salary') salarySlips.value = await api('list_salary_slips', args)
}
function selectTab(value) { if (locked.value) return; tab.value = value; preview.value = null; salaryPreview.value = null; run(loadSection) }
function selectionChanged() { preview.value = null; salaryPreview.value = null; createdClaim.value = ''; run(loadSection) }
function recordAttendance() {
  run(async () => {
    attendanceKey.value ||= identity()
    const doc = await api('mark_attendance', { employee: employee.value, attendance_date: attendanceForm.value.date,
      status: attendanceForm.value.status, reason: attendanceForm.value.reason, request_id: attendanceKey.value })
    attendanceKey.value = ''; success.value = `${t('Attendance recorded')}: ${doc.name}`; await loadSection()
  })
}
function recordClaim() {
  run(async () => {
    claimKey.value ||= identity()
    const doc = await api('create_claim', { employee: employee.value, expense_date: claimForm.value.date, expense_type: claimForm.value.type,
      amount: claimForm.value.amount, description: claimForm.value.description, request_id: claimKey.value })
    claimKey.value = ''; createdClaim.value = doc.name; success.value = `${t('Claim draft saved. Open it to attach receipts and submit.')}: ${doc.name}`
    claimForm.value.amount = ''; claimForm.value.description = ''; await loadSection()
  })
}
function previewPayroll() { run(async () => { preview.value = null; preview.value = await api('preview_payroll', { employee: employee.value, month: month.value, kind: kind.value, component: component.value }) }) }
function preparePayroll() { run(async () => { await api('prepare_payroll', { employee: employee.value, month: month.value, kind: kind.value, component: component.value, fingerprint: preview.value.fingerprint }); success.value = t('Payroll period saved for approval.'); await loadSection() }) }
function batchAction(action, batch) { run(async () => { await api(action, { name: batch.name }); success.value = t(action === 'post_payroll' ? 'Earning posted to Frappe HR payroll.' : action === 'approve_payroll' ? 'Payroll period approved.' : 'Payroll period reopened for review.'); await loadSection() }) }
function previewSalary() { run(async () => { salaryPreview.value = null; salaryPreview.value = await api('preview_salary', { employee: employee.value, month: month.value }) }) }
function saveSalaryDraft() { run(async () => { salaryKey.value ||= identity(); const doc = await api('save_salary_draft', { employee: employee.value, month: month.value, fingerprint: salaryPreview.value.fingerprint, request_id: salaryKey.value }); salaryKey.value = ''; salaryPreview.value = null; success.value = `${t('Native Salary Slip draft saved. Review and submit in Frappe HR.')}: ${doc.name}`; await loadSection() }) }
watch(() => [session.company, allowed.value], () => { ready.value = false; context.value = {}; employee.value = ''; preview.value = null; salaryPreview.value = null; refresh() })
onMounted(refresh)
</script>

<style scoped>
.hr-workspace { flex: 1; min-width: 0; overflow: auto; padding: 24px; display: flex; flex-direction: column; gap: 18px; }
.hr-heading, .hr-heading-actions, .hr-section-heading, .hr-batch, .hr-batch-actions, .hr-payroll-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.hr-heading h1 { font-size: 25px; margin: 0 0 6px; }
.hr-heading p, .hr-section-heading p { margin: 0; }
.hr-heading-actions > span { text-align: end; font-weight: 600; }
.hr-heading-actions small, td small { display: block; color: var(--text-muted); font-size: 12px; margin-top: 4px; }
.hr-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border); padding-bottom: 8px; flex-wrap: wrap; }
.hr-tabs button { border: 1px solid transparent; border-radius: 8px; padding: 10px 16px; min-height: 44px; background: transparent; color: var(--text-muted); font: inherit; cursor: pointer; }
.hr-tabs button.active, .hr-tabs button:hover { background: var(--surface-2); border-color: var(--border); color: var(--text); }
.hr-tabs button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.hr-filters { display: grid; grid-template-columns: minmax(220px, 2fr) minmax(150px, 1fr) 1fr; gap: 16px; align-items: end; }
.hr-refreshed { font-size: 12px; padding-bottom: 10px; text-align: end; }
.hr-overview, .hr-content-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr); gap: 20px; align-items: start; }
.hr-panel { padding: 22px; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.hr-panel h2 { font-size: 18px; margin: 0; }
.hr-panel h3 { font-size: 15px; margin: 0; }
.hr-panel p { margin: 0; line-height: 1.6; }
.hr-panel a, .hr-payroll-toolbar a { color: var(--brand-dark); text-underline-offset: 3px; overflow-wrap: anywhere; }
.hr-links { display: flex; flex-wrap: wrap; gap: 14px; }
.hr-intro > svg { color: var(--brand-dark); }
.hr-configuration { margin: 0; }
.hr-configuration > div { display: flex; gap: 15px; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); }
.hr-configuration dd { margin: 0; font-weight: 700; }
.hr-versions { display: flex; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--text-muted); }
.hr-workspace label { display: flex; flex-direction: column; gap: 7px; font-size: 13px; font-weight: 600; min-width: 0; }
.hr-workspace input, .hr-workspace select, .hr-workspace textarea { min-width: 0; width: 100%; }
.hr-workspace input, .hr-workspace select { min-height: 44px; }
.hr-workspace fieldset { border: 0; margin: 0; padding: 0; min-width: 0; display: flex; flex-direction: column; gap: 16px; }
.hr-notice { padding: 14px 16px; margin: 0; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; line-height: 1.6; }
.hr-error { color: var(--danger); }
.hr-empty { padding: 20px 0; color: var(--text-muted); }
.hr-table-wrap { max-width: 100%; overflow-x: auto; }
.hr-workspace table { border-collapse: collapse; width: 100%; font-size: 13px; }
.hr-workspace td, .hr-workspace th { border-bottom: 1px solid var(--border); padding: 12px 10px; white-space: nowrap; text-align: start; }
.hr-workspace th { color: var(--text-muted); font-size: 12px; font-weight: 600; }
.hr-payroll-toolbar { justify-content: flex-start; flex-wrap: wrap; align-items: end; }
.hr-payroll-toolbar label { min-width: 210px; }
.hr-payroll-toolbar a { padding-bottom: 10px; }
.hr-total { font-size: 27px; white-space: nowrap; }
.hr-batch { border-top: 1px solid var(--border); padding-top: 16px; }
.hr-batch > div:first-child { display: flex; flex-direction: column; gap: 7px; }
.hr-batch-actions { flex-wrap: wrap; justify-content: flex-end; }
@media(max-width: 1050px) { .hr-content-grid { grid-template-columns: 1fr; } .hr-filters { grid-template-columns: 2fr 1fr; } .hr-refreshed { grid-column: 1 / -1; text-align: start; padding: 0; } }
@media(max-width: 700px) { .hr-workspace { padding: 16px; gap: 16px; } .hr-heading { align-items: flex-start; flex-wrap: wrap; } .hr-heading-actions { width: 100%; } .hr-heading-actions > span { text-align: start; } .hr-heading h1 { font-size: 22px; } .hr-overview, .hr-filters { grid-template-columns: 1fr; } .hr-panel { padding: 16px; } .hr-section-heading, .hr-batch { align-items: flex-start; flex-wrap: wrap; } .hr-batch-actions { width: 100%; justify-content: flex-start; } .hr-workspace .btn { min-height: 44px; white-space: normal; } .hr-payroll-toolbar > *, .hr-batch-actions > *, fieldset > .btn { width: 100%; } .hr-tabs { gap: 2px; } .hr-tabs button { padding: 8px 10px; } }
</style>
