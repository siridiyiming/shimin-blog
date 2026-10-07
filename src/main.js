import { createApp, nextTick } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import App from './App.vue';
import Home from './pages/Home.vue';
import Library from './pages/Library.vue';
import Detail from './pages/Detail.vue';
import Board from './pages/Board.vue';
import './style.css';
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home },
    ...['games', 'knowledge', 'tools', 'search'].map(path => ({ path: '/' + path, component: Library })),
    { path: '/content/:id', component: Detail },
    { path: '/board', component: Board },
    { path: '/admin/:section?', component: () => import('./pages/Admin.vue') },
    { path: '/:pathMatch(.*)*', component: Detail }
  ],
  async scrollBehavior(to, from, saved) { await nextTick(); return saved || (to.hash ? { el: to.hash, top: 100 } : { top: 0 }); }
});
createApp(App).use(router).mount('#app');
