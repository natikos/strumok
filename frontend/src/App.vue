<template>
  <div class="shell">
    <header class="topbar">
      <h1>Garden Power Reporting</h1>
      <nav>
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink v-if="!auth.isAuthenticated" to="/login">Login</RouterLink>
        <RouterLink v-if="!auth.isAuthenticated" to="/register">Register</RouterLink>
        <RouterLink v-if="auth.user?.is_admin" to="/admin">Admin</RouterLink>
        <button v-if="auth.isAuthenticated" @click="logout" class="link-button">Logout</button>
      </nav>
    </header>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const router = useRouter()
const auth = useAuthStore()

onMounted(() => {
  if (auth.token && !auth.user) {
    auth.fetchMe().catch(() => auth.logout())
  }
})

const logout = () => {
  auth.logout()
  router.push('/login')
}
</script>
