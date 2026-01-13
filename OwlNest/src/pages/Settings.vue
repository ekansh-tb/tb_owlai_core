<template>
  <div class="max-w-4xl mx-auto space-y-8 animate-fade-in-up">
    <div class="glass-panel p-8 rounded-2xl border border-white/5 shadow-2xl">
        <h3 class="text-xl font-bold mb-6 flex items-center gap-2 text-white">
            <Cpu class="w-6 h-6 text-accent-cyan" />
            AI Model Configuration
        </h3>
        
        <div class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <div class="space-y-2">
                     <label class="text-sm font-medium text-gray-400">Default Model</label>
                     <div class="relative">
                        <select v-model="settings.model" class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-1 focus:ring-accent-purple appearance-none cursor-pointer hover:bg-black/30 transition-colors">
                            <option value="qwen2.5:1.5b-ollama" class="bg-gray-800">qwen2.5:1.5b-ollama</option>
                            <option value="gpt-4o" class="bg-gray-800">gpt-4o</option>
                            <option value="claude-3-5-sonnet" class="bg-gray-800">claude-3-5-sonnet</option>
                        </select>
                        <div class="absolute right-4 top-3.5 pointer-events-none text-gray-400">▼</div>
                     </div>
                 </div>
                 <div class="space-y-2">
                     <label class="text-sm font-medium text-gray-400">Temperature ({{ temperature }})</label>
                     <input v-model="temperature" type="range" min="0" max="1" step="0.1" class="w-full accent-accent-purple mt-3 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer" />
                     <div class="flex justify-between text-xs text-gray-500 font-medium">
                        <span>Precise (0.0)</span>
                        <span>Creative (1.0)</span>
                     </div>
                 </div>
            </div>
        </div>
    </div>

    <div class="glass-panel p-8 rounded-2xl border border-white/5 shadow-2xl">
        <h3 class="text-xl font-bold mb-6 flex items-center gap-2 text-white">
            <Sliders class="w-6 h-6 text-accent-purple" />
            System Instructions
        </h3>
        
        <div class="space-y-4">
             <div class="space-y-2">
                 <label class="text-sm font-medium text-gray-400">Custom System Prompt Additions</label>
                 <textarea rows="5" class="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:ring-1 focus:ring-accent-purple resize-none placeholder-gray-600 transition-all focus:bg-black/30" placeholder="Enter custom rules for your agent here... e.g. 'Always answer in potential haiku'"></textarea>
                 <p class="text-xs text-gray-500">These instructions will be appended to the core OwlAI system prompt.</p>
             </div>
             
             <div class="flex items-center gap-4 pt-4 border-t border-white/5 mt-6">
                 <button class="px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 transition-all border border-white/10 hover:border-white/20">Discard</button>
                 <button class="px-6 py-2.5 rounded-xl bg-accent-purple hover:bg-accent-purple/90 text-white font-medium shadow-lg hover:shadow-accent-purple/20 transition-all transform active:scale-95">Save Changes</button>
             </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Cpu, Sliders } from 'lucide-vue-next'

const settings = ref({
    model: 'qwen2.5:1.5b-ollama'
})
const temperature = ref(0.7)
</script>

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
