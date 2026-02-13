<template>
  <section class="card">
    <h2>Admin: All Readings</h2>
    <form class="row" @submit.prevent="loadReadings">
      <input v-model="period" placeholder="YYYY-MM (optional)" />
      <button class="primary" type="submit">Filter</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </section>

  <section class="card">
    <table class="table" v-if="rows.length">
      <thead>
        <tr>
          <th>User</th>
          <th>Email</th>
          <th>Period</th>
          <th>Meter</th>
          <th>Usage</th>
          <th>Submitted</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.user_full_name }}</td>
          <td>{{ r.user_email }}</td>
          <td>{{ r.period }}</td>
          <td>{{ r.meter_value }}</td>
          <td>{{ r.usage }}</td>
          <td>{{ prettyDate(r.submitted_at) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else>No results.</p>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { apiRequest } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const period = ref('')
const rows = ref([])
const error = ref('')

const loadReadings = async () => {
  error.value = ''
  try {
    const suffix = period.value ? `?period=${period.value}` : ''
    rows.value = await apiRequest(`/api/readings/admin/all${suffix}`, { token: auth.token })
  } catch (err) {
    error.value = err.message
  }
}

const prettyDate = (value) => new Date(value).toLocaleString()

onMounted(loadReadings)
</script>
