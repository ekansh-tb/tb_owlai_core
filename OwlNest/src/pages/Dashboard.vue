                                                            <template>
  <div class="space-y-6">
    <!-- Stats Row -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
       <div v-for="(stat, index) in stats" :key="index" class="glass-panel p-6 rounded-2xl border border-white/5 hover:border-accent-purple/30 transition-all duration-300 group">
          <div class="flex items-center justify-between mb-4">
             <div class="p-3 rounded-lg bg-white/5 text-gray-400 group-hover:text-white transition-colors">
                <component :is="stat.icon" class="w-6 h-6" />
             </div>
             <span class="text-xs font-medium px-2 py-1 rounded bg-green-500/10 text-green-400" v-if="stat.trend > 0">
                +{{ stat.trend }}%
             </span>
          </div>
          <h3 class="text-3xl font-bold mb-1 group-hover:text-accent-purple transition-colors">{{ stat.value }}</h3>
          <p class="text-sm text-gray-400">{{ stat.label }}</p>
       </div>
    </div>

    <!-- Main Section -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
       <!-- Recent Activity -->
       <div class="glass-panel p-6 rounded-2xl border border-white/5">
          <h3 class="text-lg font-bold mb-6 flex items-center gap-2">
             <Activity class="w-5 h-5 text-accent-cyan" />
             Recent Activity
          </h3>
          <div class="space-y-4">
             <div v-for="i in 4" :key="i" class="flex items-start gap-4 p-3 rounded-xl hover:bg-white/5 transition-colors cursor-pointer">
                <div class="w-2 h-2 rounded-full bg-accent-purple mt-2"></div>
                <div>
                   <p class="text-sm font-medium">Updated Employee Records</p>
                   <p class="text-xs text-gray-500 mt-1">2 hours ago • Agent Action</p>
                </div>
             </div>
          </div>
       </div>

       <!-- Quick Actions -->
       <div class="glass-panel p-6 rounded-2xl border border-white/5">
          <h3 class="text-lg font-bold mb-6 flex items-center gap-2">
             <Zap class="w-5 h-5 text-yellow-400" />
             Quick Actions
          </h3>
          <div class="grid grid-cols-2 gap-4">
             <button @click="openDeskRoute('Form/Employee/new-employee-1')" class="p-4 rounded-xl bg-white/5 hover:bg-white/10 hover:scale-[1.02] transition-all text-left flex flex-col gap-3 group border border-transparent hover:border-white/10">
                <UserPlus class="w-6 h-6 text-accent-purple group-hover:text-white transition-colors" />
                <span class="text-sm font-medium">New Employee</span>
             </button>
             <button @click="openDeskRoute('List/OwlAI Analytics')" class="p-4 rounded-xl bg-white/5 hover:bg-white/10 hover:scale-[1.02] transition-all text-left flex flex-col gap-3 group border border-transparent hover:border-white/10">
                <FileText class="w-6 h-6 text-accent-cyan group-hover:text-white transition-colors" />
                <span class="text-sm font-medium">Analytics & Logs</span>
             </button>
             <button @click="router.push('/settings')" class="p-4 rounded-xl bg-white/5 hover:bg-white/10 hover:scale-[1.02] transition-all text-left flex flex-col gap-3 group border border-transparent hover:border-white/10">
                <Settings class="w-6 h-6 text-gray-400 group-hover:text-white transition-colors" />
                <span class="text-sm font-medium">Configure Agent</span>
             </button>
             <button @click="openDeskRoute('List/OwlAI Knowledge Base')" class="p-4 rounded-xl bg-white/5 hover:bg-white/10 hover:scale-[1.02] transition-all text-left flex flex-col gap-3 group border border-transparent hover:border-white/10">
                <Search class="w-6 h-6 text-gray-400 group-hover:text-white transition-colors" />
                <span class="text-sm font-medium">Search Knowledge</span>
             </button>
          </div>
       </div>
    </div>
  </div>
</template>

<script setup>
import { Activity, Users, FileText, Zap, UserPlus, Search, Settings } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const router = useRouter()

const stats = [
  { label: 'Active Agents', value: '3', icon: Zap, trend: 12 },
  { label: 'Tasks Completed', value: '1,284', icon: FileText, trend: 5 },
  { label: 'Total Users', value: '842', icon: Users, trend: 0 },
]

function openDeskRoute(route) {
    const baseUrl = window.location.origin;
    window.open(`${baseUrl}/app/${route}`, '_blank');
}
</script>
