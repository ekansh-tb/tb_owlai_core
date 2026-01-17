                                                            <template>
  <div class="max-w-7xl mx-auto space-y-12 pb-20 animate-fade-in px-4 md:px-0">
    
    <!-- HERO SECTION -->
    <section class="relative py-12 px-8 rounded-[40px] overflow-hidden border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent backdrop-blur-3xl group">
        <div class="absolute -top-24 -right-24 w-96 h-96 bg-accent-purple/10 blur-[120px] rounded-full group-hover:bg-accent-purple/20 transition-all duration-700"></div>
        <div class="absolute -bottom-24 -left-24 w-96 h-96 bg-accent-cyan/10 blur-[120px] rounded-full group-hover:bg-accent-cyan/20 transition-all duration-700"></div>
        
        <div class="relative z-10 space-y-4">
            <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-bold uppercase tracking-widest text-gray-400">
                <Sparkles class="w-3 h-3 text-accent-cyan" />
                Next-Gen Agent Operating System
            </div>
            <h1 class="text-5xl md:text-6xl font-black text-white tracking-tighter leading-none">
                Welcome back, <span class="text-transparent bg-clip-text bg-gradient-to-r from-accent-purple to-accent-cyan">{{ userName }}</span>
            </h1>
            <p class="text-lg text-gray-500 max-w-2xl font-medium leading-relaxed">
                Your autonomous agents are active and ready to assist. Manage deployments, explore insights, or start a new task-driven conversation.
            </p>
            
            <div class="flex items-center gap-4 pt-6">
                <button @click="router.push('/chat')" class="px-8 py-4 rounded-2xl bg-white text-black font-bold hover:scale-105 active:scale-95 transition-all flex items-center gap-2 shadow-2xl">
                    <span>Start New Thread</span>
                    <ArrowRight class="w-5 h-5" />
                </button>
                <div class="flex -space-x-3">
                    <div v-for="i in 3" :key="i" class="w-10 h-10 rounded-full border-2 border-[#0a0a0a] bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center text-[10px] font-bold text-gray-400">
                        <Bot class="w-5 h-5" v-if="i === 1"/>
                        <Cpu v-else-if="i === 2" class="w-5 h-5" />
                        <span v-else>+2</span>
                    </div>
                </div>
                <span class="text-xs text-gray-600 font-mono uppercase tracking-widest ml-2">4 Agents Online</span>
            </div>
        </div>
    </section>

    <!-- EXPLORE CAPABILITIES GRID -->
    <section class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-sm font-black text-gray-500 uppercase tracking-[0.3em] flex items-center gap-2">
                <LayoutGrid class="w-4 h-4" />
                Core Capabilities
            </h2>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div v-for="cap in capabilities" :key="cap.title" 
                 @click="cap.action"
                 class="glass-panel p-8 rounded-[32px] border border-white/5 hover:border-white/20 transition-all duration-500 group cursor-pointer relative overflow-hidden h-64 flex flex-col justify-between">
                
                <div class="absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-10 transition-opacity duration-500" :class="cap.color"></div>
                
                <div class="w-14 h-14 rounded-2xl flex items-center justify-center bg-white/5 border border-white/10 group-hover:scale-110 transition-transform duration-500 relative z-10">
                    <component :is="cap.icon" class="w-6 h-6 text-white" />
                </div>
                
                <div class="space-y-2 relative z-10">
                    <h3 class="text-xl font-bold text-white group-hover:text-accent-purple transition-colors">{{ cap.title }}</h3>
                    <p class="text-xs text-gray-500 leading-relaxed font-medium">{{ cap.description }}</p>
                </div>
            </div>
        </div>
    </section>

    <!-- AGENTS & RECENT ACTIONS -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Agents List -->
        <div class="lg:col-span-2 glass-panel rounded-[40px] border border-white/5 p-10 space-y-8">
            <div class="flex items-center justify-between">
                 <h2 class="text-xl font-bold text-white flex items-center gap-3">
                    <Bot class="w-6 h-6 text-accent-purple" />
                    Available Agents
                 </h2>
                 <button class="text-xs text-accent-purple font-bold hover:underline">Manage All</button>
            </div>
            
            <div class="space-y-1">
                <div v-for="agent in agents" :key="agent.name" 
                     class="flex items-center justify-between p-6 rounded-3xl hover:bg-white/[0.03] transition-all border border-transparent hover:border-white/5 group">
                    <div class="flex items-center gap-6">
                        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-white/5 to-transparent border border-white/10 flex items-center justify-center overflow-hidden">
                            <Bot class="w-8 h-8 text-gray-400 group-hover:text-accent-cyan transition-colors" />
                        </div>
                        <div>
                            <div class="text-lg font-bold text-white">{{ agent.name }}</div>
                            <div class="text-xs text-gray-500 mt-1 font-medium">{{ agent.role }}</div>
                        </div>
                    </div>
                    <div class="flex items-center gap-8">
                        <div class="hidden md:block">
                            <div class="text-[10px] font-black text-gray-600 uppercase tracking-widest mb-1">Status</div>
                            <div class="flex items-center gap-1.5">
                                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>
                                <span class="text-xs font-bold text-white">Online</span>
                            </div>
                        </div>
                        <button @click="router.push({ path: '/chat', query: { agent: agent.name } })" 
                                class="p-4 rounded-2xl bg-white/5 hover:bg-white/10 text-white transition-all transform active:scale-90 border border-white/10">
                            <MessageSquare class="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Logs / History -->
        <div class="glass-panel rounded-[40px] border border-white/5 p-10 space-y-8">
            <h2 class="text-xl font-bold text-white flex items-center gap-3">
                <History class="w-6 h-6 text-accent-cyan" />
                History
            </h2>
            
            <div class="space-y-6">
                <div v-for="log in logs" :key="log.id" class="relative pl-6 border-l border-white/5 space-y-1">
                    <div class="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full" :class="log.dotColor"></div>
                    <div class="text-[10px] font-mono text-gray-600 uppercase tracking-tighter">{{ log.time }}</div>
                    <div class="text-sm font-bold text-gray-300">{{ log.action }}</div>
                    <div class="text-[11px] text-gray-600 font-medium truncate">{{ log.details }}</div>
                </div>
            </div>
            
            <button class="w-full py-4 rounded-2xl bg-white/5 hover:bg-white/10 text-xs font-bold text-gray-400 transition-all border border-white/5 border-dashed">
                View Transaction Logs
            </button>
        </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { 
    Activity, Users, FileText, Zap, UserPlus, Search, Settings, 
    Bot, Sparkles, LayoutGrid, ArrowRight, History, MessageSquare, Brain, Cpu
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { userResource } from '../data/user'

const router = useRouter()

const userName = computed(() => {
    return userResource.data?.full_name || 'Innovator'
})

const capabilities = [
    { 
        title: 'Recursive Chat', 
        description: 'Deep reasoning agents with context-aware memory and tools.', 
        icon: MessageSquare, 
        color: 'from-accent-purple to-purple-800',
        action: () => router.push('/chat')
    },
    { 
        title: 'Knowledge Engine', 
        description: 'Indexed documentation and vectorized data for instant retrieval.', 
        icon: Brain, 
        color: 'from-accent-cyan to-blue-800',
        action: () => openDeskRoute('List/OwlAI Knowledge Base')
    },
    { 
        title: 'Action Center', 
        description: 'Orchestrate Frappe workflows and automate document tasks.', 
        icon: Zap, 
        color: 'from-yellow-400 to-orange-600',
        action: () => openDeskRoute('List/OwlAI Analytics')
    },
    { 
        title: 'System Settings', 
        description: 'Configure models, agent personalities, and API connectivity.', 
        icon: Settings, 
        color: 'from-gray-400 to-gray-600',
        action: () => router.push('/settings')
    },
]

const agents = [
    { name: 'Actionable Agent', role: 'Frappe Desk Assistant', status: 'Online' },
    { name: 'Research Agent', role: 'Web Search & Synthesis', status: 'Online' },
    { name: 'Policy Agent', role: 'Internal Knowledge Expert', status: 'Online' }
]

const logs = [
    { id: 1, time: '10 mins ago', action: 'Document Created', details: 'Sales Order SO-2024-001', dotColor: 'bg-accent-purple' },
    { id: 2, time: '2 hours ago', action: 'Knowledge Indexed', details: 'HR Policy Manual Update', dotColor: 'bg-accent-cyan' },
    { id: 3, time: 'Yesterday', action: 'Tool Execution', details: 'System Health Check Dispatched', dotColor: 'bg-yellow-500' },
]

function openDeskRoute(route) {
    const baseUrl = window.location.origin;
    window.open(`${baseUrl}/app/${route}`, '_blank');
}
</script>

<style scoped>
.animate-fade-in {
    animation: fadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
