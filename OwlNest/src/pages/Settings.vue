<template>
  <div class="max-w-6xl mx-auto flex flex-col md:flex-row gap-10 animate-fade-in relative z-10 pb-20">
    <Dialog v-model="showIndexModal" :options="{ title: 'Index New Knowledge' }">
      <template #body-content>
        <div class="space-y-4">
             <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Title</label>
                <input v-model="newDoc.title" type="text" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all" placeholder="e.g. ERPNext Documentation" />
             </div>
             
             <div>
                <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Source Type</label>
                <div class="flex gap-2">
                    <button @click="newDoc.source_type = 'URL'" :class="['px-4 py-2 rounded-lg text-xs font-bold transition-all', newDoc.source_type === 'URL' ? 'bg-accent-purple text-white' : 'bg-gray-200 text-gray-600']">URL</button>
                    <button @click="newDoc.source_type = 'Text'" :class="['px-4 py-2 rounded-lg text-xs font-bold transition-all', newDoc.source_type === 'Text' ? 'bg-accent-purple text-white' : 'bg-gray-200 text-gray-600']">Text</button>
                </div>
             </div>

             <div v-if="newDoc.source_type === 'URL'">
                <label class="block text-xs font-bold text-gray-500 uppercase mb-1">URL</label>
                <input v-model="newDoc.url" type="url" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all" placeholder="https://..." />
             </div>

             <div v-if="newDoc.source_type === 'Text'">
                <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Content</label>
                <textarea v-model="newDoc.content" rows="4" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all" placeholder="Paste text content here..."></textarea>
             </div>
        </div>
      </template>
      <template #actions>
        <Button @click="idxResource" :loading="indexing" variant="solid">Start Indexing</Button>
      </template>
    </Dialog>
    
    <!-- SETTINGS SIDEBAR -->
    <aside class="w-full md:w-64 shrink-0 space-y-2">
        <button v-for="tab in tabs" :key="tab.id"
                @click="activeTab = tab.id"
                :class="[
                    'w-full flex items-center gap-3 px-6 py-4 rounded-2xl transition-all duration-300 font-bold text-sm',
                    activeTab === tab.id 
                    ? 'bg-white text-black shadow-2xl' 
                    : 'text-gray-500 hover:text-white hover:bg-white/5'
                ]">
            <component :is="tab.icon" class="w-5 h-5" />
            <span>{{ tab.label }}</span>
        </button>
    </aside>

    <!-- SETTINGS CONTENT -->
    <main class="flex-1 min-w-0">
        <!-- GENERAL SETTINGS -->
        <div v-if="activeTab === 'general'" class="space-y-8 animate-slide-right">
            <div class="glass-panel p-8 rounded-[32px] border border-white/5 space-y-8">
                <header class="space-y-1">
                    <h2 class="text-2xl font-black text-white tracking-tight">General Configuration</h2>
                    <p class="text-sm text-gray-500 font-medium">Core model and identity settings for your OwlAI instances.</p>
                </header>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="space-y-3">
                        <label class="text-xs font-black text-gray-400 uppercase tracking-widest">AI Provider</label>
                        <select v-model="settings.provider" class="w-full bg-white/[0.03] border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-accent-purple transition-all appearance-none cursor-pointer">
                            <option value="Local (Ollama)" class="bg-gray-900">Local (Ollama)</option>
                            <option value="Generative AI (Gemini)" class="bg-gray-900">Generative AI (Gemini)</option>
                        </select>
                    </div>
                    <div class="space-y-3">
                        <label class="text-xs font-black text-gray-400 uppercase tracking-widest">Default Model</label>
                        <select v-model="settings.model" class="w-full bg-white/[0.03] border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-accent-purple transition-all appearance-none cursor-pointer">
                            <option v-for="m in availableModels" :key="m.name" :value="m.name" class="bg-gray-900">{{ m.name }}</option>
                        </select>
                    </div>
                    <div class="space-y-3">
                        <label class="text-xs font-black text-gray-400 uppercase tracking-widest">Creativity (Temperature)</label>
                        <div class="flex items-center gap-4">
                             <input v-model="settings.temperature" type="range" min="0" max="1" step="0.1" class="flex-1 accent-accent-purple" />
                             <span class="text-sm font-mono text-white bg-white/5 px-3 py-1 rounded-lg border border-white/10">{{ settings.temperature }}</span>
                        </div>
                    </div>
                </div>

                <div class="space-y-3">
                    <label class="text-xs font-black text-gray-400 uppercase tracking-widest">System Voice & Persona</label>
                    <textarea v-model="settings.system_prompt" rows="4" class="w-full bg-white/[0.03] border border-white/10 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-accent-purple resize-none placeholder-gray-700" placeholder="e.g. You are a helpful assistant that specialized in ERPNext technical consulting."></textarea>
                </div>
            </div>
            
            <div class="flex items-center justify-end gap-4">
                <button class="px-8 py-4 rounded-2xl bg-white/5 hover:bg-white/10 text-sm font-bold text-gray-400 transition-all">Discard</button>
                <button @click="saveSettings" class="px-8 py-4 rounded-2xl bg-accent-purple hover:bg-accent-purple/90 text-white font-bold shadow-2xl transition-all transform active:scale-95">Save Changes</button>
            </div>
        </div>

        <!-- INTELLIGENCE / ADVANCED -->
        <div v-if="activeTab === 'intelligence'" class="space-y-8 animate-slide-right">
            <div class="glass-panel p-8 rounded-[32px] border border-white/5 space-y-10">
                <header class="space-y-1">
                    <h2 class="text-2xl font-black text-white tracking-tight">Intelligence Parameters</h2>
                    <p class="text-sm text-gray-500 font-medium">Control how the agent manages context, memory, and reasoning.</p>
                </header>

                <div class="space-y-6">
                    <div v-for="toggle in intelligenceToggles" :key="toggle.id" class="flex items-center justify-between p-6 rounded-3xl bg-white/[0.02] border border-white/5 group hover:border-white/10 transition-all">
                        <div class="space-y-1">
                            <div class="text-sm font-bold text-white">{{ toggle.label }}</div>
                            <div class="text-xs text-gray-500 font-medium">{{ toggle.description }}</div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" v-model="settings[toggle.id]" class="sr-only peer">
                            <div class="w-12 h-7 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[4px] after:left-[4px] after:bg-gray-400 peer-checked:after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-cyan transition-all"></div>
                        </label>
                    </div>
                </div>

                <div class="space-y-3">
                    <label class="text-xs font-black text-gray-400 uppercase tracking-widest flex items-center gap-2">
                        Context Compression Limit
                        <Info class="w-3.5 h-3.5 text-accent-purple cursor-help" />
                    </label>
                    <div class="flex items-center gap-4">
                        <div class="flex-1 h-3 bg-white/5 rounded-full overflow-hidden relative">
                            <div class="absolute h-full bg-accent-purple transition-all duration-500" :style="{ width: (settings.contextLimit / 32000 * 100) + '%' }"></div>
                        </div>
                        <input v-model="settings.contextLimit" type="number" class="w-24 bg-white/[0.03] border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-center text-white" />
                    </div>
                    <p class="text-[10px] text-gray-600 font-medium italic">Compression kicks in after this token threshold to preserve reasoning capacity.</p>
                </div>
            </div>
        </div>

        <!-- MEMORY MANAGEMENT -->
        <div v-if="activeTab === 'memory'" class="space-y-8 animate-slide-right">
             <div class="glass-panel p-8 rounded-[32px] border border-white/5 space-y-4">
                <div class="flex items-center justify-between mb-4">
                    <header class="space-y-1">
                        <h2 class="text-2xl font-black text-white tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-accent-purple to-pink-500">Long-term Memory</h2>
                        <p class="text-sm text-gray-500 font-medium">Insights and facts the agent has learned about you.</p>
                    </header>
                    <button @click="memories.reload()" class="p-3 rounded-xl bg-white/5 hover:bg-white/10 text-gray-400">
                        <RefreshCw class="w-5 h-5" :class="{ 'animate-spin': memories.loading }" />
                    </button>
                </div>

                <div v-if="memories.data?.length" class="space-y-3">
                    <div v-for="mem in memories.data" :key="mem.name" class="flex items-center justify-between p-5 rounded-2xl bg-white/[0.02] border border-white/5 hover:border-accent-purple/30 transition-all group">
                        <div class="flex items-center gap-4">
                             <div class="w-2 h-2 rounded-full bg-accent-purple"></div>
                             <span class="text-sm text-gray-300 font-medium italic">"{{ mem.content }}"</span>
                        </div>
                        <button @click="deleteMemory(mem.name)" class="p-2.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-red-400 transition-all">
                            <Trash2 class="w-4 h-4" />
                        </button>
                    </div>
                </div>
                <div v-else-if="!memories.loading" class="py-20 text-center space-y-4">
                    <div class="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mx-auto border border-dashed border-white/10">
                        <Brain class="w-8 h-8 text-gray-700" />
                    </div>
                    <p class="text-xs text-gray-600 font-bold uppercase tracking-widest">No memories stored yet</p>
                </div>
             </div>
        </div>

        <!-- KNOWLEDGE BASE -->
        <div v-if="activeTab === 'knowledge'" class="space-y-8 animate-slide-right">
             <div class="glass-panel p-8 rounded-[32px] border border-white/5 space-y-6">
                <header class="space-y-1">
                    <h2 class="text-2xl font-black text-white tracking-tight">Knowledge Ecosystem</h2>
                    <p class="text-sm text-gray-500 font-medium">Manage document indexing and framework expertise.</p>
                </header>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div v-for="doc in knowledge.data" :key="doc.name" class="p-5 rounded-3xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] transition-all group cursor-pointer">
                        <div class="flex items-center gap-4 mb-3">
                            <div class="p-3 rounded-2xl bg-accent-cyan/10 border border-accent-cyan/20">
                                <FileText class="w-5 h-5 text-accent-cyan" />
                            </div>
                            <div class="flex-1 min-w-0">
                                <h4 class="text-sm font-bold text-white truncate">{{ doc.title }}</h4>
                                <p class="text-[10px] text-gray-600 font-mono">{{ formatDate(doc.creation) }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                        <div class="flex items-center gap-2">
                             <div class="px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest"
                                :class="{
                                    'bg-emerald-500/10 text-emerald-400': doc.status === 'Indexed',
                                    'bg-yellow-500/10 text-yellow-400': doc.status === 'Indexing',
                                    'bg-red-500/10 text-red-400': doc.status === 'Failed',
                                    'bg-white/5 text-gray-500': doc.status === 'Pending'
                                }">
                                {{ doc.status || 'Unknown' }}
                             </div>
                        </div>
                        </div>
                    </div>
                </div>

                <button @click="showIndexModal = true" class="w-full py-6 rounded-3xl border-2 border-dashed border-white/10 hover:border-accent-cyan/30 bg-white/[0.01] hover:bg-accent-cyan/[0.02] transition-all flex flex-col items-center gap-3">
                    <div class="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center">
                        <Plus class="w-6 h-6 text-gray-500" />
                    </div>
                    <span class="text-xs font-black text-gray-500 uppercase tracking-widest">Index New Resource</span>
                </button>
             </div>
        </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { 
    Cpu, Sliders, Settings, Brain, Globe, Database, Info, 
    Trash2, RefreshCw, Layers, Zap, FileText, Plus 
} from 'lucide-vue-next'
import { createResource, Dialog, Button, call } from 'frappe-ui'

