<template>
  <section class="card">
    <h2>Register</h2>
    <form class="row" @submit.prevent="onSubmit">
      <input v-model="fullName" type="text" placeholder="Full name" required />
      <input v-model="email" type="email" placeholder="Email" required />
      <input v-model="password" type="password" placeholder="Password (min 8 chars)" required />
      <button class="primary" type="submit">Create account</button>
    </form>
    <p v-if="success">Account created. You can now log in.</p>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const fullName = ref('')
const email = ref('')
const password = ref('')
const success = ref(false)
const error = ref('')

const auth = useAuthStore()

const onSubmit = async () => {
  success.value = false
  error.value = ''
  try {
    await auth.register({
      full_name: fullName.value,
      email: email.value,
      password: password.value,
    })
    success.value = true
    fullName.value = ''
    email.value = ''
    password.value = ''
  } catch (err) {
    error.value = err.message
  }
}
</script>
