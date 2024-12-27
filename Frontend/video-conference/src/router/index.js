import { createRouter, createWebHashHistory } from 'vue-router'
import TestView from "@/views/TestView.vue";
import videoConference from "@/views/VideoConference.vue";
import testAudio from "@/views/testAudio.vue";

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
  },
  {
    path: '/testAudio',
    name: 'testAudio',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: testAudio
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