const activeTab = ref('general')

const tabs = [
    { id: 'general', label: 'General', icon: Settings },
    { id: 'intelligence', label: 'Intelligence', icon: Zap },
    { id: 'memory', label: 'Memory', icon: Brain },
    { id: 'knowledge', label: 'Knowledge', icon: Database },
]

const settings = reactive({
    provider: 'Local (Ollama)',
    model: '',
    temperature: 0.7,
    system_prompt: '',
    enable_memory: true,
    enable_compression: true,
    agentic_reasoning: true,
    contextLimit: 12000
})

const intelligenceToggles = [
    { id: 'enable_memory', label: 'Persistent Memory', description: 'Agent learns and recalls facts across sessions.' },
    { id: 'enable_compression', label: 'Context Compression', description: 'Maintains long-range history via semantic summarization.' },
    { id: 'agentic_reasoning', label: 'Agentic Reasoning', description: 'Enable multi-step thought processes for complex tasks.' }
]

// Resources
const settingsResource = createResource({
    url: 'frappe.client.get',
    params: { doctype: 'OwlAI Settings', name: 'OwlAI Settings' },
    auto: true,
    onSuccess(data) {
        settings.provider = data.provider || 'Local (Ollama)'
        settings.model = data.provider === 'Local (Ollama)' ? data.ollama_model : data.gemini_model
        settings.temperature = data.default_temperature || 0.7
        settings.system_prompt = data.default_system_prompt || ''
        settings.enable_memory = !!data.enable_memory
        settings.enable_compression = !!data.enable_compression
        settings.agentic_reasoning = !!data.agentic_reasoning
        settings.contextLimit = data.context_limit || 12000
    }
})

