<template>
  <form class="login-form" @submit.prevent>
    <h2>Welcome back</h2>
    <p>Sign in to continue to Strumok.</p>
    <label>
      Email
      <input type="email" placeholder="you@company.com" required>
    </label>
    <label>
      Password
      <input type="password" placeholder="Your password" required>
    </label>
    <button type="submit">Sign in</button>
  </form>
</template>
