<template>
  <div>
    <h2>Устройства</h2>
    <table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Статус</th>
      <th>Действия</th>
    </tr>
  </thead>
  <tbody>
    <tr v-for="d in devices" :key="d.id">
      <td>{{ d.device_id }}</td>
      <td>{{ d.status }}</td>
      <td>
        <button @click="activate(d.id)">Активировать</button>
        <button @click="remove(d.id)">Удалить</button>
      </td>
    </tr>
  </tbody>
</table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'
import { getToken } from '../store/auth'

const devices = ref([])

onMounted(async () => {
  const res = await api.get('/api/admin/devices')
  devices.value = res.data
})

async function setStatus(id, status) {
  await api.patch(`/api/admin/devices/${id}`, { status })
  location.reload()
}
</script>