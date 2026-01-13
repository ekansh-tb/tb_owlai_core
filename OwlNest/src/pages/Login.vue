<template>
  <div class="w-full max-w-md p-8 pt-10 rounded-2xl glass-panel border border-white/10 relative z-10 backdrop-blur-xl shadow-2xl">
    <div class="text-center mb-10">
      <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-accent-purple to-pink-500 mx-auto mb-6 flex items-center justify-center shadow-lg shadow-accent-purple/30 text-white text-3xl font-bold">
        <span>🦉</span>
      </div>
      <h1 class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400 mb-2">Welcome Back</h1>
      <p class="text-gray-400">Enter your credentials to access OwlNest</p>
    </div>

    <form @submit.prevent="submit" class="space-y-6">
      <div class="space-y-2">
        <label class="text-sm font-medium text-gray-300 ml-1">Email / User ID</label>
        <input 
          name="email"
          type="text" 
          v-model="email"
          class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-accent-purple/50 focus:border-transparent transition-all placeholder-gray-600"
          placeholder="administrator"
          required
        />
      </div>

      <div class="space-y-2">
        <label class="text-sm font-medium text-gray-300 ml-1">Password</label>
        <input 
          name="password"
          type="password" 
          v-model="password"
          class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-accent-purple/50 focus:border-transparent transition-all placeholder-gray-600"
          placeholder="••••••••"
          required
        />
      </div>

      <button 
        type="submit" 
        :disabled="session.login.loading"
        class="w-full py-3.5 rounded-xl bg-gradient-to-r from-accent-purple to-indigo-600 text-white font-bold hover:shadow-lg hover:shadow-accent-purple/25 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-4 flex items-center justify-center"
      >
        <span v-if="session.login.loading" class="flex items-center justify-center gap-2">
          <Loader2 class="w-5 h-5 animate-spin" />
          Signing in...
        </span>
        <span v-else>Sign In</span>
      </button>
    </form>
    
    <div v-if="session.login.error" class="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 text-sm text-center">
       {{ session.login.error?.message || 'Login failed. Please check your credentials.' }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { session } from "../data/session"
import { Loader2 } from 'lucide-vue-next'

const email = ref('')
const password = ref('')

function submit() {
	session.login.submit({
		email: email.value,
		password: password.value,
	})
}
</script>
