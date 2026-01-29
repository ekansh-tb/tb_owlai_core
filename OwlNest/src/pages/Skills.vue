<template>
  <div class="max-w-7xl mx-auto space-y-8 pb-20 animate-fade-in px-4 md:px-0">
    <header class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-black text-white tracking-tight">Skills Hub</h1>
        <p class="text-gray-500 font-medium">Manage and discover capabilities for your agents.</p>
      </div>
      <button @click="showCreateModal = true" class="px-6 py-3 rounded-xl bg-accent-purple text-white font-bold hover:bg-accent-purple/90 transition-all flex items-center gap-2">
        <Plus class="w-5 h-5" />
        <span>Create Skill</span>
      </button>
    </header>

    <div v-if="tools.loading" class="py-20 flex justify-center">
        <div class="animate-spin w-8 h-8 border-2 border-accent-purple border-t-transparent rounded-full"></div>
    </div>
    
    <div v-else-if="tools.data && tools.data.length" class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div v-for="tool in tools.data" :key="tool.name" class="glass-panel p-6 rounded-3xl border border-white/5 hover:border-white/20 transition-all group flex flex-col justify-between h-64">
        <div>
            <div class="flex items-start justify-between mb-4">
            <div class="p-3 rounded-2xl bg-white/5 border border-white/10 text-accent-cyan">
                <Wrench class="w-6 h-6" />
            </div>
            <div class="px-3 py-1 rounded-full bg-white/5 text-[10px] font-bold uppercase tracking-widest text-gray-400">
                {{ tool.type || 'Python Method' }}
            </div>
            </div>
            <h3 class="text-lg font-bold text-white mb-2 line-clamp-1">{{ tool.tool_name }}</h3>
            <p class="text-sm text-gray-500 leading-relaxed line-clamp-2">{{ tool.method_path || 'No path configured.' }}</p>
        </div>
        
        <div class="mt-6 flex items-center gap-3">
             <button @click="openTool(tool.name)" class="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-bold text-white transition-all">Edit Configuration</button>
             <button @click="deleteTool(tool.name)" class="p-3 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-all opacity-0 group-hover:opacity-100">
                <Trash2 class="w-4 h-4" />
             </button>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-20">
        <p class="text-gray-500">No skills found. Create one to get started.</p>
    </div>
    
    <Dialog v-model="showCreateModal" :options="{ title: 'Create New Skill' }">
      <template #body-content>
        <div class="space-y-4">
           <div>
             <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Tool Name</label>
             <input v-model="newTool.tool_name" type="text" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all" placeholder="e.g. Web Search" />
           </div>
           <div>
             <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Type</label>
             <select v-model="newTool.type" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all appearance-none cursor-pointer">
                <option value="Python Method">Python Method</option>
                <option value="API Call">API Call (Coming Soon)</option>
                <option value="Workflow">Workflow (Coming Soon)</option>
             </select>
           </div>
           
           <div v-if="newTool.type === 'Python Method'">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">Method Path</label>
              <input v-model="newTool.method_path" type="text" class="w-full bg-gray-100 border border-transparent focus:bg-white focus:border-gray-300 rounded-lg px-3 py-2 text-sm transition-all" placeholder="e.g. frappe.utils.now" />
              <p class="text-[10px] text-gray-500 mt-1">Dotted path to a whitelisted python function.</p>
           </div>
        </div>
      </template>
      <template #actions>
        <Button @click="createTool" :loading="creating" variant="solid">Create Skill</Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { createResource, Dialog, Button, call } from 'frappe-ui'
import { Plus, Wrench, Trash2 } from 'lucide-vue-next'

const showCreateModal = ref(false)
const creating = ref(false)
const newTool = reactive({
    tool_name: '',
    type: 'Python Method',
    method_path: ''
})

const tools = createResource({
    url: 'frappe.client.get_list',
    params: {
        doctype: 'OwlAI Tool',
        fields: ['name', 'tool_name', 'type', 'method_path'],
        limit: 50,
        order_by: 'creation desc'
    },
    auto: true
})

async function createTool() {
    if (!newTool.tool_name) return alert('Name required')
    if (newTool.type === 'Python Method' && !newTool.method_path) return alert('Method path required')

    creating.value = true
    try {
        await call('frappe.client.insert', {
            doc: {
                doctype: 'OwlAI Tool',
                tool_name: newTool.tool_name,
                type: newTool.type,
                method_path: newTool.method_path
            }
        })
        showCreateModal.value = false
        newTool.tool_name = ''
        newTool.type = 'Python Method'
        newTool.method_path = ''
        tools.reload()
    } catch (e) {
        console.error(e)
        // Extract inner message if possible
        let msg = 'Failed to create tool'
        if (e.messages && e.messages.length) msg = e.messages.join(', ')
        else if (e.message) msg = e.message
        
        alert(msg)
    } finally {
        creating.value = false
    }
}

async function deleteTool(name) {
    if(!confirm('Are you sure you want to delete this tool?')) return
    try {
        await call('frappe.client.delete', { doctype: 'OwlAI Tool', name })
        tools.reload()
    } catch(e) {
        console.error(e)
        alert('Failed to delete tool')
    }
}

function openTool(name) {
    const baseUrl = window.location.origin;
    window.open(`${baseUrl}/app/owlai-tool/${name}`, '_blank');
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
