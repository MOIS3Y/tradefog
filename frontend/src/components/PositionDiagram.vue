<template>
  <div class="position-diagram" aria-hidden="true">
    <div class="position-diagram__header">
      <span>LONG / 1:3</span>
      <span class="position-diagram__status">PLANNED</span>
    </div>
    <svg viewBox="0 0 220 112" preserveAspectRatio="none">
      <rect
        class="position-diagram__profit"
        x="8"
        y="10"
        width="174"
        height="63"
      />
      <rect
        class="position-diagram__risk"
        x="8"
        y="73"
        width="174"
        height="21"
      />
      <line class="position-diagram__take" x1="8" y1="10" x2="182" y2="10" />
      <line class="position-diagram__entry" x1="8" y1="73" x2="182" y2="73" />
      <line class="position-diagram__stop" x1="8" y1="94" x2="182" y2="94" />
      <path
        class="position-diagram__price"
        d="M8 82L27 78L43 84L61 70L78 74L97 56L115 62L134 43L151 49L168 29L182 34"
      />
      <circle class="position-diagram__point" cx="97" cy="56" r="3" />
      <text x="190" y="13">TP</text>
      <text x="190" y="76">ENTRY</text>
      <text x="190" y="97">SL</text>
    </svg>
  </div>
</template>
