<template>
  <div class="sec-card user-access">
    <div class="access-heading"><h3>{{ t('ESAFE POS USER ACCESS LEVELS') }}</h3><button class="btn btn-outline" :disabled="busy" @click="load">{{ t('Refresh') }}</button></div>
    <p class="muted">{{ t('Assign a ready-made level or a named custom profile to each user. ERPNext document permissions, company/outlet assignments and existing action rules still apply. These levels do not add ERPNext roles.') }}</p>
    <p v-if="error" class="access-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="muted">{{ t('Loading…') }}</p>
    <template v-if="data">
      <label class="access-search"><span>{{ t('Find user') }}</span><input v-model="search" type="search" :placeholder="t('Name or email')" /></label>
      <div class="access-users">
        <div v-for="row in filteredUsers" :key="row.user" class="access-user">
          <div><b>{{ row.full_name || row.user }}</b><small>{{ row.user }}</small></div>
          <label><span>{{ t('Access level') }}</span><select v-model="row.access_level" :aria-label="t('Access level') + ' ' + row.user"><option v-for="level in data.levels" :key="level" :value="level">{{ t(level) }}</option></select></label>
          <label v-if="row.access_level === 'Custom'"><span>{{ t('Custom profile') }}</span><select v-model="row.access_profile" :aria-label="t('Custom profile') + ' ' + row.user"><option value="">{{ t('Choose profile') }}</option><option v-for="profile in data.profiles" :key="profile.name" :value="profile.name">{{ profile.name }}</option></select></label>
          <button class="btn btn-primary" :disabled="!!busy || row.access_level === 'Custom' && !row.access_profile" @click="saveUser(row)">{{ busy === row.user ? t('Saving…') : t('Save user') }}</button>
          <label v-if="data.can_manage_logins"><span>{{ t('Concurrent logins') }}</span><input type="number" min="1" max="20" v-model.number="row.simultaneous_sessions" :aria-label="t('Concurrent logins') + ' ' + row.user" /></label>
          <button v-if="data.can_manage_logins" class="btn btn-outline" :disabled="!!busy" @click="saveLogins(row)">{{ t('Save login limit') }}</button>
        </div>
        <p v-if="!filteredUsers.length" class="muted">{{ t('No users match') }}</p>
      </div>
      <div class="access-heading profile-heading"><h3>{{ t('Custom access profiles') }}</h3><button class="btn btn-outline" :disabled="!!busy" @click="editProfile()">{{ t('Create profile') }}</button></div>
      <div class="profile-list"><button v-for="profile in data.profiles" :key="profile.name" class="btn btn-outline" :disabled="!!busy" @click="editProfile(profile)">{{ profile.name }}</button></div>
      <form v-if="editor" class="profile-editor" @submit.prevent="saveProfile">
        <label><span>{{ t('Profile name') }}</span><input v-model.trim="editor.name" maxlength="100" required :disabled="!!editor.modified || !!busy" /></label>
        <label><span>{{ t('Start from access level') }}</span><select v-model="editor.base_level" :disabled="!!busy" @change="applyBase"><option v-for="level in Object.keys(data.presets)" :key="level" :value="level">{{ t(level) }}</option></select></label>
        <p class="muted">{{ t('Select the actions this profile allows. Reports only remains a read-only workspace. Manager profiles include POS management access; ERPNext manager roles remain authoritative.') }}</p>
        <div class="capability-grid"><label v-for="capability in data.capabilities" :key="capability"><input type="checkbox" v-model="editor.allowed[capability]" :disabled="!!busy || editor.base_level === 'Reports only' && !data.presets['Reports only'].includes(capability)" /><span>{{ t(capability) }}</span></label></div>
        <div class="profile-actions"><button type="button" class="btn btn-outline" :disabled="!!busy" @click="editor = null">{{ t('Cancel') }}</button><button class="btn btn-primary" :disabled="!!busy || !editor.name">{{ t('Save profile') }}</button></div>
      </form>
      <p class="muted small">{{ t('Save user and Save profile apply independently of Save Settings. Refresh affected tills after changing access. Use existing roles restores the previous permission rules.') }}</p>
      <p class="muted small">{{ t('To sign the same user into two computers, allow at least 2 concurrent ERPNext logins as well as multiple-computer shifts. Changing login limits requires ERPNext User write permission and applies on the next login.') }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { call } from '../api'
import { useSessionStore } from '../stores/session'
import { t } from '../i18n'
const session = useSessionStore()
const data = ref(null), users = ref([]), search = ref(''), loading = ref(false), busy = ref(''), error = ref(''), editor = ref(null)
const filteredUsers = computed(() => users.value.filter(row => `${row.user} ${row.full_name || ''}`.toLowerCase().includes(search.value.toLowerCase())))
async function load() {
  loading.value = true; error.value = ''
  try {
    data.value = await call('esafepos.api.user_access.get_access_management')
    users.value = data.value.users.map(user => ({ user: user.name, full_name: user.full_name, simultaneous_sessions: user.simultaneous_sessions || 1, access_level: 'Use existing roles', access_profile: '', ...data.value.assignments.find(row => row.user === user.name) }))
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function saveUser(row) {
  busy.value = row.user; error.value = ''
  try {
    await call('esafepos.api.user_access.save_user_level', { user: row.user, access_level: row.access_level, access_profile: row.access_profile || '' })
    session.notify(t('User access level saved'))
  } catch (e) { error.value = e.message }
  finally { busy.value = '' }
}
async function saveLogins(row) {
  busy.value = row.user; error.value = ''
  try {
    await call('esafepos.api.user_access.save_login_limit', { user: row.user, simultaneous_sessions: row.simultaneous_sessions })
    session.notify(t('Concurrent login limit saved'))
  } catch (e) { error.value = e.message }
  finally { busy.value = '' }
}
function editProfile(profile) {
  editor.value = { name: profile?.name || '', base_level: profile?.base_level || 'Cashier', modified: profile?.modified || '', allowed: {} }
  applyBase()
  for (const row of profile?.capabilities || []) editor.value.allowed[row.capability] = Boolean(row.allowed)
}
function applyBase() {
  editor.value.allowed = Object.fromEntries(data.value.capabilities.map(capability => [capability, data.value.presets[editor.value.base_level].includes(capability)]))
}
async function saveProfile() {
  busy.value = 'profile'; error.value = ''
  try {
    await call('esafepos.api.user_access.save_access_profile', { profile: { name: editor.value.name, base_level: editor.value.base_level, modified: editor.value.modified,
      capabilities: data.value.capabilities.map(capability => ({ capability, allowed: editor.value.allowed[capability] ? 1 : 0 })) } })
    const refreshed = await call('esafepos.api.user_access.get_access_management')
    data.value.profiles = refreshed.profiles; editor.value = null
    session.notify(t('Access profile saved'))
  } catch (e) { error.value = e.message }
  finally { busy.value = '' }
}
onMounted(load)
</script>

<style scoped>
.access-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
h3 { margin: 0; font-size: 15px; }
.user-access p { line-height: 1.6; }
.access-search { display: grid; gap: 6px; max-width: 400px; margin: 16px 0; }
.access-users { max-height: 460px; overflow-y: auto; }
.access-user { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; padding: 14px 0; border-top: 1px solid var(--border); }
.access-user > div { flex: 1 1 200px; min-width: 0; overflow-wrap: anywhere; }
.access-user small { display: block; color: var(--text-muted); margin-top: 3px; }
.access-user label, .profile-editor > label { display: grid; gap: 5px; flex: 1 1 160px; font-size: 12px; }
select, input:not([type='checkbox']) { width: 100%; min-width: 0; }
.profile-heading { border-top: 1px solid var(--border); padding-top: 18px; margin-top: 18px; }
.profile-list, .profile-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
.profile-editor { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 18px; }
.profile-editor > p, .profile-actions { width: 100%; }
.capability-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 100%; }
.capability-grid label { display: flex; align-items: start; gap: 8px; line-height: 1.5; }
.access-error { color: var(--red); }
.small { font-size: 12px; }
@media (max-width: 600px) { .capability-grid { grid-template-columns: 1fr; } .access-user > button { width: 100%; } }
</style>
