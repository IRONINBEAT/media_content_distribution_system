<template>
  <div>
    <h2>Файлы</h2>
    <table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Описание</th>
      <th>Действия</th>
    </tr>
  </thead>
  <tbody>
    <tr v-for="f in files" :key="f.id">
      <td>{{ f.file_id }}</td>
      <td>{{ f.description }}</td>
      <td>
        <button @click="remove(f.id)">Удалить</button>
      </td>
    </tr>
  </tbody>
</table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'

const files = ref([])

onMounted(async () => {
  const res = await api.get('/api/admin/files')
  files.value = res.data
})

async function remove(id) {
  await api.delete(`/api/admin/files/${id}`)
  location.reload()
}
</script>