const modelsResource = createResource({
    url: 'frappe.client.get_list',
    params: {
        doctype: 'OwlAI Model',
        fields: ['name', 'provider'],
        limit: 100
    },
    auto: true
})

const availableModels = computed(() => {
    if (!modelsResource.data) return []
    // Filter based on provider logic
    return modelsResource.data.filter(m => {
        if (settings.provider.includes('Ollama')) return m.provider.includes('Ollama')
        if (settings.provider.includes('Gemini')) return m.provider.includes('Gemini')
        return true
    })
})

const memories = createResource({
    url: 'frappe.client.get_list',
    params: {
        doctype: 'OwlAI User Memory',
        fields: ['name', 'content', 'creation'],
        limit: 20,
        order_by: 'creation desc'
    },
    auto: true
})

const knowledge = createResource({
    url: 'frappe.client.get_list',
    params: () => ({
        doctype: 'OwlAI Knowledge Base',
        fields: ['name', 'title', 'creation', 'status', 'source_type', 'error'],
        limit: 10,
        order_by: 'creation desc'
    }),
    auto: true
})

async function saveSettings() {
    try {
        await call('frappe.client.set_value', {
            doctype: 'OwlAI Settings',
            name: 'OwlAI Settings',
            fieldname: {
                provider: settings.provider,
                [settings.provider === 'Local (Ollama)' ? 'ollama_model' : 'gemini_model']: settings.model,
                default_temperature: settings.temperature,
                default_system_prompt: settings.system_prompt,
                enable_memory: settings.enable_memory,
                enable_compression: settings.enable_compression,
                agentic_reasoning: settings.agentic_reasoning,
                context_limit: settings.contextLimit
            }
        })
        alert('Settings synced successfully.')
        settingsResource.reload()
    } catch (e) {
        console.error(e)
        let msg = 'Failed to save settings.'
        if (e.messages && e.messages.length) msg = e.messages.join(', ')
        else if (e.message) msg = e.message
        alert(msg)
    }
}

