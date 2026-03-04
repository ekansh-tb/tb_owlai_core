<template>
  <div class="flex h-full font-sans text-gray-100 selection:bg-purple-500/30 overflow-hidden glass-panel rounded-3xl border border-white/5 shadow-2xl relative">
     
     <!-- 1. LEFT SIDEBAR (History) -->
     <aside class="w-[300px] flex flex-col shrink-0 border-r border-white/5 bg-black/20 backdrop-blur-3xl transition-all duration-500">
        
        <!-- Search & Control -->
        <div class="h-20 flex items-center px-6 border-b border-white/5 shrink-0 justify-between">
            <span class="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-500">Recents</span>
            <button @click="startNewChat" class="w-8 h-8 flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 transition-all group">
                <Plus class="w-4 h-4 text-gray-400 group-hover:text-white group-hover:rotate-90 transition-all duration-300" />
            </button>
        </div>

        <!-- History List -->
        <div class="flex-1 overflow-auto px-4 py-4 space-y-1.5 custom-scrollbar">
            <div v-for="conv in conversations.data" :key="conv.name"
                 class="group relative p-3 rounded-xl cursor-pointer text-sm transition-all border border-transparent flex justify-between items-center"
                 :class="currentConvId === conv.name ? 'bg-white/[0.08] text-white border-white/5 shadow-inner' : 'text-gray-400 hover:bg-white/5'"
                 @click="loadConversation(conv.name)">
                 <div class="flex-1 min-w-0 pr-2">
                    <div class="truncate font-medium text-[13px] group-hover:text-white transition-colors">{{ conv.title || 'New Conversation' }}</div>
                    <div class="text-[9px] text-gray-600 mt-1 font-mono uppercase tracking-widest flex items-center gap-1.5 opacity-60">
                        <Clock class="w-2.5 h-2.5" />
                        {{ formatDate(conv.modified) }}
                    </div>
                 </div>
                 <button @click.stop="deleteConversation(conv.name)" 
                         class="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-1.5 -mr-1"
                         title="Delete Conversation">
                     <Trash2 class="w-3.5 h-3.5" />
                 </button>
            </div>
        </div>
        
        <!-- Theme Info -->
        <div class="p-6 border-t border-white/5 bg-white/5">
            <div class="flex items-center gap-2 text-[10px] font-mono text-gray-500 tracking-tighter uppercase">
               <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
               OwlAi can see what you can see!!!
            </div>
        </div>
     </aside>

     <!-- 2. MAIN CONTENT (Chat Area) -->
     <main class="flex-1 flex flex-col relative bg-transparent min-w-0">
        
        <!-- Header -->
        <header class="h-20 flex items-center justify-between px-8 border-b border-white/5">
            <div class="flex items-center gap-4">
                 <h2 class="text-xl font-bold text-white/90 tracking-tight">
                    {{ currentTitle || 'Agent Session' }}
                 </h2>
                 <transition name="fade">
                    <span v-if="chat.loading" class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-[#41d1ff] bg-[#41d1ff]/10 px-3 py-1 rounded-full border border-[#41d1ff]/20">
                        <Loader2 class="w-3 h-3 animate-spin" />
                        Generating
                    </span>
                 </transition>
            </div>
            
            <div class="flex items-center gap-3">
                 <button class="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-gray-400 hover:text-white transition-all border border-white/5">
                     <Bot class="w-3.5 h-3.5" />
                     <span>World Class Agent</span>
                 </button>
                 <button @click="showArtifacts = !showArtifacts" 
                         class="p-2.5 hover:bg-white/5 rounded-xl transition-all"
                         :class="showArtifacts ? 'text-[#bd34fe] bg-[#bd34fe]/10 border border-[#bd34fe]/20' : 'text-gray-400 border border-transparent'">
                     <PanelRight class="w-5 h-5" />
                 </button>
            </div>
        </header>

        <!-- Chat Content -->
        <div class="flex-1 overflow-auto p-6 md:p-10 space-y-10 scroll-smooth custom-scrollbar" ref="scrollContainer">
            <!-- Empty State -->
            <transition name="fade">
                <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center pb-20">
                    <div class="w-20 h-20 rounded-3xl bg-gradient-to-tr from-[#bd34fe]/20 to-[#41d1ff]/20 flex items-center justify-center mb-8 border border-white/10 backdrop-blur-xl relative">
                        <div class="absolute inset-0 bg-white/5 blur-xl rounded-full animate-pulse"></div>
                        <Bot class="w-10 h-10 text-white relative z-10" />
                    </div>
                    <h1 class="text-4xl font-black text-white mb-4 tracking-tighter">How can I assist you?</h1>
                    <p class="text-gray-500 max-w-sm text-center text-lg leading-relaxed mb-10 font-medium">
                        Explore your data, automate tasks, or just chat with our world-class AI agent.
                    </p>
                    
                    <div class="grid grid-cols-2 gap-6 max-w-2xl w-full">
                        <button @click="quickAction('Show me pending Sales Orders')" class="p-5 rounded-2xl bg-white/2 hover:bg-white/5 border border-white/5 hover:border-[#bd34fe]/40 transition-all text-left group">
                            <div class="text-sm font-bold text-white mb-2 group-hover:text-[#bd34fe]">List Pending Orders</div>
                            <div class="text-xs text-gray-500 leading-relaxed">Search for Sales Orders with a 'Pending' status across the system.</div>
                        </button>
                        <button @click="quickAction('What is the current system status?')" class="p-5 rounded-2xl bg-white/2 hover:bg-white/5 border border-white/5 hover:border-[#41d1ff]/40 transition-all text-left group">
                            <div class="text-sm font-bold text-white mb-2 group-hover:text-[#41d1ff]">System Health</div>
                            <div class="text-xs text-gray-500 leading-relaxed">Get a quick overview of active agents and background processes.</div>
                        </button>
                    </div>
                </div>
            </transition>

            <!-- Messages -->
            <div v-for="(msg, idx) in filteredMessages" :key="idx" class="flex gap-6 group max-w-4xl mx-auto" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
               <div class="w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 shadow-2xl border border-white/10 transition-transform group-hover:scale-110"
                    :class="msg.role === 'user' ? 'bg-gradient-to-br from-[#bd34fe] to-[#7c3aed]' : 'bg-white/5'">
                  <User v-if="msg.role === 'user'" class="w-5 h-5 text-white" />
                  <Bot v-else-if="msg.role === 'assistant'" class="w-6 h-6 text-[#41d1ff]" />
               </div>
               <div class="max-w-[85%] space-y-2">
                   <div class="rounded-[24px] px-6 py-5 shadow-2xl relative transition-all"
                        :class="msg.role === 'user' ? 'bg-[#bd34fe]/15 text-white border border-[#bd34fe]/30 rounded-tr-sm' : 'bg-white/[0.05] text-gray-100 border border-white/10 rounded-tl-sm'">
                      
                      <!-- Edit Button for User Message -->
                       <button v-if="msg.role === 'user'" 
                               @click="editMessage(msg.content)"
                               class="absolute -left-10 top-2 p-2 text-gray-600 hover:text-white opacity-0 group-hover:opacity-100 transition-all"
                               title="Edit message">
                           <Edit3 class="w-4 h-4" />
                       </button>

                       <div v-if="msg.message_type === 'action'" class="mb-4">
                          <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#10b981]/10 border border-[#10b981]/20 text-[10px] font-bold uppercase tracking-wider text-[#10b981]">
                             <Cpu class="w-3.5 h-3.5" />
                             <span>Action Dispatched</span>
                          </div>
                          <div class="mt-2 font-mono text-[11px] text-emerald-400/80 bg-black/40 p-3 rounded-xl border border-emerald-500/10 group-hover:bg-black/60 transition-all">
                              <div v-for="action in parseActionData(msg)" :key="action.name" class="space-y-1">
                                  <div class="flex items-center gap-2">
                                      <span class="text-emerald-500 font-bold">{{ action.name }}</span>
                                      <span class="text-gray-600">-></span>
                                  </div>
                                  <div class="pl-4 opacity-70 truncate">{{ action.parameters }}</div>
                              </div>
                          </div>
                      </div>
                      
                      <div v-else class="prose prose-invert prose-sm max-w-none break-words leading-relaxed text-base" v-html="renderMarkdown(msg.content)"></div>
                   </div>
                   <div class="text-[9px] font-mono text-gray-600 uppercase tracking-widest px-2" :class="msg.role === 'user' ? 'text-right' : 'text-left'">
                       {{ formatDate(msg.creation) }}
                   </div>
                </div>
            </div>

            <!-- Ongoing Generation Indicator -->
            <div v-if="chat.loading" class="flex gap-6 group max-w-4xl mx-auto">
                <div class="w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 bg-white/5 border border-white/10 animate-pulse">
                    <Bot class="w-6 h-6 text-[#41d1ff]" />
                </div>
                <div class="max-w-[80%] space-y-2">
                    <div class="bg-white/[0.03] text-gray-200 border border-white/10 rounded-tl-sm rounded-[24px] px-6 py-5 flex items-center gap-3">
                         <div class="flex gap-1.5">
                             <div class="w-1.5 h-1.5 rounded-full bg-accent-purple animate-bounce" style="animation-delay: 0s"></div>
                             <div class="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-bounce" style="animation-delay: 0.2s"></div>
                             <div class="w-1.5 h-1.5 rounded-full bg-accent-purple animate-bounce" style="animation-delay: 0.4s"></div>
                         </div>
                         <span class="text-sm font-medium text-gray-500 italic">Thinking...</span>
                    </div>
                </div>
            </div>
            
            <div ref="bottomRef" class="h-4"></div>
        </div>

        <!-- Input Area -->
        <div class="p-8 w-full max-w-4xl mx-auto relative z-20">
            <div class="relative bg-white/[0.03] backdrop-blur-3xl rounded-[28px] border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.5)] overflow-hidden focus-within:border-[#bd34fe]/50 focus-within:ring-1 focus-within:ring-[#bd34fe]/30 transition-all duration-500">
                <textarea 
                    v-model="userInput"
                    @keydown.enter.prevent="handleEnter"
                    rows="1"
                    placeholder="Describe what you want to achieve..." 
                    class="w-full bg-transparent text-white placeholder-gray-600 px-7 py-5 focus:outline-none resize-none max-h-60 custom-scrollbar text-lg italic font-light"
                    style="min-height: 72px;"
                ></textarea>
                
                <div class="flex items-center justify-between px-5 pb-4">
                    <div class="flex items-center gap-2">
                        <button class="p-2.5 text-gray-500 hover:text-white hover:bg-white/5 rounded-xl transition-all group" title="Add context">
                            <Paperclip class="w-5 h-5 group-hover:rotate-12 transition-transform" />
                        </button>
                    </div>
                    <button @click="sendMessage" 
                            :disabled="!userInput.trim() || chat.loading"
                            class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#bd34fe] to-[#7c3aed] text-white hover:scale-105 active:scale-95 disabled:opacity-30 disabled:grayscale transition-all shadow-[0_0_20px_rgba(189,52,254,0.3)] flex items-center gap-2 font-bold text-sm tracking-tight text-white/90">
                        <span>Send Command</span>
                        <Send class="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
     </main>

     <!-- 3. RIGHT SIDEBAR -->
     <transition name="slide">
        <aside v-if="showArtifacts" class="w-[380px] border-l border-white/5 bg-black/20 backdrop-blur-3xl flex flex-col shrink-0 relative z-30 shadow-2xl">
            <div class="h-20 flex px-8 border-b border-white/5 space-x-6">
                <button @click="workspaceTab = 'context'" 
                        :class="[workspaceTab === 'context' ? 'text-white border-b-2 border-accent-purple' : 'text-gray-500']"
                        class="h-full text-[10px] font-black uppercase tracking-widest transition-all">Context</button>
                <button @click="workspaceTab = 'memory'" 
                        :class="[workspaceTab === 'memory' ? 'text-white border-b-2 border-accent-cyan' : 'text-gray-500']"
                        class="h-full text-[10px] font-black uppercase tracking-widest transition-all">Memory</button>
            </div>
            
            <div class="p-8 flex-1 overflow-auto custom-scrollbar space-y-8">
                <!-- Tab: Context -->
                <div v-if="workspaceTab === 'context'" class="space-y-4 animate-fade-in">
                    <h4 class="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">Environment</h4>
                    <div class="bg-white/[0.03] rounded-2xl p-5 border border-white/5 space-y-4 shadow-inner">
                        <div v-if="bridgeContext.route">
                            <div class="text-[9px] font-bold text-gray-500 uppercase mb-2">Active Route</div>
                            <div class="text-xs text-[#41d1ff] font-mono bg-black/40 p-2.5 rounded-xl border border-white/5 truncate">
                                {{ bridgeContext.route }}
                            </div>
                        </div>
                        <div v-if="bridgeContext.docname">
                            <div class="text-[9px] font-bold text-gray-500 uppercase mb-2">Target Document</div>
                            <div class="text-xs text-emerald-400 font-mono bg-black/40 p-2.5 rounded-xl border border-white/5 truncate">
                                {{ bridgeContext.docname }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tab: Memory -->
                <div v-if="workspaceTab === 'memory'" class="space-y-4 animate-fade-in">
                     <h4 class="text-[10px] font-black text-gray-600 uppercase tracking-[0.2em]">What I know about you</h4>
                     <div v-if="memories.data?.length" class="space-y-2">
                        <div v-for="mem in memories.data" :key="mem.name" class="p-4 rounded-xl bg-white/[0.03] border border-white/5 text-xs text-gray-300 italic flex items-start gap-3">
                             <Brain class="w-3.5 h-3.5 text-accent-purple shrink-0 mt-0.5" />
                             <span>{{ mem.content }}</span>
                        </div>
                     </div>
                     <div v-else class="text-center py-10 opacity-50">
                        <Brain class="w-8 h-8 mx-auto mb-2 text-gray-700" />
                        <p class="text-[10px] font-bold uppercase tracking-widest">No memories stored</p>
                     </div>
                </div>
            </div>

            <div class="p-6 border-t border-white/5">
                 <button @click="showArtifacts = false" class="w-full py-3 rounded-xl bg-white/5 text-gray-400 text-[10px] font-black uppercase tracking-widest hover:bg-white/10 transition-all">Close Workspace</button>
            </div>
        </aside>
     </transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch, h } from 'vue'
import { createResource } from 'frappe-ui'
import { 
    MessageSquare, Book, Brain, LayoutGrid, Plus, Search, Trash2, 
    Bot, User, Send, PanelLeftClose, PanelLeftOpen, Cpu, Loader2, 
    PanelRight, X, ChevronDown, Paperclip, Mic, Clock, Edit3, RefreshCw
} from 'lucide-vue-next'
import showdown from 'showdown'
import { useRouter, useRoute } from 'vue-router'
import { bridge } from '../utils/bridge'

const router = useRouter()
const route = useRoute()

// State
const activeTab = ref('chat')
const showArtifacts = ref(false)
const workspaceTab = ref('context')
const userInput = ref('')
const messages = ref([])
const currentConvId = ref(null)
const bridgeContext = ref({})
const scrollContainer = ref(null)

// Resources
const conversations = createResource({
    url: 'tb_owlai_core.api.router.get_conversations',
    auto: true
})

const chat = createResource({
    url: 'tb_owlai_core.api.router.handle_input_v2',
    onSuccess(data) {
        if (data.action_data) {
            messages.value.push({ 
                role: 'assistant', 
                content: typeof data.action_data === 'string' ? data.action_data : JSON.stringify(data.action_data), 
                message_type: 'action',
                action_data: data.action_data,
                creation: new Date().toISOString()
            })
            handleAction(data.action_data)
        }
        if (data.reply) messages.value.push({ role: 'assistant', content: data.reply, message_type: 'text', creation: new Date().toISOString() })
        if (data.conversation_id && !currentConvId.value) {
            currentConvId.value = data.conversation_id
            conversations.reload()
            router.replace({ query: { ...route.query, conversation: data.conversation_id } })
        }
        scrollToBottom()
        memories.reload() // Reload memories after interaction
    }
})

const historyResource = createResource({
    url: 'tb_owlai_core.api.router.get_conversation_messages',
    makeParams() { return { conversation_id: currentConvId.value } },
    onSuccess(data) {
        messages.value = data
        scrollToBottom()
    }
})

const memories = createResource({
    url: 'frappe.client.get_list',
    params: {
        doctype: 'OwlAI User Memory',
        fields: ['content', 'name'],
        limit: 10,
        order_by: 'creation desc'
    },
    auto: true
})

// Logic
const filteredMessages = computed(() => {
    return messages.value.filter(m => ['user', 'assistant'].includes(m.role))
})

const currentTitle = computed(() => {
    const c = conversations.data?.find(x => x.name === currentConvId.value)
    return c ? (c.title || c.name) : null
})

function editMessage(content) {
    userInput.value = content
}

function formatDate(d) {
    if(!d) return ''
    const dt = new Date(d)
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function startNewChat() {
    currentConvId.value = null
    messages.value = []
    router.replace({ query: { ...route.query, conversation: undefined } })
}

function handleEnter(e) {
    if (!e.shiftKey) sendMessage()
}

function sendMessage() {
    const text = userInput.value.trim()
    if (!text || chat.loading) return
    messages.value.push({ role: 'user', content: text, message_type: 'text', creation: new Date().toISOString() })
    userInput.value = ''
    scrollToBottom()
    
    chat.submit({
        text: text,
        conversation_id: currentConvId.value,
        context: bridgeContext.value
    })
}

function quickAction(text) {
    userInput.value = text
    sendMessage()
}


function handleAction(action_data) {
    const tools = Array.isArray(action_data) ? action_data : [action_data]
    tools.forEach(tool => {
        const actionName = tool.name || tool.tool_name
        const actionParams = tool.parameters || tool.tool_args || tool.arguments || {}
        if (!actionName) return

        // Direct navigation in standalone mode (not embedded in Desk)
        if (actionName === 'navigate' && !bridge.isEmbedded) {
            const doctype = actionParams.doctype || actionParams.parameters?.doctype
            if (doctype) {
                const slug = doctype.toLowerCase().replace(/ /g, '-')
                const docname = actionParams.docname || actionParams.parameters?.docname
                const url = docname ? `/app/${slug}/${docname}` : `/app/${slug}`
                window.location.href = window.location.origin + url
                return
            }
        }

        bridge.send('EXECUTE_ACTION', {
            action: actionName === 'navigate' ? 'navigate' : actionName,
            ...actionParams
        })
    })
}

function parseActionData(msg) {
    if (!msg) return []
    // 1. Try to use action_data object directly if available
    if (msg.action_data) {
        const tools = Array.isArray(msg.action_data) ? msg.action_data : [msg.action_data]
        return tools.map(t => ({
            name: t.name || t.tool_name || 'Action',
            parameters: JSON.stringify(t.parameters || t.arguments || t.tool_args || {})
        }))
    }
    
    // 2. Fallback to parsing content string
    try {
        const data = JSON.parse(msg.content)
        const tools = Array.isArray(data) ? data : [data]
        return tools.map(t => ({
            name: t.name || t.tool_name || 'Action',
            parameters: JSON.stringify(t.parameters || t.arguments || t.tool_args || {})
        }))
    } catch (e) {
        return [{ name: 'Action Error', parameters: msg.content || '' }]
    }
}

function loadConversation(id) {
    currentConvId.value = id
    router.replace({ query: { ...route.query, conversation: id } })
    historyResource.reload()
}

function deleteConversation(id) {
    if(!confirm('Delete this conversation?')) return
    createResource({
        url: 'tb_owlai_core.api.router.delete_conversation',
        onSuccess() { conversations.reload(); if(currentConvId.value === id) startNewChat() }
    }).submit({ conversation_id: id })
}

function renderMarkdown(text) {
    if (!text) return ''
    const cleanText = text
        .replace(/<thought>[\s\S]*?<\/thought>/g, '')
        .replace(/\{"name":\s*"[\w_]+",\s*"parameters":\s*\{[\s\S]*?\}\}/g, '')
        .trim()
    const conv = new showdown.Converter({ tables: true, simplifiedAutoLink: true, strikethrough: true })
    return conv.makeHtml(cleanText)
}

function scrollToBottom() {
    nextTick(() => {
        if (scrollContainer.value) {
            scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
        }
    })
}

// Lifecycle
onMounted(() => {
    if (route.query.conversation) loadConversation(route.query.conversation)
    window.addEventListener('message', (event) => {
        const { action, payload } = event.data
        if (action === 'UPDATE_CONTEXT') bridgeContext.value = payload
    })
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.5s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-enter-active, .slide-leave-active { transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-enter-from, .slide-leave-to { transform: translateX(100%); opacity: 0; }

.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.1); }

.animate-fade-in {
    animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
