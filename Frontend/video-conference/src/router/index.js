import { createRouter, createWebHashHistory } from 'vue-router'
import TestView from "@/views/TestView.vue";
import videoConference from "@/views/VideoConference.vue";

const routes = [
  {
    path: '/videoConference',
    name: 'videoConference',
    component: videoConference
  },
  {
    path: '/test',
    name: 'TestView',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: TestView
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
