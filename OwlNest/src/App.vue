<template>
  <div class="min-h-screen text-white font-sans selection:bg-purple-500/30 bg-[#0a0a0a] relative overflow-hidden">
    
    <!-- Vite Glow Background -->
    <div class="vite-glow"></div>

    <div v-if="session.isLoggedIn && $route.name !== 'Login'" class="flex h-screen overflow-hidden relative z-10">
       <!-- SIDEBAR -->
       <aside class="w-64 glass-panel m-4 rounded-3xl flex flex-col border border-white/5 relative z-20 transition-all duration-500">
          <div class="h-24 flex items-center px-8">
             <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#bd34fe] to-[#41d1ff] mr-3 shadow-lg flex items-center justify-center transform hover:rotate-12 transition-transform duration-300">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M12 2L4.5 20.29L5.21 21L12 18L18.79 21L19.5 20.29L12 2Z"/></svg>
             </div>
             <span class="font-bold text-2xl tracking-tight text-white">OwlNest</span>
          </div>

          <nav class="p-4 space-y-2">
             <router-link to="/" class="nav-item group">
                <LayoutDashboard class="w-5 h-5 group-hover:text-[#41d1ff] transition-colors" />
                <span>Dashboard</span>
             </router-link>
             <router-link to="/chat" class="nav-item group">
                <MessageSquare class="w-5 h-5 group-hover:text-[#bd34fe] transition-colors" />
                <span>OwlAI chat</span>
             </router-link>
              <router-link to="/settings" class="nav-item group">
                <Settings class="w-5 h-5 group-hover:rotate-45 transition-transform" />
                <span>Settings</span>
             </router-link>
          </nav>

          <div class="mt-auto p-4 border-t border-white/5">
              <button @click="logout" class="nav-item w-full text-gray-500 hover:text-red-400 hover:bg-red-500/5">
                  <LogOut class="w-5 h-5" />
                  <span>Logout</span>
              </button>
          </div>
       </aside>

       <!-- MAIN CONTENT -->
       <main class="flex-1 flex flex-col h-screen overflow-hidden relative">
          <header class="h-20 flex items-center justify-between px-10 py-4 shrink-0">
             <div class="flex flex-col">
                <h2 class="text-3xl font-bold tracking-tight text-white/95">{{ $route.name }}</h2>
                <div class="text-[10px] font-mono text-gray-500 uppercase tracking-widest mt-1">OwlAI v2.0 • Build System</div>
             </div>
             <div class="flex items-center gap-6">
                <!-- Status Pill -->
                <div class="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 shadow-lg shadow-emerald-500/5">
                    <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                    <span class="text-[10px] font-black text-emerald-500 uppercase tracking-widest">System Active</span>
                </div>

                <!-- User Profile -->
                <div class="flex items-center gap-3 px-4 py-2 rounded-2xl bg-white/5 border border-white/5 hover:border-white/10 transition-colors cursor-pointer group">
                   <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center border border-white/10">
                      <span class="text-xs font-bold text-white/50">{{ session.user?.[0]?.toUpperCase() }}</span>
                   </div>
                   <span class="text-sm font-medium text-gray-400 group-hover:text-white transition-colors">{{ session.user }}</span>
                </div>
             </div>
          </header>

          <div class="flex-1 overflow-hidden p-6 md:p-8 pt-0">
             <router-view v-slot="{ Component }">
                <transition name="fade" mode="out-in">
                   <component :is="Component" />
                </transition>
             </router-view>
          </div>
       </main>
    </div>

    <!-- Login Route / Guest -->
    <div v-else class="h-screen w-full flex items-center justify-center relative z-10">
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
/* Scoped overrides if needed */
</style>
