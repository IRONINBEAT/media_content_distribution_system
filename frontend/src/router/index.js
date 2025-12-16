import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import DevicesView from '../views/DevicesView.vue'
import FilesView from '../views/FilesView.vue'
import { isAuthenticated } from '../store/auth'

const routes = [
  { path: '/login', component: LoginView },
  { path: '/', component: DashboardView, meta: { auth: true } },
  { path: '/devices', component: DevicesView, meta: { auth: true } },
  { path: '/files', component: FilesView, meta: { auth: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.auth && !isAuthenticated()) {
    next('/login')
  } else {
    next()
  }
})

export default router