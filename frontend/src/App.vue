<template>
  <div class="page" :class="{ 'app-dark': isDark }">
    <header class="topbar">
      <h1 class="brand">Strumok</h1>
      <Button
        :label="isDark ? 'Light' : 'Dark'"
        :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
        severity="secondary"
        text
        @click="toggleTheme"
      />
    </header>

    <main class="content">
      <Card class="login-card">
        <template #title>Login</template>
        <template #content>
          <div class="form-grid">
            <label for="email">Email</label>
            <InputText
              id="email"
              v-model="email"
              type="email"
              placeholder="you@example.com"
            />

            <label for="password">Password</label>
            <Password
              id="password"
              v-model="password"
              :feedback="false"
              toggleMask
              placeholder="Your password"
              :inputStyle="{ width: '100%' }"
              fluid
            />

            <Button label="Sign in" icon="pi pi-sign-in" class="signin-btn" />
          </div>
        </template>
      </Card>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import Button from "primevue/button";
import Card from "primevue/card";
import InputText from "primevue/inputtext";
import Password from "primevue/password";

const email = ref("");
const password = ref("");
const theme = ref(localStorage.getItem("theme") || "light");

const isDark = computed(() => theme.value === "dark");

const toggleTheme = () => {
  theme.value = isDark.value ? "light" : "dark";
  localStorage.setItem("theme", theme.value);
};
</script>
