<template>
  <div class="flex h-full">
     <!-- History Sidebar -->
     <div class="w-64 border-r border-white/5 p-4 flex flex-col hidden md:flex shrink-0 bg-black/20">
        <button @click="startNewChat" class="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-accent-purple text-white font-medium hover:bg-accent-purple/90 transition-all mb-4 shadow-lg shadow-accent-purple/20">
           <Plus class="w-4 h-4" />
           New Chat
        </button>

        <!-- Search Input -->
        <div class="relative mb-2">
            <input v-model="searchQuery" 
                   @input="searchConversations"
                   type="text" 
                   placeholder="Search history..." 
                   class="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-3 pr-8 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-accent-purple/50"
            />
            <Search class="w-4 h-4 text-gray-500 absolute right-2 top-2.5" />
        </div>

        <div class="flex-1 overflow-auto space-y-1 pr-2 custom-scrollbar">
            <h3 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 mt-2">History</h3>
            <div v-for="conv in conversations.data" :key="conv.name"
                 class="group relative p-3 rounded-xl hover:bg-white/5 cursor-pointer text-sm transition-all border border-transparent"
                 :class="currentConvId === conv.name ? 'bg-white/10 text-white border-white/10' : 'text-gray-400'"
                 @click="loadConversation(conv.name)">
                 
                 <div class="truncate pr-4">{{ conv.title || 'New Conversation' }}</div>

                 <!-- Delete Action (Visible on Hover) -->
                 <button @click.stop="deleteConversation(conv.name)" 
                         class="absolute right-2 top-2 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity p-1">
                     <Trash2 class="w-3.5 h-3.5" />
                 </button>
            </div>
        </div>
     </div>

     <!-- Chat Area -->
     <div class="flex-1 flex flex-col relative bg-transparent">
        
        <!-- Chat Header -->
        <div class="h-16 border-b border-white/5 flex items-center justify-between px-6 shrink-0 bg-white/5">
            <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-accent-purple to-pink-500 flex items-center justify-center shadow-lg shadow-accent-purple/20">
                     <Bot class="w-5 h-5 text-white" />
                </div>
                <div class="flex flex-col">
                    <h3 class="font-bold text-white text-sm">
                        {{ currentTitle || 'OwlAI Assistant' }}
                    </h3>
                    <span v-if="currentConvId" class="text-xs text-gray-500 font-mono">
                        {{ currentConvId }}
                    </span>
                </div>
            </div>
            
             <div class="flex items-center gap-2">
                 <button v-if="isEmbedded" @click="openFullView" class="p-2 hover:bg-white/5 rounded-lg text-gray-400 hover:text-white transition-colors" title="Open in Full View">
                     <ExternalLink class="w-4 h-4" />
                 </button>
                 <button @click="startNewChat" class="p-2 hover:bg-white/5 rounded-lg text-gray-400 hover:text-white transition-colors" title="New Chat">
                     <Plus class="w-4 h-4" />
                 </button>
             </div>
        </div>

        <div class="flex-1 overflow-auto p-6 space-y-6 scroll-smooth custom-scrollbar" ref="scrollContainer">
            <div v-if="messages.length === 0" class="h-full flex flex-col items-center justify-center text-center opacity-50 pb-20">
                <div class="w-20 h-20 rounded-2xl bg-gradient-to-tr from-accent-purple to-pink-500 flex items-center justify-center mb-6 shadow-2xl">
                    <Bot class="w-10 h-10 text-white" />
                </div>
                <h2 class="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">How can I help you?</h2>
            </div>
            
            <div v-for="(msg, idx) in messages" :key="idx" class="flex gap-4 group" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
               <div class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-lg gradient-border"
                    :class="msg.role === 'user' ? 'bg-accent-purple' : 'bg-secondary'">
                  <User v-if="msg.role === 'user'" class="w-4 h-4 text-white" />
                  <Bot v-else class="w-4 h-4 text-accent-cyan" />
               </div>
               
               <div class="max-w-[85%] rounded-2xl p-4 shadow-sm relative overflow-hidden"
                    :class="msg.role === 'user' ? 'bg-accent-purple/20 text-white rounded-tr-none border border-accent-purple/20' : 'bg-white/5 text-gray-200 rounded-tl-none border border-white/5'">
                  
                  <div v-if="msg.message_type === 'action'" class="mb-2">
                      <div class="text-xs font-mono uppercase text-gray-400 mb-1 flex items-center gap-2 border-b border-white/5 pb-1">
                         <Cpu class="w-3 h-3" />
                         Action
                      </div>
                      <code class="text-xs font-mono text-emerald-400 whitespace-pre-wrap break-all">{{ msg.content }}</code>
                  </div>
                  
                  <div v-else class="prose prose-invert prose-sm max-w-none break-words" v-html="renderMarkdown(msg.content)"></div>
               </div>
            </div>

            <div v-if="chat.loading" class="flex gap-4">
               <div class="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center shrink-0 shadow-lg border border-white/5">
                  <Bot class="w-4 h-4 text-accent-cyan" />
               </div>
               <div class="bg-white/5 rounded-2xl p-4 rounded-tl-none flex items-center gap-3 text-gray-400 border border-white/5">
                  <div class="flex gap-1">
                    <span class="w-2 h-2 bg-accent-cyan rounded-full animate-bounce"></span>
                    <span class="w-2 h-2 bg-accent-cyan rounded-full animate-bounce delay-100"></span>
                    <span class="w-2 h-2 bg-accent-cyan rounded-full animate-bounce delay-200"></span>
                  </div>
                  <span class="text-sm font-medium">Processing...</span>
               </div>
            </div>
            <div ref="bottomRef"></div>
        </div>

        <!-- Input Area -->
        <div class="p-6 pt-2 pb-6 w-full max-w-5xl mx-auto">
           <form @submit.prevent="sendMessage" class="relative group">
              <div class="absolute inset-0 bg-gradient-to-r from-accent-purple/20 to-accent-cyan/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity rounded-full"></div>
              <input v-model="userInput" 
                     type="text" 
                     placeholder="Ask OwlAI anything..." 
                     class="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-6 pr-14 text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-accent-purple/50 focus:border-accent-purple/50 transition-all font-medium shadow-2xl relative z-10"
                     :disabled="chat.loading"
              />
              <button type="submit" 
                      :disabled="!userInput.trim() || chat.loading"
                      class="absolute right-2 top-2 p-2 rounded-xl bg-accent-purple text-white hover:bg-accent-purple/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all z-20 shadow-lg">
                 <Send class="w-5 h-5" />
              </button>
           </form>
           <div class="text-center mt-2 text-xs text-gray-500">
              OwlAI Core v2.0 • Powered by TechBird
           </div>
        </div>
     </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import { createResource } from 'frappe-ui'
