import { createRouter, createWebHistory } from 'vue-router'
import { session } from './data/session'

const routes = [
	{
		path: '/',
		name: 'Dashboard',
		component: () => import('./pages/Dashboard.vue'),
		meta: { requiresAuth: true }
	},
	{
		path: '/chat',
		name: 'Chat',
		component: () => import('./pages/Chat.vue'),
		meta: { requiresAuth: true }
	},
	{
		path: '/settings',
		name: 'Settings',
		component: () => import('./pages/Settings.vue'),
		meta: { requiresAuth: true }
	},
	{
		path: '/skills',
		name: 'Skills',
		component: () => import('./pages/Skills.vue'),
		meta: { requiresAuth: true }
	},
	{
		path: '/login',
		name: 'Login',
		component: () => import('./pages/Login.vue')
	}
]

const router = createRouter({
	history: createWebHistory('/owlnest'),
	routes
})

router.beforeEach(async (to, from, next) => {
	let isLoggedIn = session.isLoggedIn
	try {
		if (!isLoggedIn) {
			await session.login()
			isLoggedIn = session.isLoggedIn
		}
	} catch (error) {
		isLoggedIn = false
	}

	if (to.meta.requiresAuth && !isLoggedIn) {
		next('/login')
	} else if (to.name === 'Login' && isLoggedIn) {
		next('/')
	} else {
		next()
	}
})

export default router