async function deleteMemory(name) {
    if (confirm('Delete this memory?')) {
        await call('frappe.client.delete', { doctype: 'OwlAI User Memory', name })
        memories.reload()
    }
}

function formatDate(date) {
    if (!date) return '-'
    return new Date(date).toLocaleDateString()
}

// Indexing Logic
const showIndexModal = ref(false)
const indexing = ref(false)
const newDoc = reactive({
    title: '',
    source_type: 'URL',
    url: '',
    content: ''
})

async function idxResource() {
    if (!newDoc.title) return alert('Title is required')
    if (newDoc.source_type === 'URL' && !newDoc.url) return alert('URL is required')
    if (newDoc.source_type === 'Text' && !newDoc.content) return alert('Content is required')
    
    try {
        indexing.value = true
        await call('frappe.client.insert', {
            doc: {
                doctype: 'OwlAI Knowledge Base',
                title: newDoc.title,
                source_type: newDoc.source_type,
                url: newDoc.source_type === 'URL' ? newDoc.url : undefined,
                content: newDoc.source_type === 'Text' ? newDoc.content : undefined,
                status: 'Pending'
            }
        })
        
        showIndexModal.value = false
        // Reset
        newDoc.title = ''
        newDoc.url = ''
        newDoc.content = ''
        
        // Refresh list
        knowledge.reload()
        alert('Indexing started. The agent will process this in the background.')
    } catch (e) {
        console.error(e)
        alert('Failed to start indexing.')
    } finally {
        indexing.value = false
    }
}
</script>

<style scoped>
.animate-fade-in {
    animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.animate-slide-right {
    animation: slideRight 0.5s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
}

/* Custom Thumb for Range Input */
input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 18px;
    width: 18px;
    border-radius: 50%;
    background: white;
    box-shadow: 0 0 10px rgba(189, 52, 254, 0.5);
    cursor: pointer;
    margin-top: -6px;
}
</style>

<style scoped>
.animate-fade-in-up {
    animation: fadeInUp 0.5s ease-out;
}
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
