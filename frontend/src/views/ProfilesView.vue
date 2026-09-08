<script setup lang="ts">
import AppShell from "@/layouts/AppShell.vue";
import ProfileWorkspace from "@/features/profiles/ProfileWorkspace.vue";
</script>

<template>
  <AppShell>
    <div class="workspace profile-workspace">
      <header class="catalog-heading">
        <h1>{{ $t("profiles.title") }}</h1>
      </header>
      <ProfileWorkspace />
    </div>
  </AppShell>
</template>