import { Plus, User, Bot, Send, Cpu, Loader2, MessageSquare, Search, Trash2, ExternalLink } from 'lucide-vue-next'
import showdown from 'showdown'
import { useRouter, useRoute } from 'vue-router'
import { bridge } from '../utils/bridge'
import debounce from 'lodash/debounce' // if available, or write custom

const router = useRouter()
const route = useRoute()
const userInput = ref('')
const messages = ref([])
const currentConvId = ref(null)
const scrollContainer = ref(null)
const bottomRef = ref(null)
const isEmbedded = bridge.isEmbedded
const searchQuery = ref('')
let searchTimeout = null

const currentTitle = computed(() => {
    if(!currentConvId.value || !conversations.data) return null
    const conv = conversations.data.find(c => c.name === currentConvId.value)
    return conv ? (conv.title || conv.name) : null
})

const converter = new showdown.Converter({
    tables: true,
    simplifiedAutoLink: true,
    strikethrough: true,
    tasklists: true
})

function renderMarkdown(text) {
    if(!text) return ''
    return converter.makeHtml(text)
}

// Conversations Resource (Auto load if standalone, manual if embedded)
const conversations = createResource({
    url: 'tb_owlai_core.api.router.get_conversations',
    auto: true
})

const searchConversations = () => {
    if(searchTimeout) clearTimeout(searchTimeout)
    searchTimeout = setTimeout(() => {
        conversations.submit({ search_text: searchQuery.value })
    }, 300)
}

