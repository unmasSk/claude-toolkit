### Vue 3

#### Recommended Stack
```
Build Tool:     Vite
Language:       TypeScript
API Style:      Composition API
State:          Pinia
Routing:        Vue Router 4
Styling:        Tailwind CSS or UnoCSS
Testing:        Vitest + Vue Test Utils
```

#### Project Structure
```
my-vue-app/
├── src/
│   ├── components/
│   │   ├── common/
│   │   └── features/
│   ├── composables/         # Composition API utilities
│   ├── views/               # Page components
│   ├── stores/              # Pinia stores
│   ├── router/
│   ├── types/
│   ├── assets/
│   ├── App.vue
│   └── main.ts
├── public/
├── tests/
├── vite.config.ts
├── tsconfig.json
└── package.json
```

#### Composition API Patterns

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useUserStore } from '@/stores/user';

// Reactive state
const count = ref(0);
const doubled = computed(() => count.value * 2);

// Store
const userStore = useUserStore();

// Lifecycle
onMounted(() => {
  userStore.fetchUsers();
});
</script>

<template>
  <div>
    <p>Count: {{ count }}</p>
    <p>Doubled: {{ doubled }}</p>
  </div>
</template>
```

#### Pinia Store Pattern

```typescript
// stores/user.ts
import { defineStore } from 'pinia';

interface User {
  id: string;
  name: string;
}

export const useUserStore = defineStore('user', {
  state: () => ({
    users: [] as User[],
    loading: false,
  }),

  getters: {
    userCount: (state) => state.users.length,
  },

  actions: {
    async fetchUsers() {
      this.loading = true;
      try {
        const response = await fetch('/api/users');
        this.users = await response.json();
      } finally {
        this.loading = false;
      }
    },
  },
});
```
