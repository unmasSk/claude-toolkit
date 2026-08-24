### Nuxt 3

#### Recommended Stack
```
Version:        3.x
Auto-imports:   Enabled
Styling:        @nuxtjs/tailwindcss
State:          Pinia (@pinia/nuxt)
API:            Nitro server routes
```

#### Project Structure
```
my-nuxt-app/
├── assets/
├── components/
├── composables/
├── layouts/
├── middleware/
├── pages/
├── plugins/
├── public/
├── server/
│   ├── api/
│   └── middleware/
├── stores/
├── app.vue
├── nuxt.config.ts
└── package.json
```

#### Auto-imports

Nuxt auto-imports Vue functions and composables:

```vue
<script setup lang="ts">
// No imports needed!
const count = ref(0);
const route = useRoute();
const { data } = await useFetch('/api/users');
</script>
```
