<template>
  <main class="not-found">
    <span class="not-found__code">404</span>
    <h1>{{ $t("notFound.title") }}</h1>
    <p>{{ $t("notFound.body") }}</p>
    <RouterLink class="button button--primary" to="/">
      {{ $t("common.home") }}
    </RouterLink>
  </main>
</template>
