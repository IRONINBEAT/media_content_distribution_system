<template>
  <div class="card">
    <h2>Вход</h2>
    <input v-model="token" placeholder="Токен пользователя" />
    <button @click="submit">Войти</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { login } from '../store/auth'
import { useRouter } from 'vue-router'

const token = ref('')
const router = useRouter()

function submit() {
  login(token.value)
  router.push('/')
}
</script>