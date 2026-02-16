<template>
  <main class="auth-page">
    <div class="auth-bg-blob auth-bg-blob--one" aria-hidden="true"></div>
    <div class="auth-bg-blob auth-bg-blob--two" aria-hidden="true"></div>
    <div class="auth-bg-blob auth-bg-blob--three" aria-hidden="true"></div>

    <section class="auth-panel">
      <nav class="auth-mode-switch" aria-label="Authentication mode">
        <button
          class="auth-mode-switch__button"
          :class="{ 'is-active': mode === 'login' }"
          type="button"
          @click="mode = 'login'"
        >
          Log in
        </button>
        <button
          class="auth-mode-switch__button"
          :class="{ 'is-active': mode === 'register' }"
          type="button"
          @click="mode = 'register'"
        >
          Create account
        </button>
      </nav>

      <form class="auth-form" @submit.prevent>
        <h1>{{ title }}</h1>
        <p>{{ subtitle }}</p>

        <label>
          Email
          <input type="email" autocomplete="email" placeholder="you@company.com" required />
        </label>

        <label v-if="mode === 'register'">
          Full name
          <input type="text" autocomplete="name" placeholder="Jane Doe" required />
        </label>

        <label>
          Password
          <input
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            placeholder="Your password"
            required
          />
        </label>

        <label v-if="mode === 'register'">
          Confirm password
          <input
            type="password"
            autocomplete="new-password"
            placeholder="Repeat password"
            required
          />
        </label>

        <button class="auth-submit" type="submit">
          {{ mode === "login" ? "Sign in" : "Create account" }}
        </button>
      </form>
    </section>
  </main>
</template>

<script setup lang="ts">
  import { computed, ref } from "vue";

  const mode = ref<"login" | "register">("login");

  const title = computed(() => (mode.value === "login" ? "Welcome back" : "Create your account"));
  const subtitle = computed(() =>
    mode.value === "login"
      ? "Use your existing account to continue."
      : "New here? Create an account to access Strumok."
  );
</script>

<style scoped lang="scss">
  .auth-page {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: clamp(1rem, 2vw, 1.5rem);
    overflow: hidden;
    position: relative;
    isolation: isolate;
    background:
      radial-gradient(
        circle at 8% 0%,
        color-mix(in srgb, var(--s-primary-color, #3b82f6), transparent 78%),
        transparent 60%
      ),
      radial-gradient(
        circle at 100% 100%,
        color-mix(in srgb, var(--s-primary-color, #3b82f6), transparent 86%),
        transparent 62%
      ),
      var(--s-layout-content-background, var(--s-surface-950, #0a0f1e));
  }

  .auth-bg-blob {
    position: absolute;
    border-radius: 999px;
    filter: blur(20px);
    opacity: 0.45;
    pointer-events: none;
    animation: auth-drift 12s ease-in-out infinite alternate;
  }

  .auth-bg-blob--one {
    width: 23rem;
    height: 23rem;
    top: -7rem;
    left: -5rem;
    background: color-mix(in srgb, var(--s-primary-color, #3b82f6), #8be9ff 45%);
  }

  .auth-bg-blob--two {
    width: 20rem;
    height: 20rem;
    right: -5rem;
    bottom: -6rem;
    background: color-mix(in srgb, var(--s-primary-color, #3b82f6), #ff94da 55%);
    animation-delay: 1.6s;
  }

  .auth-bg-blob--three {
    width: 12rem;
    height: 12rem;
    right: 28%;
    top: 24%;
    background: color-mix(in srgb, var(--s-primary-color, #3b82f6), #90b6ff 58%);
    animation-delay: 0.8s;
  }

  .auth-panel {
    position: relative;
    z-index: 1;
    width: min(100%, 28rem);
    display: grid;
    gap: 1rem;
    padding: clamp(1rem, 2.4vw, 1.8rem);
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--s-content-border-color, #475569), #ffffff 14%);
    background: color-mix(in srgb, var(--s-content-background, #0f172a), transparent 32%);
    backdrop-filter: blur(16px);
    box-shadow: 0 20px 50px rgb(0 0 0 / 32%);
  }

  .auth-logo {
    width: 8.5rem;
  }

  .auth-mode-switch {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    padding: 0.25rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--s-content-background, #0f172a), #000000 25%);
  }

  .auth-mode-switch__button {
    border: 1px solid transparent;
    border-radius: 999px;
    padding: 0.45rem 0.75rem;
    font: inherit;
    color: var(--s-text-muted-color, #94a3b8);
    background: transparent;
    cursor: pointer;
  }

  .auth-mode-switch__button.is-active {
    border-color: color-mix(in srgb, var(--s-primary-color, #3b82f6), transparent 30%);
    background: color-mix(in srgb, var(--s-primary-color, #3b82f6), transparent 82%);
    color: var(--s-text-color, #e2e8f0);
  }

  .auth-form {
    display: grid;
    gap: 0.75rem;
  }

  .auth-form h1 {
    margin: 0;
    color: var(--s-text-color, #e2e8f0);
    font-size: clamp(1.4rem, 2.6vw, 1.75rem);
  }

  .auth-form p {
    margin: 0;
    font-size: 0.95rem;
    color: var(--s-text-muted-color, #94a3b8);
  }

  .auth-form label {
    display: grid;
    gap: 0.45rem;
    font-size: 0.86rem;
    color: var(--s-text-muted-color, #94a3b8);
  }

  .auth-form input {
    width: 100%;
    border-radius: var(--s-form-field-border-radius, 0.625rem);
    border: 1px solid var(--s-content-border-color, #475569);
    background: color-mix(in srgb, var(--s-content-background, #0f172a), #000000 18%);
    color: var(--s-text-color, #e2e8f0);
    font: inherit;
    padding: var(--s-form-field-padding-y, 0.625rem) var(--s-form-field-padding-x, 0.75rem);
    outline: none;
    transition: border-color var(--s-form-field-transition-duration, 0.2s) ease;
  }

  .auth-form input:focus {
    border-color: var(--s-primary-color, #3b82f6);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--s-primary-color, #3b82f6), transparent 70%);
  }

  .auth-submit {
    margin-top: 0.2rem;
    border: 0;
    border-radius: var(--s-form-field-border-radius, 0.625rem);
    padding: 0.72rem 0.95rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    background: var(--s-primary-color, #3b82f6);
    color: var(--s-primary-inverse-color, #ffffff);
  }

  @keyframes auth-drift {
    from {
      transform: translate3d(-8px, -10px, 0) scale(1);
    }
    to {
      transform: translate3d(10px, 12px, 0) scale(1.07);
    }
  }
</style>
