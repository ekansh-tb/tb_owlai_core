<template>
  <div class="bg-primary min-h-screen text-white font-sans selection:bg-accent-purple selection:text-white">
    <div v-if="session.isLoggedIn && $route.name !== 'Login'" class="flex h-screen overflow-hidden">
       <!-- SIDEBAR -->
       <aside class="w-64 glass-panel m-4 rounded-2xl flex flex-col border border-white/5 relative z-20 transition-all duration-300">
          <div class="h-20 flex items-center px-8 border-b border-white/5">
             <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-accent-purple to-pink-500 mr-3 shadow-lg shadow-accent-purple/20 flex items-center justify-center">
                <span class="text-xs font-bold text-white">OA</span>
             </div>
             <span class="font-bold text-xl tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">OwlNest</span>
          </div>

          <nav class="p-4 space-y-2 mt-2">
             <router-link to="/" class="nav-item">
                <LayoutDashboard class="w-5 h-5" />
                <span>Dashboard</span>
             </router-link>
             <router-link to="/chat" class="nav-item">
                <MessageSquare class="w-5 h-5" />
                <span>OwlAI Chat</span>
             </router-link>
              <router-link to="/settings" class="nav-item">
                <Settings class="w-5 h-5" />
                <span>Settings</span>
             </router-link>
          </nav>

          <div class="mt-auto p-4 border-t border-white/5">
              <button @click="logout" class="nav-item w-full text-red-400 hover:bg-red-500/10 hover:text-red-300">
                  <LogOut class="w-5 h-5" />
                  <span>Logout</span>
              </button>
          </div>
       </aside>

       <!-- MAIN CONTENT -->
       <main class="flex-1 flex flex-col h-screen overflow-hidden relative">
          <!-- Header -->
          <header class="h-20 flex items-center justify-between px-8 py-4 shrink-0 transition-opacity duration-300">
             <h2 class="text-2xl font-bold text-white/90">{{ $route.name }}</h2>
             <div class="flex items-center gap-4">
                <div class="px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-gray-400 font-mono shadow-sm">
                   {{ session.user }}
                </div>
             </div>
          </header>

          <div class="flex-1 overflow-auto p-8 pt-0 custom-scrollbar">
             <router-view v-slot="{ Component }">
                <transition name="fade" mode="out-in">
                   <component :is="Component" />
                </transition>
             </router-view>
          </div>
       </main>
    </div>

    <!-- Login Route / Guest -->
    <div v-else class="h-screen w-full flex items-center justify-center relative overflow-hidden bg-primary">
       <!-- Background Decoration -->
       <div class="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-accent-purple/20 blur-[150px] rounded-full pointing-none animate-pulse-slow"></div>
       <div class="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-accent-cyan/10 blur-[150px] rounded-full pointing-none"></div>

       <router-view />
    </div>
  </div>
</template>

<script setup>
import { session } from './data/session'
import { LayoutDashboard, MessageSquare, Settings, LogOut } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const router = useRouter()

function logout() {
  session.logout.submit()
}
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 text-gray-400 font-medium;
}
.nav-item:hover {
  @apply bg-white/5 text-white translate-x-1;
}
.router-link-active {
  @apply bg-accent-purple/10 text-accent-purple border border-accent-purple/20 shadow-lg shadow-accent-purple/5;
}

/* Custom fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  @apply bg-gray-700/50 rounded-full hover:bg-gray-600;
}
</style>
