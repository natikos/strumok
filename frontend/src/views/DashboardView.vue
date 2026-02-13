<template>
  <section class="card">
    <h2>My Meter Readings</h2>
    <p>Submit new reading from day 1 to day 5 each month.</p>

    <form class="row" @submit.prevent="submitReading">
      <input
        v-model.number="meterValue"
        type="number"
        min="0"
        step="0.01"
        placeholder="Current meter value"
        required
      />
      <button type="submit" class="primary">Submit</button>
    </form>

    <p v-if="message">{{ message }}</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>

  <section class="card">
    <h3>History</h3>
    <table class="table" v-if="readings.length">
      <thead>
        <tr>
          <th>Period</th>
          <th>Meter</th>
          <th>Usage</th>
          <th>Submitted</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in readings" :key="r.id">
          <td>{{ r.period }}</td>
          <td>{{ r.meter_value }}</td>
          <td>{{ r.usage }}</td>
          <td>{{ prettyDate(r.submitted_at) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else>No readings yet.</p>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { apiRequest } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const meterValue = ref('')
const error = ref('')
const message = ref('')
const readings = ref([])

const loadReadings = async () => {
  readings.value = await apiRequest('/api/readings/my', { token: auth.token })
}

const submitReading = async () => {
  error.value = ''
  message.value = ''
  try {
    await apiRequest('/api/readings/submit', {
      method: 'POST',
      token: auth.token,
      body: { meter_value: meterValue.value },
    })
    message.value = 'Reading submitted'
    meterValue.value = ''
    await loadReadings()
  } catch (err) {
    error.value = err.message
  }
}

const prettyDate = (value) => new Date(value).toLocaleString()

onMounted(loadReadings)
</script>
