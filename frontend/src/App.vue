<script setup lang="ts">
import { onMounted, ref } from "vue";

const apiStatus = ref("Checking API");

onMounted(async () => {
  try {
    const response = await fetch("/api/v1/health");
    apiStatus.value = response.ok ? "API connected" : "API unavailable";
  } catch {
    apiStatus.value = "API unavailable";
  }
});
</script>

<template>
  <main class="launchpad">
    <section class="panel" aria-labelledby="title">
      <p class="eyebrow">Self-hosted trading journal</p>
      <h1 id="title">Tradefog</h1>
      <p class="summary">
        Build the context, define the risk, then record the decision.
      </p>
      <p class="status" role="status">{{ apiStatus }}</p>
    </section>
  </main>
</template>