const chat = createResource({
    url: 'tb_owlai_core.api.router.handle_input_v2',
    onSuccess(data) {
        if (data.reply) {
             messages.value.push({ role: 'assistant', content: data.reply, message_type: 'text' })
        }
        if (data.action) {
            handleAction(data)
        }
        if (data.conversation_id && !currentConvId.value) {
            currentConvId.value = data.conversation_id
            conversations.reload()
            router.replace({ query: { ...route.query, conversation: data.conversation_id } })
        }
    },
    onError(err) {
        messages.value.push({ role: 'assistant', content: "Error: " + (err.messages?.[0] || extractErrorMessage(err)), message_type: 'text' })
    }
})

function handleAction(data) {
    // 1. Send to Bridge for Desk execution
    bridge.send('EXECUTE_ACTION', {
        action: data.action,
        doctype: data.doctype,
        name: data.name,
        view: data.view,
        route_options: data.route_options || data.filters // flexible
    })

    // 2. Show feedback message
    let target = data.doctype
    if (data.name) target += "/" + data.name
    
    messages.value.push({ 
        role: 'assistant', 
        content: `Executing action: **${data.action}** on \`${target}\`...`, 
        message_type: 'text' 
    })
}

function extractErrorMessage(err) {
    try {
        if (typeof err === 'string') return err;
        return "An unknown error occurred."
    } catch (e) {
        return "An unknown error occurred."
    }
}

const historyResource = createResource({
    url: 'tb_owlai_core.api.router.get_conversation_messages',
    makeParams() {
        return { conversation_id: currentConvId.value }
    },
    onSuccess(data) {
        messages.value = data
        scrollToBottom()
    }
})

function loadConversation(id) {
    currentConvId.value = id
    router.replace({ query: { ...route.query, conversation: id } })
    historyResource.reload()
}

function startNewChat() {
    currentConvId.value = null
    messages.value = []
    router.replace({ query: { mode: isEmbedded ? 'embedded' : undefined } })
}

function openFullView() {
    window.open('/owlnest/chat', '_blank')
}

const deleteResource = createResource({
    url: 'tb_owlai_core.api.router.delete_conversation',
    onSuccess(data) {
        if(data.status === 'success') {
             if(currentConvId.value === deleteTargetId.value) {
                 startNewChat()
             }
             conversations.reload()
        } else {
             alert("Error deleting conversation")
        }
        deleteTargetId.value = null
    },
    onError(err) {
        alert("Error deleting conversation: " + extractErrorMessage(err))
        deleteTargetId.value = null
    }
})

let deleteTargetId = ref(null)

function deleteConversation(id) {
    if(!confirm("Are you sure you want to delete this conversation?")) return;
    deleteTargetId.value = id
    deleteResource.submit({ conversation_id: id })
}

function sendMessage() {
    const text = userInput.value
    if (!text) return
    
    messages.value.push({ role: 'user', content: text, message_type: 'text' })
    userInput.value = ''
    scrollToBottom()

    chat.submit({
        text: text,
        conversation_id: currentConvId.value,
        // Context handle by bridge or injected here if needed
    })
}

function scrollToBottom() {
    nextTick(() => {
        if(bottomRef.value) {
             bottomRef.value.scrollIntoView({ behavior: 'smooth' })
        }
    })
}

onMounted(() => {
    if (route.query.conversation) {
        loadConversation(route.query.conversation)
    }
    
    bridge.on('UPDATE_CONTEXT', (payload) => {
        console.log("OwlNest Bridge Context (Payload):", payload)
    })
})

watch(() => route.query.conversation, (newId) => {
    if (newId && newId !== currentConvId.value) {
        loadConversation(newId)
    }
})
</script>

<style>
/* ... (Global styles kept same, imported from index.css mostly) */
.prose { color: #e2e8f0; }
.prose strong { color: #fff; }
.prose a { color: #6C5DD3; }
.prose pre { background: rgba(0,0,0,0.3); border-radius: 0.5rem; }
.prose code { color: #00D2FF; }
</style>
